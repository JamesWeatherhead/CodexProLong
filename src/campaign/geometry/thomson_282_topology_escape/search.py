#!/usr/bin/env python3
"""Bounded topology-changing search for Thomson N=282.

The search enumerates graph-distinct, defect-free (12 degree-5, all other
degree-6) triangulations at N=72 using pairs of legal edge flips.  Each graph
is lifted to N=282 by inserting one normalized midpoint on every edge, exactly
the 4N-6 split construction described by Altschuler and Perez-Garrido.  Several
geometric realizations of every new graph are then released through tangent
L-BFGS and scored by the frozen EinsteinArena verifier.

No network write, Arena submission, or Git operation exists in this program.
All generated artifacts are append-only inside this directory's runs/ tree.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import networkx as nx
import numpy as np
from scipy.optimize import minimize
from scipy.spatial import ConvexHull


HERE = Path(__file__).resolve().parent
ARENA = HERE.parents[2]
SNAPSHOT = (
    ARENA
    / "campaign/geometry/snapshots/thomson-problem_20260814T234236Z.json"
)
VERIFIER_SHA256 = "4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af"
VERIFIER = ARENA / f"campaign/state/problems/thomson-problem/{VERIFIER_SHA256}.py"
N72_URL = "https://www-wales.ch.cam.ac.uk/~wales/CCD/Thomson/xyz/72.xyz"
N72 = 72
N282 = 282

Face = tuple[int, int, int]
Edge = tuple[int, int]
Flip = tuple[Edge, Edge]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ": "),
        )
        + "\n"
    ).encode()


def write_once(path: Path, value: object | bytes) -> str:
    """Create one immutable artifact and return its SHA-256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    payload = value if isinstance(value, bytes) else canonical_json_bytes(value)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return sha256_bytes(payload)


def append_event(path: Path, **event: object) -> None:
    payload = json.dumps(event, sort_keys=True, allow_nan=False) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def normalize(points: np.ndarray, count: int | None = None) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError(f"expected Nx3 points, got {points.shape}")
    if count is not None and points.shape[0] != count:
        raise ValueError(f"expected {count} points, got {points.shape[0]}")
    if not np.isfinite(points).all():
        raise ValueError("non-finite point")
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    if np.any(norms < 1e-12):
        raise ValueError("zero or near-zero point")
    return points / norms


def parse_xyz(raw: bytes, count: int) -> np.ndarray:
    lines = raw.decode("utf-8").splitlines()
    if int(lines[0].strip()) != count:
        raise ValueError("XYZ count mismatch")
    rows = []
    for line in lines[2:]:
        fields = line.split()
        if len(fields) >= 4:
            rows.append([float(fields[1]), float(fields[2]), float(fields[3])])
    return normalize(np.asarray(rows, dtype=np.float64), count)


def faces_from_points(points: np.ndarray) -> frozenset[Face]:
    return frozenset(
        tuple(sorted(int(value) for value in face))
        for face in ConvexHull(points).simplices
    )


def triangulation_data(
    faces: frozenset[Face], count: int
) -> tuple[set[Edge], dict[Edge, list[int]], np.ndarray]:
    edges: set[Edge] = set()
    opposites: dict[Edge, list[int]] = defaultdict(list)
    for a, b, c in faces:
        for first, second, opposite in ((a, b, c), (a, c, b), (b, c, a)):
            edge = tuple(sorted((first, second)))
            edges.add(edge)
            opposites[edge].append(opposite)
    degrees = np.zeros(count, dtype=np.int16)
    for first, second in edges:
        degrees[first] += 1
        degrees[second] += 1
    return edges, opposites, degrees


def triangulation_graph(faces: frozenset[Face], count: int) -> nx.Graph:
    edges, _, _ = triangulation_data(faces, count)
    graph = nx.Graph()
    graph.add_nodes_from(range(count))
    graph.add_edges_from(edges)
    return graph


def topology_summary(points: np.ndarray) -> dict[str, object]:
    faces = faces_from_points(points)
    edges, _, degrees = triangulation_data(faces, points.shape[0])
    graph = triangulation_graph(faces, points.shape[0])
    return {
        "face_count": len(faces),
        "edge_count": len(edges),
        "degree_histogram": {
            str(key): int(value) for key, value in sorted(Counter(degrees).items())
        },
        "defect_count": int(np.count_nonzero(degrees != 6)),
        "fivefold_count": int(np.count_nonzero(degrees == 5)),
        "sevenfold_count": int(np.count_nonzero(degrees == 7)),
        "wl_hash": nx.weisfeiler_lehman_graph_hash(graph, iterations=20),
        "faces_sha256": sha256_bytes(
            json.dumps(sorted(faces), separators=(",", ":")).encode()
        ),
    }


def is_defect_free_72(degrees: np.ndarray) -> bool:
    return bool(
        np.count_nonzero(degrees == 5) == 12
        and np.count_nonzero(degrees == 6) == 60
        and np.all((degrees == 5) | (degrees == 6))
    )


def is_defect_free_282(summary: dict[str, object]) -> bool:
    return summary["degree_histogram"] == {"5": 12, "6": 270}


def legal_flips(faces: frozenset[Face], count: int) -> Iterable[Flip]:
    edges, opposites, _ = triangulation_data(faces, count)
    for edge in sorted(opposites):
        other = opposites[edge]
        if len(other) == 2 and tuple(sorted(other)) not in edges:
            yield edge, tuple(other)


def apply_flip(faces: frozenset[Face], edge: Edge, opposite: Edge) -> frozenset[Face]:
    a, b = edge
    c, d = opposite
    removed = {
        tuple(sorted((a, b, c))),
        tuple(sorted((a, b, d))),
    }
    if not removed <= faces:
        raise ValueError("edge flip does not match triangulation")
    return frozenset(
        (set(faces) - removed)
        | {
            tuple(sorted((c, d, a))),
            tuple(sorted((c, d, b))),
        }
    )


def labelled_faces_hash(faces: frozenset[Face]) -> str:
    return sha256_bytes(json.dumps(sorted(faces), separators=(",", ":")).encode())


def macro_neighbors(
    faces: frozenset[Face], count: int
) -> list[tuple[frozenset[Face], tuple[Flip, Flip]]]:
    """All nontrivial two-flip neighbors that restore the 5/6 degree multiset."""
    found: dict[str, tuple[frozenset[Face], tuple[Flip, Flip]]] = {}
    for first_edge, first_opposite in legal_flips(faces, count):
        once = apply_flip(faces, first_edge, first_opposite)
        for second_edge, second_opposite in legal_flips(once, count):
            if (
                set(second_edge) == set(first_opposite)
                and set(second_opposite) == set(first_edge)
            ):
                continue
            twice = apply_flip(once, second_edge, second_opposite)
            _, _, degrees = triangulation_data(twice, count)
            if is_defect_free_72(degrees):
                found.setdefault(
                    labelled_faces_hash(twice),
                    (
                        twice,
                        (
                            (first_edge, first_opposite),
                            (second_edge, second_opposite),
                        ),
                    ),
                )
    return [found[key] for key in sorted(found)]


@dataclass(frozen=True)
class TopologyClass:
    class_id: int
    macro_depth: int
    faces: frozenset[Face]
    path: tuple[Flip, ...]
    wl_hash: str
    faces_sha256: str


def enumerate_topology_classes(
    source_faces: frozenset[Face], class_limit: int, macro_depth: int
) -> list[TopologyClass]:
    source_graph = triangulation_graph(source_faces, N72)
    source = TopologyClass(
        0,
        0,
        source_faces,
        (),
        nx.weisfeiler_lehman_graph_hash(source_graph, iterations=20),
        labelled_faces_hash(source_faces),
    )
    classes = [source]
    class_graphs = [source_graph]
    frontier = [source]

    for depth in range(1, macro_depth + 1):
        next_frontier: list[TopologyClass] = []
        for parent in frontier:
            for faces, moves in macro_neighbors(parent.faces, N72):
                graph = triangulation_graph(faces, N72)
                wl_hash = nx.weisfeiler_lehman_graph_hash(graph, iterations=20)
                duplicate = False
                for prior, prior_graph in zip(classes, class_graphs, strict=True):
                    if prior.wl_hash == wl_hash and nx.is_isomorphic(graph, prior_graph):
                        duplicate = True
                        break
                if duplicate:
                    continue
                item = TopologyClass(
                    len(classes),
                    depth,
                    faces,
                    parent.path + moves,
                    wl_hash,
                    labelled_faces_hash(faces),
                )
                classes.append(item)
                class_graphs.append(graph)
                next_frontier.append(item)
                if len(classes) >= class_limit:
                    return classes
        frontier = next_frontier
        if not frontier:
            break
    return classes


def force_flip(points: np.ndarray, edge: Edge, opposite: Edge, fraction: float) -> np.ndarray:
    a, b = edge
    c, d = opposite
    candidate = points.copy()

    def unit(row: np.ndarray) -> np.ndarray:
        return row / np.linalg.norm(row)

    candidate[c] = unit((1.0 - fraction) * points[c] + fraction * points[d])
    candidate[d] = unit((1.0 - fraction) * points[d] + fraction * points[c])
    candidate[a] = unit((1.0 + fraction) * points[a] - fraction * points[b])
    candidate[b] = unit((1.0 + fraction) * points[b] - fraction * points[a])
    return normalize(candidate, N72)


def realize_small(source: np.ndarray, path: tuple[Flip, ...], fraction: float) -> np.ndarray:
    current = source.copy()
    for edge, opposite in path:
        current = force_flip(current, edge, opposite, fraction)
    return current


def split_to_282(points: np.ndarray, faces: frozenset[Face]) -> np.ndarray:
    edges, _, degrees = triangulation_data(faces, N72)
    if len(edges) != 210 or not is_defect_free_72(degrees):
        raise ValueError("split source is not a defect-free N=72 triangulation")
    midpoints = []
    for first, second in sorted(edges):
        row = points[first] + points[second]
        midpoints.append(row / np.linalg.norm(row))
    return normalize(np.vstack((points, np.asarray(midpoints))), N282)


def energy_gradient(points: np.ndarray) -> tuple[float, np.ndarray]:
    differences = points[:, None, :] - points[None, :, :]
    distances = np.linalg.norm(differences, axis=2)
    np.fill_diagonal(distances, np.inf)
    inverse = 1.0 / distances
    energy = float(np.triu(inverse, 1).sum())
    gradient = -(differences * inverse[:, :, None] ** 3).sum(axis=1)
    return energy, gradient


def tangent_basis(points: np.ndarray) -> np.ndarray:
    count = points.shape[0]
    basis = np.empty((count, 2, 3), dtype=np.float64)
    axes = np.eye(3)
    for index, point in enumerate(points):
        reference = axes[np.argmin(np.abs(point))]
        first = np.cross(point, reference)
        first /= np.linalg.norm(first)
        basis[index, 0] = first
        basis[index, 1] = np.cross(point, first)
    return basis


def map_parameters(
    parameters: np.ndarray, base: np.ndarray, basis: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    tangent = parameters.reshape(base.shape[0], 2)
    raw = base + np.einsum("nik,ni->nk", basis, tangent)
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    return raw / norms, norms


def objective(
    parameters: np.ndarray, base: np.ndarray, basis: np.ndarray
) -> tuple[float, np.ndarray]:
    points, norms = map_parameters(parameters, base, basis)
    energy, gradient = energy_gradient(points)
    tangent = gradient - np.sum(gradient * points, axis=1, keepdims=True) * points
    raw_gradient = tangent / norms
    parameter_gradient = np.einsum("nik,nk->ni", basis, raw_gradient)
    return energy, parameter_gradient.ravel()


def relax(points: np.ndarray, rounds: int, maxiter: int) -> tuple[np.ndarray, dict[str, object]]:
    current = normalize(points)
    iterations = 0
    evaluations = 0
    messages: list[str] = []
    for _ in range(rounds):
        basis = tangent_basis(current)
        result = minimize(
            objective,
            np.zeros(2 * current.shape[0]),
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


def load_verifier() -> Callable[[dict[str, object]], float]:
    raw = VERIFIER.read_bytes()
    if sha256_bytes(raw) != VERIFIER_SHA256:
        raise ValueError("frozen verifier hash mismatch")
    spec = importlib.util.spec_from_file_location("frozen_thomson_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load frozen verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate


def parse_fractions(value: str) -> list[float]:
    fractions = [float(item) for item in value.split(",") if item.strip()]
    if not fractions or any(not (0.0 <= item < 0.5) for item in fractions):
        raise argparse.ArgumentTypeError("fractions must lie in [0, 0.5)")
    return fractions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--class-limit", type=int, default=30)
    parser.add_argument("--macro-depth", type=int, default=3)
    parser.add_argument("--trial-limit", type=int, default=48)
    parser.add_argument("--relax-rounds", type=int, default=2)
    parser.add_argument("--maxiter", type=int, default=700)
    parser.add_argument(
        "--fractions",
        type=parse_fractions,
        default=parse_fractions("0.06,0.08,0.10,0.12,0.14,0.16,0.18,0.20,0.24,0.28,0.32"),
    )
    parser.add_argument("--stamp")
    args = parser.parse_args()

    if args.class_limit < 2 or args.macro_depth < 1 or args.trial_limit < 1:
        raise ValueError("positive nontrivial search bounds required")

    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = HERE / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"

    snapshot_raw = SNAPSHOT.read_bytes()
    snapshot = json.loads(snapshot_raw)
    embedded_verifier = snapshot["problem"]["verifier"].encode()
    if sha256_bytes(embedded_verifier) != VERIFIER_SHA256:
        raise ValueError("snapshot verifier hash mismatch")
    evaluate = load_verifier()
    live_score = float(snapshot["solutions"][0]["score"])
    min_improvement = float(snapshot["problem"]["minImprovement"])
    gate = live_score - min_improvement
    leader = normalize(
        np.asarray(
            next(item for item in snapshot["solutions"] if int(item["id"]) == 561)[
                "data"
            ]["vectors"],
            dtype=np.float64,
        ),
        N282,
    )
    leader_score = float(evaluate({"vectors": leader.tolist()}))
    leader_topology = topology_summary(leader)

    request = urllib.request.Request(N72_URL, headers={"User-Agent": "CodexProLong/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        n72_raw = response.read()
    n72_sha = write_once(run_dir / "sources/72.xyz", n72_raw)
    source_72 = parse_xyz(n72_raw, N72)
    source_faces = faces_from_points(source_72)
    source_edges, _, source_degrees = triangulation_data(source_faces, N72)
    if len(source_edges) != 210 or not is_defect_free_72(source_degrees):
        raise ValueError("Cambridge N=72 source has unexpected topology")

    append_event(
        events,
        event="start",
        stamp=stamp,
        snapshot=str(SNAPSHOT),
        snapshot_sha256=sha256_bytes(snapshot_raw),
        verifier=str(VERIFIER),
        verifier_sha256=VERIFIER_SHA256,
        n72_url=N72_URL,
        n72_sha256=n72_sha,
        live_score=live_score,
        normalized_leader_score=leader_score,
        target_strictly_below=gate,
        leader_topology=leader_topology,
        bounds={
            "class_limit": args.class_limit,
            "macro_depth": args.macro_depth,
            "trial_limit": args.trial_limit,
            "relax_rounds": args.relax_rounds,
            "maxiter": args.maxiter,
            "fractions": args.fractions,
        },
    )

    classes = enumerate_topology_classes(
        source_faces, args.class_limit, args.macro_depth
    )
    for item in classes:
        payload = {
            "class_id": item.class_id,
            "macro_depth": item.macro_depth,
            "wl_hash": item.wl_hash,
            "faces_sha256": item.faces_sha256,
            "degree_histogram": {"5": 12, "6": 60},
            "faces": [list(face) for face in sorted(item.faces)],
            "path": [
                {"edge": list(edge), "opposite": list(opposite)}
                for edge, opposite in item.path
            ],
        }
        artifact = run_dir / "topology_classes" / f"class_{item.class_id:03d}.json"
        artifact_sha = write_once(artifact, payload)
        append_event(
            events,
            event="topology_class",
            class_id=item.class_id,
            macro_depth=item.macro_depth,
            wl_hash=item.wl_hash,
            faces_sha256=item.faces_sha256,
            artifact=str(artifact),
            artifact_sha256=artifact_sha,
            flip_count=len(item.path),
        )

    # Generate graph-distinct geometric realizations.  We retain at most two
    # distinct realized triangulations per exact combinatorial class.
    trial_seeds: list[dict[str, Any]] = []
    source_wl_282 = str(leader_topology["wl_hash"])
    for item in classes[1:]:
        realizations: dict[str, dict[str, Any]] = {}
        for fraction in args.fractions:
            small = realize_small(source_72, item.path, fraction)
            candidate = split_to_282(small, item.faces)
            raw_energy, _ = energy_gradient(candidate)
            summary = topology_summary(candidate)
            wl_hash = str(summary["wl_hash"])
            if not is_defect_free_282(summary) or wl_hash == source_wl_282:
                continue
            record = {
                "class": item,
                "fraction": fraction,
                "points": candidate,
                "raw_energy": raw_energy,
                "initial_topology": summary,
            }
            previous = realizations.get(wl_hash)
            if previous is None or raw_energy < float(previous["raw_energy"]):
                realizations[wl_hash] = record
        trial_seeds.extend(
            sorted(realizations.values(), key=lambda value: float(value["raw_energy"]))[:2]
        )

    trial_seeds.sort(key=lambda value: float(value["raw_energy"]))
    trial_seeds = trial_seeds[: args.trial_limit]
    append_event(
        events,
        event="realization_frontier",
        enumerated_class_count=len(classes),
        non_source_class_count=max(0, len(classes) - 1),
        retained_realization_count=len(trial_seeds),
        unique_initial_wl_count=len(
            {str(item["initial_topology"]["wl_hash"]) for item in trial_seeds}
        ),
    )

    best_any: tuple[float, np.ndarray, int] | None = None
    best_distinct: tuple[float, np.ndarray, int] | None = None
    final_wl_counts: Counter[str] = Counter()
    initial_wl_counts: Counter[str] = Counter()
    returned_to_incumbent = 0
    final_defect_free = 0

    for trial_index, seed in enumerate(trial_seeds):
        item = seed["class"]
        assert isinstance(item, TopologyClass)
        initial_wl = str(seed["initial_topology"]["wl_hash"])
        initial_wl_counts[initial_wl] += 1
        relaxed, diagnostics = relax(
            np.asarray(seed["points"]), args.relax_rounds, args.maxiter
        )
        official_score = float(evaluate({"vectors": relaxed.tolist()}))
        final_topology = topology_summary(relaxed)
        final_wl = str(final_topology["wl_hash"])
        final_wl_counts[final_wl] += 1
        same_as_incumbent = final_wl == source_wl_282
        returned_to_incumbent += int(same_as_incumbent)
        final_defect_free += int(is_defect_free_282(final_topology))
        payload = {"vectors": relaxed.tolist()}
        candidate_path = run_dir / "candidates" / f"trial_{trial_index:03d}.json"
        candidate_sha = write_once(candidate_path, payload)
        candidate_bytes = candidate_path.stat().st_size

        if best_any is None or official_score < best_any[0]:
            best_any = (official_score, relaxed.copy(), trial_index)
        if not same_as_incumbent and (
            best_distinct is None or official_score < best_distinct[0]
        ):
            best_distinct = (official_score, relaxed.copy(), trial_index)

        append_event(
            events,
            event="trial",
            trial=trial_index,
            class_id=item.class_id,
            class_wl_hash=item.wl_hash,
            class_faces_sha256=item.faces_sha256,
            macro_depth=item.macro_depth,
            flip_count=len(item.path),
            force_fraction=float(seed["fraction"]),
            raw_energy=float(seed["raw_energy"]),
            initial_topology=seed["initial_topology"],
            final_topology=final_topology,
            returned_to_incumbent=same_as_incumbent,
            final_defect_free=is_defect_free_282(final_topology),
            relaxation=diagnostics,
            official_verifier_score=official_score,
            improvement_over_live=live_score - official_score,
            gate_gap=official_score - gate,
            gate_clearing=official_score < gate,
            candidate=str(candidate_path),
            candidate_sha256=candidate_sha,
            candidate_bytes=candidate_bytes,
        )

    if best_any is None:
        raise RuntimeError("no defect-free topology-changing realization survived seeding")

    best_score, best_points, best_trial = best_any
    best_path = run_dir / "best_any.json"
    best_sha = write_once(best_path, {"vectors": best_points.tolist()})

    distinct_receipt: dict[str, object] | None = None
    if best_distinct is not None:
        distinct_score, distinct_points, distinct_trial = best_distinct
        distinct_path = run_dir / "best_distinct_final_topology.json"
        distinct_sha = write_once(distinct_path, {"vectors": distinct_points.tolist()})
        distinct_receipt = {
            "trial": distinct_trial,
            "score": distinct_score,
            "gate_gap": distinct_score - gate,
            "path": str(distinct_path),
            "sha256": distinct_sha,
            "topology": topology_summary(distinct_points),
        }

    summary = {
        "status": "gate_clearer" if best_score < gate else "bounded_negative_frontier",
        "mode": "degree-preserving N72 topology enumeration plus exact 4N-6 split",
        "verifier_sha256": VERIFIER_SHA256,
        "snapshot_sha256": sha256_bytes(snapshot_raw),
        "n72_source_sha256": n72_sha,
        "live_score": live_score,
        "target_strictly_below": gate,
        "normalized_incumbent_score": leader_score,
        "enumerated_class_count": len(classes),
        "non_source_class_count": max(0, len(classes) - 1),
        "tested_realization_count": len(trial_seeds),
        "unique_initial_topology_count": len(initial_wl_counts),
        "unique_final_topology_count": len(final_wl_counts),
        "initial_topology_frequencies": dict(sorted(initial_wl_counts.items())),
        "final_topology_frequencies": dict(sorted(final_wl_counts.items())),
        "returned_to_incumbent_count": returned_to_incumbent,
        "final_defect_free_count": final_defect_free,
        "best_any": {
            "trial": best_trial,
            "score": best_score,
            "improvement_over_live": live_score - best_score,
            "gate_gap": best_score - gate,
            "gate_clearing": best_score < gate,
            "path": str(best_path),
            "sha256": best_sha,
            "topology": topology_summary(best_points),
        },
        "best_distinct_final_topology": distinct_receipt,
        "search_bounds": {
            "class_limit": args.class_limit,
            "macro_depth": args.macro_depth,
            "trial_limit": args.trial_limit,
            "relax_rounds": args.relax_rounds,
            "maxiter": args.maxiter,
            "fractions": args.fractions,
        },
        "claim_scope": (
            "This closes only the enumerated two-flip-connected N=72 defect-free "
            "classes and their retained split realizations; it is not a proof over all "
            "N=282 triangulations or all Coulomb basins."
        ),
    }
    summary_sha = write_once(run_dir / "summary.json", summary)
    receipt = {
        "run": str(run_dir),
        "summary_sha256": summary_sha,
        "verifier_sha256": VERIFIER_SHA256,
        "candidate_sha256": best_sha,
        "official_verifier_score": best_score,
        "target_strictly_below": gate,
        "gate_clearing": best_score < gate,
        "domain": {
            "shape": list(best_points.shape),
            "finite": bool(np.isfinite(best_points).all()),
            "norm_min": float(np.linalg.norm(best_points, axis=1).min()),
            "norm_max": float(np.linalg.norm(best_points, axis=1).max()),
        },
    }
    receipt_sha = write_once(run_dir / "receipt.json", receipt)
    append_event(
        events,
        event="complete",
        summary=str(run_dir / "summary.json"),
        summary_sha256=summary_sha,
        receipt=str(run_dir / "receipt.json"),
        receipt_sha256=receipt_sha,
        status=summary["status"],
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
