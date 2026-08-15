#!/usr/bin/env python3
"""Validate and freeze an offline-controller receipt into a d12 run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from reproduce import CAMPAIGN, VERIFIER_SHA256, append_event


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    receipt_path = args.receipt.resolve()
    receipt = json.loads(receipt_path.read_text())
    candidate = Path(receipt["candidate_path"]).resolve()

    checks = {
        "slug": receipt.get("slug") == "kissing-number-d12",
        "score_zero": receipt.get("score") == 0.0,
        "clears_gate": receipt.get("clears_first_place_gate") is True,
        "verifier_pin": receipt.get("verifier_sha256") == VERIFIER_SHA256,
        "candidate_in_run": candidate.parent == run_dir,
        "candidate_hash": sha256(candidate) == receipt.get("candidate_sha256"),
    }
    if not all(checks.values()):
        raise ValueError(f"receipt validation failed: {checks}")

    frozen = {
        "schema_version": 1,
        "checks": checks,
        "score": receipt["score"],
        "leader_score": receipt["leader_score"],
        "margin": receipt["margin"],
        "clears_first_place_gate": receipt["clears_first_place_gate"],
        "candidate_relative_path": str(candidate.relative_to(CAMPAIGN)),
        "candidate_sha256": receipt["candidate_sha256"],
        "candidate_bytes": receipt["candidate_bytes"],
        "verifier_sha256": receipt["verifier_sha256"],
        "verified_at": receipt["verified_at"],
        "controller_receipt_relative_path": str(receipt_path.relative_to(CAMPAIGN)),
        "controller_receipt_sha256": sha256(receipt_path),
        "controller_receipt": receipt,
    }
    data = json.dumps(frozen, indent=2, sort_keys=True).encode("utf-8")
    output = run_dir / "verification.json"
    tmp = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, output)

    event_file = run_dir / "events.jsonl"
    last = json.loads(event_file.read_text().splitlines()[-1])
    event_hash = append_event(
        event_file,
        {
            "event": "offline_controller_receipt_frozen",
            "score": receipt["score"],
            "leader_score": receipt["leader_score"],
            "margin": receipt["margin"],
            "candidate_sha256": receipt["candidate_sha256"],
            "verifier_sha256": receipt["verifier_sha256"],
            "verification_relative_path": str(output.relative_to(CAMPAIGN)),
            "verification_sha256": sha256(output),
            "controller_receipt_sha256": sha256(receipt_path),
        },
        last["event_sha256"],
    )
    print(
        json.dumps(
            {
                "verification": str(output),
                "verification_sha256": sha256(output),
                "controller_receipt_sha256": sha256(receipt_path),
                "last_event_sha256": event_hash,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
