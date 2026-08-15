from __future__ import annotations

import json
import unittest
from fractions import Fraction

from tools.certify_erdos_continuous import (
    OUTPUT,
    PAYLOAD,
    build_certificate,
    encoded_certificate,
)


def direct_step_overlap(values: list[Fraction], shift: Fraction) -> Fraction:
    """Independent interval-intersection evaluator on [0, 2]."""
    width = Fraction(2, len(values))
    total = Fraction(0)
    for left_index, left_value in enumerate(values):
        left_start = left_index * width
        left_stop = left_start + width
        for right_index, right_value in enumerate(values):
            right_start = right_index * width + shift
            right_stop = right_start + width
            overlap = min(left_stop, right_stop) - max(left_start, right_start)
            if overlap > 0:
                total += overlap * left_value * (1 - right_value)
    return total


class ErdosContinuousCertificateTest(unittest.TestCase):
    def test_checked_in_certificate_is_fresh(self) -> None:
        self.assertEqual(OUTPUT.read_bytes(), encoded_certificate())
        certificate = build_certificate()
        self.assertEqual(certificate["n"], 3584)
        self.assertEqual(certificate["maximizing_lags"], [-192])
        self.assertTrue(certificate["comparisons"]["below_published_reference_upper_bound"])
        self.assertTrue(certificate["domain_checks"]["exact_normalized_values_in_unit_interval"])

    def test_small_continuous_example_maximizes_at_grid_boundary(self) -> None:
        # Integral is exactly one because the four values sum to two on [0, 2].
        values = [Fraction(0), Fraction(1), Fraction(1, 4), Fraction(3, 4)]
        width = Fraction(2, len(values))
        boundary_shifts = [index * width for index in range(-4, 5)]
        half_grid_shifts = [index * width / 2 for index in range(-8, 9)]
        boundary_max = max(direct_step_overlap(values, shift) for shift in boundary_shifts)
        sampled_continuous_max = max(
            direct_step_overlap(values, shift) for shift in half_grid_shifts
        )
        self.assertEqual(sampled_continuous_max, boundary_max)

    def test_certificate_json_round_trips(self) -> None:
        parsed = json.loads(OUTPUT.read_text(encoding="utf-8"))
        self.assertEqual(parsed["schema_version"], 1)
        self.assertEqual(parsed["domain_checks"]["all_grid_lags_evaluated"], 7167)

    def test_winning_lag_with_independent_fraction_arithmetic(self) -> None:
        values = json.loads(PAYLOAD.read_text(encoding="utf-8"))["values"]
        exact_values = [Fraction(*value.as_integer_ratio()) for value in values]
        mass = Fraction(len(values), 2)
        total = sum(exact_values)
        normalized = [mass * value / total for value in exact_values]
        lag = -192
        direct = sum(
            normalized[index] * (1 - normalized[index - lag])
            for index in range(0, len(values) + lag)
        ) / mass
        certificate = json.loads(OUTPUT.read_text(encoding="utf-8"))
        certified = Fraction(
            int(certificate["exact_max_numerator"]),
            int(certificate["exact_max_denominator"]),
        )
        self.assertEqual(direct, certified)
        self.assertEqual(float(certified), 0.3808585748578583)


if __name__ == "__main__":
    unittest.main()
