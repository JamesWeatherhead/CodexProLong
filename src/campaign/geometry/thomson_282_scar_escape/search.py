#!/usr/bin/env python3
"""Deterministic N=282 scar/dislocation topology escape search.

The only seed is the frozen public incumbent in the campaign snapshot.  Legal
2-2 flips are applied directly to its N=282 spherical Delaunay triangulation;
no N=72 construction or split source is used.  Each mutated realization is
released by tangent-coordinate L-BFGS against the literal Coulomb objective.

This program has no network, Arena, Git, subprocess, or dynamic-code path.
All generated files are confined to ``runs/<stamp>/`` below this directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import networkx as nx
import numpy as np
from scipy.optimize import minimize
from scipy.spatial import ConvexHull


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
SNAPSHOT = CAMPAIGN / "geometry/snapshots/thomson-problem_20260814T234236Z.json"
VERIFIER_SHA256 = "4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af"
VERIFIER = CAMPAIGN / f"state/problems/thomson-problem/{VERIFIER_SHA256}.py"
LEADER_SOLUTION_ID = 561
N = 282

Face = tuple[int, int, int]
Edge = tuple[int, int]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()


def write_once(path: Path, value: object) -> str:
    raw = canonical_json(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
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


def normalize(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    if points.shape != (N, 3) or not np.isfinite(points).all():
        raise ValueError(f"invalid point array {points.shape}")
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    if np.any(norms < 1e-12):
        raise ValueError("zero or near-zero vector")
    return points / norms


def faces_from_points(points: np.ndarray) -> frozenset[Face]:
    return frozenset(
        tuple(sorted(int(value) for value in face))
        for face in ConvexHull(points).simplices
    )


def triangulation_data(
    faces: frozenset[Face],
) -> tuple[set[Edge], dict[Edge, tuple[int, int]], np.ndarray]:
    edges: set[Edge] = set()
    raw_opposites: dict[Edge, list[int]] = defaultdict(list)
    for a, b, c in faces:
        for first, second, opposite in ((a, b, c), (a, c, b), (b, c, a)):
            edge = tuple(sorted((first, second)))
            edges.add(edge)
            raw_opposites[edge].append(opposite)
    if any(len(value) != 2 for value in raw_opposites.values()):
        raise ValueError("not a closed triangular sphere")
    opposites = {
        edge: tuple(sorted(value)) for edge, value in raw_opposites.items()
    }
    degrees = np.zeros(N, dtype=np.int16)
    for a, b in edges:
        degrees[a] += 1
        degrees[b] += 1
    return edges, opposites, degrees


def graph_from_faces(faces: frozenset[Face]) -> nx.Graph:
    edges, _, _ = triangulation_data(faces)
    graph = nx.Graph()
    graph.add_nodes_from(range(N))
    graph.add_edges_from(edges)
    return graph


def faces_hash(faces: frozenset[Face]) -> str:
    raw = json.dumps(sorted(faces), separators=(",", ":")).encode()
    return sha256_bytes(raw)


def degree_histogram(degrees: np.ndarray) -> dict[str, int]:
    return {
        str(int(key)): int(value)
        for key, value in sorted(Counter(int(item) for item in degrees).items())
    }


def topology(points: np.ndarray) -> dict[str, object]:
    faces = faces_from_points(points)
    edges, _, degrees = triangulation_data(faces)
    graph = graph_from_faces(faces)
    return {
        "face_count": len(faces),
        "edge_count": len(edges),
        "degree_histogram": degree_histogram(degrees),
        "faces_sha256": faces_hash(faces),
        "wl_hash": nx.weisfeiler_lehman_graph_hash(graph, iterations=20),
    }


def legal_flips(faces: frozenset[Face]) -> Iterable[tuple[Edge, Edge]]:
    edges, opposites, _ = triangulation_data(faces)
    for edge in sorted(opposites):
        opposite = opposites[edge]
        if tuple(sorted(opposite)) not in edges:
            yield edge, opposite


def apply_flip(faces: frozenset[Face], edge: Edge, opposite: Edge) -> frozenset[Face]:
    a, b = edge
    c, d = opposite
    removed = {tuple(sorted((a, b, c))), tuple(sorted((a, b, d)))}
    if not removed <= faces:
        raise ValueError(f"invalid flip {edge}/{opposite}")
    return frozenset(
        (set(faces) - removed)
        | {tuple(sorted((c, d, a))), tuple(sorted((c, d, b)))}
    )


@dataclass(frozen=True)
class Move:
    edge: Edge
    opposite: Edge

    def as_json(self) -> dict[str, list[int]]:
        return {"edge": list(self.edge), "opposite": list(self.opposite)}


@dataclass
class Mutation:
    operator: str
    moves: tuple[Move, ...]
    faces: frozenset[Face]
    parent: str | None

    @property
    def face_hash(self) -> str:
        return faces_hash(self.faces)

    @property
    def graph(self) -> nx.Graph:
        return graph_from_faces(self.faces)

    @property
    def wl_hash(self) -> str:
        return nx.weisfeiler_lehman_graph_hash(self.graph, iterations=20)

    @property
    def histogram(self) -> dict[str, int]:
        return degree_histogram(triangulation_data(self.faces)[2])


def is_allowed_defects(degrees: np.ndarray) -> bool:
    return bool(np.all((degrees >= 5) & (degrees <= 7)))


def exact_class_add(
    target: list[Mutation], candidate: Mutation, *, compare_all: bool = False
) -> bool:
    """Append only if no same-WL exact graph isomorph already exists."""
    candidate_wl = candidate.wl_hash
    candidate_graph: nx.Graph | None = None
    for prior in target:
        if prior.wl_hash != candidate_wl and not compare_all:
            continue
        candidate_graph = candidate_graph or candidate.graph
        if nx.is_isomorphic(candidate_graph, prior.graph):
            return False
    target.append(candidate)
    return True


def local_vertices(graph: nx.Graph, seeds: set[int], radius: int) -> set[int]:
    result = set(seeds)
    frontier = set(seeds)
    for _ in range(radius):
        frontier = {v for u in frontier for v in graph.neighbors(u)} - result
        result |= frontier
    return result


def enumerate_mutations(base: frozenset[Face]) -> tuple[list[Mutation], dict[str, int]]:
    """Enumerate bounded exact topology classes around the incumbent graph."""
    _, _, base_degrees = triangulation_data(base)
    if degree_histogram(base_degrees) != {"5": 12, "6": 270}:
        raise ValueError("incumbent is not the expected defect-free triangulation")

    mini: list[Mutation] = []
    stone_wales: list[Mutation] = []
    raw_counts: Counter[str] = Counter()
    for edge, opposite in legal_flips(base):
        changed = apply_flip(base, edge, opposite)
        _, _, degrees = triangulation_data(changed)
        histogram = degree_histogram(degrees)
        move = Move(edge, opposite)
        if histogram == {"5": 13, "6": 268, "7": 1}:
            raw_counts["mini_scar"] += 1
            exact_class_add(mini, Mutation("mini_scar", (move,), changed, None))
        elif histogram == {"5": 14, "6": 266, "7": 2}:
            raw_counts["stone_wales"] += 1
            exact_class_add(
                stone_wales, Mutation("stone_wales", (move,), changed, None)
            )

    scar_glide_1: list[Mutation] = []
    scar_extension: list[Mutation] = []
    for source in mini:
        graph = source.graph
        first_vertices = set(source.moves[0].edge) | set(source.moves[0].opposite)
        neighborhood = local_vertices(graph, first_vertices, 2)
        for edge, opposite in legal_flips(source.faces):
            if not (set(edge) | set(opposite)) <= neighborhood:
                continue
            changed = apply_flip(source.faces, edge, opposite)
            _, _, degrees = triangulation_data(changed)
            if not is_allowed_defects(degrees):
                continue
            histogram = degree_histogram(degrees)
            moves = source.moves + (Move(edge, opposite),)
            if histogram == {"5": 13, "6": 268, "7": 1}:
                raw_counts["scar_glide_1"] += 1
                exact_class_add(
                    scar_glide_1,
                    Mutation("scar_glide_1", moves, changed, source.face_hash),
                )
            elif histogram == {"5": 14, "6": 266, "7": 2}:
                raw_counts["scar_extension"] += 1
                exact_class_add(
                    scar_extension,
                    Mutation("scar_extension", moves, changed, source.face_hash),
                )

    scar_glide_2: list[Mutation] = []
    earlier_faces = {base} | {item.faces for item in mini + scar_glide_1}
    for source in scar_glide_1:
        _, _, degrees = triangulation_data(source.faces)
        defect_nodes = set(int(i) for i in np.flatnonzero(degrees != 6))
        neighborhood = local_vertices(source.graph, defect_nodes, 1)
        for edge, opposite in legal_flips(source.faces):
            if not (set(edge) | set(opposite)) <= neighborhood:
                continue
            changed = apply_flip(source.faces, edge, opposite)
            if changed in earlier_faces:
                continue
            _, _, next_degrees = triangulation_data(changed)
            if degree_histogram(next_degrees) != {"5": 13, "6": 268, "7": 1}:
                continue
            raw_counts["scar_glide_2"] += 1
            exact_class_add(
                scar_glide_2,
                Mutation(
                    "scar_glide_2",
                    source.moves + (Move(edge, opposite),),
                    changed,
                    source.face_hash,
                ),
            )

    stone_wales_glide: list[Mutation] = []
    for source in stone_wales:
        _, _, degrees = triangulation_data(source.faces)
        defect_nodes = set(int(i) for i in np.flatnonzero(degrees != 6))
        neighborhood = local_vertices(source.graph, defect_nodes, 1)
        local_candidates: list[Mutation] = []
        for edge, opposite in legal_flips(source.faces):
            if not (set(edge) | set(opposite)) <= neighborhood:
                continue
            changed = apply_flip(source.faces, edge, opposite)
            if changed == base:
                continue
            _, _, next_degrees = triangulation_data(changed)
            if degree_histogram(next_degrees) != {"5": 14, "6": 266, "7": 2}:
                continue
            raw_counts["stone_wales_glide"] += 1
            local_candidates.append(
                Mutation(
                    "stone_wales_glide",
                    source.moves + (Move(edge, opposite),),
                    changed,
                    source.face_hash,
                )
            )
        for candidate in sorted(local_candidates, key=lambda item: item.face_hash)[:4]:
            exact_class_add(stone_wales_glide, candidate)

    families = [
        mini,
        scar_glide_1[:8],
        scar_glide_2[:12],
        scar_extension[:12],
        stone_wales,
        stone_wales_glide[:24],
    ]
    result = [item for family in families for item in family]
    global_graph_classes: list[Mutation] = []
    for item in result:
        exact_class_add(global_graph_classes, item)
    counts = {name: int(value) for name, value in sorted(raw_counts.items())}
    counts.update(
        {
            "selected_path_count": len(result),
            "selected_unique_graph_class_count": len(global_graph_classes),
            "selected_mini_scar": len(families[0]),
            "selected_scar_glide_1": len(families[1]),
            "selected_scar_glide_2": len(families[2]),
            "selected_scar_extension": len(families[3]),
            "selected_stone_wales": len(families[4]),
            "selected_stone_wales_glide": len(families[5]),
        }
    )
    return result, counts


def force_flip(points: np.ndarray, edge: Edge, opposite: Edge, fraction: float) -> np.ndarray:
    a, b = edge
    c, d = opposite
    result = points.copy()

    def unit(row: np.ndarray) -> np.ndarray:
        return row / np.linalg.norm(row)

    result[c] = unit((1.0 - fraction) * points[c] + fraction * points[d])
    result[d] = unit((1.0 - fraction) * points[d] + fraction * points[c])
    result[a] = unit((1.0 + fraction) * points[a] - fraction * points[b])
    result[b] = unit((1.0 + fraction) * points[b] - fraction * points[a])
    return normalize(result)


def realize_mutation(
    base_points: np.ndarray,
    base_faces: frozenset[Face],
    mutation: Mutation,
    requested_fraction: float,
) -> tuple[np.ndarray, list[float]]:
    points = base_points.copy()
    faces = base_faces
    used: list[float] = []
    for move in mutation.moves:
        target = apply_flip(faces, move.edge, move.opposite)
        fractions = [
            requested_fraction,
            requested_fraction * 0.9,
            requested_fraction * 1.1,
            0.10,
            0.12,
            0.14,
            0.16,
            0.18,
            0.20,
        ]
        realized = None
        for fraction in dict.fromkeys(round(value, 12) for value in fractions):
            if not 0.0 < fraction < 0.5:
                continue
            candidate = force_flip(points, move.edge, move.opposite, fraction)
            if faces_from_points(candidate) == target:
                realized = candidate
                used.append(fraction)
                break
        if realized is None:
            raise RuntimeError(f"could not realize exact flip {move}")
        points, faces = realized, target
    if faces != mutation.faces:
        raise AssertionError("realized mutation path mismatch")
    return points, used


def energy_gradient(points: np.ndarray) -> tuple[float, np.ndarray]:
    differences = points[:, None, :] - points[None, :, :]
    distances = np.linalg.norm(differences, axis=2)
    np.fill_diagonal(distances, np.inf)
    inverse = 1.0 / distances
    energy = float(np.sum(1.0 / distances[np.triu_indices(N, k=1)]))
    gradient = -(differences * inverse[:, :, None] ** 3).sum(axis=1)
    return energy, gradient


def frozen_formula(points: np.ndarray) -> float:
    """Literal independent transcription of the frozen verifier formula."""
    vectors = np.array(points, dtype=np.float64)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms < 1e-12] = 1e-12
    vectors = vectors / norms
    diffs = vectors[:, None, :] - vectors[None, :, :]
    dist_sq = np.sum(diffs**2, axis=2)
    iu = np.triu_indices(N, k=1)
    dists = np.sqrt(dist_sq[iu])
    dists[dists < 1e-12] = 1e-12
    return float(np.sum(1.0 / dists))


def tangent_basis(points: np.ndarray) -> np.ndarray:
    basis = np.empty((N, 2, 3), dtype=np.float64)
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
    tangent = parameters.reshape(N, 2)
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
            np.zeros(2 * N),
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
        "internal_energy": energy,
        "iterations": iterations,
        "evaluations": evaluations,
        "projected_gradient_max": float(np.max(np.linalg.norm(tangent, axis=1))),
        "projected_gradient_total": float(np.linalg.norm(tangent)),
        "messages": messages,
    }


def parse_amplitudes(value: str) -> list[float]:
    result = [float(item) for item in value.split(",") if item.strip()]
    if not result or any(not 0.0 < item < 0.5 for item in result):
        raise argparse.ArgumentTypeError("amplitudes must lie in (0, 0.5)")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--amplitudes", type=parse_amplitudes, default=[0.10, 0.16])
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--maxiter", type=int, default=700)
    parser.add_argument("--mutation-cap", type=int, default=96)
    parser.add_argument("--stamp")
    args = parser.parse_args()
    if args.rounds < 1 or args.maxiter < 1 or args.mutation_cap < 1:
        raise ValueError("positive bounds required")

    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run = HERE / "runs" / stamp
    run.mkdir(parents=True, exist_ok=False)
    events = run / "events.jsonl"

    snapshot_raw = SNAPSHOT.read_bytes()
    snapshot = json.loads(snapshot_raw)
    if sha256_path(VERIFIER) != VERIFIER_SHA256:
        raise ValueError("frozen verifier hash mismatch")
    embedded = snapshot["problem"]["verifier"].encode()
    if sha256_bytes(embedded) != VERIFIER_SHA256:
        raise ValueError("snapshot verifier hash mismatch")
    solution = next(
        item for item in snapshot["solutions"] if int(item["id"]) == LEADER_SOLUTION_ID
    )
    incumbent = normalize(np.asarray(solution["data"]["vectors"], dtype=np.float64))
    incumbent_score = frozen_formula(incumbent)
    live_score = float(snapshot["solutions"][0]["score"])
    min_improvement = float(snapshot["problem"]["minImprovement"])
    gate = live_score - min_improvement
    base_faces = faces_from_points(incumbent)
    incumbent_topology = topology(incumbent)

    mutations, enumeration = enumerate_mutations(base_faces)
    mutations = mutations[: args.mutation_cap]
    topology_payload = {
        "source": "frozen N=282 incumbent triangulation (solution 561)",
        "explicit_non_source": "No N=72 graph, class, coordinates, or split construction is read.",
        "enumeration": enumeration,
        "selected_count_after_cap": len(mutations),
        "mutations": [
            {
                "mutation_id": index,
                "operator": item.operator,
                "parent_faces_sha256": item.parent,
                "moves": [move.as_json() for move in item.moves],
                "faces_sha256": item.face_hash,
                "wl_hash": item.wl_hash,
                "degree_histogram": item.histogram,
            }
            for index, item in enumerate(mutations)
        ],
    }
    topology_sha = write_once(run / "topology_classes.json", topology_payload)
    append_event(
        events,
        {
            "event": "start",
            "stamp": stamp,
            "snapshot": "../../snapshots/thomson-problem_20260814T234236Z.json",
            "snapshot_sha256": sha256_bytes(snapshot_raw),
            "verifier": "../../../state/problems/thomson-problem/" + VERIFIER_SHA256 + ".py",
            "verifier_sha256": VERIFIER_SHA256,
            "solution_id": LEADER_SOLUTION_ID,
            "live_score": live_score,
            "normalized_incumbent_score": incumbent_score,
            "target_strictly_below": gate,
            "incumbent_topology": incumbent_topology,
            "topology_classes_sha256": topology_sha,
            "bounds": {
                "amplitudes": args.amplitudes,
                "rounds": args.rounds,
                "maxiter": args.maxiter,
                "mutation_cap": args.mutation_cap,
            },
        },
    )

    best_score = math.inf
    best_points: np.ndarray | None = None
    best_trial = -1
    best_operator = ""
    trial_count = 0
    gate_clearers = 0
    final_topologies: Counter[str] = Counter()
    returned_to_incumbent = 0
    failures: list[dict[str, object]] = []
    incumbent_wl = str(incumbent_topology["wl_hash"])

    for mutation_id, mutation in enumerate(mutations):
        for requested_fraction in args.amplitudes:
            trial = trial_count
            trial_count += 1
            try:
                initial, used = realize_mutation(
                    incumbent, base_faces, mutation, requested_fraction
                )
            except RuntimeError as exc:
                failure = {
                    "event": "realization_failure",
                    "trial": trial,
                    "mutation_id": mutation_id,
                    "operator": mutation.operator,
                    "requested_fraction": requested_fraction,
                    "error": str(exc),
                }
                failures.append(failure)
                append_event(events, failure)
                continue
            initial_score = frozen_formula(initial)
            initial_topology = topology(initial)
            if initial_topology["faces_sha256"] != mutation.face_hash:
                raise AssertionError("initial topology differs from enumerated mutation")
            relaxed, diagnostics = relax(initial, args.rounds, args.maxiter)
            score = frozen_formula(relaxed)
            final_topology = topology(relaxed)
            final_wl = str(final_topology["wl_hash"])
            final_topologies[final_wl] += 1
            returned = final_wl == incumbent_wl
            returned_to_incumbent += int(returned)
            gate_clearing = score < gate
            gate_clearers += int(gate_clearing)
            if score < best_score:
                best_score = score
                best_points = relaxed.copy()
                best_trial = trial
                best_operator = mutation.operator
            append_event(
                events,
                {
                    "event": "trial",
                    "trial": trial,
                    "mutation_id": mutation_id,
                    "operator": mutation.operator,
                    "move_count": len(mutation.moves),
                    "requested_fraction": requested_fraction,
                    "used_fractions": used,
                    "initial_score": initial_score,
                    "initial_topology": initial_topology,
                    "relaxation": diagnostics,
                    "frozen_formula_score": score,
                    "improvement_over_live": live_score - score,
                    "gate_gap": score - gate,
                    "gate_clearing": gate_clearing,
                    "final_topology": final_topology,
                    "returned_to_incumbent_wl": returned,
                },
            )
            if gate_clearing:
                break
        if gate_clearers:
            break

    if best_points is None:
        raise RuntimeError("no mutation realization completed")
    best_sha = write_once(run / "best_candidate.json", {"vectors": best_points.tolist()})
    summary = {
        "status": "gate_clearer" if gate_clearers else "bounded_negative_frontier",
        "mode": "direct N=282 legal 2-2 scar/dislocation flips plus spherical Coulomb L-BFGS",
        "explicit_exclusion": "No member of the closed 48-class N=72 split family was read or generated.",
        "snapshot_sha256": sha256_bytes(snapshot_raw),
        "verifier_sha256": VERIFIER_SHA256,
        "live_score": live_score,
        "normalized_incumbent_score": incumbent_score,
        "target_strictly_below": gate,
        "enumeration": enumeration,
        "selected_mutation_count": len(mutations),
        "attempted_trial_slots": trial_count,
        "completed_trials": sum(final_topologies.values()),
        "realization_failures": len(failures),
        "gate_clearer_count": gate_clearers,
        "returned_to_incumbent_wl_count": returned_to_incumbent,
        "unique_final_wl_count": len(final_topologies),
        "final_wl_frequencies": dict(sorted(final_topologies.items())),
        "best": {
            "trial": best_trial,
            "operator": best_operator,
            "score": best_score,
            "improvement_over_live": live_score - best_score,
            "gate_gap": best_score - gate,
            "gate_clearing": best_score < gate,
            "candidate": "best_candidate.json",
            "candidate_sha256": best_sha,
            "topology": topology(best_points),
        },
        "bounds": {
            "amplitudes": args.amplitudes,
            "rounds": args.rounds,
            "maxiter": args.maxiter,
            "mutation_cap": args.mutation_cap,
        },
        "claim_scope": (
            "This closes only the enumerated exact graph classes, retained local glide/extension "
            "paths, two geometric flip amplitudes, and the stated deterministic relaxation. It "
            "is not a proof over all N=282 triangulations or Coulomb basins."
        ),
    }
    summary_sha = write_once(run / "summary.json", summary)
    receipt = {
        "run": f"runs/{stamp}",
        "summary_sha256": summary_sha,
        "topology_classes_sha256": topology_sha,
        "events_sha256_before_completion": sha256_path(events),
        "verifier_sha256": VERIFIER_SHA256,
        "candidate_sha256": best_sha,
        "frozen_formula_score": best_score,
        "target_strictly_below": gate,
        "gate_clearing": best_score < gate,
        "domain": {
            "shape": list(best_points.shape),
            "finite": bool(np.isfinite(best_points).all()),
            "norm_min": float(np.linalg.norm(best_points, axis=1).min()),
            "norm_max": float(np.linalg.norm(best_points, axis=1).max()),
        },
    }
    receipt_sha = write_once(run / "receipt.json", receipt)
    append_event(
        events,
        {
            "event": "complete",
            "summary": "summary.json",
            "summary_sha256": summary_sha,
            "receipt": "receipt.json",
            "receipt_sha256": receipt_sha,
            "status": summary["status"],
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
