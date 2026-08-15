#!/usr/bin/env python3
"""Stabilized column generation over unseen keys for the fixed-row master.

An arbitrary dual optimum can give spurious reduced costs on a degenerate LP.
This tool resolves that issue by retaining each priced column in the master,
reoptimizing, and then repricing from the new dual face.
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
CHECKPOINT = ROOT / "checkpoints" / "column_generation.json"


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--eta", type=float, default=0.01)
    parser.add_argument("--candidate-bound", type=float, default=0.05)
    parser.add_argument("--batch", type=int, default=20)
    parser.add_argument("--rounds", type=int, default=10)
    parser.add_argument("--safety", type=float, default=3e-10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    optimization = json.loads(OPTIMIZATION.read_text(encoding="utf-8"))
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
    mask = np.load(MASK, allow_pickle=False)

    configuration = {
        "eta": args.eta,
        "candidate_bound": args.candidate_bound,
        "batch": args.batch,
        "constraint_count": len(rows),
        "selected_count": len(keys),
    }
    added_keys: list[int] = []
    history: list[dict[str, Any]] = []
    if CHECKPOINT.exists() and not args.restart:
        prior = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if (
            prior.get("verifier_sha256") == live["verifier_sha256"]
            and prior.get("leader_id") == live["leader"]["id"]
            and prior.get("config") == configuration
        ):
            added_keys = [int(key) for key in prior.get("added_keys", [])]
            history = list(prior.get("history", []))

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
    matrix = coefficients(rows, keys)
    starts = np.arange(
        0, (len(rows) + 1) * len(keys), len(keys), dtype=np.int32
    )
    indices = np.tile(np.arange(len(keys), dtype=np.int32), len(rows))
    highs.addRows(
        len(rows),
        np.full(len(rows), -np.inf),
        LIMIT - args.safety - leader_curve[rows],
        matrix.size,
        starts,
        indices,
        matrix.ravel(),
    )
    row_indices = np.arange(len(rows), dtype=np.int32)
    for key in added_keys:
        column = -(rows % key) / key
        highs.addCol(
            float(np.log(key) / key),
            -args.candidate_bound,
            args.candidate_bound,
            len(rows),
            row_indices,
            column.astype(np.float64),
        )
    highs.run()
    if highs.modelStatusToString(highs.getModelStatus()) != "Optimal":
        raise RuntimeError("initial column-generation master did not solve")
    highs.setOptionValue("solver", "simplex")
    highs.setOptionValue("presolve", "off")
    highs.setOptionValue("simplex_strategy", 1)

    support = set(map(int, all_keys))
    for round_index in range(len(history), args.rounds):
        started = time.monotonic()
        row_dual = np.asarray(highs.getSolution().row_dual, dtype=np.float64)
        excluded = support | set(added_keys)
        priced: list[tuple[float, float, int]] = []
        for start in range(2, int(all_keys.max()) + 1, 4096):
            stop = min(start + 4096, int(all_keys.max()) + 1)
            candidates = np.fromiter(
                (key for key in range(start, stop) if key not in excluded),
                dtype=np.int64,
            )
            if not len(candidates):
                continue
            reduced = (
                np.log(candidates) / candidates
                - coefficients(rows, candidates).T @ row_dual
            )
            keep = min(args.batch, len(candidates))
            chosen = np.argpartition(np.abs(reduced), -keep)[-keep:]
            priced.extend(
                (float(abs(reduced[index])), float(reduced[index]), int(candidates[index]))
                for index in chosen
            )
        priced.sort(reverse=True)
        batch = priced[: args.batch]
        for _, _, key in batch:
            column = -(rows % key) / key
            highs.addCol(
                float(np.log(key) / key),
                -args.candidate_bound,
                args.candidate_bound,
                len(rows),
                row_indices,
                column.astype(np.float64),
            )
            added_keys.append(key)
        highs.run()
        if highs.modelStatusToString(highs.getModelStatus()) != "Optimal":
            raise RuntimeError("column-generation reoptimization failed")
        solution = np.asarray(highs.getSolution().col_value, dtype=np.float64)
        delta = solution[: len(keys)]
        new_values = solution[len(keys) :]
        curve = leader_curve + recurrence_curve(
            keys, delta, upper=len(leader_curve) - 1
        )
        if added_keys:
            curve += recurrence_curve(
                np.asarray(added_keys, dtype=np.int64),
                new_values,
                upper=len(leader_curve) - 1,
            )
        net_existing = leader_values.copy()
        net_existing[selected_indices] += delta
        existing_zero_count = int(np.count_nonzero(np.abs(net_existing) < 1e-10))
        nonzero_new_count = int(np.count_nonzero(np.abs(new_values) >= 1e-10))
        record = {
            "round": round_index,
            "elapsed_seconds": time.monotonic() - started,
            "added_batch": [
                {
                    "key": key,
                    "absolute_reduced_cost_before_add": absolute,
                    "reduced_cost_before_add": reduced,
                }
                for absolute, reduced, key in batch
            ],
            "total_added_columns": len(added_keys),
            "score_gain_fixed_row_relaxation": -float(highs.getObjectiveValue()),
            "score_fixed_row_relaxation": float(live["leader"]["score"])
            - float(highs.getObjectiveValue()),
            "new_nonzero_count": nonzero_new_count,
            "existing_zero_count": existing_zero_count,
            "support_limit_compatible": nonzero_new_count <= existing_zero_count,
            "sampled_max_before_new_cuts": float(curve[mask].max()),
            "largest_new_values": sorted(
                (
                    {"key": int(key), "value": float(value)}
                    for key, value in zip(added_keys, new_values, strict=True)
                    if abs(value) >= 1e-12
                ),
                key=lambda item: abs(item["value"]),
                reverse=True,
            )[:50],
        }
        history.append(record)
        checkpoint = {
            "updated_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "verifier_sha256": live["verifier_sha256"],
            "leader_id": live["leader"]["id"],
            "leader_score": live["leader"]["score"],
            "config": configuration,
            "added_keys": added_keys,
            "history": history,
            "current_existing_delta": delta.tolist(),
            "current_new_values": new_values.tolist(),
            "external_actions": "none",
        }
        atomic_json(CHECKPOINT, checkpoint)
        print(json.dumps(record), flush=True)
        # Exact zero reduced costs indicate a stabilized dual face.
        if not batch or batch[0][0] <= 1e-10:
            break


if __name__ == "__main__":
    main()
