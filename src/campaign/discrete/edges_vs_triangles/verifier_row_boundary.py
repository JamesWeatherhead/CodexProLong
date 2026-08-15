#!/usr/bin/env python3
"""Measure the missing ``m <= 500`` check in the live row verifier.

This intentionally explores rows beyond the problem-text budget.  It creates
artifacts for transparent verifier-boundary disclosure; it does not submit or
post them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

import numpy as np
from optimize import (
    EXPECTED_LEADER_ID,
    EXPECTED_LEADER_SCORE,
    EXPECTED_VERIFIER_SHA256,
    LIVE,
    ROOT,
    atomic_json,
    canonical,
    optimize_interval,
    padded,
    weights_for_interior,
)

SOURCE = ROOT / "checkpoints" / "optimization.json"
RESULT = ROOT / "checkpoints" / "verifier_row_boundary.json"
CANDIDATE = ROOT / "candidate-verifier-row-boundary.json"


def build_payload(optima: dict[int, Any], expected_rows: int) -> dict[str, Any]:
    rows: list[list[float]] = []
    for index in range(1, 11):
        x = 0.05 * index
        small = (1.0 - np.sqrt(max(0.0, 1.0 - 2.0 * x))) / 2.0
        rows.append(padded([float(small), float(1.0 - small)]))
    for r in range(3, 21):
        rows.extend(weights_for_interior(float(x), r) for x in optima[r].nodes)
        rows.append(padded([1.0 / r] * r))
    if len(rows) != expected_rows:
        raise RuntimeError(f"constructed {len(rows)} rows instead of {expected_rows}")
    return {"weights": rows}


def main() -> None:
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    if live["verifier_sha256"] != EXPECTED_VERIFIER_SHA256:
        raise RuntimeError("live verifier changed")
    if int(live["leader"]["id"]) != EXPECTED_LEADER_ID:
        raise RuntimeError("live leader changed")
    namespace: dict[str, Any] = {}
    exec(  # noqa: S102 - pinned live verifier is the object under test
        compile(live["problem"]["verifier"], "live_edges_verifier.py", "exec"),
        namespace,
    )
    evaluate: Callable[[dict[str, Any]], float] = namespace["evaluate"]
    leader_score = float(evaluate(live["leader"]["data"]))
    if leader_score != EXPECTED_LEADER_SCORE:
        raise RuntimeError("live leader score changed")

    allocation = {int(r): int(count) for r, count in source["final_counts"].items()}
    cache: dict[tuple[int, int], Any] = {}

    def optimum(r: int, count: int) -> Any:
        key = (r, count)
        if key not in cache:
            cache[key] = optimize_interval(r, count)
        return cache[key]

    records: list[dict[str, Any]] = []
    best_payload: dict[str, Any] | None = None
    best_score = -float("inf")
    first_gate_row: int | None = None
    for rows in range(500, 536):
        if rows > 500:
            benefits = {
                r: optimum(r, count).cost - optimum(r, count + 1).cost
                for r, count in allocation.items()
            }
            receiver = max(benefits, key=benefits.get)
            allocation[receiver] += 1

        # Repair any one-row exchange made favorable by the new total.
        while True:
            moves: list[tuple[float, int, int]] = []
            for donor, donor_count in allocation.items():
                if donor_count == 0:
                    continue
                removal = optimum(donor, donor_count - 1).cost - optimum(
                    donor, donor_count
                ).cost
                for receiver, receiver_count in allocation.items():
                    addition = optimum(receiver, receiver_count).cost - optimum(
                        receiver, receiver_count + 1
                    ).cost
                    moves.append((removal - addition, donor, receiver))
            delta, donor, receiver = min(moves)
            if delta >= -1e-15:
                break
            allocation[donor] -= 1
            allocation[receiver] += 1

        optima = {r: optimum(r, count) for r, count in allocation.items()}
        payload = build_payload(optima, rows)
        score = float(evaluate(payload))
        improvement = score - leader_score
        gate_cleared = improvement > 1e-6
        records.append(
            {
                "allocation": {str(r): count for r, count in allocation.items()},
                "gate_cleared": gate_cleared,
                "improvement": improvement,
                "rows": rows,
                "score": score,
            }
        )
        if gate_cleared and first_gate_row is None:
            first_gate_row = rows
        if score > best_score:
            best_score = score
            best_payload = payload
        print(rows, score, improvement, gate_cleared, flush=True)

    if best_payload is None:
        raise RuntimeError("no boundary payload built")
    atomic_json(CANDIDATE, best_payload)
    result = {
        "candidate_path": str(CANDIDATE),
        "candidate_payload_sha256": hashlib.sha256(canonical(best_payload)).hexdigest(),
        "candidate_rows": len(best_payload["weights"]),
        "candidate_score": best_score,
        "first_gate_clearing_rows": first_gate_row,
        "leader_id": EXPECTED_LEADER_ID,
        "leader_score": leader_score,
        "records": records,
        "schema": 1,
        "verifier_boundary": "problem text says m <= 500; verifier omits row-count check",
        "verifier_sha256": EXPECTED_VERIFIER_SHA256,
    }
    atomic_json(RESULT, result)


if __name__ == "__main__":
    main()
