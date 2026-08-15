#!/usr/bin/env python3
"""Standalone replay of the strongest Bober/Landau Arena certificate."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from landau_core import (
    clean_room_live_mirror,
    decimal_score,
    fraction_decimal,
    map_to_arena,
    period_replay,
    score_interval,
    sha256_json,
)


HERE = Path(__file__).resolve().parent
TABLE = HERE / "bober_sporadic_52.json"
PAYLOAD = HERE / "best_payload.json"
VERIFIER_SHA256 = "fd76a069b269a521d6ded609bd79185bf859df778283bebc37719dfd15b1ded6"
LIVE_GATE = Decimal("0.9976582852677297")
HISTORICAL_GATE = Decimal("0.9976498835182795")


def main() -> int:
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    row = next(row for row in table["sporadic"] if row["line"] == 31)
    a, b, period_parameter, coefficients = map_to_arena(
        row["numerator"], row["denominator"]
    )
    if a != [1, 30] or b != [6, 10, 15] or period_parameter != 30:
        raise RuntimeError("Bober line 31 no longer matches the Chebyshev ratio")
    replay = period_replay(coefficients)
    if replay["minimum"] != 0 or replay["maximum"] != 1:
        raise RuntimeError("exact all-period bound failed")
    if replay["other_values"]:
        raise RuntimeError("exact period contains a value outside {0,1}")

    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    expected_raw = {
        "partial_function": {
            str(key): float(value)
            for key, value in coefficients.items()
            if key != 1
        }
    }
    if payload != expected_raw:
        raise RuntimeError("payload does not equal the canonical line-31 mapping")
    mirror = clean_room_live_mirror(payload)
    if not mirror["passes_live_threshold"]:
        raise RuntimeError("payload fails the clean-room live formula")
    if mirror["horizon_maximum_binary64"] > 1.0:
        raise RuntimeError("payload relies on the numerical verifier tolerance")

    score = decimal_score(a, b)
    low, high = score_interval(a, b)
    result = {
        "all_real_x_ge_1_certified": True,
        "certificate_reason": (
            "exact normalization makes the integer-key floor sum 30-periodic; "
            "all 30 integer states were checked and each is 0 or 1"
        ),
        "bober_sporadic_line": 31,
        "factorial_ratio": {"numerator": a, "denominator": b},
        "M": period_parameter,
        "coefficients_including_derived_f1": {
            str(key): value for key, value in coefficients.items()
        },
        "exact_period_replay": replay,
        "score_decimal": str(score),
        "rigorous_score_lower": fraction_decimal(low),
        "rigorous_score_upper": fraction_decimal(high),
        "payload_file_sha256": hashlib.sha256(PAYLOAD.read_bytes()).hexdigest(),
        "payload_canonical_sha256": sha256_json(payload),
        "clean_room_live_replay": mirror,
        "live_verifier_sha256_metadata_only": VERIFIER_SHA256,
        "downloaded_verifier_executed": False,
        "gap_to_live_gate": str(score - LIVE_GATE),
        "gap_to_historical_gate": str(score - HISTORICAL_GATE),
        "gate_cleared": score >= LIVE_GATE,
    }
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
