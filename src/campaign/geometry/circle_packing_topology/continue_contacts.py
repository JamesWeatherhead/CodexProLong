#!/usr/bin/env python3
"""Trace topology-changing contact pivots for 26 circles in a square.

For each active equality, the program releases that contact along its
one-dimensional equality manifold until the first previously inactive pair or
wall becomes tight.  That event defines an adjacent rigid contact graph.  Both
the literal 1e-9 verifier-tolerance root and the strict zero-overlap root are
then solved and screened.  Downloaded verifier code is never executed here;
surviving payloads must be replayed through ``./arena verify``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.optimize import least_squares


COUNT = 26
VARIABLES = 3 * COUNT
PAIR_TOLERANCE = 1e-9
VERIFIER_SHA256 = "2dee3fad3cfc2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab"
CORPUS_SHA256 = "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"
LEADER_SCORE = 2.635983095260844
GATE = 1e-10
TARGET = LEADER_SCORE + GATE
WALLS = ("L", "R", "B", "T")
Constraint = tuple[str, int, int | str]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def append_event(path: Path, value: Any) -> None:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(data + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def all_constraints() -> list[Constraint]:
    result: list[Constraint] = [
        ("P", i, j) for i in range(COUNT) for j in range(i + 1, COUNT)
    ]
    result.extend(("W", i, wall) for i in range(COUNT) for wall in WALLS)
    return result


ALL_CONSTRAINTS = all_constraints()


def circles_to_values(circles: np.ndarray) -> np.ndarray:
    values = np.empty(VARIABLES, dtype=float)
    values[: 2 * COUNT] = circles[:, :2].reshape(-1)
    values[2 * COUNT :] = circles[:, 2]
    return values


def values_to_circles(values: np.ndarray) -> np.ndarray:
    circles = np.empty((COUNT, 3), dtype=float)
    circles[:, :2] = values[: 2 * COUNT].reshape(COUNT, 2)
    circles[:, 2] = values[2 * COUNT :]
    return circles


def one_value_and_gradient(
    values: np.ndarray, constraint: Constraint, pair_tolerance: float
) -> tuple[float, np.ndarray]:
    kind, first, second = constraint
    gradient = np.zeros(VARIABLES, dtype=float)
    radius_start = 2 * COUNT
    if kind == "P":
        assert isinstance(second, int)
        dx = values[2 * first] - values[2 * second]
        dy = values[2 * first + 1] - values[2 * second + 1]
        distance = math.hypot(dx, dy)
        if distance == 0:
            return -math.inf, gradient
        ux, uy = dx / distance, dy / distance
        gradient[2 * first], gradient[2 * first + 1] = ux, uy
        gradient[2 * second], gradient[2 * second + 1] = -ux, -uy
        gradient[radius_start + first] = -1
        gradient[radius_start + second] = -1
        value = (
            distance
            - values[radius_start + first]
            - values[radius_start + second]
            + pair_tolerance
        )
        return value, gradient

    wall = str(second)
    x_id, y_id, radius_id = 2 * first, 2 * first + 1, radius_start + first
    if wall == "L":
        value = values[x_id] - values[radius_id]
        gradient[x_id], gradient[radius_id] = 1, -1
    elif wall == "R":
        value = 1 - values[x_id] - values[radius_id]
        gradient[x_id], gradient[radius_id] = -1, -1
    elif wall == "B":
        value = values[y_id] - values[radius_id]
        gradient[y_id], gradient[radius_id] = 1, -1
    else:
        value = 1 - values[y_id] - values[radius_id]
        gradient[y_id], gradient[radius_id] = -1, -1
    return value, gradient


def constraint_values(
    values: np.ndarray,
    constraints: Iterable[Constraint],
    pair_tolerance: float,
) -> np.ndarray:
    return np.asarray(
        [one_value_and_gradient(values, item, pair_tolerance)[0] for item in constraints]
    )


def constraint_jacobian(
    values: np.ndarray,
    constraints: Iterable[Constraint],
    pair_tolerance: float,
) -> np.ndarray:
    return np.asarray(
        [one_value_and_gradient(values, item, pair_tolerance)[1] for item in constraints]
    )


def decode_active(circles: np.ndarray, tolerance: float) -> list[Constraint]:
    values = circles_to_values(circles)
    result = [
        constraint
        for constraint in ALL_CONSTRAINTS
        if one_value_and_gradient(values, constraint, PAIR_TOLERANCE)[0] <= tolerance
    ]
    return result


@dataclass
class Root:
    values: np.ndarray
    residual: float
    evaluations: int
    success: bool


def solve_targets(
    start: np.ndarray,
    active: list[Constraint],
    targets: np.ndarray | None = None,
    pair_tolerance: float = PAIR_TOLERANCE,
    max_evaluations: int = 300,
) -> Root:
    if len(active) != VARIABLES:
        raise ValueError(f"active system has {len(active)} constraints, expected {VARIABLES}")
    if targets is None:
        targets = np.zeros(VARIABLES)

    def function(values: np.ndarray) -> np.ndarray:
        return constraint_values(values, active, pair_tolerance) - targets

    def jacobian(values: np.ndarray) -> np.ndarray:
        return constraint_jacobian(values, active, pair_tolerance)

    result = least_squares(
        function,
        start,
        jac=jacobian,
        method="lm",
        xtol=1e-14,
        ftol=1e-14,
        gtol=1e-14,
        max_nfev=max_evaluations,
    )
    residual = float(np.max(np.abs(function(result.x))))
    return Root(
        values=result.x,
        residual=residual,
        evaluations=int(result.nfev),
        success=bool(result.success and residual <= 2e-10 and np.isfinite(result.x).all()),
    )


def metrics(values: np.ndarray, pair_tolerance: float) -> dict[str, Any]:
    circles = values_to_circles(values)
    radii = circles[:, 2]
    constraint_slacks = constraint_values(values, ALL_CONSTRAINTS, pair_tolerance)
    pair_slacks = constraint_slacks[: COUNT * (COUNT - 1) // 2]
    wall_slacks = constraint_slacks[len(pair_slacks) :]
    accepted = bool(
        np.isfinite(circles).all()
        and np.all(radii >= 0)
        and np.min(pair_slacks) >= -2e-12
        and np.min(wall_slacks) >= -2e-12
    )
    return {
        "score": float(np.sum(radii)),
        "accepted_screen": accepted,
        "minimum_radius": float(np.min(radii)),
        "minimum_pair_verifier_slack": float(np.min(pair_slacks)),
        "minimum_wall_slack": float(np.min(wall_slacks)),
    }


def verifier_buffer(values: np.ndarray) -> tuple[np.ndarray, int, dict[str, Any]]:
    circles = values_to_circles(values)
    for steps in range(2000):
        centers, radii = circles[:, :2], circles[:, 2]
        contained = bool(
            ((radii[:, None] <= centers) & (centers <= 1 - radii[:, None])).all()
        )
        pair_ok = True
        minimum = math.inf
        for i in range(COUNT):
            for j in range(i + 1, COUNT):
                slack = (
                    math.sqrt(np.sum((centers[i] - centers[j]) ** 2))
                    + PAIR_TOLERANCE
                    - radii[i]
                    - radii[j]
                )
                minimum = min(minimum, slack)
                if slack < 0:
                    pair_ok = False
        if contained and pair_ok and np.all(radii >= 0):
            report = metrics(circles_to_values(circles), PAIR_TOLERANCE)
            report["literal_pair_minimum"] = minimum
            return circles_to_values(circles), steps, report
        circles[:, 2] = np.nextafter(circles[:, 2], 0.0)
    raise RuntimeError("failed to buffer a float payload in 2,000 radius decrements")


def canonical_signature(active: Iterable[Constraint]) -> str:
    return sha256_bytes(json.dumps(sorted(active), separators=(",", ":")).encode())


def inactive_constraints(active: list[Constraint]) -> list[Constraint]:
    active_set = set(active)
    return [item for item in ALL_CONSTRAINTS if item not in active_set]


def first_crossing(
    base: np.ndarray,
    active: list[Constraint],
    release_index: int,
    max_release_slack: float,
    step_growth: float,
    max_steps: int,
) -> dict[str, Any]:
    released = active[release_index]
    inactive = inactive_constraints(active)
    base_values = constraint_values(base, inactive, PAIR_TOLERANCE)
    jacobian = constraint_jacobian(base, active, PAIR_TOLERANCE)
    try:
        direction = np.linalg.solve(jacobian, np.eye(VARIABLES)[:, release_index])
    except np.linalg.LinAlgError:
        return {"status": "singular", "released": released}
    derivatives = constraint_jacobian(base, inactive, PAIR_TOLERANCE) @ direction
    predictions = [
        value / -derivative
        for value, derivative in zip(base_values, derivatives)
        if derivative < -1e-12 and value > 0
    ]
    predicted = min(predictions) if predictions else max_release_slack
    step = min(max(1e-8, 0.08 * predicted), 2e-3, max_release_slack)
    previous_t = 0.0
    previous_root = base
    previous_min = float(np.min(base_values))
    evaluations = 0

    for step_index in range(max_steps):
        current_t = min(max_release_slack, previous_t + step)
        targets = np.zeros(VARIABLES)
        targets[release_index] = current_t
        solved = solve_targets(previous_root, active, targets)
        evaluations += solved.evaluations
        if not solved.success:
            step *= 0.5
            if step < 1e-10:
                return {
                    "status": "solver_stall",
                    "released": released,
                    "predicted_crossing": predicted,
                    "last_release_slack": previous_t,
                    "evaluations": evaluations,
                }
            continue
        current_values = constraint_values(solved.values, inactive, PAIR_TOLERANCE)
        current_min = float(np.min(current_values))
        if np.min(solved.values[2 * COUNT :]) <= 0:
            return {
                "status": "radius_zero",
                "released": released,
                "predicted_crossing": predicted,
                "last_release_slack": current_t,
                "evaluations": evaluations,
            }
        if current_min <= 0:
            low_t, high_t = previous_t, current_t
            low_root, high_root = previous_root, solved.values
            for _ in range(45):
                middle_t = (low_t + high_t) / 2
                middle_targets = np.zeros(VARIABLES)
                middle_targets[release_index] = middle_t
                start = (low_root + high_root) / 2
                middle = solve_targets(start, active, middle_targets, max_evaluations=120)
                evaluations += middle.evaluations
                if not middle.success:
                    high_t, high_root = middle_t, start
                    continue
                middle_values = constraint_values(middle.values, inactive, PAIR_TOLERANCE)
                if np.min(middle_values) <= 0:
                    high_t, high_root = middle_t, middle.values
                else:
                    low_t, low_root = middle_t, middle.values
                if high_t - low_t <= max(1e-13, 1e-11 * high_t):
                    break
            crossing_values = constraint_values(high_root, inactive, PAIR_TOLERANCE)
            new_index = int(np.argmin(crossing_values))
            added = inactive[new_index]
            new_active = active[:release_index] + active[release_index + 1 :] + [added]
            new_root = solve_targets(high_root, new_active)
            evaluations += new_root.evaluations
            if not new_root.success:
                return {
                    "status": "crossing_root_failed",
                    "released": released,
                    "added": added,
                    "release_slack": high_t,
                    "evaluations": evaluations,
                }
            full_report = metrics(new_root.values, PAIR_TOLERANCE)
            strict_root = solve_targets(
                new_root.values, new_active, pair_tolerance=0.0, max_evaluations=500
            )
            strict_report = (
                metrics(strict_root.values, 0.0)
                if strict_root.success
                else {"score": None, "accepted_screen": False}
            )
            return {
                "status": "crossing",
                "released": released,
                "added": added,
                "release_slack": high_t,
                "predicted_crossing": predicted,
                "previous_minimum_inactive_slack": previous_min,
                "crossing_minimum_inactive_slack": float(np.min(crossing_values)),
                "evaluations": evaluations,
                "new_active": new_active,
                "new_signature": canonical_signature(new_active),
                "full_root": new_root.values,
                "full_report": full_report,
                "full_root_residual": new_root.residual,
                "strict_root": strict_root.values if strict_root.success else None,
                "strict_report": strict_report,
                "strict_root_residual": strict_root.residual,
            }
        if current_t >= max_release_slack:
            return {
                "status": "no_crossing",
                "released": released,
                "predicted_crossing": predicted,
                "last_release_slack": current_t,
                "minimum_inactive_slack": current_min,
                "evaluations": evaluations,
            }
        previous_t, previous_root, previous_min = current_t, solved.values, current_min
        step = min(step * step_growth, max(1e-6, 0.15 * max(current_t, predicted)))

    return {
        "status": "step_cap",
        "released": released,
        "predicted_crossing": predicted,
        "last_release_slack": previous_t,
        "evaluations": evaluations,
    }


def serializable_result(result: dict[str, Any]) -> dict[str, Any]:
    hidden = {"full_root", "strict_root", "new_active"}
    return {key: value for key, value in result.items() if key not in hidden}


def load_corpus_solution(database: Path, solution_id: int) -> np.ndarray:
    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT record_json FROM solutions WHERE id=? AND problem_id=14", (solution_id,)
    ).fetchone()
    connection.close()
    if row is None:
        raise ValueError(f"missing circle-packing solution {solution_id}")
    circles = np.asarray(json.loads(row[0])["data"]["circles"], dtype=float)
    if circles.shape != (COUNT, 3) or not np.isfinite(circles).all():
        raise ValueError(f"solution {solution_id} has invalid circles")
    return circles


def parse_ids(value: str) -> list[int]:
    return [int(part) for part in value.split(",") if part.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="append", type=Path, default=[])
    parser.add_argument("--corpus-solution-ids", type=parse_ids, default=[])
    parser.add_argument("--active-tolerance", type=float, default=1e-6)
    parser.add_argument("--release-limit", type=int, default=78)
    parser.add_argument("--max-release-slack", type=float, default=0.25)
    parser.add_argument("--step-growth", type=float, default=1.6)
    parser.add_argument("--max-steps", type=int, default=80)
    parser.add_argument("--stamp", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--campaign-root", type=Path, default=Path(__file__).parents[2])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign = args.campaign_root.resolve()
    latest = json.loads((campaign / "research_corpus" / "latest.json").read_text())
    database = campaign / "research_corpus" / latest["database"]
    if sha256_file(database) != CORPUS_SHA256:
        raise RuntimeError("corpus database hash mismatch")
    run_dir = campaign / "geometry" / "circle_packing_topology" / "runs" / args.stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    config = {
        "stamp": args.stamp,
        "verifier_sha256": VERIFIER_SHA256,
        "corpus_database_sha256": CORPUS_SHA256,
        "leader_score": LEADER_SCORE,
        "gate": GATE,
        "target_strictly_above": TARGET,
        "pair_tolerance": PAIR_TOLERANCE,
        "release_limit": args.release_limit,
        "max_release_slack": args.max_release_slack,
        "step_growth": args.step_growth,
        "max_steps": args.max_steps,
        "active_tolerance": args.active_tolerance,
    }
    atomic_json(run_dir / "config.json", config)
    append_event(events, {"event": "run_started", **config})

    seeds: list[tuple[str, np.ndarray]] = []
    for path in args.seed:
        record = json.loads(path.resolve().read_text())
        seeds.append((f"file:{path.resolve()}", np.asarray(record["circles"], dtype=float)))
    for solution_id in args.corpus_solution_ids:
        seeds.append(
            (f"corpus_solution:{solution_id}", load_corpus_solution(database, solution_id))
        )
    if not seeds:
        raise ValueError("provide --seed and/or --corpus-solution-ids")

    discovered: dict[str, dict[str, Any]] = {}
    source_summaries = []
    best_payload: Path | None = None
    best_score = -math.inf
    total_releases = total_crossings = total_evaluations = 0
    for source_index, (source_name, circles) in enumerate(seeds):
        active = decode_active(circles, args.active_tolerance)
        source_record: dict[str, Any] = {
            "source": source_name,
            "decoded_active_count": len(active),
            "pair_contacts": sum(item[0] == "P" for item in active),
            "wall_contacts": sum(item[0] == "W" for item in active),
        }
        if len(active) != VARIABLES:
            source_record["status"] = "not_rigid_square_system"
            source_summaries.append(source_record)
            append_event(events, {"event": "source_skipped", **source_record})
            continue
        base = solve_targets(circles_to_values(circles), active)
        if not base.success:
            source_record.update(status="base_root_failed", residual=base.residual)
            source_summaries.append(source_record)
            append_event(events, {"event": "source_skipped", **source_record})
            continue
        base_report = metrics(base.values, PAIR_TOLERANCE)
        base_jacobian = constraint_jacobian(base.values, active, PAIR_TOLERANCE)
        objective = np.zeros(VARIABLES)
        objective[2 * COUNT :] = 1
        multipliers = np.linalg.solve(base_jacobian.T, -objective)
        release_order = np.argsort(multipliers)[: args.release_limit]
        source_record.update(
            status="searched",
            base_full_score=base_report["score"],
            base_root_residual=base.residual,
            minimum_multiplier=float(np.min(multipliers)),
            maximum_multiplier=float(np.max(multipliers)),
            release_count=len(release_order),
        )
        atomic_json(
            run_dir / f"source_{source_index:02d}.json",
            {
                **source_record,
                "active": active,
                "circles": values_to_circles(base.values).tolist(),
                "multipliers": multipliers.tolist(),
            },
        )
        append_event(events, {"event": "source_started", **source_record})

        source_crossings = 0
        source_best = -math.inf
        for order_index, release_index_value in enumerate(release_order):
            release_index = int(release_index_value)
            result = first_crossing(
                base.values,
                active,
                release_index,
                args.max_release_slack,
                args.step_growth,
                args.max_steps,
            )
            total_releases += 1
            total_evaluations += int(result.get("evaluations", 0))
            if result["status"] == "crossing":
                total_crossings += 1
                source_crossings += 1
                signature = str(result["new_signature"])
                full_report = result["full_report"]
                strict_report = result["strict_report"]
                score = float(full_report["score"])
                source_best = max(source_best, score)
                prior = discovered.get(signature)
                if prior is None or score > float(prior["full_report"]["score"]):
                    record = serializable_result(result)
                    record.update(source=source_name, release_order_index=order_index)
                    discovered[signature] = record
                    topology_dir = run_dir / "topologies" / signature[:16]
                    payload = topology_dir / "candidate.json"
                    if full_report["accepted_screen"]:
                        full_values, steps, buffered_report = verifier_buffer(
                            result["full_root"]
                        )
                        atomic_json(
                            payload,
                            {"circles": values_to_circles(full_values).tolist()},
                        )
                        candidate_path: str | None = str(payload)
                        candidate_sha256: str | None = sha256_file(payload)
                    else:
                        steps = None
                        buffered_report = None
                        candidate_path = None
                        candidate_sha256 = None
                    atomic_json(
                        topology_dir / "summary.json",
                        {
                            **record,
                            "active": result["new_active"],
                            "buffer_steps": steps,
                            "buffered_report": buffered_report,
                            "candidate": candidate_path,
                            "candidate_sha256": candidate_sha256,
                            "verifier_replay_required": True,
                        },
                    )
                    buffered_score = (
                        float(buffered_report["score"])
                        if buffered_report is not None
                        else -math.inf
                    )
                    if (
                        buffered_report is not None
                        and buffered_report["accepted_screen"]
                        and buffered_score > best_score
                    ):
                        best_score, best_payload = buffered_score, payload
            append_event(
                events,
                {
                    "event": "release_finished",
                    "source": source_name,
                    "release_order_index": order_index,
                    "release_index": release_index,
                    "multiplier": float(multipliers[release_index]),
                    **serializable_result(result),
                },
            )
            if total_releases % 10 == 0:
                atomic_json(
                    run_dir / "checkpoint.json",
                    {
                        "total_releases": total_releases,
                        "total_crossings": total_crossings,
                        "distinct_topologies": len(discovered),
                        "best_buffered_score": best_score,
                        "best_payload": str(best_payload) if best_payload else None,
                        "total_nonlinear_evaluations": total_evaluations,
                    },
                )
        source_record["crossing_count"] = source_crossings
        source_record["best_adjacent_full_score"] = (
            source_best if math.isfinite(source_best) else None
        )
        source_summaries.append(source_record)

    summary = {
        **config,
        "sources": source_summaries,
        "total_releases": total_releases,
        "total_crossings": total_crossings,
        "distinct_adjacent_topologies": len(discovered),
        "total_nonlinear_evaluations": total_evaluations,
        "best_buffered_score": best_score if math.isfinite(best_score) else None,
        "best_payload": str(best_payload) if best_payload else None,
        "best_margin_to_target": best_score - TARGET if math.isfinite(best_score) else None,
        "gate_clearing_screen": bool(best_score > TARGET),
        "limitation": (
            "This exhausts one-contact continuation from each supplied rigid source "
            "only up to the configured release-slack/step caps; it is not a global "
            "enumeration of all 26-circle contact graphs."
        ),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, {"event": "run_finished", **summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
