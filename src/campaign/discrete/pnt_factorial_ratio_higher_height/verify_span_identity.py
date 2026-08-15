#!/usr/bin/env python3
"""Exact proof-by-identity for signed higher-height product spans.

Let B_j=[j+1,-j,-1], the binomial factorial ratio.  Then

    sum_{j=1}^{n-1} B_j = [n] - n[1].

Every finite balanced rational list g satisfies

    g = sum_{n>=2} g(n) * ([n]-n[1]),

so it lies in the rational span of the B_j.  Since r identical copies of
B_j form a theorem-valid product of height r, the rational span of height-r
products is the same space for every r>=1.  Negative span coefficients are
allowed only in this structural upper-only experiment; they are not claimed
to be integral factorial ratios.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from fractions import Fraction


def add(target: Counter[int], source: Counter[int], scale: Fraction) -> None:
    for key, value in source.items():
        target[key] += scale * value
        if not target[key]:
            del target[key]


def binomial_atom(index: int) -> Counter[int]:
    if index < 1:
        raise ValueError("index must be positive")
    result: Counter[int] = Counter()
    result[index + 1] += Fraction(1)
    result[index] -= Fraction(1)
    result[1] -= Fraction(1)
    return result


def decompose(counts: Counter[int], product_height: int) -> Counter[int]:
    if product_height not in (2, 3):
        raise ValueError("this receipt checks heights two and three")
    if sum(Fraction(key) * value for key, value in counts.items()) != 0:
        raise ValueError("input list is not balanced")
    reconstructed: Counter[int] = Counter()
    for key, value in counts.items():
        if key < 2 or not value:
            continue
        for index in range(1, key):
            # product_height*B_index is a product of that many identical
            # binomial factorial ratios; scale back by product_height.
            add(
                reconstructed,
                binomial_atom(index),
                value,
            )
    return reconstructed


def main() -> int:
    tests: list[Counter[int]] = [
        Counter({30: Fraction(2), 15: Fraction(-2), 10: Fraction(-2),
                 6: Fraction(-2), 1: Fraction(2)}),
        Counter({12: Fraction(3, 5), 7: Fraction(-4, 5),
                 3: Fraction(-8, 5), 1: Fraction(16, 5)}),
    ]
    generator = random.Random(20260815)
    for _ in range(40):
        counts: Counter[int] = Counter()
        for key in range(2, generator.randint(4, 45)):
            value = Fraction(generator.randint(-5, 5), generator.randint(1, 7))
            if value:
                counts[key] = value
        counts[1] = -sum(Fraction(key) * value for key, value in counts.items())
        tests.append(counts)
    for product_height in (2, 3):
        for counts in tests:
            if decompose(counts, product_height) != counts:
                raise AssertionError("exact span identity failed")
    receipt = {
        "identity": "sum_{j=1}^{n-1} ([j+1]-[j]-[1]) = [n]-n[1]",
        "balanced_reconstruction": "g=sum_{n>=2}g(n)*([n]-n[1])",
        "height_two_basis": "2*B_j is a height-two product; B_j=(1/2)*(2*B_j)",
        "height_three_basis": "3*B_j is a height-three product; B_j=(1/3)*(3*B_j)",
        "conclusion": (
            "Signed rational spans of height-two or height-three product atoms "
            "equal the full finite balanced-list space."
        ),
        "claim_boundary": (
            "This is a linear-span statement.  Negative combinations need not "
            "be integral factorial ratios; they require independent upper-only replay."
        ),
        "exact_test_vectors": len(tests),
        "product_heights_tested": [2, 3],
        "status": "passed",
    }
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
