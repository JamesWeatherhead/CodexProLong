#!/usr/bin/env python3
"""Bounded exact-period screen of finite Selberg-sieve support families.

The cited Selberg construction is used only to define a finite support.  Every
claim made here is independently checked for the floor-sum problem.  For a
zero-mean function supported on divisors of ``L``,

    S(m) = sum_k f(k) floor(m/k) = -sum_{k>1} f(k) (m mod k)/k

is ``L``-periodic.  This permits a complete integer scan, which also covers
all real x because floor sums are constant on [m,m+1).

The optimizer is merely a candidate generator.  Its result is rounded to a
small common rational denominator, uniformly scaled after an exact integer
scan, and only that rational certificate is reported as globally feasible.
No downloaded verifier code is imported or executed.
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
CHECKPOINT = HERE / "selberg_master_checkpoint.json"
OUTPUT = HERE / "selberg_support_receipt.json"
CANDIDATE = HERE / "selberg_squarefree_exact_candidate.json"
SOURCE_URL = (
    "https://paperclip.gxl.ai/citations/papers/"
    "arx_2208.05762#L39-L50"
)
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


def mobius(n: int) -> int:
    value = n
    sign = 1
    prime = 2
    while prime * prime <= value:
        if value % prime == 0:
            value //= prime
            sign = -sign
            if value % prime == 0:
                return 0
            while value % prime == 0:
                value //= prime
        prime += 1
    return -sign if value > 1 else sign


def totient(n: int) -> int:
    result = n
    value = n
    prime = 2
    while prime * prime <= value:
        if value % prime == 0:
            while value % prime == 0:
                value //= prime
            result -= result // prime
        prime += 1
    if value > 1:
        result -= result // value
    return result


def selberg_weights(z: int) -> tuple[Fraction, dict[int, Fraction], dict[int, Fraction]]:
    """Return exact G(z), rho_d, and lambda_d from the cited formulas."""
    total = sum(
        (Fraction(mobius(n) ** 2, totient(n)) for n in range(1, z + 1)),
        Fraction(0),
    )
    rho: dict[int, Fraction] = {}
    for divisor in range(1, z + 1):
        mu = mobius(divisor)
        if not mu:
            continue
        tail = sum(
            (
                Fraction(mobius(n) ** 2, totient(n))
                for n in range(divisor, z + 1, divisor)
            ),
            Fraction(0),
        )
        rho[divisor] = Fraction(divisor * mu, 1) * tail / total
    weights: dict[int, Fraction] = {}
    for first, first_value in rho.items():
        for second, second_value in rho.items():
            key = math.lcm(first, second)
            weights[key] = weights.get(key, Fraction(0)) + first_value * second_value
    return total, rho, weights


def normalized(weights: dict[int, Fraction]) -> dict[int, Fraction]:
    result = dict(weights)
    mean = sum((value / key for key, value in result.items()), Fraction(0))
    result[1] = result.get(1, Fraction(0)) - mean
    assert sum((value / key for key, value in result.items()), Fraction(0)) == 0
    return {key: value for key, value in result.items() if value}


def exact_period_range(
    coefficients: dict[int, Fraction], period: int, chunk_size: int
) -> tuple[Fraction, int, Fraction, int]:
    """Complete exact scan using a common denominator and int64 numerators."""
    common = 1
    for key, value in coefficients.items():
        if key != 1:
            common = math.lcm(common, (value / key).denominator)
    terms = [
        (key, int((value / key) * common))
        for key, value in coefficients.items()
        if key != 1 and value
    ]
    worst_bound = sum(abs(integer) * (key - 1) for key, integer in terms)
    if worst_bound >= np.iinfo(np.int64).max:
        raise OverflowError(f"exact numerator bound {worst_bound} exceeds int64")
    low = 0
    high = 0
    low_at = 0
    high_at = 0
    for start in range(0, period, chunk_size):
        rows = np.arange(start, min(period, start + chunk_size), dtype=np.int64)
        values = np.zeros(len(rows), dtype=np.int64)
        for key, integer in terms:
            values -= integer * (rows % key)
        local_low = int(np.argmin(values))
        local_high = int(np.argmax(values))
        if int(values[local_low]) < low:
            low = int(values[local_low])
            low_at = int(rows[local_low])
        if int(values[local_high]) > high:
            high = int(values[local_high])
            high_at = int(rows[local_high])
    return Fraction(low, common), low_at, Fraction(high, common), high_at


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


def fraction_packet(value: Fraction) -> dict[str, str]:
    with localcontext() as context:
        context.prec = 60
        decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return {
        "numerator": str(value.numerator),
        "denominator": str(value.denominator),
        "decimal": str(decimal),
    }


def pure_screen(z: int, chunk_size: int) -> dict[str, Any]:
    total, rho, weights = selberg_weights(z)
    coefficients = normalized(weights)
    period = math.lcm(*weights)
    low, low_at, high, high_at = exact_period_range(coefficients, period, chunk_size)
    # The mathematical inequality is one-sided: negative excursions are
    # unrestricted.  Saturate the positive maximum, subject to |f(k)|<=10 on
    # submitted (non-unit) coordinates.
    coordinate_scale = min(
        (Fraction(10, 1) / abs(value) for key, value in coefficients.items() if key != 1),
        default=Fraction(1),
    )
    positive_scale = Fraction(1, 1) / high if high > 0 else coordinate_scale
    scale = min(coordinate_scale, positive_scale)
    scaled = {key: value * scale for key, value in coefficients.items()}
    if any(abs(value) > 10 for key, value in scaled.items() if key != 1):
        raise RuntimeError("pure Selberg rescaling exceeded the coordinate bound")
    return {
        "z": z,
        "G": fraction_packet(total),
        "rho_support_size": len(rho),
        "lambda_support_size": len(weights),
        "period": period,
        "unscaled_exact_minimum": fraction_packet(low),
        "unscaled_exact_minimum_at": low_at,
        "unscaled_exact_maximum": fraction_packet(high),
        "unscaled_exact_maximum_at": high_at,
        "global_feasibility_scale": fraction_packet(scale),
        "globally_feasible_score_decimal": str(decimal_score(scaled)),
    }


def scan_float_range(
    keys: np.ndarray, values: np.ndarray, period: int, chunk_size: int, keep: int
) -> tuple[float, int, float, int, list[int]]:
    highest: list[tuple[float, int]] = []
    lowest: list[tuple[float, int]] = []
    for start in range(0, period, chunk_size):
        rows = np.arange(start, min(period, start + chunk_size), dtype=np.int64)
        matrix = -((rows[:, None] % keys[None, :]) / keys[None, :])
        curve = matrix @ values
        count = min(keep, len(rows))
        high_indices = np.argpartition(curve, -count)[-count:]
        low_indices = np.argpartition(curve, count - 1)[:count]
        highest.extend((float(curve[index]), int(rows[index])) for index in high_indices)
        lowest.extend((float(curve[index]), int(rows[index])) for index in low_indices)
    highest.sort(reverse=True)
    lowest.sort()
    selected = [row for _, row in highest[:keep]] + [row for _, row in lowest[:keep]]
    return lowest[0][0], lowest[0][1], highest[0][0], highest[0][1], selected


def optimize_support(
    z: int, chunk_size: int, max_iterations: int, rounding_denominator: int
) -> dict[str, Any]:
    _, rho, _ = selberg_weights(z)
    support = sorted(
        {math.lcm(first, second) for first in rho for second in rho} - {1}
    )
    keys = np.asarray(support, dtype=np.int64)
    period = math.lcm(*support)
    costs = np.log(keys.astype(np.float64)) / keys
    initial = min(period, 30_030)
    rows = set(range(initial))
    rows.update(
        map(int, np.linspace(0, period - 1, min(period, 12_000), dtype=np.int64))
    )
    values: np.ndarray | None = None
    history: list[dict[str, Any]] = []
    for iteration in range(max_iterations):
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
            raise RuntimeError(f"support LP failed: {result.message}")
        values = np.asarray(result.x, dtype=np.float64)
        low, low_at, high, high_at, new_rows = scan_float_range(
            keys, values, period, chunk_size, 128
        )
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
                "z": z,
                "period": period,
                "support": support,
                "history": history,
                "latest_values": [repr(float(value)) for value in values],
                "candidate_generator_only": True,
            },
        )
        if high <= 1.0 + 2e-8:
            break
        before = len(rows)
        rows.update(new_rows[:128])
        if len(rows) == before:
            break
    if values is None:
        raise AssertionError("optimizer did not run")

    # Round onto a small common rational lattice, then certify/scale exactly.
    integers = np.rint(values * rounding_denominator).astype(np.int64)
    rational = {
        int(key): Fraction(int(integer), rounding_denominator)
        for key, integer in zip(keys, integers, strict=True)
        if integer
    }
    rational[1] = -sum((value / key for key, value in rational.items()), Fraction(0))
    exact_low, exact_low_at, exact_high, exact_high_at = exact_period_range(
        rational, period, chunk_size
    )
    coordinate_scale = min(
        (
            Fraction(10, 1) / abs(value)
            for key, value in rational.items()
            if key != 1
        ),
        default=Fraction(1),
    )
    positive_scale = Fraction(1, 1) / exact_high if exact_high > 0 else coordinate_scale
    scale = min(coordinate_scale, positive_scale)
    certified = {key: value * scale for key, value in rational.items()}
    certified_low = exact_low * scale
    certified_high = exact_high * scale
    if certified_high > 1:
        raise AssertionError("exact uniform scale failed")
    atomic_json(
        CANDIDATE,
        {
            "coefficient_model": "exact rational; f(1) included",
            "z": z,
            "period": period,
            "construction": {
                "rounding_denominator": rounding_denominator,
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
                for key, value in sorted(certified.items())
            },
        },
    )
    score = decimal_score(certified)
    return {
        "z": z,
        "support_size_excluding_one": len(support),
        "period": period,
        "iterations": len(history),
        "history": history,
        "rounding_denominator": rounding_denominator,
        "pre_scale_exact_minimum": fraction_packet(exact_low),
        "pre_scale_exact_minimum_at": exact_low_at,
        "pre_scale_exact_maximum": fraction_packet(exact_high),
        "pre_scale_exact_maximum_at": exact_high_at,
        "exact_uniform_scale": fraction_packet(scale),
        "certified_global_minimum": fraction_packet(certified_low),
        "certified_global_maximum": fraction_packet(certified_high),
        "certified_score_decimal": str(score),
        "gap_to_historical_gate_decimal": str(score - HISTORICAL_GATE),
        "candidate_sha256": sha256_file(CANDIDATE),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--z", type=int, default=19)
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--chunk-size", type=int, default=500_000)
    parser.add_argument("--rounding-denominator", type=int, default=1_000_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.z < 2 or args.max_iterations < 1 or args.rounding_denominator < 1:
        raise ValueError("invalid positive screen parameter")
    pure = [pure_screen(z, args.chunk_size) for z in (2, 3, 5, 7, 11, 13, 17, 19)]
    optimized = optimize_support(
        args.z, args.chunk_size, args.max_iterations, args.rounding_denominator
    )
    output = {
        "scope": "finite standard Selberg weights and their induced squarefree-lcm support",
        "source": SOURCE_URL,
        "source_role": "support/candidate generator only; no theorem transfer claimed",
        "identity": (
            "For exact zero mean and support dividing L, S(m)="
            "-sum_{k>1} f(k)(m mod k)/k is L-periodic."
        ),
        "all_real_reduction": "The floor sum is constant on every [m,m+1).",
        "pure_weight_screens": pure,
        "optimized_support_screen": optimized,
        "historical_gate": str(HISTORICAL_GATE),
        "conclusion": "bounded changed-support screen is globally upper-valid; negative values are unrestricted",
        "verifier_executed": False,
        "external_actions": "none",
    }
    atomic_json(OUTPUT, output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
