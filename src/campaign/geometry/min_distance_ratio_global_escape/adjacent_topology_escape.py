#!/usr/bin/env python3
"""Adjacent-cardinality topology escape for the n=16 min/max-distance ratio.

This lane deliberately avoids polishing the incumbent active root.  It recovers
the distinct public n=14,15,17,18 contact graphs from Friedman's diagrams,
changes cardinality by point birth/death, preserves inherited unit contacts in
an intermediate solve, and only then performs an unconstrained contact-graph
release.  Every retained point set is replayed through the frozen Arena
verifier; the event journal is append-only.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import networkx as nx
import numpy as np
from scipy.optimize import differential_evolution, least_squares, minimize


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
ASSETS_PATH = HERE / "assets.json"
CORPUS_PATH = CAMPAIGN / "research_corpus/snapshots/20260815T003306Z/corpus.sqlite3"
CORPUS_SHA256 = "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"
VERIFIER_PATH = CAMPAIGN / "state/problems/min-distance-ratio-2d/2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad.py"
VERIFIER_SHA256 = "2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad"
LEADER = 12.889229907717521
GATE = 1e-7
STRICT_TARGET = LEADER - GATE
COUNT = 16


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json(value)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def append_event(path: Path, value: dict[str, Any]) -> None:
    raw = json.dumps(value, sort_keys=True, allow_nan=False) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def score(points: np.ndarray) -> float:
    differences = points[:, None, :] - points[None, :, :]
    distances = np.sqrt(np.sum(differences**2, axis=-1))
    pairwise = distances[np.triu_indices(len(points), 1)]
    if not np.isfinite(pairwise).all() or float(pairwise.min()) <= 1e-15:
        return 1e300
    return float((pairwise.max() / pairwise.min()) ** 2)


def distance_metrics(points: np.ndarray) -> dict[str, Any]:
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    pairwise = distances[np.triu_indices(len(points), 1)]
    minimum, maximum = float(pairwise.min()), float(pairwise.max())
    minimum_edges = [
        [i, j]
        for i in range(len(points))
        for j in range(i + 1, len(points))
        if distances[i, j] <= minimum * (1.0 + 1e-6)
    ]
    maximum_edges = [
        [i, j]
        for i in range(len(points))
        for j in range(i + 1, len(points))
        if distances[i, j] >= maximum * (1.0 - 1e-6)
    ]
    return {
        "score": float((maximum / minimum) ** 2),
        "minimum": minimum,
        "maximum": maximum,
        "minimum_edges": minimum_edges,
        "maximum_edges": maximum_edges,
        "finite_distinct": bool(np.isfinite(points).all() and minimum > 1e-12),
    }


def graph_signature(points: np.ndarray, ranked: bool = True) -> str:
    rows = sorted(
        (float(np.linalg.norm(points[i] - points[j])), i, j)
        for i in range(len(points))
        for j in range(i + 1, len(points))
    )
    if ranked:
        minimum_rows, maximum_rows = rows[:22], rows[-8:]
    else:
        minimum, maximum = rows[0][0], rows[-1][0]
        minimum_rows = [row for row in rows if row[0] <= minimum * (1 + 1e-6)]
        maximum_rows = [row for row in rows if row[0] >= maximum * (1 - 1e-6)]
    graph = nx.Graph()
    for index in range(len(points)):
        graph.add_node(index, label="point")
    for _, first, second in minimum_rows:
        graph.add_edge(first, second, kind="minimum")
    for _, first, second in maximum_rows:
        graph.add_edge(first, second, kind="maximum")
    digest = nx.weisfeiler_lehman_graph_hash(
        graph, node_attr="label", edge_attr="kind", iterations=8
    )
    degrees = sorted(dict(graph.degree()).values())
    value = [digest, degrees, len(minimum_rows), len(maximum_rows)]
    return sha256_bytes(json.dumps(value, separators=(",", ":")).encode())


class RatioModel:
    """Scale-fixed smooth epigraph model for a point set of arbitrary size."""

    def __init__(self, count: int, anchor: tuple[int, int]):
        self.count = count
        self.anchor = tuple(sorted(anchor))
        self.free = [index for index in range(count) if index not in self.anchor]
        self.offset = {point: 2 * index for index, point in enumerate(self.free)}
        self.score_id = 2 * len(self.free)
        self.pairs = [
            (i, j)
            for i in range(count)
            for j in range(i + 1, count)
            if (i, j) != self.anchor
        ]

    def normalize(self, points: np.ndarray) -> np.ndarray:
        first, second = self.anchor
        translated = points - points[first]
        delta = translated[second]
        length = float(np.linalg.norm(delta))
        cosine, sine = delta / length
        rotation = np.array([[cosine, -sine], [sine, cosine]])
        return translated @ rotation / length

    def pack(self, points: np.ndarray) -> np.ndarray:
        normalized = self.normalize(points)
        return np.concatenate((normalized[self.free].ravel(), [score(normalized)]))

    def unpack(self, variables: np.ndarray) -> tuple[np.ndarray, float]:
        points = np.empty((self.count, 2), dtype=float)
        first, second = self.anchor
        points[first], points[second] = (0.0, 0.0), (1.0, 0.0)
        points[self.free] = variables[: self.score_id].reshape(-1, 2)
        return points, float(variables[self.score_id])

    def base_constraints(self, variables: np.ndarray) -> np.ndarray:
        points, epigraph = self.unpack(variables)
        squared = np.asarray(
            [np.sum((points[i] - points[j]) ** 2) for i, j in self.pairs]
        )
        return np.concatenate((squared - 1.0, epigraph - squared))

    def base_jacobian(self, variables: np.ndarray) -> np.ndarray:
        points, _ = self.unpack(variables)
        pair_count = len(self.pairs)
        jacobian = np.zeros((2 * pair_count, self.score_id + 1))
        for row, (first, second) in enumerate(self.pairs):
            gradient = 2.0 * (points[first] - points[second])
            if first in self.offset:
                offset = self.offset[first]
                jacobian[row, offset : offset + 2] = gradient
                jacobian[pair_count + row, offset : offset + 2] = -gradient
            if second in self.offset:
                offset = self.offset[second]
                jacobian[row, offset : offset + 2] = -gradient
                jacobian[pair_count + row, offset : offset + 2] = gradient
            jacobian[pair_count + row, self.score_id] = 1.0
        return jacobian

    def edge_equalities(
        self, variables: np.ndarray, edges: tuple[tuple[int, int], ...]
    ) -> np.ndarray:
        points, _ = self.unpack(variables)
        return np.asarray(
            [np.sum((points[i] - points[j]) ** 2) - 1.0 for i, j in edges]
        )

    def edge_jacobian(
        self, variables: np.ndarray, edges: tuple[tuple[int, int], ...]
    ) -> np.ndarray:
        points, _ = self.unpack(variables)
        jacobian = np.zeros((len(edges), self.score_id + 1))
        for row, (first, second) in enumerate(edges):
            gradient = 2.0 * (points[first] - points[second])
            if first in self.offset:
                offset = self.offset[first]
                jacobian[row, offset : offset + 2] = gradient
            if second in self.offset:
                offset = self.offset[second]
                jacobian[row, offset : offset + 2] = -gradient
        return jacobian


def closest_pair(points: np.ndarray) -> tuple[int, int]:
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    distances[np.diag_indices(len(points))] = np.inf
    first, second = np.unravel_index(np.argmin(distances), distances.shape)
    return tuple(sorted((int(first), int(second))))


def reconstruct_equalities(record: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    pixels = np.asarray(record["pixel_centers"], dtype=float)
    minimum_edges = [tuple(edge) for edge in record["minimum_edges"]]
    diameter_edges = [tuple(edge) for edge in record["diameter_edges"]]
    anchor = minimum_edges[0]
    model = RatioModel(len(pixels), anchor)
    normalized = model.normalize(pixels)
    initial_t = float(
        np.mean([np.sum((normalized[i] - normalized[j]) ** 2) for i, j in diameter_edges])
    )
    initial = np.concatenate((normalized[model.free].ravel(), [initial_t]))

    def residual(variables: np.ndarray) -> np.ndarray:
        points, diameter = model.unpack(variables)
        return np.concatenate(
            (
                [np.sum((points[i] - points[j]) ** 2) - 1.0 for i, j in minimum_edges],
                [np.sum((points[i] - points[j]) ** 2) - diameter for i, j in diameter_edges],
            )
        )

    result = least_squares(
        residual,
        initial,
        method="trf",
        ftol=1e-14,
        xtol=1e-14,
        gtol=1e-14,
        max_nfev=100000,
    )
    points, diameter = model.unpack(result.x)
    report = {
        "method": "contact_equalities",
        "cost": float(result.cost),
        "max_residual": float(np.max(np.abs(residual(result.x)))),
        "jacobian_rank": int(np.linalg.matrix_rank(result.jac, tol=1e-9)),
        "variable_count": int(len(initial)),
        "diameter_squared": diameter,
        **distance_metrics(points),
    }
    return points, report


def slsqp_polish(
    points: np.ndarray,
    inherited_edges: Iterable[tuple[int, int]] = (),
    maxiter: int = 2000,
) -> tuple[np.ndarray, dict[str, Any]]:
    anchor = closest_pair(points)
    model = RatioModel(len(points), anchor)
    variables = model.pack(points)
    gradient = np.zeros(model.score_id + 1)
    gradient[-1] = 1.0
    bounds = [(-8.0, 8.0)] * model.score_id + [(1.0, 60.0)]
    base = {"type": "ineq", "fun": model.base_constraints, "jac": model.base_jacobian}
    locked = tuple(
        sorted(tuple(sorted(edge)) for edge in inherited_edges if tuple(sorted(edge)) != anchor)
    )
    stages: list[dict[str, Any]] = []
    if locked:
        equality = {
            "type": "eq",
            "fun": lambda values: model.edge_equalities(values, locked),
            "jac": lambda values: model.edge_jacobian(values, locked),
        }
        result = minimize(
            lambda values: values[-1],
            variables,
            jac=lambda _values: gradient,
            method="SLSQP",
            bounds=bounds,
            constraints=[base, equality],
            options={"maxiter": maxiter, "ftol": 1e-13, "disp": False},
        )
        variables = result.x
        locked_points, _ = model.unpack(variables)
        stages.append(
            {
                "stage": "inherited_contact_lock",
                "success": bool(result.success),
                "status": int(result.status),
                "iterations": int(result.nit),
                "message": str(result.message),
                "constraint_min": float(np.min(model.base_constraints(variables))),
                "equality_max_abs": float(
                    np.max(np.abs(model.edge_equalities(variables, locked)))
                ),
                "score": score(locked_points),
                "ranked_signature": graph_signature(locked_points),
            }
        )
    for release in range(3):
        result = minimize(
            lambda values: values[-1],
            variables,
            jac=lambda _values: gradient,
            method="SLSQP",
            bounds=bounds,
            constraints=[base],
            options={"maxiter": maxiter, "ftol": 1e-13, "disp": False},
        )
        variables = result.x
        released_points, _ = model.unpack(variables)
        stages.append(
            {
                "stage": f"free_release_{release + 1}",
                "success": bool(result.success),
                "status": int(result.status),
                "iterations": int(result.nit),
                "message": str(result.message),
                "constraint_min": float(np.min(model.base_constraints(variables))),
                "score": score(released_points),
                "ranked_signature": graph_signature(released_points),
            }
        )
    polished, _ = model.unpack(variables)
    return polished, {
        "anchor": list(anchor),
        "locked_edge_count": len(locked),
        "stages": stages,
        **distance_metrics(polished),
        "ranked_signature": graph_signature(polished),
        "threshold_signature": graph_signature(polished, ranked=False),
    }


def remap_surviving_edges(
    edges: Iterable[tuple[int, int]], deleted: tuple[int, ...], count: int
) -> list[tuple[int, int]]:
    survivors = [index for index in range(count) if index not in deleted]
    remap = {old: new for new, old in enumerate(survivors)}
    return [
        tuple(sorted((remap[first], remap[second])))
        for first, second in edges
        if first in remap and second in remap
    ]


def recover_assets(assets: dict[str, Any]) -> tuple[dict[int, np.ndarray], dict[str, Any]]:
    recovered: dict[int, np.ndarray] = {}
    reports: dict[str, Any] = {}
    for count in (14, 15, 17):
        points, report = reconstruct_equalities(assets["diagrams"][str(count)])
        if report["max_residual"] > 1e-10 or not report["finite_distinct"]:
            raise RuntimeError(f"failed exact diagram reconstruction for n={count}: {report}")
        recovered[count] = points
        reports[str(count)] = report

    # The n=18 diagram has two flex degrees after its colored equalities.  The
    # full epigraph inequalities select the displayed local optimum cleanly.
    record18 = assets["diagrams"]["18"]
    pixels18 = np.asarray(record18["pixel_centers"], dtype=float)
    points18, report18 = slsqp_polish(
        pixels18, [tuple(edge) for edge in record18["minimum_edges"]]
    )
    if abs(score(points18) - 14.7252760916858) > 1e-7:
        raise RuntimeError(f"n=18 reconstruction left published basin: {score(points18)}")
    recovered[18] = points18
    reports["18"] = {"method": "contact_lock_then_full_epigraph", **report18}
    return recovered, reports


def load_verifier() -> Any:
    if sha256_file(VERIFIER_PATH) != VERIFIER_SHA256:
        raise RuntimeError("frozen verifier hash changed")
    namespace: dict[str, Any] = {}
    exec(compile(VERIFIER_PATH.read_text(), str(VERIFIER_PATH), "exec"), namespace)
    return namespace["evaluate"]


def audit_corpus(evaluate: Any) -> tuple[list[np.ndarray], dict[str, Any]]:
    if sha256_file(CORPUS_PATH) != CORPUS_SHA256:
        raise RuntimeError("retained corpus hash changed")
    connection = sqlite3.connect(CORPUS_PATH)
    solution_rows = connection.execute(
        "SELECT id, agent_name, score, record_sha256, record_json "
        "FROM solutions WHERE problem_id=5 ORDER BY score, id"
    ).fetchall()
    thread_rows = connection.execute(
        "SELECT id, record_sha256, title, body FROM threads WHERE problem_id=5 ORDER BY id"
    ).fetchall()
    reply_rows = connection.execute(
        "SELECT r.id, r.record_sha256, r.body FROM replies r "
        "JOIN threads t ON t.id=r.thread_id WHERE t.problem_id=5 ORDER BY r.id"
    ).fetchall()
    connection.close()
    solutions: list[np.ndarray] = []
    records = []
    maximum_score_delta = 0.0
    for solution_id, agent, stored_score, record_hash, raw_record in solution_rows:
        record = json.loads(raw_record)
        points = np.asarray(record["data"]["vectors"], dtype=float)
        replayed = float(evaluate({"vectors": points.tolist()}))
        maximum_score_delta = max(maximum_score_delta, abs(replayed - float(stored_score)))
        solutions.append(points)
        records.append(
            {
                "id": solution_id,
                "agent": agent,
                "stored_score": stored_score,
                "replayed_score": replayed,
                "record_sha256": record_hash,
                "ranked_signature": graph_signature(points),
                "threshold_signature": graph_signature(points, ranked=False),
            }
        )
    text = "\n".join([row[3] for row in thread_rows] + [row[2] for row in reply_rows]).lower()
    technique_terms = [
        "anneal", "cma", "differential evolution", "softmax", "active set",
        "contact graph", "nullspace", "two-ring", "lattice", "slsqp",
    ]
    return solutions, {
        "database_sha256": CORPUS_SHA256,
        "solution_count": len(solution_rows),
        "thread_count": len(thread_rows),
        "reply_count": len(reply_rows),
        "solution_record_set_sha256": sha256_bytes(
            "\n".join(row[3] for row in solution_rows).encode()
        ),
        "discussion_record_set_sha256": sha256_bytes(
            "\n".join([row[1] for row in thread_rows] + [row[1] for row in reply_rows]).encode()
        ),
        "maximum_stored_vs_replayed_score_delta": maximum_score_delta,
        "technique_term_counts": {term: text.count(term) for term in technique_terms},
        "solutions": records,
    }


@dataclass
class Seed:
    method: str
    source_count: int
    operation: dict[str, Any]
    points: np.ndarray
    inherited_edges: list[tuple[int, int]]


def generate_seeds(
    recovered: dict[int, np.ndarray],
    assets: dict[str, Any],
    birth15_starts: int,
    birth14_starts: int,
) -> list[Seed]:
    seeds: list[Seed] = []
    for deleted in itertools.combinations(range(17), 1):
        seeds.append(
            Seed(
                "n17_delete1",
                17,
                {"deleted": list(deleted)},
                np.delete(recovered[17], deleted, axis=0),
                remap_surviving_edges(
                    [tuple(edge) for edge in assets["diagrams"]["17"]["minimum_edges"]],
                    deleted,
                    17,
                ),
            )
        )
    for deleted in itertools.combinations(range(18), 2):
        seeds.append(
            Seed(
                "n18_delete2",
                18,
                {"deleted": list(deleted)},
                np.delete(recovered[18], deleted, axis=0),
                remap_surviving_edges(
                    [tuple(edge) for edge in assets["diagrams"]["18"]["minimum_edges"]],
                    deleted,
                    18,
                ),
            )
        )

    points15 = recovered[15]
    lower15, upper15 = points15.min(axis=0) - 0.7, points15.max(axis=0) + 0.7
    for random_seed in range(birth15_starts):
        result = differential_evolution(
            lambda point: score(np.vstack((points15, point))),
            list(zip(lower15, upper15)),
            seed=random_seed,
            popsize=20,
            maxiter=200,
            tol=1e-9,
            polish=True,
            workers=1,
            updating="immediate",
        )
        seeds.append(
            Seed(
                "n15_birth1",
                15,
                {
                    "random_seed": random_seed,
                    "fixed_parent_score": float(result.fun),
                    "birth_points": [result.x.tolist()],
                },
                np.vstack((points15, result.x)),
                [tuple(edge) for edge in assets["diagrams"]["15"]["minimum_edges"]],
            )
        )

    points14 = recovered[14]
    lower14, upper14 = points14.min(axis=0) - 0.7, points14.max(axis=0) + 0.7
    bounds14 = [*zip(lower14, upper14), *zip(lower14, upper14)]
    for random_seed in range(birth14_starts):
        result = differential_evolution(
            lambda values: score(np.vstack((points14, values.reshape(2, 2)))),
            bounds14,
            seed=random_seed,
            popsize=18,
            maxiter=250,
            tol=1e-9,
            polish=True,
            workers=1,
            updating="immediate",
        )
        births = result.x.reshape(2, 2)
        seeds.append(
            Seed(
                "n14_birth2",
                14,
                {
                    "random_seed": random_seed,
                    "fixed_parent_score": float(result.fun),
                    "birth_points": births.tolist(),
                },
                np.vstack((points14, births)),
                [tuple(edge) for edge in assets["diagrams"]["14"]["minimum_edges"]],
            )
        )
    return seeds


def n16_diagram_duplicate(
    assets: dict[str, Any], leader_points: np.ndarray
) -> dict[str, Any]:
    diagram = nx.Graph()
    diagram.add_nodes_from(range(COUNT))
    diagram.add_edges_from(tuple(edge) for edge in assets["diagrams"]["16"]["minimum_edges"])
    metrics = distance_metrics(leader_points)
    leader = nx.Graph()
    leader.add_nodes_from(range(COUNT))
    leader.add_edges_from(tuple(edge) for edge in metrics["minimum_edges"])
    matcher = nx.algorithms.isomorphism.GraphMatcher(diagram, leader)
    isomorphic = matcher.is_isomorphic()
    mapping = matcher.mapping if isomorphic else {}
    return {
        "diagram_minimum_edges": diagram.number_of_edges(),
        "leader_minimum_edges": leader.number_of_edges(),
        "minimum_graph_isomorphic": isomorphic,
        "one_diagram_to_leader_mapping": {str(key): value for key, value in mapping.items()},
        "conclusion": "published n=16 diagram is not a new minimum-contact topology" if isomorphic else "different topology",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id")
    parser.add_argument("--birth15-starts", type=int, default=32)
    parser.add_argument("--birth14-starts", type=int, default=12)
    parser.add_argument("--maxiter", type=int, default=2000)
    args = parser.parse_args()
    if args.birth15_starts < 0 or args.birth14_starts < 0:
        raise SystemExit("birth start counts must be nonnegative")

    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = HERE / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    assets = json.loads(ASSETS_PATH.read_text())
    evaluate = load_verifier()
    corpus_solutions, corpus_audit = audit_corpus(evaluate)
    atomic_json(run_dir / "corpus_audit.json", corpus_audit)

    recovered, recovery_reports = recover_assets(assets)
    duplicate_report = n16_diagram_duplicate(assets, corpus_solutions[0])
    atomic_json(
        run_dir / "reconstructed_assets.json",
        {
            "reports": recovery_reports,
            "n16_diagram_duplicate": duplicate_report,
            "constructions": {
                str(count): {"vectors": recovered[count].tolist()} for count in recovered
            },
        },
    )
    append_event(
        events_path,
        {"event": "assets_reconstructed", "reports": recovery_reports, "n16_duplicate": duplicate_report},
    )

    seeds = generate_seeds(
        recovered, assets, args.birth15_starts, args.birth14_starts
    )
    corpus_signatures = {
        graph_signature(points): index for index, points in enumerate(corpus_solutions)
    }
    best_points = corpus_solutions[0].copy()
    best_score = float(evaluate({"vectors": best_points.tolist()}))
    records: list[dict[str, Any]] = []
    endpoint_signatures: set[str] = set()
    method_counts: dict[str, int] = {}
    for index, seed in enumerate(seeds):
        polished, report = slsqp_polish(
            seed.points, seed.inherited_edges, maxiter=args.maxiter
        )
        official = float(evaluate({"vectors": polished.tolist()}))
        if abs(official - report["score"]) > 1e-12:
            raise RuntimeError("frozen verifier disagreed with local exact metric")
        ranked_signature = graph_signature(polished)
        endpoint_signatures.add(ranked_signature)
        method_counts[seed.method] = method_counts.get(seed.method, 0) + 1
        record = {
            "event": "candidate_replayed",
            "index": index,
            "method": seed.method,
            "source_count": seed.source_count,
            "operation": seed.operation,
            "inherited_edge_count": len(seed.inherited_edges),
            "seed_score": score(seed.points),
            "official_score": official,
            "strict_target": STRICT_TARGET,
            "gate_clearing": official < STRICT_TARGET,
            "ranked_signature": ranked_signature,
            "threshold_signature": graph_signature(polished, ranked=False),
            "matches_retained_signature": ranked_signature in corpus_signatures,
            "matched_retained_solution_index": corpus_signatures.get(ranked_signature),
            "optimization": report,
        }
        append_event(events_path, record)
        records.append(record)
        if official < best_score:
            best_points, best_score = polished.copy(), official
            atomic_json(run_dir / "best.json", {"vectors": best_points.tolist()})
            append_event(
                events_path,
                {
                    "event": "checkpoint",
                    "candidate_index": index,
                    "official_score": official,
                    "payload_sha256": sha256_bytes(
                        canonical_json({"vectors": best_points.tolist()})
                    ),
                },
            )

    best_payload = {"vectors": best_points.tolist()}
    atomic_json(run_dir / "best.json", best_payload)
    top = [
        {
            "index": item["index"],
            "method": item["method"],
            "operation": item["operation"],
            "seed_score": item["seed_score"],
            "official_score": item["official_score"],
            "ranked_signature": item["ranked_signature"],
            "threshold_signature": item["threshold_signature"],
            "matches_retained_signature": item["matches_retained_signature"],
            "matched_retained_solution_index": item["matched_retained_solution_index"],
        }
        for item in sorted(records, key=lambda candidate: candidate["official_score"])[:30]
    ]
    novel_records = [item for item in records if not item["matches_retained_signature"]]
    novel_signatures = sorted(endpoint_signatures - set(corpus_signatures))
    best_novel = min(novel_records, key=lambda item: item["official_score"])
    summary = {
        "run_id": run_id,
        "method": "published adjacent-cardinality contact-graph birth/death",
        "verifier_sha256": VERIFIER_SHA256,
        "corpus_database_sha256": CORPUS_SHA256,
        "assets_sha256": sha256_file(ASSETS_PATH),
        "leader": LEADER,
        "gate": GATE,
        "strict_target": STRICT_TARGET,
        "candidate_count": len(records),
        "method_counts": method_counts,
        "distinct_ranked_endpoint_signatures": len(endpoint_signatures),
        "endpoint_signatures_absent_from_retained_corpus_count": len(novel_signatures),
        "endpoint_signature_set_sha256": sha256_bytes("\n".join(sorted(endpoint_signatures)).encode()),
        "novel_endpoint_signature_set_sha256": sha256_bytes("\n".join(novel_signatures).encode()),
        "best_endpoint_absent_from_retained_corpus": {
            "index": best_novel["index"],
            "method": best_novel["method"],
            "operation": best_novel["operation"],
            "official_score": best_novel["official_score"],
            "ranked_signature": best_novel["ranked_signature"],
            "threshold_signature": best_novel["threshold_signature"],
        },
        "best_official_score": best_score,
        "improvement_over_leader": LEADER - best_score,
        "shortfall_to_strict_target": best_score - STRICT_TARGET,
        "gate_clearing": best_score < STRICT_TARGET,
        "best_payload": str((run_dir / "best.json").resolve()),
        "best_payload_sha256": sha256_bytes(canonical_json(best_payload)),
        "events_sha256": sha256_file(events_path),
        "n16_published_diagram_duplicate": duplicate_report,
        "asset_recovery_reports": recovery_reports,
        "corpus_audit": {
            key: value for key, value in corpus_audit.items() if key != "solutions"
        },
        "top_candidates": top,
        "claim_scope": (
            "Bounded deterministic adjacent-cardinality screen: all 17 n=17 deletions, "
            "all 153 n=18 two-point deletions, and configured multistart n=15/n=14 "
            "births. It is not a global proof for the continuous n=16 problem."
        ),
        "literature": assets["literature"],
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if summary["gate_clearing"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
