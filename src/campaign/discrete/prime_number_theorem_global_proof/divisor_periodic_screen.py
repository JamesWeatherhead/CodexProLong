#!/usr/bin/env python3
"""Exact-period LP screen on all divisors of a smooth modulus.

This is a changed-support experiment motivated by finite divisor-sieve
weights.  The floating-point LP only proposes coefficients.  The retained
candidate is rounded to a common rational lattice and certified over every
state of its complete period using integer recurrence arithmetic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linprog


HERE = Path(__file__).resolve().parent
CHECKPOINT = HERE / "divisor_periodic_checkpoint.json"
CANDIDATE = HERE / "divisor_periodic_exact_candidate.json"
OUTPUT = HERE / "divisor_periodic_receipt.json"
HISTORICAL_GATE = Decimal("0.9976498835182795")


def atomic_json(path: Path, value: Any) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def divisors(number: int) -> list[int]:
    result: list[int] = []
    for divisor in range(1, math.isqrt(number) + 1):
        if number % divisor:
            continue
        result.append(divisor)
        if divisor * divisor != number:
            result.append(number // divisor)
    return sorted(result)


def float_period_curve(keys: np.ndarray, values: np.ndarray, period: int) -> np.ndarray:
    mean = float(np.sum(values / keys))
    increments = np.full(period + 1, -mean, dtype=np.float64)
    increments[0] = 0.0
    for key, value in zip(keys, values, strict=True):
        increments[int(key) :: int(key)] += float(value)
    return np.cumsum(increments)[:period]


def exact_period_curve(
    keys: np.ndarray, integers: np.ndarray, denominator: int, period: int
) -> tuple[int, int, int, int, int]:
    """Return exact numerator extrema for f(k)=integers[k]/denominator.

    The common output denominator is denominator*period.  Eliminating f(1)
    gives increment numerator ``-T + period*n_k`` on multiples of k, where
    ``T=sum n_k*period/k``.
    """
    total = sum(
        int(integer) * (period // int(key))
        for key, integer in zip(keys, integers, strict=True)
    )
    direct_bound = period * sum(map(abs, map(int, integers)))
    if direct_bound >= np.iinfo(np.int64).max:
        raise OverflowError(f"exact numerator bound {direct_bound} exceeds int64")
    increments = np.full(period + 1, -total, dtype=np.int64)
    increments[0] = 0
    for key, integer in zip(keys, integers, strict=True):
        increments[int(key) :: int(key)] += period * int(integer)
    curve = np.cumsum(increments)[:period]
    low_at = int(np.argmin(curve))
    high_at = int(np.argmax(curve))
    return (
        int(curve[low_at]),
        low_at,
        int(curve[high_at]),
        high_at,
        denominator * period,
    )


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


def packet(value: Fraction) -> dict[str, str]:
    with localcontext() as context:
        context.prec = 60
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return {
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
        "decimal": str(decimal),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", type=int, default=510_510)
    parser.add_argument("--max-iterations", type=int, default=20)
    parser.add_argument("--rounding-denominator", type=int, default=1_000_000)
    parser.add_argument("--bundle-size", type=int, default=256)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.period < 2 or args.max_iterations < 1 or args.rounding_denominator < 1:
        raise ValueError("invalid positive screen parameter")
    support = divisors(args.period)
    if support[0] != 1:
        raise AssertionError("unit divisor missing")
    keys = np.asarray(support[1:], dtype=np.int64)
    costs = np.log(keys.astype(np.float64)) / keys
    history: list[dict[str, Any]] = []
    if args.resume:
        saved = json.loads(CHECKPOINT.read_text())
        if int(saved["period"]) != args.period or "constraint_rows" not in saved:
            raise RuntimeError("checkpoint is absent, legacy, or for another period")
        rows = set(map(int, saved["constraint_rows"]))
        history = list(saved["history"])
    else:
        rows = set(range(min(args.period, 30_030)))
        rows.update(
            map(
                int,
                np.linspace(
                    0, args.period - 1, min(args.period, 12_000), dtype=np.int64
                ),
            )
        )
    values: np.ndarray | None = None
    for iteration in range(args.max_iterations):
        row_array = np.asarray(sorted(rows), dtype=np.int64)
        matrix = -((row_array[:, None] % keys[None, :]) / keys[None, :])
        result = linprog(
            costs,
            A_ub=matrix,
            b_ub=np.ones(len(row_array), dtype=np.float64),
            bounds=(-10.0, 10.0),
            method="highs",
            options={
                "primal_feasibility_tolerance": 1e-9,
                "dual_feasibility_tolerance": 1e-9,
            },
        )
        if not result.success:
            raise RuntimeError(f"periodic divisor LP failed: {result.message}")
        values = np.asarray(result.x, dtype=np.float64)
        curve = float_period_curve(keys, values, args.period)
        low_at = int(np.argmin(curve))
        high_at = int(np.argmax(curve))
        low = float(curve[low_at])
        high = float(curve[high_at])
        history.append(
            {
                "iteration": iteration,
                "master_rows": len(rows),
                "solver_score": -float(result.fun),
                "full_period_float_minimum": low,
                "full_period_float_minimum_at": low_at,
                "full_period_float_maximum": high,
                "full_period_float_maximum_at": high_at,
            }
        )
        atomic_json(
            CHECKPOINT,
            {
                "period": args.period,
                "support": support,
                "history": history,
                "latest_values": [repr(float(value)) for value in values],
                "constraint_rows": sorted(rows),
                "candidate_generator_only": True,
            },
        )
        if high <= 1.0 + 2e-8:
            break
        count = min(args.bundle_size, args.period)
        high_rows = np.argpartition(curve, -count)[-count:]
        before = len(rows)
        rows.update(map(int, high_rows))
        if len(rows) == before:
            break
    if values is None:
        raise AssertionError("optimizer did not run")

    integers = np.rint(values * args.rounding_denominator).astype(np.int64)
    low_num, low_at, high_num, high_at, common = exact_period_curve(
        keys, integers, args.rounding_denominator, args.period
    )
    unscaled = {
        int(key): Fraction(int(integer), args.rounding_denominator)
        for key, integer in zip(keys, integers, strict=True)
        if integer
    }
    coordinate_scale = min(
        (Fraction(10, 1) / abs(value) for value in unscaled.values()),
        default=Fraction(1),
    )
    positive_scale = Fraction(common, high_num) if high_num > 0 else coordinate_scale
    scale = min(coordinate_scale, positive_scale)
    coefficients = {key: value * scale for key, value in unscaled.items()}
    coefficients[1] = -sum(
        (value / key for key, value in coefficients.items()), Fraction(0)
    )
    if any(abs(value) > 10 for key, value in coefficients.items() if key != 1):
        raise RuntimeError("certified candidate exceeded the submitted coordinate bound")
    exact_low = Fraction(low_num, common) * scale
    exact_high = Fraction(high_num, common) * scale
    if exact_high > 1:
        raise AssertionError("complete-period scale failed")
    atomic_json(
        CANDIDATE,
        {
            "coefficient_model": "exact rational; f(1) included",
            "period": args.period,
            "construction": {
                "rounding_denominator": args.rounding_denominator,
                "integer_coefficients_excluding_one": {
                    str(key): int(integer)
                    for key, integer in zip(keys, integers, strict=True)
                    if integer
                },
                "uniform_scale": f"{scale.numerator}/{scale.denominator}",
                "unit_coefficient_rule": "f(1)=-sum_{k>1}f(k)/k",
            },
            "partial_function_rational": {
                str(key): f"{value.numerator}/{value.denominator}"
                for key, value in sorted(coefficients.items())
            },
        },
    )
    score = decimal_score(coefficients)
    output = {
        "scope": "all-divisors support of one smooth period",
        "period": args.period,
        "support_size_including_one": len(support),
        "identity": (
            "Exact zero mean makes S(m)=-sum_{k>1}f(k)(m mod k)/k "
            "periodic modulo L."
        ),
        "all_real_reduction": "The floor sum is constant on each [m,m+1).",
        "optimizer_role": "candidate generator only",
        "iterations": len(history),
        "history": history,
        "rounding_denominator": args.rounding_denominator,
        "pre_scale_exact_minimum": packet(Fraction(low_num, common)),
        "pre_scale_exact_minimum_at": low_at,
        "pre_scale_exact_maximum": packet(Fraction(high_num, common)),
        "pre_scale_exact_maximum_at": high_at,
        "exact_uniform_scale": packet(scale),
        "certified_global_minimum": packet(exact_low),
        "certified_global_maximum": packet(exact_high),
        "certified_score_decimal": str(score),
        "historical_gate": str(HISTORICAL_GATE),
        "gap_to_historical_gate_decimal": str(score - HISTORICAL_GATE),
        "candidate_sha256": sha256_file(CANDIDATE),
        "verifier_executed": False,
        "external_actions": "none",
    }
    atomic_json(OUTPUT, output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
