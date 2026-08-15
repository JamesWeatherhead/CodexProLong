#!/usr/bin/env python3
"""Checkpointed fixed-stream cutting-plane search near the live leader.

The search keeps the verifier's support size, maximum key, and RNG stream
unchanged.  It expands a trust region only after the preceding master is
feasible on every integer row visited by the ten-million-sample stream.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize._highspy._core import _Highs

from audit import LIMIT, direct_rows, recurrence_curve


ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "checkpoints" / "live.json"
MASK = ROOT / "checkpoints" / "sampled_grid.npy"
CHECKPOINT = ROOT / "checkpoints" / "optimization.json"
BEST = ROOT / "best_feasible.json"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, value: Any, *, sort_keys: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=sort_keys).encode())
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def coefficients(rows: np.ndarray, keys: np.ndarray) -> np.ndarray:
    return -((rows[:, None] % keys[None, :]) / keys[None, :])


def make_payload(
    raw: dict[str, float], selected_indices: np.ndarray, values: np.ndarray
) -> dict[str, Any]:
    partial = dict(raw)
    raw_keys = list(raw)
    for raw_index, value in zip(selected_indices, values, strict=True):
        partial[raw_keys[int(raw_index)]] = float(value)
    return {"partial_function": partial}


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
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--best", type=Path, default=BEST)
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--key-limit", type=int, default=1800)
    parser.add_argument("--absolute-value-limit", type=float, default=0.5)
    parser.add_argument("--etas", default="0.001,0.003")
    parser.add_argument("--initial-rows", type=int, default=1200)
    parser.add_argument("--cut-batch", type=int, default=500)
    parser.add_argument("--max-rounds", type=int, default=30)
    parser.add_argument("--safety", type=float, default=3e-10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checkpoint_path = args.checkpoint.expanduser().resolve()
    best_path = args.best.expanduser().resolve()
    etas = [float(item) for item in args.etas.split(",") if item]
    if not etas or any(eta <= 0 for eta in etas):
        raise ValueError("--etas must contain positive values")
    if etas != sorted(etas):
        raise ValueError("trust radii must be nondecreasing")

    live = json.loads(LIVE.read_text(encoding="utf-8"))
    raw = live["leader"]["data"]["partial_function"]
    all_keys = np.fromiter((int(key) for key in raw), dtype=np.int64)
    leader_values = np.fromiter(raw.values(), dtype=np.float64)
    mask = np.load(MASK, allow_pickle=False)
    if len(mask) != 10 * int(all_keys.max()) + 1:
        raise RuntimeError("sample mask does not match the live leader's reach")
    leader_curve = recurrence_curve(all_keys, leader_values)
    sampled_rows = np.flatnonzero(mask)
    selected_indices = np.flatnonzero(
        (all_keys <= args.key_limit)
        | (np.abs(leader_values) < args.absolute_value_limit)
    )
    keys = all_keys[selected_indices]
    base = leader_values[selected_indices]
    costs = np.log(keys) / keys

    config = {
        "key_limit": args.key_limit,
        "absolute_value_limit": args.absolute_value_limit,
        "etas": etas,
        "initial_rows": args.initial_rows,
        "cut_batch": args.cut_batch,
        "safety": args.safety,
        "selected_count": len(keys),
    }
    prior: dict[str, Any] | None = None
    if checkpoint_path.exists() and not args.restart:
        candidate = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        prior_config = candidate.get("config", {})
        comparable_prior = {
            key: value for key, value in prior_config.items() if key != "etas"
        }
        comparable_current = {
            key: value for key, value in config.items() if key != "etas"
        }
        if (
            candidate.get("verifier_sha256") == live["verifier_sha256"]
            and candidate.get("leader_id") == live["leader"]["id"]
            and comparable_prior == comparable_current
        ):
            prior = candidate

    if prior and prior.get("constraint_rows"):
        row_order = [int(row) for row in prior["constraint_rows"]]
    else:
        count = min(args.initial_rows, len(sampled_rows))
        top = sampled_rows[
            np.argpartition(leader_curve[sampled_rows], -count)[-count:]
        ]
        row_order = list(map(int, top))
    added = set(row_order)

    highs = _Highs()
    highs.setOptionValue("output_flag", False)
    highs.setOptionValue("solver", "ipm")
    highs.setOptionValue("run_crossover", "on")
    highs.setOptionValue("primal_feasibility_tolerance", 1e-9)
    highs.setOptionValue("dual_feasibility_tolerance", 1e-9)
    first_eta = etas[0]
    lower = np.maximum(-10.0 - base, -first_eta)
    upper = np.minimum(10.0 - base, first_eta)
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
    add_rows(
        highs,
        np.asarray(row_order, dtype=np.int64),
        keys,
        leader_curve,
        args.safety,
    )

    stages: list[dict[str, Any]] = []
    best_gain = -np.inf
    best_payload: dict[str, Any] | None = None
    best_record: dict[str, Any] | None = None
    switched_to_simplex = False
    for stage_index, eta in enumerate(etas):
        indices = np.arange(len(keys), dtype=np.int32)
        lower = np.maximum(-10.0 - base, -eta)
        upper = np.minimum(10.0 - base, eta)
        highs.changeColsBounds(len(keys), indices, lower, upper)
        stage_history = []
        stage_feasible = False
        for round_index in range(args.max_rounds):
            started = time.monotonic()
            highs.run()
            if highs.modelStatusToString(highs.getModelStatus()) != "Optimal":
                raise RuntimeError(
                    f"HiGHS failed: {highs.modelStatusToString(highs.getModelStatus())}"
                )
            delta = np.asarray(highs.getSolution().col_value, dtype=np.float64)
            curve = leader_curve + recurrence_curve(
                keys, delta, upper=len(leader_curve) - 1
            )
            sampled_values = curve[mask]
            maximum_index = int(np.argmax(sampled_values))
            maximum_row = int(sampled_rows[maximum_index])
            maximum = float(sampled_values[maximum_index])
            gain = -float(np.dot(costs, delta))
            near_violations = np.flatnonzero(mask & (curve > LIMIT - 2e-9))
            ranked = near_violations[np.argsort(curve[near_violations])[::-1]]
            new_rows = np.fromiter(
                (int(row) for row in ranked if int(row) not in added),
                dtype=np.int64,
                count=min(
                    args.cut_batch,
                    sum(int(row) not in added for row in ranked),
                ),
            )
            record = {
                "stage": stage_index,
                "eta": eta,
                "round": round_index,
                "constraint_count": len(row_order),
                "elapsed_seconds": time.monotonic() - started,
                "score_gain": gain,
                "score": float(live["leader"]["score"]) + gain,
                "sampled_max": maximum,
                "sampled_argmax": maximum_row,
                "near_violation_count": len(near_violations),
                "new_cut_count": len(new_rows),
            }
            stage_history.append(record)
            print(json.dumps(record), flush=True)
            checkpoint = {
                "updated_at": datetime.now(timezone.utc)
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z"),
                "verifier_sha256": live["verifier_sha256"],
                "leader_id": live["leader"]["id"],
                "leader_score": live["leader"]["score"],
                "config": config,
                "constraint_rows": row_order,
                "completed_stages": stages,
                "current_stage_history": stage_history,
                "current_delta": delta.tolist(),
            }
            atomic_json(checkpoint_path, checkpoint)
            if not switched_to_simplex:
                highs.setOptionValue("solver", "simplex")
                highs.setOptionValue("simplex_strategy", 1)
                highs.setOptionValue("presolve", "off")
                switched_to_simplex = True
            if len(new_rows) == 0:
                stage_feasible = maximum <= LIMIT - args.safety / 2
                break
            add_rows(highs, new_rows, keys, leader_curve, args.safety)
            row_order.extend(map(int, new_rows))
            added.update(map(int, new_rows))

        if not stage_feasible:
            raise RuntimeError(
                f"stage eta={eta} did not stabilize in {args.max_rounds} rounds"
            )
        adjusted = base + delta
        payload = make_payload(raw, selected_indices, adjusted)
        # Recompute the tightest rows directly to remove recurrence drift.
        top_count = min(100_000, len(sampled_rows))
        top_rows = sampled_rows[
            np.argpartition(curve[sampled_rows], -top_count)[-top_count:]
        ]
        payload_values = np.fromiter(
            payload["partial_function"].values(), dtype=np.float64
        )
        direct = direct_rows(top_rows, all_keys, payload_values)
        direct_argmax = int(top_rows[int(np.argmax(direct))])
        direct_max = float(np.max(direct))
        stage = {
            "eta": eta,
            "feasible_on_sampled_grid": bool(direct_max <= LIMIT),
            "score_gain": -float(np.dot(costs, delta)),
            "score": -float(np.dot(payload_values, np.log(all_keys) / all_keys)),
            "recurrence_sampled_max": float(curve[mask].max()),
            "direct_sampled_max": direct_max,
            "direct_sampled_argmax": direct_argmax,
            "rounds": stage_history,
            "delta": delta.tolist(),
        }
        stages.append(stage)
        if stage["feasible_on_sampled_grid"] and stage["score_gain"] > best_gain:
            best_gain = stage["score_gain"]
            best_payload = payload
            best_record = stage
            atomic_json(best_path, payload, sort_keys=False)

    if best_payload is None or best_record is None:
        raise RuntimeError("no feasible trust-region stage was found")
    result = {
        "updated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "verifier_sha256": live["verifier_sha256"],
        "leader_id": live["leader"]["id"],
        "leader_score": live["leader"]["score"],
        "config": config,
        "constraint_rows": row_order,
        "stages": stages,
        "best": {
            key: value for key, value in best_record.items() if key != "delta"
        },
        "best_payload_path": str(best_path),
        "best_payload_sha256": hashlib.sha256(canonical(best_payload)).hexdigest(),
        "gate_cleared_by_grid_audit": best_gain > 1e-6,
    }
    atomic_json(checkpoint_path, result)
    print(json.dumps(result["best"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
