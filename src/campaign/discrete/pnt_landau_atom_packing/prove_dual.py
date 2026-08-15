#!/usr/bin/env python3
"""Exact sparse dual for 52 Bober sporadics dilated by 1 through 100."""

from __future__ import annotations

import json
import math
from fractions import Fraction
from pathlib import Path


HERE = Path(__file__).resolve().parent
TABLE = HERE / "bober_sporadic_52.json"

# HiGHS identified this nonsingular dual basis.  Everything below is rebuilt
# and checked with exact rational arithmetic; these decimals are not used.
DUAL_POINTS = (
    7,
    23,
    481,
    518,
    1397,
    2237,
    2239,
    3523,
    3563,
    4283,
    6041,
    6368,
    6467,
    6479,
    6629,
    7193,
    7579,
    7781,
    7891,
    8099,
    8449,
    8498,
    8567,
)
ACTIVE_ATOMS = (
    (1, 13),
    (1, 43),
    (1, 55),
    (1, 61),
    (2, 43),
    (4, 19),
    (7, 7),
    (10, 8),
    (13, 88),
    (20, 1),
    (23, 47),
    (30, 28),
    (31, 1),
    (31, 7),
    (31, 13),
    (31, 38),
    (31, 73),
    (32, 5),
    (32, 14),
    (35, 5),
    (35, 33),
    (41, 11),
    (49, 7),
)


def factor_exponents(value: int) -> dict[int, int]:
    factors: dict[int, int] = {}
    divisor = 2
    while divisor * divisor <= value:
        while value % divisor == 0:
            factors[divisor] = factors.get(divisor, 0) + 1
            value //= divisor
        divisor += 1
    if value > 1:
        factors[value] = factors.get(value, 0) + 1
    return factors


def score_vector(row: dict, dilation: int) -> dict[int, Fraction]:
    values = row["numerator"] + row["denominator"]
    period = math.lcm(*values)
    result: dict[int, Fraction] = {}
    for sign, vector in ((1, row["numerator"]), (-1, row["denominator"])):
        for value in vector:
            for prime, exponent in factor_exponents(value).items():
                result[prime] = result.get(prime, Fraction()) + Fraction(
                    sign * value * exponent, period * dilation
                )
    return {prime: coefficient for prime, coefficient in result.items() if coefficient}


def atom_value(row: dict, dilation: int, x: int) -> int:
    period = math.lcm(*(row["numerator"] + row["denominator"]))
    quotient = x // dilation
    value = sum(quotient // (period // item) for item in row["numerator"])
    value -= sum(quotient // (period // item) for item in row["denominator"])
    if value not in (0, 1):
        raise ValueError(f"nonbinary atom at line={row['line']} d={dilation} x={x}")
    return value


def solve_fraction(matrix: list[list[int]], rhs: list[Fraction]) -> list[Fraction]:
    size = len(matrix)
    augmented = [
        [Fraction(value) for value in row] + [rhs[index]]
        for index, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot = next(
            (row for row in range(column, size) if augmented[row][column]), None
        )
        if pivot is None:
            raise ValueError("singular dual basis")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(size):
            if row == column or not augmented[row][column]:
                continue
            scale = augmented[row][column]
            augmented[row] = [
                left - scale * right
                for left, right in zip(augmented[row], augmented[column])
            ]
    return [augmented[row][-1] for row in range(size)]


def add_vector(
    target: dict[int, Fraction], source: dict[int, Fraction], scale: int = 1
) -> None:
    for prime, coefficient in source.items():
        target[prime] = target.get(prime, Fraction()) + scale * coefficient
        if not target[prime]:
            del target[prime]


def log_ratio_bounds(numerator: int, denominator: int, terms: int) -> tuple[Fraction, Fraction]:
    if numerator < denominator:
        lower, upper = log_ratio_bounds(denominator, numerator, terms)
        return -upper, -lower
    if numerator == denominator:
        return Fraction(), Fraction()
    z = Fraction(numerator - denominator, numerator + denominator)
    partial = Fraction()
    power = z
    for index in range(terms):
        partial += Fraction(2, 2 * index + 1) * power
        power *= z * z
    remainder = Fraction(2, 2 * terms + 1) * power / (1 - z * z)
    return partial, partial + remainder


def prime_log_bounds(prime: int, terms: int = 80) -> tuple[Fraction, Fraction]:
    log_two = log_ratio_bounds(2, 1, terms)
    if prime == 2:
        return log_two
    exponent = prime.bit_length() - 1
    lower, upper = log_ratio_bounds(prime, 1 << exponent, terms)
    return exponent * log_two[0] + lower, exponent * log_two[1] + upper


def expression_bounds(
    vector: dict[int, Fraction], logs: dict[int, tuple[Fraction, Fraction]]
) -> tuple[Fraction, Fraction]:
    lower = Fraction()
    upper = Fraction()
    for prime, coefficient in vector.items():
        log_lower, log_upper = logs[prime]
        if coefficient >= 0:
            lower += coefficient * log_lower
            upper += coefficient * log_upper
        else:
            lower += coefficient * log_upper
            upper += coefficient * log_lower
    return lower, upper


def directed_decimal(value: Fraction, digits: int, upper: bool) -> str:
    """Render a rigorous decimal endpoint without binary floating conversion."""
    scale = 10**digits
    quotient, remainder = divmod(value.numerator * scale, value.denominator)
    if upper and remainder:
        quotient += 1
    sign = "-" if quotient < 0 else ""
    magnitude = abs(quotient)
    integer, fractional = divmod(magnitude, scale)
    return f"{sign}{integer}.{fractional:0{digits}d}"


def main() -> None:
    rows = json.loads(TABLE.read_text(encoding="utf-8"))["sporadic"]
    by_line = {row["line"]: row for row in rows}
    primes = sorted(
        {
            prime
            for row in rows
            for value in row["numerator"] + row["denominator"]
            for prime in factor_exponents(value)
        }
    )
    matrix = [
        [atom_value(by_line[line], dilation, x) for x in DUAL_POINTS]
        for line, dilation in ACTIVE_ATOMS
    ]
    dual_vectors = [dict() for _ in DUAL_POINTS]
    for prime in primes:
        rhs = [score_vector(by_line[line], dilation).get(prime, Fraction()) for line, dilation in ACTIVE_ATOMS]
        solution = solve_fraction(matrix, rhs)
        for index, coefficient in enumerate(solution):
            if coefficient:
                dual_vectors[index][prime] = coefficient

    objective: dict[int, Fraction] = {}
    for vector in dual_vectors:
        add_vector(objective, vector)
    chebyshev = score_vector(by_line[31], 1)
    if objective != chebyshev:
        raise ValueError("dual objective is not symbolically equal to Chebyshev")
    if any(not atom_value(by_line[31], 1, x) for x in DUAL_POINTS):
        raise ValueError("dual mass is not entirely on Chebyshev-one residues")

    logs = {prime: prime_log_bounds(prime) for prime in primes}
    dual_bounds = [expression_bounds(vector, logs) for vector in dual_vectors]
    if any(lower <= 0 for lower, _ in dual_bounds):
        raise ValueError("a dual weight is not rigorously positive")

    exact_equalities = 0
    strict_slacks: list[tuple[Fraction, int, int]] = []
    for row in rows:
        for dilation in range(1, 101):
            slack: dict[int, Fraction] = {}
            for x, vector in zip(DUAL_POINTS, dual_vectors):
                if atom_value(row, dilation, x):
                    add_vector(slack, vector)
            add_vector(slack, score_vector(row, dilation), scale=-1)
            if not slack:
                exact_equalities += 1
                continue
            lower, _ = expression_bounds(slack, logs)
            if lower <= 0:
                raise ValueError(
                    f"dual does not dominate line={row['line']} d={dilation}"
                )
            strict_slacks.append((lower, row["line"], dilation))

    objective_bounds = expression_bounds(objective, logs)
    minimum_dual = min(lower for lower, _ in dual_bounds)
    minimum_slack, minimum_line, minimum_dilation = min(strict_slacks)
    result = {
        "status": "exact_dual_pass",
        "sporadic_rows": len(rows),
        "dilations_per_row": 100,
        "atoms_proved": len(rows) * 100,
        "dual_support_size": len(DUAL_POINTS),
        "dual_points": list(DUAL_POINTS),
        "symbolic_objective_equals_chebyshev": True,
        "objective_interval": [
            directed_decimal(objective_bounds[0], 30, upper=False),
            directed_decimal(objective_bounds[1], 30, upper=True),
        ],
        "exact_equality_constraints": exact_equalities,
        "strict_constraints": len(strict_slacks),
        "minimum_dual_weight_lower_bound": directed_decimal(
            minimum_dual, 30, upper=False
        ),
        "minimum_strict_slack_lower_bound": directed_decimal(
            minimum_slack, 30, upper=False
        ),
        "minimum_strict_slack_atom": {
            "line": minimum_line,
            "dilation": minimum_dilation,
        },
        "log_bounds_terms": 80,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
