"""Bounded intended-domain search in the D6-symmetric Tammes-50 family.

The public all-on-sphere incumbent has an exact order-12 rotational symmetry
that was not characterized in the captured discussion corpus.  Its 50 points
split into four generic D6 orbits of size 12 and one polar orbit of size two.
This program detects that structure from the frozen public construction, then
searches the resulting eight-parameter family without using the verifier's
zero-norm/unit-ball mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
from scipy.optimize import differential_evolution, linear_sum_assignment, minimize

COUNT = 50
DIMENSION = 3
INCUMBENT_SOLUTION_ID = 1035
SLUG = "tammes-problem"
ANGLE_PERIOD = math.pi / 3.0
PHASE_BOUND = math.pi / 6.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def append_event(path: Path, **payload: Any) -> None:
    record = {"at": datetime.now(UTC).isoformat(), **payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def normalize(points: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(points, axis=1)
    if points.shape != (COUNT, DIMENSION):
        raise ValueError(f"expected {(COUNT, DIMENSION)}, got {points.shape}")
    if not np.isfinite(points).all() or np.any(norms < 1e-12):
        raise ValueError("points must be finite and nonzero")
    return points / norms[:, None]


def verifier_score(points: np.ndarray) -> float:
    unit = normalize(points)
    rows, columns = np.triu_indices(COUNT, 1)
    return float(np.min(np.linalg.norm(unit[rows] - unit[columns], axis=1)))


def squared_distances(points: np.ndarray) -> np.ndarray:
    rows, columns = np.triu_indices(COUNT, 1)
    return np.sum((points[rows] - points[columns]) ** 2, axis=1)


def contact_graph(points: np.ndarray, tolerance: float = 1e-8) -> nx.Graph:
    distances = np.linalg.norm(points[:, None] - points[None, :], axis=2)
    np.fill_diagonal(distances, np.inf)
    minimum = float(np.min(distances))
    rows, columns = np.where(np.triu(distances <= minimum + tolerance, 1))
    graph = nx.Graph()
    graph.add_nodes_from(range(COUNT))
    graph.add_edges_from(zip(map(int, rows), map(int, columns), strict=True))
    return graph


def graph_signature(points: np.ndarray, tolerance: float = 1e-7) -> dict[str, Any]:
    graph = contact_graph(points, tolerance)
    degree_counts: dict[str, int] = {}
    for _, degree in graph.degree():
        key = str(degree)
        degree_counts[key] = degree_counts.get(key, 0) + 1
    edges = sorted((min(a, b), max(a, b)) for a, b in graph.edges())
    encoded = json.dumps(edges, separators=(",", ":")).encode()
    return {
        "active_tolerance": tolerance,
        "edge_count": graph.number_of_edges(),
        "degree_counts": degree_counts,
        "labeled_edge_sha256": hashlib.sha256(encoded).hexdigest(),
        "weisfeiler_lehman_hash": nx.weisfeiler_lehman_graph_hash(graph),
    }


def geometric_automorphisms(
    points: np.ndarray,
) -> tuple[nx.Graph, list[dict[str, Any]]]:
    graph = contact_graph(points)
    automorphisms: list[dict[str, Any]] = []
    matcher = nx.algorithms.isomorphism.GraphMatcher(graph, graph)
    for mapping in matcher.isomorphisms_iter():
        permutation = np.array([mapping[index] for index in range(COUNT)])
        cross = points.T @ points[permutation]
        left, _, right = np.linalg.svd(cross)
        rotation = left @ right
        residual = float(
            np.max(np.linalg.norm(points @ rotation - points[permutation], axis=1))
        )
        determinant = float(np.linalg.det(rotation))
        if residual < 1e-9 and determinant > 0.999999:
            automorphisms.append(
                {
                    "permutation": permutation,
                    "rotation": rotation,
                    "residual": residual,
                    "determinant": determinant,
                }
            )
    return graph, automorphisms


def reduce_phase(angle: float) -> float:
    return float((angle + PHASE_BOUND) % ANGLE_PERIOD - PHASE_BOUND)


def detect_d6_parameters(points: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    graph, automorphisms = geometric_automorphisms(points)
    isolated = sorted(node for node, degree in graph.degree() if degree == 0)
    if len(automorphisms) != 12 or len(isolated) != 2:
        raise RuntimeError(
            f"expected 12 geometric automorphisms and two poles, got "
            f"{len(automorphisms)} and {isolated}"
        )
    axis = points[isolated[0]]
    if abs(float(axis @ points[isolated[1]]) + 1.0) > 1e-12:
        raise RuntimeError("isolated vertices are not antipodal")

    half_turn = None
    for item in automorphisms:
        permutation = item["permutation"]
        rotation = item["rotation"]
        angle = math.acos(float(np.clip((np.trace(rotation) - 1.0) / 2.0, -1, 1)))
        if permutation[isolated[0]] == isolated[1] and abs(angle - math.pi) < 1e-6:
            half_turn = rotation
            break
    if half_turn is None:
        raise RuntimeError("could not locate a horizontal D6 half-turn")

    eigenvalues, eigenvectors = np.linalg.eig(half_turn.T)
    horizontal = np.real(eigenvectors[:, np.argmin(np.abs(eigenvalues - 1.0))])
    horizontal -= float(horizontal @ axis) * axis
    horizontal /= np.linalg.norm(horizontal)
    transverse = np.cross(axis, horizontal)

    unseen = set(range(COUNT))
    orbits: list[list[int]] = []
    while unseen:
        representative = min(unseen)
        orbit = sorted(
            {int(item["permutation"][representative]) for item in automorphisms}
        )
        orbits.append(orbit)
        unseen.difference_update(orbit)
    ring_orbits = [orbit for orbit in orbits if len(orbit) == 12]
    if sorted(map(len, orbits)) != [2, 12, 12, 12, 12]:
        raise RuntimeError(f"unexpected D6 orbit sizes: {list(map(len, orbits))}")

    parameters: list[tuple[float, float]] = []
    orbit_details: list[dict[str, Any]] = []
    for orbit in ring_orbits:
        positive = [index for index in orbit if float(points[index] @ axis) > 0]
        if len(positive) != 6:
            raise RuntimeError("generic D6 orbit does not split six/six by latitude")
        latitudes = [float(points[index] @ axis) for index in positive]
        phases = [
            reduce_phase(
                math.atan2(
                    float(points[index] @ transverse),
                    float(points[index] @ horizontal),
                )
            )
            for index in positive
        ]
        z_value = float(np.mean(latitudes))
        phase = float(np.mean(phases))
        if np.ptp(latitudes) > 1e-10 or np.ptp(phases) > 1e-10:
            raise RuntimeError("public orbit is not numerically D6 exact")
        parameters.append((z_value, phase))
        orbit_details.append({"indices": orbit, "z": z_value, "phase": phase})
    parameters.sort()
    vector = np.array(
        [item[0] for item in parameters] + [item[1] for item in parameters]
    )
    reconstructed = make_points(vector)
    canonical_to_public = np.column_stack((horizontal, transverse, axis))
    reconstructed_public_frame = reconstructed @ canonical_to_public.T
    costs = np.linalg.norm(
        points[:, None] - reconstructed_public_frame[None, :], axis=2
    )
    rows, columns = linear_sum_assignment(costs)
    reconstruction_error = float(np.max(costs[rows, columns]))
    if reconstruction_error > 1e-9:
        raise RuntimeError(f"D6 reconstruction error {reconstruction_error}")

    details = {
        "contact_graph": graph_signature(points, 1e-8),
        "combinatorial_automorphism_count": sum(
            1
            for _ in nx.algorithms.isomorphism.GraphMatcher(
                graph, graph
            ).isomorphisms_iter()
        ),
        "geometric_proper_rotation_count": len(automorphisms),
        "orbit_sizes": sorted(map(len, orbits)),
        "ring_orbits": orbit_details,
        "poles": isolated,
        "canonical_to_public_frame": canonical_to_public.tolist(),
        "reconstruction_bottleneck_error": reconstruction_error,
        "parameters_sorted_by_positive_latitude": vector.tolist(),
    }
    return vector, details


def make_points(parameters: np.ndarray) -> np.ndarray:
    z_values = parameters[:4]
    phases = parameters[4:]
    points: list[list[float]] = []
    for z_value, phase in zip(z_values, phases, strict=True):
        radius = math.sqrt(max(0.0, 1.0 - float(z_value) ** 2))
        for step in range(6):
            angle = float(phase) + step * ANGLE_PERIOD
            points.append(
                [radius * math.cos(angle), radius * math.sin(angle), float(z_value)]
            )
        for step in range(6):
            angle = -float(phase) + step * ANGLE_PERIOD
            points.append(
                [radius * math.cos(angle), radius * math.sin(angle), -float(z_value)]
            )
    points.extend(([0.0, 0.0, 1.0], [0.0, 0.0, -1.0]))
    return np.asarray(points)


def objective(parameters: np.ndarray) -> float:
    return -float(np.min(squared_distances(make_points(parameters))))


def polish(parameters: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    initial_squared = -objective(parameters)
    start = np.r_[parameters, initial_squared]

    def constraints(vector: np.ndarray) -> np.ndarray:
        return squared_distances(make_points(vector[:8])) - vector[8]

    z_values = parameters[:4]
    midpoints = [(z_values[index] + z_values[index + 1]) / 2 for index in range(3)]
    z_bounds = [
        (0.001, midpoints[0]),
        (midpoints[0], midpoints[1]),
        (midpoints[1], midpoints[2]),
        (midpoints[2], 0.999),
    ]
    bounds = z_bounds + [(-PHASE_BOUND, PHASE_BOUND)] * 4 + [(0.0, 1.0)]
    result = minimize(
        lambda vector: -vector[8],
        start,
        method="SLSQP",
        bounds=bounds,
        constraints={"type": "ineq", "fun": constraints},
        options={"ftol": 1e-14, "maxiter": 1000, "disp": False},
    )
    polished = np.asarray(result.x[:8])
    score = verifier_score(make_points(polished))
    return polished, {
        "success": bool(result.success),
        "message": str(result.message),
        "iterations": int(result.nit),
        "function_evaluations": int(result.nfev),
        "constraint_minimum": float(np.min(constraints(result.x))),
        "score": score,
    }


def database_paths(campaign_root: Path) -> tuple[Path, dict[str, Any]]:
    latest_path = campaign_root / "research_corpus" / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    database = campaign_root / "research_corpus" / latest["database"]
    if sha256_file(database) != latest["database_sha256"]:
        raise RuntimeError("public corpus database hash mismatch")
    return database, latest


def load_public_context(database: Path) -> tuple[np.ndarray, dict[str, Any]]:
    connection = sqlite3.connect(database)
    solution_row = connection.execute(
        "SELECT record_json, record_sha256 FROM solutions WHERE id = ?",
        (INCUMBENT_SOLUTION_ID,),
    ).fetchone()
    problem_row = connection.execute(
        "SELECT verifier_sha256, min_improvement FROM problems WHERE slug = ?",
        (SLUG,),
    ).fetchone()
    counts = connection.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM solutions s JOIN problems p ON p.id=s.problem_id
            WHERE p.slug=?),
          (SELECT COUNT(*) FROM threads WHERE problem_slug=?),
          (SELECT COUNT(*) FROM replies r JOIN threads t ON t.id=r.thread_id
            WHERE t.problem_slug=?)
        """,
        (SLUG, SLUG, SLUG),
    ).fetchone()
    sphere_scores = connection.execute(
        """
        SELECT s.id, s.score FROM solutions s JOIN problems p ON p.id=s.problem_id
        WHERE p.slug=? AND s.id NOT IN (2496,2497) ORDER BY s.score DESC
        """,
        (SLUG,),
    ).fetchall()
    live_scores = connection.execute(
        """
        SELECT s.id, s.score FROM solutions s JOIN problems p ON p.id=s.problem_id
        WHERE p.slug=? ORDER BY s.score DESC
        """,
        (SLUG,),
    ).fetchall()
    connection.close()
    if solution_row is None or problem_row is None:
        raise RuntimeError("public Tammes context missing from corpus")
    record = json.loads(solution_row[0])
    points = normalize(np.asarray(record["data"]["vectors"], dtype=float))
    context = {
        "solution_id": INCUMBENT_SOLUTION_ID,
        "solution_record_sha256": solution_row[1],
        "verifier_sha256": problem_row[0],
        "min_improvement": float(problem_row[1]),
        "corpus_solution_count": int(counts[0]),
        "corpus_thread_count": int(counts[1]),
        "corpus_reply_count": int(counts[2]),
        "legitimate_sphere_leader_id": int(sphere_scores[0][0]),
        "legitimate_sphere_leader_score": float(sphere_scores[0][1]),
        "live_leader_id": int(live_scores[0][0]),
        "live_leader_score": float(live_scores[0][1]),
    }
    return points, context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--stamp", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--trials", type=int, default=8)
    parser.add_argument("--maxiter", type=int, default=450)
    parser.add_argument("--population", type=int, default=160)
    parser.add_argument("--resume", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_root = args.campaign_root.resolve()
    database, latest = database_paths(campaign_root)
    public_points, context = load_public_context(database)
    incumbent_parameters, symmetry = detect_d6_parameters(public_points)
    incumbent_score = verifier_score(public_points)
    reconstructed_score = verifier_score(make_points(incumbent_parameters))
    if abs(incumbent_score - reconstructed_score) > 1e-12:
        raise RuntimeError("D6 reconstruction changes the incumbent score")

    if args.resume:
        run_dir = args.resume.resolve()
        checkpoint = json.loads((run_dir / "checkpoint.json").read_text())
        records = checkpoint["records"]
        best_parameters = np.asarray(checkpoint["best_parameters"], dtype=float)
        best_score = float(checkpoint["best_score"])
    else:
        run_dir = (campaign_root / "geometry" / "runs" / args.stamp / SLUG).resolve()
        run_dir.mkdir(parents=True, exist_ok=False)
        records = []
        best_parameters = incumbent_parameters.copy()
        best_score = incumbent_score

    events_path = run_dir / "events.jsonl"
    if not records:
        append_event(
            events_path,
            event="start",
            mode="strict unit-sphere D6 orbit search",
            verifier_sha256=context["verifier_sha256"],
            corpus_database_sha256=latest["database_sha256"],
            corpus_counts={
                "solutions": context["corpus_solution_count"],
                "threads": context["corpus_thread_count"],
                "replies": context["corpus_reply_count"],
            },
            symmetry=symmetry,
        )
    else:
        append_event(events_path, event="resume", completed_trials=len(records))

    midpoints = [
        (incumbent_parameters[index] + incumbent_parameters[index + 1]) / 2
        for index in range(3)
    ]
    bounds = [
        (0.001, midpoints[0]),
        (midpoints[0], midpoints[1]),
        (midpoints[1], midpoints[2]),
        (midpoints[2], 0.999),
    ] + [(-PHASE_BOUND, PHASE_BOUND)] * 4

    for trial in range(len(records), args.trials):
        started = time.monotonic()
        seed = 81000 + trial
        rng = np.random.default_rng(seed)
        population = np.column_stack(
            [rng.uniform(lower, upper, args.population) for lower, upper in bounds]
        )
        mode = "warm" if trial % 2 == 0 else "cold"
        if mode == "warm":
            population[0] = incumbent_parameters
            for row in range(1, min(9, len(population))):
                jitter = rng.normal(scale=np.r_[np.full(4, 0.01), np.full(4, 0.02)])
                population[row] = np.clip(
                    incumbent_parameters + jitter,
                    [item[0] for item in bounds],
                    [item[1] for item in bounds],
                )
        result = differential_evolution(
            objective,
            bounds,
            init=population,
            seed=seed,
            maxiter=args.maxiter,
            tol=1e-10,
            atol=1e-12,
            mutation=(0.5, 1.7),
            recombination=0.9,
            polish=False,
            updating="immediate",
            workers=1,
        )
        raw_parameters = np.asarray(result.x)
        raw_score = verifier_score(make_points(raw_parameters))
        polished_parameters, polish_result = polish(raw_parameters)
        polished_points = make_points(polished_parameters)
        polished_score = verifier_score(polished_points)
        norms = np.linalg.norm(polished_points, axis=1)
        record = {
            "trial": trial,
            "seed": seed,
            "mode": mode,
            "elapsed_seconds": time.monotonic() - started,
            "de_iterations": int(result.nit),
            "de_function_evaluations": int(result.nfev),
            "de_success": bool(result.success),
            "de_message": str(result.message),
            "raw_score": raw_score,
            "raw_parameters": raw_parameters.tolist(),
            "polished_score": polished_score,
            "polished_parameters": polished_parameters.tolist(),
            "polish": polish_result,
            "topology": graph_signature(polished_points),
            "minimum_norm": float(np.min(norms)),
            "maximum_norm": float(np.max(norms)),
            "finite": bool(np.isfinite(polished_points).all()),
            "strict_unit_sphere": bool(np.max(np.abs(norms - 1.0)) < 5e-15),
        }
        records.append(record)
        if polished_score > best_score:
            best_score = polished_score
            best_parameters = polished_parameters.copy()
            atomic_json(
                run_dir / "best.json",
                {"vectors": make_points(best_parameters).tolist()},
            )
        checkpoint = {
            "records": records,
            "best_score": best_score,
            "best_parameters": best_parameters.tolist(),
            "verifier_sha256": context["verifier_sha256"],
            "corpus_database_sha256": latest["database_sha256"],
        }
        atomic_json(run_dir / "checkpoint.json", checkpoint)
        append_event(events_path, event="trial_complete", **record)

    distinct_topologies = sorted(
        {record["topology"]["weisfeiler_lehman_hash"] for record in records}
    )
    best_points = make_points(best_parameters)
    best_norms = np.linalg.norm(best_points, axis=1)
    summary = {
        "slug": SLUG,
        "mode": "strict unit-sphere D6 orbit search",
        "run_dir": str(run_dir),
        "corpus_database": str(database),
        "corpus_database_sha256": latest["database_sha256"],
        "public_context": context,
        "symmetry_detection": symmetry,
        "incumbent_score_host_replay": incumbent_score,
        "incumbent_parameters": incumbent_parameters.tolist(),
        "incumbent_reconstructed_score": reconstructed_score,
        "trial_count": len(records),
        "warm_trial_count": sum(record["mode"] == "warm" for record in records),
        "cold_trial_count": sum(record["mode"] == "cold" for record in records),
        "total_de_function_evaluations": sum(
            record["de_function_evaluations"] for record in records
        ),
        "distinct_polished_contact_graph_hashes": distinct_topologies,
        "best_score": best_score,
        "best_parameters": best_parameters.tolist(),
        "best_shape": list(best_points.shape),
        "best_finite": bool(np.isfinite(best_points).all()),
        "best_norm_range": [float(np.min(best_norms)), float(np.max(best_norms))],
        "improvement_over_legitimate_sphere_leader": (
            best_score - context["legitimate_sphere_leader_score"]
        ),
        "strict_sphere_gate": (
            context["legitimate_sphere_leader_score"] + context["min_improvement"]
        ),
        "clears_strict_sphere_gate": bool(
            best_score
            > context["legitimate_sphere_leader_score"] + context["min_improvement"]
        ),
        "live_gate": context["live_leader_score"] + context["min_improvement"],
        "clears_live_gate": bool(
            best_score > context["live_leader_score"] + context["min_improvement"]
        ),
        "candidate_payload": (
            str((run_dir / "best.json").resolve())
            if (run_dir / "best.json").exists()
            else None
        ),
        "records": records,
        "limitations": (
            "This searches the complete four-generic-orbit plus polar-orbit D6 "
            "parameterization, but it is a bounded numerical search rather than "
            "a proof over that family or over arbitrary 50-point spherical codes."
        ),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events_path, event="complete", summary=summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
