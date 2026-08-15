#!/usr/bin/env python3
"""C3 smooth-max continuation in a configurable signed-power geometry.

The map ``f = sign(u) * abs(u)**power`` changes the local metric without
changing the set of finite signed vectors.  Direct verifier acceptance remains
the only criterion for updating the persistent best checkpoint.
"""

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
    return float(2.0 * len(f) * np.max(np.convolve(f, f)) / np.sum(f) ** 2)


def normalize(values: np.ndarray) -> np.ndarray:
    f = np.asarray(values, dtype=np.float64)
    mass = float(np.sum(f))
    if not np.isfinite(f).all() or not np.isfinite(mass) or abs(mass) < 1e-12:
        raise RuntimeError("signed-power iterate has invalid mass")
    return f * (len(f) / mass)


def to_parameter(values: np.ndarray, power: float) -> np.ndarray:
    f = np.asarray(values, dtype=np.float64)
    return np.sign(f) * np.abs(f) ** (1.0 / power)


def from_parameter(parameter: np.ndarray, power: float) -> np.ndarray:
    u = np.asarray(parameter, dtype=np.float64)
    return np.sign(u) * np.abs(u) ** power


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
    parser.add_argument("--power", type=float, default=3.0)
    parser.add_argument("--betas", default="1e5,3e5,1e6,3e6,1e7,3e7,1e8")
    parser.add_argument("--maxiter", type=int, default=1500)
    parser.add_argument("--maxcor", type=int, default=100)
    parser.add_argument("--noise", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--gate", type=float, default=1e-5)
    args = parser.parse_args()
    if not np.isfinite(args.power) or args.power <= 1.0:
        raise RuntimeError("power must be finite and greater than one")
    if args.noise < 0.0:
        raise RuntimeError("noise must be non-negative")

    baseline = normalize(np.load(args.input, allow_pickle=False).astype(np.float64))
    baseline_score = exact_score(baseline)
    u = to_parameter(baseline, args.power)
    if args.noise:
        rng = np.random.default_rng(args.seed)
        u += rng.normal(0.0, args.noise * np.sqrt(np.mean(u * u)), size=u.shape)
    f = normalize(from_parameter(u, args.power))
    u = to_parameter(f, args.power)
    best = baseline.copy()
    best_score = baseline_score
    reference_max = float(np.max(np.convolve(f, f)))

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "runs-signed-power" / f"p{args.power:g}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "seed.npy", f)
    atomic_npy(run_dir / "best.npy", best)

    evaluations = 0
    current_beta = 0.0

    def objective_gradient(parameter: np.ndarray) -> tuple[float, np.ndarray]:
        nonlocal evaluations
        evaluations += 1
        values = from_parameter(parameter, args.power)
        convolution = fftconvolve(values, values, mode="full")
        logits = current_beta * (convolution / reference_max - 1.0)
        lse = float(logsumexp(logits))
        weights = np.exp(logits - lse)
        smooth_max = reference_max * (1.0 + lse / current_beta)
        mass = float(np.sum(values))
        objective = float(np.log(smooth_max) - 2.0 * np.log(abs(mass)))
        gradient_f = (
            2.0 * fftconvolve(weights, values[::-1], mode="valid") / smooth_max
            - 2.0 / mass
        )
        derivative = args.power * np.abs(parameter) ** (args.power - 1.0)
        return objective, gradient_f * derivative

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
            candidate = normalize(from_parameter(result.x, args.power))
            candidate_score = exact_score(candidate)
            accepted = candidate_score < best_score
            if accepted:
                best = candidate.copy()
                best_score = candidate_score
                atomic_npy(run_dir / "best.npy", best)
            f = candidate
            u = to_parameter(f, args.power)
            event = {
                "accepted": accepted,
                "best_score": best_score,
                "beta": beta,
                "candidate_score": candidate_score,
                "gain": baseline_score - best_score,
                "nfev": int(result.nfev),
                "nit": int(result.nit),
                "optimizer_message": str(result.message),
                "optimizer_status": int(result.status),
                "power": args.power,
                "total_evaluations": evaluations,
            }
            events.write(json.dumps(event, sort_keys=True) + "\n")
            events.flush()
            print(json.dumps(event, sort_keys=True), flush=True)

    summary = {
        "baseline_score": baseline_score,
        "best_score": best_score,
        "evaluations": evaluations,
        "gain": baseline_score - best_score,
        "gate_cleared": best_score <= baseline_score - args.gate,
        "power": args.power,
        "target_score": baseline_score - args.gate,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
