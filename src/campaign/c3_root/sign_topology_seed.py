#!/usr/bin/env python3
"""Create an atomic C3 seed by changing only near-zero sign topology."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--mode", choices=("zero", "flip", "random-flip"), required=True)
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--probability", type=float, default=0.5)
    args = parser.parse_args()
    if args.threshold <= 0.0 or not np.isfinite(args.threshold):
        raise RuntimeError("threshold must be positive and finite")
    if not 0.0 <= args.probability <= 1.0:
        raise RuntimeError("probability must be between zero and one")

    values = np.load(args.input, allow_pickle=False).astype(np.float64)
    if values.ndim != 1 or not np.isfinite(values).all() or abs(np.sum(values)) < 1e-12:
        raise RuntimeError("invalid source vector")
    selected = np.abs(values) < args.threshold
    if args.mode == "zero":
        values[selected] = 0.0
    elif args.mode == "flip":
        values[selected] *= -1.0
    else:
        rng = np.random.default_rng(args.seed)
        selected &= rng.random(len(values)) < args.probability
        values[selected] *= -1.0

    if abs(np.sum(values)) < 1e-12:
        raise RuntimeError("topology seed has near-zero mass")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, args.output)
    print(f"changed={int(np.sum(selected))} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
