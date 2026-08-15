#!/usr/bin/env python3
"""Exact q=144..220 threshold and public-rounding screen for Heilbronn n=11."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import tempfile
from decimal import Decimal, ROUND_CEILING, getcontext
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
SNAPSHOT = (
    REPOSITORY
    / "campaign/geometry/snapshots/heilbronn-triangles_20260814T231406Z.json"
)
SNAPSHOT_SHA256 = "e6332c0715a82c9e62d9029385a7db1cab46549bf482ff65dca30e9ee5468d90"
VERIFIER_SHA256 = "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d"
TARGET_TEXT = "0.036529890880030155"
COUNT = 11


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    encoded = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def cartesian_to_barycentric(points: list[list[float]]) -> np.ndarray:
    cartesian = np.asarray(points, dtype=np.float64)
    third = 2.0 * cartesian[:, 1] / math.sqrt(3.0)
    second = cartesian[:, 0] - 0.5 * third
    first = 1.0 - second - third
    barycentric = np.column_stack((first, second, third))
    barycentric[np.abs(barycentric) < 1e-12] = 0.0
    if barycentric.shape != (COUNT, 3) or np.any(barycentric < -1e-9):
        raise ValueError("public solution is outside the equilateral triangle")
    return np.maximum(barycentric, 0.0)


def nearest_grid(barycentric: np.ndarray, denominator: int) -> np.ndarray:
    rows = []
    for row in barycentric:
        scaled = row * denominator
        base = np.floor(scaled + 1e-12).astype(np.int64)
        needed = denominator - int(base.sum())
        if not 0 <= needed <= 2:
            raise RuntimeError("invalid largest-remainder state")
        order = np.argsort(-(scaled - base), kind="stable")
        base[order[:needed]] += 1
        if np.any(base < 0) or int(base.sum()) != denominator:
            raise RuntimeError("invalid rounded barycentric point")
        rows.append(base)
    return np.asarray(rows, dtype=np.int64)


def determinant(first: np.ndarray, second: np.ndarray, third: np.ndarray) -> int:
    return abs(
        int(second[1] - first[1]) * int(third[2] - first[2])
        - int(second[2] - first[2]) * int(third[1] - first[1])
    )


def grid_metrics(grid: np.ndarray, threshold: int) -> dict[str, Any]:
    values = [
        determinant(grid[first], grid[second], grid[third])
        for first, second, third in itertools.combinations(range(COUNT), 3)
    ]
    minimum = min(values)
    return {
        "minimum_numerator": minimum,
        "threshold_deficit": threshold - minimum,
        "violating_triple_count": sum(value < threshold for value in values),
        "minimum_triple_count": sum(value == minimum for value in values),
    }


def canonical_key(grid: np.ndarray) -> tuple[tuple[int, int, int], ...]:
    return min(
        tuple(sorted(tuple(map(int, row)) for row in grid[:, permutation]))
        for permutation in itertools.permutations(range(3))
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--q-min", type=int, default=144)
    parser.add_argument("--q-max", type=int, default=220)
    parser.add_argument("--select-count", type=int, default=4)
    parser.add_argument("--output", type=Path, default=ROOT / "denominator_screen.json")
    args = parser.parse_args()
    if args.q_min < 1 or args.q_max < args.q_min or args.select_count < 1:
        raise ValueError("invalid denominator range or selection count")
    if sha256(SNAPSHOT) != SNAPSHOT_SHA256:
        raise RuntimeError("frozen public snapshot hash drift")
    snapshot = json.loads(SNAPSHOT.read_text())
    if snapshot["verifier_sha256"] != VERIFIER_SHA256:
        raise RuntimeError("snapshot verifier hash drift")

    getcontext().prec = 80
    target = Decimal(TARGET_TEXT)
    records = []
    for denominator in range(args.q_min, args.q_max + 1):
        square = denominator * denominator
        threshold = int(
            (target * Decimal(square)).to_integral_value(rounding=ROUND_CEILING)
        )
        threshold_score = Decimal(threshold) / Decimal(square)
        public_roundings = []
        keys = set()
        for solution in snapshot["solutions"]:
            grid = nearest_grid(
                cartesian_to_barycentric(solution["data"]["points"]), denominator
            )
            keys.add(canonical_key(grid))
            public_roundings.append(
                {
                    "public_id": int(solution["id"]),
                    "public_score": float(solution["score"]),
                    **grid_metrics(grid, threshold),
                }
            )
        best = max(
            public_roundings,
            key=lambda record: (
                record["minimum_numerator"],
                -record["violating_triple_count"],
                record["public_score"],
            ),
        )
        records.append(
            {
                "denominator": denominator,
                "threshold_numerator": threshold,
                "threshold_score_decimal": str(threshold_score),
                "overshoot_decimal": str(threshold_score - target),
                "noncorner_grid_point_count": (denominator + 1)
                * (denominator + 2)
                // 2
                - 3,
                "distinct_public_rounded_basins": len(keys),
                "best_public_rounding": best,
            }
        )
    ranked = sorted(
        records,
        key=lambda record: (
            Decimal(record["overshoot_decimal"]),
            record["denominator"],
        ),
    )
    selected = [record["denominator"] for record in ranked[: args.select_count]]
    output = {
        "schema": 1,
        "scope": [args.q_min, args.q_max],
        "target_strictly_above_decimal": TARGET_TEXT,
        "snapshot": str(SNAPSHOT.relative_to(REPOSITORY)),
        "snapshot_sha256": SNAPSHOT_SHA256,
        "verifier_sha256": VERIFIER_SHA256,
        "record_count": len(records),
        "selected_denominators": selected,
        "selection_rule": "four smallest exact threshold overshoots in the requested range",
        "records": records,
    }
    atomic_json(args.output.resolve(), output)
    print(json.dumps({"output": str(args.output.resolve()), "selected": selected}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
