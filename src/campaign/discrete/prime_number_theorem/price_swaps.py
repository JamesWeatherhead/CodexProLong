#!/usr/bin/env python3
"""Price unseen keys and screen bounded one-for-one support swaps.

The fixed-row LP is a relaxation of the exact sampled-grid problem.  Its score
is therefore a valid upper bound for the same trust region.  Only a swap whose
relaxation clears the gate needs the more expensive full-grid cut loop.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize._highspy._core import _Highs

from audit import LIMIT, recurrence_curve


ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "checkpoints" / "live.json"
MASK = ROOT / "checkpoints" / "sampled_grid.npy"
OPTIMIZATION = ROOT / "checkpoints" / "optimization.json"
PRICING = ROOT / "checkpoints" / "pricing.json"


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


def coefficients(rows: np.ndarray, keys: np.ndarray) -> np.ndarray:
    return -((rows[:, None] % keys[None, :]) / keys[None, :])


def add_rows(
    highs: _Highs,
    rows: np.ndarray,
    keys: np.ndarray,
    leader_curve: np.ndarray,
    safety: float,
) -> None:
    matrix = coefficients(rows, keys)
    width = len(keys)
    starts = np.arange(0, (len(rows) + 1) * width, width, dtype=np.int32)
    indices = np.tile(np.arange(width, dtype=np.int32), len(rows))
    highs.addRows(
        len(rows),
        np.full(len(rows), -np.inf),
        LIMIT - safety - leader_curve[rows],
        matrix.size,
        starts,
        indices,
        matrix.ravel(),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eta", type=float, default=0.01)
    parser.add_argument("--candidate-bound", type=float, default=0.05)
    parser.add_argument("--candidate-limit", type=int, default=20)
    parser.add_argument("--removal-limit", type=int, default=3)
    parser.add_argument("--price-save-limit", type=int, default=2000)
    parser.add_argument("--safety", type=float, default=3e-10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    optimization = json.loads(OPTIMIZATION.read_text(encoding="utf-8"))
    if optimization["verifier_sha256"] != live["verifier_sha256"]:
        raise RuntimeError("optimization checkpoint is stale")
    raw = live["leader"]["data"]["partial_function"]
    all_keys = np.fromiter((int(key) for key in raw), dtype=np.int64)
    leader_values = np.fromiter(raw.values(), dtype=np.float64)
    config = optimization["config"]
    selected_indices = np.flatnonzero(
        (all_keys <= int(config["key_limit"]))
        | (np.abs(leader_values) < float(config["absolute_value_limit"]))
    )
    keys = all_keys[selected_indices]
    base = leader_values[selected_indices]
    costs = np.log(keys) / keys
    rows = np.asarray(optimization["constraint_rows"], dtype=np.int64)
    leader_curve = recurrence_curve(all_keys, leader_values)

    highs = _Highs()
    highs.setOptionValue("output_flag", False)
    highs.setOptionValue("solver", "ipm")
    highs.setOptionValue("run_crossover", "on")
    highs.setOptionValue("primal_feasibility_tolerance", 1e-9)
    highs.setOptionValue("dual_feasibility_tolerance", 1e-9)
    lower = np.maximum(-10.0 - base, -args.eta)
    upper = np.minimum(10.0 - base, args.eta)
    highs.addCols(
        len(keys),
        costs,
        lower,
        upper,
        0,
        np.zeros(len(keys) + 1, dtype=np.int32),
        np.empty(0, dtype=np.int32),
        np.empty(0, dtype=np.float64),
    )
    add_rows(highs, rows, keys, leader_curve, args.safety)
    started = time.monotonic()
    highs.run()
    if highs.modelStatusToString(highs.getModelStatus()) != "Optimal":
        raise RuntimeError("base pricing master did not solve")
    base_elapsed = time.monotonic() - started
    base_gain = -float(highs.getObjectiveValue())
    row_dual = np.asarray(highs.getSolution().row_dual, dtype=np.float64)
    support = set(map(int, all_keys))
    prices: list[dict[str, Any]] = []
    for start in range(2, int(all_keys.max()) + 1, 4096):
        stop = min(start + 4096, int(all_keys.max()) + 1)
        candidates = np.fromiter(
            (key for key in range(start, stop) if key not in support),
            dtype=np.int64,
        )
        if not len(candidates):
            continue
        reduced = (
            np.log(candidates) / candidates
            - coefficients(rows, candidates).T @ row_dual
        )
        prices.extend(
            {
                "key": int(key),
                "reduced_cost": float(reduced_cost),
                "absolute_reduced_cost": float(abs(reduced_cost)),
                "dual_gain_bound": float(
                    args.candidate_bound * abs(reduced_cost)
                ),
                "gate_possible_by_dual_bound": bool(
                    base_gain + args.candidate_bound * abs(reduced_cost) > 1e-6
                ),
            }
            for key, reduced_cost in zip(candidates, reduced, strict=True)
        )
    prices.sort(key=lambda item: item["absolute_reduced_cost"], reverse=True)
    candidate_keys = [item["key"] for item in prices[: args.candidate_limit]]
    removable_local = np.argsort(np.abs(base))[: args.removal_limit]

    highs.setOptionValue("solver", "simplex")
    highs.setOptionValue("presolve", "off")
    highs.setOptionValue("simplex_strategy", 1)
    row_indices = np.arange(len(rows), dtype=np.int32)
    screens: list[dict[str, Any]] = []
    for local_index in removable_local:
        local_index = int(local_index)
        removed_key = int(keys[local_index])
        removed_value = float(base[local_index])
        highs.changeColBounds(local_index, -removed_value, -removed_value)
        for candidate_key in candidate_keys:
            column = -(rows % candidate_key) / candidate_key
            highs.addCol(
                float(np.log(candidate_key) / candidate_key),
                -args.candidate_bound,
                args.candidate_bound,
                len(rows),
                row_indices,
                column.astype(np.float64),
            )
            started = time.monotonic()
            highs.run()
            status = highs.modelStatusToString(highs.getModelStatus())
            solution = np.asarray(highs.getSolution().col_value, dtype=np.float64)
            score_gain_upper_bound = (
                -float(highs.getObjectiveValue()) if status == "Optimal" else None
            )
            screen = {
                "removed_key": removed_key,
                "removed_value": removed_value,
                "candidate_key": candidate_key,
                "candidate_value_relaxation": (
                    float(solution[-1]) if status == "Optimal" else None
                ),
                "score_gain_upper_bound": score_gain_upper_bound,
                "score_upper_bound": (
                    float(live["leader"]["score"]) + score_gain_upper_bound
                    if score_gain_upper_bound is not None
                    else None
                ),
                "gate_possible_in_fixed_row_relaxation": bool(
                    score_gain_upper_bound is not None
                    and score_gain_upper_bound > 1e-6
                ),
                "status": status,
                "elapsed_seconds": time.monotonic() - started,
            }
            screens.append(screen)
            print(json.dumps(screen), flush=True)
            highs.deleteCols(
                1, np.asarray([highs.getNumCol() - 1], dtype=np.int32)
            )
        highs.changeColBounds(
            local_index, float(lower[local_index]), float(upper[local_index])
        )
        highs.run()

    result = {
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "verifier_sha256": live["verifier_sha256"],
        "leader_id": live["leader"]["id"],
        "leader_score": live["leader"]["score"],
        "config": {
            "eta": args.eta,
            "candidate_bound": args.candidate_bound,
            "candidate_limit": args.candidate_limit,
            "removal_limit": args.removal_limit,
            "constraint_count": len(rows),
            "selected_count": len(keys),
        },
        "base_master_elapsed_seconds": base_elapsed,
        "base_score_gain": base_gain,
        "saved_prices": prices[: args.price_save_limit],
        "screened_swaps": screens,
        "best_screened_swap": max(
            screens,
            key=lambda item: (
                -np.inf
                if item["score_gain_upper_bound"] is None
                else item["score_gain_upper_bound"]
            ),
        ),
        "gate_possible_in_any_screened_relaxation": any(
            item["gate_possible_in_fixed_row_relaxation"] for item in screens
        ),
        "external_actions": "none",
    }
    atomic_json(PRICING, result)
    print(json.dumps(result["best_screened_swap"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
