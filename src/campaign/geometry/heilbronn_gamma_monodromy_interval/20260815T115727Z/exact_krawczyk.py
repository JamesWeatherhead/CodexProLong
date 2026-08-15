#!/usr/bin/env python3
"""Exact-rational Krawczyk certificate for a real isolated active-system root.

The approximate root and inverse Jacobian are produced with mpmath, rounded to
decimal rationals, and then treated as exact Fractions.  Every inclusion test
after that conversion is exact rational interval arithmetic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable, Sequence

import mpmath as mp

from core import ACTIVE, SIGNS, STRICT_GATE, VARIABLE_NAMES, load_seed


@dataclass(frozen=True)
class Interval:
    lo: Fraction
    hi: Fraction

    def __post_init__(self) -> None:
        if self.lo > self.hi:
            raise ValueError("reversed interval")

    @classmethod
    def point(cls, value: Fraction | int) -> "Interval":
        q = Fraction(value)
        return cls(q, q)

    def __add__(self, other: "Interval" | Fraction | int) -> "Interval":
        rhs = other if isinstance(other, Interval) else Interval.point(other)
        return Interval(self.lo + rhs.lo, self.hi + rhs.hi)

    __radd__ = __add__

    def __neg__(self) -> "Interval":
        return Interval(-self.hi, -self.lo)

    def __sub__(self, other: "Interval" | Fraction | int) -> "Interval":
        rhs = other if isinstance(other, Interval) else Interval.point(other)
        return self + (-rhs)

    def __rsub__(self, other: "Interval" | Fraction | int) -> "Interval":
        return Interval.point(other) - self

    def __mul__(self, other: "Interval" | Fraction | int) -> "Interval":
        rhs = other if isinstance(other, Interval) else Interval.point(other)
        products = (
            self.lo * rhs.lo,
            self.lo * rhs.hi,
            self.hi * rhs.lo,
            self.hi * rhs.hi,
        )
        return Interval(min(products), max(products))

    __rmul__ = __mul__

    def max_abs(self) -> Fraction:
        return max(abs(self.lo), abs(self.hi))


def expand(values: Sequence[object]) -> list[tuple[object, object]]:
    x = values
    return [
        (x[0], 0),
        (x[1], 0),
        (x[2], x[3]),
        (x[4], x[5]),
        (x[6], x[7]),
        (0, x[8]),
        (x[9], x[10]),
        (x[11], 1 - x[11]),
        (0, x[12]),
        (x[13], x[14]),
        (x[15], 1 - x[15]),
    ]


def determinant(points: Sequence[tuple[object, object]], triple: tuple[int, int, int]):
    i, j, k = triple
    bi, ci = points[i]
    bj, cj = points[j]
    bk, ck = points[k]
    return (bj - bi) * (ck - ci) - (cj - ci) * (bk - bi)


def system_mp(values: Sequence[mp.mpf]) -> tuple[mp.matrix, mp.matrix]:
    points = expand(values)
    equations = []
    jacobian = mp.matrix(17, 17)
    for row, triple in enumerate(ACTIVE):
        i, j, k = triple
        bi, ci = points[i]
        bj, cj = points[j]
        bk, ck = points[k]
        sign = SIGNS[triple]
        equations.append(sign * determinant(points, triple) - values[16])
        point_grad = [[mp.mpf("0"), mp.mpf("0")] for _ in range(11)]
        point_grad[i] = [sign * (cj - ck), sign * (bk - bj)]
        point_grad[j] = [sign * (ck - ci), sign * (bi - bk)]
        point_grad[k] = [sign * (ci - cj), sign * (bj - bi)]
        grad = [mp.mpf("0")] * 17
        grad[0] = point_grad[0][0]
        grad[1] = point_grad[1][0]
        grad[2:4] = point_grad[2]
        grad[4:6] = point_grad[3]
        grad[6:8] = point_grad[4]
        grad[8] = point_grad[5][1]
        grad[9:11] = point_grad[6]
        grad[11] = point_grad[7][0] - point_grad[7][1]
        grad[12] = point_grad[8][1]
        grad[13:15] = point_grad[9]
        grad[15] = point_grad[10][0] - point_grad[10][1]
        grad[16] = -1
        for column, value in enumerate(grad):
            jacobian[row, column] = value
    return mp.matrix(equations), jacobian


def decimal_string(value: mp.mpf, digits: int) -> str:
    return mp.nstr(value, n=digits, strip_zeros=False)


def fraction_matrix_rank(matrix: list[list[Fraction]]) -> int:
    work = [row[:] for row in matrix]
    rows = len(work)
    columns = len(work[0])
    rank = 0
    for column in range(columns):
        pivot = next((r for r in range(rank, rows) if work[r][column]), None)
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        pivot_value = work[rank][column]
        work[rank] = [value / pivot_value for value in work[rank]]
        for row in range(rows):
            if row == rank or not work[row][column]:
                continue
            factor = work[row][column]
            work[row] = [
                left - factor * right
                for left, right in zip(work[row], work[rank])
            ]
        rank += 1
        if rank == rows:
            break
    return rank


def system_fraction(values: Sequence[Fraction]) -> list[Fraction]:
    points = expand(values)
    return [
        SIGNS[triple] * determinant(points, triple) - values[16]
        for triple in ACTIVE
    ]


def jacobian_interval(box: Sequence[Interval]) -> list[list[Interval]]:
    points = expand(box)
    result: list[list[Interval]] = []
    zero = Interval.point(0)
    for triple in ACTIVE:
        i, j, k = triple
        bi, ci = points[i]
        bj, cj = points[j]
        bk, ck = points[k]
        sign = SIGNS[triple]
        point_grad = [[zero, zero] for _ in range(11)]
        point_grad[i] = [sign * (cj - ck), sign * (bk - bj)]
        point_grad[j] = [sign * (ck - ci), sign * (bi - bk)]
        point_grad[k] = [sign * (ci - cj), sign * (bj - bi)]
        grad = [zero for _ in range(17)]
        grad[0] = point_grad[0][0]
        grad[1] = point_grad[1][0]
        grad[2:4] = point_grad[2]
        grad[4:6] = point_grad[3]
        grad[6:8] = point_grad[4]
        grad[8] = point_grad[5][1]
        grad[9:11] = point_grad[6]
        grad[11] = point_grad[7][0] - point_grad[7][1]
        grad[12] = point_grad[8][1]
        grad[13:15] = point_grad[9]
        grad[15] = point_grad[10][0] - point_grad[10][1]
        grad[16] = Interval.point(-1)
        result.append(grad)
    return result


def exact_krawczyk_check(certificate: dict[str, object]) -> dict[str, object]:
    center = [Fraction(value) for value in certificate["center"]]
    preconditioner = [
        [Fraction(value) for value in row]
        for row in certificate["preconditioner"]
    ]
    radius = Fraction(certificate["radius"])
    box = [Interval(value - radius, value + radius) for value in center]
    f_center = system_fraction(center)
    jac_box = jacobian_interval(box)
    rank = fraction_matrix_rank(preconditioner)
    term = [
        -sum(preconditioner[i][k] * f_center[k] for k in range(17))
        for i in range(17)
    ]
    matrix: list[list[Interval]] = []
    for i in range(17):
        row = []
        for j in range(17):
            product = Interval.point(0)
            for k in range(17):
                product += preconditioner[i][k] * jac_box[k][j]
            row.append(Interval.point(1 if i == j else 0) - product)
        matrix.append(row)
    row_ratios = []
    krawczyk_bounds = []
    for i in range(17):
        bound = abs(term[i]) + radius * sum(entry.max_abs() for entry in matrix[i])
        krawczyk_bounds.append(bound)
        row_ratios.append(bound / radius)
    maximum_ratio = max(row_ratios)
    z_upper = center[16] + radius
    gate = Fraction(str(STRICT_GATE))
    return {
        "preconditioner_exact_rank": rank,
        "strict_inclusion": bool(rank == 17 and maximum_ratio < 1),
        "maximum_krawczyk_ratio_fraction": f"{maximum_ratio.numerator}/{maximum_ratio.denominator}",
        "maximum_krawczyk_ratio_decimal": float(maximum_ratio),
        "maximum_center_residual_fraction": str(max(abs(value) for value in f_center)),
        "z_upper_fraction": f"{z_upper.numerator}/{z_upper.denominator}",
        "z_upper_decimal": float(z_upper),
        "strict_gate_fraction": f"{gate.numerator}/{gate.denominator}",
        "z_box_strictly_below_gate": bool(z_upper < gate),
        "certified_unique_real_root_in_box": bool(rank == 17 and maximum_ratio < 1),
        "certified_root_cannot_clear_gate": bool(
            rank == 17 and maximum_ratio < 1 and z_upper < gate
        ),
    }


def canonical_hash(value: object) -> str:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("incumbent_krawczyk.json"))
    parser.add_argument("--digits", type=int, default=160)
    parser.add_argument("--stored-digits", type=int, default=110)
    parser.add_argument("--radius", default="1e-70")
    parser.add_argument("--replay", type=Path)
    args = parser.parse_args()

    if args.replay:
        certificate = json.loads(args.replay.read_text())
        result = exact_krawczyk_check(certificate)
        matches = result == certificate["exact_check"]
        print(json.dumps({"matches": matches, **result}, indent=2, sort_keys=True))
        if not matches:
            raise SystemExit(1)
        return

    mp.mp.dps = args.digits
    seed = [mp.mpf(str(value)) for value in load_seed()]
    values = mp.matrix(seed)
    iterations = 0
    for iterations in range(1, 25):
        equations, jacobian = system_mp(values)
        residual = max(abs(value) for value in equations)
        if residual < mp.mpf(10) ** (-(args.stored_digits + 20)):
            break
        values -= mp.lu_solve(jacobian, equations)
    equations, jacobian = system_mp(values)
    inverse = jacobian**-1
    center_strings = [decimal_string(values[i], args.stored_digits) for i in range(17)]
    inverse_strings = [
        [decimal_string(inverse[i, j], args.stored_digits) for j in range(17)]
        for i in range(17)
    ]
    certificate: dict[str, object] = {
        "schema": "heilbronn-exact-rational-krawczyk-v1",
        "system": {
            "variable_names": list(VARIABLE_NAMES),
            "active_triples": [list(triple) for triple in ACTIVE],
            "signs": [SIGNS[triple] for triple in ACTIVE],
            "boundary_elimination": [
                "c0=0",
                "c1=0",
                "b5=0",
                "c7=1-b7",
                "b8=0",
                "c10=1-b10",
            ],
        },
        "generation": {
            "mpmath_digits": args.digits,
            "stored_significant_digits": args.stored_digits,
            "newton_iterations": iterations,
            "mpmath_residual": mp.nstr(max(abs(v) for v in equations), 20),
        },
        "center": center_strings,
        "preconditioner": inverse_strings,
        "radius": args.radius,
    }
    certificate["exact_check"] = exact_krawczyk_check(certificate)
    certificate["certificate_payload_sha256"] = canonical_hash(certificate)
    args.output.write_text(json.dumps(certificate, indent=2, sort_keys=True) + "\n")
    print(json.dumps(certificate["exact_check"], indent=2, sort_keys=True))
    if not certificate["exact_check"]["strict_inclusion"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
