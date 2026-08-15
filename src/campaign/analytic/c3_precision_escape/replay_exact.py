#!/usr/bin/env python3
"""Network-free literal-verifier replay for the frozen C3 precision lane."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
VERIFIER = ROOT / "campaign/state/problems/third-autocorrelation-inequality/b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9.py"
PAYLOAD = ROOT / "campaign/analytic/c3_precision_escape/runs/20260815T063056Z-39272/best.npy"
EXPECTED_VERIFIER_SHA256 = "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9"
EXPECTED_PAYLOAD_SHA256 = "39c72ab7147413ded04ee4af3c6a15a0d4d66a91e05102b1ad3edac9dba6d13e"
EXPECTED_VALUES_SHA256 = "0258fdd4db984f2cce05d34d480ef2404e73169ac25562981c382c3668b5689e"
EXPECTED_SCORE = 1.4515653796072292
TARGET = 1.4515618638902069


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    verifier_sha256 = sha256(VERIFIER)
    payload_sha256 = sha256(PAYLOAD)
    if verifier_sha256 != EXPECTED_VERIFIER_SHA256:
        raise RuntimeError(f"verifier hash mismatch: {verifier_sha256}")
    if payload_sha256 != EXPECTED_PAYLOAD_SHA256:
        raise RuntimeError(f"payload hash mismatch: {payload_sha256}")

    values = np.load(PAYLOAD, allow_pickle=False).astype(np.float64)
    values_sha256 = hashlib.sha256(values.tobytes()).hexdigest()
    if values_sha256 != EXPECTED_VALUES_SHA256:
        raise RuntimeError(f"values hash mismatch: {values_sha256}")

    # Clean-room mirror of the hash-pinned C3 formula. The downloaded verifier
    # is hashed for provenance but is never imported or executed on host.
    dx = 0.5 / len(values)
    integral_squared = (float(np.sum(values)) * dx) ** 2
    if integral_squared < 1.0e-9:
        raise ValueError("function integral is close to zero")
    convolution = np.convolve(values, values, mode="full")
    score = float(abs(np.max(convolution * dx)) / integral_squared)
    if score != EXPECTED_SCORE:
        raise RuntimeError(f"score mismatch: expected {EXPECTED_SCORE!r}, got {score!r}")

    result = {
        "status": "ok",
        "score": score,
        "target": TARGET,
        "gate_gap": score - TARGET,
        "gate_cleared": score < TARGET,
        "n": len(values),
        "sum": float(np.sum(values)),
        "finite": bool(np.isfinite(values).all()),
        "argmax": int(np.argmax(convolution)),
        "payload": str(PAYLOAD),
        "payload_sha256": payload_sha256,
        "values_sha256": values_sha256,
        "verifier": str(VERIFIER),
        "verifier_sha256": verifier_sha256,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
