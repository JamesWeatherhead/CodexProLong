#!/usr/bin/env python3
"""Forced multi-contact topology search for min-distance-ratio-2d."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

from min_distance_active_refine import active_sets, rigidity_and_multipliers


BASE = "https://einsteinarena.com"
SLUG = "min-distance-ratio-2d"
PROBLEM_ID = 5
COUNT = 16


def get(path: str, **params: object) -> object:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.load(response)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append(path: Path, event: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def anchor_points(points: np.ndarray, anchor: tuple[int, int]) -> np.ndarray:
    a, b = anchor
    centered = points - points[a]
    delta = centered[b]
    length = np.linalg.norm(delta)
    cosine, sine = delta[0] / length, delta[1] / length
    rotation = np.array([[cosine, sine], [-sine, cosine]])
    return centered @ rotation.T / length


class AnchoredProblem:
    def __init__(self, anchor: tuple[int, int]):
        self.anchor = anchor
        self.free = [point for point in range(COUNT) if point not in anchor]
        self.offset = {point: 2 * index for index, point in enumerate(self.free)}
        self.pairs = [
            (i, j)
            for i in range(COUNT)
            for j in range(i + 1, COUNT)
            if (i, j) != anchor
        ]
        self.score_id = 2 * len(self.free)

    def pack(self, points: np.ndarray) -> np.ndarray:
        pairwise = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
        score = np.max(pairwise[np.triu_indices(COUNT, 1)]) ** 2
        return np.concatenate((points[self.free].ravel(), [score]))

    def unpack(self, variables: np.ndarray) -> tuple[np.ndarray, float]:
        points = np.empty((COUNT, 2))
        a, b = self.anchor
        points[a], points[b] = (0.0, 0.0), (1.0, 0.0)
        points[self.free] = variables[: self.score_id].reshape(len(self.free), 2)
        return points, float(variables[self.score_id])

    def base_constraints(self, variables: np.ndarray) -> np.ndarray:
        points, score = self.unpack(variables)
        squared = np.asarray([np.sum((points[i] - points[j]) ** 2) for i, j in self.pairs])
        return np.concatenate((squared - 1.0, score - squared))

    def base_jacobian(self, variables: np.ndarray) -> np.ndarray:
        points, _ = self.unpack(variables)
        pair_count = len(self.pairs)
        jacobian = np.zeros((2 * pair_count, self.score_id + 1))
        for row, (i, j) in enumerate(self.pairs):
            gradient = 2.0 * (points[i] - points[j])
            if i in self.offset:
                offset = self.offset[i]
                jacobian[row, offset : offset + 2] = gradient
                jacobian[pair_count + row, offset : offset + 2] = -gradient
            if j in self.offset:
                offset = self.offset[j]
                jacobian[row, offset : offset + 2] = -gradient
                jacobian[pair_count + row, offset : offset + 2] = gradient
            jacobian[pair_count + row, self.score_id] = 1.0
        return jacobian

    def selected_distances(self, variables: np.ndarray, edges: tuple[tuple[int, int], ...]) -> np.ndarray:
        points, _ = self.unpack(variables)
        return np.asarray([np.sum((points[i] - points[j]) ** 2) for i, j in edges])

    def selected_jacobian(self, variables: np.ndarray, edges: tuple[tuple[int, int], ...]) -> np.ndarray:
        points, _ = self.unpack(variables)
        jacobian = np.zeros((len(edges), self.score_id + 1))
        for row, (i, j) in enumerate(edges):
            gradient = 2.0 * (points[i] - points[j])
            if i in self.offset:
                offset = self.offset[i]
                jacobian[row, offset : offset + 2] = gradient
            if j in self.offset:
                offset = self.offset[j]
                jacobian[row, offset : offset + 2] = -gradient
        return jacobian


def exact_metrics(points: np.ndarray) -> dict[str, object]:
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    pairwise = distances[np.triu_indices(COUNT, 1)]
    minimum, maximum = float(pairwise.min()), float(pairwise.max())
    if not np.isfinite(points).all() or minimum <= 1e-12:
        return {
            "score": 1e300,
            "min_distance": minimum,
            "max_distance": maximum,
            "finite_distinct": False,
            "minimum_edges": (),
            "maximum_edges": (),
        }
    normalized = distances / minimum
    minimum_edges = tuple(
        (i, j)
        for i in range(COUNT)
        for j in range(i + 1, COUNT)
        if normalized[i, j] <= 1.0 + 1e-6
    )
    maximum_edges = tuple(
        (i, j)
        for i in range(COUNT)
        for j in range(i + 1, COUNT)
        if normalized[i, j] >= maximum / minimum - 1e-6
    )
    return {
        "score": (maximum / minimum) ** 2,
        "min_distance": minimum,
        "max_distance": maximum,
        "finite_distinct": bool(np.isfinite(points).all() and minimum > 1e-12),
        "minimum_edges": minimum_edges,
        "maximum_edges": maximum_edges,
    }


def verifier_score(evaluate: object, points: np.ndarray) -> float:
    try:
        return float(evaluate({"vectors": points.tolist()}))  # type: ignore[operator]
    except (AssertionError, KeyError, TypeError, ValueError):
        return 1e300


def parse_floats(value: str) -> list[float]:
    return [float(item) for item in value.split(",") if item.strip()]


def parse_modes(value: str) -> list[str]:
    modes = [item.strip() for item in value.split(",") if item.strip()]
    if any(item not in {"release", "promote"} for item in modes):
        raise argparse.ArgumentTypeError("modes must be release and/or promote")
    return modes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("seed_payload", type=Path)
    parser.add_argument("--weak-edge-count", type=int, default=8)
    parser.add_argument("--release-count", type=int, default=4)
    parser.add_argument("--trial-limit", type=int, default=70)
    parser.add_argument("--gaps", type=parse_floats, default=parse_floats("0.005,0.02"))
    parser.add_argument("--modes", type=parse_modes, default=parse_modes("release,promote"))
    parser.add_argument("--maxiter", type=int, default=600)
    parser.add_argument("--ftol", type=float, default=1e-12)
    parser.add_argument("--topology-gap", type=float, default=1e-4)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    args = parser.parse_args()

    with args.seed_payload.open(encoding="utf-8") as handle:
        raw = np.asarray(json.load(handle)["vectors"], dtype=np.float64)
    minimum_edges, maximum_edges, _ = active_sets(raw, 1e-6)
    diagnostics = rigidity_and_multipliers(raw, minimum_edges, maximum_edges)
    multipliers = {
        tuple(item["edge"]): float(item["multiplier"])
        for item in diagnostics["minimum_edge_multipliers"]
    }
    anchor = max(minimum_edges, key=multipliers.get)
    seed = anchor_points(raw, anchor)
    problem_model = AnchoredProblem(anchor)
    initial = problem_model.pack(seed)
    weak_edges = sorted((edge for edge in minimum_edges if edge != anchor), key=multipliers.get)[
        : args.weak_edge_count
    ]
    combinations = sorted(
        itertools.combinations(weak_edges, args.release_count),
        key=lambda edges: sum(multipliers[edge] for edge in edges),
    )[: args.trial_limit]
    inactive = sorted(
        (
            (np.linalg.norm(seed[i] - seed[j]), (i, j))
            for i in range(COUNT)
            for j in range(i + 1, COUNT)
            if (i, j) not in minimum_edges
        ),
        key=lambda item: item[0],
    )
    promote_edge = inactive[0][1]

    problem = get(f"/api/problems/{SLUG}")
    solutions = get("/api/solutions/best", problem_id=PROBLEM_ID, limit=100)
    leaderboard = get("/api/leaderboard", problem_id=PROBLEM_ID, limit=100)
    assert isinstance(problem, dict) and isinstance(solutions, list) and isinstance(leaderboard, list)
    live_best = float(solutions[0]["score"])
    target = live_best - float(problem["minImprovement"])
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
    namespace: dict[str, object] = {}
    exec(problem["verifier"], namespace)
    evaluate = namespace["evaluate"]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_json(run_dir / "problem.json", problem)
    atomic_json(run_dir / "leaderboard.json", leaderboard)
    atomic_json(run_dir / "best_solutions.json", solutions)
    atomic_json(run_dir / "seed.json", {"vectors": seed.tolist()})
    atomic_json(
        run_dir / "search_space.json",
        {
            "anchor": anchor,
            "weak_edges": weak_edges,
            "weak_edge_multipliers": {str(edge): multipliers[edge] for edge in weak_edges},
            "promote_edge": promote_edge,
            "promote_edge_seed_distance": inactive[0][0],
            "combinations": combinations,
            "gaps": args.gaps,
            "modes": args.modes,
        },
    )

    best = raw.copy()
    best_score = verifier_score(evaluate, best)
    atomic_json(run_dir / "best.json", {"vectors": best.tolist()})
    seen_topologies = {(tuple(minimum_edges), tuple(maximum_edges))}
    accepted = 0
    trial_records: list[dict[str, object]] = []
    bounds = [(-6.0, 6.0)] * problem_model.score_id + [(1.0, 30.0)]
    objective_gradient = np.zeros(problem_model.score_id + 1)
    objective_gradient[-1] = 1.0
    base_constraint = {
        "type": "ineq",
        "fun": problem_model.base_constraints,
        "jac": problem_model.base_jacobian,
    }

    trial_id = 0
    for edges in combinations:
        edge_tuple = tuple(edges)
        for gap in args.gaps:
            release_bound = (1.0 + gap) ** 2
            for mode in args.modes:
                forced_constraints: list[dict[str, object]] = [base_constraint]
                forced_constraints.append(
                    {
                        "type": "ineq",
                        "fun": lambda values, chosen=edge_tuple, bound=release_bound: problem_model.selected_distances(
                            values, chosen
                        )
                        - bound,
                        "jac": lambda values, chosen=edge_tuple: problem_model.selected_jacobian(values, chosen),
                    }
                )
                if mode == "promote":
                    forced_constraints.append(
                        {
                            "type": "eq",
                            "fun": lambda values, chosen=(promote_edge,): problem_model.selected_distances(values, chosen)
                            - 1.0,
                            "jac": lambda values, chosen=(promote_edge,): problem_model.selected_jacobian(values, chosen),
                        }
                    )
                forced = minimize(
                    lambda values: values[-1],
                    initial,
                    jac=lambda _values: objective_gradient,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=forced_constraints,
                    options={"maxiter": args.maxiter, "ftol": args.ftol, "disp": False},
                )
                topology_bound = (1.0 + args.topology_gap) ** 2
                topology_constraints: list[dict[str, object]] = [base_constraint]
                topology_constraints.append(
                    {
                        "type": "ineq",
                        "fun": lambda values, chosen=edge_tuple, bound=topology_bound: problem_model.selected_distances(
                            values, chosen
                        )
                        - bound,
                        "jac": lambda values, chosen=edge_tuple: problem_model.selected_jacobian(values, chosen),
                    }
                )
                if mode == "promote":
                    topology_constraints.append(
                        {
                            "type": "eq",
                            "fun": lambda values, chosen=(promote_edge,): problem_model.selected_distances(values, chosen)
                            - 1.0,
                            "jac": lambda values, chosen=(promote_edge,): problem_model.selected_jacobian(values, chosen),
                        }
                    )
                topology_polished = minimize(
                    lambda values: values[-1],
                    forced.x,
                    jac=lambda _values: objective_gradient,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=topology_constraints,
                    options={"maxiter": args.maxiter, "ftol": args.ftol, "disp": False},
                )
                polished = minimize(
                    lambda values: values[-1],
                    topology_polished.x,
                    jac=lambda _values: objective_gradient,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=[base_constraint],
                    options={"maxiter": args.maxiter, "ftol": args.ftol, "disp": False},
                )
                stage_candidates = []
                stage_reports = []
                for stage, result in (
                    ("forced", forced),
                    ("topology_polished", topology_polished),
                    ("generic_polished", polished),
                ):
                    points, _ = problem_model.unpack(result.x)
                    report = exact_metrics(points)
                    official_score = verifier_score(evaluate, points)
                    report["official_score"] = official_score
                    report["stage"] = stage
                    report["success"] = bool(result.success)
                    report["status"] = int(result.status)
                    report["iterations"] = int(result.nit)
                    report["message"] = str(result.message)
                    stage_candidates.append((official_score, points, report))
                    stage_topology = (tuple(report["minimum_edges"]), tuple(report["maximum_edges"]))
                    seen_topologies.add(stage_topology)
                    stage_reports.append(
                        {
                            "stage": stage,
                            "official_score": official_score,
                            "success": bool(result.success),
                            "iterations": int(result.nit),
                            "minimum_edges": report["minimum_edges"],
                            "maximum_edges": report["maximum_edges"],
                        }
                    )
                official_score, points, report = min(stage_candidates, key=lambda item: item[0])
                topology = (tuple(report["minimum_edges"]), tuple(report["maximum_edges"]))
                seen_topologies.add(topology)
                record = {
                    "event": "trial",
                    "trial": trial_id,
                    "release_edges": edge_tuple,
                    "release_multiplier_sum": sum(multipliers[edge] for edge in edge_tuple),
                    "gap": gap,
                    "mode": mode,
                    "promote_edge": promote_edge if mode == "promote" else None,
                    "stage_reports": stage_reports,
                    "live_best": live_best,
                    "improvement_over_live": live_best - official_score,
                    "distinct_topologies": len(seen_topologies),
                    **report,
                }
                append(events, record)
                trial_records.append(record)
                if report["finite_distinct"] and official_score < best_score:
                    best, best_score = points.copy(), official_score
                    accepted += 1
                    atomic_json(run_dir / "best.json", {"vectors": best.tolist()})
                    atomic_json(run_dir / f"checkpoint_{accepted:03d}.json", {"vectors": best.tolist()})
                trial_id += 1

    top_trials = sorted(trial_records, key=lambda item: float(item["official_score"]))[:20]
    summary = {
        "slug": SLUG,
        "seed_payload": str(args.seed_payload.resolve()),
        "verifier_sha256": verifier_hash,
        "live_best": live_best,
        "target": target,
        "official_verifier_score": best_score,
        "improvement_over_live": live_best - best_score,
        "gate_clearing": best_score < target,
        "trials": trial_id,
        "distinct_labeled_topologies": len(seen_topologies),
        "accepted_checkpoints": accepted,
        "weak_edge_count": len(weak_edges),
        "release_count": args.release_count,
        "top_trials": top_trials,
        "payload": str((run_dir / "best.json").resolve()),
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
