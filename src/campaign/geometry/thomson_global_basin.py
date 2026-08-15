#!/usr/bin/env python3
"""Bounded topology-changing basin campaign for Thomson n=282.

This search uses only a saved public snapshot and an independent implementation
of the stated Coulomb objective.  It does not execute downloaded verifier code.
The seed families deliberately alter the incumbent Delaunay/contact topology
before tangent-space relaxation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.spatial import ConvexHull

SLUG = "thomson-problem"
COUNT = 282
LEADER_SOLUTION_ID = 561
DEFAULT_SNAPSHOT = (
    Path(__file__).parent / "snapshots" / "thomson-problem_20260814T234236Z.json"
)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_event(path: Path, **event: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def normalize(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    if points.shape != (COUNT, 3) or not np.isfinite(points).all():
        raise ValueError("expected 282 finite three-dimensional points")
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    if np.any(norms < 1e-12):
        raise ValueError("zero or near-zero point")
    return points / norms


def energy_gradient(points: np.ndarray) -> tuple[float, np.ndarray]:
    differences = points[:, None, :] - points[None, :, :]
    distances = np.linalg.norm(differences, axis=2)
    np.fill_diagonal(distances, np.inf)
    inverse = 1.0 / distances
    energy = float(np.triu(inverse, 1).sum())
    gradient = -(differences * inverse[:, :, None] ** 3).sum(axis=1)
    return energy, gradient


def point_energies(points: np.ndarray) -> np.ndarray:
    differences = points[:, None, :] - points[None, :, :]
    distances = np.linalg.norm(differences, axis=2)
    np.fill_diagonal(distances, np.inf)
    return np.sum(1.0 / distances, axis=1)


def tangent_basis(points: np.ndarray) -> np.ndarray:
    basis = np.empty((COUNT, 2, 3))
    axes = np.eye(3)
    for index, point in enumerate(points):
        reference = axes[np.argmin(np.abs(point))]
        first = np.cross(point, reference)
        first /= np.linalg.norm(first)
        second = np.cross(point, first)
        basis[index, 0] = first
        basis[index, 1] = second
    return basis


def map_parameters(
    parameters: np.ndarray, base: np.ndarray, basis: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    tangent = parameters.reshape(COUNT, 2)
    raw = base + np.einsum("nik,ni->nk", basis, tangent)
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    return raw / norms, norms


def objective(
    parameters: np.ndarray, base: np.ndarray, basis: np.ndarray
) -> tuple[float, np.ndarray]:
    points, norms = map_parameters(parameters, base, basis)
    energy, gradient = energy_gradient(points)
    tangent_gradient = (
        gradient - np.sum(gradient * points, axis=1, keepdims=True) * points
    )
    raw_gradient = tangent_gradient / norms
    parameter_gradient = np.einsum("nik,nk->ni", basis, raw_gradient)
    return energy, parameter_gradient.ravel()


def relax(
    points: np.ndarray, rounds: int, maxiter: int
) -> tuple[np.ndarray, dict[str, object]]:
    current = normalize(points)
    iterations = 0
    evaluations = 0
    messages = []
    for _ in range(rounds):
        basis = tangent_basis(current)
        result = minimize(
            objective,
            np.zeros(2 * COUNT),
            args=(current, basis),
            method="L-BFGS-B",
            jac=True,
            options={
                "maxiter": maxiter,
                "maxfun": maxiter * 3,
                "maxls": 60,
                "maxcor": 30,
                "ftol": 0.0,
                "gtol": 1e-11,
            },
        )
        current = normalize(map_parameters(result.x, current, basis)[0])
        iterations += int(result.nit)
        evaluations += int(result.nfev)
        messages.append(str(result.message))
    energy, gradient = energy_gradient(current)
    tangent = gradient - np.sum(gradient * current, axis=1, keepdims=True) * current
    return current, {
        "energy": energy,
        "iterations": iterations,
        "evaluations": evaluations,
        "projected_gradient_max": float(np.max(np.linalg.norm(tangent, axis=1))),
        "projected_gradient_total": float(np.linalg.norm(tangent)),
        "messages": messages,
    }


def delaunay_data(
    points: np.ndarray,
) -> tuple[np.ndarray, set[tuple[int, int]], np.ndarray]:
    faces = np.asarray(ConvexHull(points).simplices, dtype=np.int64)
    edges: set[tuple[int, int]] = set()
    for a, b, c in faces:
        edges.add(tuple(sorted((int(a), int(b)))))
        edges.add(tuple(sorted((int(a), int(c)))))
        edges.add(tuple(sorted((int(b), int(c)))))
    degrees = np.zeros(COUNT, dtype=np.int64)
    for a, b in edges:
        degrees[a] += 1
        degrees[b] += 1
    return faces, edges, degrees


def topology_summary(points: np.ndarray) -> dict[str, object]:
    faces, edges, degrees = delaunay_data(points)
    defect_indices = np.flatnonzero(degrees != 6)
    neighbors: list[list[int]] = [[] for _ in range(COUNT)]
    for first, second in edges:
        neighbors[first].append(second)
        neighbors[second].append(first)
    colors = [str(int(degree)) for degree in degrees]
    refinement_history = []
    for _ in range(10):
        colors = [
            hashlib.sha256(
                (
                    colors[index]
                    + "|"
                    + ",".join(sorted(colors[item] for item in neighbors[index]))
                ).encode()
            ).hexdigest()
            for index in range(COUNT)
        ]
        refinement_history.append(sorted(colors))
    digest = hashlib.sha256(
        json.dumps(refinement_history, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "face_count": int(faces.shape[0]),
        "edge_count": len(edges),
        "degree_histogram": {
            str(k): int(v) for k, v in sorted(Counter(degrees).items())
        },
        "defect_count": int(defect_indices.size),
        "defect_indices": defect_indices.tolist(),
        "graph_wl_hash": digest,
    }


def rodrigues(points: np.ndarray, axis: np.ndarray, angle: float) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    cosine = np.cos(angle)
    sine = np.sin(angle)
    return (
        points * cosine
        + np.cross(axis, points) * sine
        + np.outer(points @ axis, axis) * (1.0 - cosine)
    )


def cap_transport(
    points: np.ndarray,
    center_index: int,
    target_index: int,
    cap_size: int,
    angle: float,
) -> np.ndarray:
    center = points[center_index]
    target = points[target_index]
    axis = np.cross(center, target)
    if np.linalg.norm(axis) < 1e-12:
        raise ValueError("degenerate cap-transport axis")
    selected = np.argsort(points @ center)[-cap_size:]
    candidate = points.copy()
    candidate[selected] = rodrigues(candidate[selected], axis, angle)
    return normalize(candidate)


def triangle_holes(
    points: np.ndarray, faces: np.ndarray
) -> list[tuple[float, np.ndarray, tuple[int, int, int]]]:
    holes = []
    for face in faces:
        center = np.sum(points[face], axis=0)
        center /= np.linalg.norm(center)
        clearance = float(np.min(np.linalg.norm(points - center, axis=1)))
        holes.append((clearance, center, tuple(int(value) for value in face)))
    return sorted(holes, key=lambda item: item[0], reverse=True)


def vacancy_interstitial(
    points: np.ndarray, source: int, target: np.ndarray
) -> np.ndarray:
    candidate = points.copy()
    candidate[source] = target
    return normalize(candidate)


def edge_opposites(faces: np.ndarray) -> dict[tuple[int, int], list[int]]:
    opposites: dict[tuple[int, int], list[int]] = defaultdict(list)
    for a, b, c in faces:
        opposites[tuple(sorted((int(a), int(b))))].append(int(c))
        opposites[tuple(sorted((int(a), int(c))))].append(int(b))
        opposites[tuple(sorted((int(b), int(c))))].append(int(a))
    return opposites


def bond_flip_seed(
    points: np.ndarray,
    edge: tuple[int, int],
    opposite: tuple[int, int],
    fraction: float,
) -> np.ndarray:
    a, b = edge
    c, d = opposite
    candidate = points.copy()
    # Contract the alternate diagonal c-d while expanding the old diagonal a-b.
    candidate[c] = normalize_row((1.0 - fraction) * points[c] + fraction * points[d])
    candidate[d] = normalize_row((1.0 - fraction) * points[d] + fraction * points[c])
    candidate[a] = normalize_row((1.0 + fraction) * points[a] - fraction * points[b])
    candidate[b] = normalize_row((1.0 + fraction) * points[b] - fraction * points[a])
    return normalize(candidate)


def normalize_row(row: np.ndarray) -> np.ndarray:
    return row / np.linalg.norm(row)


def load_snapshot(path: Path) -> tuple[dict[str, Any], np.ndarray]:
    with path.open(encoding="utf-8") as handle:
        snapshot = json.load(handle)
    verifier_hash = hashlib.sha256(snapshot["problem"]["verifier"].encode()).hexdigest()
    if verifier_hash != snapshot["verifier_sha256"]:
        raise ValueError("snapshot verifier hash mismatch")
    leader = next(
        item for item in snapshot["solutions"] if item["id"] == LEADER_SOLUTION_ID
    )
    return snapshot, normalize(np.asarray(leader["data"]["vectors"], dtype=np.float64))


def generate_trials(
    snapshot: dict[str, Any], leader: np.ndarray, rng: np.random.Generator, limit: int
) -> list[tuple[str, dict[str, object], np.ndarray]]:
    trials: list[tuple[str, dict[str, object], np.ndarray]] = []
    faces, edges, degrees = delaunay_data(leader)
    defects = np.flatnonzero(degrees == 5)
    regular = np.flatnonzero(degrees == 6)
    stresses = point_energies(leader)

    # Distinct public local minima supply already-relaxed alternate defect graphs.
    for solution in snapshot["solutions"]:
        if int(solution["id"]) in (1076, 663, 1185, 1108, 645):
            trials.append(
                (
                    "public_basin",
                    {
                        "solution_id": int(solution["id"]),
                        "agent": solution["agentName"],
                    },
                    normalize(
                        np.asarray(solution["data"]["vectors"], dtype=np.float64)
                    ),
                )
            )

    # Translate a rigid cap containing a pentagonal defect toward a nearby
    # regular site.  Angles are contact-scale rather than microscopic.
    for index, defect in enumerate(defects):
        neighbors = regular[np.argsort(leader[regular] @ leader[defect])[-8:]]
        target = int(neighbors[-1 - (index % min(4, neighbors.size))])
        cap_size = (7, 13, 19, 31)[index % 4]
        angle = (0.035, 0.06, 0.095)[index % 3]
        trials.append(
            (
                "defect_cap_transport",
                {
                    "center": int(defect),
                    "target": target,
                    "cap_size": cap_size,
                    "angle": angle,
                },
                cap_transport(leader, int(defect), target, cap_size, angle),
            )
        )

    # Vacancy/interstitial surgery moves high-stress points into the largest
    # triangular holes, creating explicit 5/7 defect pairs.
    holes = triangle_holes(leader, faces)
    sources = list(np.argsort(stresses)[-8:][::-1]) + list(defects[:4])
    for index, source in enumerate(sources):
        for hole in holes:
            if int(source) not in hole[2]:
                break
        trials.append(
            (
                "vacancy_interstitial",
                {
                    "source": int(source),
                    "face": list(hole[2]),
                    "initial_clearance": hole[0],
                },
                vacancy_interstitial(leader, int(source), hole[1]),
            )
        )

    # Force selected Delaunay edge flips, prioritizing long edges and edges
    # incident to a pentagonal defect.
    opposites = edge_opposites(faces)
    eligible = [edge for edge in edges if len(opposites[edge]) == 2]
    eligible.sort(
        key=lambda edge: (
            degrees[edge[0]] != 6 or degrees[edge[1]] != 6,
            np.linalg.norm(leader[edge[0]] - leader[edge[1]]),
        ),
        reverse=True,
    )
    for index, edge in enumerate(eligible[:12]):
        fraction = (0.08, 0.14, 0.22)[index % 3]
        opposite = tuple(opposites[edge])
        trials.append(
            (
                "bond_flip",
                {"edge": list(edge), "opposite": list(opposite), "fraction": fraction},
                bond_flip_seed(leader, edge, opposite, fraction),
            )
        )

    # Low-frequency, contact-scale kicks are controls, retained only when they
    # actually change the incumbent triangulation.
    leader_edges = edges
    for scale in (0.025, 0.04, 0.06, 0.09):
        for repeat in range(3):
            candidate = normalize(leader + rng.normal(scale=scale, size=leader.shape))
            _, candidate_edges, _ = delaunay_data(candidate)
            if candidate_edges != leader_edges:
                trials.append(
                    (
                        "topology_changing_kick",
                        {"scale": scale, "repeat": repeat},
                        candidate,
                    )
                )

    return trials[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    parser.add_argument("--stamp")
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--trial-limit", type=int, default=48)
    parser.add_argument("--relax-rounds", type=int, default=2)
    parser.add_argument("--maxiter", type=int, default=700)
    args = parser.parse_args()

    snapshot, leader = load_snapshot(args.snapshot)
    problem = snapshot["problem"]
    live_score = float(snapshot["solutions"][0]["score"])
    target = live_score - float(problem["minImprovement"])
    verifier_hash = snapshot["verifier_sha256"]
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_json(run_dir / "seed.json", {"vectors": leader.tolist()})
    atomic_json(run_dir / "best.json", {"vectors": leader.tolist()})

    leader_energy, _ = energy_gradient(leader)
    leader_topology = topology_summary(leader)
    append_event(
        events,
        event="start",
        live_score=live_score,
        local_leader_energy=leader_energy,
        target=target,
        verifier_sha256=verifier_hash,
        leader_topology=leader_topology,
    )
    trials = generate_trials(
        snapshot, leader, np.random.default_rng(args.seed), args.trial_limit
    )
    best = leader.copy()
    best_energy = leader_energy
    family_best: dict[str, float] = {}
    topology_counts: Counter[str] = Counter()
    topology_best: dict[str, float] = {}
    below_fibonacci_basin = 0

    for trial_index, (family, metadata, candidate) in enumerate(trials):
        initial_energy, _ = energy_gradient(candidate)
        initial_topology = topology_summary(candidate)
        relaxed, result = relax(candidate, args.relax_rounds, args.maxiter)
        final_energy = float(result["energy"])
        final_topology = topology_summary(relaxed)
        family_best[family] = min(family_best.get(family, np.inf), final_energy)
        topology_hash = str(final_topology["graph_wl_hash"])
        topology_counts[topology_hash] += 1
        if final_energy < topology_best.get(topology_hash, np.inf):
            topology_best[topology_hash] = final_energy
            atomic_json(
                run_dir / f"topology_{topology_hash[:12]}.json",
                {"vectors": relaxed.tolist()},
            )
        if final_energy < 37147.826:
            below_fibonacci_basin += 1
        if final_energy < best_energy:
            best = relaxed.copy()
            best_energy = final_energy
            atomic_json(run_dir / "best.json", {"vectors": best.tolist()})
            atomic_json(
                run_dir / f"checkpoint_{trial_index:03d}.json",
                {"vectors": best.tolist()},
            )
        append_event(
            events,
            event="trial",
            trial=trial_index,
            family=family,
            metadata=metadata,
            initial_energy=initial_energy,
            initial_topology=initial_topology,
            final_energy=final_energy,
            final_topology=final_topology,
            relaxation=result,
            improvement_over_live=live_score - final_energy,
        )

    norms = np.linalg.norm(best, axis=1)
    summary = {
        "slug": SLUG,
        "mode": "topology-changing global-basin campaign",
        "snapshot": str(args.snapshot.resolve()),
        "verifier_sha256": verifier_hash,
        "live_score": live_score,
        "local_leader_energy": leader_energy,
        "target_strictly_below": target,
        "best_local_energy": best_energy,
        "improvement_over_live": live_score - best_energy,
        "gate_gap": best_energy - target,
        "gate_clearing": bool(best_energy < target),
        "trial_count": len(trials),
        "family_best": family_best,
        "distinct_final_topology_count": len(topology_counts),
        "final_topology_frequencies": dict(topology_counts),
        "trials_below_fibonacci_basin": below_fibonacci_basin,
        "leader_topology": leader_topology,
        "best_topology": topology_summary(best),
        "domain": {
            "finite": bool(np.isfinite(best).all()),
            "norm_min": float(norms.min()),
            "norm_max": float(norms.max()),
        },
        "payload": str((run_dir / "best.json").resolve()),
        "events": str(events.resolve()),
        "conclusion": "No conclusion until the bounded topology-changing trial set completes.",
    }
    if not summary["gate_clearing"]:
        summary["conclusion"] = (
            "No tested cap transport, vacancy/interstitial, bond flip, public alternate basin, "
            "or topology-changing kick cleared the live gate."
        )
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, event="complete", summary=summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
