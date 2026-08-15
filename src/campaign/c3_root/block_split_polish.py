#!/usr/bin/env python3
"""Optimize only zero-mean within-block modes of an exact C3 repeat lift."""

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


def lift(means: np.ndarray, raw_offsets: np.ndarray) -> np.ndarray:
    offsets = raw_offsets - np.mean(raw_offsets, axis=1, keepdims=True)
    return (means[:, None] + offsets).reshape(-1)


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
    parser.add_argument("--factor", type=int, default=3)
    parser.add_argument("--betas", default="1e7,3e7,1e8,3e8,1e9")
    parser.add_argument("--maxiter", type=int, default=1500)
    parser.add_argument("--maxcor", type=int, default=80)
    parser.add_argument("--noise", type=float, default=1e-6)
    parser.add_argument("--seed", type=int, default=20260815)
    args = parser.parse_args()
    if not 2 <= args.factor <= 8:
        raise RuntimeError("factor must be between two and eight")
    if args.noise < 0.0:
        raise RuntimeError("noise must be non-negative")

    means = np.load(args.input, allow_pickle=False).astype(np.float64)
    if means.ndim != 1 or not np.isfinite(means).all() or abs(np.sum(means)) < 1e-12:
        raise RuntimeError("invalid source vector")
    offsets = np.zeros((len(means), args.factor), dtype=np.float64)
    if args.noise:
        rng = np.random.default_rng(args.seed)
        offsets = rng.normal(
            0.0,
            args.noise * np.sqrt(np.mean(means * means)),
            size=offsets.shape,
        )
        offsets -= np.mean(offsets, axis=1, keepdims=True)
    baseline = np.repeat(means, args.factor)
    baseline_score = exact_score(baseline)
    best = baseline.copy()
    best_score = baseline_score
    reference_max = float(np.max(np.convolve(baseline, baseline)))

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "runs-block-split" / f"k{args.factor}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "baseline.npy", baseline)
    atomic_npy(run_dir / "best.npy", best)
    evaluations = 0
    current_beta = 0.0

    def objective_gradient(flat_offsets: np.ndarray) -> tuple[float, np.ndarray]:
        nonlocal evaluations
        evaluations += 1
        raw = flat_offsets.reshape(len(means), args.factor)
        f = lift(means, raw)
        convolution = fftconvolve(f, f, mode="full")
        logits = current_beta * (convolution / reference_max - 1.0)
        lse = float(logsumexp(logits))
        weights = np.exp(logits - lse)
        smooth_max = reference_max * (1.0 + lse / current_beta)
        objective = float(np.log(smooth_max))
        gradient = 2.0 * fftconvolve(weights, f[::-1], mode="valid") / smooth_max
        gradient = gradient.reshape(len(means), args.factor)
        gradient -= np.mean(gradient, axis=1, keepdims=True)
        return objective, gradient.reshape(-1)

    with events_path.open("a", encoding="utf-8") as events:
        for beta in (float(value) for value in args.betas.split(",")):
            current_beta = beta
            result = minimize(
                objective_gradient,
                offsets.reshape(-1),
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
            offsets = result.x.reshape(len(means), args.factor)
            offsets -= np.mean(offsets, axis=1, keepdims=True)
            candidate = lift(means, offsets)
            candidate_score = exact_score(candidate)
            accepted = candidate_score < best_score
            if accepted:
                best = candidate.copy()
                best_score = candidate_score
                atomic_npy(run_dir / "best.npy", best)
            event = {
                "accepted": accepted,
                "best_score": best_score,
                "beta": beta,
                "candidate_score": candidate_score,
                "factor": args.factor,
                "gain": baseline_score - best_score,
                "nfev": int(result.nfev),
                "nit": int(result.nit),
                "offset_rms": float(np.sqrt(np.mean(offsets * offsets))),
                "optimizer_message": str(result.message),
                "optimizer_status": int(result.status),
                "total_evaluations": evaluations,
            }
            events.write(json.dumps(event, sort_keys=True) + "\n")
            events.flush()
            print(json.dumps(event, sort_keys=True), flush=True)

    summary = {
        "baseline_score": baseline_score,
        "best_score": best_score,
        "evaluations": evaluations,
        "factor": args.factor,
        "gain": baseline_score - best_score,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
