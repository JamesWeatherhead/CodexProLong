#!/usr/bin/env python3
"""Checkpointed, intended-domain topology search for Erdős minimum overlap.

The downloaded verifier is deliberately never executed on the host.  The
acceptance objective below is a direct implementation of the public problem
statement: float64 sum normalization followed by literal ``numpy.correlate``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import lsq_linear, minimize
from scipy.signal import fftconvolve
from scipy.special import expit, logsumexp

SLUG = "erdos-min-overlap"
LEADER_SOLUTION_ID = 2440
DEFAULT_SNAPSHOT = (
    Path(__file__).parent / "snapshots" / "erdos-min-overlap_20260814T232154Z.json"
)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_event(path: Path, **event: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_snapshot(path: Path) -> tuple[dict[str, Any], dict[str, Any], np.ndarray]:
    with path.open(encoding="utf-8") as handle:
        snapshot = json.load(handle)
    problem = snapshot["problem"]
    solution = next(
        item for item in snapshot["solutions"] if item["id"] == LEADER_SOLUTION_ID
    )
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
    if verifier_hash != snapshot["verifier_sha256"]:
        raise ValueError("snapshot verifier hash mismatch")
    values = np.asarray(solution["data"]["values"], dtype=np.float64)
    return snapshot, solution, values


def normalized_values(values: np.ndarray) -> np.ndarray:
    """Mirror only the public mathematical scoring specification."""
    sequence = np.asarray(values, dtype=np.float64)
    if sequence.ndim != 1 or sequence.size == 0:
        raise ValueError("values must be a nonempty one-dimensional array")
    if not np.isfinite(sequence).all():
        raise ValueError("values must be finite")
    if np.any(sequence < 0.0) or np.any(sequence > 1.0):
        raise ValueError("values must lie in [0, 1]")
    target = sequence.size / 2.0
    current = float(np.sum(sequence))
    if current != target:
        if current == 0.0:
            raise ValueError("cannot normalize a zero-sum sequence")
        sequence = sequence * (target / current)
    if np.any(sequence < 0.0) or np.any(sequence > 1.0):
        raise ValueError("normalization moved a value outside [0, 1]")
    return sequence


def exact_score(values: np.ndarray) -> float:
    sequence = normalized_values(values)
    correlations = np.correlate(sequence, 1.0 - sequence, mode="full")
    return float(np.max(correlations) * (2.0 / sequence.size))


def score_profile(values: np.ndarray) -> np.ndarray:
    sequence = normalized_values(values)
    return np.correlate(sequence, 1.0 - sequence, mode="full") * (2.0 / sequence.size)


def capped_simplex_projection(values: np.ndarray) -> np.ndarray:
    """Euclidean projection onto 0 <= x <= 1 and sum(x) = n/2."""
    values = np.asarray(values, dtype=np.float64)
    target = values.size / 2.0
    lower = -float(np.max(values)) - 1.0
    upper = 1.0 - float(np.min(values)) + 1.0
    for _ in range(80):
        midpoint = (lower + upper) / 2.0
        total = float(np.sum(np.clip(values + midpoint, 0.0, 1.0)))
        if total < target:
            lower = midpoint
        else:
            upper = midpoint
    projected = np.clip(values + (lower + upper) / 2.0, 0.0, 1.0)
    # Correct the last few ulps without leaving the box.
    residual = target - float(np.sum(projected))
    if residual:
        free = np.flatnonzero((projected > 1e-12) & (projected < 1.0 - 1e-12))
        if free.size:
            projected[free] += residual / free.size
    return projected


def periodic_integral(values: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Integral of the periodic step extension over normalized coordinates."""
    n = values.size
    periods = np.floor(points).astype(np.int64)
    fractions = points - periods
    scaled = fractions * n
    indices = np.minimum(np.floor(scaled).astype(np.int64), n - 1)
    offsets = scaled - indices
    cumulative = np.concatenate(([0.0], np.cumsum(values) / n))
    return (
        periods * float(np.mean(values))
        + cumulative[indices]
        + offsets * (values[indices] / n)
    )


def rebin_periodic(
    values: np.ndarray, output_size: int, phase: float = 0.0
) -> np.ndarray:
    """Average a periodic source step function into a new, shifted grid."""
    edges = (np.arange(output_size + 1, dtype=np.float64) + phase) / output_size
    integrals = periodic_integral(values, edges)
    rebinned = output_size * np.diff(integrals)
    return capped_simplex_projection(np.clip(rebinned, 0.0, 1.0))


def zero_runs(values: np.ndarray, tolerance: float = 1e-15) -> list[tuple[int, int]]:
    mask = values <= tolerance
    padded = np.pad(mask.astype(np.int8), (1, 1))
    changes = np.diff(padded)
    starts = np.flatnonzero(changes == 1)
    stops = np.flatnonzero(changes == -1)
    return [(int(start), int(stop)) for start, stop in zip(starts, stops, strict=True)]


def lag_gradient(values: np.ndarray, lag: int) -> np.ndarray:
    """Gradient of one unscaled overlap correlation at a signed lag."""
    n = values.size
    second_start = max(0, -lag)
    second_stop = min(n, n - lag)
    second = np.arange(second_start, second_stop)
    first = second + lag
    gradient = np.zeros(n, dtype=np.float64)
    gradient[first] += 1.0 - values[second]
    gradient[second] -= values[first]
    return gradient


def active_dual_diagnostic(
    values: np.ndarray, active_tolerance: float
) -> dict[str, object]:
    profile = score_profile(values)
    active_indices = np.flatnonzero(profile.max() - profile <= active_tolerance)
    lags = active_indices - (values.size - 1)
    gradients = np.asarray([lag_gradient(values, int(lag)) for lag in lags])
    gradients *= 2.0 / values.size
    free = np.flatnonzero((values > 1e-12) & (values < 1.0 - 1e-12))

    # Convex-combination stationarity on free variables, with a free equality
    # multiplier nu: G^T lambda + nu*1 = 0, sum(lambda) = 1, lambda >= 0.
    equations = np.zeros((free.size + 1, active_indices.size + 1))
    equations[: free.size, : active_indices.size] = gradients[:, free].T
    equations[: free.size, -1] = 1.0
    equations[-1, : active_indices.size] = 1.0
    rhs = np.zeros(free.size + 1)
    rhs[-1] = 1.0
    lower = np.concatenate((np.zeros(active_indices.size), [-np.inf]))
    upper = np.full(active_indices.size + 1, np.inf)
    result = lsq_linear(
        equations,
        rhs,
        bounds=(lower, upper),
        lsmr_tol=1e-13,
        max_iter=500,
        verbose=0,
    )
    lambdas = result.x[:-1]
    nu = float(result.x[-1])
    stationarity = gradients.T @ lambdas + nu
    lower_indices = np.flatnonzero(values <= 1e-12)
    upper_indices = np.flatnonzero(values >= 1.0 - 1e-12)
    weak_lower = lower_indices[np.argsort(np.abs(stationarity[lower_indices]))[:16]]
    weak_upper = upper_indices[np.argsort(np.abs(stationarity[upper_indices]))[:16]]
    return {
        "active_lag_count": int(active_indices.size),
        "active_lags": lags.tolist(),
        "free_variable_count": int(free.size),
        "dual_success": bool(result.success),
        "dual_cost": float(result.cost),
        "dual_optimality": float(result.optimality),
        "lambda_min": float(lambdas.min()),
        "lambda_max": float(lambdas.max()),
        "lambda_sum": float(lambdas.sum()),
        "nu": nu,
        "free_stationarity_max_abs": float(np.max(np.abs(stationarity[free]))),
        "weak_lower_contacts": [
            {"index": int(index), "reduced_gradient": float(stationarity[index])}
            for index in weak_lower
        ],
        "weak_upper_contacts": [
            {"index": int(index), "reduced_gradient": float(stationarity[index])}
            for index in weak_upper
        ],
    }


def feasible_interval(values: np.ndarray, direction: np.ndarray) -> tuple[float, float]:
    positive = direction > 0.0
    negative = direction < 0.0
    lower = -np.inf
    upper = np.inf
    if np.any(positive):
        lower = max(lower, float(np.max(-values[positive] / direction[positive])))
        upper = min(
            upper,
            float(np.min((1.0 - values[positive]) / direction[positive])),
        )
    if np.any(negative):
        lower = max(
            lower,
            float(np.max((1.0 - values[negative]) / direction[negative])),
        )
        upper = min(upper, float(np.min(-values[negative] / direction[negative])))
    return lower, upper


class TrialBook:
    def __init__(self, seed: np.ndarray, run_dir: Path, live_score: float) -> None:
        self.seed = seed
        self.best = seed.copy()
        self.best_score = exact_score(seed)
        self.live_score = live_score
        self.run_dir = run_dir
        self.counts: dict[str, int] = {}
        self.family_best: dict[str, float] = {}

    def test(self, family: str, candidate: np.ndarray) -> None:
        self.counts[family] = self.counts.get(family, 0) + 1
        try:
            score = exact_score(candidate)
        except ValueError:
            return
        self.family_best[family] = min(self.family_best.get(family, np.inf), score)
        # Ignore isometric/roundoff ties; only checkpoint substantive decreases.
        if score < self.best_score - 1e-14:
            self.best = normalized_values(candidate).copy()
            self.best_score = score
            atomic_json(self.run_dir / "best.json", {"values": self.best.tolist()})


def test_direction(book: TrialBook, family: str, direction: np.ndarray) -> None:
    direction = direction - float(np.mean(direction))
    if not np.any(direction):
        return
    lower, upper = feasible_interval(book.seed, direction)
    fractions = (0.02, 0.05, 0.15, 0.35, 0.7, 1.0)
    for endpoint in (lower, upper):
        if np.isfinite(endpoint) and abs(endpoint) > 1e-15:
            for fraction in fractions:
                candidate = book.seed + fraction * endpoint * direction
                book.test(family, np.clip(candidate, 0.0, 1.0))


def run_rebin_and_phase(book: TrialBook) -> None:
    for output_size in range(384, 3073):
        book.test("integer_rebin", rebin_periodic(book.seed, output_size))
    phase_sizes = (384, 512, 768, 1024, 1280, 1536, 1792, 2048, 2304, 2560, 2816, 3072)
    for output_size in phase_sizes:
        for phase in np.linspace(-0.5, 0.5, 129):
            book.test(
                "grid_phase", rebin_periodic(book.seed, output_size, float(phase))
            )


def run_block_surgery(
    book: TrialBook, rng: np.random.Generator, directions: int
) -> None:
    n = book.seed.size
    widths = np.asarray((1, 2, 4, 8, 16, 32, 64, 96, 128))
    for _ in range(directions):
        width_a = int(rng.choice(widths))
        width_b = int(rng.choice(widths))
        start_a = int(rng.integers(0, n - width_a + 1))
        start_b = int(rng.integers(0, n - width_b + 1))
        direction = np.zeros(n)
        direction[start_a : start_a + width_a] += 1.0 / width_a
        direction[start_b : start_b + width_b] -= 1.0 / width_b
        test_direction(book, "multiscale_block_transfer", direction)

    for _ in range(directions // 2):
        width = int(rng.choice(widths))
        start_a = int(rng.integers(0, n - width + 1))
        start_b = int(rng.integers(0, n - width + 1))
        if start_a == start_b:
            continue
        candidate = book.seed.copy()
        block_a = candidate[start_a : start_a + width].copy()
        block_b = candidate[start_b : start_b + width].copy()
        for fraction in (0.25, 0.5, 0.75, 1.0):
            candidate = book.seed.copy()
            candidate[start_a : start_a + width] = (
                1.0 - fraction
            ) * block_a + fraction * block_b
            candidate[start_b : start_b + width] = (
                1.0 - fraction
            ) * block_b + fraction * block_a
            book.test("block_swap", candidate)

    for _ in range(directions // 2):
        width = int(rng.choice(widths[2:]))
        start = int(rng.integers(0, n - width + 1))
        direction = np.zeros(n)
        block = book.seed[start : start + width]
        direction[start : start + width] = block - float(np.mean(block))
        test_direction(book, "support_polarization", direction)


def run_zero_run_relocations(book: TrialBook) -> None:
    n = book.seed.size
    for start, stop in zero_runs(book.seed):
        width = stop - start
        if width == 0:
            continue
        stride = max(1, (n - width) // 196)
        for target in range(0, n - width + 1, stride):
            if max(start, target) < min(stop, target + width):
                continue
            candidate = book.seed.copy()
            source_block = candidate[start:stop].copy()
            target_block = candidate[target : target + width].copy()
            candidate[start:stop] = target_block
            candidate[target : target + width] = source_block
            book.test("zero_run_relocation", candidate)


def run_public_crossovers(book: TrialBook, snapshot: dict[str, Any]) -> None:
    source_ids = (2406, 2407, 2421)
    sources = []
    for solution_id in source_ids:
        matches = [item for item in snapshot["solutions"] if item["id"] == solution_id]
        if matches:
            source = np.asarray(matches[0]["data"]["values"], dtype=np.float64)
            sources.append((str(solution_id), rebin_periodic(source, book.seed.size)))
    transforms = [
        ("reverse", book.seed[::-1]),
        ("complement", 1.0 - book.seed),
    ] + sources
    for name, source in transforms:
        for fraction in np.concatenate(
            (np.logspace(-8, -2, 7), np.linspace(0.05, 1.0, 20))
        ):
            candidate = (1.0 - fraction) * book.seed + fraction * source
            book.test(f"blend_{name}", capped_simplex_projection(candidate))
        for breakpoint in range(0, book.seed.size + 1, 8):
            candidate = np.concatenate((book.seed[:breakpoint], source[breakpoint:]))
            book.test(f"crossover_{name}", capped_simplex_projection(candidate))


def run_audit(args: argparse.Namespace) -> int:
    snapshot, leader, seed = load_snapshot(args.snapshot)
    problem = snapshot["problem"]
    verifier_hash = snapshot["verifier_sha256"]
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    live_score = float(leader["score"])
    target = live_score - float(problem["minImprovement"])
    seed_score = exact_score(seed)
    atomic_json(run_dir / "seed.json", {"values": seed.tolist()})
    atomic_json(run_dir / "best.json", {"values": seed.tolist()})
    append_event(
        events,
        event="start",
        live_score=live_score,
        target=target,
        local_seed_score=seed_score,
        verifier_sha256=verifier_hash,
        snapshot=str(args.snapshot.resolve()),
    )

    profile = score_profile(seed)
    topology = {
        "n": int(seed.size),
        "raw_sum": float(seed.sum()),
        "exact_zero_count": int(np.count_nonzero(seed == 0.0)),
        "exact_one_count": int(np.count_nonzero(seed == 1.0)),
        "near_zero_count_1e-12": int(np.count_nonzero(seed <= 1e-12)),
        "near_one_count_1e-12": int(np.count_nonzero(seed >= 1.0 - 1e-12)),
        "fractional_count_1e-12": int(
            np.count_nonzero((seed > 1e-12) & (seed < 1.0 - 1e-12))
        ),
        "active_lag_counts_by_score_gap": {
            str(tolerance): int(np.count_nonzero(profile.max() - profile <= tolerance))
            for tolerance in (1e-14, 5e-14, 1e-13, 1e-12, 1e-10, 1e-8, 1e-7)
        },
        "zero_runs_1e-15": zero_runs(seed),
    }
    atomic_json(run_dir / "topology.json", topology)
    dual = active_dual_diagnostic(seed, args.active_tolerance)
    atomic_json(run_dir / "active_dual.json", dual)
    append_event(events, event="diagnostic", topology=topology, dual=dual)

    book = TrialBook(seed, run_dir, live_score)
    rng = np.random.default_rng(args.seed)
    run_rebin_and_phase(book)
    append_event(
        events,
        event="family_complete",
        family="rebin_phase",
        counts=book.counts,
        family_best=book.family_best,
    )
    run_block_surgery(book, rng, args.block_directions)
    append_event(
        events,
        event="family_complete",
        family="block_surgery",
        counts=book.counts,
        family_best=book.family_best,
    )
    run_zero_run_relocations(book)
    run_public_crossovers(book, snapshot)

    total_trials = int(sum(book.counts.values()))
    summary = {
        "slug": SLUG,
        "mode": "intended-domain topology audit",
        "verifier_sha256": verifier_hash,
        "snapshot": str(args.snapshot.resolve()),
        "leader_solution_id": LEADER_SOLUTION_ID,
        "live_score": live_score,
        "local_seed_score": seed_score,
        "target_strictly_below": target,
        "best_local_score": book.best_score,
        "improvement_over_live": live_score - book.best_score,
        "gate_gap": book.best_score - target,
        "gate_clearing": bool(book.best_score < target),
        "trial_count": total_trials,
        "trial_counts": book.counts,
        "family_best_scores": book.family_best,
        "domain": {
            "finite": bool(np.isfinite(book.best).all()),
            "min": float(book.best.min()),
            "max": float(book.best.max()),
            "raw_sum": float(book.best.sum()),
            "normalized_sum": float(normalized_values(book.best).sum()),
        },
        "payload": str((run_dir / "best.json").resolve()),
        "events": str(events.resolve()),
        "conclusion": "No tested support, multiscale block, grid, or public-crossover topology clears the live gate.",
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, event="complete", summary=summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def parse_schedule(value: str) -> list[tuple[float, int, int]]:
    schedule = []
    for item in value.split(","):
        beta, iterations, repeats = item.split(":")
        schedule.append((float(beta), int(iterations), int(repeats)))
    return schedule


def sum_constrained_sigmoid(logits: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lower = -80.0
    upper = 80.0
    target = logits.size / 2.0
    for _ in range(70):
        shift = (lower + upper) / 2.0
        total = float(np.sum(expit(logits + shift)))
        if total < target:
            lower = shift
        else:
            upper = shift
    values = expit(logits + (lower + upper) / 2.0)
    derivatives = values * (1.0 - values)
    return values, derivatives


def smooth_objective(logits: np.ndarray, beta: float) -> tuple[float, np.ndarray]:
    values, derivatives = sum_constrained_sigmoid(logits)
    correlations = np.correlate(values, 1.0 - values, mode="full")
    profile = correlations * (2.0 / values.size)
    scaled = beta * profile
    weights = np.exp(scaled - logsumexp(scaled))
    smooth_max = float(logsumexp(scaled) / beta)

    first = fftconvolve(weights, 1.0 - values, mode="full")
    second = fftconvolve(weights[::-1], values, mode="full")
    value_gradient = (first - second)[values.size - 1 : 2 * values.size - 1]
    value_gradient *= 2.0 / values.size
    weighted_mean = float(np.dot(derivatives, value_gradient) / np.sum(derivatives))
    logit_gradient = derivatives * (value_gradient - weighted_mean)
    return smooth_max, logit_gradient


def run_multigrid(args: argparse.Namespace) -> int:
    snapshot, leader, seed = load_snapshot(args.snapshot)
    problem = snapshot["problem"]
    verifier_hash = snapshot["verifier_sha256"]
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    live_score = float(leader["score"])
    target = live_score - float(problem["minImprovement"])

    values = rebin_periodic(seed, args.output_size)
    initial_score = exact_score(values)
    epsilon = args.logit_epsilon
    clipped = np.clip(values, epsilon, 1.0 - epsilon)
    logits = np.log(clipped) - np.log1p(-clipped)
    values, _ = sum_constrained_sigmoid(logits)
    best = values.copy()
    best_score = exact_score(best)
    atomic_json(run_dir / "seed.json", {"values": values.tolist()})
    atomic_json(run_dir / "best_distinct.json", {"values": best.tolist()})
    append_event(
        events,
        event="start",
        output_size=args.output_size,
        rebin_score=initial_score,
        constrained_logit_score=best_score,
        live_score=live_score,
        target=target,
        verifier_sha256=verifier_hash,
    )

    stage = 0
    total_iterations = 0
    total_evaluations = 0
    for beta, maxiter, repeats in args.schedule:
        for repeat in range(repeats):
            result = minimize(
                smooth_objective,
                logits,
                args=(beta,),
                method="L-BFGS-B",
                jac=True,
                options={
                    "maxiter": maxiter,
                    "maxfun": maxiter * 3,
                    "maxls": 50,
                    "maxcor": 30,
                    "ftol": 1e-15,
                    "gtol": 1e-13,
                },
            )
            logits = result.x
            values, _ = sum_constrained_sigmoid(logits)
            score = exact_score(values)
            stage += 1
            total_iterations += int(result.nit)
            total_evaluations += int(result.nfev)
            if score < best_score:
                best = values.copy()
                best_score = score
                atomic_json(run_dir / "best_distinct.json", {"values": best.tolist()})
            checkpoint = run_dir / f"checkpoint_{stage:03d}.json"
            atomic_json(checkpoint, {"values": values.tolist()})
            append_event(
                events,
                event="continuation_stage",
                stage=stage,
                beta=beta,
                repeat=repeat,
                exact_score=score,
                best_exact_score=best_score,
                iterations=int(result.nit),
                evaluations=int(result.nfev),
                success=bool(result.success),
                status=int(result.status),
                message=str(result.message),
                checkpoint=str(checkpoint.resolve()),
            )

    summary = {
        "slug": SLUG,
        "mode": "noninteger-grid distinct-basin continuation",
        "verifier_sha256": verifier_hash,
        "snapshot": str(args.snapshot.resolve()),
        "leader_solution_id": LEADER_SOLUTION_ID,
        "output_size": args.output_size,
        "live_score": live_score,
        "target_strictly_below": target,
        "initial_rebin_score": initial_score,
        "best_distinct_score": best_score,
        "improvement_over_live": live_score - best_score,
        "gate_gap": best_score - target,
        "gate_clearing": bool(best_score < target),
        "continuation_stages": stage,
        "optimizer_iterations": total_iterations,
        "optimizer_evaluations": total_evaluations,
        "domain": {
            "finite": bool(np.isfinite(best).all()),
            "min": float(best.min()),
            "max": float(best.max()),
            "raw_sum": float(best.sum()),
            "normalized_sum": float(normalized_values(best).sum()),
        },
        "payload": str((run_dir / "best_distinct.json").resolve()),
        "events": str(events.resolve()),
        "conclusion": "The distinct n-grid basin converged above the live leader and does not clear the gate.",
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, event="complete", summary=summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    common.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    common.add_argument("--stamp")

    audit = subparsers.add_parser("audit", parents=[common])
    audit.add_argument("--seed", type=int, default=20260814)
    audit.add_argument("--block-directions", type=int, default=2000)
    audit.add_argument("--active-tolerance", type=float, default=1e-10)
    audit.set_defaults(function=run_audit)

    multigrid = subparsers.add_parser("multigrid", parents=[common])
    multigrid.add_argument("--output-size", type=int, default=2560)
    multigrid.add_argument("--logit-epsilon", type=float, default=1e-12)
    multigrid.add_argument(
        "--schedule",
        type=parse_schedule,
        default=parse_schedule(
            "1e5:200:1,1e6:300:1,1e7:500:1,1e8:500:2,"
            "1e9:500:3,1e10:1000:4,1e11:1000:4,1e12:1000:2"
        ),
    )
    multigrid.set_defaults(function=run_multigrid)

    args = parser.parse_args()
    return int(args.function(args))


if __name__ == "__main__":
    raise SystemExit(main())
