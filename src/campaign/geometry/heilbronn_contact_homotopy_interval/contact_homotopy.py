#!/usr/bin/env python3
"""Global labelled contact-exchange homotopies for Heilbronn n=11.

The search works in two barycentric coordinates per point.  In these
coordinates the normalized triangle area is exactly the absolute value of a
2x2 determinant, so the active systems are quadratic polynomials with integer
coefficients.  No Arena verifier code is imported or executed here.

The incumbent has 17 active triangle constraints and six boundary contacts,
giving a square 23-equation system in 22 coordinates plus the common area z.
For each outgoing active triangle and each distant inactive triangle, this
program tracks the affine polynomial homotopy

    (1-t) (D_out - z) - t (D_in - z) = 0,

while preserving the other 16 active triangles and all six boundary contacts.
The minus sign follows the geometrically feasible exchange direction: the
outgoing constraint is released upward while the incoming constraint is pulled
down to equality.  Inactive triangles in the previously reported top-58
low-area pool are deliberately skipped.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.optimize import minimize

COUNT = 11
VARIABLES = 2 * COUNT + 1
TRIPLES = tuple(itertools.combinations(range(COUNT), 3))
BOUNDING_AREA = math.sqrt(3.0) / 4.0
LIVE_LEADER = 0.036529889880030156
STRICT_GATE = 0.036529890880030155
VERIFIER_SHA256 = "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d"
CORPUS_SHA256 = "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"

HERE = Path(__file__).resolve().parent
DEFAULT_SEED = (
    HERE.parent
    / "runs/20260814T231710Z/heilbronn-triangles/best.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    data = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_jsonl(path: Path, value: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def cartesian_to_barycentric(points: np.ndarray) -> np.ndarray:
    """Return (b,c), where p = a*A + b*B + c*C and a+b+c=1."""
    result = np.empty_like(points, dtype=np.float64)
    result[:, 1] = 2.0 * points[:, 1] / math.sqrt(3.0)
    result[:, 0] = points[:, 0] - 0.5 * result[:, 1]
    return result


def barycentric_to_cartesian(points: np.ndarray) -> np.ndarray:
    result = np.empty_like(points, dtype=np.float64)
    result[:, 0] = points[:, 0] + 0.5 * points[:, 1]
    result[:, 1] = (math.sqrt(3.0) / 2.0) * points[:, 1]
    return result


def determinant(points: np.ndarray, triple: tuple[int, int, int]) -> float:
    i, j, k = triple
    bi, ci = points[i]
    bj, cj = points[j]
    bk, ck = points[k]
    return float((bj - bi) * (ck - ci) - (cj - ci) * (bk - bi))


def determinant_gradient(
    points: np.ndarray,
    triple: tuple[int, int, int],
    sign: int,
) -> np.ndarray:
    i, j, k = triple
    bi, ci = points[i]
    bj, cj = points[j]
    bk, ck = points[k]
    gradient = np.zeros(VARIABLES, dtype=np.float64)
    gradient[2 * i] = sign * (cj - ck)
    gradient[2 * i + 1] = sign * (bk - bj)
    gradient[2 * j] = sign * (ck - ci)
    gradient[2 * j + 1] = sign * (bi - bk)
    gradient[2 * k] = sign * (ci - cj)
    gradient[2 * k + 1] = sign * (bj - bi)
    gradient[-1] = -1.0
    return gradient


def signed_constraint(
    values: np.ndarray,
    triple: tuple[int, int, int],
    sign: int,
) -> float:
    points = values[:-1].reshape(COUNT, 2)
    return sign * determinant(points, triple) - float(values[-1])


def boundary_value(values: np.ndarray, contact: tuple[int, str]) -> float:
    points = values[:-1].reshape(COUNT, 2)
    point, side = contact
    b, c = points[point]
    if side == "b0":
        return float(b)
    if side == "c0":
        return float(c)
    if side == "a0":
        return float(1.0 - b - c)
    raise ValueError(side)


def boundary_gradient(contact: tuple[int, str]) -> np.ndarray:
    point, side = contact
    gradient = np.zeros(VARIABLES, dtype=np.float64)
    if side == "b0":
        gradient[2 * point] = 1.0
    elif side == "c0":
        gradient[2 * point + 1] = 1.0
    elif side == "a0":
        gradient[2 * point] = -1.0
        gradient[2 * point + 1] = -1.0
    else:
        raise ValueError(side)
    return gradient


def domain_slacks(points: np.ndarray) -> np.ndarray:
    return np.concatenate((points[:, 0], points[:, 1], 1.0 - points.sum(axis=1)))


def all_scores(points: np.ndarray) -> np.ndarray:
    return np.asarray([abs(determinant(points, triple)) for triple in TRIPLES])


def metrics(values: np.ndarray) -> dict[str, object]:
    if not np.isfinite(values).all():
        return {
            "score": None,
            "system_z": None,
            "minimum_domain_slack": None,
            "minimum_pair_distance": None,
            "finite": False,
            "intended_domain": False,
            "active_triples_1e_8": [],
            "first_five": [],
        }
    points = values[:-1].reshape(COUNT, 2)
    scores = all_scores(points)
    domain = domain_slacks(points)
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    distances += np.eye(COUNT)
    score = float(scores.min())
    ordered = np.argsort(scores)
    return {
        "score": score,
        "system_z": float(values[-1]),
        "minimum_domain_slack": float(domain.min()),
        "minimum_pair_distance": float(distances.min()),
        "finite": bool(np.isfinite(values).all()),
        "intended_domain": bool(
            np.isfinite(values).all()
            and domain.min() >= -2e-10
            and distances.min() > 1e-9
        ),
        "active_triples_1e_8": [list(TRIPLES[i]) for i in ordered if scores[i] - score <= 1e-8],
        "first_five": [
            {"triple": list(TRIPLES[i]), "score": float(scores[i])}
            for i in ordered[:5]
        ],
    }


@dataclass(frozen=True)
class ActiveSystem:
    active: tuple[tuple[int, int, int], ...]
    signs: dict[tuple[int, int, int], int]
    boundaries: tuple[tuple[int, str], ...]


def discover_system(seed_values: np.ndarray, tolerance: float = 5e-13) -> ActiveSystem:
    points = seed_values[:-1].reshape(COUNT, 2)
    scores = all_scores(points)
    minimum = float(scores.min())
    active = tuple(TRIPLES[i] for i, score in enumerate(scores) if score - minimum <= tolerance)
    signs = {triple: (1 if determinant(points, triple) > 0 else -1) for triple in TRIPLES}
    boundaries: list[tuple[int, str]] = []
    for i, (b, c) in enumerate(points):
        if abs(b) <= tolerance:
            boundaries.append((i, "b0"))
        if abs(c) <= tolerance:
            boundaries.append((i, "c0"))
        if abs(1.0 - b - c) <= tolerance:
            boundaries.append((i, "a0"))
    result = ActiveSystem(active, signs, tuple(boundaries))
    if len(result.active) != 17 or len(result.boundaries) != 6:
        raise RuntimeError(
            f"expected incumbent 17+6 active system, found {len(result.active)}+{len(result.boundaries)}"
        )
    return result


def active_equation(
    values: np.ndarray,
    triple: tuple[int, int, int],
    system: ActiveSystem,
) -> tuple[float, np.ndarray]:
    sign = system.signs[triple]
    return signed_constraint(values, triple, sign), determinant_gradient(
        values[:-1].reshape(COUNT, 2), triple, sign
    )


def homotopy_system(
    values: np.ndarray,
    t: float,
    outgoing: tuple[int, int, int],
    incoming: tuple[int, int, int],
    system: ActiveSystem,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    equations: list[float] = []
    jacobian: list[np.ndarray] = []
    for triple in system.active:
        if triple == outgoing:
            continue
        value, gradient = active_equation(values, triple, system)
        equations.append(value)
        jacobian.append(gradient)
    for contact in system.boundaries:
        equations.append(boundary_value(values, contact))
        jacobian.append(boundary_gradient(contact))
    out_value, out_gradient = active_equation(values, outgoing, system)
    in_value, in_gradient = active_equation(values, incoming, system)
    equations.append((1.0 - t) * out_value - t * in_value)
    jacobian.append((1.0 - t) * out_gradient - t * in_gradient)
    derivative_t = np.zeros(VARIABLES, dtype=np.float64)
    derivative_t[-1] = -out_value - in_value
    return np.asarray(equations), np.asarray(jacobian), derivative_t


def newton_correct(
    initial: np.ndarray,
    t: float,
    outgoing: tuple[int, int, int],
    incoming: tuple[int, int, int],
    system: ActiveSystem,
    tolerance: float,
    max_iterations: int,
) -> tuple[np.ndarray, bool, int, float, float]:
    values = initial.copy()
    worst_condition = 0.0
    for iteration in range(1, max_iterations + 1):
        equations, jacobian, _ = homotopy_system(values, t, outgoing, incoming, system)
        residual = float(np.max(np.abs(equations)))
        try:
            condition = float(np.linalg.cond(jacobian))
        except np.linalg.LinAlgError:
            return values, False, iteration, residual, math.inf
        worst_condition = max(worst_condition, condition)
        if not math.isfinite(residual) or not math.isfinite(condition):
            return values, False, iteration, residual, worst_condition
        if residual <= tolerance:
            return values, True, iteration, residual, worst_condition
        try:
            step = np.linalg.solve(jacobian, -equations)
        except np.linalg.LinAlgError:
            return values, False, iteration, residual, worst_condition
        accepted = False
        scale = 1.0
        for _ in range(12):
            candidate = values + scale * step
            candidate_equations, _, _ = homotopy_system(
                candidate, t, outgoing, incoming, system
            )
            candidate_residual = float(np.max(np.abs(candidate_equations)))
            if math.isfinite(candidate_residual) and candidate_residual < residual:
                values = candidate
                accepted = True
                break
            scale *= 0.5
        if not accepted:
            return values, False, iteration, residual, worst_condition
    equations, _, _ = homotopy_system(values, t, outgoing, incoming, system)
    residual = float(np.max(np.abs(equations)))
    return values, residual <= tolerance, max_iterations, residual, worst_condition


def track_path(
    task_id: int,
    outgoing: tuple[int, int, int],
    incoming: tuple[int, int, int],
    seed_values: np.ndarray,
    system: ActiveSystem,
    initial_step: float,
    minimum_step: float,
    maximum_step: float,
    tolerance: float,
    max_newton_iterations: int,
    max_steps: int,
) -> dict[str, object]:
    started = time.perf_counter()
    values = seed_values.copy()
    t = 0.0
    step = initial_step
    steps = 0
    rejected_steps = 0
    newton_iterations = 0
    worst_condition = 0.0
    maximum_abs_value = float(np.max(np.abs(values)))
    while t < 1.0 and steps < max_steps:
        equations, jacobian, derivative_t = homotopy_system(
            values, t, outgoing, incoming, system
        )
        try:
            tangent = np.linalg.solve(jacobian, -derivative_t)
        except np.linalg.LinAlgError:
            return {
                "task_id": task_id,
                "outgoing": list(outgoing),
                "incoming": list(incoming),
                "status": "singular_tangent",
                "t_reached": t,
                "steps": steps,
                "rejected_steps": rejected_steps,
                "elapsed_seconds": time.perf_counter() - started,
            }
        next_t = min(1.0, t + step)
        predicted = values + (next_t - t) * tangent
        corrected, success, iterations, residual, condition = newton_correct(
            predicted,
            next_t,
            outgoing,
            incoming,
            system,
            tolerance,
            max_newton_iterations,
        )
        newton_iterations += iterations
        worst_condition = max(worst_condition, condition)
        if not success or np.max(np.abs(corrected)) > 1e4:
            step *= 0.5
            rejected_steps += 1
            if step < minimum_step:
                return {
                    "task_id": task_id,
                    "outgoing": list(outgoing),
                    "incoming": list(incoming),
                    "status": "step_floor",
                    "t_reached": t,
                    "steps": steps,
                    "rejected_steps": rejected_steps,
                    "newton_iterations": newton_iterations,
                    "final_residual": residual,
                    "worst_condition": worst_condition,
                    "elapsed_seconds": time.perf_counter() - started,
                }
            continue
        if not np.isfinite(corrected).all():
            step *= 0.5
            rejected_steps += 1
            if step < minimum_step:
                return {
                    "task_id": task_id,
                    "outgoing": list(outgoing),
                    "incoming": list(incoming),
                    "status": "nonfinite_step_floor",
                    "t_reached": t,
                    "steps": steps,
                    "rejected_steps": rejected_steps,
                    "newton_iterations": newton_iterations,
                    "elapsed_seconds": time.perf_counter() - started,
                }
            continue
        values = corrected
        t = next_t
        steps += 1
        maximum_abs_value = max(maximum_abs_value, float(np.max(np.abs(values))))
        if iterations <= 3:
            step = min(maximum_step, step * 1.45)
        elif iterations >= max_newton_iterations // 2:
            step = max(minimum_step, step * 0.7)
    if t < 1.0:
        return {
            "task_id": task_id,
            "outgoing": list(outgoing),
            "incoming": list(incoming),
            "status": "step_cap",
            "t_reached": t,
            "steps": steps,
            "rejected_steps": rejected_steps,
            "newton_iterations": newton_iterations,
            "worst_condition": worst_condition,
            "elapsed_seconds": time.perf_counter() - started,
        }
    equations, jacobian, _ = homotopy_system(values, 1.0, outgoing, incoming, system)
    try:
        singular_values = np.linalg.svd(jacobian, compute_uv=False)
        endpoint_rank = int(np.linalg.matrix_rank(jacobian))
        endpoint_smallest = float(singular_values[-1])
    except np.linalg.LinAlgError:
        endpoint_rank = -1
        endpoint_smallest = None
    record: dict[str, object] = {
        "task_id": task_id,
        "outgoing": list(outgoing),
        "incoming": list(incoming),
        "status": "complete",
        "t_reached": 1.0,
        "steps": steps,
        "rejected_steps": rejected_steps,
        "newton_iterations": newton_iterations,
        "final_residual": float(np.max(np.abs(equations))),
        "endpoint_jacobian_rank": endpoint_rank,
        "endpoint_smallest_singular_value": endpoint_smallest,
        "worst_condition": worst_condition,
        "maximum_abs_value": maximum_abs_value,
        "elapsed_seconds": time.perf_counter() - started,
        "endpoint": values.tolist(),
        "endpoint_sha256": hashlib.sha256(canonical_json(values.tolist())).hexdigest(),
    }
    record.update(metrics(values))
    return record


def worker(arguments: tuple[object, ...]) -> dict[str, object]:
    try:
        return track_path(*arguments)  # type: ignore[arg-type]
    except Exception as error:  # keep the bounded census durable across singular paths
        return {
            "task_id": int(arguments[0]),
            "outgoing": list(arguments[1]),
            "incoming": list(arguments[2]),
            "status": "worker_exception",
            "error_type": type(error).__name__,
            "error": str(error),
        }


def constraint_values_and_jacobian(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    points = values[:-1].reshape(COUNT, 2)
    rows: list[float] = []
    jacobian: list[np.ndarray] = []
    for triple in TRIPLES:
        raw = determinant(points, triple)
        sign = 1 if raw >= 0 else -1
        rows.append(sign * raw - float(values[-1]))
        jacobian.append(determinant_gradient(points, triple, sign))
    for point in range(COUNT):
        for side in ("b0", "c0", "a0"):
            contact = (point, side)
            rows.append(boundary_value(values, contact))
            jacobian.append(boundary_gradient(contact))
    return np.asarray(rows), np.asarray(jacobian)


def polish(values: np.ndarray, maxiter: int) -> tuple[np.ndarray, dict[str, object]]:
    gradient = np.zeros(VARIABLES, dtype=np.float64)
    gradient[-1] = -1.0
    result = minimize(
        lambda current: -float(current[-1]),
        values,
        jac=lambda _current: gradient,
        constraints=[
            {
                "type": "ineq",
                "fun": lambda current: constraint_values_and_jacobian(current)[0],
                "jac": lambda current: constraint_values_and_jacobian(current)[1],
            }
        ],
        method="SLSQP",
        options={"ftol": 1e-14, "maxiter": maxiter, "disp": False},
    )
    polished = np.asarray(result.x, dtype=np.float64)
    detail: dict[str, object] = {
        "success": bool(result.success),
        "status": int(result.status),
        "message": str(result.message),
        "iterations": int(result.nit),
        "objective": float(polished[-1]),
    }
    detail.update(metrics(polished))
    detail["values"] = polished.tolist()
    detail["values_sha256"] = hashlib.sha256(canonical_json(polished.tolist())).hexdigest()
    return polished, detail


def parse_triple(value: Iterable[int]) -> tuple[int, int, int]:
    result = tuple(int(item) for item in value)
    if len(result) != 3:
        raise ValueError(result)
    return result  # type: ignore[return-value]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--stamp")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--skip-low-pool", type=int, default=58)
    parser.add_argument("--task-limit", type=int)
    parser.add_argument("--initial-step", type=float, default=0.02)
    parser.add_argument("--minimum-step", type=float, default=1e-7)
    parser.add_argument("--maximum-step", type=float, default=0.08)
    parser.add_argument("--tolerance", type=float, default=2e-12)
    parser.add_argument("--max-newton-iterations", type=int, default=16)
    parser.add_argument("--max-steps", type=int, default=800)
    parser.add_argument("--polish-top", type=int, default=80)
    parser.add_argument("--polish-maxiter", type=int, default=1400)
    args = parser.parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive")

    source_path = Path(__file__).resolve()
    seed_path = args.seed.resolve()
    payload = json.loads(seed_path.read_text())
    cartesian = np.asarray(payload["points"], dtype=np.float64)
    if cartesian.shape != (COUNT, 2) or not np.isfinite(cartesian).all():
        raise ValueError("seed must contain exactly 11 finite 2D points")
    barycentric = cartesian_to_barycentric(cartesian)
    seed_score = float(all_scores(barycentric).min())
    seed_values = np.concatenate((barycentric.ravel(), [seed_score]))
    system = discover_system(seed_values)

    inactive = [triple for triple in TRIPLES if triple not in system.active]
    inactive.sort(key=lambda triple: abs(determinant(barycentric, triple)))
    skip_inactive = max(0, args.skip_low_pool - len(system.active))
    selected_inactive = inactive[skip_inactive:]
    tasks = [
        (outgoing, incoming)
        for outgoing in system.active
        for incoming in selected_inactive
    ]
    if args.task_limit is not None:
        tasks = tasks[: args.task_limit]

    if args.run_dir:
        run_dir = args.run_dir.resolve()
    else:
        stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = HERE / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    results_path = run_dir / "results.jsonl"
    events_path = run_dir / "events.jsonl"
    config = {
        "schema": "heilbronn-contact-homotopy-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source": str(source_path),
        "source_sha256": sha256_file(source_path),
        "seed": str(seed_path),
        "seed_sha256": sha256_file(seed_path),
        "seed_score_clean_barycentric": seed_score,
        "live_leader": LIVE_LEADER,
        "strict_gate": STRICT_GATE,
        "verifier_sha256": VERIFIER_SHA256,
        "research_corpus_sha256": CORPUS_SHA256,
        "active_triples": [list(triple) for triple in system.active],
        "boundary_contacts_barycentric": [list(contact) for contact in system.boundaries],
        "all_inactive_count": len(inactive),
        "previously_reported_low_area_pool_size": args.skip_low_pool,
        "skipped_inactive_count": skip_inactive,
        "selected_distant_inactive_count": len(selected_inactive),
        "task_count": len(tasks),
        "workers": args.workers,
        "initial_step": args.initial_step,
        "minimum_step": args.minimum_step,
        "maximum_step": args.maximum_step,
        "tolerance": args.tolerance,
        "max_newton_iterations": args.max_newton_iterations,
        "max_steps": args.max_steps,
        "polish_top": args.polish_top,
        "polish_maxiter": args.polish_maxiter,
        "formula": "normalized area = abs(det((b,c)_j-(b,c)_i,(b,c)_k-(b,c)_i))",
        "homotopy": "(1-t)*(signed_det_out-z)-t*(signed_det_in-z)=0",
        "external_actions": [],
    }
    atomic_json(run_dir / "config.json", config)
    append_jsonl(events_path, {"event": "start", **config})

    started = time.perf_counter()
    records: list[dict[str, object]] = []
    arguments = [
        (
            task_id,
            outgoing,
            incoming,
            seed_values,
            system,
            args.initial_step,
            args.minimum_step,
            args.maximum_step,
            args.tolerance,
            args.max_newton_iterations,
            args.max_steps,
        )
        for task_id, (outgoing, incoming) in enumerate(tasks)
    ]
    if args.workers == 1:
        iterator = (worker(argument) for argument in arguments)
        for record in iterator:
            records.append(record)
            append_jsonl(results_path, record)
            if bool(record.get("intended_domain")) and float(record.get("score", -1.0)) > STRICT_GATE:
                break
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            future_map = {executor.submit(worker, argument): argument[0] for argument in arguments}
            buffered: dict[int, dict[str, object]] = {}
            next_id = 0
            for future in as_completed(future_map):
                record = future.result()
                buffered[int(record["task_id"])] = record
                while next_id in buffered:
                    ordered = buffered.pop(next_id)
                    records.append(ordered)
                    append_jsonl(results_path, ordered)
                    next_id += 1

    completed = [record for record in records if record["status"] == "complete"]
    domain_endpoints = [record for record in completed if bool(record.get("intended_domain"))]
    ranked = sorted(
        domain_endpoints,
        key=lambda record: (float(record.get("score", -1.0)), -int(record["task_id"])),
        reverse=True,
    )
    unique: list[dict[str, object]] = []
    seen = set()
    for record in ranked:
        values = np.asarray(record["endpoint"], dtype=np.float64)
        key = tuple(np.round(values, 9))
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
        if len(unique) >= args.polish_top:
            break

    polish_records: list[dict[str, object]] = []
    best_values = seed_values.copy()
    best_metrics = metrics(best_values)
    for rank, record in enumerate(unique):
        initial = np.asarray(record["endpoint"], dtype=np.float64)
        polished, detail = polish(initial, args.polish_maxiter)
        detail.update(
            {
                "rank": rank,
                "source_task_id": record["task_id"],
                "source_endpoint_sha256": record["endpoint_sha256"],
            }
        )
        polish_records.append(detail)
        append_jsonl(run_dir / "polish.jsonl", detail)
        if bool(detail["intended_domain"]) and float(detail["score"]) > float(best_metrics["score"]):
            best_values = polished
            best_metrics = metrics(best_values)

    best_payload = {"points": barycentric_to_cartesian(best_values[:-1].reshape(COUNT, 2)).tolist()}
    best_payload_sha256 = hashlib.sha256(canonical_json(best_payload)).hexdigest()
    atomic_json(run_dir / "best.json", best_payload)
    summary = {
        "schema": "heilbronn-contact-homotopy-summary-v1",
        "completed_at": datetime.now(UTC).isoformat(),
        "elapsed_seconds": time.perf_counter() - started,
        "tasks_planned": len(tasks),
        "tasks_recorded": len(records),
        "complete_paths": len(completed),
        "failed_paths": len(records) - len(completed),
        "domain_valid_endpoints": len(domain_endpoints),
        "endpoint_gate_clearers": sum(
            bool(record.get("intended_domain")) and float(record.get("score", -1.0)) > STRICT_GATE
            for record in completed
        ),
        "polished_count": len(polish_records),
        "polished_gate_clearers": sum(
            bool(record.get("intended_domain")) and float(record.get("score", -1.0)) > STRICT_GATE
            for record in polish_records
        ),
        "seed_score": seed_score,
        "best_score_clean_formula": best_metrics["score"],
        "best_intended_domain": best_metrics["intended_domain"],
        "best_minimum_domain_slack": best_metrics["minimum_domain_slack"],
        "live_leader": LIVE_LEADER,
        "strict_gate": STRICT_GATE,
        "gate_margin": float(best_metrics["score"]) - STRICT_GATE,
        "gate_clearing": bool(best_metrics["intended_domain"])
        and float(best_metrics["score"]) > STRICT_GATE,
        "best_payload": "best.json",
        "best_payload_sha256": best_payload_sha256,
        "config_sha256": sha256_file(run_dir / "config.json"),
        "results_sha256": sha256_file(results_path),
        "polish_sha256": sha256_file(run_dir / "polish.jsonl")
        if (run_dir / "polish.jsonl").exists()
        else None,
        "verifier_sha256": VERIFIER_SHA256,
        "research_corpus_sha256": CORPUS_SHA256,
        "scope_caveat": (
            "This is a bounded real predictor-corrector pass over labelled one-for-one "
            "active-triangle exchanges outside the reported top-58 low-area pool; it is "
            "not a complete enumeration of real roots or a global upper bound."
        ),
        "external_actions": [],
    }
    atomic_json(run_dir / "summary.json", summary)
    append_jsonl(events_path, {"event": "complete", **summary})
    summary["events_sha256"] = sha256_file(events_path)
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not summary["gate_clearing"] else 2


if __name__ == "__main__":
    sys.exit(main())
