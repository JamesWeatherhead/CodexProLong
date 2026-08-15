#!/usr/bin/env python3
"""Independent frozen replay for the circle-packing codimension-two packet."""

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


def replay(path: Path, expected_hash: str) -> dict[str, Any]:
    actual_hash = sha256_file(path)
    if actual_hash != expected_hash:
        raise RuntimeError(f"payload hash mismatch for {path}: {actual_hash}")
    payload = json.loads(path.read_text())
    if set(payload) != {"circles"}:
        raise RuntimeError(f"schema keys mismatch for {path}")
    circles = np.asarray(payload["circles"], dtype=np.float64)
    if circles.shape != (26, 3) or not np.isfinite(circles).all():
        raise RuntimeError(f"schema shape/finite mismatch for {path}")
    evaluate = load_evaluate()
    score = float(evaluate(payload))
    return {
        "payload": portable_path(path),
        "payload_sha256": actual_hash,
        "schema_valid": True,
        "accepted": math.isfinite(score),
        "score": score if math.isfinite(score) else None,
    }


def main() -> int:
    receipt_path = HERE / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    targets = [receipt["incumbent_tolerance_ceiling"]]
    targets.extend(run["best_changed"] for run in receipt["runs"])
    results = [
        replay(resolve_receipt_path(item["payload"]), item["payload_sha256"])
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
        "solution_schema": {"circles": "array of [x, y, r] triples"},
        "results": results,
        "maximum_score": max(float(item["score"]) for item in results if item["accepted"]),
        "target_strictly_above": receipt["target_strictly_above"],
        "gate_clearing": any(
            item["accepted"] and float(item["score"]) > receipt["target_strictly_above"]
            for item in results
        ),
    }
    atomic_json(HERE / "replay_receipt.json", output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
