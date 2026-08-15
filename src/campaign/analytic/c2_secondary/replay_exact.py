#!/usr/bin/env python3
"""Replay a C2 NumPy checkpoint with the live verifier implementation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.signal import oaconvolve


VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
TARGET_SCORE = 0.963598110582029


def evaluate(values: np.ndarray) -> float:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    args = parser.parse_args()
    values = np.load(args.checkpoint, allow_pickle=False).astype(np.float64)
    score = evaluate(values)
    result = {
        "checkpoint": str(args.checkpoint.resolve()),
        "score": score,
        "target_score": TARGET_SCORE,
        "gap_to_target": TARGET_SCORE - score,
        "gate_cleared": score >= TARGET_SCORE,
        "n": int(values.size),
        "nonzero": int(np.count_nonzero(values)),
        "values_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
        "verifier_sha256": VERIFIER_SHA256,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
