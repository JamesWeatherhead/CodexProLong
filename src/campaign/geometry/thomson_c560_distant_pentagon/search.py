#!/usr/bin/env python3
"""Relax seven graph-distinct C560 fullerene-dual candidates for Thomson N=282.

The private adjacency inputs came from a bounded, modified, GPL-licensed
buckygen research build seeded with the unique C540 (3,3) fullerene.  They are
not claimed to be a complete or canonical C560 enumeration.  This clean-room
campaign script validates those graph bytes, constructs numerical spherical
spectral realizations, releases them through tangent L-BFGS, and mirrors the
literal Thomson energy formula.  It has no network, Arena, Git, or submission
capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import networkx as nx
import numpy as np
import scipy
from scipy.optimize import minimize
from scipy.spatial import ConvexHull


HERE = Path(__file__).resolve().parent
ARENA = HERE.parents[2]
INPUTS = HERE / "private_inputs"
PRIOR_SUMMARY = (
    ARENA
    / "campaign/geometry/thomson_282_topology_escape/runs/"
    "20260815T_THOMSON_SPLIT_V1/summary.json"
)
PRIOR_SUMMARY_SHA256 = "433dc3a15d958f4029f9d1152d4065bf4a29087c828ad1c5aa0b6fd411919cf3"
N = 282
LEADER = 37147.29441846226
MIN_IMPROVEMENT = 1e-6
GATE = LEADER - MIN_IMPROVEMENT
VERIFIER_SHA256 = "4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af"
VERIFIER_PATH = (
    ARENA
    / "campaign/state/problems/thomson-problem"
    / f"{VERIFIER_SHA256}.py"
)
NETWORKX_VERSION = "3.6.1"


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_once(path: Path, value: object | bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    raw = value if isinstance(value, bytes) else canonical_bytes(value)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return sha256_bytes(raw)


def append_event(path: Path, value: object) -> None:
    raw = json.dumps(value, sort_keys=True, allow_nan=False) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def read_adjacency(path: Path) -> tuple[np.ndarray, nx.Graph]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or int(lines[0]) != N or len(lines) != N + 1:
        raise ValueError(f"invalid order/line count in {path}")
    adjacency = np.zeros((N, N), dtype=np.float64)
    graph = nx.Graph()
    graph.add_nodes_from(range(N))
    for vertex, line in enumerate(lines[1:]):
        values = [int(item) for item in line.split()]
        degree, neighbours = values[0], values[1:]
        if degree != len(neighbours) or degree not in (5, 6):
            raise ValueError(f"invalid degree row {vertex} in {path}")
        if len(set(neighbours)) != degree or vertex in neighbours:
            raise ValueError(f"invalid neighbours at {vertex} in {path}")
        for neighbour in neighbours:
            if not 0 <= neighbour < N:
                raise ValueError(f"out-of-range neighbour in {path}")
            adjacency[vertex, neighbour] = 1.0
            graph.add_edge(vertex, neighbour)
    if not np.array_equal(adjacency, adjacency.T):
        raise ValueError(f"asymmetric adjacency in {path}")
    histogram = Counter(dict(graph.degree()).values())
    if histogram != Counter({6: 270, 5: 12}) or graph.number_of_edges() != 840:
        raise ValueError(f"not a defect-free C560 dual: {path}")
    return adjacency, graph


def pentagon_distances(graph: nx.Graph) -> tuple[int, dict[str, int]]:
    pentagons = [vertex for vertex, degree in graph.degree() if degree == 5]
    values: list[int] = []
    for index, first in enumerate(pentagons):
        lengths = nx.single_source_shortest_path_length(graph, first)
        values.extend(lengths[second] for second in pentagons[index + 1 :])
    counts = Counter(values)
    return min(values), {str(key): counts[key] for key in sorted(counts)}


def graph_hash(graph: nx.Graph) -> str:
    return nx.weisfeiler_lehman_graph_hash(graph, iterations=20)


def edge_set(graph: nx.Graph) -> set[tuple[int, int]]:
    return {tuple(sorted((int(first), int(second)))) for first, second in graph.edges()}


def hull_graph(points: np.ndarray) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(range(points.shape[0]))
    for first, second, third in ConvexHull(points).simplices:
        graph.add_edges_from(
            (
                (int(first), int(second)),
                (int(second), int(third)),
                (int(third), int(first)),
            )
        )
    return graph


def verifier_score(points: np.ndarray) -> float:
    """Clean-room mirror of the frozen verifier's exact float64 operation order."""
    if points.shape != (N, 3) or not np.isfinite(points).all():
        raise ValueError("candidate shape/finiteness failure")
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    norms[norms < 1e-12] = 1e-12
    normalized = points / norms
    differences = normalized[:, None, :] - normalized[None, :, :]
    distance_sq = np.sum(differences**2, axis=2)
    upper = np.triu_indices(N, k=1)
    distances = np.sqrt(distance_sq[upper])
    distances[distances < 1e-12] = 1e-12
    return float(np.sum(1.0 / distances))


def spectral_embedding(adjacency: np.ndarray, scales: tuple[float, float, float]) -> np.ndarray:
    laplacian = np.diag(adjacency.sum(axis=1)) - adjacency
    eigenvalues, eigenvectors = np.linalg.eigh(laplacian)
    if eigenvalues[1] <= 1e-10:
        raise ValueError("disconnected input")
    points = eigenvectors[:, 1:4] * np.asarray(scales)[None, :]
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    if np.any(norms < 1e-12):
        raise ValueError("degenerate spectral row")
    return points / norms


def energy_gradient(points: np.ndarray) -> tuple[float, np.ndarray]:
    differences = points[:, None, :] - points[None, :, :]
    distance_sq = np.sum(differences * differences, axis=2)
    np.fill_diagonal(distance_sq, np.inf)
    distances = np.sqrt(distance_sq)
    inverse = 1.0 / distances
    energy = float(np.sum(np.triu(inverse, 1)))
    gradient = -(differences * inverse[:, :, None] ** 3).sum(axis=1)
    return energy, gradient


def tangent_basis(points: np.ndarray) -> np.ndarray:
    result = np.empty((points.shape[0], 2, 3), dtype=np.float64)
    axes = np.eye(3)
    for index, point in enumerate(points):
        reference = axes[np.argmin(np.abs(point))]
        first = np.cross(point, reference)
        first /= np.linalg.norm(first)
        result[index, 0] = first
        result[index, 1] = np.cross(point, first)
    return result


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
    parameter_gradient = np.einsum("nik,nk->ni", basis, tangent / norms)
    return energy, parameter_gradient.ravel()


def relax(points: np.ndarray, rounds: int, maxiter: int) -> tuple[np.ndarray, dict[str, object]]:
    current = points.copy()
    total_iterations = 0
    total_evaluations = 0
    messages: list[str] = []
    successes: list[bool] = []
    for _ in range(rounds):
        basis = tangent_basis(current)
        result = minimize(
            objective,
            np.zeros(2 * N),
            args=(current, basis),
            method="L-BFGS-B",
            jac=True,
            options={
                "maxiter": maxiter,
                "maxfun": 3 * maxiter,
                "maxls": 60,
                "maxcor": 30,
                "ftol": 0.0,
                "gtol": 1e-11,
            },
        )
        current = map_parameters(result.x, current, basis)[0]
        total_iterations += int(result.nit)
        total_evaluations += int(result.nfev)
        messages.append(str(result.message))
        successes.append(bool(result.success))
    energy, gradient = energy_gradient(current)
    tangent = gradient - np.sum(gradient * current, axis=1, keepdims=True) * current
    return current, {
        "score": energy,
        "iterations": total_iterations,
        "evaluations": total_evaluations,
        "projected_gradient_max": float(np.max(np.linalg.norm(tangent, axis=1))),
        "projected_gradient_total": float(np.linalg.norm(tangent)),
        "messages": messages,
        "successes": successes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=INPUTS)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--maxiter", type=int, default=800)
    parser.add_argument("--stamp")
    args = parser.parse_args()
    if args.rounds < 1 or args.maxiter < 1:
        raise ValueError("positive relaxation budget required")
    if nx.__version__ != NETWORKX_VERSION:
        raise RuntimeError(
            f"NetworkX {NETWORKX_VERSION} required for stable WL metadata; "
            f"found {nx.__version__}"
        )
    if sha256_file(VERIFIER_PATH) != VERIFIER_SHA256:
        raise RuntimeError("frozen verifier byte hash mismatch")
    if sha256_file(PRIOR_SUMMARY) != PRIOR_SUMMARY_SHA256:
        raise RuntimeError("prior topology summary byte hash mismatch")

    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run = HERE / "runs" / stamp
    run.mkdir(parents=True, exist_ok=False)
    events = run / "events.jsonl"

    prior = json.loads(PRIOR_SUMMARY.read_text(encoding="utf-8"))
    prior_hashes = set(prior["initial_topology_frequencies"])
    if len(prior_hashes) != 30:
        raise ValueError(f"expected 30 prior split topology hashes, found {len(prior_hashes)}")
    scales = (
        (1.0, 1.0, 1.0),
        (0.85, 1.0, 1.15),
        (1.15, 0.85, 1.0),
        (1.0, 1.15, 0.85),
    )
    seen_graphs: list[nx.Graph] = []
    graph_rows: list[tuple[Path, np.ndarray, nx.Graph, str, int, dict[str, int]]] = []
    input_paths = sorted(args.input_dir.glob("*.adj"))
    if len(input_paths) != 7:
        raise ValueError(f"expected exactly 7 input files, found {len(input_paths)}")
    for path in input_paths:
        adjacency, graph = read_adjacency(path)
        if not nx.is_connected(graph) or not nx.check_planarity(graph)[0]:
            raise ValueError(f"input is not connected planar: {path}")
        wl_hash = graph_hash(graph)
        if any(nx.is_isomorphic(graph, prior_graph) for prior_graph in seen_graphs):
            raise ValueError(f"isomorphic duplicate input: {path}")
        seen_graphs.append(graph)
        if wl_hash in prior_hashes:
            raise ValueError(f"input repeats a prior split topology: {path}")
        separation, distance_histogram = pentagon_distances(graph)
        if separation != 4:
            raise ValueError(f"expected separation-4 descendant, found {separation}: {path}")
        graph_rows.append((path, adjacency, graph, wl_hash, separation, distance_histogram))

    if len(graph_rows) != 7:
        raise ValueError(f"expected 7 graph classes, found {len(graph_rows)}")

    best: tuple[float, np.ndarray, int] | None = None
    accepted = 0
    trial = 0
    result_rows: list[dict[str, object]] = []
    final_representatives: list[nx.Graph] = []
    for path, adjacency, intended, wl_hash, separation, distances in graph_rows:
        for scale in scales:
            initial = spectral_embedding(adjacency, scale)
            initial_graph = hull_graph(initial)
            if edge_set(initial_graph) != edge_set(intended):
                append_event(
                    events,
                    {
                        "event": "rejected_embedding",
                        "trial": trial,
                        "source": path.name,
                        "scale": scale,
                        "graph_wl_hash": wl_hash,
                    },
                )
                trial += 1
                continue
            initial_score = energy_gradient(initial)[0]
            relaxed, diagnostics = relax(initial, args.rounds, args.maxiter)
            objective_score = float(diagnostics["score"])
            exact_score = verifier_score(relaxed)
            normalized = relaxed / np.linalg.norm(relaxed, axis=1, keepdims=True)
            final_graph = hull_graph(normalized)
            final_hash = graph_hash(final_graph)
            returned_isomorphic = nx.is_isomorphic(final_graph, intended)
            returned_labeled = edge_set(final_graph) == edge_set(intended)
            final_class = next(
                (
                    index
                    for index, representative in enumerate(final_representatives)
                    if nx.is_isomorphic(final_graph, representative)
                ),
                None,
            )
            if final_class is None:
                final_class = len(final_representatives)
                final_representatives.append(final_graph.copy())
            degree_histogram_counter = Counter(dict(final_graph.degree()).values())
            degree_histogram = {
                str(key): degree_histogram_counter[key]
                for key in sorted(degree_histogram_counter)
            }
            defect_free = degree_histogram_counter == Counter({5: 12, 6: 270})
            final_separation = pentagon_distances(final_graph)[0] if defect_free else None
            payload = {"vectors": relaxed.tolist()}
            candidate_path = run / "candidates" / f"trial_{trial:03d}.json"
            candidate_sha = write_once(candidate_path, payload)
            accepted += 1
            if best is None or exact_score < best[0]:
                best = (exact_score, relaxed.copy(), trial)
            result_rows.append(
                {
                    "trial": trial,
                    "score": exact_score,
                    "candidate_sha256": candidate_sha,
                    "source": path.name,
                    "source_retaining": returned_isomorphic,
                    "defect_free": defect_free,
                    "final_pentagon_separation": final_separation,
                    "final_exact_isomorphism_class": final_class,
                    "final_degree_histogram": degree_histogram,
                }
            )
            append_event(
                events,
                {
                    "event": "trial",
                    "trial": trial,
                    "source": path.name,
                    "source_sha256": sha256_file(path),
                    "graph_wl_hash": wl_hash,
                    "pentagon_separation": separation,
                    "pentagon_distance_histogram": distances,
                    "prior_split_wl_collision": False,
                    "scale": scale,
                    "initial_score": initial_score,
                    "optimizer_score": objective_score,
                    "verifier_score": exact_score,
                    "final_wl_hash": final_hash,
                    "final_exact_isomorphism_class": final_class,
                    "final_edge_count": final_graph.number_of_edges(),
                    "final_degree_histogram": degree_histogram,
                    "final_defect_free": defect_free,
                    "final_pentagon_separation": final_separation,
                    "returned_to_source_topology": returned_isomorphic,
                    "returned_to_source_labeled_edges": returned_labeled,
                    "target_at_or_below": GATE,
                    "gate_clearing": exact_score <= GATE,
                    "gate_gap": exact_score - GATE,
                    "candidate": f"candidates/{candidate_path.name}",
                    "candidate_sha256": candidate_sha,
                    "relaxation": diagnostics,
                },
            )
            trial += 1

    if best is None:
        raise RuntimeError("no spectral realization survived")
    if trial != 28 or accepted != 28:
        raise RuntimeError(f"expected 28 accepted trials, got trial={trial}, accepted={accepted}")
    best_score, best_points, best_trial = best
    best_sha = write_once(run / "best.json", {"vectors": best_points.tolist()})
    best_all = min(result_rows, key=lambda row: float(row["score"]))
    best_defect_free = min(
        (row for row in result_rows if bool(row["defect_free"])),
        key=lambda row: float(row["score"]),
    )
    best_source_retaining = min(
        (row for row in result_rows if bool(row["source_retaining"])),
        key=lambda row: float(row["score"]),
    )
    summary = {
        "status": "complete",
        "mode": "bounded C540-seeded C560 graph-output spectral release",
        "graph_class_count": len(graph_rows),
        "prior_split_graph_class_count": len(prior_hashes),
        "trial_count": trial,
        "accepted_trial_count": accepted,
        "source_retaining_count": sum(
            bool(row["source_retaining"]) for row in result_rows
        ),
        "defect_free_final_count": sum(bool(row["defect_free"]) for row in result_rows),
        "distinct_final_exact_isomorphism_class_count": len(final_representatives),
        "best_score": best_score,
        "best_trial": best_trial,
        "best_sha256": best_sha,
        "leader": LEADER,
        "minimum_improvement": MIN_IMPROVEMENT,
        "target_at_or_below": GATE,
        "best_gate_gap": best_score - GATE,
        "best_all": best_all,
        "best_defect_free": best_defect_free,
        "best_source_retaining": best_source_retaining,
        "gate_clearer": best_score <= GATE,
        "verifier_sha256": VERIFIER_SHA256,
        "verifier_bytes_checked": True,
        "networkx_version": NETWORKX_VERSION,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "python_version": platform.python_version(),
        "search_sha256": sha256_file(Path(__file__)),
        "prior_summary_sha256": PRIOR_SUMMARY_SHA256,
        "input_manifest": {
            path.name: sha256_file(path)
            for path, *_ in graph_rows
        },
        "scope_caveat": (
            "Seven distinct graph outputs from a bounded modified-buckygen "
            "generation seeded with the unique C540 (3,3) fullerene; not a "
            "complete or canonical enumeration of all C560 fullerenes."
        ),
    }
    summary_sha = write_once(run / "summary.json", summary)
    print(json.dumps({**summary, "summary_sha256": summary_sha}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
