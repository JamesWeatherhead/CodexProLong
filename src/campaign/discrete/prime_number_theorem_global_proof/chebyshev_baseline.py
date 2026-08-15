#!/usr/bin/env python3
"""Exact global replay of Chebyshev's five-term floor certificate."""

from __future__ import annotations

import hashlib
import json
import math
import os
from decimal import Decimal, localcontext
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "chebyshev_baseline_receipt.json"
COEFFICIENTS = {1: 1, 2: -1, 3: -1, 5: -1, 30: 1}


def atomic_json(path: Path, value: object) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def main() -> int:
    normalization_numerator = sum(
        value * (30 // key) for key, value in COEFFICIENTS.items()
    )
    if normalization_numerator != 0:
        raise RuntimeError("normalization identity failed")
    period = math.lcm(*COEFFICIENTS)
    values = {
        point: sum(value * (point // key) for key, value in COEFFICIENTS.items())
        for point in range(1, period + 1)
    }
    if min(values.values()) < 0 or max(values.values()) > 1:
        raise RuntimeError("global bound failed on a complete period")
    with localcontext() as context:
        context.prec = 80
        score = -sum(
            Decimal(value) * Decimal(key).ln() / Decimal(key)
            for key, value in COEFFICIENTS.items()
        )
    canonical = json.dumps(
        {str(key): value for key, value in COEFFICIENTS.items()},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    output = {
        "coefficients": {str(key): value for key, value in COEFFICIENTS.items()},
        "coefficient_sha256": hashlib.sha256(canonical).hexdigest(),
        "normalization_sum": "0",
        "period": period,
        "complete_period_minimum": min(values.values()),
        "complete_period_maximum": max(values.values()),
        "values_equal_to_one": [point for point, value in values.items() if value == 1],
        "all_real_x_ge_1_certified": True,
        "reason": (
            "Integer keys make the sum constant on [m,m+1), exact "
            "normalization makes it 30-periodic, and all 30 states were checked."
        ),
        "score_decimal": str(score),
        "historical_gate": "0.9976498835182795",
        "gap_to_historical_gate_decimal": str(
            score - Decimal("0.9976498835182795")
        ),
        "external_actions": "none",
    }
    atomic_json(OUTPUT, output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
