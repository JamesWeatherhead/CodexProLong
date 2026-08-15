#!/usr/bin/env python3
"""Independent deterministic replay of the frozen construction landmarks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import freeze_receipt as freeze
import search
import tail_sweep
import prime_power_sweep


HERE = Path(__file__).resolve().parent


def strip_elapsed(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_elapsed(item)
            for key, item in value.items()
            if key != "elapsed_seconds"
        }
    if isinstance(value, list):
        return [strip_elapsed(item) for item in value]
    return value


def find_k0(q: int) -> dict[str, Any]:
    for path in freeze.K0_CHECKPOINTS:
        checkpoint = json.loads(path.read_text())
        for record in checkpoint["records"]:
            if int(record["q"]) == q:
                return record
    raise RuntimeError(f"missing frozen q={q}")


def main() -> int:
    receipt_path = HERE / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if freeze.sha256_file(freeze.VERIFIER) != search.VERIFIER_SHA256:
        raise RuntimeError("verifier hash mismatch")

    landmark_results = []
    for q in (53, 89, 97):
        replayed = strip_elapsed(search.asdict(search.scan_q(q)))
        frozen = strip_elapsed(find_k0(q))
        if replayed != frozen:
            raise RuntimeError(f"k=0 replay mismatch at q={q}")
        landmark_results.append(replayed)

    frozen_prime_power = json.loads(freeze.PRIME_POWER_CHECKPOINT.read_text())
    replayed_prime_power = strip_elapsed(prime_power_sweep.scan_q(64))
    frozen_q64 = strip_elapsed(
        next(
            item
            for item in frozen_prime_power["records"]
            if int(item["q"]) == 64
        )
    )
    if replayed_prime_power != frozen_q64:
        raise RuntimeError("prime-power replay mismatch at q=64")

    frozen_tail = json.loads(freeze.TAIL_FULL_CHECKPOINT.read_text())
    for q in (89, 101):
        maximum = next(
            int(item["maximum_extra"])
            for item in frozen_tail["q_records"]
            if int(item["q"]) == q
        )
        replayed = strip_elapsed(tail_sweep.scan(q, maximum))
        frozen = strip_elapsed(
            next(item for item in frozen_tail["q_records"] if int(item["q"]) == q)
        )
        if replayed != frozen:
            raise RuntimeError(f"tail replay mismatch at q={q}")

    output = {
        "receipt_sha256": freeze.sha256_file(receipt_path),
        "verifier_sha256": freeze.sha256_file(freeze.VERIFIER),
        "frozen_verifier_executed": False,
        "landmark_k0_replays": landmark_results,
        "landmark_prime_power_replay": replayed_prime_power,
        "complete_tail_replays": [89, 101],
        "maximum_score_improvement": 0.0,
        "gate_clearing": False,
        "target_strictly_below": receipt["target_strictly_below"],
    }
    freeze.atomic_json(HERE / "replay_receipt.json", output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
