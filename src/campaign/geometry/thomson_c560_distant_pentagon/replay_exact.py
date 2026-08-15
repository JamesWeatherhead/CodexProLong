#!/usr/bin/env python3
"""Independent clean-room replay for the frozen C560-descendant Thomson run.

The script hashes, but never imports or executes, the frozen Arena verifier.  It
reconstructs the verifier formula directly, revalidates every source graph and
spectral realization, and classifies final hull graphs by exact isomorphism.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.spatial import ConvexHull


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
N = 282
LEADER = 37147.29441846226
MIN_IMPROVEMENT = 1e-6
GATE = LEADER - MIN_IMPROVEMENT
NETWORKX_VERSION = "3.6.1"
VERIFIER_SHA256 = "4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af"
PRIOR_SUMMARY_SHA256 = "433dc3a15d958f4029f9d1152d4065bf4a29087c828ad1c5aa0b6fd411919cf3"
DEFAULT_VERIFIER = (
    REPOSITORY
    / "campaign/state/problems/thomson-problem"
    / f"{VERIFIER_SHA256}.py"
)
DEFAULT_INPUTS = HERE / "private_inputs"
DEFAULT_PRIOR_SUMMARY = (
    REPOSITORY
    / "campaign/geometry/thomson_282_topology_escape/runs"
    / "20260815T_THOMSON_SPLIT_V1/summary.json"
)
SCALES = (
    (1.0, 1.0, 1.0),
    (0.85, 1.0, 1.15),
    (1.15, 0.85, 1.0),
    (1.0, 1.15, 0.85),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def edge_set(graph: nx.Graph) -> set[tuple[int, int]]:
    return {tuple(sorted((int(first), int(second)))) for first, second in graph.edges()}


def graph_hash(graph: nx.Graph) -> str:
    return nx.weisfeiler_lehman_graph_hash(graph, iterations=20)


def read_adjacency(path: Path) -> tuple[np.ndarray, nx.Graph]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or int(lines[0]) != N or len(lines) != N + 1:
        raise ValueError(f"invalid order/line count: {path}")
    adjacency = np.zeros((N, N), dtype=np.float64)
    graph = nx.Graph()
    graph.add_nodes_from(range(N))
    for vertex, line in enumerate(lines[1:]):
        values = [int(item) for item in line.split()]
        degree, neighbours = values[0], values[1:]
        if degree != len(neighbours) or degree not in (5, 6):
            raise ValueError(f"invalid degree row {vertex}: {path}")
        if len(set(neighbours)) != degree or vertex in neighbours:
            raise ValueError(f"invalid neighbour row {vertex}: {path}")
        for neighbour in neighbours:
            if not 0 <= neighbour < N:
                raise ValueError(f"out-of-range neighbour: {path}")
            adjacency[vertex, neighbour] = 1.0
            graph.add_edge(vertex, neighbour)
    if not np.array_equal(adjacency, adjacency.T):
        raise ValueError(f"asymmetric adjacency: {path}")
    if Counter(dict(graph.degree()).values()) != Counter({5: 12, 6: 270}):
        raise ValueError(f"wrong source degree histogram: {path}")
    if graph.number_of_edges() != 840 or not nx.is_connected(graph):
        raise ValueError(f"wrong edge/connectivity invariant: {path}")
    if not nx.check_planarity(graph)[0]:
        raise ValueError(f"nonplanar source graph: {path}")
    return adjacency, graph


def five_vertex_distance(graph: nx.Graph) -> tuple[int, dict[str, int]]:
    degree_five = [vertex for vertex, degree in graph.degree() if degree == 5]
    if len(degree_five) < 2:
        raise ValueError("fewer than two degree-five vertices")
    distances: list[int] = []
    for index, first in enumerate(degree_five):
        lengths = nx.single_source_shortest_path_length(graph, first)
        distances.extend(lengths[second] for second in degree_five[index + 1 :])
    counts = Counter(distances)
    return min(distances), {str(key): counts[key] for key in sorted(counts)}


def spectral_embedding(adjacency: np.ndarray, scales: tuple[float, float, float]) -> np.ndarray:
    laplacian = np.diag(adjacency.sum(axis=1)) - adjacency
    eigenvalues, eigenvectors = np.linalg.eigh(laplacian)
    if eigenvalues[1] <= 1e-10 or eigenvalues[4] - eigenvalues[3] <= 1e-8:
        raise ValueError("disconnected or spectrally ambiguous source")
    points = eigenvectors[:, 1:4] * np.asarray(scales)[None, :]
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    if np.any(norms < 1e-12):
        raise ValueError("degenerate spectral row")
    return points / norms


def normalize(points: np.ndarray) -> tuple[np.ndarray, float]:
    if points.shape != (N, 3) or not np.isfinite(points).all():
        raise ValueError("candidate shape/finiteness failure")
    raw_norms = np.linalg.norm(points, axis=1, keepdims=True)
    maximum_error = float(np.max(np.abs(raw_norms - 1.0)))
    norms = raw_norms.copy()
    norms[norms < 1e-12] = 1e-12
    return points / norms, maximum_error


def verifier_energy(points: np.ndarray) -> tuple[float, float, float, bool, bool]:
    raw_norms = np.linalg.norm(points, axis=1)
    norm_clamp_active = bool(np.any(raw_norms < 1e-12))
    normalized, norm_error = normalize(points)
    differences = normalized[:, None, :] - normalized[None, :, :]
    distance_sq = np.sum(differences**2, axis=2)
    upper = np.triu_indices(N, k=1)
    distances = np.sqrt(distance_sq[upper])
    minimum_distance = float(np.min(distances))
    distance_clamp_active = bool(np.any(distances < 1e-12))
    distances[distances < 1e-12] = 1e-12
    return (
        float(np.sum(1.0 / distances)),
        norm_error,
        minimum_distance,
        norm_clamp_active,
        distance_clamp_active,
    )


def hull_graph(points: np.ndarray) -> nx.Graph:
    normalized, _ = normalize(points)
    graph = nx.Graph()
    graph.add_nodes_from(range(N))
    for first, second, third in ConvexHull(normalized).simplices:
        graph.add_edges_from(
            (
                (int(first), int(second)),
                (int(second), int(third)),
                (int(third), int(first)),
            )
        )
    return graph


def graph_class(graph: nx.Graph, representatives: list[nx.Graph]) -> int:
    for index, representative in enumerate(representatives):
        if nx.is_isomorphic(graph, representative):
            return index
    representatives.append(graph.copy())
    return len(representatives) - 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUTS)
    parser.add_argument("--prior-summary", type=Path, default=DEFAULT_PRIOR_SUMMARY)
    parser.add_argument("--verifier", type=Path, default=DEFAULT_VERIFIER)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if nx.__version__ != NETWORKX_VERSION:
        raise RuntimeError(
            f"NetworkX {NETWORKX_VERSION} required; found {nx.__version__}"
        )
    if sha256(args.verifier) != VERIFIER_SHA256:
        raise ValueError("frozen verifier byte hash mismatch")

    run = args.run.resolve()
    summary_path = run / "summary.json"
    events_path = run / "events.jsonl"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("search_sha256") != sha256(HERE / "search.py"):
        raise ValueError("search source hash mismatch")
    if summary.get("prior_summary_sha256") != PRIOR_SUMMARY_SHA256:
        raise ValueError("prior-summary pin mismatch")
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    trials = [event for event in events if event.get("event") == "trial"]
    if len(events) != 28 or len(trials) != 28:
        raise ValueError("expected exactly 28 accepted trial events")
    if sorted(int(event["trial"]) for event in trials) != list(range(28)):
        raise ValueError("trial IDs are not unique and complete")
    trials.sort(key=lambda event: int(event["trial"]))
    if int(summary["accepted_trial_count"]) != 28 or int(summary["trial_count"]) != 28:
        raise ValueError("summary trial-count mismatch")

    input_paths = sorted(args.input_dir.glob("*.adj"))
    if len(input_paths) != 7:
        raise ValueError(f"expected exactly seven input graphs, found {len(input_paths)}")
    inputs: dict[str, tuple[np.ndarray, nx.Graph]] = {}
    source_representatives: list[nx.Graph] = []
    if sha256(args.prior_summary) != PRIOR_SUMMARY_SHA256:
        raise ValueError("prior summary byte hash mismatch")
    prior_hashes = set(
        json.loads(args.prior_summary.read_text(encoding="utf-8"))[
            "initial_topology_frequencies"
        ]
    )
    if len(prior_hashes) != 30:
        raise ValueError("prior split topology count mismatch")
    for path in input_paths:
        adjacency, graph = read_adjacency(path)
        if any(nx.is_isomorphic(graph, prior) for prior in source_representatives):
            raise ValueError(f"isomorphic duplicate source: {path.name}")
        source_representatives.append(graph.copy())
        source_hash = sha256(path)
        if summary["input_manifest"].get(path.name) != source_hash:
            raise ValueError(f"source manifest mismatch: {path.name}")
        wl_hash = graph_hash(graph)
        if wl_hash in prior_hashes:
            raise ValueError(f"WL collision with prior split corpus: {path.name}")
        separation, histogram = five_vertex_distance(graph)
        if separation != 4 or histogram.get("4") != 2:
            raise ValueError(f"unexpected source pentagon distances: {path.name}")
        inputs[path.name] = (adjacency, graph)

    by_source: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    final_representatives: list[nx.Graph] = []
    rows: list[dict[str, object]] = []
    max_event_score_delta = 0.0
    max_initial_score_delta = 0.0
    max_norm_error = 0.0
    min_pair_distance = float("inf")
    norm_clamp_count = 0
    distance_clamp_count = 0
    for event in trials:
        trial = int(event["trial"])
        source = str(event["source"])
        if source not in inputs:
            raise ValueError(f"unknown source in trial {trial}: {source}")
        by_source[source].append(event)
        expected_scale = SCALES[trial % 4]
        scale = tuple(float(value) for value in event["scale"])
        if scale != expected_scale or source != input_paths[trial // 4].name:
            raise ValueError(f"source/scale schedule mismatch at trial {trial}")
        adjacency, intended = inputs[source]
        source_path = args.input_dir / source
        if event["source_sha256"] != sha256(source_path):
            raise ValueError(f"source hash mismatch at trial {trial}")
        source_wl = graph_hash(intended)
        source_separation, source_histogram = five_vertex_distance(intended)
        if event["graph_wl_hash"] != source_wl:
            raise ValueError(f"source WL mismatch at trial {trial}")
        if int(event["pentagon_separation"]) != source_separation:
            raise ValueError(f"source separation mismatch at trial {trial}")
        if event["pentagon_distance_histogram"] != source_histogram:
            raise ValueError(f"source distance histogram mismatch at trial {trial}")

        initial = spectral_embedding(adjacency, expected_scale)
        if edge_set(hull_graph(initial)) != edge_set(intended):
            raise ValueError(f"spectral hull mismatch at trial {trial}")
        initial_score = verifier_energy(initial)[0]
        max_initial_score_delta = max(
            max_initial_score_delta,
            abs(initial_score - float(event["initial_score"])),
        )
        if abs(initial_score - float(event["initial_score"])) > 1e-10:
            raise ValueError(f"initial score mismatch at trial {trial}")

        candidate = run / "candidates" / f"trial_{trial:03d}.json"
        recorded_candidate = Path(str(event["candidate"]))
        if str(recorded_candidate) != f"candidates/{candidate.name}":
            raise ValueError(f"candidate path metadata mismatch at trial {trial}")
        if sha256(candidate) != event["candidate_sha256"]:
            raise ValueError(f"candidate hash mismatch at trial {trial}")
        points = np.asarray(
            json.loads(candidate.read_text(encoding="utf-8"))["vectors"],
            dtype=np.float64,
        )
        (
            exact_score,
            norm_error,
            pair_distance,
            norm_clamp_active,
            distance_clamp_active,
        ) = verifier_energy(points)
        if "verifier_score" not in event or "optimizer_score" not in event:
            raise ValueError(f"corrected score fields absent at trial {trial}")
        event_score = float(event["verifier_score"])
        delta = abs(exact_score - event_score)
        max_event_score_delta = max(max_event_score_delta, delta)
        if delta > 1e-10:
            raise ValueError(f"candidate score mismatch at trial {trial}")
        max_norm_error = max(max_norm_error, norm_error)
        min_pair_distance = min(min_pair_distance, pair_distance)
        norm_clamp_count += int(norm_clamp_active)
        distance_clamp_count += int(distance_clamp_active)

        final_graph = hull_graph(points)
        if graph_hash(final_graph) != event["final_wl_hash"]:
            raise ValueError(f"final WL mismatch at trial {trial}")
        returned = nx.is_isomorphic(final_graph, intended)
        if bool(event["returned_to_source_topology"]) != returned:
            raise ValueError(f"source-return metadata mismatch at trial {trial}")
        final_class = graph_class(final_graph, final_representatives)
        degree_histogram = Counter(dict(final_graph.degree()).values())
        defect_free = degree_histogram == Counter({5: 12, 6: 270})
        final_separation = five_vertex_distance(final_graph)[0] if defect_free else None
        rendered_histogram = {
            str(key): degree_histogram[key] for key in sorted(degree_histogram)
        }
        if int(event["final_exact_isomorphism_class"]) != final_class:
            raise ValueError(f"final exact class mismatch at trial {trial}")
        if int(event["final_edge_count"]) != final_graph.number_of_edges():
            raise ValueError(f"final edge-count mismatch at trial {trial}")
        if event["final_degree_histogram"] != rendered_histogram:
            raise ValueError(f"final degree-histogram mismatch at trial {trial}")
        if bool(event["final_defect_free"]) != defect_free:
            raise ValueError(f"final defect-free mismatch at trial {trial}")
        if event["final_pentagon_separation"] != final_separation:
            raise ValueError(f"final separation mismatch at trial {trial}")
        if bool(event["returned_to_source_labeled_edges"]) != (
            edge_set(final_graph) == edge_set(intended)
        ):
            raise ValueError(f"labeled-return mismatch at trial {trial}")
        if bool(event["gate_clearing"]) != (exact_score <= GATE):
            raise ValueError(f"gate flag mismatch at trial {trial}")
        if float(event["target_at_or_below"]) != GATE:
            raise ValueError(f"target metadata mismatch at trial {trial}")
        if abs(float(event["gate_gap"]) - (exact_score - GATE)) > 1e-12:
            raise ValueError(f"gate gap mismatch at trial {trial}")
        rows.append(
            {
                "trial": trial,
                "source": source,
                "score": exact_score,
                "candidate_sha256": sha256(candidate),
                "source_retaining": returned,
                "defect_free": defect_free,
                "final_pentagon_separation": final_separation,
                "final_class": final_class,
                "final_wl_hash": graph_hash(final_graph),
                "degree_histogram": rendered_histogram,
            }
        )

    if any(len(by_source[path.name]) != 4 for path in input_paths):
        raise ValueError("source trial multiplicity mismatch")
    if max_initial_score_delta > 1e-10:
        raise ValueError("initial-score aggregate mismatch")

    best_all = min(rows, key=lambda row: float(row["score"]))
    best_defect_free = min(
        (row for row in rows if bool(row["defect_free"])),
        key=lambda row: float(row["score"]),
    )
    best_source_retaining = min(
        (row for row in rows if bool(row["source_retaining"])),
        key=lambda row: float(row["score"]),
    )
    best_path = run / "best.json"
    if sha256(best_path) != summary["best_sha256"]:
        raise ValueError("best artifact hash mismatch")
    best_score = verifier_energy(
        np.asarray(
            json.loads(best_path.read_text(encoding="utf-8"))["vectors"],
            dtype=np.float64,
        )
    )[0]
    if abs(best_score - float(best_all["score"])) > 1e-10:
        raise ValueError("best artifact is not the replayed minimum")
    if summary.get("verifier_sha256") != VERIFIER_SHA256:
        raise ValueError("summary verifier hash mismatch")
    if abs(float(summary["best_score"]) - float(best_all["score"])) > 1e-12:
        raise ValueError("summary best score mismatch")
    if int(summary["best_trial"]) != int(best_all["trial"]):
        raise ValueError("summary best trial mismatch")
    if summary["best_sha256"] != best_all["candidate_sha256"]:
        raise ValueError("best bytes do not match winning trial")

    defect_free_count = sum(bool(row["defect_free"]) for row in rows)
    source_retaining_count = sum(bool(row["source_retaining"]) for row in rows)
    if int(summary["source_retaining_count"]) != source_retaining_count:
        raise ValueError("summary source-retaining count mismatch")
    if int(summary["defect_free_final_count"]) != defect_free_count:
        raise ValueError("summary defect-free count mismatch")
    if int(summary["distinct_final_exact_isomorphism_class_count"]) != len(
        final_representatives
    ):
        raise ValueError("summary exact-class count mismatch")
    degree_histograms = Counter(
        json.dumps(row["degree_histogram"], sort_keys=True) for row in rows
    )
    result = {
        "status": "pass",
        "run": f"runs/{run.name}",
        "networkx_version": NETWORKX_VERSION,
        "frozen_verifier_sha256": sha256(args.verifier),
        "frozen_verifier_executed": False,
        "formula": (
            "float64 row normalization with norms below 1e-12 clamped; "
            "float64 pair distances below 1e-12 clamped; sum 1/d for i<j"
        ),
        "leader": LEADER,
        "minimum_improvement": MIN_IMPROVEMENT,
        "strict_target_at_or_below": GATE,
        "trial_count": len(rows),
        "source_graph_count": len(inputs),
        "source_graph_scope": (
            "seven distinct graph outputs from a bounded modified-buckygen "
            "generation seeded with the unique C540 Goldberg (3,3) fullerene; "
            "not a complete or canonical C560 enumeration"
        ),
        "source_graph_invariants": {
            "vertices": N,
            "edges": 840,
            "degree_histogram": {"5": 12, "6": 270},
            "connected_planar": True,
            "minimum_pentagon_separation": 4,
            "pairs_at_minimum_separation": 2,
            "prior_split_wl_collision_count": 0,
        },
        "source_retaining_count": source_retaining_count,
        "defect_free_final_count": defect_free_count,
        "distinct_final_exact_isomorphism_class_count": len(final_representatives),
        "degree_histogram_frequencies": dict(sorted(degree_histograms.items())),
        "best_all": best_all,
        "best_all_gate_gap": float(best_all["score"]) - GATE,
        "best_defect_free": best_defect_free,
        "best_defect_free_gate_gap": float(best_defect_free["score"]) - GATE,
        "best_source_retaining": best_source_retaining,
        "best_source_retaining_gate_gap": float(best_source_retaining["score"]) - GATE,
        "gate_clearer": float(best_all["score"]) <= GATE,
        "maximum_candidate_norm_error": max_norm_error,
        "minimum_candidate_pair_distance": min_pair_distance,
        "maximum_recorded_score_delta": max_event_score_delta,
        "maximum_initial_score_delta": max_initial_score_delta,
        "norm_clamp_trial_count": norm_clamp_count,
        "distance_clamp_trial_count": distance_clamp_count,
        "clamps_active": bool(norm_clamp_count or distance_clamp_count),
        "input_manifest": summary["input_manifest"],
        "prior_summary_sha256": PRIOR_SUMMARY_SHA256,
        "events_sha256": sha256(events_path),
        "summary_sha256": sha256(summary_path),
        "best_sha256": sha256(best_path),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
