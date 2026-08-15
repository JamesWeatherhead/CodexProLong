#!/usr/bin/env python3
"""Signed-square continuation in deliberately changed sign-support basins."""

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


def normalize(f: np.ndarray) -> np.ndarray:
    return f * (len(f) / np.sum(f))


def to_parameter(f: np.ndarray) -> np.ndarray:
    return np.sign(f) * np.sqrt(np.abs(f))


def from_parameter(u: np.ndarray) -> np.ndarray:
    return u * np.abs(u)


def exact_score(f: np.ndarray) -> float:
    return float(2.0 * len(f) * np.max(np.convolve(f, f)) / np.sum(f) ** 2)


def atomic_npy(path: Path, f: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, f, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--flip-indices", required=True)
    parser.add_argument("--betas", default="1e7,3e7,1e8,3e8,1e9,3e9,1e10,3e10")
    parser.add_argument("--maxiter", type=int, default=700)
    parser.add_argument("--maxcor", type=int, default=80)
    parser.add_argument("--objective-scale", type=float, default=1e7)
    args = parser.parse_args()

    baseline = normalize(np.load(args.input, allow_pickle=False).astype(np.float64))
    baseline_score = exact_score(baseline)
    current = baseline.copy()
    indices = [int(value) for value in args.flip_indices.split(",") if value]
    for index in indices:
        current[index] *= -1.0
    current = normalize(current)
    initial_flipped_score = exact_score(current)
    best = baseline.copy()
    best_score = baseline_score
    reference_max = float(np.max(np.convolve(baseline, baseline)))
    n = len(baseline)

    name = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + "_".join(map(str, indices))
    run_dir = ROOT / "runs-support-flip" / name
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "baseline.npy", baseline)
    atomic_npy(run_dir / "seed.npy", current)
    atomic_npy(run_dir / "best.npy", best)
    evaluations = 0
    u = to_parameter(current)

    with events_path.open("a", encoding="utf-8") as events:
        for beta in (float(value) for value in args.betas.split(",")):

            def objective_gradient(parameter: np.ndarray) -> tuple[float, np.ndarray]:
                nonlocal evaluations
                evaluations += 1
                f = from_parameter(parameter)
                convolution = fftconvolve(f, f, mode="full")
                logits = beta * (convolution / reference_max - 1.0)
                lse = float(logsumexp(logits))
                weights = np.exp(logits - lse)
                smooth_max = reference_max * (1.0 + lse / beta)
                mass = float(np.sum(f))
                prefactor = args.objective_scale * 2.0 * n / (mass * mass)
                objective = prefactor * smooth_max
                gradient_f = prefactor * (
                    2.0 * fftconvolve(weights, f[::-1], mode="valid")
                    - 2.0 * smooth_max / mass
                )
                return float(objective), gradient_f * (2.0 * np.abs(parameter))

            result = minimize(
                objective_gradient,
                u,
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
            u = np.asarray(result.x, dtype=np.float64)
            current = normalize(from_parameter(u))
            u = to_parameter(current)
            candidate_score = exact_score(current)
            accepted = candidate_score < best_score
            if accepted:
                best = current.copy()
                best_score = candidate_score
                atomic_npy(run_dir / "best.npy", best)
            event = {
                "beta": beta,
                "candidate_score": candidate_score,
                "best_score": best_score,
                "gain": baseline_score - best_score,
                "accepted": accepted,
                "negative_count": int(np.count_nonzero(current < 0.0)),
                "rms_from_baseline": float(np.sqrt(np.mean((current - baseline) ** 2))),
                "nit": int(result.nit),
                "nfev": int(result.nfev),
                "optimizer_status": int(result.status),
                "optimizer_message": str(result.message),
                "total_evaluations": evaluations,
                "gate_gap": best_score - TARGET_SCORE,
            }
            events.write(json.dumps(event, sort_keys=True) + "\n")
            events.flush()
            print(json.dumps(event, sort_keys=True), flush=True)

    payload = run_dir / "best.npy"
    summary = {
        "input": str(args.input),
        "flip_indices": indices,
        "baseline_score": baseline_score,
        "initial_flipped_score": initial_flipped_score,
        "best_score": best_score,
        "gain": baseline_score - best_score,
        "target_score": TARGET_SCORE,
        "gate_gap": best_score - TARGET_SCORE,
        "gate_cleared": best_score <= TARGET_SCORE,
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
