#!/usr/bin/env python3
"""Independently replay an Erdős payload against a frozen verifier snapshot.

This intentionally imports none of the optimization code.  It executes the
verbatim verifier from the snapshot and separately evaluates its literal
``numpy.correlate`` expression, then requires bit-identical float64 results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


SOURCE_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_ROOT = SOURCE_ROOT.parent if SOURCE_ROOT.name == "src" else SOURCE_ROOT
SOURCE_PAYLOAD = SOURCE_ROOT / (
    "campaign/analytic/erdos_global/slp_runs/"
    "20260815T063000Z-n3584-trust25e5/best.json"
)
PUBLIC_PAYLOAD = PUBLIC_ROOT / "artifacts/frontier/erdos-min-overlap.json"
DEFAULT_PAYLOAD = SOURCE_PAYLOAD if SOURCE_PAYLOAD.is_file() else PUBLIC_PAYLOAD
SOURCE_SNAPSHOT = SOURCE_ROOT / (
    "campaign/erdos_root/snapshots/"
    "erdos-min-overlap_20260814T232154Z.json"
)
PUBLIC_SNAPSHOT = PUBLIC_ROOT / "artifacts/verifiers/erdos-min-overlap.json"
DEFAULT_SNAPSHOT = SOURCE_SNAPSHOT if SOURCE_SNAPSHOT.is_file() else PUBLIC_SNAPSHOT
STRICT_GATE = 0.38085857721583954


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args()

    payload_raw = args.payload.read_bytes()
    snapshot_raw = args.snapshot.read_bytes()
    payload = json.loads(payload_raw)
    snapshot = json.loads(snapshot_raw)

    verifier_source = snapshot["problem"]["verifier"]
    verifier_sha256 = sha256_bytes(verifier_source.encode())
    if verifier_sha256 != snapshot["verifier_sha256"]:
        raise AssertionError("snapshot verifier hash mismatch")

    # First replay: execute the frozen server source verbatim.
    namespace: dict[str, object] = {}
    exec(compile(verifier_source, "<frozen-arena-verifier>", "exec"), namespace)
    verifier_score = float(namespace["evaluate"](payload))

    # Second replay: independent literal implementation of the documented path.
    values = np.asarray(payload["values"], dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise AssertionError("payload is not a finite vector")
    if np.any(values < 0.0) or np.any(values > 1.0):
        raise AssertionError("payload violates the input box")
    input_sum = float(np.sum(values))
    target_sum = values.size / 2.0
    normalized = values.copy()
    if input_sum != target_sum:
        if input_sum == 0.0:
            raise AssertionError("payload has zero mass")
        normalized *= target_sum / input_sum
    if np.any(normalized < 0.0) or np.any(normalized > 1.0):
        raise AssertionError("payload violates the post-normalization box")
    direct_score = float(
        np.max(np.correlate(normalized, 1.0 - normalized, mode="full"))
        / values.size
        * 2.0
    )
    if direct_score != verifier_score:
        raise AssertionError(
            f"replay mismatch: verifier={verifier_score!r}, direct={direct_score!r}"
        )

    result = {
        "direct_literal_np_correlate_score": direct_score,
        "frozen_verifier_score": verifier_score,
        "gate_clearing": verifier_score < STRICT_GATE,
        "gate_gap": verifier_score - STRICT_GATE,
        "input_domain": {
            "finite": bool(np.isfinite(values).all()),
            "maximum": float(values.max()),
            "minimum": float(values.min()),
            "sum": input_sum,
        },
        "n": int(values.size),
        "normalized_sum": float(np.sum(normalized)),
        "payload": str(args.payload.resolve()),
        "payload_sha256": sha256_bytes(payload_raw),
        "snapshot": str(args.snapshot.resolve()),
        "snapshot_sha256": sha256_bytes(snapshot_raw),
        "strict_gate": STRICT_GATE,
        "verifier_sha256": verifier_sha256,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
