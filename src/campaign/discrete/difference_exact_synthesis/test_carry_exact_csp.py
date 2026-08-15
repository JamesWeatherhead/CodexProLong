#!/usr/bin/env python3
"""Regression tests for the carry-exact Difference Bases CSP."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import carry_exact_csp as csp
import complete_capacity_closure as complete


class CarryExactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        frozen = json.loads(
            (Path(__file__).resolve().parent / "frozen_inputs.json").read_text(
                encoding="utf-8"
            )
        )
        residues = [int(value) for value in frozen["core"]["residues"]]
        if csp.sha256_json(residues) != frozen["core"]["residues_sha256"]:
            raise RuntimeError("frozen residue hash drift")
        cls.inputs = {
            "leader_coverage": int(frozen["leader"]["coverage"]),
            "leader_score": float(frozen["leader"]["score"]),
            "gate_score": float(frozen["leader"]["gate_score"]),
            "residues": residues,
        }
        cls.residues = cls.inputs["residues"]

    def test_frozen_leader_and_gate(self) -> None:
        self.assertEqual(self.inputs["leader_coverage"], 49109)
        self.assertEqual(self.inputs["leader_score"], 360**2 / 49109)
        self.assertEqual(csp.required_coverage(360, self.inputs["gate_score"]), 49110)
        self.assertEqual(csp.required_coverage(361, self.inputs["gate_score"]), 49383)

    def test_perfect_cyclic_core(self) -> None:
        counts = {
            residue: sum(
                (a - b) % csp.MODULUS == residue
                for a in self.residues
                for b in self.residues
                if a != b
            )
            for residue in range(1, csp.MODULUS)
        }
        self.assertEqual(set(counts.values()), {1})

    def test_carry_requirements_at_first_hole(self) -> None:
        before = 6 * csp.MODULUS + 1043
        after = before + 1
        self.assertEqual(
            csp.cross_requirements(6967, before), frozenset(range(-6, 6))
        )
        self.assertEqual(
            csp.cross_requirements(6967, after),
            frozenset([*range(-7, 0), *range(0, 6)]),
        )
        self.assertEqual(
            csp.cross_requirements(1044, after),
            frozenset([*range(-6, 0), *range(0, 7)]),
        )

    def test_incumbent_relation_matches_exact_prefix(self) -> None:
        incumbent = (0, 1, 4, 6)
        for target, expected_failures in ((49109, 0), (49110, 1)):
            failures = 0
            for high in range(len(self.residues)):
                for low in range(high):
                    needed = csp.cross_requirements(
                        self.residues[high] - self.residues[low], target
                    )
                    if not needed <= {a - b for a in incumbent for b in incumbent}:
                        failures += 1
            self.assertEqual(failures, expected_failures)

    def test_pattern_domain_is_complete_after_singleton_presolve(self) -> None:
        supports = csp.patterns(7)
        self.assertEqual(len(supports), 247)
        self.assertEqual(min(map(len, supports)), 2)
        self.assertEqual(max(map(len, supports)), 8)
        # A singleton paired with any support in eight shells has at most eight
        # cross differences, fewer than the mandatory twelve at this frontier.
        self.assertLess(1 * 8, len(csp.cross_requirements(2000, 49110)))

    def test_complete_capacity_domain_includes_singletons(self) -> None:
        supports = complete.complete_patterns(7)
        self.assertEqual(len(supports), 255)
        self.assertEqual(min(map(len, supports)), 1)
        self.assertEqual(max(map(len, supports)), 8)
        target = csp.required_coverage(320, self.inputs["gate_score"])
        minimum_pair_requirements = min(
            len(
                csp.cross_requirements(
                    self.residues[high] - self.residues[low], target
                )
            )
            for high in range(len(self.residues))
            for low in range(high)
        )
        self.assertEqual(minimum_pair_requirements, 9)


if __name__ == "__main__":
    unittest.main()
