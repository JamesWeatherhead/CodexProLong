#!/usr/bin/env python3
"""Fast standalone replay of the frozen higher-height frontier."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from higher_height_core import (
    canonical_signed_list,
    clean_room_live_mirror,
    decimal_score,
    exact_period_replay,
    payload,
)


HERE = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    frozen = json.loads((HERE / "receipt.json").read_text())
    for name, expected in frozen["hashes"].items():
        if sha256_file(HERE / name) != expected:
            raise AssertionError(f"frozen receipt hash mismatch: {name}")
    family_receipt = json.loads((HERE / "family_search_receipt.json").read_text())
    best_payload = json.loads((HERE / "best_payload.json").read_text())
    if sha256_file(HERE / "best_payload.json") != family_receipt["best_payload_sha256"]:
        raise AssertionError("best payload hash mismatch")
    if sha256_file(HERE / "family_search_checkpoint.json") != family_receipt["checkpoint_sha256"]:
        raise AssertionError("family checkpoint hash mismatch")
    counts = canonical_signed_list(family_receipt["best"]["canonical_signed_list"])
    replay = exact_period_replay(counts)
    if replay != family_receipt["best"]["exact_period_replay"]:
        raise AssertionError("exact period replay mismatch")
    if payload(counts) != best_payload:
        raise AssertionError("payload reconstruction mismatch")
    mirror = clean_room_live_mirror(best_payload)
    if mirror != family_receipt["best"]["clean_room_live_mirror"]:
        raise AssertionError("clean-room verifier mirror mismatch")
    score = str(decimal_score(counts))
    if score != family_receipt["best"]["score_decimal"]:
        raise AssertionError("high-precision score mismatch")

    divisor = json.loads((HERE / "divisor_lattice_receipt.json").read_text())
    for run in divisor["results"]:
        exact = run["rounded_exact_candidate"]
        run_counts = canonical_signed_list(exact["signed_list"])
        if exact_period_replay(run_counts) != exact["exact_period_replay"]:
            raise AssertionError("divisor-lattice exact replay mismatch")
        if str(decimal_score(run_counts)) != exact["score_decimal"]:
            raise AssertionError("divisor-lattice exact score mismatch")

    output = {
        "status": "passed",
        "family": family_receipt["best"]["family"],
        "height": family_receipt["best"]["height"],
        "exact_period_replay": replay,
        "score_decimal": score,
        "score_binary64": mirror["score_binary64"],
        "clean_room_live_mirror": mirror,
        "divisor_lattice_exact_candidates_replayed": len(divisor["results"]),
        "verifier_executed": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
