#!/usr/bin/env python3
"""Optimize the legal 500-row Razborov/Turan sampling mesh.

The exact verifier segment functional on the active branch is

    F((x0,y0),(x1,y1)) = y1*(x1-x0) - (y1-y0)^2/6.

Within each smooth multipartite scallop, the gradient Hessian is tridiagonal.
Every transition density 1-1/r is retained as a kink node.  Interior nodes are
polished by damped Newton, then one-node transfers between scallops are tested.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.linalg import eigvalsh_tridiagonal, solve_banded


ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "checkpoints" / "live.json"
CANDIDATE = ROOT / "candidate.json"
RESULT = ROOT / "checkpoints" / "optimization.json"
EXPECTED_VERIFIER_SHA256 = "800ae2fbd2619d50de2177d49609289813bb6a2000b350f63e22820ad667052e"
EXPECTED_LEADER_ID = 2367
EXPECTED_LEADER_SCORE = -0.7117091757692579
GATE = 1e-6


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True).encode())
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def curve(x: np.ndarray, r: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return y, y', y'' on scallop r, including its two endpoints."""

    root = np.sqrt(np.maximum(0.0, (r - 1) * ((r - 1) - r * x)))
    small = (1.0 - root) / r
    large = (1.0 - small) / (r - 1)
    q2 = small**2 + (r - 1) * large**2
    q3 = small**3 + (r - 1) * large**3
    y = 1.0 - 3.0 * q2 + 2.0 * q3
    first = 3.0 * (r - 2) * (1.0 - small) / (r - 1)
    second = -3.0 * (r - 2) / (2.0 * np.maximum(1e-300, 1.0 - r * small))
    return y, first, second


def objective_gradient_hessian(
    interior: np.ndarray, r: int
) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    lower = 1.0 - 1.0 / (r - 1)
    upper = 1.0 - 1.0 / r
    x = np.r_[lower, interior, upper]
    y, first, second = curve(x, r)
    objective = float(np.sum(y[1:] * np.diff(x) - np.diff(y) ** 2 / 6.0))
    left_width = x[1:-1] - x[:-2]
    bracket = left_width + (y[2:] - 2.0 * y[1:-1] + y[:-2]) / 3.0
    gradient = y[1:-1] - y[2:] + first[1:-1] * bracket
    diagonal = (
        2.0 * first[1:-1]
        - 2.0 * first[1:-1] ** 2 / 3.0
        + second[1:-1] * bracket
    )
    off_diagonal = first[2:-1] * (-1.0 + first[1:-2] / 3.0)
    return objective, gradient, diagonal, off_diagonal


@dataclass
class Optimum:
    r: int
    count: int
    nodes: np.ndarray
    cost: float
    iterations: int
    max_gradient: float
    min_hessian_eigenvalue: float


def optimize_interval(r: int, count: int, initial: np.ndarray | None = None) -> Optimum:
    lower = 1.0 - 1.0 / (r - 1)
    upper = 1.0 - 1.0 / r
    if count == 0:
        cost, gradient, _, _ = objective_gradient_hessian(np.array([]), r)
        return Optimum(r, 0, np.array([]), cost, 0, 0.0, math.inf)
    if initial is None or len(initial) != count:
        nodes = np.linspace(lower, upper, count + 2, dtype=np.float64)[1:-1]
    else:
        nodes = np.asarray(initial, dtype=np.float64).copy()

    iterations = 0
    for iterations in range(100):
        cost, gradient, diagonal, off_diagonal = objective_gradient_hessian(nodes, r)
        if float(np.max(np.abs(gradient))) < 1e-14:
            break
        banded = np.zeros((3, count), dtype=np.float64)
        banded[1] = diagonal
        if count > 1:
            banded[0, 1:] = off_diagonal
            banded[2, :-1] = off_diagonal
        step = solve_banded((1, 1), banded, -gradient)
        scale = 1.0
        directional = float(np.dot(gradient, step))
        while scale > 1e-13:
            proposed = nodes + scale * step
            if np.all(np.diff(np.r_[lower, proposed, upper]) > 1e-14):
                proposed_cost = objective_gradient_hessian(proposed, r)[0]
                if proposed_cost <= cost + 1e-4 * scale * directional:
                    nodes = proposed
                    break
            scale *= 0.5
        if scale <= 1e-13:
            raise RuntimeError(f"Newton line search stalled on r={r}, count={count}")

    cost, gradient, diagonal, off_diagonal = objective_gradient_hessian(nodes, r)
    if count == 1:
        minimum_eigenvalue = float(diagonal[0])
    else:
        minimum_eigenvalue = float(
            eigvalsh_tridiagonal(
                diagonal, off_diagonal, select="i", select_range=(0, 0)
            )[0]
        )
    return Optimum(
        r=r,
        count=count,
        nodes=nodes,
        cost=cost,
        iterations=iterations,
        max_gradient=float(np.max(np.abs(gradient))),
        min_hessian_eigenvalue=minimum_eigenvalue,
    )


def density_rows(payload: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    weights = np.asarray(payload["weights"], dtype=np.float64)
    weights = weights / np.sum(weights, axis=1, keepdims=True)
    q2 = np.sum(weights**2, axis=1)
    q3 = np.sum(weights**3, axis=1)
    return weights, 1.0 - q2, 1.0 - 3.0 * q2 + 2.0 * q3


def padded(values: list[float]) -> list[float]:
    return values + [0.0] * (20 - len(values))


def weights_for_interior(x: float, r: int) -> list[float]:
    root = math.sqrt(max(0.0, (r - 1) * ((r - 1) - r * x)))
    small = (1.0 - root) / r
    large = (1.0 - small) / (r - 1)
    return padded([large] * (r - 1) + [small])


def build_payload(optima: dict[int, Optimum]) -> dict[str, Any]:
    rows: list[list[float]] = []
    for index in range(1, 11):
        x = 0.05 * index
        small = (1.0 - math.sqrt(max(0.0, 1.0 - 2.0 * x))) / 2.0
        rows.append(padded([small, 1.0 - small]))
    for r in range(3, 21):
        rows.extend(weights_for_interior(float(x), r) for x in optima[r].nodes)
        rows.append(padded([1.0 / r] * r))
    if len(rows) != 500:
        raise RuntimeError(f"constructed {len(rows)} rows instead of 500")
    return {"weights": rows}


def kink_subgradients(optima: dict[int, Optimum]) -> list[dict[str, float | int | bool]]:
    x_nodes = [0.5]
    y_nodes = [0.0]
    kink_indices: dict[int, int] = {}
    for r in range(3, 21):
        for x in optima[r].nodes:
            x_nodes.append(float(x))
            y_nodes.append(float(curve(np.array([x]), r)[0][0]))
        x_nodes.append(1.0 - 1.0 / r)
        y_nodes.append(float(curve(np.array([1.0 - 1.0 / r]), r)[0][0]))
        kink_indices[r] = len(x_nodes) - 1
    records = []
    for r in range(3, 20):
        index = kink_indices[r]
        x_prev, x_here = x_nodes[index - 1], x_nodes[index]
        y_prev, y_here, y_next = y_nodes[index - 1], y_nodes[index], y_nodes[index + 1]
        bracket = x_here - x_prev + (y_next - 2.0 * y_here + y_prev) / 3.0
        left_slope = 3.0 * (r - 2) / r
        right_slope = 3.0 * (r - 1) / r
        left = y_here - y_next + left_slope * bracket
        right = y_here - y_next + right_slope * bracket
        records.append(
            {
                "r": r,
                "density": x_here,
                "left_derivative": left,
                "right_derivative": right,
                "local_minimum": bool(left <= 1e-13 and right >= -1e-13),
            }
        )
    return records


def main() -> None:
    snapshot = json.loads(LIVE.read_text(encoding="utf-8"))
    if snapshot["verifier_sha256"] != EXPECTED_VERIFIER_SHA256:
        raise RuntimeError("snapshot verifier hash is not the pinned live verifier")
    leader = snapshot["leader"]
    if int(leader["id"]) != EXPECTED_LEADER_ID:
        raise RuntimeError("snapshot is not leader #2367")
    verifier = snapshot["problem"]["verifier"]
    namespace: dict[str, Any] = {}
    exec(compile(verifier, "live_edges_verifier.py", "exec"), namespace)
    evaluate: Callable[[dict[str, Any]], float] = namespace["evaluate"]
    leader_score = float(evaluate(leader["data"]))
    if leader_score != float(leader["score"]) or leader_score != EXPECTED_LEADER_SCORE:
        raise RuntimeError("live verifier does not reproduce the pinned leader")

    _, leader_x, leader_y = density_rows(leader["data"])
    order = np.argsort(leader_x)
    leader_x, leader_y = leader_x[order], leader_y[order]
    leader_fixed_zero_error = float(np.max(np.abs(leader_y[:10])))
    counts: dict[int, int] = {}
    leader_interior: dict[int, np.ndarray] = {}
    for r in range(3, 21):
        lower, upper = 1.0 - 1.0 / (r - 1), 1.0 - 1.0 / r
        selected = leader_x[(leader_x > lower + 1e-7) & (leader_x < upper - 1e-7)]
        counts[r] = int(len(selected))
        leader_interior[r] = selected
    if sum(counts.values()) != 472:
        raise RuntimeError("leader does not have 472 scallop-interior nodes")

    cache: dict[tuple[int, int], Optimum] = {}

    def optimum(r: int, count: int) -> Optimum:
        key = (r, count)
        if key not in cache:
            initial = leader_interior[r] if count == counts[r] else None
            cache[key] = optimize_interval(r, count, initial)
        return cache[key]

    original_optima = {r: optimum(r, count) for r, count in counts.items()}
    original_polished_cost = sum(item.cost for item in original_optima.values())
    original_leader_cost = sum(
        objective_gradient_hessian(leader_interior[r], r)[0] for r in range(3, 21)
    )

    allocation = dict(counts)
    transfers: list[dict[str, Any]] = []
    while True:
        candidates: list[tuple[float, int, int, float, float]] = []
        for donor, donor_count in allocation.items():
            if donor_count == 0:
                continue
            removal_cost = optimum(donor, donor_count - 1).cost - optimum(
                donor, donor_count
            ).cost
            for receiver, receiver_count in allocation.items():
                addition_benefit = optimum(receiver, receiver_count).cost - optimum(
                    receiver, receiver_count + 1
                ).cost
                candidates.append(
                    (
                        removal_cost - addition_benefit,
                        donor,
                        receiver,
                        removal_cost,
                        addition_benefit,
                    )
                )
        delta, donor, receiver, removal_cost, addition_benefit = min(candidates)
        if delta >= -1e-15:
            best_remaining_transfer = {
                "delta": delta,
                "donor": donor,
                "receiver": receiver,
                "removal_cost": removal_cost,
                "addition_benefit": addition_benefit,
            }
            break
        allocation[donor] -= 1
        allocation[receiver] += 1
        transfers.append(
            {
                "delta": delta,
                "donor": donor,
                "receiver": receiver,
                "removal_cost": removal_cost,
                "addition_benefit": addition_benefit,
            }
        )

    final_optima = {r: optimum(r, count) for r, count in allocation.items()}
    candidate = build_payload(final_optima)
    atomic_json(CANDIDATE, candidate)
    candidate_score = float(evaluate(candidate))
    improvement = candidate_score - leader_score
    candidate_weights, candidate_x, candidate_y = density_rows(candidate)
    sorted_indices = np.argsort(candidate_x)
    sorted_x, sorted_y = candidate_x[sorted_indices], candidate_y[sorted_indices]
    full_x = np.r_[0.0, sorted_x, 1.0]
    full_y = np.r_[0.0, sorted_y, 1.0]
    gaps = np.diff(full_x)
    cap_branch = bool(np.all(full_y[:-1] + 3.0 * gaps > full_y[1:] + 1e-9))
    kinks = kink_subgradients(final_optima)
    curve_residuals = []
    for x, y in zip(sorted_x[10:], sorted_y[10:]):
        r = min(20, max(3, math.ceil(1.0 / (1.0 - float(x)) - 1e-10)))
        expected_y = float(curve(np.array([x]), r)[0][0])
        curve_residuals.append(abs(float(y) - expected_y))
    uniform_cost_disagreement = max(
        abs(original_optima[r].cost - optimize_interval(r, counts[r]).cost)
        for r in range(3, 21)
    )

    result = {
        "schema": 1,
        "verifier_sha256": EXPECTED_VERIFIER_SHA256,
        "leader_id": EXPECTED_LEADER_ID,
        "leader_payload_sha256": hashlib.sha256(canonical(leader["data"])).hexdigest(),
        "leader_score": leader_score,
        "candidate_path": str(CANDIDATE),
        "candidate_payload_sha256": hashlib.sha256(canonical(candidate)).hexdigest(),
        "candidate_score": candidate_score,
        "score_improvement": improvement,
        "required_improvement": GATE,
        "gate_cleared": improvement > GATE,
        "rows": len(candidate_weights),
        "minimum_weight": float(np.min(candidate_weights)),
        "maximum_row_sum_error": float(
            np.max(np.abs(np.sum(candidate_weights, axis=1) - 1.0))
        ),
        "leader_fixed_zero_triangle_error": leader_fixed_zero_error,
        "candidate_fixed_zero_triangle_error": float(
            np.max(np.abs(sorted_y[:10]))
        ),
        "candidate_curve_residual": max(curve_residuals),
        "max_gap": float(np.max(gaps)),
        "all_segments_on_cap_branch": cap_branch,
        "original_counts": {str(k): v for k, v in counts.items()},
        "final_counts": {str(k): v for k, v in allocation.items()},
        "coordinate_polish_area_improvement": original_leader_cost
        - original_polished_cost,
        "allocation_area_improvement": original_polished_cost
        - sum(item.cost for item in final_optima.values()),
        "transfers": transfers,
        "best_remaining_transfer": best_remaining_transfer,
        "max_stationarity_residual": max(
            item.max_gradient for item in final_optima.values()
        ),
        "minimum_hessian_eigenvalue": min(
            item.min_hessian_eigenvalue for item in final_optima.values()
        ),
        "uniform_vs_seeded_cost_disagreement": uniform_cost_disagreement,
        "interval_diagnostics": [
            {
                "r": item.r,
                "interior_nodes": item.count,
                "cost": item.cost,
                "iterations": item.iterations,
                "max_gradient": item.max_gradient,
                "minimum_hessian_eigenvalue": item.min_hessian_eigenvalue,
            }
            for item in final_optima.values()
        ],
        "kink_subgradients": kinks,
        "all_kinks_locally_minimal": all(item["local_minimum"] for item in kinks),
    }
    atomic_json(RESULT, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
