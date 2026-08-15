#!/usr/bin/env python3
"""Float64 L-BFGS cascade for the C1 max-autoconvolution objective."""

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


def exact_score(f: np.ndarray, *, signed: bool = False) -> float:
    values = np.asarray(f, dtype=np.float64)
    if not signed:
        values = np.maximum(values, 0.0)
    convolution = np.convolve(values, values, mode="full")
    return float(2.0 * len(values) * np.max(convolution) / np.sum(values) ** 2)


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
    parser.add_argument("--betas", default="1e6,3e6,1e7,3e7,1e8,3e8,1e9")
    parser.add_argument("--maxiter", type=int, default=120)
    parser.add_argument("--maxcor", type=int, default=12)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--gate", type=float, default=1e-8)
    parser.add_argument("--signed", action="store_true")
    args = parser.parse_args()

    f = np.load(args.input, allow_pickle=False).astype(np.float64)
    if not args.signed:
        f = np.maximum(f, 0.0)
    f *= len(f) / np.sum(f)
    seed_score = exact_score(f, signed=args.signed)
    best = f.copy()
    best_score = seed_score
    reference_conv = np.convolve(f, f, mode="full")
    reference_max = float(np.max(reference_conv))
    run_dir = args.run_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "seed.npy", f)
    atomic_npy(run_dir / "best.npy", best)

    evaluations = 0
    current_beta = 0.0

    def objective_gradient(x: np.ndarray) -> tuple[float, np.ndarray]:
        nonlocal evaluations
        evaluations += 1
        convolution = fftconvolve(x, x, mode="full")
        logits = current_beta * (convolution / reference_max - 1.0)
        lse = float(logsumexp(logits))
        weights = np.exp(logits - lse)
        smooth_max = reference_max * (1.0 + lse / current_beta)
        mass = float(np.sum(x))
        objective = float(np.log(smooth_max) - 2.0 * np.log(abs(mass)))
        gradient = (
            2.0 * fftconvolve(weights, x[::-1], mode="valid") / smooth_max
            - 2.0 / mass
        )
        return objective, gradient

    with events_path.open("a", encoding="utf-8") as events:
        for beta in (float(value) for value in args.betas.split(",")):
            current_beta = beta
            result = minimize(
                objective_gradient,
                f,
                method="L-BFGS-B",
                jac=True,
                bounds=[(None, None)] * len(f) if args.signed else [(0.0, None)] * len(f),
                options={
                    "maxiter": args.maxiter,
                    "maxcor": args.maxcor,
                    "ftol": 1e-15,
                    "gtol": 1e-12,
                    "maxls": 30,
                },
            )
            f = np.asarray(result.x, dtype=np.float64)
            if not args.signed:
                f = np.maximum(f, 0.0)
            f *= len(f) / np.sum(f)
            candidate_score = exact_score(f, signed=args.signed)
            accepted = candidate_score < best_score
            if accepted:
                best = f.copy()
                best_score = candidate_score
                atomic_npy(run_dir / "best.npy", best)
            event = {
                "beta": beta,
                "candidate_score": candidate_score,
                "best_score": best_score,
                "gain": seed_score - best_score,
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
        "seed_score": seed_score,
        "best_score": best_score,
        "gain": seed_score - best_score,
        "target_score": seed_score - args.gate,
        "gate_cleared": best_score <= seed_score - args.gate,
        "evaluations": evaluations,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
