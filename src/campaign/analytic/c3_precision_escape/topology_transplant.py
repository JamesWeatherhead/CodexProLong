#!/usr/bin/env python3
"""Exact-accepted C3 sign-wall transplant and full-coordinate release.

This lane starts from a frozen verifier-replayed vector, crosses explicitly
selected sign walls, locks those walls during a signed-square continuation,
then releases every coordinate. FFT convolution is proposal machinery only;
all checkpoints are accepted with literal float64 ``numpy.convolve``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.signal import fftconvolve
from scipy.special import logsumexp


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = Path(
    ROOT.parents[1]
    / "c3_root/turbo-topology-continuation-v2/runs/20260815T031008Z/best.npy"
)
VERIFIER_SHA256 = "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9"
TARGET = 1.4515618638902069


def normalize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    mass = float(np.sum(values))
    if values.ndim != 1 or not np.isfinite(values).all() or abs(mass) < 1e-12:
        raise ValueError("invalid vector")
    return values * (len(values) / mass)


def exact_metrics(values: np.ndarray) -> tuple[float, int, float, float]:
    values = normalize(values)
    convolution = np.convolve(values, values, mode="full")
    score = float(2.0 * len(values) * np.max(convolution) / np.sum(values) ** 2)
    return score, int(np.argmax(convolution)), float(np.max(convolution)), float(np.min(convolution))


def atomic_npy(path: Path, values: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_jsonl(path: Path, value: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def signed_square(values: np.ndarray) -> np.ndarray:
    return values * np.abs(values)


def to_parameter(values: np.ndarray) -> np.ndarray:
    return np.sign(values) * np.sqrt(np.abs(values))


def smooth_objective_gradient(
    values: np.ndarray,
    beta: float,
    reference_max: float,
) -> tuple[float, np.ndarray]:
    convolution = fftconvolve(values, values, mode="full")
    logits = beta * (convolution / reference_max - 1.0)
    partition = float(logsumexp(logits))
    weights = np.exp(logits - partition)
    smooth_max = reference_max * (1.0 + partition / beta)
    mass = float(np.sum(values))
    objective = float(np.log(smooth_max) - 2.0 * np.log(abs(mass)))
    gradient = (
        2.0 * fftconvolve(weights, values[::-1], mode="valid") / smooth_max
        - 2.0 / mass
    )
    return objective, gradient


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--flip-indices", required=True)
    parser.add_argument("--betas", default="3e7,1e8,3e8,1e9")
    parser.add_argument("--maxiter", type=int, default=1200)
    parser.add_argument("--maxcor", type=int, default=100)
    parser.add_argument("--lock-stages", type=int, default=4)
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs")
    args = parser.parse_args()

    baseline = normalize(np.load(args.input, allow_pickle=False))
    baseline_score, _, reference_max, _ = exact_metrics(baseline)
    indices = sorted({int(value) for value in args.flip_indices.split(",") if value})
    if not indices or indices[0] < 0 or indices[-1] >= len(baseline):
        raise ValueError("flip indices are empty or out of range")
    current = baseline.copy()
    current[indices] *= -1.0
    current = normalize(current)
    seed_score = exact_metrics(current)[0]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / f"{stamp}-{'_'.join(map(str, indices))}"
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_npy(run_dir / "baseline.npy", baseline)
    atomic_npy(run_dir / "seed.npy", current)
    atomic_npy(run_dir / "best.npy", baseline)
    best = baseline.copy()
    best_score = baseline_score
    total_evaluations = 0
    betas = [float(value) for value in args.betas.split(",") if value]

    parameter = to_parameter(current)
    for stage, beta in enumerate(betas, start=1):
        evaluations = 0

        def locked_objective(u: np.ndarray) -> tuple[float, np.ndarray]:
            nonlocal evaluations
            evaluations += 1
            values = signed_square(u)
            objective, gradient = smooth_objective_gradient(values, beta, reference_max)
            return objective, gradient * (2.0 * np.abs(u))

        bounds: list[tuple[float | None, float | None]] = [(None, None)] * len(parameter)
        if stage <= args.lock_stages:
            for index in indices:
                bounds[index] = (1e-12, None) if current[index] >= 0.0 else (None, -1e-12)
        result = minimize(
            locked_objective,
            parameter,
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            options={"maxiter": args.maxiter, "maxcor": args.maxcor, "ftol": 1e-15,
                     "gtol": 1e-12, "maxls": 40},
        )
        current = normalize(signed_square(np.asarray(result.x, dtype=np.float64)))
        parameter = to_parameter(current)
        atomic_npy(run_dir / "current.npy", current)
        score, argmax, maximum, minimum = exact_metrics(current)
        total_evaluations += evaluations
        if score < best_score:
            best, best_score = current.copy(), score
            atomic_npy(run_dir / "best.npy", best)
        append_jsonl(events, {
            "phase": "locked", "stage": stage, "beta": beta, "score": score,
            "best_score": best_score, "argmax": argmax, "max_convolution": maximum,
            "min_convolution": minimum, "nfev": int(result.nfev), "nit": int(result.nit),
            "locked": stage <= args.lock_stages, "total_evaluations": total_evaluations,
        })
        print(json.dumps({"phase": "locked", "stage": stage, "score": score,
                          "best_score": best_score, "gate_gap": best_score - TARGET}), flush=True)

    locked_final = current.copy()
    atomic_npy(run_dir / "locked-final.npy", locked_final)

    if args.release:
        current = locked_final
        for stage, beta in enumerate(betas, start=1):
            evaluations = 0

            def release_objective(values: np.ndarray) -> tuple[float, np.ndarray]:
                nonlocal evaluations
                evaluations += 1
                return smooth_objective_gradient(values, beta, reference_max)

            result = minimize(
                release_objective,
                current,
                method="L-BFGS-B",
                jac=True,
                options={"maxiter": args.maxiter, "maxcor": args.maxcor, "ftol": 1e-15,
                         "gtol": 1e-12, "maxls": 40},
            )
            current = normalize(np.asarray(result.x, dtype=np.float64))
            atomic_npy(run_dir / "current.npy", current)
            score, argmax, maximum, minimum = exact_metrics(current)
            total_evaluations += evaluations
            if score < best_score:
                best, best_score = current.copy(), score
                atomic_npy(run_dir / "best.npy", best)
            append_jsonl(events, {
                "phase": "release", "stage": stage, "beta": beta, "score": score,
                "best_score": best_score, "argmax": argmax, "max_convolution": maximum,
                "min_convolution": minimum, "nfev": int(result.nfev), "nit": int(result.nit),
                "total_evaluations": total_evaluations,
            })
            print(json.dumps({"phase": "release", "stage": stage, "score": score,
                              "best_score": best_score, "gate_gap": best_score - TARGET}), flush=True)

    payload = run_dir / "best.npy"
    atomic_npy(run_dir / "final.npy", current)
    score, argmax, maximum, minimum = exact_metrics(best)
    summary = {
        "input": str(args.input.resolve()), "flip_indices": indices,
        "baseline_score": baseline_score, "seed_score": seed_score, "best_score": score,
        "gain": baseline_score - score, "target": TARGET, "gate_gap": score - TARGET,
        "gate_cleared": score < TARGET, "n": len(best), "sum": float(np.sum(best)),
        "finite": bool(np.isfinite(best).all()), "argmax": argmax,
        "max_convolution": maximum, "min_convolution": minimum,
        "evaluations": total_evaluations, "verifier_sha256": VERIFIER_SHA256,
        "payload": str(payload.resolve()),
        "payload_sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
