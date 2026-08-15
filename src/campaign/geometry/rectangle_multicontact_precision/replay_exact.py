#!/usr/bin/env python3
"""Independent exact replay of the frozen rectangle multi-contact payloads."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np

import verifier_formula


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
VERIFIER = verifier_formula.VERIFIER
EXPECTED_VERIFIER_SHA256 = verifier_formula.VERIFIER_SHA256


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def load_evaluate():
    verifier_formula.assert_verifier_hash()
    return verifier_formula.evaluate


def resolve_receipt_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY / path


def portable_path(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY.resolve()).as_posix()


def replay(path: Path, expected_hash: str, evaluate) -> dict[str, Any]:
    actual_hash = sha256_file(path)
    if actual_hash != expected_hash:
        raise RuntimeError(f"payload hash mismatch: {path}")
    payload = json.loads(path.read_text())
    if set(payload) != {"circles"}:
        raise RuntimeError(f"schema key mismatch: {path}")
    circles = np.asarray(payload["circles"], dtype=np.float64)
    if circles.shape != (21, 3) or not np.isfinite(circles).all():
        raise RuntimeError(f"schema value mismatch: {path}")
    score = float(evaluate(payload))
    centers, radii = circles[:, :2], circles[:, 2]
    min_x = float(np.min(centers[:, 0] - radii))
    max_x = float(np.max(centers[:, 0] + radii))
    min_y = float(np.min(centers[:, 1] - radii))
    max_y = float(np.max(centers[:, 1] + radii))
    pair_overrun = max(
        float(
            radii[first]
            + radii[second]
            - np.linalg.norm(centers[first] - centers[second])
        )
        for first in range(21)
        for second in range(first + 1, 21)
    )
    return {
        "payload": portable_path(path),
        "payload_sha256": actual_hash,
        "schema_valid": True,
        "accepted": math.isfinite(score),
        "score": score if math.isfinite(score) else None,
        "maximum_pair_overrun": max(0.0, pair_overrun),
        "maximum_perimeter_overrun": max(0.0, max_x - min_x + max_y - min_y - 2.0),
    }


def main() -> int:
    receipt_path = HERE / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    evaluate = load_evaluate()
    targets = [receipt["canonical_tolerance_ceiling"]]
    targets.extend(run["best_changed"] for run in receipt["runs"])
    results = [
        replay(resolve_receipt_path(item["payload"]), item["payload_sha256"], evaluate)
        for item in targets
    ]
    output = {
        "verifier_sha256": sha256_file(VERIFIER),
        "evaluation_mirror": {
            "path": portable_path(Path(verifier_formula.__file__)),
            "sha256": sha256_file(Path(verifier_formula.__file__)),
            "frozen_verifier_executed": False,
        },
        "receipt_sha256": sha256_file(receipt_path),
        "solution_schema": {"circles": "array of 21 [x, y, r] triples"},
        "target_strictly_above": receipt["live"]["target_strictly_above"],
        "results": results,
        "maximum_score": max(float(item["score"]) for item in results if item["accepted"]),
        "gate_clearing": any(
            item["accepted"]
            and float(item["score"]) > receipt["live"]["target_strictly_above"]
            for item in results
        ),
    }
    atomic_json(HERE / "replay_receipt.json", output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
