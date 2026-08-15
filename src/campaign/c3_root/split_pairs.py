#!/usr/bin/env python3
"""Lift a C3 vector to twice the resolution with zero-sum pair splitting."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np


def score(values: np.ndarray) -> float:
    f = np.asarray(values, dtype=np.float64)
    return float(2.0 * len(f) * np.max(np.convolve(f, f)) / np.sum(f) ** 2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--noise", type=float, default=1e-6)
    parser.add_argument("--seed", type=int, default=20260814)
    args = parser.parse_args()
    if args.noise < 0:
        raise RuntimeError("noise must be non-negative")

    source = np.load(args.input, allow_pickle=False).astype(np.float64)
    if source.ndim != 1 or not np.isfinite(source).all() or abs(np.sum(source)) < 1e-12:
        raise RuntimeError("invalid source vector")
    repeated = np.repeat(source, 2)
    rng = np.random.default_rng(args.seed)
    perturbation = rng.normal(0.0, args.noise * np.sqrt(np.mean(source**2)), len(source))
    split = repeated.copy()
    split[0::2] += perturbation
    split[1::2] -= perturbation
    if np.sum(split) != np.sum(repeated):
        # Remove only the aggregate float64 summation residue.
        split[-1] -= float(np.sum(split) - np.sum(repeated))
    if not np.isfinite(split).all():
        raise RuntimeError("pair split produced non-finite values")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, split, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, args.output)
    print(
        f"n={len(split)} repeat_score={score(repeated):.16g} "
        f"split_score={score(split):.16g} mass_delta={np.sum(split)-np.sum(repeated):.3g}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
