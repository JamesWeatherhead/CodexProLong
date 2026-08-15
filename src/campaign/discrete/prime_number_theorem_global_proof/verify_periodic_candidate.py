#!/usr/bin/env python3
"""Solver-free exact replay of a retained smooth-period construction."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
KINDS = {
    "selberg": (
        HERE / "selberg_squarefree_exact_candidate.json",
        HERE / "selberg_support_receipt.json",
    ),
    "divisor": (
        HERE / "divisor_periodic_exact_candidate.json",
        HERE / "divisor_periodic_receipt.json",
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_fraction(text: str) -> Fraction:
    numerator, denominator = text.split("/", 1)
    return Fraction(int(numerator), int(denominator))


def packet_fraction(packet: dict[str, Any]) -> Fraction:
    return Fraction(int(packet["numerator"]), int(packet["denominator"]))


def decimal_score(coefficients: dict[int, Fraction]) -> Decimal:
    with localcontext() as context:
        context.prec = 70
        return -sum(
            (
                Decimal(value.numerator)
                / Decimal(value.denominator)
                * Decimal(key).ln()
                / Decimal(key)
                for key, value in sorted(coefficients.items())
                if key > 1
            ),
            Decimal(0),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=sorted(KINDS))
    args = parser.parse_args()
    candidate_path, receipt_path = KINDS[args.kind]
    candidate = json.loads(candidate_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    record = receipt["optimized_support_screen"] if args.kind == "selberg" else receipt
    if sha256_file(candidate_path) != record["candidate_sha256"]:
        raise RuntimeError("candidate hash does not match receipt")
    period = int(candidate["period"])
    if period != int(record["period"]):
        raise RuntimeError("period mismatch")
    coefficients = {
        int(key): parse_fraction(value)
        for key, value in candidate["partial_function_rational"].items()
    }
    if 1 not in coefficients or any(key <= 0 for key in coefficients):
        raise ValueError("candidate must include the normalized unit coefficient")
    normalization = sum(
        (value / key for key, value in coefficients.items()), Fraction(0)
    )
    if normalization:
        raise RuntimeError("candidate does not have exact zero mean")
    scale = packet_fraction(record["exact_uniform_scale"])
    lattice = int(record["rounding_denominator"])
    base: dict[int, int] = {}
    for key, value in coefficients.items():
        if key == 1:
            continue
        if period % key:
            raise RuntimeError(f"support key {key} does not divide the period")
        integer = value / scale * lattice
        if integer.denominator != 1:
            raise RuntimeError(f"coefficient {key} is not on the recorded lattice")
        base[key] = integer.numerator
    total = sum(integer * (period // key) for key, integer in base.items())
    direct_bound = period * sum(abs(integer) for integer in base.values())
    if direct_bound >= np.iinfo(np.int64).max:
        raise OverflowError("exact recurrence would overflow int64")
    increments = np.full(period + 1, -total, dtype=np.int64)
    increments[0] = 0
    for key, integer in base.items():
        increments[key::key] += period * integer
    curve = np.cumsum(increments)[:period]
    low_at = int(np.argmin(curve))
    high_at = int(np.argmax(curve))
    denominator = lattice * period
    low = Fraction(int(curve[low_at]), denominator) * scale
    high = Fraction(int(curve[high_at]), denominator) * scale
    if high > 1:
        raise RuntimeError("retained candidate violates the ideal upper bound")
    if low != packet_fraction(record["certified_global_minimum"]):
        raise RuntimeError("minimum mismatch")
    if high != packet_fraction(record["certified_global_maximum"]):
        raise RuntimeError("maximum mismatch")
    score = decimal_score(coefficients)
    recorded_score = Decimal(record["certified_score_decimal"])
    if abs(score - recorded_score) > Decimal("1e-65"):
        raise RuntimeError("score mismatch")
    output = {
        "verified": True,
        "kind": args.kind,
        "period_states_checked": period,
        "support_size_including_one": len(coefficients),
        "normalization": "0",
        "maximum": f"{high.numerator}/{high.denominator}",
        "maximum_at": high_at,
        "minimum_diagnostic": f"{low.numerator}/{low.denominator}",
        "minimum_at": low_at,
        "score_decimal": str(score),
        "candidate_sha256": sha256_file(candidate_path),
        "receipt_sha256": sha256_file(receipt_path),
        "verifier_executed": False,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
