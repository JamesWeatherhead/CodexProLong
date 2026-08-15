#!/usr/bin/env python3
"""Replay the fixed-task answer under exact PSL arithmetic and frozen verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
VERIFIER_SHA256 = "ff991bd84aec2b5b5d44f58a68dba00f961e01d517ec1de3225e0902f0f2fce2"
VERIFIER_SOURCE_ID = (
    "campaign/state/problems/flat-polynomials/"
    f"{VERIFIER_SHA256}.py"
)
ANSWER = (
    "0000011100001011111111110101001010111100110011001101010110010110010110"
)
EXPECTED_SCORE = 1.309817443680567


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite append-only receipt: {path}")
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def clean_room_evaluate(data: dict[str, list[int]]) -> float:
    """Literal formula mirror of the hash-pinned five-line live evaluator."""
    coefficients = np.array(data["coefficients"], dtype=np.float64)
    assert len(coefficients) == 70
    assert all(value in (-1, 1) for value in coefficients)
    polynomial = np.poly1d(coefficients)
    points = np.exp(1j * np.linspace(0, 2 * np.pi, 1_000_000))
    values = np.abs(polynomial(points))
    return float(np.max(values) / np.sqrt(len(coefficients) + 1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    coefficients = [1 if bit == "1" else -1 for bit in ANSWER]
    correlations = [
        sum(coefficients[i] * coefficients[i + lag] for i in range(70 - lag))
        for lag in range(1, 70)
    ]
    peak_sidelobe = max(abs(value) for value in correlations)
    if peak_sidelobe != 4:
        raise RuntimeError(f"unexpected exact PSL: {peak_sidelobe}")

    score = clean_room_evaluate({"coefficients": coefficients})
    if score != EXPECTED_SCORE:
        raise RuntimeError(
            f"verifier score changed: expected {EXPECTED_SCORE}, observed {score}"
        )

    payload = {"coefficients": coefficients}
    receipt = {
        "schema": "flat-psl4-accelerator-clean-room-verifier-replay-v1",
        "answer_bits": ANSWER,
        "answer_sha256": sha256_bytes(ANSWER.encode()),
        "payload_sha256": sha256_bytes(canonical(payload)),
        "autocorrelations_sha256": sha256_bytes(canonical(correlations)),
        "exact_peak_sidelobe": peak_sidelobe,
        "verifier_source_id": VERIFIER_SOURCE_ID,
        "verifier_sha256": VERIFIER_SHA256,
        "evaluation_method": "standalone literal formula mirror; no verifier import or canonical-state dependency",
        "verifier_score": score,
        "scope": (
            "The one completed benchmark task reproduces a valid PSL-4 class; "
            "this is not a full enumeration and the class does not clear the "
            "flat-polynomials live gate."
        ),
    }
    if args.receipt:
        atomic_json(args.receipt, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
