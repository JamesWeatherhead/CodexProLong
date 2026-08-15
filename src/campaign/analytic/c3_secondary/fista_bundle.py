#!/usr/bin/env python3
"""Dense proximal bundle solver for C3 using accelerated projected gradients.

Unlike smooth log-sum-exp continuation, this optimizes the exact max's affine
bundle over every convolution lag. Candidate acceptance is always replayed by
the frozen verifier's direct float64 ``numpy.convolve`` computation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = Path(
    "/Users/jacweath/EinsteinArena/campaign/c3_root/"
    "runs-signed-square/20260814T234148Z/best.npy"
)
VERIFIER_SHA256 = "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9"
TARGET_SCORE = 1.4515618638902069


def atomic_npy(path: Path, values: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def normalize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    return values * (len(values) / np.sum(values))


def exact_metrics(values: np.ndarray) -> tuple[float, np.ndarray, int]:
    values = np.asarray(values, dtype=np.float64)
    convolution = np.convolve(values, values, mode="full")
    argmax = int(np.argmax(convolution))
    score = float(
        2.0 * len(values) * convolution[argmax] / np.sum(values) ** 2
    )
    return score, convolution, argmax


def project_simplex(values: np.ndarray) -> np.ndarray:
    """Euclidean projection onto {x >= 0, sum x = 1}."""
    ordered = np.sort(values)[::-1]
    cumulative = np.cumsum(ordered) - 1.0
    indices = np.arange(1, len(values) + 1, dtype=np.float64)
    positive = ordered - cumulative / indices > 0.0
    rho = int(np.flatnonzero(positive)[-1])
    threshold = cumulative[rho] / (rho + 1.0)
    return np.maximum(values - threshold, 0.0)


def dual_to_gradient(weights: np.ndarray, f: np.ndarray) -> np.ndarray:
    gradient = 2.0 * fftconvolve(weights, f[::-1], mode="valid")
    gradient -= np.mean(gradient)
    return gradient


def gradient_to_rows(gradient: np.ndarray, f: np.ndarray) -> np.ndarray:
    return 2.0 * fftconvolve(f, gradient, mode="full")


def estimate_operator_norm_sq(f: np.ndarray, iterations: int = 40) -> float:
    """Power iteration for ||A P||^2, where (A d)_k=2(f*d)_k."""
    rng = np.random.default_rng(20260814)
    vector = rng.normal(size=len(f))
    vector -= np.mean(vector)
    vector /= np.linalg.norm(vector)
    eigenvalue = 0.0
    for _ in range(iterations):
        rows = gradient_to_rows(vector, f)
        image = dual_to_gradient(rows, f)
        eigenvalue = float(np.dot(vector, image))
        norm = float(np.linalg.norm(image))
        vector = image / norm
    return eigenvalue


def solve_bundle(
    f: np.ndarray,
    convolution: np.ndarray,
    eta: float,
    iterations: int,
    tolerance: float,
    operator_norm_sq: float,
) -> tuple[np.ndarray, dict[str, float | int]]:
    maximum = float(np.max(convolution))
    offsets = convolution - maximum
    size = len(convolution)
    weights = np.zeros(size, dtype=np.float64)
    weights[int(np.argmax(convolution))] = 1.0
    extrapolated = weights.copy()
    momentum = 1.0
    lipschitz = eta * operator_norm_sq * 1.01
    last_objective = np.inf
    last_projected_residual = np.inf

    for iteration in range(1, iterations + 1):
        aggregate_y = dual_to_gradient(extrapolated, f)
        row_inner_y = gradient_to_rows(aggregate_y, f)
        dual_gradient = eta * row_inner_y - offsets
        candidate = project_simplex(extrapolated - dual_gradient / lipschitz)
        delta = candidate - extrapolated

        aggregate_candidate = dual_to_gradient(candidate, f)
        objective_candidate = float(
            0.5 * eta * np.dot(aggregate_candidate, aggregate_candidate)
            - np.dot(candidate, offsets)
        )
        objective_y = float(
            0.5 * eta * np.dot(aggregate_y, aggregate_y)
            - np.dot(extrapolated, offsets)
        )
        upper_model = float(
            objective_y
            + np.dot(dual_gradient, delta)
            + 0.5 * lipschitz * np.dot(delta, delta)
        )
        if objective_candidate > upper_model + 1e-12:
            lipschitz *= 2.0
            continue

        projected = project_simplex(candidate - (eta * gradient_to_rows(
            aggregate_candidate, f
        ) - offsets) / lipschitz)
        last_projected_residual = float(
            lipschitz * np.linalg.norm(candidate - projected)
        )

        next_momentum = 0.5 * (1.0 + np.sqrt(1.0 + 4.0 * momentum * momentum))
        next_extrapolated = candidate + (
            (momentum - 1.0) / next_momentum
        ) * (candidate - weights)
        # Adaptive restart avoids the long oscillations common near support changes.
        if np.dot(candidate - weights, next_extrapolated - candidate) > 0.0:
            next_momentum = 1.0
            next_extrapolated = candidate.copy()

        weights = candidate
        extrapolated = next_extrapolated
        momentum = next_momentum
        if (
            abs(last_objective - objective_candidate)
            <= tolerance * max(1.0, abs(objective_candidate))
            and last_projected_residual <= np.sqrt(tolerance)
        ):
            break
        last_objective = objective_candidate

    aggregate = dual_to_gradient(weights, f)
    direction = -eta * aggregate
    direction -= np.mean(direction)
    linearized = offsets + gradient_to_rows(direction, f)
    info: dict[str, float | int] = {
        "iterations": iteration,
        "dual_objective": float(last_objective),
        "projected_residual": float(last_projected_residual),
        "support_size": int(np.count_nonzero(weights > 1e-14)),
        "lipschitz": float(lipschitz),
        "direction_rms": float(np.sqrt(np.mean(direction * direction))),
        "direction_max_abs": float(np.max(np.abs(direction))),
        "predicted_max_change": float(np.max(linearized)),
        "predicted_argmax": int(np.argmax(linearized)),
    }
    return direction, info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--etas", default="3e-4,1e-3,3e-3,1e-2")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--tolerance", type=float, default=1e-13)
    parser.add_argument("--fractions", default="0.1,0.25,0.5,0.75,1,1.25")
    args = parser.parse_args()

    f = normalize(np.load(args.input, allow_pickle=False).astype(np.float64))
    best_score, convolution, argmax = exact_metrics(f)
    initial_score = best_score
    etas = [float(value) for value in args.etas.split(",")]
    fractions = [float(value) for value in args.fractions.split(",")]
    operator_norm_sq = estimate_operator_norm_sq(f)

    run_dir = ROOT / "runs-fista-bundle" / datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "seed.npy", f)
    atomic_npy(run_dir / "best.npy", f)

    with events_path.open("a", encoding="utf-8") as events:
        for cycle in range(1, args.cycles + 1):
            cycle_improved = False
            for eta in etas:
                direction, info = solve_bundle(
                    f,
                    convolution,
                    eta,
                    args.iterations,
                    args.tolerance,
                    operator_norm_sq,
                )
                accepted = False
                accepted_fraction = 0.0
                candidate_best_score = best_score
                candidate_best = f
                candidate_argmax = argmax
                for fraction in fractions:
                    candidate = normalize(f + fraction * direction)
                    score, _, trial_argmax = exact_metrics(candidate)
                    if score < candidate_best_score:
                        candidate_best_score = score
                        candidate_best = candidate
                        candidate_argmax = trial_argmax
                        accepted_fraction = fraction
                        accepted = True
                if accepted:
                    f = candidate_best
                    best_score, convolution, argmax = exact_metrics(f)
                    atomic_npy(run_dir / "best.npy", f)
                    cycle_improved = True
                event = {
                    "cycle": cycle,
                    "eta": eta,
                    "operator_norm_sq": operator_norm_sq,
                    **info,
                    "accepted": accepted,
                    "fraction": accepted_fraction,
                    "best_score": best_score,
                    "gain": initial_score - best_score,
                    "argmax": argmax,
                    "gate_gap": best_score - TARGET_SCORE,
                }
                events.write(json.dumps(event, sort_keys=True) + "\n")
                events.flush()
                print(json.dumps(event, sort_keys=True), flush=True)
            if not cycle_improved:
                break

    payload = run_dir / "best.npy"
    summary = {
        "input": str(args.input),
        "initial_score": initial_score,
        "best_score": best_score,
        "gain": initial_score - best_score,
        "target_score": TARGET_SCORE,
        "gate_gap": best_score - TARGET_SCORE,
        "gate_cleared": best_score <= TARGET_SCORE,
        "argmax": argmax,
        "n": len(f),
        "sum": float(np.sum(f)),
        "finite": bool(np.isfinite(f).all()),
        "operator_norm_sq": operator_norm_sq,
        "verifier_sha256": VERIFIER_SHA256,
        "payload": str(payload),
        "payload_sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
