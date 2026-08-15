#!/usr/bin/env python3
"""Deterministic tests for the C2 public replay packet.

Copyright (c) 2026 C2 Native Basin contributors. MIT License.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from typing import Any

import numpy as np

import c2_cleanroom as c2
import replay_public


def test_objective_matches_direct_convolution() -> None:
    rng = np.random.default_rng(1701)
    values = rng.random(383)
    values[rng.random(values.size) < 0.43] = 0.0
    components = c2.objective_components(values)
    convolution = np.convolve(values, values)
    numerator = (
        2.0 * np.dot(convolution, convolution)
        + np.dot(convolution[:-1], convolution[1:])
    ) / 3.0
    expected = numerator / (np.abs(convolution).sum() * np.abs(convolution).max())
    assert math.isclose(components["score"], expected, rel_tol=0.0, abs_tol=2e-15)


def test_active_branch_gradient_matches_finite_difference() -> None:
    rng = np.random.default_rng(2901)
    values = rng.random(255) + 0.1
    log_score, gradients, _ = c2.log_active_branch_gradients(values)
    assert math.isfinite(log_score)
    assert len(gradients) == 1
    direction = rng.standard_normal(values.size)
    direction /= np.abs(direction).max()
    epsilon = 2.0e-7
    numeric = (
        math.log(c2.score(values + epsilon * direction))
        - math.log(c2.score(values - epsilon * direction))
    ) / (2.0 * epsilon)
    analytic = float(np.dot(gradients[0], direction))
    assert abs(analytic - numeric) < 2.0e-6


def test_true_same_point_two_lag_clarke_hull() -> None:
    values = np.zeros(127, dtype=np.float64)
    values[2] = 2.0
    values[63] = 1.0
    components = c2.objective_components(values)
    _, gradients, diagnostics = c2.log_active_branch_gradients(values, components)
    active = [int(value) for value in components["exact_active_lags"]]
    assert components["exact_active_count"] == 2
    assert len(set(active)) == 2
    assert len(gradients) == len(diagnostics) == 2


def test_minimum_norm_bundle_simplex() -> None:
    gradients = [
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.8, 0.8, 0.0]),
    ]
    combined, weights, diagnostics = c2.minimum_norm_convex_combination(gradients)
    assert np.all(weights >= 0.0)
    assert math.isclose(float(weights.sum()), 1.0, abs_tol=2.0e-15)
    assert np.linalg.norm(combined) <= 1.0
    assert diagnostics["minimum_branch_directional_derivative"] >= -1.0e-10


def test_public_allowlist_and_receipts() -> None:
    result = replay_public.verify_packet()
    assert result["status"] == "PASS"
    assert result["receipts"]["member_steps"] == 200
    assert not result["receipts"]["gate_cleared"]
    assert result["provenance"]["third_party_bytes"] == 0


def test_public_module_has_no_private_verifier_loader() -> None:
    source = replay_public.Path(replay_public.__file__).read_text(encoding="utf-8")
    joined = source.lower()
    assert "exec_module" not in joined
    assert "spec_from_file_location" not in joined
    assert "urlopen" not in joined
    assert "requests" not in joined


def main() -> int:
    tests: list[tuple[str, Callable[[], Any]]] = sorted(
        (name, value)
        for name, value in globals().items()
        if name.startswith("test_") and callable(value)
    )
    results = []
    for name, test in tests:
        test()
        results.append({"name": name, "status": "PASS"})
    print(json.dumps({"status": "PASS", "tests": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
