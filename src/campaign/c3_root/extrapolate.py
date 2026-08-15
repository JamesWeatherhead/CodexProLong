#!/usr/bin/env python3
"""Create a scale-aligned trajectory extrapolation seed."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("newer", type=Path)
    parser.add_argument("older", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--factor", type=float, required=True)
    parser.add_argument(
        "--base",
        type=Path,
        help="apply the newer-minus-older direction to this checkpoint",
    )
    args = parser.parse_args()
    newer = np.load(args.newer, allow_pickle=False).astype(np.float64)
    older = np.load(args.older, allow_pickle=False).astype(np.float64)
    if newer.shape != older.shape:
        raise RuntimeError("trajectory shapes differ")
    older *= np.sum(newer) / np.sum(older)
    base = newer
    if args.base is not None:
        base = np.load(args.base, allow_pickle=False).astype(np.float64)
        if base.shape != newer.shape:
            raise RuntimeError("base and trajectory shapes differ")
        base *= np.sum(newer) / np.sum(base)
    candidate = base + args.factor * (newer - older)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, candidate, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
