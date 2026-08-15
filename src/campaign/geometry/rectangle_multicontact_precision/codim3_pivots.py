#!/usr/bin/env python3
"""Codimension-three active-contact pivots for rectangle circle packing."""

from __future__ import annotations

import argparse
import itertools
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.spatial import HalfspaceIntersection, QhullError

import codim2_pivots as c2


def polytope_vertices(
    gaps: np.ndarray,
    derivatives: np.ndarray,
    maximum_opening: float,
) -> list[dict[str, Any]]:
    """Enumerate genuine three-inactive-contact vertices of the 3-D flex polytope."""
    # scipy uses a.x + b <= 0.  The inactive feasibility inequalities are
    # gaps + derivatives @ opening >= 0.  A finite upper box is included only
    # to make the polytope bounded; vertices touching it are discarded.
    inactive_halfspaces = np.column_stack((-derivatives, -gaps))
    lower = np.column_stack((-np.eye(3), np.zeros(3)))
    upper = np.column_stack((np.eye(3), -maximum_opening * np.ones(3)))
    halfspaces = np.vstack((inactive_halfspaces, lower, upper))

    epsilon = min(1e-9, maximum_opening * 1e-6)
    interior = np.full(3, epsilon)
    while np.max(halfspaces[:, :3] @ interior + halfspaces[:, 3]) >= -1e-13:
        epsilon *= 0.1
        interior[:] = epsilon
        if epsilon < 1e-16:
            return []
    try:
        intersections = HalfspaceIntersection(halfspaces, interior).intersections
    except (QhullError, ValueError, FloatingPointError):
        return []

    seen: set[tuple[int, int, int]] = set()
    result: list[dict[str, Any]] = []
    for opening in intersections:
        if not np.isfinite(opening).all():
            continue
        if np.min(opening) <= 2e-8:
            continue
        if np.max(opening) >= maximum_opening - 2e-8:
            continue
        slacks = gaps + derivatives @ opening
        minimum = float(np.min(slacks))
        if minimum < -max(2e-7, 2e-5 * float(np.max(opening))):
            continue
        tight_tolerance = max(2e-8, 2e-6 * float(np.max(opening)))
        tight = np.flatnonzero(np.abs(slacks) <= tight_tolerance).tolist()
        if len(tight) < 3:
            tight = np.argsort(np.abs(slacks))[:3].tolist()
        for selected in itertools.combinations(tight, 3):
            selected_tuple = tuple(sorted(int(value) for value in selected))
            if selected_tuple in seen:
                continue
            matrix = derivatives[list(selected_tuple)]
            if abs(float(np.linalg.det(matrix))) <= 1e-11:
                continue
            reconstructed = np.linalg.solve(matrix, -gaps[list(selected_tuple)])
            if np.linalg.norm(reconstructed - opening, ord=np.inf) > max(
                1e-7, 2e-5 * float(np.max(opening))
            ):
                continue
            seen.add(selected_tuple)
            result.append(
                {
                    "new_indices": list(selected_tuple),
                    "opening": reconstructed,
                    "linear_minimum_slack": minimum,
                }
            )
    return result


def make_start(
    base: np.ndarray,
    active: list[c2.core.Constraint],
    released: tuple[int, int, int],
    opening: np.ndarray,
) -> tuple[np.ndarray, int, float]:
    targets = np.zeros(c2.core.VARIABLES)
    targets[list(released)] = opening
    solved = c2.core.solve_targets(
        base,
        active,
        targets,
        pair_tolerance=c2.core.PAIR_TOLERANCE,
        perimeter_tolerance=c2.core.PERIMETER_TOLERANCE,
        max_evaluations=550,
    )
    if solved.success:
        return solved.values, solved.evaluations, solved.residual
    jacobian = c2.core.constraint_jacobian(
        base, active, c2.core.PAIR_TOLERANCE, c2.core.PERIMETER_TOLERANCE
    )
    rhs = np.zeros(c2.core.VARIABLES)
    rhs[list(released)] = opening
    try:
        linear = base + np.linalg.solve(jacobian, rhs)
    except np.linalg.LinAlgError:
        linear = base.copy()
    return linear, solved.evaluations, solved.residual


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        type=Path,
        default=(
            c2.CAMPAIGN
            / "geometry/runs/20260815T035100Z/circles-rectangle/candidate.json"
        ),
    )
    parser.add_argument("--stamp", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--release-triple-limit", type=int, default=41664)
    parser.add_argument("--maximum-opening", type=float, default=0.30)
    parser.add_argument("--maximum-vertices-per-release", type=int, default=12)
    parser.add_argument("--active-tolerance", type=float, default=1e-6)
    parser.add_argument("--checkpoint-every", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run = c2.HERE / "runs" / args.stamp
    run.mkdir(parents=True, exist_ok=False)
    events = run / "events.jsonl"
    evaluate = c2.load_verifier()

    seed_record = json.loads(args.seed.resolve().read_text())
    circles = np.asarray(seed_record.get("circles"), dtype=np.float64)
    if circles.shape != (c2.core.COUNT, 3) or not np.isfinite(circles).all():
        raise ValueError("seed must have 21 finite [x,y,r] rows")
    active = c2.core.decode_active(circles, args.active_tolerance)
    if len(active) != c2.core.VARIABLES:
        raise RuntimeError(f"expected 65 active constraints, decoded {len(active)}")
    perimeter_indices = [index for index, item in enumerate(active) if item[0] == "E"]
    if len(perimeter_indices) != 1:
        raise RuntimeError("seed has no unique active perimeter equality")
    perimeter_index = perimeter_indices[0]

    base_root = c2.core.solve_targets(
        c2.core.circles_to_values(circles),
        active,
        pair_tolerance=c2.core.PAIR_TOLERANCE,
        perimeter_tolerance=c2.core.PERIMETER_TOLERANCE,
    )
    if not base_root.success:
        raise RuntimeError(f"base root failed: {base_root.residual}")
    base = base_root.values
    base_payload, base_exact = c2.exact_payload(base, evaluate)
    if base_payload is None:
        raise RuntimeError(f"base replay failed: {base_exact}")

    jacobian = c2.core.constraint_jacobian(
        base, active, c2.core.PAIR_TOLERANCE, c2.core.PERIMETER_TOLERANCE
    )
    inverse = np.linalg.solve(jacobian, np.eye(c2.core.VARIABLES))
    objective = np.zeros(c2.core.VARIABLES)
    objective[c2.core.RADIUS_START : c2.core.WIDTH_ID] = 1.0
    multipliers = np.linalg.solve(jacobian.T, -objective)
    active_set = set(active)
    inactive = [item for item in c2.core.ALL_CONSTRAINTS if item not in active_set]
    gaps = c2.core.constraint_values(
        base, inactive, c2.core.PAIR_TOLERANCE, c2.core.PERIMETER_TOLERANCE
    )
    inactive_jacobian = c2.core.constraint_jacobian(
        base, inactive, c2.core.PAIR_TOLERANCE, c2.core.PERIMETER_TOLERANCE
    )

    releasable = [index for index in range(c2.core.VARIABLES) if index != perimeter_index]
    release_triples = list(itertools.combinations(releasable, 3))
    release_triples.sort(
        key=lambda triple: (sum(float(multipliers[index]) for index in triple), triple)
    )
    release_triples = release_triples[: args.release_triple_limit]
    config = {
        "stamp": args.stamp,
        "dimension": 3,
        "seed": str(args.seed.resolve()),
        "seed_sha256": c2.sha256_file(args.seed.resolve()),
        "verifier": str(c2.VERIFIER),
        "verifier_sha256": c2.VERIFIER_SHA256,
        "live_solution_schema": c2.LIVE_SCHEMA,
        "leader": c2.LEADER,
        "min_improvement": c2.MIN_IMPROVEMENT,
        "target_strictly_above": c2.TARGET,
        "pair_tolerance": c2.core.PAIR_TOLERANCE,
        "perimeter_tolerance": c2.core.PERIMETER_TOLERANCE,
        "release_triple_count": len(release_triples),
        "maximum_opening": args.maximum_opening,
        "maximum_vertices_per_release": args.maximum_vertices_per_release,
        "base": base_exact,
        "base_active": [c2.tuple_constraint(item) for item in active],
        "base_multipliers": multipliers.tolist(),
    }
    c2.atomic_json(run / "config.json", config)
    c2.append_jsonl(events, {"event": "run_started", **config})

    base_score = float(base_exact["literal_verifier_score"])
    c2.atomic_json(run / "best.json", base_payload)
    best_record: dict[str, Any] = {
        "source": "base",
        "score": base_score,
        "payload": str(run / "best.json"),
        "payload_sha256": c2.sha256_file(run / "best.json"),
        "exact": base_exact,
    }
    best_changed_score = -math.inf
    best_changed_record: dict[str, Any] | None = None
    labeled_graphs: set[str] = set()
    wl_graphs: set[str] = set()
    counters = {
        "release_triples_processed": 0,
        "linear_vertices": 0,
        "graphs_tested": 0,
        "duplicate_labeled_graphs": 0,
        "qhull_empty_or_failed": 0,
        "root_failures": 0,
        "infeasible_roots": 0,
        "accepted_labeled_graphs": 0,
        "strict_roots": 0,
        "total_nonlinear_evaluations": base_root.evaluations,
    }

    for release_order, released in enumerate(release_triples):
        derivative = inactive_jacobian @ inverse[:, released]
        vertices = polytope_vertices(gaps, derivative, args.maximum_opening)
        if not vertices:
            counters["qhull_empty_or_failed"] += 1
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
            released_set = set(released)
            new_active = [
                item for index, item in enumerate(active) if index not in released_set
            ] + [inactive[index] for index in new_indices]
            signature = c2.core.canonical_signature(new_active)
            if signature in labeled_graphs:
                counters["duplicate_labeled_graphs"] += 1
                continue
            labeled_graphs.add(signature)
            counters["graphs_tested"] += 1

            start, start_evaluations, start_residual = make_start(
                base, active, released, np.asarray(vertex["opening"])
            )
            root = c2.core.solve_targets(
                start,
                new_active,
                pair_tolerance=c2.core.PAIR_TOLERANCE,
                perimeter_tolerance=c2.core.PERIMETER_TOLERANCE,
                max_evaluations=900,
            )
            counters["total_nonlinear_evaluations"] += start_evaluations + root.evaluations
            if not root.success:
                counters["root_failures"] += 1
                continue
            payload, exact = c2.exact_payload(root.values, evaluate)
            if payload is None:
                counters["infeasible_roots"] += 1
                continue

            counters["accepted_labeled_graphs"] += 1
            wl_signature = c2.graph_hash(new_active)
            wl_graphs.add(wl_signature)
            score = float(exact["literal_verifier_score"])
            strict_root = c2.core.solve_targets(
                root.values,
                new_active,
                pair_tolerance=0.0,
                perimeter_tolerance=0.0,
                max_evaluations=1000,
            )
            counters["total_nonlinear_evaluations"] += strict_root.evaluations
            strict_report = None
            if strict_root.success:
                strict_payload, strict_exact = c2.exact_payload(strict_root.values, evaluate)
                if strict_payload is not None:
                    counters["strict_roots"] += 1
                    strict_report = {
                        "equation_score": c2.core.values_metrics(
                            strict_root.values, 0.0, 0.0
                        )["score"],
                        "live_verifier_score": strict_exact["literal_verifier_score"],
                        "residual": strict_root.residual,
                        "exact": strict_exact,
                    }
            record = {
                "event": "graph_accepted",
                "release_order": release_order,
                "vertex_index": vertex_index,
                "released_indices": list(released),
                "released": [c2.tuple_constraint(active[index]) for index in released],
                "added": [c2.tuple_constraint(inactive[index]) for index in new_indices],
                "opening": np.asarray(vertex["opening"]).tolist(),
                "linear_objective_opening": vertex["linear_objective_opening"],
                "signature": signature,
                "wl_signature": wl_signature,
                "score": score,
                "margin_to_target": score - c2.TARGET,
                "root_residual": root.residual,
                "exact": exact,
                "strict": strict_report,
            }
            c2.append_jsonl(events, record)
            if score > best_changed_score:
                best_changed_score = score
                c2.atomic_json(run / "best_changed.json", payload)
                best_changed_record = {
                    **record,
                    "payload": str(run / "best_changed.json"),
                    "payload_sha256": c2.sha256_file(run / "best_changed.json"),
                }
                c2.atomic_json(run / "best_changed_record.json", best_changed_record)
                c2.append_jsonl(events, {**best_changed_record, "event": "new_best_changed"})
            if score > float(best_record["score"]):
                c2.atomic_json(run / "best.json", payload)
                best_record = {
                    **record,
                    "payload": str(run / "best.json"),
                    "payload_sha256": c2.sha256_file(run / "best.json"),
                }
                c2.atomic_json(run / "best_record.json", best_record)
                c2.append_jsonl(events, {**best_record, "event": "new_best"})

        counters["release_triples_processed"] += 1
        if counters["release_triples_processed"] % args.checkpoint_every == 0:
            c2.atomic_json(
                run / "checkpoint.json",
                {
                    **counters,
                    "unlabeled_wl_graph_classes": len(wl_graphs),
                    "best": best_record,
                    "best_changed": best_changed_record,
                },
            )

    summary = {
        **config,
        **counters,
        "unlabeled_wl_graph_classes": len(wl_graphs),
        "best": best_record,
        "best_changed": best_changed_record,
        "best_score": float(best_record["score"]),
        "best_margin_to_target": float(best_record["score"]) - c2.TARGET,
        "gate_clearing": bool(float(best_record["score"]) > c2.TARGET),
        "classification": (
            "verifier-only"
            if best_record.get("exact", {}).get("verifier_tolerance_only")
            else "physical-strict"
        ),
        "limitation": (
            "Exhaustive over configured active-contact triples and every non-box "
            "vertex returned by 3-D half-space intersection from this seed."
        ),
    }
    c2.atomic_json(run / "summary.json", summary)
    c2.append_jsonl(events, {"event": "run_finished", **summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
