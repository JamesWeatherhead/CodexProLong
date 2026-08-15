#!/usr/bin/env python3
"""C3 smooth-max continuation with the signed-square map f = u * |u|."""

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


def exact_score(values: np.ndarray) -> float:
    f = np.asarray(values, dtype=np.float64)
    convolution = np.convolve(f, f, mode="full")
    return float(2.0 * len(f) * np.max(convolution) / np.sum(f) ** 2)


def normalize(values: np.ndarray) -> np.ndarray:
    f = np.asarray(values, dtype=np.float64)
    mass = float(np.sum(f))
    if not np.isfinite(f).all() or not np.isfinite(mass) or abs(mass) < 1e-12:
        raise RuntimeError("signed-square iterate has invalid mass")
    return f * (len(f) / mass)


def to_parameter(values: np.ndarray) -> np.ndarray:
    f = np.asarray(values, dtype=np.float64)
    return np.sign(f) * np.sqrt(np.abs(f))


def from_parameter(parameter: np.ndarray) -> np.ndarray:
    u = np.asarray(parameter, dtype=np.float64)
    return u * np.abs(u)


def atomic_npy(path: Path, values: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "leader.npy")
    parser.add_argument("--betas", default="1e4,3e4,1e5,3e5,1e6,3e6,1e7")
    parser.add_argument("--maxiter", type=int, default=1500)
    parser.add_argument("--maxcor", type=int, default=100)
    parser.add_argument("--noise", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--gate", type=float, default=1e-5)
    parser.add_argument(
        "--reset-on-reject",
        action="store_true",
        help="restart the next beta from the exact best instead of carrying the surrogate iterate",
    )
    args = parser.parse_args()

    baseline = normalize(np.load(args.input, allow_pickle=False).astype(np.float64))
    baseline_score = exact_score(baseline)
    f = baseline.copy()
    if args.noise:
        rng = np.random.default_rng(args.seed)
        scale = float(np.sqrt(np.mean(np.abs(f))))
        u = to_parameter(f) + rng.normal(0.0, args.noise * scale, size=f.shape)
        f = normalize(from_parameter(u))
    optimization_seed_score = exact_score(f)
    best = baseline.copy()
    best_score = baseline_score
    reference_max = float(np.max(np.convolve(f, f, mode="full")))

    run_dir = ROOT / "runs-signed-square" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "seed.npy", f)
    atomic_npy(run_dir / "best.npy", best)

    evaluations = 0
    current_beta = 0.0

    def objective_gradient(u: np.ndarray) -> tuple[float, np.ndarray]:
        nonlocal evaluations
        evaluations += 1
        x = from_parameter(u)
        convolution = fftconvolve(x, x, mode="full")
        logits = current_beta * (convolution / reference_max - 1.0)
        lse = float(logsumexp(logits))
        weights = np.exp(logits - lse)
        smooth_max = reference_max * (1.0 + lse / current_beta)
        mass = float(np.sum(x))
        objective = float(np.log(smooth_max) - 2.0 * np.log(abs(mass)))
        gradient_f = (
            2.0 * fftconvolve(weights, x[::-1], mode="valid") / smooth_max
            - 2.0 / mass
        )
        return objective, gradient_f * (2.0 * np.abs(u))

    u = to_parameter(f)
    with events_path.open("a", encoding="utf-8") as events:
        for beta in (float(value) for value in args.betas.split(",")):
            current_beta = beta
            result = minimize(
                objective_gradient,
                u,
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
            candidate = normalize(from_parameter(np.asarray(result.x, dtype=np.float64)))
            candidate_score = exact_score(candidate)
            accepted = candidate_score < best_score
            if accepted:
                best = candidate.copy()
                best_score = candidate_score
                atomic_npy(run_dir / "best.npy", best)
            f = best.copy() if args.reset_on_reject and not accepted else candidate
            u = to_parameter(f)
            event = {
                "beta": beta,
                "candidate_score": candidate_score,
                "best_score": best_score,
                "gain": baseline_score - best_score,
                "accepted": accepted,
                "optimizer_success": bool(result.success),
                "optimizer_status": int(result.status),
                "optimizer_message": str(result.message),
                "nit": int(result.nit),
                "nfev": int(result.nfev),
                "total_evaluations": evaluations,
            }
            events.write(json.dumps(event, sort_keys=True) + "\n")
            events.flush()
            print(json.dumps(event, sort_keys=True), flush=True)

    summary = {
        "baseline_score": baseline_score,
        "optimization_seed_score": optimization_seed_score,
        "best_score": best_score,
        "gain": baseline_score - best_score,
        "target_score": baseline_score - args.gate,
        "gate_cleared": best_score <= baseline_score - args.gate,
        "evaluations": evaluations,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
