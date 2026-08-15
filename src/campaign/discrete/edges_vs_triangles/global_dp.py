#!/usr/bin/env python3
"""Globally allocate the 472 smooth-branch nodes by exact resource DP.

The ten zero-triangle rows and all 18 curve transition rows are fixed.  For
each of the 18 smooth Razborov scallops this computes its unique Newton mesh
for every possible node count 0..472, proves discrete convexity numerically,
and solves the complete integer allocation rather than making local exchanges.

No downloaded verifier is imported or executed here.  The resulting payload
is replayed separately through ``./arena verify``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from audit_corpus import analyze
from optimize import (
    EXPECTED_LEADER_ID,
    EXPECTED_LEADER_SCORE,
    EXPECTED_VERIFIER_SHA256,
    LIVE,
    Optimum,
    build_payload,
    canonical,
    optimize_interval,
)


ROOT = Path(__file__).resolve().parent
TOTAL_INTERIOR = 472
BRANCHES = tuple(range(3, 21))


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


def dynamic_program(costs: np.ndarray) -> tuple[float, list[int], float]:
    """Return best cost/counts and the best distinct allocation cost."""

    branches, budget_plus_one = costs.shape
    budget = budget_plus_one - 1
    # Each state keeps the two cheapest distinct paths.  A path is represented
    # by its tuple of counts, making the second-best comparison unambiguous.
    states: list[list[tuple[float, tuple[int, ...]]]] = [[] for _ in range(budget + 1)]
    states[0] = [(0.0, ())]
    for branch in range(branches):
        updated: list[list[tuple[float, tuple[int, ...]]]] = [
            [] for _ in range(budget + 1)
        ]
        for used in range(budget + 1):
            if not states[used]:
                continue
            for count in range(budget - used + 1):
                increment = float(costs[branch, count])
                target = updated[used + count]
                for previous, path in states[used]:
                    target.append((previous + increment, path + (count,)))
        # Retaining only two paths per state is valid because every continuation
        # adds the same branch-dependent cost to either prefix.
        states = []
        for candidates in updated:
            candidates.sort(key=lambda item: item[0])
            kept: list[tuple[float, tuple[int, ...]]] = []
            seen: set[tuple[int, ...]] = set()
            for item in candidates:
                if item[1] in seen:
                    continue
                kept.append(item)
                seen.add(item[1])
                if len(kept) == 2:
                    break
            states.append(kept)
    final = states[budget]
    if len(final) < 2:
        raise RuntimeError("DP failed to retain two complete allocations")
    return final[0][0], list(final[0][1]), final[1][0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stamp", default="20260815T023100Z")
    args = parser.parse_args()
    run_dir = ROOT / "runs" / args.stamp / "global_dp"
    events = run_dir / "events.jsonl"
    if events.exists():
        raise RuntimeError(f"refusing to overwrite append-only event log {events}")

    live = json.loads(LIVE.read_text(encoding="utf-8"))
    if live["verifier_sha256"] != EXPECTED_VERIFIER_SHA256:
        raise RuntimeError("pinned verifier hash changed")
    if int(live["leader"]["id"]) != EXPECTED_LEADER_ID:
        raise RuntimeError("pinned leader changed")
    if float(live["leader"]["score"]) != EXPECTED_LEADER_SCORE:
        raise RuntimeError("pinned leader score changed")
    append_event(
        events,
        {
            "event": "start",
            "leader_id": EXPECTED_LEADER_ID,
            "leader_score": EXPECTED_LEADER_SCORE,
            "total_interior_nodes": TOTAL_INTERIOR,
            "verifier_sha256": EXPECTED_VERIFIER_SHA256,
        },
    )

    cache: dict[tuple[int, int], Optimum] = {}
    costs = np.empty((len(BRANCHES), TOTAL_INTERIOR + 1), dtype=np.float64)
    convexity = []
    for branch_index, r in enumerate(BRANCHES):
        for count in range(TOTAL_INTERIOR + 1):
            optimum = optimize_interval(r, count)
            cache[(r, count)] = optimum
            costs[branch_index, count] = optimum.cost
        second = np.diff(costs[branch_index], n=2)
        minimum_second = float(np.min(second))
        record = {
            "r": r,
            "minimum_discrete_second_difference": minimum_second,
            "strictly_discretely_convex": bool(minimum_second > 0.0),
        }
        convexity.append(record)
        append_event(events, {"event": "branch_costs_complete", **record})

    best_cost, counts_list, second_cost = dynamic_program(costs)
    counts = dict(zip(BRANCHES, counts_list, strict=True))
    optima = {r: cache[(r, count)] for r, count in counts.items()}
    candidate = build_payload(optima)
    candidate_path = run_dir / "candidate.json"
    atomic_json(candidate_path, candidate)
    diagnostics = analyze(candidate["weights"])

    # Independent greedy marginal allocation is exact for separable discretely
    # convex costs.  It cross-checks the DP path and makes the certificate easy
    # to inspect.
    marginals: list[tuple[float, int, int]] = []
    for branch_index, r in enumerate(BRANCHES):
        for count in range(1, TOTAL_INTERIOR + 1):
            benefit = costs[branch_index, count - 1] - costs[branch_index, count]
            marginals.append((float(benefit), r, count))
    marginals.sort(reverse=True)
    selected = marginals[:TOTAL_INTERIOR]
    marginal_counts = {r: 0 for r in BRANCHES}
    for _, r, count in selected:
        if count != marginal_counts[r] + 1:
            raise RuntimeError("discrete convex marginal prefix property failed")
        marginal_counts[r] = count
    if marginal_counts != counts:
        raise RuntimeError("dynamic program and marginal allocation disagree")
    boundary_selected = selected[-1][0]
    boundary_rejected = marginals[TOTAL_INTERIOR][0]

    cost_table = {
        "schema": 1,
        "branches": list(BRANCHES),
        "costs": {str(r): costs[index].tolist() for index, r in enumerate(BRANCHES)},
    }
    cost_table_path = run_dir / "cost_table.json"
    atomic_json(cost_table_path, cost_table)
    result = {
        "schema": 1,
        "stamp": args.stamp,
        "method": "complete 18-branch integer dynamic program with all counts 0..472",
        "scope": {
            "fixed_zero_triangle_rows": 10,
            "fixed_transition_rows": 18,
            "globally_allocated_interior_rows": TOTAL_INTERIOR,
            "total_rows": 500,
        },
        "leader_id": EXPECTED_LEADER_ID,
        "leader_score": EXPECTED_LEADER_SCORE,
        "verifier_sha256": EXPECTED_VERIFIER_SHA256,
        "candidate_path": str(candidate_path),
        "candidate_payload_sha256": hashlib.sha256(canonical(candidate)).hexdigest(),
        "candidate_score_clean_room": diagnostics["score"],
        "candidate_improvement_clean_room": float(diagnostics["score"])
        - EXPECTED_LEADER_SCORE,
        "gate_cleared_clean_room": float(diagnostics["score"])
        - EXPECTED_LEADER_SCORE
        > 1e-6,
        "counts": {str(r): count for r, count in counts.items()},
        "best_smooth_cost": best_cost,
        "second_best_smooth_cost": second_cost,
        "second_best_allocation_gap": second_cost - best_cost,
        "smallest_selected_marginal_benefit": boundary_selected,
        "largest_rejected_marginal_benefit": boundary_rejected,
        "marginal_exchange_gap": boundary_selected - boundary_rejected,
        "all_branches_strictly_discretely_convex": all(
            item["strictly_discretely_convex"] for item in convexity
        ),
        "convexity": convexity,
        "cost_table_path": str(cost_table_path),
        "cost_table_sha256": hashlib.sha256(cost_table_path.read_bytes()).hexdigest(),
        "candidate_diagnostics": diagnostics,
        "limitation": "This certificate is global only with every Razborov transition retained; transition-removal topologies are screened separately.",
    }
    summary_path = run_dir / "summary.json"
    atomic_json(summary_path, result)
    append_event(
        events,
        {
            "event": "complete",
            "candidate_score_clean_room": diagnostics["score"],
            "counts": result["counts"],
            "gate_cleared_clean_room": result["gate_cleared_clean_room"],
            "summary_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        },
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
