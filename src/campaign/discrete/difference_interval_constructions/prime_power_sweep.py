#!/usr/bin/env python3
"""Complete the k=0 Singer sweep at non-prime prime-power orders q <= 499."""

from __future__ import annotations

import argparse
import itertools
import json
import math
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from sympy.polys.domains import ZZ
from sympy.polys.galoistools import gf_irreducible_p

import search


HERE = Path(__file__).resolve().parent


class BaseField:
    """Small deterministic GF(p^degree), represented in a polynomial basis."""

    def __init__(self, prime: int, degree: int) -> None:
        self.prime = prime
        self.degree = degree
        self.order = prime**degree
        self.modulus = self._first_irreducible_modulus()
        self.coefficients = np.asarray(
            [self._decode(value) for value in range(self.order)], dtype=np.int64
        )
        self.addition = np.empty((self.order, self.order), dtype=np.int32)
        self.multiplication = np.empty((self.order, self.order), dtype=np.int32)
        for first in range(self.order):
            for second in range(self.order):
                self.addition[first, second] = self._encode(
                    (self.coefficients[first] + self.coefficients[second]) % prime
                )
                self.multiplication[first, second] = self._multiply_raw(first, second)
        self.negative = np.asarray(
            [self._encode((-self.coefficients[value]) % prime) for value in range(self.order)],
            dtype=np.int32,
        )

    def _first_irreducible_modulus(self) -> tuple[int, ...]:
        # SymPy's galoistools coefficients are highest-degree first.
        for tail in itertools.product(range(self.prime), repeat=self.degree):
            if tail[-1] == 0:
                continue
            polynomial = [1, *tail]
            if gf_irreducible_p(polynomial, self.prime, ZZ):
                return tuple(reversed(tail))
        raise RuntimeError(
            f"no irreducible polynomial found for GF({self.prime}^{self.degree})"
        )

    def _decode(self, value: int) -> tuple[int, ...]:
        coefficients = []
        remaining = value
        for _ in range(self.degree):
            coefficients.append(remaining % self.prime)
            remaining //= self.prime
        return tuple(coefficients)

    def _encode(self, coefficients: Any) -> int:
        value = 0
        scale = 1
        for coefficient in coefficients:
            value += int(coefficient) * scale
            scale *= self.prime
        return value

    def _multiply_raw(self, first: int, second: int) -> int:
        product = np.convolve(self.coefficients[first], self.coefficients[second]).astype(
            np.int64
        )
        product %= self.prime
        for power in range(len(product) - 1, self.degree - 1, -1):
            coefficient = int(product[power]) % self.prime
            if coefficient == 0:
                continue
            offset = power - self.degree
            for index, modulus_coefficient in enumerate(self.modulus):
                product[offset + index] -= coefficient * modulus_coefficient
                product[offset + index] %= self.prime
        return self._encode(product[: self.degree] % self.prime)

    def add(self, first: int, second: int) -> int:
        return int(self.addition[first, second])

    def negate(self, value: int) -> int:
        return int(self.negative[value])

    def subtract(self, first: int, second: int) -> int:
        return self.add(first, self.negate(second))

    def multiply(self, first: int, second: int) -> int:
        return int(self.multiplication[first, second])

    def power(self, value: int, exponent: int) -> int:
        result = 1
        base = value
        remaining = exponent
        while remaining:
            if remaining & 1:
                result = self.multiply(result, base)
            base = self.multiply(base, base)
            remaining >>= 1
        return result


TowerElement = tuple[int, int, int]


def tower_multiply(
    field: BaseField,
    first: TowerElement,
    second: TowerElement,
    polynomial_a: int,
    polynomial_b: int,
) -> TowerElement:
    a, b, c = first
    d, e, f = second
    cross = field.add(field.multiply(b, f), field.multiply(c, e))
    constant = field.subtract(field.multiply(a, d), field.multiply(polynomial_b, cross))
    linear = field.add(field.multiply(a, e), field.multiply(b, d))
    linear = field.subtract(linear, field.multiply(polynomial_a, cross))
    linear = field.subtract(linear, field.multiply(polynomial_b, field.multiply(c, f)))
    quadratic = field.add(field.multiply(a, f), field.multiply(b, e))
    quadratic = field.add(quadratic, field.multiply(c, d))
    quadratic = field.subtract(
        quadratic, field.multiply(polynomial_a, field.multiply(c, f))
    )
    return constant, linear, quadratic


def tower_power(
    field: BaseField,
    value: TowerElement,
    exponent: int,
    polynomial_a: int,
    polynomial_b: int,
) -> TowerElement:
    result: TowerElement = (1, 0, 0)
    base = value
    remaining = exponent
    while remaining:
        if remaining & 1:
            result = tower_multiply(
                field, result, base, polynomial_a, polynomial_b
            )
        base = tower_multiply(field, base, base, polynomial_a, polynomial_b)
        remaining >>= 1
    return result


def tower_is_scalar(value: TowerElement) -> bool:
    return value[0] != 0 and value[1] == 0 and value[2] == 0


def tower_cubic_has_root(field: BaseField, polynomial_a: int, polynomial_b: int) -> bool:
    for value in range(field.order):
        cube = field.power(value, 3)
        result = field.add(cube, field.multiply(polynomial_a, value))
        result = field.add(result, polynomial_b)
        if result == 0:
            return True
    return False


def find_projective_generator(
    field: BaseField,
    polynomial_a: int,
    polynomial_b: int,
) -> TowerElement | None:
    modulus = field.order * field.order + field.order + 1
    factors = search.prime_factors(modulus)
    for value in itertools.product(range(field.order), repeat=3):
        if value == (0, 0, 0) or tower_is_scalar(value):
            continue
        if not tower_is_scalar(
            tower_power(field, value, modulus, polynomial_a, polynomial_b)
        ):
            continue
        if any(
            tower_is_scalar(
                tower_power(
                    field,
                    value,
                    modulus // factor,
                    polynomial_a,
                    polynomial_b,
                )
            )
            for factor in factors
        ):
            continue
        return value
    return None


def generate_singer_prime_power(
    prime: int, degree: int
) -> tuple[list[int], BaseField, int, int, TowerElement]:
    field = BaseField(prime, degree)
    q = field.order
    modulus = q * q + q + 1
    for polynomial_a in range(q):
        for polynomial_b in range(1, q):
            if tower_cubic_has_root(field, polynomial_a, polynomial_b):
                continue
            generator = find_projective_generator(
                field, polynomial_a, polynomial_b
            )
            if generator is None:
                continue
            residues = []
            current: TowerElement = (1, 0, 0)
            for exponent in range(modulus):
                if current[2] == 0:
                    residues.append(exponent)
                current = tower_multiply(
                    field, current, generator, polynomial_a, polynomial_b
                )
            if len(residues) != q + 1:
                continue
            search.verify_difference_set(residues, modulus)
            return residues, field, polynomial_a, polynomial_b, generator
    raise RuntimeError(f"no projective generator found for q={q}")


def prime_power_decomposition(value: int) -> tuple[int, int] | None:
    for prime in range(2, value + 1):
        if not search.is_prime(prime):
            continue
        power = prime * prime
        degree = 2
        while power <= value:
            if power == value:
                return prime, degree
            power *= prime
            degree += 1
    return None


def nonprime_prime_powers(limit: int = 499) -> list[int]:
    return [
        value
        for value in range(4, limit + 1)
        if not search.is_prime(value) and prime_power_decomposition(value) is not None
    ]


def scan_q(q: int) -> dict[str, Any]:
    started = time.monotonic()
    decomposition = prime_power_decomposition(q)
    if decomposition is None or search.is_prime(q):
        raise ValueError(f"q is not a non-prime prime power: {q}")
    prime, degree = decomposition
    residues, field, polynomial_a, polynomial_b, generator = (
        generate_singer_prime_power(prime, degree)
    )
    modulus = q * q + q + 1
    affine = search.longest_affine_gap(residues, modulus)
    candidate = search.theorem_candidate(
        residues, modulus, affine["multiplier"], affine["boundary_residue"]
    )
    coverage, score = search.literal_evaluate(candidate)
    predicted = 6 * modulus + affine["gap"] - 1
    if coverage != predicted:
        raise RuntimeError(f"q={q}: exact coverage {coverage} != {predicted}")
    return {
        "q": q,
        "base_prime": prime,
        "base_degree": degree,
        "base_modulus_low_to_high": list(field.modulus),
        "tower_polynomial_a": polynomial_a,
        "tower_polynomial_b": polynomial_b,
        "tower_projective_generator": list(generator),
        "modulus": modulus,
        "residue_count": len(residues),
        "residue_sha256": search.canonical_sha256(residues),
        "unit_multipliers": affine["unit_multipliers"],
        "best_multiplier": affine["multiplier"],
        "best_boundary_index": affine["boundary_index"],
        "best_boundary_residue": affine["boundary_residue"],
        "maximum_empty_arc": affine["gap"],
        "cardinality": len(candidate),
        "coverage": coverage,
        "score": score,
        "gap_to_gate": score - search.TARGET,
        "candidate_sha256": search.canonical_sha256(candidate),
        "elapsed_seconds": time.monotonic() - started,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--q",
        default=",".join(map(str, nonprime_prime_powers())),
        help="comma-separated non-prime prime powers",
    )
    parser.add_argument(
        "--checkpoint", type=Path, default=HERE / "prime_power_checkpoint.json"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    q_values = [int(token) for token in args.q.split(",") if token.strip()]
    records = []
    output: dict[str, Any] = {
        "method": "Theorem-4.7 k=0 full affine non-prime prime-power Singer sweep",
        "scope": {
            "q_requested": q_values,
            "q_completed": [],
            "every_unit_multiplier_and_cyclic_cut": True,
            "height_basis": list(search.HEIGHTS),
        },
        "live": {
            "leader": search.LEADER,
            "min_improvement": search.MIN_IMPROVEMENT,
            "target_strictly_below": search.TARGET,
            "verifier_sha256": search.VERIFIER_SHA256,
        },
        "records": records,
        "best": None,
        "gate_clearing": False,
    }
    started = time.monotonic()
    for q in q_values:
        record = scan_q(q)
        records.append(record)
        output["scope"]["q_completed"].append(q)
        output["best"] = min(records, key=lambda item: float(item["score"]))
        output["gate_clearing"] = output["best"]["score"] < search.TARGET
        output["elapsed_seconds"] = time.monotonic() - started
        search.atomic_json(args.checkpoint, output)
        print(
            f"q={q}={record['base_prime']}^{record['base_degree']} "
            f"gap={record['maximum_empty_arc']} coverage={record['coverage']} "
            f"score={record['score']:.15g}",
            flush=True,
        )
        if output["gate_clearing"]:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
