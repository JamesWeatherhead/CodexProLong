#!/usr/bin/env python3
"""Independent exact-integer and frozen-verifier replay of a q=143 candidate."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
VERIFIER = (
    ROOT.parents[1]
    / "state/problems/heilbronn-triangles/"
    "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d.py"
)
VERIFIER_SHA256 = "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d"
Q = 143
THRESHOLD = 747
TARGET = 0.036529890880030155


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def determinant(first: np.ndarray, second: np.ndarray, third: np.ndarray) -> int:
    return abs(
        int(second[1] - first[1]) * int(third[2] - first[2])
        - int(second[2] - first[2]) * int(third[1] - first[1])
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument(
        "--scenario",
        help="replay this scenario when the summary contains multiple candidates",
    )
    args = parser.parse_args()
    run = args.run.resolve()
    summary = json.loads((run / "summary.json").read_text())
    candidates = summary.get("candidates")
    if candidates is None:
        singular = summary.get("candidate")
        candidates = [singular] if singular else []
    if args.scenario:
        candidates = [
            candidate
            for candidate in candidates
            if candidate.get("scenario") == args.scenario
        ]
    if not candidates:
        raise SystemExit("summary contains no candidate")
    gate_candidates = [
        candidate for candidate in candidates if candidate.get("gate_clearing")
    ]
    if len(gate_candidates) == 1:
        candidate = gate_candidates[0]
    elif len(candidates) == 1:
        candidate = candidates[0]
    else:
        scenarios = [candidate.get("scenario") for candidate in candidates]
        raise SystemExit(
            f"summary contains multiple candidates {scenarios}; pass --scenario"
        )
    payload_path = run / candidate["payload"]
    payload_bytes = payload_path.read_bytes()
    payload = json.loads(payload_bytes)
    recorded_payload_hash = candidate.get("payload_sha256")
    if recorded_payload_hash and sha256(payload_bytes) != recorded_payload_hash:
        raise RuntimeError("candidate payload hash mismatch")

    raw_grid = candidate["barycentric_integer_points"]
    if not isinstance(raw_grid, list) or len(raw_grid) != 11:
        raise RuntimeError("integer grid must contain 11 rows")
    for row in raw_grid:
        if not isinstance(row, list) or len(row) != 3:
            raise RuntimeError("each integer-grid row must have three coordinates")
        if any(type(value) is not int for value in row):
            raise RuntimeError("barycentric coordinates must be JSON integers")
        if any(value < 0 for value in row) or sum(row) != Q:
            raise RuntimeError("invalid barycentric integer point")
    grid = np.asarray(raw_grid, dtype=np.int64)
    minimum = min(
        determinant(grid[first], grid[second], grid[third])
        for first in range(9)
        for second in range(first + 1, 10)
        for third in range(second + 1, 11)
    )
    mathematical_score = minimum / (Q * Q)

    if sha256(VERIFIER.read_bytes()) != VERIFIER_SHA256:
        raise RuntimeError("frozen verifier hash drift")
    spec = importlib.util.spec_from_file_location("independent_heilbronn_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load verifier")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    barycentric = grid.astype(np.float64) / Q
    recomputed_points = np.column_stack(
        (
            barycentric[:, 1] + 0.5 * barycentric[:, 2],
            (np.sqrt(3.0) / 2.0) * barycentric[:, 2],
        )
    )
    recomputed_payload = {"points": recomputed_points.tolist()}
    payload_points = np.asarray(payload.get("points"), dtype=np.float64)
    if payload_points.shape != (11, 2) or not np.array_equal(
        payload_points, recomputed_points
    ):
        raise RuntimeError("payload points are not the recorded integer grid")
    verifier_score = float(verifier.evaluate(recomputed_payload))
    receipt = {
        "status": "ok",
        "payload": str(payload_path),
        "payload_sha256": sha256(payload_bytes),
        "payload_matches_integer_grid": True,
        "verifier_sha256": VERIFIER_SHA256,
        "minimum_numerator": minimum,
        "threshold_numerator": THRESHOLD,
        "mathematical_score": mathematical_score,
        "frozen_verifier_score": verifier_score,
        "target_strictly_above": TARGET,
        "gate_clearing": verifier_score > TARGET,
    }
    if minimum < THRESHOLD or not receipt["gate_clearing"]:
        raise RuntimeError(f"candidate does not clear exact gate: {receipt}")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
