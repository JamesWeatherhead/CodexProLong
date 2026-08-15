#!/usr/bin/env python3
"""Boundary-eliminated Heilbronn n=11 active polynomial systems.

All coefficients are integers.  The numerical routines deliberately avoid any
Arena verifier dependency; domain filtering recomputes all 165 determinants.
"""

from __future__ import annotations

import itertools
import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

COUNT = 11
TRIPLES = tuple(itertools.combinations(range(COUNT), 3))
ACTIVE = (
    (0, 1, 6),
    (0, 2, 4),
    (0, 3, 9),
    (0, 4, 8),
    (0, 5, 9),
    (1, 2, 3),
    (1, 3, 7),
    (2, 5, 8),
    (2, 7, 10),
    (3, 4, 5),
    (3, 4, 10),
    (3, 6, 7),
    (3, 8, 9),
    (4, 8, 10),
    (5, 6, 8),
    (5, 9, 10),
    (6, 9, 10),
)
BOUNDARIES = (
    (0, "c0"),
    (1, "c0"),
    (5, "b0"),
    (7, "a0"),
    (8, "b0"),
    (10, "a0"),
)
VARIABLE_NAMES = (
    "b0",
    "b1",
    "b2",
    "c2",
    "b3",
    "c3",
    "b4",
    "c4",
    "c5",
    "b6",
    "c6",
    "b7",
    "c8",
    "b9",
    "c9",
    "b10",
    "z",
)
POINT_GROUP_DIMS = (1, 1, 2, 2, 2, 1, 2, 1, 1, 2, 1, 1)
REFLECTION_LABELS = (10, 7, 6, 3, 9, 8, 2, 1, 5, 4, 0)
STRICT_GATE = 0.036529890880030155
LIVE_LEADER = 0.036529889880030156

HERE = Path(__file__).resolve().parent
DERIVED_INPUTS_PATH = HERE / "derived_inputs.json"
TARGET_MANIFEST_PATH = HERE / "target_manifest.json"


@lru_cache(maxsize=1)
def load_derived_inputs() -> dict[str, object]:
    """Load the compact, publication-owned numerical/inventory fixture."""
    payload = json.loads(DERIVED_INPUTS_PATH.read_text())
    if payload.get("schema") != "heilbronn-gamma-monodromy-derived-inputs-v1":
        raise ValueError("unexpected derived-input fixture schema")
    return payload


def load_seed() -> np.ndarray:
    values = load_derived_inputs()["incumbent_center"]["decimal_values"]
    result = np.asarray(values, dtype=float)
    if result.shape != (17,) or not np.isfinite(result).all():
        raise ValueError("invalid derived incumbent center")
    return result


def expand_points(values: Sequence[complex]) -> np.ndarray:
    """Map 16 free coordinates to the 11 by 2 barycentric array."""
    x = values
    return np.asarray(
        [
            (x[0], 0),
            (x[1], 0),
            (x[2], x[3]),
            (x[4], x[5]),
            (x[6], x[7]),
            (0, x[8]),
            (x[9], x[10]),
            (x[11], 1 - x[11]),
            (0, x[12]),
            (x[13], x[14]),
            (x[15], 1 - x[15]),
        ],
        dtype=np.result_type(*values),
    )


def compress_points(points: np.ndarray, z: complex) -> np.ndarray:
    return np.asarray(
        [
            points[0, 0],
            points[1, 0],
            points[2, 0],
            points[2, 1],
            points[3, 0],
            points[3, 1],
            points[4, 0],
            points[4, 1],
            points[5, 1],
            points[6, 0],
            points[6, 1],
            points[7, 0],
            points[8, 1],
            points[9, 0],
            points[9, 1],
            points[10, 0],
            z,
        ],
        dtype=np.result_type(points, z),
    )


def det(points: np.ndarray, triple: tuple[int, int, int]) -> complex:
    i, j, k = triple
    bi, ci = points[i]
    bj, cj = points[j]
    bk, ck = points[k]
    return (bj - bi) * (ck - ci) - (cj - ci) * (bk - bi)


def signs_from_seed() -> dict[tuple[int, int, int], int]:
    points = expand_points(load_seed())
    return {triple: 1 if det(points, triple).real > 0 else -1 for triple in TRIPLES}


SIGNS = signs_from_seed()


def equation_and_point_gradient(
    values: np.ndarray,
    triple: tuple[int, int, int],
) -> tuple[complex, np.ndarray]:
    points = expand_points(values)
    i, j, k = triple
    bi, ci = points[i]
    bj, cj = points[j]
    bk, ck = points[k]
    sign = SIGNS[triple]
    point_grad = np.zeros((COUNT, 2), dtype=values.dtype)
    point_grad[i] = sign * np.asarray((cj - ck, bk - bj))
    point_grad[j] = sign * np.asarray((ck - ci, bi - bk))
    point_grad[k] = sign * np.asarray((ci - cj, bj - bi))
    grad = np.zeros(17, dtype=values.dtype)
    grad[0] = point_grad[0, 0]
    grad[1] = point_grad[1, 0]
    grad[2:4] = point_grad[2]
    grad[4:6] = point_grad[3]
    grad[6:8] = point_grad[4]
    grad[8] = point_grad[5, 1]
    grad[9:11] = point_grad[6]
    grad[11] = point_grad[7, 0] - point_grad[7, 1]
    grad[12] = point_grad[8, 1]
    grad[13:15] = point_grad[9]
    grad[15] = point_grad[10, 0] - point_grad[10, 1]
    grad[16] = -1
    return sign * det(points, triple) - values[16], grad


@dataclass(frozen=True)
class PolynomialSystem:
    triples: tuple[tuple[int, int, int], ...]

    def evaluate(self, values: np.ndarray) -> np.ndarray:
        return np.asarray(
            [equation_and_point_gradient(values, t)[0] for t in self.triples],
            dtype=values.dtype,
        )

    def jacobian(self, values: np.ndarray) -> np.ndarray:
        return np.asarray(
            [equation_and_point_gradient(values, t)[1] for t in self.triples],
            dtype=values.dtype,
        )


INCUMBENT_SYSTEM = PolynomialSystem(ACTIVE)


def target_system(
    outgoing: tuple[int, int, int], incoming: tuple[int, int, int]
) -> PolynomialSystem:
    triples = tuple(t for t in ACTIVE if t != outgoing) + (incoming,)
    if len(triples) != 17:
        raise ValueError("outgoing triple is not uniquely active")
    return PolynomialSystem(triples)


def reflect_triple(triple: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(sorted(REFLECTION_LABELS[i] for i in triple))


def canonical_exchange(
    outgoing: tuple[int, int, int], incoming: tuple[int, int, int]
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    pair = (outgoing, incoming)
    reflected = (reflect_triple(outgoing), reflect_triple(incoming))
    return min(pair, reflected)


def read_unresolved() -> list[dict[str, object]]:
    fixture = load_derived_inputs()
    pseudo_codes = fixture["status_codebooks"]["pseudo_status"]
    reflection_codes = fixture["status_codebooks"]["reflection_status"]
    rows = []
    for inventory_index, record in enumerate(fixture["unresolved_exchange_records"]):
        outgoing_index, i, j, k, pseudo_code, reflection_code = record
        rows.append(
            {
                "inventory_index": inventory_index,
                "outgoing": list(ACTIVE[outgoing_index]),
                "incoming": [i, j, k],
                "status": pseudo_codes[pseudo_code],
                "reflection_status": reflection_codes[reflection_code],
            }
        )
    return rows


def metrics(values: np.ndarray, imaginary_tolerance: float = 1e-9) -> dict[str, object]:
    imag = float(np.max(np.abs(values.imag)))
    result: dict[str, object] = {
        "maximum_imaginary_part": imag,
        "real": bool(imag <= imaginary_tolerance),
    }
    if imag > imaginary_tolerance or not np.isfinite(values).all():
        result.update({"intended_domain": False, "score": None})
        return result
    real_values = values.real
    points = expand_points(real_values)
    slacks = np.concatenate((points[:, 0], points[:, 1], 1 - points.sum(axis=1)))
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    distances += np.eye(COUNT)
    scores = np.asarray([abs(det(points, triple)) for triple in TRIPLES], dtype=float)
    score = float(scores.min())
    result.update(
        {
            "minimum_domain_slack": float(slacks.min()),
            "minimum_pair_distance": float(distances.min()),
            "score": score,
            "system_z": float(real_values[-1]),
            "intended_domain": bool(slacks.min() >= -1e-10 and distances.min() > 1e-9),
            "gate_clearing": bool(
                slacks.min() >= -1e-10
                and distances.min() > 1e-9
                and score > STRICT_GATE
            ),
        }
    )
    return result


def newton(
    system: PolynomialSystem,
    initial: np.ndarray,
    rhs: np.ndarray | None = None,
    tolerance: float = 2e-12,
    max_iterations: int = 20,
) -> tuple[np.ndarray, bool, int, float]:
    rhs_array = np.zeros(17, dtype=initial.dtype) if rhs is None else rhs
    values = initial.copy()
    for iteration in range(max_iterations + 1):
        residual_vector = system.evaluate(values) - rhs_array
        residual = float(np.max(np.abs(residual_vector)))
        if residual <= tolerance:
            return values, True, iteration, residual
        if iteration == max_iterations:
            break
        try:
            delta = np.linalg.solve(system.jacobian(values), -residual_vector)
        except np.linalg.LinAlgError:
            return values, False, iteration, residual
        accepted = False
        scale = 1.0
        for _ in range(10):
            candidate = values + scale * delta
            candidate_residual = float(
                np.max(np.abs(system.evaluate(candidate) - rhs_array))
            )
            if math.isfinite(candidate_residual) and candidate_residual < residual:
                values = candidate
                accepted = True
                break
            scale *= 0.5
        if not accepted:
            return values, False, iteration, residual
    return values, False, max_iterations, residual


def track_rhs_segment(
    system: PolynomialSystem,
    initial: np.ndarray,
    rhs_start: np.ndarray,
    rhs_target: np.ndarray,
    *,
    initial_step: float = 0.05,
    minimum_step: float = 1e-7,
    maximum_step: float = 0.2,
    tolerance: float = 2e-11,
) -> tuple[np.ndarray, dict[str, object]]:
    """Track F(x)=p along one affine complex RHS segment."""
    values = initial.copy()
    direction = rhs_target - rhs_start
    t = 0.0
    step = initial_step
    accepted = rejected = newton_iterations = 0
    worst_condition = 0.0
    while t < 1.0:
        h = min(step, 1.0 - t)
        jac = system.jacobian(values)
        try:
            condition = float(np.linalg.cond(jac))
            tangent = np.linalg.solve(jac, direction)
        except np.linalg.LinAlgError:
            return values, {
                "success": False,
                "reason": "singular_predictor",
                "t": t,
                "accepted_steps": accepted,
                "rejected_steps": rejected,
            }
        worst_condition = max(worst_condition, condition)
        predicted = values + h * tangent
        rhs = rhs_start + (t + h) * direction
        corrected, ok, iterations, residual = newton(
            system, predicted, rhs, tolerance=tolerance, max_iterations=16
        )
        newton_iterations += iterations
        if not ok or not np.isfinite(corrected).all():
            step *= 0.5
            rejected += 1
            if step < minimum_step:
                return values, {
                    "success": False,
                    "reason": "step_floor",
                    "t": t,
                    "accepted_steps": accepted,
                    "rejected_steps": rejected,
                    "residual": residual,
                    "worst_condition": worst_condition,
                }
            continue
        values = corrected
        t += h
        accepted += 1
        if iterations <= 3:
            step = min(maximum_step, step * 1.4)
        elif iterations >= 8:
            step = max(minimum_step, step * 0.7)
    final_residual = float(np.max(np.abs(system.evaluate(values) - rhs_target)))
    return values, {
        "success": bool(final_residual <= tolerance * 1.1),
        "reason": "complete",
        "t": t,
        "accepted_steps": accepted,
        "rejected_steps": rejected,
        "newton_iterations": newton_iterations,
        "residual": final_residual,
        "worst_condition": worst_condition,
    }


def track_general_segment(
    evaluate: Callable[[np.ndarray, float], np.ndarray],
    jacobian: Callable[[np.ndarray, float], np.ndarray],
    derivative_t: Callable[[np.ndarray, float], np.ndarray],
    initial: np.ndarray,
    *,
    initial_step: float = 0.025,
    minimum_step: float = 1e-8,
    maximum_step: float = 0.1,
    tolerance: float = 2e-11,
) -> tuple[np.ndarray, dict[str, object]]:
    """Track a general affine-in-t square complex homotopy from 0 to 1."""
    values = initial.copy()
    t = 0.0
    step = initial_step
    accepted = rejected = newton_iterations = 0
    worst_condition = 0.0
    while t < 1.0:
        h = min(step, 1.0 - t)
        jac = jacobian(values, t)
        try:
            condition = float(np.linalg.cond(jac))
            tangent = np.linalg.solve(jac, -derivative_t(values, t))
        except np.linalg.LinAlgError:
            return values, {"success": False, "reason": "singular_predictor", "t": t}
        worst_condition = max(worst_condition, condition)
        predicted = values + h * tangent
        target_t = t + h
        corrected = predicted.copy()
        ok = False
        residual = math.inf
        for iteration in range(17):
            f = evaluate(corrected, target_t)
            residual = float(np.max(np.abs(f)))
            if residual <= tolerance:
                ok = True
                newton_iterations += iteration
                break
            try:
                delta = np.linalg.solve(jacobian(corrected, target_t), -f)
            except np.linalg.LinAlgError:
                break
            corrected += delta
        if not ok or not np.isfinite(corrected).all():
            step *= 0.5
            rejected += 1
            if step < minimum_step:
                return values, {
                    "success": False,
                    "reason": "step_floor",
                    "t": t,
                    "accepted_steps": accepted,
                    "rejected_steps": rejected,
                    "residual": residual,
                    "worst_condition": worst_condition,
                }
            continue
        values = corrected
        t = target_t
        accepted += 1
        step = min(maximum_step, step * (1.35 if iteration <= 3 else 0.8))
    return values, {
        "success": True,
        "reason": "complete",
        "t": t,
        "accepted_steps": accepted,
        "rejected_steps": rejected,
        "newton_iterations": newton_iterations,
        "residual": float(np.max(np.abs(evaluate(values, 1.0)))),
        "worst_condition": worst_condition,
    }


def gamma_track_to_target(
    initial: np.ndarray,
    base_rhs: np.ndarray,
    target: PolynomialSystem,
    gamma: complex,
) -> tuple[np.ndarray, dict[str, object]]:
    start = INCUMBENT_SYSTEM

    def evaluate(values: np.ndarray, t: float) -> np.ndarray:
        return (1 - t) * gamma * (start.evaluate(values) - base_rhs) + t * target.evaluate(values)

    def jacobian(values: np.ndarray, t: float) -> np.ndarray:
        return (1 - t) * gamma * start.jacobian(values) + t * target.jacobian(values)

    def derivative(values: np.ndarray, _t: float) -> np.ndarray:
        return target.evaluate(values) - gamma * (start.evaluate(values) - base_rhs)

    return track_general_segment(evaluate, jacobian, derivative, initial)


def cluster_index(roots: Sequence[np.ndarray], candidate: np.ndarray, tolerance: float) -> int | None:
    for index, root in enumerate(roots):
        scale = max(1.0, float(np.max(np.abs(root))))
        if float(np.max(np.abs(root - candidate))) <= tolerance * scale:
            return index
    return None
