#!/usr/bin/env python3
"""Bounded Fourier-square and semismooth-Newton probes for signed C3.

The verifier objective for a mass-normalized vector ``f`` is

    2 n max_k [z^k] F(z)^2,    F(z) = sum_j f_j z^j.

This program tests two routes that are not value-space sign-wall mutations:

* projection onto a one-sided cap on coefficients of ``F^2``, followed by
  nearest frequencywise root signs, inverse transformation, causal truncation,
  and a line search (a proposal heuristic, not exact causal factorization);
* a matrix-free generalized Newton step for the smooth finite-max KKT system,
  including the softmax covariance term in the Hessian-vector product.

All convolution evaluations here are single-threaded FFT screening.  The tool
never calls the Arena and never labels a screened point submission-ready.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.fft import irfft, next_fast_len, rfft
from scipy.signal import fftconvolve
from scipy.sparse.linalg import LinearOperator, cg
from scipy.special import logsumexp


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
DEFAULT_INPUT = (
    CAMPAIGN
    / "analytic/c3_precision_escape/runs/20260815T063056Z-39272/best.npy"
)
VERIFIER = (
    CAMPAIGN
    / "state/problems/third-autocorrelation-inequality/"
    "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9.py"
)
VERIFIER_SHA256 = "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9"
BASELINE_OFFICIAL_SCORE = 1.4515653796072292
LIVE_LEADER = 1.4515718638902069
MINIMUM_IMPROVEMENT = 1e-5
TARGET = LIVE_LEADER - MINIMUM_IMPROVEMENT


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def append_jsonl(path: Path, value: Any) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class FFTObjective:
    def __init__(self, n: int):
        self.n = n
        self.transform_length = next_fast_len(2 * n - 1)

    def convolution(self, values: np.ndarray) -> np.ndarray:
        spectrum = rfft(values, self.transform_length)
        return irfft(spectrum * spectrum, self.transform_length)[: 2 * self.n - 1]

    def score(self, values: np.ndarray) -> float:
        normalized = np.asarray(values, dtype=np.float64)
        normalized = normalized / float(np.sum(normalized))
        return float(2.0 * self.n * np.max(self.convolution(normalized)))


def project_cap_with_mass(convolution: np.ndarray, cap: float) -> np.ndarray:
    """Euclidean projection onto {q <= cap, sum(q)=1}."""
    lower = -max(1.0, float(np.max(np.abs(convolution))))
    upper = max(1.0, float(np.max(np.abs(convolution))))
    for _ in range(80):
        shift = 0.5 * (lower + upper)
        mass = float(np.sum(np.minimum(convolution + shift, cap)))
        if mass < 1.0:
            lower = shift
        else:
            upper = shift
    return np.minimum(convolution + 0.5 * (lower + upper), cap)


def closest_causal_square_root(
    projected: np.ndarray, current: np.ndarray, transform_length: int
) -> tuple[np.ndarray, int]:
    """Choose nearest frequency roots, then causally truncate and normalize.

    The untruncated inverse transform is a periodic Fourier root.  Truncating
    to the first ``len(current)`` entries generally destroys exact equality to
    ``projected``; callers use the result only as a screened direction.
    """
    padded = np.pad(current, (0, transform_length - len(current)))
    current_spectrum = rfft(padded, transform_length)
    projected_spectrum = rfft(projected, transform_length)
    roots = np.sqrt(projected_spectrum)
    flip = np.abs(-roots - current_spectrum) < np.abs(roots - current_spectrum)
    roots[flip] *= -1.0
    candidate = irfft(roots, transform_length)[: len(current)]
    if float(np.sum(candidate)) < 0.0:
        candidate *= -1.0
    candidate /= float(np.sum(candidate))
    return candidate, int(np.count_nonzero(flip))


def cap_projection_probe(
    f: np.ndarray, objective: FFTObjective, events: Path
) -> list[dict[str, Any]]:
    convolution = objective.convolution(f)
    maximum = float(np.max(convolution))
    baseline = objective.score(f)
    rows: list[dict[str, Any]] = []
    for relative_drop in (3e-6, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3):
        projected = project_cap_with_mass(
            convolution, maximum * (1.0 - relative_drop)
        )
        root, flips = closest_causal_square_root(
            projected, f, objective.transform_length
        )
        direction = root - f
        best_score = baseline
        best_alpha = 0.0
        for alpha in (-4.0, -2.0, -1.0, -0.5, 0.05, 0.1, 0.2, 0.4, 0.7, 1.0, 2.0, 4.0):
            candidate = f + alpha * direction
            if abs(float(np.sum(candidate))) < 1e-12:
                continue
            score = objective.score(candidate)
            if score < best_score:
                best_score = score
                best_alpha = alpha
        row = {
            "event": "cap_square_projection",
            "relative_cap_drop": relative_drop,
            "nearest_root_frequency_signs": flips,
            "direction_rms": float(np.sqrt(np.mean(direction * direction))),
            "best_fft_score": best_score,
            "best_alpha": best_alpha,
            "fft_gain": baseline - best_score,
        }
        append_jsonl(events, row)
        rows.append(row)
    return rows


def branch_probe(
    f: np.ndarray, objective: FFTObjective, events: Path
) -> dict[str, Any]:
    padded = np.pad(f, (0, objective.transform_length - len(f)))
    spectrum = rfft(padded, objective.transform_length)
    eligible = np.arange(1, len(spectrum) - 1)
    lowest = eligible[np.argsort(np.abs(spectrum[eligible]))[:1024]]
    baseline = objective.score(f)
    best = {
        "best_fft_score": baseline,
        "fft_gain": 0.0,
        "frequencies": [],
        "alpha": 0.0,
        "group_size": 0,
    }
    tested = 0

    def test(frequencies: np.ndarray, group_size: int) -> None:
        nonlocal tested, best
        delta_spectrum = np.zeros_like(spectrum)
        delta_spectrum[frequencies] = -2.0 * spectrum[frequencies]
        direction = irfft(delta_spectrum, objective.transform_length)[: len(f)]
        for alpha in (-2.0, -1.0, -0.5, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
            candidate = f + alpha * direction
            if abs(float(np.sum(candidate))) < 1e-12:
                continue
            score = objective.score(candidate)
            tested += 1
            if score < best["best_fft_score"]:
                best = {
                    "best_fft_score": score,
                    "fft_gain": baseline - score,
                    "frequencies": [int(value) for value in frequencies],
                    "alpha": alpha,
                    "group_size": group_size,
                }

    for frequency in lowest[:128]:
        test(np.asarray([frequency]), 1)
    random = np.random.default_rng(20260815)
    for group_size in (2, 3, 4, 6, 8, 12, 16, 24, 32):
        for _ in range(30):
            test(random.choice(lowest, size=group_size, replace=False), group_size)

    result = {
        "event": "fourier_branch_screen",
        "tested_candidates": tested,
        "frequency_pool": len(lowest),
        **best,
    }
    append_jsonl(events, result)
    return result


def newton_probe(
    f_mass_n: np.ndarray, beta: float, events: Path
) -> dict[str, Any]:
    n = len(f_mass_n)
    convolution = fftconvolve(f_mass_n, f_mass_n, mode="full")
    reference = float(np.max(convolution))
    logits = beta * (convolution / reference - 1.0)
    log_partition = float(logsumexp(logits))
    weights = np.exp(logits - log_partition)
    smooth_maximum = reference * (1.0 + log_partition / beta)
    gradient_s = 2.0 * fftconvolve(weights, f_mass_n[::-1], mode="valid")
    gradient = gradient_s / smooth_maximum
    gradient -= np.mean(gradient)
    calls = 0
    damping = 1e-2

    def hessian_vector(direction: np.ndarray) -> np.ndarray:
        nonlocal calls
        calls += 1
        direction = direction - np.mean(direction)
        convolution_derivative = 2.0 * fftconvolve(
            f_mass_n, direction, mode="full"
        )
        weighted_mean = float(np.dot(weights, convolution_derivative))
        weight_derivative = (
            (beta / reference)
            * weights
            * (convolution_derivative - weighted_mean)
        )
        hessian_s = 2.0 * fftconvolve(
            weights, direction[::-1], mode="valid"
        ) + 2.0 * fftconvolve(
            weight_derivative, f_mass_n[::-1], mode="valid"
        )
        image = (
            hessian_s / smooth_maximum
            - gradient
            * (float(np.dot(gradient_s, direction)) / smooth_maximum)
            + damping * direction
        )
        return image - np.mean(image)

    operator = LinearOperator(
        (n, n), matvec=hessian_vector, dtype=np.dtype(np.float64)
    )
    direction, cg_info = cg(
        operator,
        -gradient,
        rtol=1e-5,
        atol=1e-12,
        maxiter=45,
    )
    direction -= np.mean(direction)
    baseline_fft_score = float(2.0 * reference / n)
    best_score = baseline_fft_score
    best_alpha = 0.0
    for alpha in (-4.0, -2.0, -1.0, -0.5, 0.03125, 0.0625, 0.125, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0):
        candidate = f_mass_n + alpha * direction
        candidate *= n / float(np.sum(candidate))
        score = float(2.0 * np.max(fftconvolve(candidate, candidate)) / n)
        if score < best_score:
            best_score = score
            best_alpha = alpha
    result = {
        "event": "semismooth_newton",
        "beta": beta,
        "damping": damping,
        "effective_dual_support": float(1.0 / np.dot(weights, weights)),
        "dual_support_above_1e-14": int(np.count_nonzero(weights > 1e-14)),
        "projected_gradient_norm": float(np.linalg.norm(gradient)),
        "cg_info": int(cg_info),
        "hessian_vector_products": calls,
        "direction_rms": float(np.sqrt(np.mean(direction * direction))),
        "best_fft_score": best_score,
        "best_alpha": best_alpha,
        "fft_gain": baseline_fft_score - best_score,
    }
    append_jsonl(events, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run-root", type=Path, default=HERE / "runs")
    parser.add_argument("--run-name")
    args = parser.parse_args()

    if sha256_file(VERIFIER) != VERIFIER_SHA256:
        raise RuntimeError("frozen C3 verifier hash mismatch")
    raw = np.load(args.input, allow_pickle=False).astype(np.float64)
    if raw.ndim != 1 or not raw.size or not np.isfinite(raw).all():
        raise ValueError("input must be a finite nonempty vector")
    n = len(raw)
    f = raw / float(np.sum(raw))
    objective = FFTObjective(n)
    baseline_fft_score = objective.score(f)
    if abs(baseline_fft_score - BASELINE_OFFICIAL_SCORE) > 2e-12:
        raise RuntimeError("FFT screen does not reproduce the frozen official baseline")

    run_name = args.run_name or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run = args.run_root / run_name
    run.mkdir(parents=True, exist_ok=False)
    events = run / "events.jsonl"
    config = {
        "schema": 1,
        "input": str(args.input.relative_to(CAMPAIGN)),
        "input_artifact_sha256": sha256_file(args.input),
        "input_values_float64_sha256": hashlib.sha256(raw.tobytes()).hexdigest(),
        "n": n,
        "verifier_sha256": VERIFIER_SHA256,
        "official_baseline_score": BASELINE_OFFICIAL_SCORE,
        "live_leader": LIVE_LEADER,
        "minimum_improvement": MINIMUM_IMPROVEMENT,
        "strict_target": TARGET,
        "fft_transform_length": objective.transform_length,
        "screening_only": True,
    }
    atomic_json(run / "config.json", config)
    append_jsonl(events, {"event": "config", **config})

    caps = cap_projection_probe(f, objective, events)
    branches = branch_probe(f, objective, events)
    f_mass_n = f * n
    newton = [
        newton_probe(f_mass_n, beta, events)
        for beta in (3e9, 1e10, 3e10, 1e11)
    ]
    all_fft_scores = [row["best_fft_score"] for row in caps]
    all_fft_scores.append(branches["best_fft_score"])
    all_fft_scores.extend(row["best_fft_score"] for row in newton)
    best_screen = min(all_fft_scores)
    summary = {
        "schema": 1,
        "status": "bounded_no_gate",
        "official_baseline_score": BASELINE_OFFICIAL_SCORE,
        "baseline_fft_score": baseline_fft_score,
        "best_fft_screen_score": best_screen,
        "best_fft_screen_gain": baseline_fft_score - best_screen,
        "strict_target": TARGET,
        "remaining_gate_gap": BASELINE_OFFICIAL_SCORE - TARGET,
        "gate_cleared": best_screen < TARGET,
        "cap_projection_trials": len(caps),
        "fourier_branch_candidates": branches["tested_candidates"],
        "newton_systems": len(newton),
        "maximum_newton_fft_gain": max(row["fft_gain"] for row in newton),
        "screening_boundary": (
            "FFT values are proposal diagnostics, not official-verifier receipts. "
            "No candidate approached the gate, so no Arena verify or submit was attempted."
        ),
        "config_sha256": sha256_file(run / "config.json"),
        "events_sha256": sha256_file(events),
        "source_sha256": sha256_file(Path(__file__)),
    }
    atomic_json(run / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
