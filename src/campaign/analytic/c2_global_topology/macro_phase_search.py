#!/usr/bin/env python3
"""Checkpointed global comb-phase screen for the live C2 construction.

The search acts on seven macroscopic row regions of the 5,455-cell lattice.
It applies circular phase offsets or affine row-phase schedules while keeping
each row's detailed tooth profile and mass unchanged.  Single-region probes
are followed by deterministic joint random schedules and a bounded greedy
coordinate sweep.  Only the literal live verifier score can update ``best``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.signal import oaconvolve


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT.parent / "c2_secondary/public_2416.npy"
PERIOD = 5455
PUBLIC_SCORE = 0.963588110582029
STRICT_GATE = 0.963598110582029
VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"

# All endpoints are full lattice rows.  The partial final row is deliberately
# left fixed so circular phase updates never discard padded mass.
REGIONS = (
    ("head", 0, 75),
    ("ramp_a", 75, 155),
    ("ramp_b", 155, 224),
    ("ramp_edge", 224, 237),
    ("left_bridge", 237, 256),
    ("right_bridge", 318, 329),
    ("terminal", 329, 366),
)


def literal_live_score(values: np.ndarray) -> float:
    f = np.array(values, dtype=np.float64)
    n_points = len(values)
    if f.shape != (n_points,):
        raise ValueError(f"Expected shape ({n_points},), got {f.shape}")
    if np.any(f < -1e-6):
        raise ValueError("Function must be non-negative.")
    f_nonneg = np.maximum(f, 0.0)
    if np.sum(f_nonneg) == 0:
        raise ValueError("Function must have positive integral.")
    convolution = oaconvolve(f_nonneg, f_nonneg, mode="full")
    num_conv_points = len(convolution)
    x_points = np.linspace(-0.5, 0.5, num_conv_points + 2)
    x_intervals = np.diff(x_points)
    y_points = np.concatenate(([0], convolution, [0]))
    y1 = y_points[:-1]
    y2 = y_points[1:]
    l2_norm_squared = float(
        np.sum((x_intervals / 3) * (y1**2 + y1 * y2 + y2**2))
    )
    norm_1 = np.sum(np.abs(convolution)) / (num_conv_points + 1)
    norm_inf = np.max(np.abs(convolution))
    return float(l2_norm_squared / (norm_1 * norm_inf))


def atomic_npy(path: Path, values: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_event(path: Path, value: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def apply_schedule(
    values: np.ndarray,
    offsets: np.ndarray,
    slopes: np.ndarray | None = None,
) -> np.ndarray:
    if offsets.shape != (len(REGIONS),):
        raise ValueError("one offset is required per region")
    if slopes is None:
        slopes = np.zeros_like(offsets)
    full_rows = values.size // PERIOD
    reshaped = values[: full_rows * PERIOD].reshape(full_rows, PERIOD)
    candidate = values.copy()
    output = candidate[: full_rows * PERIOD].reshape(full_rows, PERIOD)
    for region_index, (_, start, stop) in enumerate(REGIONS):
        center = (start + stop - 1) / 2.0
        for row in range(start, min(stop, full_rows)):
            phase = int(round(offsets[region_index] + slopes[region_index] * (row - center)))
            if phase:
                output[row] = np.roll(reshaped[row], phase)
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--stamp")
    parser.add_argument("--random-schedules", type=int, default=96)
    parser.add_argument("--seed", type=int, default=20260815)
    args = parser.parse_args()

    seed = np.maximum(np.load(args.input, allow_pickle=False).astype(np.float64), 0.0)
    if seed.ndim != 1 or seed.size > 2_000_000 or not np.isfinite(seed).all():
        raise ValueError("invalid seed")
    seed_score = literal_live_score(seed)
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_npy(run_dir / "seed.npy", seed)
    atomic_npy(run_dir / "best.npy", seed)

    best = seed.copy()
    best_score = seed_score
    best_offsets = np.zeros(len(REGIONS), dtype=np.int64)
    best_slopes = np.zeros(len(REGIONS), dtype=np.int64)
    evaluations = 0

    def evaluate(
        family: str, offsets: np.ndarray, slopes: np.ndarray | None = None
    ) -> tuple[float, np.ndarray]:
        nonlocal best, best_score, best_offsets, best_slopes, evaluations
        if slopes is None:
            slopes = np.zeros(len(REGIONS), dtype=np.int64)
        candidate = apply_schedule(seed, offsets, slopes)
        score = literal_live_score(candidate)
        evaluations += 1
        accepted = score > best_score
        if accepted:
            best = candidate
            best_score = score
            best_offsets = offsets.copy()
            best_slopes = slopes.copy()
            atomic_npy(run_dir / "best.npy", best)
        event = {
            "event": "evaluate",
            "family": family,
            "evaluation": evaluations,
            "score": score,
            "gain_from_seed": score - seed_score,
            "accepted": accepted,
            "offsets": offsets.tolist(),
            "slopes": slopes.tolist(),
        }
        append_event(events, event)
        print(json.dumps(event, sort_keys=True), flush=True)
        return score, candidate

    # Single-region exact phase response, from subcell offsets through the
    # large tail phase quantum seen in adjacent-row correlations.
    offset_grid = (-1184, -952, -128, -64, -32, -16, -8, -4, -2, -1,
                   1, 2, 4, 8, 16, 32, 64, 128, 952, 1184)
    for region_index, (name, _, _) in enumerate(REGIONS):
        for offset in offset_grid:
            vector = np.zeros(len(REGIONS), dtype=np.int64)
            vector[region_index] = offset
            evaluate(f"single_offset:{name}", vector)

    # Affine row-phase schedules change the inter-row comb pitch without the
    # destructive interpolation used by ordinary dilation/chirp transforms.
    for region_index, (name, _, _) in enumerate(REGIONS):
        for slope in (-8, -4, -2, -1, 1, 2, 4, 8):
            slopes = np.zeros(len(REGIONS), dtype=np.int64)
            slopes[region_index] = slope
            evaluate(f"single_slope:{name}", np.zeros(len(REGIONS), dtype=np.int64), slopes)

    # Joint schedules can cross a phase barrier even when every one-region
    # direction is downhill.  The deterministic mixture spans small phase
    # corrections and the terminal comb's observed alternating quantum.
    rng = np.random.default_rng(args.seed)
    joint_choices = np.array((-16, -8, -4, -2, -1, 0, 1, 2, 4, 8, 16), dtype=np.int64)
    for _ in range(args.random_schedules):
        offsets = rng.choice(joint_choices, size=len(REGIONS), replace=True)
        slopes = rng.choice((-2, -1, 0, 0, 0, 1, 2), size=len(REGIONS), replace=True)
        evaluate("joint_schedule", offsets, slopes)

    # One greedy coordinate sweep in the topology parameter space, seeded by
    # the best complete schedule found above.  Candidate construction always
    # starts from the immutable live seed, avoiding cumulative roll artifacts.
    current_offsets = best_offsets.copy()
    current_slopes = best_slopes.copy()
    for region_index, (name, _, _) in enumerate(REGIONS):
        local_best_score = best_score
        local_best_offsets = current_offsets.copy()
        for delta in (-16, -8, -4, -2, -1, 1, 2, 4, 8, 16):
            offsets = current_offsets.copy()
            offsets[region_index] += delta
            score, _ = evaluate(f"greedy_offset:{name}", offsets, current_slopes)
            if score > local_best_score:
                local_best_score = score
                local_best_offsets = offsets
        current_offsets = local_best_offsets

    replay = literal_live_score(np.load(run_dir / "best.npy", allow_pickle=False))
    if replay != best_score:
        raise RuntimeError(f"exact replay mismatch: {replay} != {best_score}")
    summary = {
        "mode": "whole-region comb phase topology",
        "input": str(args.input.resolve()),
        "n": int(best.size),
        "seed_score": seed_score,
        "best_score": best_score,
        "gain_from_seed": best_score - seed_score,
        "strict_gate": STRICT_GATE,
        "gap_to_gate": STRICT_GATE - best_score,
        "gate_cleared": bool(best_score >= STRICT_GATE),
        "evaluations": evaluations,
        "best_offsets": best_offsets.tolist(),
        "best_slopes": best_slopes.tolist(),
        "payload": str((run_dir / "best.npy").resolve()),
        "values_sha256": hashlib.sha256(best.tobytes()).hexdigest(),
        "verifier_sha256": VERIFIER_SHA256,
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, {"event": "complete", "summary": summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
