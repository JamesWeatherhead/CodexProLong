#!/usr/bin/env python3
"""Exhaustive two-contact pivots for 21-circle perimeter-four rectangles."""

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

import verifier_formula


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
CORE_PATH = CAMPAIGN / "geometry" / "rectangle_topology"
sys.path.insert(0, str(CORE_PATH))
import core  # noqa: E402


VERIFIER = verifier_formula.VERIFIER
VERIFIER_SHA256 = verifier_formula.VERIFIER_SHA256
LEADER = 2.365832385207997
MIN_IMPROVEMENT = 1e-10
TARGET = LEADER + MIN_IMPROVEMENT
LIVE_SCHEMA = {"circles": "array of 21 [x, y, r] triples"}


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
    return bool(circles.shape == (core.COUNT, 3) and np.isfinite(circles).all())


def tuple_constraint(item: core.Constraint) -> list[Any]:
    return [item[0], int(item[1]), item[2]]


def graph_hash(active: list[core.Constraint]) -> str:
    graph = nx.Graph()
    for index in range(core.COUNT):
        graph.add_node(f"C{index}", kind="circle")
    for wall in core.WALLS:
        graph.add_node(f"W{wall}", kind="wall")
    for kind, first, second in active:
        if kind == "P":
            graph.add_edge(f"C{first}", f"C{int(second)}")
        elif kind == "W":
            graph.add_edge(f"C{first}", f"W{second}")
    return nx.weisfeiler_lehman_graph_hash(graph, node_attr="kind", iterations=6)


def predicted_vertices(
    gaps: np.ndarray,
    derivatives: np.ndarray,
    angle_count: int,
    maximum_opening: float,
) -> list[dict[str, Any]]:
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

    visible = list(dict.fromkeys(int(index) for index in winners))
    pairs: set[tuple[int, int]] = set()
    previous = int(winners[0])
    for value in winners[1:]:
        current = int(value)
        if current != previous:
            pairs.add(tuple(sorted((previous, current))))
        previous = current
    if len(visible) <= 28:
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
            }
        )
    return vertices


def make_start(
    base: np.ndarray,
    active: list[core.Constraint],
    released: tuple[int, int],
    opening: np.ndarray,
) -> tuple[np.ndarray, int, float]:
    targets = np.zeros(core.VARIABLES)
    targets[released[0]], targets[released[1]] = opening
    solved = core.solve_targets(
        base,
        active,
        targets,
        pair_tolerance=core.PAIR_TOLERANCE,
        perimeter_tolerance=core.PERIMETER_TOLERANCE,
        max_evaluations=500,
    )
    if solved.success:
        return solved.values, solved.evaluations, solved.residual
    jacobian = core.constraint_jacobian(
        base, active, core.PAIR_TOLERANCE, core.PERIMETER_TOLERANCE
    )
    rhs = np.zeros(core.VARIABLES)
    rhs[released[0]], rhs[released[1]] = opening
    try:
        linear = base + np.linalg.solve(jacobian, rhs)
    except np.linalg.LinAlgError:
        linear = base.copy()
    return linear, solved.evaluations, solved.residual


def raw_overruns(circles: np.ndarray) -> tuple[float, float]:
    normalized, width, height = core.normalize_origin(circles)
    centers, radii = normalized[:, :2], normalized[:, 2]
    pair_overrun = max(
        float(
            radii[first]
            + radii[second]
            - np.linalg.norm(centers[first] - centers[second])
        )
        for first in range(core.COUNT)
        for second in range(first + 1, core.COUNT)
    )
    return max(0.0, pair_overrun), max(0.0, width + height - 2.0)


def exact_payload(values: np.ndarray, evaluate) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    try:
        buffered, nextafter_steps, screen = core.verifier_buffer(values)
    except RuntimeError as error:
        circles = core.values_to_circles(values)
        pair_overrun, perimeter_overrun = raw_overruns(circles)
        return None, {
            "schema_valid": True,
            "literal_verifier_accepted": False,
            "buffer_failure": str(error),
            "raw_maximum_pair_overrun": pair_overrun,
            "raw_maximum_perimeter_overrun": perimeter_overrun,
        }
    payload = {"circles": core.values_to_circles(buffered).tolist()}
    if not schema_valid(payload):
        return None, {"schema_valid": False}
    score = float(evaluate(payload))
    accepted = math.isfinite(score)
    pair_overrun, perimeter_overrun = raw_overruns(
        np.asarray(payload["circles"], dtype=np.float64)
    )
    tolerance_only = bool(pair_overrun > 2e-12 or perimeter_overrun > 2e-12)
    report = {
        "schema_valid": True,
        "literal_verifier_accepted": accepted,
        "literal_verifier_score": score if accepted else None,
        "nextafter_buffer_steps": nextafter_steps,
        "maximum_pair_overrun": pair_overrun,
        "maximum_perimeter_overrun": perimeter_overrun,
        "verifier_tolerance_only": tolerance_only,
        "physical_strict": not tolerance_only,
        "screen": screen,
    }
    return (payload if accepted else None), report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        type=Path,
        default=(
            CAMPAIGN
            / "geometry/runs/20260815T035100Z/circles-rectangle/candidate.json"
        ),
    )
    parser.add_argument("--stamp", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--release-pair-limit", type=int, default=2016)
    parser.add_argument("--angle-count", type=int, default=513)
    parser.add_argument("--maximum-opening", type=float, default=0.30)
    parser.add_argument("--maximum-vertices-per-release", type=int, default=16)
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
    circles = np.asarray(seed_record.get("circles"), dtype=np.float64)
    if circles.shape != (core.COUNT, 3) or not np.isfinite(circles).all():
        raise ValueError("seed must have 21 finite [x,y,r] rows")
    active = core.decode_active(circles, args.active_tolerance)
    if len(active) != core.VARIABLES:
        raise RuntimeError(f"expected 65 active constraints, decoded {len(active)}")
    perimeter_indices = [index for index, item in enumerate(active) if item[0] == "E"]
    if len(perimeter_indices) != 1:
        raise RuntimeError("seed has no unique active perimeter equality")
    perimeter_index = perimeter_indices[0]

    base_root = core.solve_targets(
        core.circles_to_values(circles),
        active,
        pair_tolerance=core.PAIR_TOLERANCE,
        perimeter_tolerance=core.PERIMETER_TOLERANCE,
    )
    if not base_root.success:
        raise RuntimeError(f"base root failed: {base_root.residual}")
    base = base_root.values
    base_payload, base_exact = exact_payload(base, evaluate)
    if base_payload is None:
        raise RuntimeError(f"base exact replay failed: {base_exact}")

    jacobian = core.constraint_jacobian(
        base, active, core.PAIR_TOLERANCE, core.PERIMETER_TOLERANCE
    )
    inverse = np.linalg.solve(jacobian, np.eye(core.VARIABLES))
    objective = np.zeros(core.VARIABLES)
    objective[core.RADIUS_START : core.WIDTH_ID] = 1.0
    multipliers = np.linalg.solve(jacobian.T, -objective)
    active_set = set(active)
    inactive = [item for item in core.ALL_CONSTRAINTS if item not in active_set]
    gaps = core.constraint_values(
        base, inactive, core.PAIR_TOLERANCE, core.PERIMETER_TOLERANCE
    )
    inactive_jacobian = core.constraint_jacobian(
        base, inactive, core.PAIR_TOLERANCE, core.PERIMETER_TOLERANCE
    )

    releasable = [index for index in range(core.VARIABLES) if index != perimeter_index]
    release_pairs = list(itertools.combinations(releasable, 2))
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
        "pair_tolerance": core.PAIR_TOLERANCE,
        "perimeter_tolerance": core.PERIMETER_TOLERANCE,
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

    base_score = float(base_exact["literal_verifier_score"])
    atomic_json(run / "best.json", base_payload)
    best_record: dict[str, Any] = {
        "source": "base",
        "score": base_score,
        "payload": str(run / "best.json"),
        "payload_sha256": sha256_file(run / "best.json"),
        "exact": base_exact,
    }
    best_changed_score = -math.inf
    best_changed_record: dict[str, Any] | None = None
    labeled_graphs: set[str] = set()
    wl_graphs: set[str] = set()
    counters = {
        "release_pairs_processed": 0,
        "linear_vertices": 0,
        "graphs_tested": 0,
        "duplicate_labeled_graphs": 0,
        "root_failures": 0,
        "infeasible_roots": 0,
        "accepted_labeled_graphs": 0,
        "strict_roots": 0,
        "total_nonlinear_evaluations": base_root.evaluations,
    }

    for release_order, released in enumerate(release_pairs):
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
            released_set = set(released)
            new_active = [
                item for index, item in enumerate(active) if index not in released_set
            ] + [inactive[new_indices[0]], inactive[new_indices[1]]]
            signature = core.canonical_signature(new_active)
            if signature in labeled_graphs:
                counters["duplicate_labeled_graphs"] += 1
                continue
            labeled_graphs.add(signature)
            counters["graphs_tested"] += 1

            start, start_evaluations, start_residual = make_start(
                base, active, released, np.asarray(vertex["opening"])
            )
            root = core.solve_targets(
                start,
                new_active,
                pair_tolerance=core.PAIR_TOLERANCE,
                perimeter_tolerance=core.PERIMETER_TOLERANCE,
                max_evaluations=800,
            )
            counters["total_nonlinear_evaluations"] += start_evaluations + root.evaluations
            if not root.success:
                counters["root_failures"] += 1
                append_jsonl(
                    events,
                    {
                        "event": "graph_root_failed",
                        "release_order": release_order,
                        "released": [tuple_constraint(active[index]) for index in released],
                        "added": [tuple_constraint(inactive[index]) for index in new_indices],
                        "opening": np.asarray(vertex["opening"]).tolist(),
                        "start_residual": start_residual,
                        "root_residual": root.residual,
                        "signature": signature,
                    },
                )
                continue

            payload, exact = exact_payload(root.values, evaluate)
            if payload is None:
                counters["infeasible_roots"] += 1
                continue
            counters["accepted_labeled_graphs"] += 1
            wl_signature = graph_hash(new_active)
            wl_graphs.add(wl_signature)
            score = float(exact["literal_verifier_score"])

            strict_root = core.solve_targets(
                root.values,
                new_active,
                pair_tolerance=0.0,
                perimeter_tolerance=0.0,
                max_evaluations=900,
            )
            counters["total_nonlinear_evaluations"] += strict_root.evaluations
            strict_report = None
            if strict_root.success:
                strict_payload, strict_exact = exact_payload(strict_root.values, evaluate)
                if strict_payload is not None:
                    counters["strict_roots"] += 1
                    strict_report = {
                        "equation_score": core.values_metrics(
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
                "released": [tuple_constraint(active[index]) for index in released],
                "added": [tuple_constraint(inactive[index]) for index in new_indices],
                "opening": np.asarray(vertex["opening"]).tolist(),
                "linear_objective_opening": vertex["linear_objective_opening"],
                "signature": signature,
                "wl_signature": wl_signature,
                "score": score,
                "margin_to_target": score - TARGET,
                "root_residual": root.residual,
                "exact": exact,
                "strict": strict_report,
            }
            append_jsonl(events, record)
            if score > best_changed_score:
                best_changed_score = score
                atomic_json(run / "best_changed.json", payload)
                best_changed_record = {
                    **record,
                    "payload": str(run / "best_changed.json"),
                    "payload_sha256": sha256_file(run / "best_changed.json"),
                }
                atomic_json(run / "best_changed_record.json", best_changed_record)
                append_jsonl(events, {**best_changed_record, "event": "new_best_changed"})
            if score > float(best_record["score"]):
                atomic_json(run / "best.json", payload)
                best_record = {
                    **record,
                    "payload": str(run / "best.json"),
                    "payload_sha256": sha256_file(run / "best.json"),
                }
                atomic_json(run / "best_record.json", best_record)
                append_jsonl(events, {**best_record, "event": "new_best"})

        counters["release_pairs_processed"] += 1
        if counters["release_pairs_processed"] % args.checkpoint_every == 0:
            atomic_json(
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
        "best_margin_to_target": float(best_record["score"]) - TARGET,
        "gate_clearing": bool(float(best_record["score"]) > TARGET),
        "classification": (
            "verifier-only"
            if best_record.get("exact", {}).get("verifier_tolerance_only")
            else "physical-strict"
        ),
        "limitation": (
            "Exhaustive over active-contact pairs and visible vertices of each local "
            "two-dimensional flex cone from this seed; not a global contact-graph enumeration."
        ),
    }
    atomic_json(run / "summary.json", summary)
    append_jsonl(events, {"event": "run_finished", **summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
