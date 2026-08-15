#!/usr/bin/env python3
"""Depth-four active-triple and boundary-release search for Heilbronn n=11."""

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

from heilbronn_active_refine import (
    BOUNDING_AREA,
    COUNT,
    PROBLEM_ID,
    SLUG,
    active_diagnostics,
    active_triples,
    boundary_contacts,
    signed_double_area,
    triangle_gradient,
)

BASE = "https://einsteinarena.com"


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


def parse_floats(value: str) -> list[float]:
    return [float(item) for item in value.split(",") if item.strip()]


def parse_strings(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class HeilbronnModel:
    def __init__(self, signs: dict[tuple[int, int, int], int]):
        self.triples = list(itertools.combinations(range(COUNT), 3))
        self.signs = signs
        self.score_id = 2 * COUNT
        self.size = self.score_id + 1
        self.sq3 = np.sqrt(3.0)

    def pack(self, points: np.ndarray) -> np.ndarray:
        areas = [abs(signed_double_area(points, triple)) / 2.0 for triple in self.triples]
        return np.concatenate((points.ravel(), [min(areas)]))

    def unpack(self, values: np.ndarray) -> tuple[np.ndarray, float]:
        return values[: self.score_id].reshape(COUNT, 2), float(values[-1])

    def areas(self, values: np.ndarray) -> np.ndarray:
        points, _ = self.unpack(values)
        return np.asarray(
            [
                self.signs[triple] * signed_double_area(points, triple) / 2.0
                for triple in self.triples
            ]
        )

    def area_jacobian(self, values: np.ndarray) -> np.ndarray:
        points, _ = self.unpack(values)
        jacobian = np.zeros((len(self.triples), self.size))
        for row, triple in enumerate(self.triples):
            jacobian[row, : self.score_id] = triangle_gradient(points, triple, self.signs[triple])
        return jacobian

    def domain_slacks(self, values: np.ndarray) -> np.ndarray:
        points, _ = self.unpack(values)
        result = np.empty(3 * COUNT)
        for point, (x, y) in enumerate(points):
            result[3 * point : 3 * point + 3] = (
                y,
                self.sq3 * x - y,
                self.sq3 - self.sq3 * x - y,
            )
        return result

    def domain_jacobian(self, _values: np.ndarray) -> np.ndarray:
        jacobian = np.zeros((3 * COUNT, self.size))
        for point in range(COUNT):
            x_id, y_id = 2 * point, 2 * point + 1
            jacobian[3 * point, y_id] = 1.0
            jacobian[3 * point + 1, x_id], jacobian[3 * point + 1, y_id] = self.sq3, -1.0
            jacobian[3 * point + 2, x_id], jacobian[3 * point + 2, y_id] = -self.sq3, -1.0
        return jacobian

    def base_constraints(self, values: np.ndarray) -> np.ndarray:
        return np.concatenate((self.areas(values) - values[-1], self.domain_slacks(values)))

    def base_jacobian(self, values: np.ndarray) -> np.ndarray:
        area = self.area_jacobian(values)
        area[:, -1] = -1.0
        return np.vstack((area, self.domain_jacobian(values)))

    def selected_area_slacks(
        self,
        values: np.ndarray,
        triples: tuple[tuple[int, int, int], ...],
    ) -> np.ndarray:
        points, score = self.unpack(values)
        return np.asarray(
            [self.signs[triple] * signed_double_area(points, triple) / 2.0 - score for triple in triples]
        )

    def selected_area_jacobian(
        self,
        values: np.ndarray,
        triples: tuple[tuple[int, int, int], ...],
    ) -> np.ndarray:
        points, _ = self.unpack(values)
        jacobian = np.zeros((len(triples), self.size))
        for row, triple in enumerate(triples):
            jacobian[row, : self.score_id] = triangle_gradient(points, triple, self.signs[triple])
            jacobian[row, -1] = -1.0
        return jacobian

    def selected_boundary_slacks(
        self,
        values: np.ndarray,
        contacts: tuple[tuple[int, str], ...],
    ) -> np.ndarray:
        points, _ = self.unpack(values)
        slacks = []
        for point, side in contacts:
            x, y = points[point]
            if side == "bottom":
                slacks.append(y)
            elif side == "left":
                slacks.append(self.sq3 * x - y)
            else:
                slacks.append(self.sq3 - self.sq3 * x - y)
        return np.asarray(slacks)

    def selected_boundary_jacobian(
        self,
        values: np.ndarray,
        contacts: tuple[tuple[int, str], ...],
    ) -> np.ndarray:
        full = self.domain_jacobian(values)
        side_id = {"bottom": 0, "left": 1, "right": 2}
        return np.asarray([full[3 * point + side_id[side]] for point, side in contacts])


def metrics(points: np.ndarray) -> dict[str, object]:
    areas = sorted(
        (abs(signed_double_area(points, triple)) / 2.0, triple)
        for triple in itertools.combinations(range(COUNT), 3)
    )
    minimum = areas[0][0]
    triples = tuple(sorted(triple for area, triple in areas if area - minimum <= 1e-7))
    contacts = tuple(boundary_contacts(points, 1e-7))
    sq3 = np.sqrt(3.0)
    domain = []
    for x, y in points:
        domain.extend((y, sq3 * x - y, sq3 - sq3 * x - y))
    distances = np.linalg.norm(points[:, None] - points[None, :], axis=2) + np.eye(COUNT)
    return {
        "score": minimum / BOUNDING_AREA,
        "raw_area": minimum,
        "active_triples": triples,
        "boundary_contacts": contacts,
        "minimum_domain_slack": float(min(domain)),
        "intended_domain": bool(np.isfinite(points).all() and min(domain) >= -1e-10 and distances.min() > 1e-10),
    }


def verifier_score(evaluate: object, points: np.ndarray) -> float:
    try:
        return float(evaluate({"points": points.tolist()}))  # type: ignore[operator]
    except (AssertionError, KeyError, TypeError, ValueError):
        return -1e300


def solve(
    model: HeilbronnModel,
    initial: np.ndarray,
    constraints: list[dict[str, object]],
    maxiter: int,
    ftol: float,
) -> object:
    gradient = np.zeros(model.size)
    gradient[-1] = -1.0
    bounds = [(0.0, 1.0), (0.0, model.sq3 / 2.0)] * COUNT + [(0.0, 0.1)]
    return minimize(
        lambda values: -values[-1],
        initial,
        jac=lambda _values: gradient,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": maxiter, "ftol": ftol, "disp": False},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("seed_payload", type=Path)
    parser.add_argument("--weak-count", type=int, default=8)
    parser.add_argument("--release-count", type=int, default=4)
    parser.add_argument("--combination-limit", type=int, default=70)
    parser.add_argument("--relative-gaps", type=parse_floats, default=parse_floats("0.0005,0.005"))
    parser.add_argument(
        "--active-modes",
        type=parse_strings,
        default=parse_strings("release,promote_one,promote_pair"),
    )
    parser.add_argument("--boundary-depths", type=parse_floats, default=parse_floats("1,2"))
    parser.add_argument("--boundary-gaps", type=parse_floats, default=parse_floats("0.0001,0.001"))
    parser.add_argument("--maxiter", type=int, default=500)
    parser.add_argument("--ftol", type=float, default=1e-13)
    parser.add_argument("--checkpoint-every", type=int, default=10)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    args = parser.parse_args()
    allowed_modes = {"release", "promote_one", "promote_pair"}
    if not set(args.active_modes) <= allowed_modes:
        raise ValueError(f"active modes must be drawn from {sorted(allowed_modes)}")

    with args.seed_payload.open(encoding="utf-8") as handle:
        seed = np.asarray(json.load(handle)["points"], dtype=np.float64)
    active, signs, _ = active_triples(seed, 1e-12)
    contacts = boundary_contacts(seed, 1e-12)
    diagnostics = active_diagnostics(seed, active, signs, contacts)
    multipliers = {
        tuple(item["triple"]): float(item["multiplier"])
        for item in diagnostics["triple_multipliers"]
    }
    weak = sorted(active, key=multipliers.get)[: args.weak_count]
    combinations = sorted(
        itertools.combinations(weak, args.release_count),
        key=lambda group: sum(multipliers[triple] for triple in group),
    )[: args.combination_limit]
    inactive = sorted(
        (
            (abs(signed_double_area(seed, triple)) / 2.0, triple)
            for triple in itertools.combinations(range(COUNT), 3)
            if triple not in active
        ),
        key=lambda item: item[0],
    )
    promote_one = (inactive[0][1],)
    promote_pair = (inactive[0][1], inactive[1][1])
    model = HeilbronnModel(signs)
    initial = model.pack(seed)

    problem = get(f"/api/problems/{SLUG}")
    solutions = get("/api/solutions/best", problem_id=PROBLEM_ID, limit=100)
    leaderboard = get("/api/leaderboard", problem_id=PROBLEM_ID, limit=100)
    assert isinstance(problem, dict) and isinstance(solutions, list) and isinstance(leaderboard, list)
    live_best = float(solutions[0]["score"])
    target = live_best + float(problem["minImprovement"])
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
    namespace: dict[str, object] = {}
    exec(problem["verifier"], namespace)  # noqa: S102 -- live public verifier replay
    evaluate = namespace["evaluate"]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_json(run_dir / "problem.json", problem)
    atomic_json(run_dir / "leaderboard.json", leaderboard)
    atomic_json(run_dir / "best_solutions.json", solutions)
    atomic_json(run_dir / "seed.json", {"points": seed.tolist()})
    atomic_json(
        run_dir / "search_space.json",
        {
            "active_triples": active,
            "boundary_contacts": contacts,
            "weak_triples": weak,
            "weak_multipliers": {str(triple): multipliers[triple] for triple in weak},
            "active_combinations": combinations,
            "relative_gaps": args.relative_gaps,
            "active_modes": args.active_modes,
            "promote_one": promote_one,
            "promote_pair": promote_pair,
            "boundary_depths": args.boundary_depths,
            "boundary_gaps": args.boundary_gaps,
        },
    )

    base_constraint = {"type": "ineq", "fun": model.base_constraints, "jac": model.base_jacobian}
    best_points = seed.copy()
    best_score = verifier_score(evaluate, seed)
    best_topology_points = seed.copy()
    best_topology_score = -1e300
    seed_topology = (tuple(sorted(active)), tuple(contacts))
    seen_topologies = {seed_topology}
    best_distinct_generic_points: np.ndarray | None = None
    best_distinct_generic_score = -1e300
    trials: list[dict[str, object]] = []

    specifications: list[dict[str, object]] = []
    for group in combinations:
        for relative_gap in args.relative_gaps:
            for mode in args.active_modes:
                specifications.append(
                    {
                        "family": "active_depth4",
                        "released_triples": tuple(group),
                        "relative_gap": relative_gap,
                        "mode": mode,
                    }
                )
    for raw_depth in args.boundary_depths:
        depth = int(raw_depth)
        for group in itertools.combinations(contacts, depth):
            for boundary_gap in args.boundary_gaps:
                specifications.append(
                    {
                        "family": "boundary_release",
                        "released_contacts": tuple(group),
                        "boundary_gap": boundary_gap,
                    }
                )

    for trial_id, specification in enumerate(specifications, start=1):
        forced_constraints: list[dict[str, object]] = [base_constraint]
        topology_constraints: list[dict[str, object]] = [base_constraint]
        if specification["family"] == "active_depth4":
            released = specification["released_triples"]
            gap = float(specification["relative_gap"]) * initial[-1]
            topology_gap = min(gap, initial[-1] * 1e-5)
            forced_constraints.append(
                {
                    "type": "ineq",
                    "fun": lambda values, chosen=released, margin=gap: model.selected_area_slacks(values, chosen)
                    - margin,
                    "jac": lambda values, chosen=released: model.selected_area_jacobian(values, chosen),
                }
            )
            topology_constraints.append(
                {
                    "type": "ineq",
                    "fun": lambda values, chosen=released, margin=topology_gap: model.selected_area_slacks(
                        values, chosen
                    )
                    - margin,
                    "jac": lambda values, chosen=released: model.selected_area_jacobian(values, chosen),
                }
            )
            mode = str(specification["mode"])
            promoted: tuple[tuple[int, int, int], ...] = ()
            if mode == "promote_one":
                promoted = promote_one
            elif mode == "promote_pair":
                promoted = promote_pair
            if promoted:
                equality = {
                    "type": "eq",
                    "fun": lambda values, chosen=promoted: model.selected_area_slacks(values, chosen),
                    "jac": lambda values, chosen=promoted: model.selected_area_jacobian(values, chosen),
                }
                forced_constraints.append(equality)
                topology_constraints.append(equality)
        else:
            released_contacts = specification["released_contacts"]
            gap = float(specification["boundary_gap"])
            topology_gap = min(gap, 2e-7)
            forced_constraints.append(
                {
                    "type": "ineq",
                    "fun": lambda values, chosen=released_contacts, margin=gap: model.selected_boundary_slacks(
                        values, chosen
                    )
                    - margin,
                    "jac": lambda values, chosen=released_contacts: model.selected_boundary_jacobian(values, chosen),
                }
            )
            topology_constraints.append(
                {
                    "type": "ineq",
                    "fun": lambda values, chosen=released_contacts, margin=topology_gap: model.selected_boundary_slacks(
                        values, chosen
                    )
                    - margin,
                    "jac": lambda values, chosen=released_contacts: model.selected_boundary_jacobian(values, chosen),
                }
            )

        forced = solve(model, initial, forced_constraints, args.maxiter, args.ftol)
        topology = solve(model, forced.x, topology_constraints, args.maxiter, args.ftol)
        generic = solve(model, topology.x, [base_constraint], args.maxiter, args.ftol)
        stage_records = []
        for stage_name, result in (("forced", forced), ("topology", topology), ("generic", generic)):
            points, _ = model.unpack(result.x)
            local = metrics(points)
            official = verifier_score(evaluate, points)
            topology_label = (tuple(local["active_triples"]), tuple(local["boundary_contacts"]))
            seen_topologies.add(topology_label)
            if local["intended_domain"] and official > best_score:
                best_score, best_points = official, points.copy()
                atomic_json(run_dir / "best.json", {"points": best_points.tolist()})
            if (
                stage_name == "topology"
                and topology_label != seed_topology
                and local["intended_domain"]
                and official > best_topology_score
            ):
                best_topology_score, best_topology_points = official, points.copy()
                atomic_json(run_dir / "best_topology.json", {"points": best_topology_points.tolist()})
            if (
                stage_name == "generic"
                and topology_label != seed_topology
                and local["intended_domain"]
                and official > best_distinct_generic_score
            ):
                best_distinct_generic_score = official
                best_distinct_generic_points = points.copy()
                atomic_json(run_dir / "best_distinct_generic.json", {"points": points.tolist()})
            stage_records.append(
                {
                    "stage": stage_name,
                    "success": bool(result.success),
                    "status": int(result.status),
                    "message": str(result.message),
                    "iterations": int(result.nit),
                    "official_score": official,
                    "model_score": local["score"],
                    "active_triples": len(local["active_triples"]),
                    "boundary_contacts": len(local["boundary_contacts"]),
                    "intended_domain": local["intended_domain"],
                    "topology_changed": topology_label != seed_topology,
                }
            )
        record = {"trial": trial_id, **specification, "stages": stage_records}
        trials.append(record)
        append(events, record)
        if trial_id % args.checkpoint_every == 0:
            atomic_json(
                run_dir / f"checkpoint_{trial_id:04d}.json",
                {
                    "completed": trial_id,
                    "total": len(specifications),
                    "best_score": best_score,
                    "best_topology_score": best_topology_score,
                    "distinct_labeled_topologies": len(seen_topologies),
                },
            )

    atomic_json(run_dir / "best.json", {"points": best_points.tolist()})
    atomic_json(run_dir / "best_topology.json", {"points": best_topology_points.tolist()})
    if best_distinct_generic_points is not None:
        atomic_json(
            run_dir / "best_distinct_generic.json",
            {"points": best_distinct_generic_points.tolist()},
        )
    generic_scores = [stage["official_score"] for trial in trials for stage in trial["stages"] if stage["stage"] == "generic"]
    summary = {
        "slug": SLUG,
        "verifier_sha256": verifier_hash,
        "live_best": live_best,
        "target": target,
        "trial_count": len(trials),
        "active_depth4_trials": sum(spec["family"] == "active_depth4" for spec in specifications),
        "boundary_release_trials": sum(spec["family"] == "boundary_release" for spec in specifications),
        "distinct_labeled_topologies": len(seen_topologies),
        "best_official_score": best_score,
        "improvement_over_live": best_score - live_best,
        "gate_clearing": best_score > target,
        "best_forced_topology_score": best_topology_score,
        "best_generic_score": max(generic_scores),
        "best_distinct_generic_score": (
            best_distinct_generic_score if best_distinct_generic_points is not None else None
        ),
        "generic_distinct_intended_count": sum(
            stage["topology_changed"] and stage["intended_domain"]
            for trial in trials
            for stage in trial["stages"]
            if stage["stage"] == "generic"
        ),
        "generic_distinct_rejected_count": sum(
            stage["topology_changed"] and not stage["intended_domain"]
            for trial in trials
            for stage in trial["stages"]
            if stage["stage"] == "generic"
        ),
        "payload": str((run_dir / "best.json").resolve()),
        "best_topology_payload": str((run_dir / "best_topology.json").resolve()),
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
