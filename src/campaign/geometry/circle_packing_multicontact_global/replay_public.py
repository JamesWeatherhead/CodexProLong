#!/usr/bin/env python3
"""Replay the compact public codimension-three payloads without host imports."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

import public_verifier_formula as verifier


HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "receipt_v2.json"
RECEIPT_SHA256 = "ecc7d290d3496a30c749d2294d662736b71a681c2366ba5e938c8cf2688d98e4"
STRICT_GATE = 2.635983095360844


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def geometry_report(payload: dict[str, Any]) -> dict[str, float | bool]:
    circles = np.asarray(payload["circles"], dtype=np.float64)
    centers, radii = circles[:, :2], circles[:, 2]
    maximum_pair_overrun = -math.inf
    for first in range(26):
        for second in range(first + 1, 26):
            distance = float(np.linalg.norm(centers[first] - centers[second]))
            maximum_pair_overrun = max(
                maximum_pair_overrun,
                float(radii[first] + radii[second] - distance),
            )
    maximum_wall_overrun = float(
        max(
            np.max(radii - centers[:, 0]),
            np.max(radii - centers[:, 1]),
            np.max(centers[:, 0] + radii - 1),
            np.max(centers[:, 1] + radii - 1),
        )
    )
    return {
        "maximum_pair_overrun": maximum_pair_overrun,
        "maximum_wall_overrun": maximum_wall_overrun,
        "physical_strict": bool(
            maximum_pair_overrun <= 2e-12 and maximum_wall_overrun <= 0
        ),
    }


def replay() -> dict[str, Any]:
    verifier.assert_reference_hash()
    if sha256_file(RECEIPT) != RECEIPT_SHA256:
        raise RuntimeError("receipt_v2.json hash mismatch")
    receipt = json.loads(RECEIPT.read_text())
    if receipt["verifier_sha256"] != verifier.VERIFIER_SHA256:
        raise RuntimeError("receipt verifier hash mismatch")

    results: list[dict[str, Any]] = []
    for run in receipt["runs"]:
        recorded = run.get("best_changed_artifact")
        replay_record = run.get("best_changed_replay")
        if recorded is None:
            if replay_record is not None:
                raise RuntimeError(f"artifact/replay mismatch in {run['name']}")
            continue
        recorded_path = Path(recorded)
        if recorded_path.is_absolute() or ".." in recorded_path.parts:
            raise RuntimeError(f"non-relative artifact path: {recorded}")
        artifact = HERE / "artifacts" / recorded_path.name
        if not artifact.is_file():
            raise RuntimeError(f"missing public artifact: {artifact.name}")
        actual_hash = sha256_file(artifact)
        if actual_hash != replay_record["payload_sha256"]:
            raise RuntimeError(f"artifact hash mismatch: {artifact.name}")
        payload = json.loads(artifact.read_text())
        score = float(verifier.evaluate(payload))
        if not math.isfinite(score) or score != float(replay_record["score"]):
            raise RuntimeError(f"score mismatch: {artifact.name}")
        results.append(
            {
                "run": run["name"],
                "artifact": f"artifacts/{artifact.name}",
                "artifact_sha256": actual_hash,
                "score": score,
                "margin_to_strict_gate": score - STRICT_GATE,
                **geometry_report(payload),
            }
        )

    best = max(results, key=lambda item: float(item["score"]))
    report = {
        "schema": "circle-packing-codim3-public-replay-v1",
        "reference_verifier_sha256": verifier.VERIFIER_SHA256,
        "receipt_sha256": RECEIPT_SHA256,
        "strict_gate": STRICT_GATE,
        "replayed_artifact_count": len(results),
        "results": results,
        "best_changed_score": best["score"],
        "best_margin_to_strict_gate": best["margin_to_strict_gate"],
        "gate_clearing": bool(float(best["score"]) > STRICT_GATE),
    }
    if report["gate_clearing"]:
        raise RuntimeError("unexpected gate-clearer requires separate review")
    return report


def main() -> int:
    print(json.dumps(replay(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
