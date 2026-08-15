#!/usr/bin/env python3
"""Small deterministic regression suite for the exact Difference Bases tools."""

from __future__ import annotations

import unittest
from fractions import Fraction

from exact import coverage, difference_bits, first_missing, load_live, replay
from relative_graph_search import Parameters, construct


class ExactTests(unittest.TestCase):
    def test_sparse_ruler(self) -> None:
        values = [0, 1, 4, 6]
        bits = difference_bits(values)
        self.assertEqual(first_missing(bits), 7)
        self.assertEqual(coverage(values), 6)

    def test_frozen_leader_replay(self) -> None:
        live = load_live()
        result = replay(live["leader_values"], live)
        self.assertEqual(result["coverage"], 49_109)
        self.assertEqual(Fraction(result["score_fraction"]), Fraction(129_600, 49_109))
        self.assertFalse(result["gate_cleared"])

    def test_quadratic_graph_relative_difference_property(self) -> None:
        # Before integer carry embedding, {(x,x^2)} covers each modular pair
        # with nonzero first coordinate exactly once as a directed difference.
        p = 7
        graph = [(x, x * x % p) for x in range(p)]
        counts: dict[tuple[int, int], int] = {}
        for first in graph:
            for second in graph:
                if first == second:
                    continue
                delta = ((first[0] - second[0]) % p, (first[1] - second[1]) % p)
                counts[delta] = counts.get(delta, 0) + 1
        for x in range(p):
            for y in range(p):
                expected = 1 if x else 0
                self.assertEqual(counts.get((x, y), 0), expected)

    def test_constructor_has_four_disjoint_blocks(self) -> None:
        parameters = Parameters(
            p=7,
            heights=(0, 1, 4, 6),
            quadratic=1,
            matrix=(1, 0, 0, 1),
            slopes=(0, 1, 2, 3),
            intercepts=(0, 0, 0, 0),
        )
        values = construct(parameters)
        self.assertEqual(len(values), 28)
        self.assertEqual(len(set(values)), 28)


if __name__ == "__main__":
    unittest.main()
