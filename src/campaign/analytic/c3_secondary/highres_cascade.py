#!/usr/bin/env python3
"""High-resolution block-repeat/noise C3 continuation with smooth-state carry.

This route intentionally carries each LogSumExp minimizer into the next beta
even when its exact max is temporarily worse. The best construction is kept
separately and accepted only by direct float64 ``numpy.convolve`` replay.
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


def exact_metrics(values: np.ndarray) -> tuple[float, int, float]:
    convolution = np.convolve(values, values, mode="full")
    argmax = int(np.argmax(convolution))
    score = float(
        2.0 * len(values) * convolution[argmax] / np.sum(values) ** 2
    )
    return score, argmax, float(convolution[argmax])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--betas", default="1e4,3e4,1e5,3e5,1e6,3e6,1e7,3e7,1e8,3e8,1e9,3e9,1e10")
    parser.add_argument("--maxiter", type=int, default=600)
    parser.add_argument("--maxcor", type=int, default=50)
    parser.add_argument("--noise", type=float, default=1e-6)
    parser.add_argument("--seed", type=int, default=20260816)
    parser.add_argument("--objective-scale", type=float, default=1e6)
    parser.add_argument(
        "--flip-smallest",
        type=int,
        default=0,
        help="Flip this many smallest-|f| coordinates before continuation.",
    )
    args = parser.parse_args()
    if args.repeat < 1:
        raise RuntimeError("repeat must be positive")

    source = normalize(np.load(args.input, allow_pickle=False).astype(np.float64))
    baseline = np.repeat(source, args.repeat)
    baseline = normalize(baseline)
    baseline_score, baseline_argmax, _ = exact_metrics(baseline)
    rng = np.random.default_rng(args.seed)
    current = baseline.copy()
    if args.flip_smallest:
        if not 0 <= args.flip_smallest <= len(current):
            raise RuntimeError("flip-smallest is outside the vector")
        flip_indices = np.argsort(np.abs(current))[: args.flip_smallest]
        current[flip_indices] *= -1.0
    perturbation = rng.normal(
        0.0, args.noise * np.sqrt(np.mean(baseline * baseline)), size=baseline.shape
    )
    perturbation -= np.mean(perturbation)
    current = normalize(current + perturbation)
    seed_score, _, _ = exact_metrics(current)
    best = baseline.copy()
    best_score = baseline_score
    reference_max = float(np.max(np.convolve(baseline, baseline, mode="full")))
    n = len(current)

    run_dir = ROOT / "runs-highres" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "baseline.npy", baseline)
    atomic_npy(run_dir / "seed.npy", current)
    atomic_npy(run_dir / "best.npy", best)
    atomic_npy(run_dir / "current.npy", current)
    evaluations = 0

    with events_path.open("a", encoding="utf-8") as events:
        for beta in (float(value) for value in args.betas.split(",")):

            def objective_gradient(x: np.ndarray) -> tuple[float, np.ndarray]:
                nonlocal evaluations
                evaluations += 1
                convolution = fftconvolve(x, x, mode="full")
                logits = beta * (convolution / reference_max - 1.0)
                lse = float(logsumexp(logits))
                weights = np.exp(logits - lse)
                smooth_max = reference_max * (1.0 + lse / beta)
                mass = float(np.sum(x))
                prefactor = args.objective_scale * 2.0 * n / (mass * mass)
                objective = prefactor * smooth_max
                gradient_smooth = 2.0 * fftconvolve(
                    weights, x[::-1], mode="valid"
                )
                gradient = prefactor * (
                    gradient_smooth - 2.0 * smooth_max / mass
                )
                return float(objective), gradient

            result = minimize(
                objective_gradient,
                current,
                method="L-BFGS-B",
                jac=True,
                options={
                    "maxiter": args.maxiter,
                    "maxcor": args.maxcor,
                    "ftol": 1e-15,
                    "gtol": 1e-9,
                    "maxls": 40,
                },
            )
            current = normalize(np.asarray(result.x, dtype=np.float64))
            atomic_npy(run_dir / "current.npy", current)
            candidate_score, candidate_argmax, _ = exact_metrics(current)
            accepted = candidate_score < best_score
            if accepted:
                best = current.copy()
                best_score = candidate_score
                atomic_npy(run_dir / "best.npy", best)
            event = {
                "beta": beta,
                "candidate_score": candidate_score,
                "candidate_argmax": candidate_argmax,
                "best_score": best_score,
                "gain": baseline_score - best_score,
                "accepted": accepted,
                "current_rms_from_baseline": float(
                    np.sqrt(np.mean((current - baseline) ** 2))
                ),
                "optimizer_success": bool(result.success),
                "optimizer_status": int(result.status),
                "optimizer_message": str(result.message),
                "nit": int(result.nit),
                "nfev": int(result.nfev),
                "total_evaluations": evaluations,
                "gate_gap": best_score - TARGET_SCORE,
            }
            events.write(json.dumps(event, sort_keys=True) + "\n")
            events.flush()
            print(json.dumps(event, sort_keys=True), flush=True)

    payload = run_dir / "best.npy"
    final_score, final_argmax, final_max = exact_metrics(best)
    summary = {
        "input": str(args.input),
        "repeat": args.repeat,
        "noise": args.noise,
        "flip_smallest": args.flip_smallest,
        "random_seed": args.seed,
        "baseline_score": baseline_score,
        "baseline_argmax": baseline_argmax,
        "seed_score": seed_score,
        "best_score": final_score,
        "gain": baseline_score - final_score,
        "target_score": TARGET_SCORE,
        "gate_gap": final_score - TARGET_SCORE,
        "gate_cleared": final_score <= TARGET_SCORE,
        "argmax": final_argmax,
        "max_convolution": final_max,
        "n": len(best),
        "sum": float(np.sum(best)),
        "finite": bool(np.isfinite(best).all()),
        "evaluations": evaluations,
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
