#!/usr/bin/env python3
"""Systematic codimension-two contact pivots for n=26 circle packing.

This is intentionally different from the earlier one-contact continuation and
random multi-contact perturbation campaigns.  For every selected pair of
active contacts, it opens both contacts and studies the two-dimensional
linearized flex cone.  A dense angular sweep identifies adjacent inactive
constraints on the cone boundary.  Each predicted two-contact vertex defines
a rigid graph obtained by replacing two old contacts with two new ones; that
graph is solved nonlinearly under both the literal 1e-9 pair tolerance and the
strict physical constraints.

Downloaded verifier code is never imported or executed.  Every accepted
payload is evaluated by a clean-room formula mirror after the frozen verifier
bytes pass a SHA-256 check, and its exact JSON shape is checked against the
live API schema recorded by the campaign.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

import verifier_formula


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
TOPOLOGY = CAMPAIGN / "geometry" / "circle_packing_topology"
sys.path.insert(0, str(TOPOLOGY))
import continue_contacts as cc  # noqa: E402


VERIFIER = verifier_formula.VERIFIER
VERIFIER_SHA256 = verifier_formula.VERIFIER_SHA256
LEADER = 2.635983095260844
MIN_IMPROVEMENT = 1e-10
TARGET = LEADER + MIN_IMPROVEMENT
LIVE_SCHEMA = {"circles": "array of [x, y, r] triples"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_verifier():
    verifier_formula.assert_verifier_hash()
    return verifier_formula.evaluate


def schema_valid(payload: dict[str, Any]) -> bool:
    if set(payload) != {"circles"}:
        return False
    try:
        circles = np.asarray(payload["circles"], dtype=np.float64)
    except (TypeError, ValueError):
        return False
    return bool(circles.shape == (cc.COUNT, 3) and np.isfinite(circles).all())


def tuple_constraint(item: cc.Constraint) -> list[Any]:
    return [item[0], int(item[1]), item[2]]


def predicted_vertices(
    gaps: np.ndarray,
    derivatives: np.ndarray,
    angle_count: int,
    maximum_opening: float,
) -> list[dict[str, Any]]:
    """Return feasible 2D linearized vertices visible from the base point."""
    epsilon = 1e-7
    angles = np.linspace(epsilon, math.pi / 2 - epsilon, angle_count)
    directions = np.stack((np.cos(angles), np.sin(angles)))
    rates = derivatives @ directions
    crossing = np.full_like(rates, np.inf)
    mask = rates < -1e-13
    np.divide(gaps[:, None], -rates, out=crossing, where=mask)
    winners = np.argmin(crossing, axis=0)
    distances = crossing[winners, np.arange(angle_count)]
    winners = winners[np.isfinite(distances) & (distances <= maximum_opening * 2)]
    if winners.size < 2:
        return []

    # Every change in the first-hit constraint along angle identifies a vertex
    # of the star-shaped linearized feasible polygon.  Also test all pairs in
    # the typically small visible support set to avoid discretization misses.
    visible = list(dict.fromkeys(int(index) for index in winners))
    pairs: set[tuple[int, int]] = set()
    previous = int(winners[0])
    for value in winners[1:]:
        current = int(value)
        if current != previous:
            pairs.add(tuple(sorted((previous, current))))
        previous = current
    if len(visible) <= 24:
        pairs.update(itertools.combinations(sorted(visible), 2))

    vertices: list[dict[str, Any]] = []
    for first, second in sorted(pairs):
        matrix = derivatives[[first, second]]
        determinant = float(np.linalg.det(matrix))
        if abs(determinant) <= 1e-12:
            continue
        opening = np.linalg.solve(matrix, -gaps[[first, second]])
        if np.min(opening) <= 2e-8 or np.max(opening) > maximum_opening:
            continue
        slacks = gaps + derivatives @ opening
        minimum = float(np.min(slacks))
        if minimum < -max(2e-7, 2e-5 * float(np.max(opening))):
            continue
        vertices.append(
            {
                "new_indices": [first, second],
                "opening": opening,
                "linear_minimum_slack": minimum,
                "linear_objective_opening": None,
            }
        )
    return vertices


def make_start(
    base: np.ndarray,
    active: list[cc.Constraint],
    released: tuple[int, int],
    opening: np.ndarray,
) -> tuple[np.ndarray, int, float]:
    targets = np.zeros(cc.VARIABLES)
    targets[released[0]], targets[released[1]] = opening
    solved = cc.solve_targets(base, active, targets, max_evaluations=450)
    if solved.success:
        return solved.values, solved.evaluations, solved.residual

    jacobian = cc.constraint_jacobian(base, active, cc.PAIR_TOLERANCE)
    rhs = np.zeros(cc.VARIABLES)
    rhs[released[0]], rhs[released[1]] = opening
    try:
        linear = base + np.linalg.solve(jacobian, rhs)
    except np.linalg.LinAlgError:
        linear = base.copy()
    return linear, solved.evaluations, solved.residual


def exact_payload(values: np.ndarray, evaluate) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    try:
        buffered, nextafter_steps, screen = cc.verifier_buffer(values)
    except RuntimeError as error:
        raw = cc.values_to_circles(values)
        raw_centers, raw_radii = raw[:, :2], raw[:, 2]
        pair_overrun = max(
            float(
                raw_radii[first]
                + raw_radii[second]
                - np.linalg.norm(raw_centers[first] - raw_centers[second])
            )
            for first in range(cc.COUNT)
            for second in range(first + 1, cc.COUNT)
        )
        wall_overrun = float(
            max(
                np.max(raw_radii - raw_centers[:, 0]),
                np.max(raw_radii - raw_centers[:, 1]),
                np.max(raw_centers[:, 0] + raw_radii - 1),
                np.max(raw_centers[:, 1] + raw_radii - 1),
            )
        )
        return None, {
            "schema_valid": True,
            "literal_verifier_accepted": False,
            "buffer_failure": str(error),
            "raw_maximum_pair_overrun": pair_overrun,
            "raw_maximum_wall_overrun": wall_overrun,
        }
    payload = {"circles": cc.values_to_circles(buffered).tolist()}
    if not schema_valid(payload):
        return None, {"schema_valid": False}
    score = float(evaluate(payload))
    accepted = math.isfinite(score)
    circles = np.asarray(payload["circles"], dtype=np.float64)
    centers, radii = circles[:, :2], circles[:, 2]
    pair_overrun = -math.inf
    for first in range(cc.COUNT):
        for second in range(first + 1, cc.COUNT):
            distance = float(np.linalg.norm(centers[first] - centers[second]))
            pair_overrun = max(pair_overrun, float(radii[first] + radii[second] - distance))
    wall_overrun = float(
        max(
            np.max(radii - centers[:, 0]),
            np.max(radii - centers[:, 1]),
            np.max(centers[:, 0] + radii - 1),
            np.max(centers[:, 1] + radii - 1),
        )
    )
    report = {
        "schema_valid": True,
        "literal_verifier_accepted": accepted,
        "literal_verifier_score": score if accepted else None,
        "nextafter_buffer_steps": nextafter_steps,
        "maximum_pair_overrun": pair_overrun,
        "maximum_wall_overrun": wall_overrun,
        "pair_tolerance_only": bool(pair_overrun > 2e-12),
        "physical_strict": bool(pair_overrun <= 2e-12 and wall_overrun <= 0),
        "screen": screen,
    }
    return (payload if accepted else None), report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        type=Path,
        default=CAMPAIGN / "geometry/runs/20260815T035000Z/circle-packing/candidate.json",
    )
    parser.add_argument("--stamp", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--release-pair-limit", type=int, default=3003)
    parser.add_argument("--angle-count", type=int, default=513)
    parser.add_argument("--maximum-opening", type=float, default=0.35)
    parser.add_argument("--maximum-vertices-per-release", type=int, default=12)
    parser.add_argument("--active-tolerance", type=float, default=1e-6)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run = HERE / "runs" / args.stamp
    run.mkdir(parents=True, exist_ok=False)
    events = run / "events.jsonl"
    evaluate = load_verifier()

    seed_record = json.loads(args.seed.resolve().read_text())
    try:
        circles = np.asarray(seed_record["circles"], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("seed has no numeric circles array") from error
    if circles.shape != (cc.COUNT, 3) or not np.isfinite(circles).all():
        raise ValueError("seed circles do not have shape (26, 3)")
    active = cc.decode_active(circles, args.active_tolerance)
    if len(active) != cc.VARIABLES:
        raise RuntimeError(f"expected 78 active contacts, decoded {len(active)}")
    base_root = cc.solve_targets(cc.circles_to_values(circles), active)
    if not base_root.success:
        raise RuntimeError(f"base root failed: {base_root.residual}")
    base = base_root.values
    base_payload, base_exact = exact_payload(base, evaluate)
    assert base_payload is not None

    jacobian = cc.constraint_jacobian(base, active, cc.PAIR_TOLERANCE)
    inverse = np.linalg.solve(jacobian, np.eye(cc.VARIABLES))
    objective = np.zeros(cc.VARIABLES)
    objective[2 * cc.COUNT :] = 1
    multipliers = np.linalg.solve(jacobian.T, -objective)
    inactive = cc.inactive_constraints(active)
    gaps = cc.constraint_values(base, inactive, cc.PAIR_TOLERANCE)
    inactive_jacobian = cc.constraint_jacobian(base, inactive, cc.PAIR_TOLERANCE)

    # Lowest total KKT load first, but eventually enumerate all C(78,2).
    release_pairs = list(itertools.combinations(range(cc.VARIABLES), 2))
    release_pairs.sort(key=lambda pair: (multipliers[pair[0]] + multipliers[pair[1]], pair))
    release_pairs = release_pairs[: args.release_pair_limit]
    config = {
        "stamp": args.stamp,
        "seed": str(args.seed.resolve()),
        "seed_sha256": sha256_file(args.seed.resolve()),
        "verifier": str(VERIFIER),
        "verifier_sha256": VERIFIER_SHA256,
        "live_solution_schema": LIVE_SCHEMA,
        "leader": LEADER,
        "min_improvement": MIN_IMPROVEMENT,
        "target_strictly_above": TARGET,
        "pair_tolerance": cc.PAIR_TOLERANCE,
        "wall_tolerance": 0.0,
        "release_pair_count": len(release_pairs),
        "angle_count": args.angle_count,
        "maximum_opening": args.maximum_opening,
        "maximum_vertices_per_release": args.maximum_vertices_per_release,
        "base": base_exact,
        "base_active": [tuple_constraint(item) for item in active],
        "base_multipliers": multipliers.tolist(),
    }
    atomic_json(run / "config.json", config)
    append_jsonl(events, {"event": "run_started", **config})

    tested_graphs: set[str] = set()
    best_score = float(base_exact["literal_verifier_score"])
    best_payload_path = run / "best.json"
    atomic_json(best_payload_path, base_payload)
    best_record: dict[str, Any] = {
        "source": "base",
        "score": best_score,
        "payload": str(best_payload_path),
        "payload_sha256": sha256_file(best_payload_path),
        "exact": base_exact,
    }
    counters = {
        "release_pairs_processed": 0,
        "linear_vertices": 0,
        "graphs_tested": 0,
        "duplicate_graphs": 0,
        "root_failures": 0,
        "infeasible_roots": 0,
        "accepted_distinct_graphs": 0,
        "strict_roots": 0,
        "noncanonical_better_than_next_frontier": 0,
        "total_nonlinear_evaluations": base_root.evaluations,
    }
    next_noncanonical_frontier = 2.6359774051184153

    for order, released in enumerate(release_pairs):
        derivative = inactive_jacobian @ inverse[:, released]
        vertices = predicted_vertices(
            gaps, derivative, args.angle_count, args.maximum_opening
        )
        for vertex in vertices:
            vertex["linear_objective_opening"] = float(
                objective @ inverse[:, released] @ vertex["opening"]
            )
        vertices.sort(
            key=lambda item: (
                -float(item["linear_objective_opening"]),
                float(np.max(item["opening"])),
            )
        )
        vertices = vertices[: args.maximum_vertices_per_release]
        counters["linear_vertices"] += len(vertices)

        for vertex_index, vertex in enumerate(vertices):
            new_indices = tuple(int(value) for value in vertex["new_indices"])
            new_active = [
                item for index, item in enumerate(active) if index not in set(released)
            ] + [inactive[new_indices[0]], inactive[new_indices[1]]]
            signature = cc.canonical_signature(new_active)
            if signature in tested_graphs:
                counters["duplicate_graphs"] += 1
                continue
            tested_graphs.add(signature)
            counters["graphs_tested"] += 1

            start, start_evaluations, start_residual = make_start(
                base, active, released, np.asarray(vertex["opening"])
            )
            tolerance_root = cc.solve_targets(
                start, new_active, pair_tolerance=cc.PAIR_TOLERANCE, max_evaluations=750
            )
            counters["total_nonlinear_evaluations"] += start_evaluations + tolerance_root.evaluations
            if not tolerance_root.success:
                counters["root_failures"] += 1
                append_jsonl(
                    events,
                    {
                        "event": "graph_root_failed",
                        "release_order": order,
                        "released": [tuple_constraint(active[index]) for index in released],
                        "added": [tuple_constraint(inactive[index]) for index in new_indices],
                        "opening": np.asarray(vertex["opening"]).tolist(),
                        "start_residual": start_residual,
                        "root_residual": tolerance_root.residual,
                        "signature": signature,
                    },
                )
                continue

            payload, exact = exact_payload(tolerance_root.values, evaluate)
            if payload is None:
                counters["infeasible_roots"] += 1
                append_jsonl(
                    events,
                    {
                        "event": "graph_infeasible",
                        "release_order": order,
                        "released": [tuple_constraint(active[index]) for index in released],
                        "added": [tuple_constraint(inactive[index]) for index in new_indices],
                        "opening": np.asarray(vertex["opening"]).tolist(),
                        "signature": signature,
                        "exact": exact,
                    },
                )
                continue

            counters["accepted_distinct_graphs"] += 1
            score = float(exact["literal_verifier_score"])
            strict_root = cc.solve_targets(
                tolerance_root.values, new_active, pair_tolerance=0.0, max_evaluations=900
            )
            counters["total_nonlinear_evaluations"] += strict_root.evaluations
            strict_report = None
            if strict_root.success:
                counters["strict_roots"] += 1
                strict_payload, strict_exact = exact_payload(strict_root.values, evaluate)
                strict_report = {
                    "equation_score": cc.metrics(strict_root.values, 0.0)["score"],
                    "payload_score_under_live_verifier": (
                        strict_exact.get("literal_verifier_score") if strict_payload else None
                    ),
                    "residual": strict_root.residual,
                }
            if score > next_noncanonical_frontier + 1e-12:
                counters["noncanonical_better_than_next_frontier"] += 1

            record = {
                "event": "graph_accepted",
                "release_order": order,
                "vertex_index": vertex_index,
                "released_indices": list(released),
                "released": [tuple_constraint(active[index]) for index in released],
                "added": [tuple_constraint(inactive[index]) for index in new_indices],
                "opening": np.asarray(vertex["opening"]).tolist(),
                "linear_objective_opening": vertex["linear_objective_opening"],
                "signature": signature,
                "score": score,
                "margin_to_target": score - TARGET,
                "root_residual": tolerance_root.residual,
                "exact": exact,
                "strict": strict_report,
            }
            append_jsonl(events, record)
            if score > best_score:
                candidate_dir = run / "candidates" / signature[:16]
                candidate_path = candidate_dir / "candidate.json"
                atomic_json(candidate_path, payload)
                best_score = score
                best_payload_path = candidate_path
                best_record = {
                    **record,
                    "payload": str(candidate_path),
                    "payload_sha256": sha256_file(candidate_path),
                }
                atomic_json(run / "best_record.json", best_record)
                append_jsonl(events, {"event": "new_best", **best_record})

        counters["release_pairs_processed"] += 1
        if counters["release_pairs_processed"] % args.checkpoint_every == 0:
            atomic_json(
                run / "checkpoint.json",
                {
                    **counters,
                    "best_score": best_score,
                    "best_margin_to_target": best_score - TARGET,
                    "best": best_record,
                },
            )

    summary = {
        **config,
        **counters,
        "best_score": best_score,
        "best_margin_to_target": best_score - TARGET,
        "best": best_record,
        "gate_clearing": bool(best_score > TARGET),
        "classification": (
            "verifier-only" if best_record.get("exact", {}).get("pair_tolerance_only") else "physical-strict"
        ),
        "limitation": (
            "Exhaustive over configured active-contact release pairs and the visible "
            "vertices of each local two-dimensional linearized flex cone; not a global "
            "enumeration of all unlabeled 26-circle contact graphs."
        ),
    }
    atomic_json(run / "summary.json", summary)
    append_jsonl(events, {"event": "run_finished", **summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
