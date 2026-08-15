#!/usr/bin/env python3
"""Apply a uniform repeat lift with optional zero-mean within-block noise."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--factor", type=int, default=2)
    parser.add_argument("--noise", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=20260815)
    args = parser.parse_args()
    if args.factor < 2:
        raise RuntimeError("factor must be at least two")
    if args.noise < 0.0:
        raise RuntimeError("noise must be non-negative")
    values = np.load(args.input, allow_pickle=False).astype(np.float64)
    repeated = np.repeat(values, args.factor)
    if args.noise:
        rng = np.random.default_rng(args.seed)
        offsets = rng.normal(
            0.0,
            args.noise * np.sqrt(np.mean(values * values)),
            size=(len(values), args.factor),
        )
        offsets -= np.mean(offsets, axis=1, keepdims=True)
        repeated += offsets.reshape(-1)
    if repeated.size > 2_000_000 or not np.isfinite(repeated).all():
        raise RuntimeError("invalid repeated checkpoint")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, repeated, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
