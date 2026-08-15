#!/usr/bin/env python3
"""Test a changed-reach PNT support with the exact fixed verifier stream.

The public frontier grew by replacing near-zero low keys with a small number
of far-tail keys.  Existing fixed-reach tools cannot evaluate that move because
changing ``max(key)`` changes every sample drawn by the verifier.  This program
therefore regenerates the exact ``RandomState(42)`` stream for the proposed
support, solves a trust-region LP, separates against every sampled integer row,
and writes append-only/atomic evidence.  It contains no submission endpoint.
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
from audit import LIMIT, direct_rows, recurrence_curve
from scipy.optimize._highspy._core import _Highs

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "checkpoints" / "live.json"
OLD_OPTIMIZATION = ROOT / "checkpoints" / "optimization.json"
OLD_GLOBAL = ROOT / "checkpoints" / "global_reopt.json"
DEFAULT_CHECKPOINT = ROOT / "checkpoints" / "reach_extend.json"
DEFAULT_BEST = ROOT / "reach_extend_best.json"
NUM_SAMPLES = 10_000_000
TARGET_BATCH_BYTES = 40 * 1024 * 1024


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


def parse_ints(text: str) -> tuple[int, ...]:
    values = tuple(int(item) for item in text.split(",") if item.strip())
    if not values or len(set(values)) != len(values) or min(values) <= 1:
        raise ValueError("integer lists must be distinct keys greater than one")
    return values


def coefficients(rows: np.ndarray, keys: np.ndarray) -> np.ndarray:
    return -((rows[:, None] % keys[None, :]) / keys[None, :])


def official_mask(max_key: int, submitted_count: int) -> np.ndarray:
    """Regenerate exactly the verifier's set of visited integer floors."""
    if submitted_count != 2000:
        raise ValueError("this campaign requires the full 2,000-key budget")
    internal_count = submitted_count + 1  # normalization inserts key 1
    upper = 10 * max_key
    batch_size = max(1, TARGET_BATCH_BYTES // (internal_count * 8))
    rng = np.random.RandomState(42)
    mask = np.zeros(upper + 1, dtype=np.bool_)
    remaining = NUM_SAMPLES
    while remaining:
        count = min(batch_size, remaining)
        sampled = np.floor(rng.uniform(1, float(upper), size=count)).astype(np.int64)
        mask[sampled] = True
        remaining -= count
    return mask


def add_rows(
    highs: _Highs,
    rows: np.ndarray,
    keys: np.ndarray,
    base_curve: np.ndarray,
    safety: float,
) -> None:
    matrix = coefficients(rows, keys)
    width = len(keys)
    starts = np.arange(0, (len(rows) + 1) * width, width, dtype=np.int32)
    indices = np.tile(np.arange(width, dtype=np.int32), len(rows))
    highs.addRows(
        len(rows),
        np.full(len(rows), -np.inf),
        LIMIT - safety - base_curve[rows],
        matrix.size,
        starts,
        indices,
        matrix.ravel(),
    )


def inherited_rows(mask: np.ndarray, upper: int) -> set[int]:
    result: set[int] = set()
    for path in (OLD_OPTIMIZATION, OLD_GLOBAL):
        if not path.is_file():
            continue
        packet = json.loads(path.read_text(encoding="utf-8"))
        for row in packet.get("constraint_rows", []):
            row = int(row)
            if 0 < row <= upper and mask[row]:
                result.add(row)
    return result


def initial_rows(
    curve: np.ndarray,
    mask: np.ndarray,
    count: int,
    window_count: int,
) -> np.ndarray:
    sampled = np.flatnonzero(mask)
    count = min(count, len(sampled))
    top = sampled[np.argpartition(curve[sampled], -count)[-count:]]
    rows = set(map(int, top))
    for section in np.array_split(sampled, min(window_count, len(sampled))):
        if len(section):
            rows.add(int(section[int(np.argmax(curve[section]))]))
    rows.update(inherited_rows(mask, len(mask) - 1))
    return np.asarray(sorted(rows), dtype=np.int64)


def diverse_cuts(
    curve: np.ndarray,
    mask: np.ndarray,
    added: set[int],
    threshold: float,
    limit: int,
    window_count: int,
) -> np.ndarray:
    candidates = np.flatnonzero(mask & (curve > threshold))
    candidates = np.asarray(
        [row for row in candidates if int(row) not in added], dtype=np.int64
    )
    if not len(candidates):
        return candidates
    chosen: set[int] = set()
    width = max(1, (len(mask) + window_count - 1) // window_count)
    windows = candidates // width
    for window in np.unique(windows):
        section = candidates[windows == window]
        chosen.add(int(section[int(np.argmax(curve[section]))]))
    ranked = candidates[np.argsort(curve[candidates])[::-1]]
    for row in ranked:
        chosen.add(int(row))
        if len(chosen) >= limit:
            break
    return np.asarray(
        sorted(chosen, key=lambda row: curve[row], reverse=True)[:limit],
        dtype=np.int64,
    )


def direct_maximum(
    curve: np.ndarray,
    mask: np.ndarray,
    keys: np.ndarray,
    values: np.ndarray,
    top_count: int,
) -> tuple[float, int]:
    sampled = np.flatnonzero(mask)
    count = min(top_count, len(sampled))
    rows = sampled[np.argpartition(curve[sampled], -count)[-count:]]
    maximum = -np.inf
    argmax = -1
    for batch in np.array_split(rows, max(1, (len(rows) + 4999) // 5000)):
        values_at_rows = direct_rows(batch, keys, values)
        index = int(np.argmax(values_at_rows))
        if float(values_at_rows[index]) > maximum:
            maximum = float(values_at_rows[index])
            argmax = int(batch[index])
    return maximum, argmax


def exact_evaluate(verifier: str, payload: dict[str, Any]) -> float:
    namespace: dict[str, Any] = {}
    exec(  # noqa: S102 - the verifier is hash-pinned campaign input
        compile(verifier, "pnt_live_verifier.py", "exec"), namespace
    )
    return float(namespace["evaluate"](payload))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--add",
        default="120658,122009,123407,124849,126330,127849",
        help="comma-separated changed-reach keys",
    )
    parser.add_argument(
        "--drop",
        default="",
        help="comma-separated incumbent keys; defaults to smallest magnitudes",
    )
    parser.add_argument("--eta", type=float, default=0.5)
    parser.add_argument("--new-bound", type=float, default=10.0)
    parser.add_argument("--initial-rows", type=int, default=3000)
    parser.add_argument("--initial-windows", type=int, default=600)
    parser.add_argument("--cut-batch", type=int, default=1000)
    parser.add_argument("--cut-windows", type=int, default=500)
    parser.add_argument("--max-rounds", type=int, default=40)
    parser.add_argument("--safety", type=float, default=3e-10)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--best", type=Path, default=DEFAULT_BEST)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume rows/history and pre-separate from an intermediate checkpoint",
    )
    parser.add_argument("--live-replay", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    additions = parse_ints(args.add)
    if args.eta <= 0 or args.new_bound <= 0 or args.safety <= 0:
        raise ValueError("bounds and safety must be positive")
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    raw = live["leader"]["data"]["partial_function"]
    if "1" in raw or len(raw) != 2000:
        raise RuntimeError("unexpected incumbent key budget")
    old_values = {int(key): float(value) for key, value in raw.items()}
    if args.drop:
        removals = parse_ints(args.drop)
    else:
        removals = tuple(
            key
            for key, _ in sorted(old_values.items(), key=lambda item: abs(item[1]))[
                : len(additions)
            ]
        )
    if len(removals) != len(additions):
        raise ValueError("add and drop counts must match")
    if any(key not in old_values for key in removals):
        raise ValueError("drop list contains a key outside the incumbent")
    if set(additions) & set(old_values):
        raise ValueError("add list contains an incumbent key")

    retained = [key for key in old_values if key not in set(removals)]
    keys = np.asarray(retained + list(additions), dtype=np.int64)
    base = np.asarray([old_values[key] for key in retained] + [0.0] * len(additions))
    if len(keys) != 2000 or len(set(map(int, keys))) != 2000:
        raise RuntimeError("changed support does not use exactly 2,000 keys")
    max_key = int(keys.max())
    mask = official_mask(max_key, len(keys))
    sampled_rows = np.flatnonzero(mask)
    base_curve = recurrence_curve(keys, base)
    checkpoint_path = args.checkpoint.expanduser().resolve()
    resume_packet: dict[str, Any] | None = None
    if args.resume:
        if not checkpoint_path.is_file():
            raise FileNotFoundError(checkpoint_path)
        resume_packet = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        saved_config = resume_packet.get("config", {})
        expected = {
            "additions": list(additions),
            "removals": list(removals),
            "eta": args.eta,
            "new_bound": args.new_bound,
            "max_key": max_key,
        }
        for key, value in expected.items():
            if saved_config.get(key) != value:
                raise RuntimeError(
                    f"resume config mismatch for {key}: "
                    f"{saved_config.get(key)!r} != {value!r}"
                )
        if "current_delta" not in resume_packet:
            raise RuntimeError("checkpoint is not an intermediate resumable packet")
        row_order = list(map(int, resume_packet["constraint_rows"]))
        added_rows = set(row_order)
        resume_delta = np.asarray(resume_packet["current_delta"], dtype=np.float64)
        resume_curve = base_curve + recurrence_curve(
            keys, resume_delta, upper=10 * max_key
        )
        pre_cuts = diverse_cuts(
            resume_curve,
            mask,
            added_rows,
            LIMIT - args.safety,
            args.cut_batch,
            args.cut_windows,
        )
        row_order.extend(map(int, pre_cuts))
        added_rows.update(map(int, pre_cuts))
        rows = np.asarray(row_order, dtype=np.int64)
        print(
            json.dumps(
                {
                    "event": "resume_preseparation",
                    "saved_rows": len(resume_packet["constraint_rows"]),
                    "pre_cuts": len(pre_cuts),
                    "starting_rows": len(rows),
                }
            ),
            flush=True,
        )
    else:
        rows = initial_rows(base_curve, mask, args.initial_rows, args.initial_windows)
        row_order = list(map(int, rows))
        added_rows = set(row_order)
    costs = np.log(keys) / keys
    base_score = -float(np.dot(base, costs))
    gate = float(live["leader"]["score"]) + float(live["problem"]["minImprovement"])

    lower = np.maximum(-10.0 - base, -args.eta)
    upper = np.minimum(10.0 - base, args.eta)
    lower[-len(additions) :] = -args.new_bound
    upper[-len(additions) :] = args.new_bound
    highs = _Highs()
    highs.setOptionValue("output_flag", False)
    highs.setOptionValue("solver", "ipm")
    highs.setOptionValue("run_crossover", "on")
    highs.setOptionValue("primal_feasibility_tolerance", 1e-9)
    highs.setOptionValue("dual_feasibility_tolerance", 1e-9)
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
    add_rows(highs, rows, keys, base_curve, args.safety)

    config = {
        "additions": list(additions),
        "removals": list(removals),
        "eta": args.eta,
        "new_bound": args.new_bound,
        "initial_rows": args.initial_rows,
        "initial_windows": args.initial_windows,
        "cut_batch": args.cut_batch,
        "cut_windows": args.cut_windows,
        "safety": args.safety,
        "max_key": max_key,
        "sampled_row_count": int(mask.sum()),
        "mask_sha256": hashlib.sha256(mask.tobytes()).hexdigest(),
    }
    history: list[dict[str, Any]] = (
        list(resume_packet.get("history", [])) if resume_packet else []
    )
    switched = False
    final_delta: np.ndarray | None = None
    final_curve: np.ndarray | None = None
    for round_index in range(len(history), args.max_rounds):
        started = time.monotonic()
        highs.run()
        status = highs.modelStatusToString(highs.getModelStatus())
        if status != "Optimal":
            raise RuntimeError(f"HiGHS failed: {status}")
        delta = np.asarray(highs.getSolution().col_value, dtype=np.float64)
        curve = base_curve + recurrence_curve(keys, delta, upper=10 * max_key)
        sampled_max = float(curve[mask].max())
        sampled_argmax = int(sampled_rows[int(np.argmax(curve[mask]))])
        score = base_score - float(np.dot(costs, delta))
        new_rows = diverse_cuts(
            curve,
            mask,
            added_rows,
            LIMIT - args.safety,
            args.cut_batch,
            args.cut_windows,
        )
        record = {
            "round": round_index,
            "status": status,
            "constraint_count": len(row_order),
            "score": score,
            "gate_margin": score - gate,
            "sampled_max": sampled_max,
            "sampled_argmax": sampled_argmax,
            "new_cut_count": len(new_rows),
            "elapsed_seconds": time.monotonic() - started,
        }
        history.append(record)
        print(json.dumps(record), flush=True)
        packet = {
            "updated_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            "verifier_sha256": live["verifier_sha256"],
            "leader_id": live["leader"]["id"],
            "leader_score": live["leader"]["score"],
            "gate": gate,
            "config": config,
            "constraint_rows": row_order,
            "history": history,
            "current_delta": delta.tolist(),
            "external_actions": "none",
        }
        atomic_json(checkpoint_path, packet)
        final_delta, final_curve = delta, curve
        if not len(new_rows):
            break
        add_rows(highs, new_rows, keys, base_curve, args.safety)
        row_order.extend(map(int, new_rows))
        added_rows.update(map(int, new_rows))
        if not switched:
            highs.setOptionValue("solver", "simplex")
            highs.setOptionValue("presolve", "off")
            highs.setOptionValue("simplex_strategy", 1)
            switched = True
    else:
        raise RuntimeError("cut separation did not converge")

    if final_delta is None or final_curve is None:
        raise RuntimeError("solver produced no candidate")
    values = base + final_delta
    direct_max, direct_argmax = direct_maximum(
        final_curve, mask, keys, values, top_count=50_000
    )
    payload = {
        "partial_function": {
            str(int(key)): float(value) for key, value in zip(keys, values, strict=True)
        }
    }
    score = -float(np.dot(values, costs))
    result = {
        "updated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "verifier_sha256": live["verifier_sha256"],
        "leader_id": live["leader"]["id"],
        "leader_score": live["leader"]["score"],
        "gate": gate,
        "config": config,
        "constraint_rows": row_order,
        "history": history,
        "score": score,
        "gate_margin": score - gate,
        "recurrence_sampled_max": float(final_curve[mask].max()),
        "direct_sampled_max": direct_max,
        "direct_sampled_argmax": direct_argmax,
        "grid_feasible": direct_max <= LIMIT,
        "payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "external_actions": "none",
    }
    if args.live_replay and result["grid_feasible"] and score > gate:
        result["live_verifier_score"] = exact_evaluate(
            live["problem"]["verifier"], payload
        )
    if result["grid_feasible"]:
        atomic_json(args.best.expanduser().resolve(), payload, sort_keys=False)
    atomic_json(checkpoint_path, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
