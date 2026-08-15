#!/usr/bin/env python3
"""Pseudo-arclength recovery of folded distant Heilbronn exchange paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from contact_homotopy import (
    CORPUS_SHA256,
    COUNT,
    DEFAULT_SEED,
    HERE,
    LIVE_LEADER,
    STRICT_GATE,
    VERIFIER_SHA256,
    append_jsonl,
    atomic_json,
    barycentric_to_cartesian,
    canonical_json,
    cartesian_to_barycentric,
    discover_system,
    homotopy_system,
    metrics,
    newton_correct,
    polish,
    sha256_file,
    all_scores,
)


def extended_tangent(
    values: np.ndarray,
    t: float,
    outgoing: tuple[int, int, int],
    incoming: tuple[int, int, int],
    system: object,
    previous: np.ndarray | None,
) -> tuple[np.ndarray, float]:
    _, jacobian, derivative_t = homotopy_system(
        values, t, outgoing, incoming, system  # type: ignore[arg-type]
    )
    extended = np.column_stack((jacobian, derivative_t))
    try:
        _, singular_values, right = np.linalg.svd(extended, full_matrices=True)
    except np.linalg.LinAlgError as error:
        raise RuntimeError("extended SVD failed") from error
    tangent = right[-1]
    tangent /= np.linalg.norm(tangent)
    if previous is None:
        if tangent[-1] < 0:
            tangent = -tangent
    elif float(np.dot(tangent, previous)) < 0:
        tangent = -tangent
    return tangent, float(singular_values[-1])


def arclength_correct(
    predicted: np.ndarray,
    tangent: np.ndarray,
    outgoing: tuple[int, int, int],
    incoming: tuple[int, int, int],
    system: object,
    tolerance: float,
    max_iterations: int,
) -> tuple[np.ndarray, bool, int, float, float]:
    current = predicted.copy()
    worst_condition = 0.0
    for iteration in range(1, max_iterations + 1):
        values, t = current[:-1], float(current[-1])
        equations, jacobian, derivative_t = homotopy_system(
            values, t, outgoing, incoming, system  # type: ignore[arg-type]
        )
        augmented_equations = np.concatenate(
            (equations, [float(np.dot(tangent, current - predicted))])
        )
        augmented_jacobian = np.vstack(
            (np.column_stack((jacobian, derivative_t)), tangent)
        )
        residual = float(np.max(np.abs(augmented_equations)))
        try:
            condition = float(np.linalg.cond(augmented_jacobian))
        except np.linalg.LinAlgError:
            return current, False, iteration, residual, math.inf
        worst_condition = max(worst_condition, condition)
        if not np.isfinite(current).all() or not math.isfinite(residual):
            return current, False, iteration, residual, worst_condition
        if residual <= tolerance:
            return current, True, iteration, residual, worst_condition
        try:
            delta = np.linalg.solve(augmented_jacobian, -augmented_equations)
        except np.linalg.LinAlgError:
            return current, False, iteration, residual, worst_condition
        accepted = False
        scale = 1.0
        for _ in range(12):
            candidate = current + scale * delta
            candidate_values, candidate_t = candidate[:-1], float(candidate[-1])
            candidate_equations, _, _ = homotopy_system(
                candidate_values,
                candidate_t,
                outgoing,
                incoming,
                system,  # type: ignore[arg-type]
            )
            candidate_augmented = np.concatenate(
                (
                    candidate_equations,
                    [float(np.dot(tangent, candidate - predicted))],
                )
            )
            candidate_residual = float(np.max(np.abs(candidate_augmented)))
            if math.isfinite(candidate_residual) and candidate_residual < residual:
                current = candidate
                accepted = True
                break
            scale *= 0.5
        if not accepted:
            return current, False, iteration, residual, worst_condition
    values, t = current[:-1], float(current[-1])
    equations, _, _ = homotopy_system(
        values, t, outgoing, incoming, system  # type: ignore[arg-type]
    )
    residual = max(
        float(np.max(np.abs(equations))),
        abs(float(np.dot(tangent, current - predicted))),
    )
    return current, residual <= tolerance, max_iterations, residual, worst_condition


def track_pseudo(
    task_id: int,
    source_task_id: int,
    outgoing: tuple[int, int, int],
    incoming: tuple[int, int, int],
    seed_values: np.ndarray,
    system: object,
    initial_step: float,
    minimum_step: float,
    maximum_step: float,
    tolerance: float,
    max_newton_iterations: int,
    max_steps: int,
    t_limit: float,
    coordinate_limit: float,
) -> dict[str, object]:
    started = time.perf_counter()
    current = np.concatenate((seed_values.copy(), [0.0]))
    try:
        tangent, minimum_extended_singular = extended_tangent(
            seed_values, 0.0, outgoing, incoming, system, None
        )
    except RuntimeError as error:
        return {
            "task_id": task_id,
            "source_task_id": source_task_id,
            "outgoing": list(outgoing),
            "incoming": list(incoming),
            "status": "initial_tangent_failure",
            "error": str(error),
        }
    step = initial_step
    accepted_steps = 0
    rejected_steps = 0
    newton_iterations = 0
    worst_condition = 0.0
    minimum_t = 0.0
    maximum_t = 0.0
    folds = 0
    previous_dt = float(tangent[-1])
    while accepted_steps < max_steps:
        predicted = current + step * tangent
        corrected, success, iterations, residual, condition = arclength_correct(
            predicted,
            tangent,
            outgoing,
            incoming,
            system,
            tolerance,
            max_newton_iterations,
        )
        newton_iterations += iterations
        worst_condition = max(worst_condition, condition)
        if not success or not np.isfinite(corrected).all():
            step *= 0.5
            rejected_steps += 1
            if step < minimum_step:
                return {
                    "task_id": task_id,
                    "source_task_id": source_task_id,
                    "outgoing": list(outgoing),
                    "incoming": list(incoming),
                    "status": "arc_step_floor",
                    "accepted_steps": accepted_steps,
                    "rejected_steps": rejected_steps,
                    "newton_iterations": newton_iterations,
                    "t_reached": float(current[-1]),
                    "minimum_t": minimum_t,
                    "maximum_t": maximum_t,
                    "folds": folds,
                    "final_residual": residual,
                    "worst_condition": worst_condition,
                    "elapsed_seconds": time.perf_counter() - started,
                }
            continue
        previous = current
        current = corrected
        accepted_steps += 1
        current_t = float(current[-1])
        minimum_t = min(minimum_t, current_t)
        maximum_t = max(maximum_t, current_t)
        try:
            new_tangent, extended_smallest = extended_tangent(
                current[:-1], current_t, outgoing, incoming, system, tangent
            )
        except RuntimeError:
            return {
                "task_id": task_id,
                "source_task_id": source_task_id,
                "outgoing": list(outgoing),
                "incoming": list(incoming),
                "status": "arc_tangent_failure",
                "accepted_steps": accepted_steps,
                "rejected_steps": rejected_steps,
                "t_reached": current_t,
                "minimum_t": minimum_t,
                "maximum_t": maximum_t,
                "folds": folds,
                "elapsed_seconds": time.perf_counter() - started,
            }
        minimum_extended_singular = min(minimum_extended_singular, extended_smallest)
        if new_tangent[-1] * previous_dt < 0:
            folds += 1
        if abs(float(new_tangent[-1])) > 1e-10:
            previous_dt = float(new_tangent[-1])
        tangent = new_tangent

        previous_t = float(previous[-1])
        if (previous_t - 1.0) * (current_t - 1.0) <= 0 and current_t != previous_t:
            alpha = (1.0 - previous_t) / (current_t - previous_t)
            endpoint_initial = previous[:-1] + alpha * (current[:-1] - previous[:-1])
            endpoint, endpoint_success, endpoint_iterations, endpoint_residual, endpoint_condition = newton_correct(
                endpoint_initial,
                1.0,
                outgoing,
                incoming,
                system,  # type: ignore[arg-type]
                tolerance,
                max_newton_iterations * 2,
            )
            newton_iterations += endpoint_iterations
            worst_condition = max(worst_condition, endpoint_condition)
            if endpoint_success and np.isfinite(endpoint).all():
                record: dict[str, object] = {
                    "task_id": task_id,
                    "source_task_id": source_task_id,
                    "outgoing": list(outgoing),
                    "incoming": list(incoming),
                    "status": "complete",
                    "accepted_steps": accepted_steps,
                    "rejected_steps": rejected_steps,
                    "newton_iterations": newton_iterations,
                    "minimum_t": minimum_t,
                    "maximum_t": maximum_t,
                    "folds": folds,
                    "endpoint_residual": endpoint_residual,
                    "worst_condition": worst_condition,
                    "minimum_extended_singular_value": minimum_extended_singular,
                    "elapsed_seconds": time.perf_counter() - started,
                    "endpoint": endpoint.tolist(),
                    "endpoint_sha256": hashlib.sha256(canonical_json(endpoint.tolist())).hexdigest(),
                }
                record.update(metrics(endpoint))
                return record
        if abs(current_t) > t_limit:
            return {
                "task_id": task_id,
                "source_task_id": source_task_id,
                "outgoing": list(outgoing),
                "incoming": list(incoming),
                "status": "t_limit",
                "accepted_steps": accepted_steps,
                "rejected_steps": rejected_steps,
                "t_reached": current_t,
                "minimum_t": minimum_t,
                "maximum_t": maximum_t,
                "folds": folds,
                "elapsed_seconds": time.perf_counter() - started,
            }
        if float(np.max(np.abs(current[:-1]))) > coordinate_limit:
            return {
                "task_id": task_id,
                "source_task_id": source_task_id,
                "outgoing": list(outgoing),
                "incoming": list(incoming),
                "status": "coordinate_limit",
                "accepted_steps": accepted_steps,
                "rejected_steps": rejected_steps,
                "t_reached": current_t,
                "minimum_t": minimum_t,
                "maximum_t": maximum_t,
                "folds": folds,
                "elapsed_seconds": time.perf_counter() - started,
            }
        if iterations <= 3:
            step = min(maximum_step, step * 1.35)
        elif iterations >= max_newton_iterations // 2:
            step = max(minimum_step, step * 0.7)
    return {
        "task_id": task_id,
        "source_task_id": source_task_id,
        "outgoing": list(outgoing),
        "incoming": list(incoming),
        "status": "arc_step_cap",
        "accepted_steps": accepted_steps,
        "rejected_steps": rejected_steps,
        "newton_iterations": newton_iterations,
        "t_reached": float(current[-1]),
        "minimum_t": minimum_t,
        "maximum_t": maximum_t,
        "folds": folds,
        "worst_condition": worst_condition,
        "minimum_extended_singular_value": minimum_extended_singular,
        "elapsed_seconds": time.perf_counter() - started,
    }


def worker(arguments: tuple[object, ...]) -> dict[str, object]:
    try:
        return track_pseudo(*arguments)  # type: ignore[arg-type]
    except Exception as error:
        return {
            "task_id": int(arguments[0]),
            "source_task_id": int(arguments[1]),
            "outgoing": list(arguments[2]),
            "incoming": list(arguments[3]),
            "status": "worker_exception",
            "error_type": type(error).__name__,
            "error": str(error),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_run", type=Path)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--stamp")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--task-limit", type=int)
    parser.add_argument("--initial-step", type=float, default=0.01)
    parser.add_argument("--minimum-step", type=float, default=1e-7)
    parser.add_argument("--maximum-step", type=float, default=0.05)
    parser.add_argument("--tolerance", type=float, default=2e-12)
    parser.add_argument("--max-newton-iterations", type=int, default=18)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--t-limit", type=float, default=5.0)
    parser.add_argument("--coordinate-limit", type=float, default=1000.0)
    parser.add_argument("--polish-top", type=int, default=80)
    parser.add_argument("--polish-maxiter", type=int, default=1400)
    args = parser.parse_args()

    source_run = args.source_run.resolve()
    source_records = [
        json.loads(line) for line in (source_run / "results.jsonl").read_text().splitlines()
    ]
    failures = [record for record in source_records if record["status"] != "complete"]
    if args.task_limit is not None:
        failures = failures[: args.task_limit]
    seed_path = args.seed.resolve()
    cartesian = np.asarray(json.loads(seed_path.read_text())["points"], dtype=np.float64)
    barycentric = cartesian_to_barycentric(cartesian)
    seed_score = float(all_scores(barycentric).min())
    seed_values = np.concatenate((barycentric.ravel(), [seed_score]))
    system = discover_system(seed_values)
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-pseudo")
    run_dir = HERE / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    results_path = run_dir / "results.jsonl"
    events_path = run_dir / "events.jsonl"
    config = {
        "schema": "heilbronn-contact-pseudo-arclength-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_sha256": sha256_file(Path(__file__).resolve()),
        "seed_sha256": sha256_file(seed_path),
        "source_run": str(source_run),
        "source_results_sha256": sha256_file(source_run / "results.jsonl"),
        "source_failed_paths": sum(record["status"] != "complete" for record in source_records),
        "task_count": len(failures),
        "workers": args.workers,
        "initial_step": args.initial_step,
        "minimum_step": args.minimum_step,
        "maximum_step": args.maximum_step,
        "tolerance": args.tolerance,
        "max_newton_iterations": args.max_newton_iterations,
        "max_steps": args.max_steps,
        "t_limit": args.t_limit,
        "coordinate_limit": args.coordinate_limit,
        "live_leader": LIVE_LEADER,
        "strict_gate": STRICT_GATE,
        "verifier_sha256": VERIFIER_SHA256,
        "research_corpus_sha256": CORPUS_SHA256,
        "external_actions": [],
    }
    atomic_json(run_dir / "config.json", config)
    append_jsonl(events_path, {"event": "start", **config})
    arguments = []
    for task_id, record in enumerate(failures):
        arguments.append(
            (
                task_id,
                int(record["task_id"]),
                tuple(record["outgoing"]),
                tuple(record["incoming"]),
                seed_values,
                system,
                args.initial_step,
                args.minimum_step,
                args.maximum_step,
                args.tolerance,
                args.max_newton_iterations,
                args.max_steps,
                args.t_limit,
                args.coordinate_limit,
            )
        )
    started = time.perf_counter()
    records: list[dict[str, object]] = []
    if args.workers == 1:
        for argument in arguments:
            record = worker(argument)
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
    domain = [record for record in completed if bool(record.get("intended_domain"))]
    ranked = sorted(domain, key=lambda record: float(record["score"]), reverse=True)
    unique: list[dict[str, object]] = []
    seen: set[tuple[float, ...]] = set()
    for record in ranked:
        key = tuple(np.round(np.asarray(record["endpoint"], dtype=np.float64), 9))
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
        polished, detail = polish(
            np.asarray(record["endpoint"], dtype=np.float64), args.polish_maxiter
        )
        detail.update(
            {
                "rank": rank,
                "source_task_id": record["source_task_id"],
                "pseudo_task_id": record["task_id"],
                "source_endpoint_sha256": record["endpoint_sha256"],
            }
        )
        polish_records.append(detail)
        append_jsonl(run_dir / "polish.jsonl", detail)
        if bool(detail["intended_domain"]) and float(detail["score"]) > float(best_metrics["score"]):
            best_values = polished
            best_metrics = metrics(best_values)
    payload = {"points": barycentric_to_cartesian(best_values[:-1].reshape(COUNT, 2)).tolist()}
    payload_hash = hashlib.sha256(canonical_json(payload)).hexdigest()
    atomic_json(run_dir / "best.json", payload)
    summary = {
        "schema": "heilbronn-contact-pseudo-arclength-summary-v1",
        "completed_at": datetime.now(UTC).isoformat(),
        "elapsed_seconds": time.perf_counter() - started,
        "tasks_planned": len(failures),
        "tasks_recorded": len(records),
        "complete_paths": len(completed),
        "failed_paths": len(records) - len(completed),
        "paths_with_folds": sum(int(record.get("folds", 0)) > 0 for record in records),
        "total_detected_folds": sum(int(record.get("folds", 0)) for record in records),
        "domain_valid_endpoints": len(domain),
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
        "live_leader": LIVE_LEADER,
        "strict_gate": STRICT_GATE,
        "gate_margin": float(best_metrics["score"]) - STRICT_GATE,
        "gate_clearing": bool(best_metrics["intended_domain"])
        and float(best_metrics["score"]) > STRICT_GATE,
        "best_payload": "best.json",
        "best_payload_sha256": payload_hash,
        "config_sha256": sha256_file(run_dir / "config.json"),
        "results_sha256": sha256_file(results_path),
        "polish_sha256": sha256_file(run_dir / "polish.jsonl")
        if (run_dir / "polish.jsonl").exists()
        else None,
        "verifier_sha256": VERIFIER_SHA256,
        "research_corpus_sha256": CORPUS_SHA256,
        "scope_caveat": (
            "Pseudo-arclength recovery follows one oriented real branch per failed "
            "direct homotopy, with finite arclength, parameter, and coordinate caps; "
            "it is not a complete complex-path or branch-point enumeration."
        ),
        "external_actions": [],
    }
    atomic_json(run_dir / "summary.json", summary)
    append_jsonl(events_path, {"event": "complete", **summary})
    summary["events_sha256"] = sha256_file(events_path)
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 2 if summary["gate_clearing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
