#!/usr/bin/env python3

from __future__ import annotations

import unittest

from solver import (
    build_reduction,
    derive_edges,
    graph_facts,
    load_inputs,
    normalized_four_shapes,
    required_quotients,
    solve_reduction,
    validate_perfect_difference_set,
)


class CarryPotentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inputs = load_inputs()
        cls.residues = cls.inputs["core"]["residues"]
        cls.modulus = cls.inputs["core"]["modulus"]
        cls.target = cls.inputs["leader"]["first_missing"]

    def test_perfect_cyclic_core(self) -> None:
        validate_perfect_difference_set(self.residues, self.modulus)

    def test_forced_quotient_intervals(self) -> None:
        self.assertEqual(
            required_quotients(1, self.modulus, self.target), tuple(range(-6, 7))
        )
        self.assertEqual(
            required_quotients(1043, self.modulus, self.target), tuple(range(-6, 7))
        )
        self.assertEqual(
            required_quotients(1044, self.modulus, self.target), tuple(range(-6, 7))
        )
        self.assertEqual(
            required_quotients(1045, self.modulus, self.target), tuple(range(-6, 6))
        )
        self.assertEqual(
            required_quotients(6966, self.modulus, self.target), tuple(range(-6, 6))
        )
        self.assertEqual(
            required_quotients(6967, self.modulus, self.target), tuple(range(-7, 6))
        )

    def test_edge_partition_and_boundary_graph(self) -> None:
        low, middle, high = derive_edges(self.residues, self.modulus, self.target)
        self.assertEqual((len(low), len(middle), len(high)), (1043, 2961, 1))
        self.assertEqual((high[0].upper, high[0].lower, high[0].gap), (6967, 0, 6967))
        facts = graph_facts(self.residues, low)
        self.assertTrue(facts["connected"])
        self.assertEqual(facts["minimum_degree"], 14)
        self.assertEqual(facts["distance_from_zero_maximum"], 7)

    def test_shape_enumeration(self) -> None:
        shapes = normalized_four_shapes()
        self.assertEqual(len(shapes), 220)
        self.assertEqual(shapes[0], (0, 1, 2, 3))
        self.assertEqual(shapes[-1], (0, 10, 11, 12))

    def test_exact_boundary_relaxation_is_infeasible(self) -> None:
        reduction = build_reduction()
        self.assertEqual(reduction.facts["model_sha256"], "0fcb2054f099e398959e5318033f8969582becb5d6bbce072c40a6d455b0e4b4")
        self.assertEqual(reduction.facts["low_boundary_allowed_tuples"], 238)
        self.assertEqual(reduction.facts["high_boundary_allowed_tuples"], 238)
        result = solve_reduction(reduction, seconds=30.0, seed=20260815)
        self.assertEqual(result["status"], "INFEASIBLE")


if __name__ == "__main__":
    unittest.main()
