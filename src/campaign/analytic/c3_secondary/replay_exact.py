#!/usr/bin/env python3
"""Replay a C3 NumPy payload with the frozen live verifier algebra."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


VERIFIER_SHA256 = "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9"
TARGET_SCORE = 1.4515618638902069


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    values = np.load(args.payload, allow_pickle=False).astype(np.float64)
    n_points = len(values)
    dx = 0.5 / n_points
    integral_f_sq = (np.sum(values) * dx) ** 2
    if integral_f_sq < 1e-9:
        raise ValueError("Function integral is close to zero, ratio is unstable.")
    convolution = np.convolve(values, values, mode="full")
    scaled_convolution = convolution * dx
    argmax = int(np.argmax(scaled_convolution))
    score = float(abs(np.max(scaled_convolution)) / integral_f_sq)
    print(
        json.dumps(
            {
                "score": score,
                "target_score": TARGET_SCORE,
                "gate_gap": score - TARGET_SCORE,
                "gate_cleared": score <= TARGET_SCORE,
                "n": n_points,
                "sum": float(np.sum(values)),
                "finite": bool(np.isfinite(values).all()),
                "argmax": argmax,
                "max_convolution": float(convolution[argmax]),
                "payload": str(args.payload.resolve()),
                "payload_sha256": hashlib.sha256(args.payload.read_bytes()).hexdigest(),
                "raw_values_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
                "verifier_sha256": VERIFIER_SHA256,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
