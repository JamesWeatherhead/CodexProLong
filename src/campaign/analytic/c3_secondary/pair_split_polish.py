#!/usr/bin/env python3
"""Open the block-repeat nullspace with pair-antisymmetric optimization.

For a 25,600-vector f, optimize x[2i]=f[i]+d[i], x[2i+1]=f[i]-d[i].
This keeps the verifier mass exactly fixed while exposing the new 51,200-point
within-block directions. FFT smooth-max drives the search; only direct
float64 numpy.convolve scores are checkpointed as accepted constructions.
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


def split_vector(base: np.ndarray, difference: np.ndarray) -> np.ndarray:
    result = np.empty(2 * len(base), dtype=np.float64)
    result[0::2] = base + difference
    result[1::2] = base - difference
    return result


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
    parser.add_argument("--betas", default="1e7,3e7,1e8,3e8,1e9,3e9,1e10")
    parser.add_argument("--maxiter", type=int, default=1200)
    parser.add_argument("--maxcor", type=int, default=80)
    parser.add_argument("--objective-scale", type=float, default=1e7)
    parser.add_argument("--noise", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument(
        "--carry-worse",
        action="store_true",
        help="Continue smooth states even if their exact max is temporarily worse.",
    )
    args = parser.parse_args()

    base = np.load(args.input, allow_pickle=False).astype(np.float64)
    base *= len(base) / np.sum(base)
    rng = np.random.default_rng(args.seed)
    difference = rng.normal(0.0, args.noise, size=base.shape)
    current = split_vector(base, difference)
    baseline = split_vector(base, np.zeros_like(base))
    baseline_score, baseline_argmax, _ = exact_metrics(baseline)
    best = baseline.copy()
    best_score = baseline_score
    reference_max = float(np.max(np.convolve(baseline, baseline, mode="full")))

    run_dir = ROOT / "runs-pair-split" / datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "seed.npy", current)
    atomic_npy(run_dir / "best.npy", best)
    evaluations = 0

    with events_path.open("a", encoding="utf-8") as events:
        for beta in (float(value) for value in args.betas.split(",")):

            def objective_gradient(d: np.ndarray) -> tuple[float, np.ndarray]:
                nonlocal evaluations
                evaluations += 1
                x = split_vector(base, d)
                convolution = fftconvolve(x, x, mode="full")
                logits = beta * (convolution / reference_max - 1.0)
                lse = float(logsumexp(logits))
                weights = np.exp(logits - lse)
                objective = args.objective_scale * (1.0 + lse / beta)
                gradient_x = (
                    args.objective_scale
                    * 2.0
                    * fftconvolve(weights, x[::-1], mode="valid")
                    / reference_max
                )
                gradient_d = gradient_x[0::2] - gradient_x[1::2]
                return float(objective), gradient_d

            result = minimize(
                objective_gradient,
                difference,
                method="L-BFGS-B",
                jac=True,
                options={
                    "maxiter": args.maxiter,
                    "maxcor": args.maxcor,
                    "ftol": 1e-15,
                    "gtol": 1e-10,
                    "maxls": 40,
                },
            )
            candidate_difference = np.asarray(result.x, dtype=np.float64)
            candidate = split_vector(base, candidate_difference)
            candidate_score, candidate_argmax, _ = exact_metrics(candidate)
            accepted = candidate_score < best_score
            if accepted:
                best = candidate.copy()
                best_score = candidate_score
                atomic_npy(run_dir / "best.npy", best)
            if args.carry_worse or accepted:
                difference = candidate_difference
                current = candidate
            else:
                # Restore the best pair split; the base pair means never move.
                difference = 0.5 * (best[0::2] - best[1::2])
                current = best
            event = {
                "beta": beta,
                "candidate_score": candidate_score,
                "candidate_argmax": candidate_argmax,
                "best_score": best_score,
                "gain": baseline_score - best_score,
                "accepted": accepted,
                "difference_rms": float(
                    np.sqrt(np.mean(candidate_difference * candidate_difference))
                ),
                "difference_max_abs": float(np.max(np.abs(candidate_difference))),
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
        "baseline_score": baseline_score,
        "baseline_argmax": baseline_argmax,
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
