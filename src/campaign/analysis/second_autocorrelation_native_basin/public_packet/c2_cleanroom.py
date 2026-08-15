#!/usr/bin/env python3
"""Independent CPU float64 C2 objective and active-branch derivatives.

Copyright (c) 2026 C2 Native Basin contributors. MIT License.

This module is intentionally data-free. It accepts caller-provided arrays and
never loads a verifier, candidate, repository state, environment secret, or
network resource.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
from scipy.optimize import minimize
from scipy.signal import oaconvolve


def objective_components(values: np.ndarray) -> dict[str, Any]:
    """Compute the clean-room C2 score and exact active convolution lags."""

    function = np.asarray(values, dtype=np.float64)
    if function.ndim != 1 or function.size == 0:
        raise ValueError("values must be a nonempty one-dimensional array")
    if not np.isfinite(function).all():
        raise ValueError("values must be finite")
    if np.any(function < -1.0e-6):
        raise ValueError("values violate the -1e-6 nonnegativity tolerance")
    function = np.maximum(function, 0.0)
    mass = float(function.sum())
    if mass <= 0.0:
        raise ValueError("values must have positive mass")

    convolution = np.asarray(
        oaconvolve(function, function, mode="full"), dtype=np.float64
    )
    numerator = float(
        (
            2.0 * np.dot(convolution, convolution)
            + np.dot(convolution[:-1], convolution[1:])
        )
        / 3.0
    )
    convolution_l1 = float(np.abs(convolution).sum())
    maximum = float(np.abs(convolution).max())
    score = float(numerator / (convolution_l1 * maximum))
    active_lags = np.flatnonzero(np.abs(convolution) == maximum).astype(np.int64)
    return {
        "score": score,
        "function": function,
        "convolution": convolution,
        "numerator": numerator,
        "mass": mass,
        "convolution_l1": convolution_l1,
        "maximum": maximum,
        "active_lag": int(np.argmax(np.abs(convolution))),
        "exact_active_lags": active_lags,
        "exact_active_count": int(active_lags.size),
    }


def score(values: np.ndarray) -> float:
    """Return only the clean-room C2 score."""

    return float(objective_components(values)["score"])


def log_active_branch_gradients(
    values: np.ndarray, components: dict[str, Any] | None = None
) -> tuple[float, list[np.ndarray], list[dict[str, Any]]]:
    """Return every exact same-point smooth-branch gradient of log(C2)."""

    if components is None:
        components = objective_components(values)
    function = np.asarray(components["function"], dtype=np.float64)
    convolution = np.asarray(components["convolution"], dtype=np.float64)
    numerator = float(components["numerator"])
    mass = float(components["mass"])
    maximum = float(components["maximum"])
    active_lags = [int(value) for value in components["exact_active_lags"]]
    if len(active_lags) > 256:
        raise ValueError("exact Clarke hull has more than 256 active branches")

    kernel = 4.0 * convolution / (3.0 * numerator)
    kernel[:-1] += convolution[1:] / (3.0 * numerator)
    kernel[1:] += convolution[:-1] / (3.0 * numerator)
    common = (
        2.0 * oaconvolve(kernel, function[::-1], mode="valid")
        - 2.0 / mass
    )

    gradients: list[np.ndarray] = []
    diagnostics: list[dict[str, Any]] = []
    for active_lag in active_lags:
        gradient = np.asarray(common, dtype=np.float64).copy()
        lower = max(0, active_lag - (function.size - 1))
        upper = min(function.size - 1, active_lag)
        indices = np.arange(lower, upper + 1, dtype=np.int64)
        gradient[indices] -= (
            2.0 * function[active_lag - indices] / maximum
        )
        gradients.append(gradient)
        diagnostics.append(
            {
                "active_lag": active_lag,
                "exact_active_count": len(active_lags),
                "gradient_norm": float(np.linalg.norm(gradient)),
                "gradient_max_abs": float(np.abs(gradient).max()),
            }
        )
    return math.log(float(components["score"])), gradients, diagnostics


def minimum_norm_convex_combination(
    gradients: Sequence[np.ndarray],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Find the minimum-norm point in a finite gradient convex hull."""

    if not gradients:
        raise ValueError("at least one gradient is required")
    matrix = np.vstack(
        [np.asarray(gradient, dtype=np.float64) for gradient in gradients]
    )
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise ValueError("gradients must be finite equal-length vectors")
    gram = matrix @ matrix.T
    scale = max(float(np.diag(gram).max()), 1.0)
    scaled = gram / scale
    count = matrix.shape[0]

    def objective(weights: np.ndarray) -> tuple[float, np.ndarray]:
        return 0.5 * float(weights @ scaled @ weights), scaled @ weights

    result = minimize(
        objective,
        np.full(count, 1.0 / count),
        jac=True,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * count,
        constraints={
            "type": "eq",
            "fun": lambda weights: float(weights.sum() - 1.0),
            "jac": lambda weights: np.ones_like(weights),
        },
        options={"ftol": 1.0e-14, "maxiter": 500, "disp": False},
    )
    if not result.success:
        raise RuntimeError(f"simplex solve failed: {result.message}")
    weights = np.maximum(np.asarray(result.x, dtype=np.float64), 0.0)
    weights /= weights.sum()
    combined = weights @ matrix
    branch_dots = matrix @ combined
    return combined, weights, {
        "combined_norm": float(np.linalg.norm(combined)),
        "minimum_branch_directional_derivative": float(branch_dots.min()),
        "maximum_branch_directional_derivative": float(branch_dots.max()),
        "solver_iterations": int(result.nit),
    }
