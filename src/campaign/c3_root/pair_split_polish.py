#!/usr/bin/env python3
"""Optimize only the antisymmetric degrees opened by a 2x block repeat."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.signal import fftconvolve
from scipy.special import logsumexp


ROOT = Path(__file__).resolve().parent


def lift(means: np.ndarray, differences: np.ndarray) -> np.ndarray:
    values = np.empty(2 * len(means), dtype=np.float64)
    values[0::2] = means + differences
    values[1::2] = means - differences
    return values


def exact_score(values: np.ndarray) -> float:
    f = np.asarray(values, dtype=np.float64)
    return float(2.0 * len(f) * np.max(np.convolve(f, f)) / np.sum(f) ** 2)


def atomic_npy(path: Path, values: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--betas", default="1e5,3e5,1e6,3e6,1e7,3e7,1e8")
    parser.add_argument("--maxiter", type=int, default=2000)
    parser.add_argument("--maxcor", type=int, default=100)
    parser.add_argument("--noise", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=20260814)
    args = parser.parse_args()

    means = np.load(args.input, allow_pickle=False).astype(np.float64)
    if means.ndim != 1 or not np.isfinite(means).all() or abs(np.sum(means)) < 1e-12:
        raise RuntimeError("invalid source vector")
    differences = np.zeros_like(means)
    if args.noise:
        rng = np.random.default_rng(args.seed)
        differences = rng.normal(
            0.0, args.noise * np.sqrt(np.mean(means**2)), size=means.shape
        )
    baseline = lift(means, np.zeros_like(means))
    baseline_score = exact_score(baseline)
    best = baseline.copy()
    best_score = baseline_score
    reference_max = float(np.max(np.convolve(baseline, baseline)))

    run_dir = ROOT / "runs-pair-split" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "baseline.npy", baseline)
    atomic_npy(run_dir / "best.npy", best)
    evaluations = 0
    current_beta = 0.0

    def objective_gradient(delta: np.ndarray) -> tuple[float, np.ndarray]:
        nonlocal evaluations
        evaluations += 1
        f = lift(means, delta)
        convolution = fftconvolve(f, f, mode="full")
        logits = current_beta * (convolution / reference_max - 1.0)
        lse = float(logsumexp(logits))
        weights = np.exp(logits - lse)
        smooth_max = reference_max * (1.0 + lse / current_beta)
        objective = float(np.log(smooth_max))
        gradient_f = 2.0 * fftconvolve(weights, f[::-1], mode="valid") / smooth_max
        return objective, gradient_f[0::2] - gradient_f[1::2]

    with events_path.open("a", encoding="utf-8") as events:
        for beta in (float(value) for value in args.betas.split(",")):
            current_beta = beta
            result = minimize(
                objective_gradient,
                differences,
                method="L-BFGS-B",
                jac=True,
                options={
                    "maxiter": args.maxiter,
                    "maxcor": args.maxcor,
                    "ftol": 1e-15,
                    "gtol": 1e-12,
                    "maxls": 30,
                },
            )
            differences = np.asarray(result.x, dtype=np.float64)
            candidate = lift(means, differences)
            candidate_score = exact_score(candidate)
            accepted = candidate_score < best_score
            if accepted:
                best = candidate.copy()
                best_score = candidate_score
                atomic_npy(run_dir / "best.npy", best)
            event = {
                "beta": beta,
                "candidate_score": candidate_score,
                "best_score": best_score,
                "gain": baseline_score - best_score,
                "accepted": accepted,
                "difference_rms": float(np.sqrt(np.mean(differences**2))),
                "nit": int(result.nit),
                "nfev": int(result.nfev),
                "optimizer_status": int(result.status),
                "optimizer_message": str(result.message),
                "total_evaluations": evaluations,
            }
            events.write(json.dumps(event, sort_keys=True) + "\n")
            events.flush()
            print(json.dumps(event, sort_keys=True), flush=True)

    summary = {
        "baseline_score": baseline_score,
        "best_score": best_score,
        "gain": baseline_score - best_score,
        "evaluations": evaluations,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
