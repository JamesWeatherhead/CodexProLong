#!/usr/bin/env python3
"""Brute-force regression for the exact single-lag feasibility bound."""

from __future__ import annotations

import itertools
import random
import unittest


def lag_interval(
    values: list[int], assigned: list[bool], lag: int
) -> tuple[int, int, int]:
    """Return the exact attainable correlation progression (lo, hi, step)."""
    size = len(values)
    constrained_lo = 0
    constrained_hi = 0
    free_edges = 0

    for residue in range(lag):
        path = list(range(residue, size, lag))
        if len(path) < 2:
            continue
        fixed = [offset for offset, index in enumerate(path) if assigned[index]]
        edge_count = len(path) - 1
        if len(fixed) < 2:
            free_edges += edge_count
            continue

        free_edges += fixed[0] + (edge_count - fixed[-1])
        for first_offset, second_offset in itertools.pairwise(fixed):
            length = second_offset - first_offset
            product = values[path[first_offset]] * values[path[second_offset]]
            if product == 1:
                segment_lo = -length if length % 2 == 0 else -length + 2
                segment_hi = length
            else:
                segment_lo = -length if length % 2 == 1 else -length + 2
                segment_hi = length - 2
            constrained_lo += segment_lo
            constrained_hi += segment_hi

    if free_edges:
        return (
            constrained_lo - free_edges,
            constrained_hi + free_edges,
            2,
        )
    return constrained_lo, constrained_hi, 4


def progression_intersects(
    lo: int, hi: int, step: int, target_lo: int, target_hi: int
) -> bool:
    first = max(lo, target_lo)
    first += (-((first - lo) % step)) % step
    return first <= min(hi, target_hi)


def bound_feasible(
    values: list[int], assigned: list[bool], lag: int, bound: int
) -> bool:
    lo, hi, step = lag_interval(values, assigned, lag)
    return progression_intersects(lo, hi, step, -bound, bound)


def clipped_interval(
    values: list[int], assigned: list[bool], lag: int, bound: int
) -> tuple[int, int] | None:
    lo, hi, step = lag_interval(values, assigned, lag)
    first = max(lo, -bound)
    first += (-((first - lo) % step)) % step
    upper = min(hi, bound)
    if first > upper:
        return None
    return first, first + ((upper - first) // step) * step


def moment_bound_feasible(values: list[int], assigned: list[bool], bound: int) -> bool:
    size = len(values)
    ranges: dict[int, tuple[int, int]] = {}
    for lag in range(1, size):
        interval = clipped_interval(values, assigned, lag, bound)
        if interval is None:
            return False
        ranges[lag] = interval

    for modulus in range(2, min(5, size - 1) + 1):
        correlation_lo = sum(ranges[lag][0] for lag in range(modulus, size, modulus))
        correlation_hi = sum(ranges[lag][1] for lag in range(modulus, size, modulus))
        square_lo = 0
        square_hi = 0
        for residue in range(modulus):
            fixed_sum = sum(
                values[index]
                for index in range(residue, size, modulus)
                if assigned[index]
            )
            remaining = sum(
                not assigned[index] for index in range(residue, size, modulus)
            )
            lo = fixed_sum - remaining
            hi = fixed_sum + remaining
            if lo > 0:
                minimum_absolute = lo
            elif hi < 0:
                minimum_absolute = -hi
            else:
                minimum_absolute = abs(lo) % 2
            square_lo += minimum_absolute**2
            square_hi += max(lo * lo, hi * hi)
        target_lo = (square_lo - size) // 2
        target_hi = (square_hi - size) // 2
        if target_lo > correlation_hi or target_hi < correlation_lo:
            return False
    return True


def brute_feasible(
    values: list[int], assigned: list[bool], lag: int, bound: int
) -> bool:
    free = [index for index, fixed in enumerate(assigned) if not fixed]
    for choices in itertools.product((-1, 1), repeat=len(free)):
        candidate = values.copy()
        for index, value in zip(free, choices):
            candidate[index] = value
        correlation = sum(
            candidate[index] * candidate[index + lag]
            for index in range(len(candidate) - lag)
        )
        if abs(correlation) <= bound:
            return True
    return False


class ExactLagBoundTest(unittest.TestCase):
    def test_random_outside_in_states_match_brute_force(self) -> None:
        rng = random.Random(0xC0DE70)
        checked = 0
        for size in range(4, 13):
            for _ in range(250):
                depth = rng.randrange(1, size // 2 + 1)
                assigned = [False] * size
                values = [1] * size
                for index in list(range(depth)) + list(range(size - depth, size)):
                    assigned[index] = True
                    values[index] = rng.choice((-1, 1))
                for lag in range(1, size):
                    for bound in range(5):
                        self.assertEqual(
                            bound_feasible(values, assigned, lag, bound),
                            brute_feasible(values, assigned, lag, bound),
                            (
                                size,
                                depth,
                                values,
                                assigned,
                                lag,
                                bound,
                                lag_interval(values, assigned, lag),
                            ),
                        )
                        checked += 1
        self.assertGreater(checked, 70_000)

    def test_modular_moment_identity(self) -> None:
        rng = random.Random(0xB0170)
        for size in range(4, 31):
            for _ in range(100):
                values = [rng.choice((-1, 1)) for _ in range(size)]
                correlations = {
                    lag: sum(
                        values[index] * values[index + lag]
                        for index in range(size - lag)
                    )
                    for lag in range(1, size)
                }
                for modulus in range(2, min(5, size - 1) + 1):
                    residue_sums = [
                        sum(values[residue::modulus]) for residue in range(modulus)
                    ]
                    expected = (
                        sum(value * value for value in residue_sums) - size
                    ) // 2
                    actual = sum(
                        correlations[lag] for lag in range(modulus, size, modulus)
                    )
                    self.assertEqual(actual, expected)

    def test_moment_bound_never_rejects_a_valid_completion(self) -> None:
        rng = random.Random(0x51DE10BE)
        checked = 0
        for size in range(6, 13):
            for _ in range(300):
                complete = [rng.choice((-1, 1)) for _ in range(size)]
                bound = max(
                    abs(
                        sum(
                            complete[index] * complete[index + lag]
                            for index in range(size - lag)
                        )
                    )
                    for lag in range(1, size)
                )
                depth = rng.randrange(1, size // 2 + 1)
                assigned = [
                    index < depth or index >= size - depth for index in range(size)
                ]
                values = [
                    complete[index] if assigned[index] else 1 for index in range(size)
                ]
                self.assertTrue(
                    moment_bound_feasible(values, assigned, bound),
                    (size, depth, bound, complete),
                )
                checked += 1
        self.assertEqual(checked, 2_100)


if __name__ == "__main__":
    unittest.main()
