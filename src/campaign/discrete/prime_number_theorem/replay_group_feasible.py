#!/usr/bin/env python3
"""Replay the preserved group-exchange incumbent with the pinned verifier."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def main() -> None:
    receipt = json.loads((ROOT / "group_refine_feasible.json").read_text())
    live = json.loads((ROOT / "checkpoints" / "live.json").read_text())
    verifier = live["problem"]["verifier"]
    verifier_hash = hashlib.sha256(verifier.encode()).hexdigest()
    payload_hash = hashlib.sha256(canonical(receipt["payload"])).hexdigest()
    if verifier_hash != receipt["verifier_sha256"]:
        raise RuntimeError("live verifier no longer matches the receipt")
    if payload_hash != receipt["payload_sha256"]:
        raise RuntimeError("payload hash no longer matches the receipt")
    namespace: dict[str, Any] = {}
    exec(compile(verifier, "live_prime_number_verifier.py", "exec"), namespace)
    score = float(namespace["evaluate"](receipt["payload"]))
    print(
        json.dumps(
            {
                "payload_sha256": payload_hash,
                "verifier_sha256": verifier_hash,
                "recorded_live_score": receipt["live_score"],
                "replayed_live_score": score,
                "gate_score": receipt["gate_score"],
                "gate_cleared": score > float(receipt["gate_score"]),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
