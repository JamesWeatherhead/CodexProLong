#!/usr/bin/env python3
"""Export an exact float64 C1 checkpoint to the arena JSON schema."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    values = np.load(args.checkpoint, allow_pickle=False).astype(np.float64)
    if values.ndim != 1 or not values.size or values.size > 2_000_000:
        raise RuntimeError("invalid candidate shape")
    if not np.isfinite(values).all() or np.min(values) < 0 or np.sum(values) <= 0:
        raise RuntimeError("invalid candidate domain")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(
            {"values": values.tolist()},
            handle,
            separators=(",", ":"),
            allow_nan=False,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

