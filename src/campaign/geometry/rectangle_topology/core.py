#!/usr/bin/env python3
"""Shared local-only geometry for n=21 circles in a perimeter-4 rectangle."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.optimize import least_squares, linprog
from scipy.sparse import lil_matrix


COUNT = 21
VARIABLES = 3 * COUNT + 2
RADIUS_START = 2 * COUNT
WIDTH_ID = 3 * COUNT
HEIGHT_ID = WIDTH_ID + 1
PAIR_TOLERANCE = 1e-9
PERIMETER_TOLERANCE = 1e-9
VERIFIER_SHA256 = "c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9"
CORPUS_SHA256 = "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"
LEADER_SCORE = 2.365832385207997
GATE = 1e-10
TARGET = LEADER_SCORE + GATE
WALLS = ("L", "R", "B", "T")
Constraint = tuple[str, int, int | str]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def append_event(path: Path, value: Any) -> None:
    line = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def all_constraints() -> list[Constraint]:
    constraints: list[Constraint] = [
        ("P", first, second)
        for first in range(COUNT)
        for second in range(first + 1, COUNT)
    ]
    constraints.extend(("W", index, wall) for index in range(COUNT) for wall in WALLS)
    constraints.append(("E", 0, "perimeter"))
    return constraints


ALL_CONSTRAINTS = all_constraints()


def normalize_origin(circles: np.ndarray) -> tuple[np.ndarray, float, float]:
    normalized = np.asarray(circles, dtype=float).copy()
    radii = normalized[:, 2]
    left = float(np.min(normalized[:, 0] - radii))
    bottom = float(np.min(normalized[:, 1] - radii))
    normalized[:, 0] -= left
    normalized[:, 1] -= bottom
    width = float(np.max(normalized[:, 0] + radii))
    height = float(np.max(normalized[:, 1] + radii))
    return normalized, width, height


def circles_to_values(circles: np.ndarray, width: float | None = None, height: float | None = None) -> np.ndarray:
    normalized, inferred_width, inferred_height = normalize_origin(circles)
    values = np.empty(VARIABLES, dtype=float)
    values[: 2 * COUNT] = normalized[:, :2].reshape(-1)
    values[RADIUS_START:WIDTH_ID] = normalized[:, 2]
    values[WIDTH_ID] = inferred_width if width is None else width
    values[HEIGHT_ID] = inferred_height if height is None else height
    return values


def values_to_circles(values: np.ndarray) -> np.ndarray:
    circles = np.empty((COUNT, 3), dtype=float)
    circles[:, :2] = values[: 2 * COUNT].reshape(COUNT, 2)
    circles[:, 2] = values[RADIUS_START:WIDTH_ID]
    return circles


def one_value_and_gradient(
    values: np.ndarray,
    constraint: Constraint,
    pair_tolerance: float,
    perimeter_tolerance: float,
) -> tuple[float, np.ndarray]:
    kind, first, second = constraint
    gradient = np.zeros(VARIABLES, dtype=float)
    if kind == "P":
        assert isinstance(second, int)
        dx = values[2 * first] - values[2 * second]
        dy = values[2 * first + 1] - values[2 * second + 1]
        distance = math.hypot(dx, dy)
        if distance == 0:
            return -1e100, gradient
        ux, uy = dx / distance, dy / distance
        gradient[2 * first], gradient[2 * first + 1] = ux, uy
        gradient[2 * second], gradient[2 * second + 1] = -ux, -uy
        gradient[RADIUS_START + first] = -1
        gradient[RADIUS_START + second] = -1
        return (
            distance
            - values[RADIUS_START + first]
            - values[RADIUS_START + second]
            + pair_tolerance,
            gradient,
        )
    if kind == "E":
        gradient[WIDTH_ID] = gradient[HEIGHT_ID] = -1
        return 2 + perimeter_tolerance - values[WIDTH_ID] - values[HEIGHT_ID], gradient

    wall = str(second)
    x_id, y_id, radius_id = 2 * first, 2 * first + 1, RADIUS_START + first
    if wall == "L":
        value = values[x_id] - values[radius_id]
        gradient[x_id], gradient[radius_id] = 1, -1
    elif wall == "R":
        value = values[WIDTH_ID] - values[x_id] - values[radius_id]
        gradient[WIDTH_ID], gradient[x_id], gradient[radius_id] = 1, -1, -1
    elif wall == "B":
        value = values[y_id] - values[radius_id]
        gradient[y_id], gradient[radius_id] = 1, -1
    else:
        value = values[HEIGHT_ID] - values[y_id] - values[radius_id]
        gradient[HEIGHT_ID], gradient[y_id], gradient[radius_id] = 1, -1, -1
    return value, gradient


def constraint_values(
    values: np.ndarray,
    constraints: Iterable[Constraint],
    pair_tolerance: float,
    perimeter_tolerance: float,
) -> np.ndarray:
    return np.asarray(
        [
            one_value_and_gradient(values, constraint, pair_tolerance, perimeter_tolerance)[0]
            for constraint in constraints
        ]
    )


def constraint_jacobian(
    values: np.ndarray,
    constraints: Iterable[Constraint],
    pair_tolerance: float,
    perimeter_tolerance: float,
) -> np.ndarray:
    return np.asarray(
        [
            one_value_and_gradient(values, constraint, pair_tolerance, perimeter_tolerance)[1]
            for constraint in constraints
        ]
    )


def decode_active(
    circles: np.ndarray,
    tolerance: float,
    pair_tolerance: float = PAIR_TOLERANCE,
    perimeter_tolerance: float = PERIMETER_TOLERANCE,
) -> list[Constraint]:
    values = circles_to_values(circles)
    return [
        constraint
        for constraint in ALL_CONSTRAINTS
        if one_value_and_gradient(values, constraint, pair_tolerance, perimeter_tolerance)[0]
        <= tolerance
    ]


@dataclass
class Root:
    values: np.ndarray
    residual: float
    evaluations: int
    success: bool


def solve_targets(
    start: np.ndarray,
    active: list[Constraint],
    targets: np.ndarray | None = None,
    pair_tolerance: float = PAIR_TOLERANCE,
    perimeter_tolerance: float = PERIMETER_TOLERANCE,
    max_evaluations: int = 500,
) -> Root:
    if len(active) != VARIABLES:
        raise ValueError(f"active system has {len(active)} constraints, expected {VARIABLES}")
    if targets is None:
        targets = np.zeros(VARIABLES)

    def function(values: np.ndarray) -> np.ndarray:
        return (
            constraint_values(values, active, pair_tolerance, perimeter_tolerance)
            - targets
        )

    def jacobian(values: np.ndarray) -> np.ndarray:
        return constraint_jacobian(values, active, pair_tolerance, perimeter_tolerance)

    result = least_squares(
        function,
        start,
        jac=jacobian,
        method="lm",
        xtol=1e-14,
        ftol=1e-14,
        gtol=1e-14,
        max_nfev=max_evaluations,
    )
    residual = float(np.max(np.abs(function(result.x))))
    return Root(
        result.x,
        residual,
        int(result.nfev),
        bool(result.success and residual <= 2e-10 and np.isfinite(result.x).all()),
    )


def candidate_metrics(circles: np.ndarray, pair_tolerance: float, perimeter_tolerance: float) -> dict[str, Any]:
    normalized, width, height = normalize_origin(circles)
    centers, radii = normalized[:, :2], normalized[:, 2]
    pair_slacks = np.asarray(
        [
            np.linalg.norm(centers[first] - centers[second])
            - radii[first]
            - radii[second]
            + pair_tolerance
            for first in range(COUNT)
            for second in range(first + 1, COUNT)
        ]
    )
    ulp = np.maximum(np.abs(np.spacing(centers[:, 0])), np.abs(np.spacing(centers[:, 1])))
    perimeter_slack = 2 + perimeter_tolerance - width - height
    accepted = bool(
        normalized.shape == (COUNT, 3)
        and np.isfinite(normalized).all()
        and np.all(radii > 0)
        and np.max(np.abs(centers)) <= 1e6
        and np.all(radii >= 1e6 * ulp)
        and np.min(pair_slacks) >= 0
        and perimeter_slack >= 0
    )
    return {
        "score": float(np.sum(radii)),
        "accepted_screen": accepted,
        "minimum_radius": float(np.min(radii)),
        "width": width,
        "height": height,
        "aspect_ratio": width / height,
        "minimum_pair_slack": float(np.min(pair_slacks)),
        "perimeter_slack": float(perimeter_slack),
    }


def values_metrics(values: np.ndarray, pair_tolerance: float, perimeter_tolerance: float) -> dict[str, Any]:
    circles = values_to_circles(values)
    report = candidate_metrics(circles, pair_tolerance, perimeter_tolerance)
    report["encoded_width"] = float(values[WIDTH_ID])
    report["encoded_height"] = float(values[HEIGHT_ID])
    report["envelope_width_error"] = report["width"] - float(values[WIDTH_ID])
    report["envelope_height_error"] = report["height"] - float(values[HEIGHT_ID])
    return report


def verifier_buffer(values: np.ndarray) -> tuple[np.ndarray, int, dict[str, Any]]:
    circles = values_to_circles(values)
    for steps in range(3000):
        report = candidate_metrics(circles, PAIR_TOLERANCE, PERIMETER_TOLERANCE)
        if report["accepted_screen"]:
            return circles_to_values(circles), steps, report
        circles[:, 2] = np.nextafter(circles[:, 2], 0.0)
    raise RuntimeError("failed to buffer a literal float payload in 3,000 radius steps")


def canonical_signature(active: Iterable[Constraint]) -> str:
    return sha256_bytes(json.dumps(sorted(active), separators=(",", ":")).encode())


def fixed_aspect_radii_lp(
    centers: np.ndarray,
    width: float,
    safety: float,
    pair_tolerance: float = 0.0,
    perimeter_budget: float = 2.0,
) -> np.ndarray | None:
    height = perimeter_budget - width
    if width <= 0 or height <= 0:
        return None
    caps = np.minimum.reduce(
        (centers[:, 0], width - centers[:, 0], centers[:, 1], height - centers[:, 1])
    ) - safety
    if np.any(caps <= 1e-12):
        return None
    rows: list[np.ndarray] = []
    rhs: list[float] = []
    for first in range(COUNT):
        for second in range(first + 1, COUNT):
            row = np.zeros(COUNT)
            row[first] = row[second] = 1
            rows.append(row)
            rhs.append(
                float(np.linalg.norm(centers[first] - centers[second]) + pair_tolerance - safety)
            )
    result = linprog(
        -np.ones(COUNT),
        A_ub=np.asarray(rows),
        b_ub=np.asarray(rhs),
        bounds=[(1e-12, float(cap)) for cap in caps],
        method="highs",
        options={"primal_feasibility_tolerance": 1e-10, "dual_feasibility_tolerance": 1e-10},
    )
    return result.x if result.success else None


def strict_repair(centers: np.ndarray, width: float, safety: float) -> tuple[np.ndarray, float] | None:
    height = 2 - width
    if width <= 2e-4 or height <= 2e-4:
        return None
    centers = np.asarray(centers, dtype=float).copy()
    radii = fixed_aspect_radii_lp(centers, width, safety)
    if radii is None:
        return None
    circles = np.column_stack((centers, radii))
    report = candidate_metrics(circles, 0.0, 0.0)
    if not report["accepted_screen"]:
        deficit = max(0.0, -report["minimum_pair_slack"] / 2, -report["perimeter_slack"] / 4)
        circles[:, 2] -= deficit + max(safety, 2e-15)
        if np.min(circles[:, 2]) <= 0 or not candidate_metrics(circles, 0.0, 0.0)["accepted_screen"]:
            return None
    normalized, normalized_width, _ = normalize_origin(circles)
    # Translation does not change the requested rectangle dimensions.  The LP
    # may leave a wall unused; keep the global aspect rather than replacing it
    # with the smaller envelope, since subsequent SLP controls that variable.
    shift_x = float(np.min(circles[:, 0] - circles[:, 2]))
    shift_y = float(np.min(circles[:, 1] - circles[:, 2]))
    normalized[:, 0] = circles[:, 0] - shift_x
    normalized[:, 1] = circles[:, 1] - shift_y
    if normalized_width > width + 1e-9:
        return None
    return normalized, width


def slp_centers_aspect(
    circles: np.ndarray,
    width: float,
    trust: float,
    aspect_trust: float,
    safety: float,
) -> tuple[np.ndarray, float] | None:
    height = 2 - width
    centers = circles[:, :2]
    # Variables: 2n center deltas, delta-width, and n new radii.
    delta_width_id = 2 * COUNT
    radius_start = delta_width_id + 1
    variable_count = radius_start + COUNT
    row_count = 4 * COUNT + COUNT * (COUNT - 1) // 2
    constraints = lil_matrix((row_count, variable_count))
    rhs = np.empty(row_count)
    row = 0
    for index, (x, y) in enumerate(centers):
        dx, dy, radius = 2 * index, 2 * index + 1, radius_start + index
        # left: -(dx) + r <= x
        constraints[row, dx], constraints[row, radius], rhs[row] = -1, 1, x - safety
        row += 1
        # right: dx - dW + r <= W-x
        constraints[row, dx] = 1
        constraints[row, delta_width_id] = -1
        constraints[row, radius], rhs[row] = 1, width - x - safety
        row += 1
        # bottom: -dy + r <= y
        constraints[row, dy], constraints[row, radius], rhs[row] = -1, 1, y - safety
        row += 1
        # top: dy + dW + r <= H-y because dH=-dW.
        constraints[row, dy] = 1
        constraints[row, delta_width_id] = 1
        constraints[row, radius], rhs[row] = 1, height - y - safety
        row += 1
    for first in range(COUNT):
        for second in range(first + 1, COUNT):
            delta = centers[first] - centers[second]
            distance = float(np.linalg.norm(delta))
            if distance <= 1e-15:
                return None
            direction = delta / distance
            constraints[row, 2 * first : 2 * first + 2] = -direction
            constraints[row, 2 * second : 2 * second + 2] = direction
            constraints[row, radius_start + first] = 1
            constraints[row, radius_start + second] = 1
            rhs[row] = distance - safety
            row += 1
    objective = np.zeros(variable_count)
    objective[radius_start:] = -1
    width_low = max(-aspect_trust, 1e-3 - width)
    width_high = min(aspect_trust, 1.999 - width)
    result = linprog(
        objective,
        A_ub=constraints.tocsr(),
        b_ub=rhs,
        bounds=[(-trust, trust)] * (2 * COUNT)
        + [(width_low, width_high)]
        + [(1e-12, None)] * COUNT,
        method="highs",
        options={"primal_feasibility_tolerance": 1e-10, "dual_feasibility_tolerance": 1e-10},
    )
    if not result.success:
        return None
    moved = centers + result.x[: 2 * COUNT].reshape(COUNT, 2)
    new_width = width + float(result.x[delta_width_id])
    return strict_repair(moved, new_width, safety)


def optimize_strict(
    centers: np.ndarray,
    width: float,
    safety: float,
    trusts: list[float],
    aspect_ratio: float,
    rounds: int,
) -> tuple[tuple[np.ndarray, float] | None, dict[str, Any]]:
    repaired = strict_repair(centers, width, safety)
    if repaired is None:
        return None, {"status": "initial_repair_failed"}
    current, current_width = repaired
    initial = candidate_metrics(current, 0.0, 0.0)
    accepted_steps = 0
    for _ in range(rounds):
        incumbent = current
        incumbent_width = current_width
        incumbent_score = float(candidate_metrics(current, 0.0, 0.0)["score"])
        chosen = None
        for trust in trusts:
            trial = slp_centers_aspect(
                current,
                current_width,
                trust,
                max(1e-7, aspect_ratio * trust),
                safety,
            )
            if trial is None:
                continue
            circles, trial_width = trial
            report = candidate_metrics(circles, 0.0, 0.0)
            if report["accepted_screen"] and float(report["score"]) > incumbent_score + 2e-13:
                incumbent = circles
                incumbent_width = trial_width
                incumbent_score = float(report["score"])
                chosen = trust
        if chosen is None:
            break
        current, current_width = incumbent, incumbent_width
        accepted_steps += 1
    return (current, current_width), {
        "status": "optimized",
        "initial_strict": initial,
        "final_strict": candidate_metrics(current, 0.0, 0.0),
        "accepted_slp_steps": accepted_steps,
    }


def select_rigid_active(values: np.ndarray, tolerance: float = 3e-6) -> list[Constraint] | None:
    # Perimeter equality is essential to remove the aspect-ratio objective DOF.
    perimeter = ("E", 0, "perimeter")
    selected: list[Constraint] = [perimeter]
    rows = [one_value_and_gradient(values, perimeter, 0.0, 0.0)[1]]
    rank = 1
    slacks = constraint_values(values, ALL_CONSTRAINTS, 0.0, 0.0)
    perimeter_index = len(ALL_CONSTRAINTS) - 1
    for index_value in np.argsort(slacks):
        index = int(index_value)
        if index == perimeter_index:
            continue
        if slacks[index] > tolerance:
            break
        constraint = ALL_CONSTRAINTS[index]
        row = one_value_and_gradient(values, constraint, 0.0, 0.0)[1]
        new_rank = int(np.linalg.matrix_rank(np.asarray(rows + [row]), tol=1e-10))
        if new_rank > rank:
            selected.append(constraint)
            rows.append(row)
            rank = new_rank
        if len(selected) == VARIABLES:
            return selected
    return None


def refine_rigid(circles: np.ndarray, width: float) -> dict[str, Any]:
    values = circles_to_values(circles, width=width, height=2 - width)
    active = select_rigid_active(values)
    if active is None:
        return {"status": "no_65_constraint_rigid_system"}
    strict = solve_targets(values, active, pair_tolerance=0.0, perimeter_tolerance=0.0, max_evaluations=800)
    if not strict.success:
        return {"status": "strict_root_failed", "residual": strict.residual}
    strict_report = values_metrics(strict.values, 0.0, 0.0)
    strict_roundoff_valid = bool(
        strict_report["minimum_radius"] > 0
        and strict_report["minimum_pair_slack"] >= -2e-12
        and strict_report["perimeter_slack"] >= -2e-12
        and abs(strict_report["envelope_width_error"]) <= 2e-12
        and abs(strict_report["envelope_height_error"]) <= 2e-12
    )
    if not strict_roundoff_valid:
        return {"status": "strict_root_globally_invalid", "strict_report": strict_report}
    full = solve_targets(
        strict.values,
        active,
        pair_tolerance=PAIR_TOLERANCE,
        perimeter_tolerance=PERIMETER_TOLERANCE,
        max_evaluations=800,
    )
    if not full.success:
        return {"status": "full_root_failed", "residual": full.residual}
    full_report = values_metrics(full.values, PAIR_TOLERANCE, PERIMETER_TOLERANCE)
    if not full_report["accepted_screen"]:
        # Equations can be globally valid but round one active inequality a few
        # ulps negative; the literal candidate buffer below is authoritative.
        pass
    buffered, steps, buffered_report = verifier_buffer(full.values)
    return {
        "status": "refined",
        "active": active,
        "signature": canonical_signature(active),
        "strict_report": strict_report,
        "strict_root_screen_with_roundoff": strict_roundoff_valid,
        "full_report": full_report,
        "buffer_steps": steps,
        "buffered_report": buffered_report,
        "buffered_values": buffered,
    }


def pain_ranking(circles: np.ndarray) -> tuple[np.ndarray, list[Constraint], np.ndarray]:
    active = decode_active(circles, 1e-6)
    if len(active) != VARIABLES:
        raise ValueError(f"rigid pain seed needs 65 active constraints, found {len(active)}")
    root = solve_targets(circles_to_values(circles), active)
    if not root.success:
        raise ValueError("failed to solve source active system")
    jacobian = constraint_jacobian(root.values, active, PAIR_TOLERANCE, PERIMETER_TOLERANCE)
    objective = np.zeros(VARIABLES)
    objective[RADIUS_START:WIDTH_ID] = 1
    multipliers = np.linalg.solve(jacobian.T, -objective)
    pain = np.zeros(COUNT)
    degree = np.zeros(COUNT)
    for multiplier, constraint in zip(multipliers, active):
        if constraint[0] == "E":
            continue
        load = float(multiplier) ** 2
        pain[constraint[1]] += load
        degree[constraint[1]] += 1
        if constraint[0] == "P":
            pain[int(constraint[2])] += load
            degree[int(constraint[2])] += 1
    pain += degree * 1e-9
    return pain, active, root.values


def load_corpus_solution(database: Path, solution_id: int) -> np.ndarray:
    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT record_json FROM solutions WHERE id=? AND problem_id=18", (solution_id,)
    ).fetchone()
    connection.close()
    if row is None:
        raise ValueError(f"missing circles-rectangle solution {solution_id}")
    circles = np.asarray(json.loads(row[0])["data"]["circles"], dtype=float)
    if circles.shape != (COUNT, 3) or not np.isfinite(circles).all():
        raise ValueError(f"solution {solution_id} has invalid circles")
    return normalize_origin(circles)[0]
