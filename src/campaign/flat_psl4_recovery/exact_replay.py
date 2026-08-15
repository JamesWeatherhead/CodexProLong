#!/usr/bin/env python3
"""Replay a recovered flat-polynomial payload with the frozen live verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
VERIFIER_SHA256 = "ff991bd84aec2b5b5d44f58a68dba00f961e01d517ec1de3225e0902f0f2fce2"
VERIFIER = (
    CAMPAIGN
    / "state"
    / "problems"
    / "flat-polynomials"
    / f"{VERIFIER_SHA256}.py"
)
LEADER_SCORE = 1.2807274949642549
GATE_SCORE = LEADER_SCORE - 1e-6


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    verifier_bytes = VERIFIER.read_bytes()
    actual_hash = hashlib.sha256(verifier_bytes).hexdigest()
    if actual_hash != VERIFIER_SHA256:
        raise RuntimeError(f"verifier hash changed: {actual_hash}")
    namespace: dict[str, Any] = {}
    exec(compile(verifier_bytes, str(VERIFIER), "exec"), namespace)

    payload = json.loads(args.payload.read_text())
    score = float(namespace["evaluate"](payload))
    record = {
        "label": str(args.payload),
        "verifier_path": str(VERIFIER),
        "verifier_sha256": actual_hash,
        "payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "score": score,
        "leader_score": LEADER_SCORE,
        "gate_score": GATE_SCORE,
        "gap_to_gate": score - GATE_SCORE,
        "clears_gate": score < GATE_SCORE,
        "payload": payload,
    }
    if args.receipt:
        atomic_json(args.receipt, record)
    print(json.dumps(record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
