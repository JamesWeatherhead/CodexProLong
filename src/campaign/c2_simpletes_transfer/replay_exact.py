#!/usr/bin/env python3
"""Fresh-process replay of the retained SimpleTES-transfer checkpoint.

This script imports the frozen Arena verifier itself after checking its
SHA-256.  It also pins the retained ``.npy`` byte hash, so the receipt cannot
silently drift to a different payload.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DEFAULT_CHECKPOINT = ROOT / "runs/20260815T045500Z-repeat/best.npy"
VERIFIER = (
    REPO
    / "campaign/state/problems/second-autocorrelation-inequality/"
    "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768.py"
)
CHECKPOINT_SHA256 = (
    "b122a49ed64b07217948baa2119e28efe81e8179fd7f9e97da5e3717fea257bd"
)
VERIFIER_SHA256 = (
    "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
)
STRICT_GATE = 0.963598110582029


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path, nargs="?", default=DEFAULT_CHECKPOINT)
    args = parser.parse_args()
    checkpoint = args.checkpoint.resolve()

    checkpoint_hash = sha256(checkpoint.read_bytes())
    if checkpoint_hash != CHECKPOINT_SHA256:
        raise RuntimeError(f"checkpoint hash drift: {checkpoint_hash}")
    verifier_hash = sha256(VERIFIER.read_bytes())
    if verifier_hash != VERIFIER_SHA256:
        raise RuntimeError(f"verifier hash drift: {verifier_hash}")

    spec = importlib.util.spec_from_file_location("frozen_c2_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import frozen verifier")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)

    values = np.load(checkpoint, allow_pickle=False).astype(np.float64)
    score = float(verifier.evaluate({"values": values.tolist()}))
    result = {
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_hash,
        "external_writes": [],
        "gate_cleared": score >= STRICT_GATE,
        "gap_to_strict_gate": STRICT_GATE - score,
        "maximum": float(np.max(values)),
        "minimum": float(np.min(values)),
        "n": int(values.size),
        "nonzero": int(np.count_nonzero(values)),
        "score": score,
        "strict_gate": STRICT_GATE,
        "sum": float(np.sum(values)),
        "values_sha256": sha256(np.ascontiguousarray(values).tobytes()),
        "verifier_sha256": verifier_hash,
    }
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
