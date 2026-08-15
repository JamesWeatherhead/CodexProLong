#!/usr/bin/env python3
"""Bounded global search over omitted Razborov transition nodes.

The incumbent spends one row on every non-smooth transition of the exact
minimum-triangle curve.  This program removes coordinated subsets of those 17
internal transition rows, reallocates all freed rows globally, and optimizes
the resulting multi-scallop blocks.  It screens all 2^17-1 masks and refines a
deterministic mix of the best additive masks, every contiguous removal block,
and stratified random masks.

The code is clean-room and does not import or execute the downloaded verifier.
Candidates are replayed separately with the offline controller.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import itertools
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize

from audit_corpus import analyze
from optimize import (
    EXPECTED_LEADER_ID,
    EXPECTED_LEADER_SCORE,
    EXPECTED_VERIFIER_SHA256,
    LIVE,
    canonical,
    curve,
    optimize_interval,
    padded,
    weights_for_interior,
)


ROOT = Path(__file__).resolve().parent
BRANCHES = tuple(range(3, 21))
TRANSITIONS = tuple(range(3, 20))
BASE_INTERIOR = 472


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True).encode())
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        **event,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def allocations(costs: dict[int, list[float]]) -> dict[int, dict[int, int]]:
    marginals = []
    for r in BRANCHES:
        for count in range(1, BASE_INTERIOR + len(TRANSITIONS) + 1):
            marginals.append((costs[r][count - 1] - costs[r][count], r, count))
    marginals.sort(reverse=True)
    output = {}
    for removed_count in range(len(TRANSITIONS) + 1):
        counts = {r: 0 for r in BRANCHES}
        for _, r, count in marginals[: BASE_INTERIOR + removed_count]:
            if count != counts[r] + 1:
                raise RuntimeError("marginal allocation lost its prefix property")
            counts[r] = count
        output[removed_count] = counts
    return output


def branch_values(x: np.ndarray, r: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return curve(x, r)


def edge_cost(x0: float, y0: float, x1: float, y1: float) -> float:
    return y1 * (x1 - x0) - (y1 - y0) ** 2 / 6.0


def fixed_mesh_penalties(counts: dict[int, int]) -> tuple[float, dict[int, float]]:
    full = sum(optimize_interval(r, counts[r]).cost for r in BRANCHES)
    penalty = {}
    for r in TRANSITIONS:
        left_nodes = optimize_interval(r, counts[r]).nodes
        right_nodes = optimize_interval(r + 1, counts[r + 1]).nodes
        left_x = float(left_nodes[-1])
        kink_x = 1.0 - 1.0 / r
        right_x = float(right_nodes[0])
        left_y = float(curve(np.array([left_x]), r)[0][0])
        kink_y = float(curve(np.array([kink_x]), r)[0][0])
        right_y = float(curve(np.array([right_x]), r + 1)[0][0])
        penalty[r] = (
            edge_cost(left_x, left_y, right_x, right_y)
            - edge_cost(left_x, left_y, kink_x, kink_y)
            - edge_cost(kink_x, kink_y, right_x, right_y)
        )
    return full, penalty


def partition(removed: frozenset[int]) -> list[tuple[int, int]]:
    blocks = []
    start = 3
    for transition in TRANSITIONS:
        if transition not in removed:
            blocks.append((start, transition))
            start = transition + 1
    blocks.append((start, 20))
    return blocks


def sorted_groups(
    values: np.ndarray, groups: list[np.ndarray]
) -> tuple[np.ndarray, list[np.ndarray]]:
    sorted_values = values.copy()
    orders = []
    for indices in groups:
        order = np.argsort(values[indices])
        sorted_values[indices] = values[indices][order]
        orders.append(order)
    return sorted_values, orders


def optimize_block(
    first: int,
    last: int,
    counts: dict[int, int],
    exclusion: float,
    starts: int,
    rng_seed: int,
) -> dict[str, Any]:
    if first == last:
        optimum = optimize_interval(first, counts[first])
        return {
            "cost": optimum.cost,
            "iterations": optimum.iterations,
            "minimum_omitted_transition_distance": math.inf,
            "nodes": {str(first): optimum.nodes.tolist()},
            "status": "single_scallop_exact",
        }

    branches = np.concatenate(
        [np.full(counts[r], r, dtype=np.int64) for r in range(first, last + 1)]
    )
    initial = np.concatenate(
        [optimize_interval(r, counts[r]).nodes for r in range(first, last + 1)]
    )
    groups = [np.where(branches == r)[0] for r in range(first, last + 1)]
    lower = np.array([1.0 - 1.0 / (r - 1) for r in branches])
    upper = np.array([1.0 - 1.0 / r for r in branches])
    for r in range(first, last):
        upper[branches == r] -= exclusion
        lower[branches == r + 1] += exclusion
    lower += 1e-14
    upper -= 1e-14
    left_x = 1.0 - 1.0 / (first - 1)
    right_x = 1.0 - 1.0 / last
    left_y = float(curve(np.array([left_x]), first)[0][0])
    right_y = float(curve(np.array([right_x]), last)[0][0])

    def objective_gradient(raw: np.ndarray, scale: float = 1.0) -> tuple[float, np.ndarray]:
        x, orders = sorted_groups(raw, groups)
        y = np.empty(len(x), dtype=np.float64)
        derivative = np.empty(len(x), dtype=np.float64)
        for r, indices in zip(range(first, last + 1), groups, strict=True):
            y[indices], derivative[indices], _ = branch_values(x[indices], r)
        all_x = np.r_[left_x, x, right_x]
        all_y = np.r_[left_y, y, right_y]
        bracket = (
            all_x[1:-1]
            - all_x[:-2]
            + (all_y[2:] - 2.0 * all_y[1:-1] + all_y[:-2]) / 3.0
        )
        gradient_sorted = (
            all_y[1:-1] - all_y[2:] + derivative * bracket
        )
        gradient = np.empty_like(gradient_sorted)
        for indices, order in zip(groups, orders, strict=True):
            gradient[indices[order]] = gradient_sorted[indices]
        cost = float(
            np.sum(all_y[1:] * np.diff(all_x) - np.diff(all_y) ** 2 / 6.0)
        )
        return cost * scale, gradient * scale

    seed_values = [np.clip(initial, lower, upper)]
    # Repel the two neighboring meshes from every omitted transition.
    repelled = seed_values[0].copy()
    attracted = seed_values[0].copy()
    for r in range(first, last):
        left_indices = np.where(branches == r)[0]
        right_indices = np.where(branches == r + 1)[0]
        kink = 1.0 - 1.0 / r
        if len(left_indices):
            index = left_indices[-1]
            repelled[index] -= 0.35 * (kink - repelled[index])
            attracted[index] += 0.70 * (kink - attracted[index])
        if len(right_indices):
            index = right_indices[0]
            repelled[index] += 0.35 * (repelled[index] - kink)
            attracted[index] -= 0.70 * (attracted[index] - kink)
    if starts >= 2:
        seed_values.append(np.clip(repelled, lower, upper))
    if starts >= 3:
        seed_values.append(np.clip(attracted, lower, upper))
    rng = np.random.default_rng(rng_seed)
    while len(seed_values) < starts:
        jitter = np.empty_like(initial)
        for r, indices in zip(range(first, last + 1), groups, strict=True):
            spacing = (1.0 / (r * (r - 1))) / (counts[r] + 1)
            jitter[indices] = rng.normal(0.0, 0.20 * spacing, len(indices))
        seed_values.append(np.clip(initial + jitter, lower, upper))

    best: tuple[float, np.ndarray, Any] | None = None
    bounds = list(zip(lower, upper, strict=True))
    for seed in seed_values:
        result = minimize(
            lambda value: objective_gradient(value, 1e9),
            seed,
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            options={"ftol": 1e-15, "gtol": 1e-8, "maxiter": 1200, "maxls": 60},
        )
        nodes, _ = sorted_groups(result.x, groups)
        cost = objective_gradient(nodes)[0]
        if best is None or cost < best[0]:
            best = (cost, nodes, result)
    if best is None:
        raise RuntimeError("block optimizer produced no result")
    cost, nodes, result = best
    distances = []
    for r in range(first, last):
        kink = 1.0 - 1.0 / r
        distances.append(float(np.min(np.abs(nodes - kink))))
    node_map = {
        str(r): nodes[indices].tolist()
        for r, indices in zip(range(first, last + 1), groups, strict=True)
    }
    return {
        "cost": cost,
        "iterations": int(result.nit),
        "minimum_omitted_transition_distance": min(distances),
        "nodes": node_map,
        "status": str(result.message),
    }


def optimize_mask(
    removed: frozenset[int],
    counts: dict[int, int],
    exclusion: float,
    starts: int,
    cache: dict[tuple[Any, ...], dict[str, Any]],
) -> dict[str, Any]:
    total_cost = 0.0
    iterations = 0
    minimum_distance = math.inf
    node_map: dict[str, list[float]] = {}
    block_records = []
    for first, last in partition(removed):
        key = (
            first,
            last,
            tuple(counts[r] for r in range(first, last + 1)),
            exclusion,
            starts,
        )
        if key not in cache:
            seed = 20260815 + first * 101 + last * 1009 + sum(counts.values()) * 17
            cache[key] = optimize_block(
                first, last, counts, exclusion, starts, seed
            )
        block = cache[key]
        total_cost += float(block["cost"])
        iterations += int(block["iterations"])
        minimum_distance = min(
            minimum_distance, float(block["minimum_omitted_transition_distance"])
        )
        node_map.update(block["nodes"])
        block_records.append(
            {
                "first": first,
                "last": last,
                "cost": block["cost"],
                "iterations": block["iterations"],
                "minimum_omitted_transition_distance": block[
                    "minimum_omitted_transition_distance"
                ],
                "status": block["status"],
            }
        )
    return {
        "cost": total_cost,
        "iterations": iterations,
        "minimum_omitted_transition_distance": minimum_distance,
        "nodes": node_map,
        "blocks": block_records,
    }


def build_payload(
    nodes: dict[str, list[float]], removed: frozenset[int]
) -> dict[str, Any]:
    rows = []
    for index in range(1, 11):
        x = 0.05 * index
        small = (1.0 - math.sqrt(max(0.0, 1.0 - 2.0 * x))) / 2.0
        rows.append(padded([small, 1.0 - small]))
    for r in BRANCHES:
        rows.extend(weights_for_interior(float(x), r) for x in nodes[str(r)])
        if r not in removed:
            rows.append(padded([1.0 / r] * r))
    if len(rows) != 500:
        raise RuntimeError(f"changed-topology payload has {len(rows)} rows")
    return {"weights": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--global-summary",
        type=Path,
        default=ROOT / "runs" / "20260815T023100Z" / "global_dp" / "summary.json",
    )
    parser.add_argument("--stamp", default="20260815T023200Z")
    parser.add_argument("--top-per-size", type=int, default=8)
    parser.add_argument("--random-per-size", type=int, default=4)
    parser.add_argument("--starts", type=int, default=3)
    parser.add_argument("--separated-exclusion", type=float, default=1e-6)
    args = parser.parse_args()
    run_dir = ROOT / "runs" / args.stamp / "transition_topology"
    events = run_dir / "events.jsonl"
    if events.exists():
        raise RuntimeError(f"refusing to overwrite append-only log {events}")

    live = json.loads(LIVE.read_text())
    if live["verifier_sha256"] != EXPECTED_VERIFIER_SHA256:
        raise RuntimeError("pinned verifier changed")
    if int(live["leader"]["id"]) != EXPECTED_LEADER_ID:
        raise RuntimeError("pinned leader changed")
    global_summary = json.loads(args.global_summary.read_text())
    cost_table_path = Path(global_summary["cost_table_path"])
    cost_table = json.loads(cost_table_path.read_text())
    costs = {int(r): list(map(float, values)) for r, values in cost_table["costs"].items()}
    for r in BRANCHES:
        for count in range(len(costs[r]), BASE_INTERIOR + len(TRANSITIONS) + 1):
            costs[r].append(optimize_interval(r, count).cost)
    base_cost = float(global_summary["best_smooth_cost"])
    count_by_size = allocations(costs)
    append_event(
        events,
        {
            "event": "start",
            "global_summary": str(args.global_summary),
            "global_summary_sha256": hashlib.sha256(args.global_summary.read_bytes()).hexdigest(),
            "verifier_sha256": EXPECTED_VERIFIER_SHA256,
        },
    )

    rng = np.random.default_rng(20260815)
    selected_masks: set[frozenset[int]] = set()
    screening = []
    total_masks = 0
    for size in range(1, len(TRANSITIONS) + 1):
        counts = count_by_size[size]
        retained_cost, penalties = fixed_mesh_penalties(counts)
        combinations = math.comb(len(TRANSITIONS), size)
        total_masks += combinations
        candidates = (
            (sum(penalties[r] for r in mask), tuple(mask))
            for mask in itertools.combinations(TRANSITIONS, size)
        )
        top = heapq.nsmallest(args.top_per_size, candidates)
        for _, mask in top:
            selected_masks.add(frozenset(mask))
        # Every contiguous omitted block is included, regardless of its
        # additive rank, because adjacent omissions have the strongest coupling.
        for start in range(3, 21 - size):
            selected_masks.add(frozenset(range(start, start + size)))
        random_masks = set()
        while len(random_masks) < min(args.random_per_size, combinations):
            mask = frozenset(
                int(value)
                for value in rng.choice(TRANSITIONS, size=size, replace=False)
            )
            random_masks.add(mask)
        selected_masks.update(random_masks)
        best_penalty, best_mask = top[0]
        record = {
            "removed_count": size,
            "combination_count": combinations,
            "best_fixed_mesh_mask": list(best_mask),
            "best_fixed_mesh_cost_delta": retained_cost + best_penalty - base_cost,
            "globally_reallocated_interior_count": BASE_INTERIOR + size,
        }
        screening.append(record)
        append_event(events, {"event": "screen_size_complete", **record})

    cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    refined = []
    best_closure: tuple[float, dict[str, Any], frozenset[int], dict[int, int]] | None = None
    best_separated: tuple[float, dict[str, Any], frozenset[int], dict[int, int]] | None = None
    ordered_masks = sorted(selected_masks, key=lambda mask: (len(mask), tuple(mask)))
    for index, removed in enumerate(ordered_masks):
        counts = count_by_size[len(removed)]
        closure = optimize_mask(removed, counts, 1e-12, args.starts, cache)
        separated = optimize_mask(
            removed, counts, args.separated_exclusion, args.starts, cache
        )
        record = {
            "mask": sorted(removed),
            "removed_count": len(removed),
            "counts": {str(r): counts[r] for r in BRANCHES},
            "closure_cost": closure["cost"],
            "closure_cost_delta": closure["cost"] - base_cost,
            "closure_minimum_transition_distance": closure[
                "minimum_omitted_transition_distance"
            ],
            "separated_cost": separated["cost"],
            "separated_cost_delta": separated["cost"] - base_cost,
            "separated_minimum_transition_distance": separated[
                "minimum_omitted_transition_distance"
            ],
        }
        refined.append(record)
        if best_closure is None or closure["cost"] < best_closure[0]:
            best_closure = (closure["cost"], closure, removed, counts)
        if best_separated is None or separated["cost"] < best_separated[0]:
            best_separated = (separated["cost"], separated, removed, counts)
        append_event(events, {"event": "mask_refined", "index": index, **record})

    if best_closure is None or best_separated is None:
        raise RuntimeError("no topology masks were refined")
    closure_cost, closure_result, closure_mask, _ = best_closure
    separated_cost, separated_result, separated_mask, _ = best_separated
    closure_payload = build_payload(closure_result["nodes"], closure_mask)
    separated_payload = build_payload(separated_result["nodes"], separated_mask)
    closure_path = run_dir / "best_closure_candidate.json"
    separated_path = run_dir / "best_separated_candidate.json"
    atomic_json(closure_path, closure_payload)
    atomic_json(separated_path, separated_payload)
    closure_diagnostics = analyze(closure_payload["weights"])
    separated_diagnostics = analyze(separated_payload["weights"])
    screen_path = run_dir / "screening.json"
    atomic_json(
        screen_path,
        {
            "schema": 1,
            "all_nonempty_masks_screened": total_masks,
            "screening_by_removed_count": screening,
            "refined": refined,
        },
    )
    summary = {
        "schema": 1,
        "stamp": args.stamp,
        "method": "all-mask additive screen plus bounded multi-scallop L-BFGS refinement",
        "verifier_sha256": EXPECTED_VERIFIER_SHA256,
        "leader_id": EXPECTED_LEADER_ID,
        "leader_score": EXPECTED_LEADER_SCORE,
        "required_improvement": 1e-6,
        "base_retained_transition_score": global_summary["candidate_score_clean_room"],
        "base_smooth_cost": base_cost,
        "all_nonempty_transition_masks_screened": total_masks,
        "refined_mask_count": len(ordered_masks),
        "refinement_starts_per_block": args.starts,
        "separated_exclusion": args.separated_exclusion,
        "best_closure": {
            "mask": sorted(closure_mask),
            "smooth_cost": closure_cost,
            "cost_delta_from_base": closure_cost - base_cost,
            "minimum_omitted_transition_distance": closure_result[
                "minimum_omitted_transition_distance"
            ],
            "payload": str(closure_path),
            "payload_sha256": hashlib.sha256(canonical(closure_payload)).hexdigest(),
            "diagnostics": closure_diagnostics,
        },
        "best_separated": {
            "mask": sorted(separated_mask),
            "smooth_cost": separated_cost,
            "cost_delta_from_base": separated_cost - base_cost,
            "minimum_omitted_transition_distance": separated_result[
                "minimum_omitted_transition_distance"
            ],
            "payload": str(separated_path),
            "payload_sha256": hashlib.sha256(canonical(separated_payload)).hexdigest(),
            "diagnostics": separated_diagnostics,
        },
        "screening_path": str(screen_path),
        "screening_sha256": hashlib.sha256(screen_path.read_bytes()).hexdigest(),
        "gate_cleared_clean_room": max(
            float(closure_diagnostics["score"]),
            float(separated_diagnostics["score"]),
        )
        - EXPECTED_LEADER_SCORE
        > 1e-6,
        "limitation": "Every mask was screened, but continuous refinement used a deterministic bounded subset and fixed globally optimal retained-curve counts for each cardinality.",
    }
    summary_path = run_dir / "summary.json"
    atomic_json(summary_path, summary)
    append_event(
        events,
        {
            "event": "complete",
            "best_closure_score": closure_diagnostics["score"],
            "best_separated_score": separated_diagnostics["score"],
            "gate_cleared_clean_room": summary["gate_cleared_clean_room"],
            "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        },
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
