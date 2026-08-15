#!/usr/bin/env python3
"""Exact one-point obstructions to an all-x interpretation of solution #2506."""

from __future__ import annotations

import hashlib
import json
import math
import os
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
PAYLOAD = HERE / "input_payload.json"
PAYLOAD_SHA256 = "d43c5531d562d06981a55829deb1c579a87a7c02405d69688dcc79e7f45f22c1"
FINITE_AUDIT = HERE / "finite_horizon_audit.json"
FINITE_AUDIT_SHA256 = "1ec5b03f9b1d72af559df9b4240e8c2384068d267044b48f86138dd1424d5f7c"
WITNESSES = (1, 1_254_707, 1_814_943, 3_312_217, 4_570_184, 8_015_392)
OUTPUT = HERE / "counterexample_receipt.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def packet(value: Fraction) -> dict[str, Any]:
    text = f"{value.numerator}/{value.denominator}"
    with localcontext() as context:
        context.prec = 60
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return {
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
        "decimal_50": str(decimal),
        "rational_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def exact_decimal_model(raw_bytes: bytes) -> tuple[dict[int, Fraction], Fraction]:
    parsed = json.loads(raw_bytes, parse_float=Decimal, parse_int=int)["partial_function"]
    values = {
        int(label): Fraction(max(Decimal(-10), min(Decimal(10), value)))
        for label, value in parsed.items()
    }
    normalization = sum((value / key for key, value in values.items()), Fraction(0))
    values[1] = values.get(1, Fraction(0)) - normalization
    return values, sum((value / key for key, value in values.items()), Fraction(0))


def exact_binary64_model(raw_bytes: bytes) -> tuple[dict[int, Fraction], Fraction]:
    parsed = json.loads(raw_bytes)["partial_function"]
    floats = {
        int(label): np.clip(float(value), -10.0, 10.0)
        for label, value in parsed.items()
    }
    total = sum(value / key for key, value in floats.items())
    floats[1] = floats.get(1, 0.0) - total
    values = {key: Fraction.from_float(float(value)) for key, value in floats.items()}
    return values, sum((value / key for key, value in values.items()), Fraction(0))


def value_at(values: dict[int, Fraction], point: int) -> Fraction:
    return sum(
        (value * (point // key) for key, value in values.items()), Fraction(0)
    )


def main() -> int:
    raw_bytes = PAYLOAD.read_bytes()
    if hashlib.sha256(raw_bytes).hexdigest() != PAYLOAD_SHA256:
        raise RuntimeError("#2506 payload hash mismatch")
    decimal_values, decimal_residual = exact_decimal_model(raw_bytes)
    binary_values, binary_residual = exact_binary64_model(raw_bytes)
    decimal_f1 = decimal_values[1]
    models = {}
    for name, values, residual in (
        ("submitted_decimal_exact_normalization", decimal_values, decimal_residual),
        ("post_parse_binary64_coefficients", binary_values, binary_residual),
    ):
        witnesses = []
        for point in WITNESSES:
            value = value_at(values, point)
            witnesses.append(
                {
                    "x": point,
                    "value": packet(value),
                    "excess_over_one": packet(value - 1),
                    "violates_ideal_bound": value > 1,
                }
            )
        models[name] = {
            "normalization_residual": packet(residual),
            "witnesses": witnesses,
        }

    scaled_witnesses = []
    for point in WITNESSES:
        value = value_at(decimal_values, point) / decimal_f1
        scaled_witnesses.append(
            {
                "x": point,
                "value": packet(value),
                "excess_over_one": packet(value - 1),
                "violates_ideal_bound": value > 1,
            }
        )
    if sha256_file(FINITE_AUDIT) != FINITE_AUDIT_SHA256:
        raise RuntimeError("finite-horizon audit hash mismatch")
    finite_audit = json.loads(FINITE_AUDIT.read_text())
    finite_record = finite_audit["hardened"]["exact_decimal_lexeme_horizon"]
    finite_argmax = int(finite_record["exact_argmax"])
    finite_maximum = value_at(decimal_values, finite_argmax)
    recorded_maximum = Fraction(
        int(finite_record["exact_maximum"]["numerator"]),
        int(finite_record["exact_maximum"]["denominator"]),
    )
    if finite_maximum != recorded_maximum:
        raise RuntimeError("finite-horizon maximum did not independently reproduce")
    horizon_scale = 1 / finite_maximum
    horizon_scaled_witnesses = []
    for point in WITNESSES:
        value = value_at(decimal_values, point) * horizon_scale
        horizon_scaled_witnesses.append(
            {
                "x": point,
                "value": packet(value),
                "excess_over_one": packet(value - 1),
                "violates_ideal_bound": value > 1,
            }
        )
    keys = [key for key in decimal_values if key != 1]
    lcm_value = math.lcm(*keys)
    output = {
        "payload": PAYLOAD.name,
        "payload_sha256": sha256_file(PAYLOAD),
        "verifier_executed": False,
        "breakpoint_reduction": (
            "All keys are positive integers, so the floor sum is constant on "
            "each real interval [m,m+1); an integer witness is an all-real-x witness."
        ),
        "models": models,
        "uniform_scale_making_exact_decimal_f1_equal_one": {
            "scale": packet(1 / decimal_f1),
            "witnesses": scaled_witnesses,
        },
        "uniform_scale_certified_on_entire_verifier_horizon": {
            "finite_audit_sha256": sha256_file(FINITE_AUDIT),
            "audited_upper_inclusive": int(finite_record["full_horizon_upper_inclusive"]),
            "audited_argmax": finite_argmax,
            "audited_maximum": packet(finite_maximum),
            "scale": packet(horizon_scale),
            "witnesses": horizon_scaled_witnesses,
        },
        "exact_decimal_period": {
            "reason": "exact normalization gives S(x+L)=S(x) for L=lcm(support)",
            "lcm_bit_length": lcm_value.bit_length(),
            "lcm_decimal_digits": int(lcm_value.bit_length() * math.log10(2)) + 1,
        },
        "conclusion": (
            "#2506 fails the ideal inequality already at x=1. Uniform scaling "
            "fixes x=1 but does not create a tail certificate: exact integer "
            "witnesses beyond the verifier horizon exceed 1 by orders of magnitude."
        ),
        "external_actions": "none",
    }
    atomic_json(OUTPUT, output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
