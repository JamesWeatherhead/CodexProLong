#!/usr/bin/env python3
"""Affine Singer/Leech interval-basis sweep for ``difference-bases``.

This is a clean implementation of the construction in Banakh--Gavrylkiv,
Theorem 4.7, specialized first to the four-mark interval basis
``{0, 1, 4, 6}``.  For each prime order ``q`` it constructs a cyclic Singer
difference set in ``Z/(q^2+q+1)``, exhausts every unit multiplier, and chooses
the cyclic cut with the longest empty initial arc.  The resulting integer set
is replayed by the literal Arena formula implemented below.

No downloaded verifier or third-party program is imported or executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


HERE = Path(__file__).resolve().parent
CHECKPOINT = HERE / "checkpoint.json"
LEADER = 2.639027469506608
MIN_IMPROVEMENT = 1e-9
TARGET = LEADER - MIN_IMPROVEMENT
HEIGHTS = (0, 1, 4, 6)
VERIFIER_SHA256 = "a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585"

FieldElement = tuple[int, int, int]


@dataclass(frozen=True)
class SingerRecord:
    q: int
    modulus: int
    polynomial_a: int
    polynomial_b: int
    residue_count: int
    residue_sha256: str
    unit_multipliers: int
    best_multiplier: int
    best_boundary_index: int
    best_boundary_residue: int
    maximum_empty_arc: int
    cardinality: int
    coverage: int
    score: float
    gap_to_gate: float
    candidate_sha256: str
    elapsed_seconds: float


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def canonical_sha256(values: Iterable[int]) -> str:
    raw = json.dumps(list(values), separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def prime_factors(value: int) -> tuple[int, ...]:
    factors: list[int] = []
    divisor = 2
    remaining = value
    while divisor * divisor <= remaining:
        if remaining % divisor == 0:
            factors.append(divisor)
            while remaining % divisor == 0:
                remaining //= divisor
        divisor += 1 if divisor == 2 else 2
    if remaining > 1:
        factors.append(remaining)
    return tuple(factors)


def is_prime(value: int) -> bool:
    if value < 2:
        return False
    if value % 2 == 0:
        return value == 2
    divisor = 3
    while divisor * divisor <= value:
        if value % divisor == 0:
            return False
        divisor += 2
    return True


def field_multiply(
    first: FieldElement,
    second: FieldElement,
    q: int,
    polynomial_a: int,
    polynomial_b: int,
) -> FieldElement:
    """Multiply modulo x^3 + polynomial_a*x + polynomial_b over F_q."""
    a, b, c = first
    d, e, f = second
    cross = b * f + c * e
    return (
        (a * d - polynomial_b * cross) % q,
        (a * e + b * d - polynomial_a * cross - polynomial_b * c * f) % q,
        (a * f + b * e + c * d - polynomial_a * c * f) % q,
    )


def field_power(
    value: FieldElement,
    exponent: int,
    q: int,
    polynomial_a: int,
    polynomial_b: int,
) -> FieldElement:
    result: FieldElement = (1, 0, 0)
    base = value
    power = exponent
    while power:
        if power & 1:
            result = field_multiply(result, base, q, polynomial_a, polynomial_b)
        base = field_multiply(base, base, q, polynomial_a, polynomial_b)
        power >>= 1
    return result


def is_scalar(value: FieldElement) -> bool:
    return value[1] == 0 and value[2] == 0 and value[0] != 0


def irreducible_cubic(q: int, polynomial_a: int, polynomial_b: int) -> bool:
    # A cubic over a field is irreducible exactly when it has no field root.
    return all(
        (root**3 + polynomial_a * root + polynomial_b) % q != 0
        for root in range(q)
    )


def verify_difference_set(residues: list[int], modulus: int) -> None:
    seen = bytearray(modulus)
    for first in residues:
        for second in residues:
            if first == second:
                continue
            difference = (first - second) % modulus
            if difference == 0 or seen[difference]:
                raise RuntimeError("Singer residues are not a planar difference set")
            seen[difference] = 1
    if any(value == 0 for value in seen[1:]):
        raise RuntimeError("Singer residues do not cover every nonzero residue")


def generate_singer(q: int) -> tuple[list[int], int, int]:
    """Return one cyclic Singer set and its defining irreducible cubic."""
    if not is_prime(q):
        raise ValueError(f"this bounded implementation requires prime q, got {q}")
    modulus = q * q + q + 1
    x: FieldElement = (0, 1, 0)
    factors = prime_factors(modulus)
    for polynomial_a in range(q):
        for polynomial_b in range(1, q):
            if not irreducible_cubic(q, polynomial_a, polynomial_b):
                continue
            if not is_scalar(field_power(x, modulus, q, polynomial_a, polynomial_b)):
                continue
            if any(
                is_scalar(
                    field_power(
                        x,
                        modulus // factor,
                        q,
                        polynomial_a,
                        polynomial_b,
                    )
                )
                for factor in factors
            ):
                continue
            residues: list[int] = []
            current: FieldElement = (1, 0, 0)
            for exponent in range(modulus):
                # This two-dimensional F_q hyperplane is a projective line.
                if current[2] == 0:
                    residues.append(exponent)
                current = field_multiply(
                    current, x, q, polynomial_a, polynomial_b
                )
            if len(residues) != q + 1:
                continue
            verify_difference_set(residues, modulus)
            return residues, polynomial_a, polynomial_b
    raise RuntimeError(f"could not construct a projective generator for q={q}")


def longest_affine_gap(residues: list[int], modulus: int) -> dict[str, int]:
    """Exhaust every group automorphism and cyclic cut."""
    base = np.asarray(residues, dtype=np.int64)
    best_gap = -1
    best_multiplier = -1
    best_index = -1
    best_boundary = -1
    units = 0
    for multiplier in range(1, modulus):
        if math.gcd(multiplier, modulus) != 1:
            continue
        units += 1
        scaled = np.sort((base * multiplier) % modulus)
        gaps = np.diff(np.concatenate((scaled, scaled[:1] + modulus)))
        index = int(np.argmax(gaps))
        gap = int(gaps[index])
        if gap > best_gap:
            best_gap = gap
            best_multiplier = multiplier
            best_index = index
            best_boundary = int(scaled[index])
    return {
        "gap": best_gap,
        "multiplier": best_multiplier,
        "boundary_index": best_index,
        "boundary_residue": best_boundary,
        "unit_multipliers": units,
    }


def theorem_candidate(
    residues: list[int], modulus: int, multiplier: int, boundary_residue: int
) -> list[int]:
    """Build the k=0 Theorem-4.7 product and translate its minimum to zero."""
    scaled = sorted((multiplier * value) % modulus for value in residues)
    representatives = sorted(
        ((value - boundary_residue) % modulus) or modulus for value in scaled
    )
    candidate = sorted(
        {
            representative + modulus * height
            for representative in representatives
            for height in HEIGHTS
        }
    )
    origin = candidate[0]
    return [value - origin for value in candidate]


def literal_evaluate(candidate: list[int]) -> tuple[int, float]:
    """Mirror the live verifier with integer arithmetic and return (v, score)."""
    basis = sorted(set(int(value) for value in candidate))
    if 0 not in basis:
        basis = sorted([0, *basis])
    if len(basis) > 2000:
        return 0, float("inf")
    differences = bytearray(basis[-1] - basis[0] + 1)
    for index, first in enumerate(basis):
        for second in basis[index + 1 :]:
            differences[second - first] = 1
    first_missing = next(
        (value for value in range(1, len(differences)) if not differences[value]),
        len(differences),
    )
    coverage = first_missing - 1
    if coverage < 1:
        return coverage, float("inf")
    return coverage, float(len(basis) ** 2 / coverage)


def scan_q(q: int) -> SingerRecord:
    started = time.monotonic()
    residues, polynomial_a, polynomial_b = generate_singer(q)
    modulus = q * q + q + 1
    affine = longest_affine_gap(residues, modulus)
    candidate = theorem_candidate(
        residues,
        modulus,
        affine["multiplier"],
        affine["boundary_residue"],
    )
    coverage, score = literal_evaluate(candidate)
    predicted = 6 * modulus + affine["gap"] - 1
    if coverage != predicted:
        raise RuntimeError(
            f"q={q}: exact coverage {coverage} != construction prediction {predicted}"
        )
    return SingerRecord(
        q=q,
        modulus=modulus,
        polynomial_a=polynomial_a,
        polynomial_b=polynomial_b,
        residue_count=len(residues),
        residue_sha256=canonical_sha256(residues),
        unit_multipliers=affine["unit_multipliers"],
        best_multiplier=affine["multiplier"],
        best_boundary_index=affine["boundary_index"],
        best_boundary_residue=affine["boundary_residue"],
        maximum_empty_arc=affine["gap"],
        cardinality=len(candidate),
        coverage=coverage,
        score=score,
        gap_to_gate=score - TARGET,
        candidate_sha256=canonical_sha256(candidate),
        elapsed_seconds=time.monotonic() - started,
    )


def parse_q_values(raw: str) -> list[int]:
    values: set[int] = set()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            first, last = (int(value) for value in token.split("-", 1))
            values.update(value for value in range(first, last + 1) if is_prime(value))
        else:
            value = int(token)
            if not is_prime(value):
                raise ValueError(f"q must be prime: {value}")
            values.add(value)
    return sorted(values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--q",
        default="59-199",
        help="comma-separated primes and inclusive ranges; ranges retain primes only",
    )
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    q_values = parse_q_values(args.q)
    records: list[dict[str, Any]] = []
    best: dict[str, Any] | None = None
    started = time.monotonic()
    for q in q_values:
        record = asdict(scan_q(q))
        records.append(record)
        if best is None or record["score"] < best["score"]:
            best = record
        output = {
            "method": "Leech-Golay/Theorem-4.7 k=0 with full affine Singer sweep",
            "scope": {
                "q_requested": q_values,
                "q_completed": [item["q"] for item in records],
                "prime_orders_only": True,
                "height_basis": list(HEIGHTS),
                "every_unit_multiplier_and_every_cyclic_cut": True,
            },
            "live": {
                "leader": LEADER,
                "min_improvement": MIN_IMPROVEMENT,
                "target_strictly_below": TARGET,
                "verifier_sha256": VERIFIER_SHA256,
            },
            "records": records,
            "best": best,
            "gate_clearing": bool(best is not None and best["score"] < TARGET),
            "elapsed_seconds": time.monotonic() - started,
        }
        atomic_json(args.checkpoint, output)
        print(
            f"q={q} modulus={record['modulus']} gap={record['maximum_empty_arc']} "
            f"coverage={record['coverage']} score={record['score']:.15g}",
            flush=True,
        )
        if output["gate_clearing"]:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
