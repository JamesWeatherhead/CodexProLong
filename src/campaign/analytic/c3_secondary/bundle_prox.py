#!/usr/bin/env python3
"""Proximal active-bundle steps for the C3 max-autoconvolution objective.

The verifier score is accepted only through direct float64 ``numpy.convolve``.
FFT convolution is used solely inside the dual Frank-Wolfe bundle solver.
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
    f = np.asarray(values, dtype=np.float64)
    return f * (len(f) / np.sum(f))


def exact_metrics(values: np.ndarray) -> tuple[float, np.ndarray, int]:
    f = np.asarray(values, dtype=np.float64)
    convolution = np.convolve(f, f, mode="full")
    argmax = int(np.argmax(convolution))
    score = float(2.0 * len(f) * convolution[argmax] / np.sum(f) ** 2)
    return score, convolution, argmax


def projected_lag_gradient(f: np.ndarray, lag: int) -> np.ndarray:
    """Return P grad((f*f)[lag]) for the fixed-mass tangent space."""
    n = len(f)
    result = np.zeros(n, dtype=np.float64)
    lo = max(0, lag - (n - 1))
    hi = min(n - 1, lag)
    indices = np.arange(lo, hi + 1)
    result[indices] = 2.0 * f[lag - indices]
    result -= np.mean(result)
    return result


def solve_dual_fw(
    f: np.ndarray,
    convolution: np.ndarray,
    eta: float,
    iterations: int,
    tolerance: float,
) -> tuple[np.ndarray, dict[str, float | int]]:
    """Solve the proximal max-linearization dual over all convolution lags.

    For b_k=(f*f)_k-M and projected rows a_k, the primal model is
        min_d max_k (b_k + a_k d) + ||d||^2/(2 eta).
    Its simplex dual minimizes eta/2 ||sum lambda_k a_k||^2 - lambda.b.
    Frank-Wolfe needs only two FFT convolutions and one explicit lag row per
    iteration, so the full 51,199-row bundle remains usable.
    """
    maximum = float(np.max(convolution))
    offsets = convolution - maximum
    initial_lag = int(np.argmax(convolution))
    aggregate = projected_lag_gradient(f, initial_lag)
    offset_average = float(offsets[initial_lag])
    support: dict[int, float] = {initial_lag: 1.0}
    last_gap = np.inf

    for iteration in range(1, iterations + 1):
        row_inner = 2.0 * fftconvolve(f, aggregate, mode="full")
        dual_gradient = eta * row_inner - offsets
        lag = int(np.argmin(dual_gradient))
        aggregate_norm_sq = float(np.dot(aggregate, aggregate))
        derivative = float(
            eta * (row_inner[lag] - aggregate_norm_sq)
            - (offsets[lag] - offset_average)
        )
        average_gradient = float(eta * aggregate_norm_sq - offset_average)
        last_gap = max(0.0, average_gradient - float(dual_gradient[lag]))
        if derivative >= -tolerance:
            break

        row = projected_lag_gradient(f, lag)
        delta = row - aggregate
        curvature = float(eta * np.dot(delta, delta))
        if not np.isfinite(curvature) or curvature <= 0.0:
            break
        step = float(np.clip(-derivative / curvature, 0.0, 1.0))
        aggregate += step * delta
        offset_average += step * (float(offsets[lag]) - offset_average)
        if support:
            for key in tuple(support):
                support[key] *= 1.0 - step
                if support[key] < 1e-15:
                    del support[key]
        support[lag] = support.get(lag, 0.0) + step

    direction = -eta * aggregate
    direction -= np.mean(direction)
    linearized = offsets + 2.0 * fftconvolve(f, direction, mode="full")
    info: dict[str, float | int] = {
        "iterations": iteration,
        "fw_gap": float(last_gap),
        "support_size": len(support),
        "direction_rms": float(np.sqrt(np.mean(direction * direction))),
        "direction_max_abs": float(np.max(np.abs(direction))),
        "predicted_max_change": float(np.max(linearized)),
        "predicted_argmax": int(np.argmax(linearized)),
    }
    return direction, info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--etas", default="1e-4,3e-4,1e-3,3e-3,1e-2")
    parser.add_argument("--cycles", type=int, default=4)
    parser.add_argument("--fw-iterations", type=int, default=1500)
    parser.add_argument("--fw-tolerance", type=float, default=1e-12)
    parser.add_argument("--fractions", default="0.25,0.5,0.75,1,1.25")
    args = parser.parse_args()

    f = normalize(np.load(args.input, allow_pickle=False).astype(np.float64))
    best_score, convolution, argmax = exact_metrics(f)
    initial_score = best_score
    etas = [float(value) for value in args.etas.split(",")]
    fractions = [float(value) for value in args.fractions.split(",")]

    run_dir = ROOT / "runs-bundle" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "seed.npy", f)
    atomic_npy(run_dir / "best.npy", f)

    with events_path.open("a", encoding="utf-8") as events:
        for cycle in range(1, args.cycles + 1):
            cycle_improved = False
            for eta in etas:
                direction, info = solve_dual_fw(
                    f, convolution, eta, args.fw_iterations, args.fw_tolerance
                )
                trial_best_score = best_score
                trial_best: np.ndarray | None = None
                trial_fraction = 0.0
                trial_argmax = argmax
                for fraction in fractions:
                    candidate = normalize(f + fraction * direction)
                    candidate_score, _, candidate_argmax = exact_metrics(candidate)
                    if candidate_score < trial_best_score:
                        trial_best_score = candidate_score
                        trial_best = candidate
                        trial_fraction = fraction
                        trial_argmax = candidate_argmax

                accepted = trial_best is not None
                if accepted:
                    f = trial_best
                    best_score, convolution, argmax = exact_metrics(f)
                    atomic_npy(run_dir / "best.npy", f)
                    cycle_improved = True
                event = {
                    "cycle": cycle,
                    "eta": eta,
                    **info,
                    "accepted": accepted,
                    "fraction": trial_fraction,
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
