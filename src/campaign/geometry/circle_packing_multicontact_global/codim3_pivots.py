#!/usr/bin/env python3
"""Codimension-three contact-graph pivots for 26 circles in a square.

This lane begins strictly beyond the frozen codimension-two campaign.  It
opens three active equalities simultaneously, constructs the three-dimensional
linearized feasible polytope, and tests its genuine non-box vertices where
three previously inactive contacts become tight.  Each resulting 78-contact
graph is solved nonlinearly and replayed through the unchanged clean-room
mirror of the live verifier.

The finite search performed by one invocation is deliberately checkpointed
and fully described in its run manifest.  It is not a global enumeration of
all 26-circle contact graphs.
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

import networkx as nx
import numpy as np
from scipy.spatial import HalfspaceIntersection, QhullError


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
PRECISION = HERE.parent / "circle_packing_multicontact_precision"
sys.path.insert(0, str(PRECISION))
import codim2_pivots as c2  # noqa: E402


WALL_IDS = {"L": 26, "R": 27, "B": 28, "T": 29}
LITERATURE_PINS = [
    {
        "paperclip_path": "/papers/arx_1701.00541/content.lines",
        "lines": "19,22,47,84-97,123-126",
        "use": "active-inequality/contact-system and Newton refinement grounding",
    },
    {
        "paperclip_path": "/papers/arx_2511.02864/content.lines",
        "lines": "513-516",
        "use": "published circle-packing computational context",
    },
]


def graph_hash(active: list[c2.cc.Constraint]) -> str:
    """Return a relabeling-insensitive contact-graph fingerprint."""
    graph = nx.Graph()
    for index in range(c2.cc.COUNT):
        graph.add_node(index, label="circle")
    for index in range(26, 30):
        graph.add_node(index, label="wall")
    for first, second in ((26, 28), (28, 27), (27, 29), (29, 26)):
        graph.add_edge(first, second, kind="frame")
    for kind, first, second in active:
        if kind == "P":
            graph.add_edge(first, int(second), kind="contact")
        else:
            graph.add_edge(first, WALL_IDS[str(second)], kind="contact")
    wl = nx.weisfeiler_lehman_graph_hash(
        graph, node_attr="label", edge_attr="kind", iterations=8
    )
    invariant = [wl, sorted(dict(graph.degree()).values()), graph.number_of_edges()]
    return hashlib.sha256(
        json.dumps(invariant, separators=(",", ":")).encode()
    ).hexdigest()


def polytope_vertices(
    gaps: np.ndarray,
    derivatives: np.ndarray,
    maximum_opening: float,
) -> tuple[list[dict[str, Any]], dict[str, int | float | str | None]]:
    """Enumerate genuine three-inactive-contact vertices of a 3-D flex cone.

    ``gaps + derivatives @ opening >= 0`` are the exact linearized inactive
    inequalities.  A temporary upper box bounds the half-space intersection;
    every vertex touching that artificial box is discarded.
    """
    if derivatives.ndim != 2 or derivatives.shape[1] != 3:
        raise ValueError("derivatives must have shape (constraints, 3)")
    inactive_halfspaces = np.column_stack((-derivatives, -gaps))
    lower = np.column_stack((-np.eye(3), np.zeros(3)))
    upper = np.column_stack((np.eye(3), -maximum_opening * np.ones(3)))
    halfspaces = np.vstack((inactive_halfspaces, lower, upper))

    # The base point is feasible but lies on the three artificial lower
    # bounds.  Move equally into the positive orthant until a strict interior
    # point is found; convergence to zero is safe because every inactive gap
    # is strictly positive after the active set has been decoded.
    epsilon = min(1e-9, maximum_opening * 1e-6)
    interior = np.full(3, epsilon)
    while np.max(halfspaces[:, :3] @ interior + halfspaces[:, 3]) >= -1e-13:
        epsilon *= 0.1
        interior[:] = epsilon
        if epsilon < 1e-16:
            return [], {
                "status": "no_strict_interior",
                "intersection_count": 0,
                "degenerate_tight_triples": 0,
                "minimum_inactive_gap": float(np.min(gaps)),
            }

    try:
        intersections = HalfspaceIntersection(halfspaces, interior).intersections
    except (QhullError, ValueError, FloatingPointError) as error:
        return [], {
            "status": f"qhull_failure:{type(error).__name__}",
            "intersection_count": 0,
            "degenerate_tight_triples": 0,
            "minimum_inactive_gap": float(np.min(gaps)),
        }

    seen: set[tuple[int, int, int]] = set()
    result: list[dict[str, Any]] = []
    degenerate = 0
    rejected_box = 0
    rejected_feasibility = 0
    for opening in intersections:
        if not np.isfinite(opening).all() or np.min(opening) <= 2e-8:
            rejected_box += 1
            continue
        if np.max(opening) >= maximum_opening - 2e-8:
            rejected_box += 1
            continue
        slacks = gaps + derivatives @ opening
        minimum = float(np.min(slacks))
        feasibility_tolerance = max(2e-7, 2e-5 * float(np.max(opening)))
        if minimum < -feasibility_tolerance:
            rejected_feasibility += 1
            continue
        tight_tolerance = max(2e-8, 2e-6 * float(np.max(opening)))
        tight = np.flatnonzero(np.abs(slacks) <= tight_tolerance).tolist()
        if len(tight) < 3:
            tight = np.argsort(np.abs(slacks))[:3].tolist()
        for selected in itertools.combinations(tight, 3):
            key = tuple(sorted(int(value) for value in selected))
            if key in seen:
                continue
            matrix = derivatives[list(key)]
            determinant = float(np.linalg.det(matrix))
            if abs(determinant) <= 1e-11:
                degenerate += 1
                continue
            reconstructed = np.linalg.solve(matrix, -gaps[list(key)])
            if np.linalg.norm(reconstructed - opening, ord=np.inf) > max(
                1e-7, 2e-5 * float(np.max(opening))
            ):
                continue
            reconstructed_slacks = gaps + derivatives @ reconstructed
            if float(np.min(reconstructed_slacks)) < -feasibility_tolerance:
                rejected_feasibility += 1
                continue
            seen.add(key)
            result.append(
                {
                    "new_indices": list(key),
                    "opening": reconstructed,
                    "linear_minimum_slack": float(np.min(reconstructed_slacks)),
                    "activation_determinant": determinant,
                }
            )
    return result, {
        "status": "ok",
        "intersection_count": int(len(intersections)),
        "degenerate_tight_triples": degenerate,
        "rejected_box_vertices": rejected_box,
        "rejected_feasibility": rejected_feasibility,
        "minimum_inactive_gap": float(np.min(gaps)),
    }


def make_start(
    base: np.ndarray,
    active: list[c2.cc.Constraint],
    released: tuple[int, int, int],
    opening: np.ndarray,
) -> tuple[np.ndarray, int, float]:
    targets = np.zeros(c2.cc.VARIABLES)
    targets[list(released)] = opening
    solved = c2.cc.solve_targets(base, active, targets, max_evaluations=550)
    if solved.success:
        return solved.values, solved.evaluations, solved.residual

    jacobian = c2.cc.constraint_jacobian(base, active, c2.cc.PAIR_TOLERANCE)
    rhs = np.zeros(c2.cc.VARIABLES)
    rhs[list(released)] = opening
    try:
        linear = base + np.linalg.solve(jacobian, rhs)
    except np.linalg.LinAlgError:
        linear = base.copy()
    return linear, solved.evaluations, solved.residual


def selected_triples(
    multipliers: np.ndarray,
    offset: int,
    limit: int,
    selection: str,
) -> tuple[list[tuple[int, int, int]], int]:
    triples = list(itertools.combinations(range(c2.cc.VARIABLES), 3))
    triples.sort(key=lambda triple: (sum(float(multipliers[i]) for i in triple), triple))
    total = len(triples)
    if selection == "pain":
        return triples[offset : offset + limit], total
    if selection == "stratified":
        available = triples[offset:]
        if limit >= len(available):
            return available, total
        # Deterministic whole-spectrum screen, retaining both extremal ends.
        indices = np.linspace(0, len(available) - 1, limit, dtype=int)
        return [available[int(index)] for index in indices], total
    raise ValueError(f"unknown selection: {selection}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        type=Path,
        default=CAMPAIGN / "geometry/runs/20260815T035000Z/circle-packing/candidate.json",
    )
    parser.add_argument("--stamp", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--release-triple-offset", type=int, default=0)
    parser.add_argument("--release-triple-limit", type=int, default=500)
    parser.add_argument("--selection", choices=("pain", "stratified"), default="pain")
    parser.add_argument("--maximum-opening", type=float, default=0.35)
    parser.add_argument("--maximum-vertices-per-release", type=int, default=16)
    parser.add_argument("--active-tolerance", type=float, default=1e-6)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.release_triple_offset < 0 or args.release_triple_limit <= 0:
        raise ValueError("triple offset must be nonnegative and limit positive")
    if not 0 < args.maximum_opening < 1:
        raise ValueError("maximum opening must lie in (0,1)")

    run = HERE / "runs" / args.stamp
    run.mkdir(parents=True, exist_ok=False)
    events = run / "events.jsonl"
    evaluate = c2.load_verifier()

    seed_path = args.seed.resolve()
    seed_record = json.loads(seed_path.read_text())
    circles = np.asarray(seed_record.get("circles"), dtype=np.float64)
    if circles.shape != (c2.cc.COUNT, 3) or not np.isfinite(circles).all():
        raise ValueError("seed must have 26 finite [x,y,r] rows")
    active = c2.cc.decode_active(circles, args.active_tolerance)
    if len(active) != c2.cc.VARIABLES:
        raise RuntimeError(f"expected 78 active contacts, decoded {len(active)}")

    base_root = c2.cc.solve_targets(c2.cc.circles_to_values(circles), active)
    if not base_root.success:
        raise RuntimeError(f"base root failed: {base_root.residual}")
    base = base_root.values
    base_payload, base_exact = c2.exact_payload(base, evaluate)
    if base_payload is None:
        raise RuntimeError(f"base replay failed: {base_exact}")

    jacobian = c2.cc.constraint_jacobian(base, active, c2.cc.PAIR_TOLERANCE)
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    inverse = np.linalg.solve(jacobian, np.eye(c2.cc.VARIABLES))
    objective = np.zeros(c2.cc.VARIABLES)
    objective[2 * c2.cc.COUNT :] = 1.0
    multipliers = np.linalg.solve(jacobian.T, -objective)
    inactive = c2.cc.inactive_constraints(active)
    gaps = c2.cc.constraint_values(base, inactive, c2.cc.PAIR_TOLERANCE)
    inactive_jacobian = c2.cc.constraint_jacobian(base, inactive, c2.cc.PAIR_TOLERANCE)
    if float(np.min(gaps)) <= 0:
        raise RuntimeError("decoded inactive set is not strictly slack")

    release_triples, total_release_triples = selected_triples(
        multipliers,
        args.release_triple_offset,
        args.release_triple_limit,
        args.selection,
    )
    source_path = Path(__file__).resolve()
    config = {
        "stamp": args.stamp,
        "dimension": 3,
        "method": "three-active-release/three-inactive-activation half-space vertices",
        "non_overlap": (
            "No one-contact continuation, two-contact release, 513-direction 2-D sweep, "
            "weak-contact polish, or fixed-graph tolerance optimization is performed."
        ),
        "source": str(source_path),
        "source_sha256": c2.sha256_file(source_path),
        "seed": str(seed_path),
        "seed_sha256": c2.sha256_file(seed_path),
        "verifier": str(c2.VERIFIER),
        "verifier_sha256": c2.VERIFIER_SHA256,
        "live_solution_schema": c2.LIVE_SCHEMA,
        "leader": c2.LEADER,
        "min_improvement": c2.MIN_IMPROVEMENT,
        "target_strictly_above": c2.TARGET,
        "pair_tolerance": c2.cc.PAIR_TOLERANCE,
        "wall_tolerance": 0.0,
        "base_jacobian_smallest_singular_value": float(singular_values[-1]),
        "base_jacobian_condition_number": float(singular_values[0] / singular_values[-1]),
        "total_possible_release_triples": total_release_triples,
        "release_triple_offset": args.release_triple_offset,
        "release_triple_count": len(release_triples),
        "selection": args.selection,
        "maximum_opening": args.maximum_opening,
        "maximum_vertices_per_release": args.maximum_vertices_per_release,
        "base": base_exact,
        "base_active": [c2.tuple_constraint(item) for item in active],
        "base_multipliers": multipliers.tolist(),
        "literature_pins": LITERATURE_PINS,
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
        "linear_intersections": 0,
        "linear_vertices": 0,
        "degenerate_tight_triples": 0,
        "empty_or_failed_polytopes": 0,
        "graphs_tested": 0,
        "duplicate_labeled_graphs": 0,
        "rank_deficient_graphs": 0,
        "root_failures": 0,
        "infeasible_roots": 0,
        "accepted_labeled_graphs": 0,
        "strict_roots": 0,
        "total_nonlinear_evaluations": base_root.evaluations,
    }

    for release_order, released in enumerate(release_triples):
        derivative = inactive_jacobian @ inverse[:, released]
        vertices, polytope = polytope_vertices(gaps, derivative, args.maximum_opening)
        counters["linear_intersections"] += int(polytope["intersection_count"])
        counters["degenerate_tight_triples"] += int(polytope["degenerate_tight_triples"])
        if not vertices:
            counters["empty_or_failed_polytopes"] += 1
        for vertex in vertices:
            vertex["linear_objective_opening"] = float(
                objective @ inverse[:, released] @ vertex["opening"]
            )
        vertices.sort(
            key=lambda item: (
                -float(item["linear_objective_opening"]),
                float(np.max(item["opening"])),
                tuple(item["new_indices"]),
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
            signature = c2.cc.canonical_signature(new_active)
            if signature in labeled_graphs:
                counters["duplicate_labeled_graphs"] += 1
                continue
            labeled_graphs.add(signature)
            counters["graphs_tested"] += 1

            new_jacobian = c2.cc.constraint_jacobian(base, new_active, c2.cc.PAIR_TOLERANCE)
            new_singular_values = np.linalg.svd(new_jacobian, compute_uv=False)
            if new_singular_values[-1] <= 1e-11:
                counters["rank_deficient_graphs"] += 1
                c2.append_jsonl(
                    events,
                    {
                        "event": "rank_deficient_graph",
                        "release_order": release_order,
                        "released_indices": list(released),
                        "released": [c2.tuple_constraint(active[index]) for index in released],
                        "added": [c2.tuple_constraint(inactive[index]) for index in new_indices],
                        "opening": np.asarray(vertex["opening"]).tolist(),
                        "signature": signature,
                        "smallest_singular_value_at_base": float(new_singular_values[-1]),
                    },
                )
                continue

            start, start_evaluations, start_residual = make_start(
                base, active, released, np.asarray(vertex["opening"])
            )
            root = c2.cc.solve_targets(
                start, new_active, pair_tolerance=c2.cc.PAIR_TOLERANCE, max_evaluations=1000
            )
            counters["total_nonlinear_evaluations"] += start_evaluations + root.evaluations
            if not root.success:
                counters["root_failures"] += 1
                c2.append_jsonl(
                    events,
                    {
                        "event": "graph_root_failed",
                        "release_order": release_order,
                        "vertex_index": vertex_index,
                        "released": [c2.tuple_constraint(active[index]) for index in released],
                        "added": [c2.tuple_constraint(inactive[index]) for index in new_indices],
                        "opening": np.asarray(vertex["opening"]).tolist(),
                        "start_residual": start_residual,
                        "root_residual": root.residual,
                        "signature": signature,
                    },
                )
                continue

            payload, exact = c2.exact_payload(root.values, evaluate)
            if payload is None:
                counters["infeasible_roots"] += 1
                c2.append_jsonl(
                    events,
                    {
                        "event": "graph_infeasible",
                        "release_order": release_order,
                        "vertex_index": vertex_index,
                        "signature": signature,
                        "exact": exact,
                    },
                )
                continue

            counters["accepted_labeled_graphs"] += 1
            wl_signature = graph_hash(new_active)
            wl_graphs.add(wl_signature)
            score = float(exact["literal_verifier_score"])
            strict_root = c2.cc.solve_targets(
                root.values, new_active, pair_tolerance=0.0, max_evaluations=1200
            )
            counters["total_nonlinear_evaluations"] += strict_root.evaluations
            strict_report = None
            if strict_root.success:
                strict_payload, strict_exact = c2.exact_payload(strict_root.values, evaluate)
                if strict_payload is not None:
                    counters["strict_roots"] += 1
                    strict_report = {
                        "equation_score": c2.cc.metrics(strict_root.values, 0.0)["score"],
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
                "activation_determinant": vertex["activation_determinant"],
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
            if best_record.get("exact", {}).get("pair_tolerance_only")
            else "physical-strict"
        ),
        "limitation": (
            "Finite codimension-three screen over the configured release-triple slice and "
            "at most the configured number of objective-ranked non-box vertices per release. "
            "It is not a global contact-graph enumeration."
        ),
    }
    c2.atomic_json(run / "summary.json", summary)
    c2.append_jsonl(events, {"event": "run_finished", **summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["gate_clearing"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
