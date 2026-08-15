#!/usr/bin/env python3
"""Cutting-plane epigraph SLP for the signed C3 construction problem.

The proposal model is the exact first variation

    (f + d) * (f + d) = f * f + 2 f * d + d * d

restricted to a deterministic multiscale basis.  A linear epigraph problem is
solved on a small lag bundle, then every omitted lag is searched for violated
cuts.  Thus a direction is not accepted merely because it lowers the current
argmax: the linear model must survive all 2n-1 lag constraints.  A one-
dimensional quadratic line search deliberately crosses max-lag boundaries.

FFT convolution is used only to build proposal derivatives.  Every accepted
checkpoint is replayed with the frozen verifier's direct float64
``numpy.convolve`` computation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.linalg import qr
from scipy.optimize import linprog, minimize_scalar
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "runs-102400" / "20260815T011534Z" / "best.npy"
VERIFIER_SHA256 = "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9"
LEADER_SCORE = 1.4515718638902069
TARGET_SCORE = 1.4515618638902069


def atomic_npy(path: Path, values: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_event(path: Path, value: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def normalize(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    mass = float(np.sum(result))
    if not np.isfinite(mass) or abs(mass) < 1e-12:
        raise ValueError("candidate mass is zero or non-finite")
    return result * (len(result) / mass)


def exact_metrics(values: np.ndarray) -> tuple[float, np.ndarray, int]:
    """Replay the public verifier algebra with direct float64 convolution."""
    f = np.asarray(values, dtype=np.float64)
    if f.ndim != 1 or not np.isfinite(f).all():
        raise ValueError("values must be a finite vector")
    n = len(f)
    dx = 0.5 / n
    integral_squared = (float(np.sum(f)) * dx) ** 2
    if integral_squared < 1e-9:
        raise ValueError("function integral is close to zero")
    convolution = np.convolve(f, f, mode="full")
    argmax = int(np.argmax(convolution))
    score = float(abs(float(np.max(convolution)) * dx) / integral_squared)
    return score, convolution, argmax


def deterministic_basis(n: int) -> tuple[np.ndarray, list[str]]:
    """Build a zero-mass multiscale basis spanning envelope and grid modes."""
    coordinate = (np.arange(n, dtype=np.float64) + 0.5) / n
    columns: list[np.ndarray] = []
    labels: list[str] = []

    frequencies = np.unique(np.rint(np.geomspace(1, 2048, 16)).astype(int))
    for frequency in frequencies:
        for kind in ("sin", "cos"):
            phase = 2.0 * np.pi * frequency * coordinate
            column = np.sin(phase) if kind == "sin" else np.cos(phase)
            column -= np.mean(column)
            column /= np.sqrt(np.mean(column * column))
            columns.append(column)
            labels.append(f"{kind}-{frequency}")

    for scale in (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384):
        width = n // scale
        positions = np.unique(np.linspace(0, scale - 1, min(2, scale), dtype=int))
        for position in positions:
            lower = position * width
            upper = n if position == scale - 1 else (position + 1) * width
            middle = (lower + upper) // 2
            column = np.zeros(n, dtype=np.float64)
            column[lower:middle] = 1.0
            column[middle:upper] = -1.0
            column -= np.mean(column)
            column /= np.sqrt(np.mean(column * column))
            columns.append(column)
            labels.append(f"haar-{scale}-{position}")

    for period in (2, 4, 8, 16, 32):
        if n % period:
            continue
        for frequency in range(1, min(period, 4)):
            pattern = np.cos(2.0 * np.pi * frequency * np.arange(period) / period)
            column = np.tile(pattern, n // period).astype(np.float64)
            column -= np.mean(column)
            column /= np.sqrt(np.mean(column * column))
            columns.append(column)
            labels.append(f"phase-{period}-{frequency}")

    raw = np.column_stack(columns)
    raw -= np.mean(raw, axis=0, keepdims=True)
    # Several periodic columns can be algebraically identical.  Pivoted QR
    # removes those dependencies rather than letting an unpivoted factorization
    # invent numerically arbitrary complement directions.
    orthogonal, triangular, pivots = qr(raw, mode="economic", pivoting=True)
    diagonal = np.abs(np.diag(triangular))
    rank_tolerance = max(raw.shape) * np.finfo(np.float64).eps * diagonal[0]
    rank = int(np.count_nonzero(diagonal > rank_tolerance))
    orthogonal = orthogonal[:, :rank]
    labels = [labels[int(index)] for index in pivots[:rank]]
    # QR preserves the zero-sum subspace up to roundoff.  Reprojection makes
    # the fixed-mass constraint explicit; the second pivoted QR is full-rank.
    orthogonal -= np.mean(orthogonal, axis=0, keepdims=True)
    orthogonal, _, pivots = qr(orthogonal, mode="economic", pivoting=True)
    labels = [labels[int(index)] for index in pivots]
    basis = np.asarray(orthogonal * np.sqrt(n), dtype=np.float64)
    return basis, labels


def derivative_matrix(f: np.ndarray, basis: np.ndarray) -> np.ndarray:
    rows = 2 * len(f) - 1
    result = np.empty((rows, basis.shape[1]), dtype=np.float64)
    for column in range(basis.shape[1]):
        result[:, column] = 2.0 * fftconvolve(
            f, basis[:, column], mode="full"
        )
    return result


def solve_exchange_slp(
    offsets: np.ndarray,
    derivatives: np.ndarray,
    trust: float,
    initial_cuts: int,
    exchange_batch: int,
    max_exchanges: int,
    violation_tolerance: float,
    events_path: Path,
    cycle: int,
) -> tuple[np.ndarray, float, np.ndarray, int]:
    dimensions = derivatives.shape[1]
    coefficient_bound = trust / np.sqrt(dimensions)
    cut_count = min(initial_cuts, len(offsets))
    cuts = set(np.argpartition(offsets, -cut_count)[-cut_count:].tolist())
    solution = np.zeros(dimensions, dtype=np.float64)
    tau = 0.0
    linearized = offsets.copy()

    for exchange in range(max_exchanges):
        indices = np.array(sorted(cuts), dtype=np.int64)
        lhs = np.column_stack(
            [derivatives[indices], -np.ones(len(indices), dtype=np.float64)]
        )
        rhs = -offsets[indices]
        objective = np.zeros(dimensions + 1, dtype=np.float64)
        objective[-1] = 1.0
        result = linprog(
            objective,
            A_ub=lhs,
            b_ub=rhs,
            bounds=[(-coefficient_bound, coefficient_bound)] * dimensions
            + [(None, None)],
            method="highs",
        )
        if not result.success:
            raise RuntimeError(f"epigraph LP failed: {result.message}")
        solution = np.asarray(result.x[:dimensions], dtype=np.float64)
        tau = float(result.x[-1])
        linearized = offsets + derivatives @ solution
        violations = linearized - tau
        batch = min(exchange_batch, len(violations))
        worst = np.argpartition(violations, -batch)[-batch:]
        additions = [
            int(index)
            for index in worst
            if violations[index] > violation_tolerance and int(index) not in cuts
        ]
        cuts.update(additions)
        event = {
            "event": "slp_exchange",
            "cycle": cycle,
            "exchange": exchange,
            "trust": trust,
            "cuts": len(cuts),
            "tau": tau,
            "global_linearized_max": float(np.max(linearized)),
            "global_linearized_argmax": int(np.argmax(linearized)),
            "added_cuts": len(additions),
        }
        append_event(events_path, event)
        print(json.dumps(event, sort_keys=True), flush=True)
        if not additions:
            return solution, tau, linearized, len(cuts)

    raise RuntimeError(
        "cut exchange budget exhausted before the global linear model closed"
    )


def line_search(
    f: np.ndarray,
    direction: np.ndarray,
    alpha_max: float,
    grid_points: int,
) -> tuple[float, float, int, int]:
    """Minimize the exact quadratic convolution envelope along a direction."""
    base = np.convolve(f, f, mode="full")
    linear = 2.0 * np.convolve(f, direction, mode="full")
    quadratic = np.convolve(direction, direction, mode="full")

    def envelope(alpha: float) -> float:
        return float(np.max(base + alpha * linear + alpha * alpha * quadratic))

    grid = np.linspace(0.0, alpha_max, grid_points)
    values = np.array([envelope(float(alpha)) for alpha in grid])
    best_index = int(np.argmin(values))
    if best_index == 0:
        return 0.0, float(values[0]), int(np.argmax(base)), 0
    lower = float(grid[max(0, best_index - 1)])
    upper = float(grid[min(len(grid) - 1, best_index + 1)])
    if upper > lower:
        result = minimize_scalar(
            envelope,
            method="bounded",
            bounds=(lower, upper),
            options={"xatol": 1e-12, "maxiter": 200},
        )
        alpha = float(result.x)
    else:
        alpha = float(grid[best_index])
    model = base + alpha * linear + alpha * alpha * quadratic
    return alpha, float(np.max(model)), int(np.argmax(model)), best_index


def write_candidate(path: Path, values: np.ndarray) -> None:
    atomic_json(path, {"values": [float(value) for value in values]})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs-active-bundle")
    parser.add_argument("--trusts", default="0.1")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--initial-cuts", type=int, default=512)
    parser.add_argument("--exchange-batch", type=int, default=512)
    parser.add_argument("--max-exchanges", type=int, default=32)
    parser.add_argument("--violation-tolerance", type=float, default=1e-9)
    parser.add_argument("--alpha-max", type=float, default=64.0)
    parser.add_argument("--alpha-grid", type=int, default=257)
    args = parser.parse_args()
    if args.cycles < 1:
        raise ValueError("cycles must be positive")

    f = normalize(np.load(args.input, allow_pickle=False).astype(np.float64))
    initial_score, convolution, argmax = exact_metrics(f)
    initial_argmax = argmax
    best_score = initial_score
    run_dir = args.run_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "seed.npy", f)
    atomic_npy(run_dir / "best.npy", f)

    trusts = [float(value) for value in args.trusts.split(",")]
    basis, labels = deterministic_basis(len(f))
    atomic_json(
        run_dir / "basis.json",
        {"dimensions": basis.shape[1], "labels": labels},
    )

    accepted_steps = 0
    attempted_models = 0
    for cycle in range(1, args.cycles + 1):
        cycle_accepted = False
        maximum = float(np.max(convolution))
        offsets = convolution - maximum
        derivatives = derivative_matrix(f, basis)
        for trust in trusts:
            attempted_models += 1
            coefficients, tau, linearized, cuts = solve_exchange_slp(
                offsets,
                derivatives,
                trust,
                args.initial_cuts,
                args.exchange_batch,
                args.max_exchanges,
                args.violation_tolerance,
                events_path,
                cycle,
            )
            direction = basis @ coefficients
            direction -= np.mean(direction)
            alpha, model_max, model_argmax, grid_index = line_search(
                f, direction, args.alpha_max, args.alpha_grid
            )
            candidate = normalize(f + alpha * direction)

            # Acceptance is based only on a fresh direct float64 replay.
            candidate_score, candidate_convolution, candidate_argmax = exact_metrics(
                candidate
            )
            accepted = bool(candidate_score < best_score)
            if accepted:
                f = candidate
                convolution = candidate_convolution
                argmax = candidate_argmax
                best_score = candidate_score
                accepted_steps += 1
                cycle_accepted = True
                atomic_npy(run_dir / "best.npy", f)
                atomic_npy(run_dir / f"accepted-{accepted_steps:03d}.npy", f)
            event = {
                "event": "model_completed",
                "cycle": cycle,
                "trust": trust,
                "cuts": cuts,
                "tau": tau,
                "global_linearized_max": float(np.max(linearized)),
                "direction_rms": float(np.sqrt(np.mean(direction * direction))),
                "direction_max_abs": float(np.max(np.abs(direction))),
                "alpha": alpha,
                "alpha_grid_index": grid_index,
                "quadratic_model_max": model_max,
                "quadratic_model_argmax": model_argmax,
                "candidate_score": candidate_score,
                "candidate_argmax": candidate_argmax,
                "accepted": accepted,
                "best_score": best_score,
                "gate_gap": best_score - TARGET_SCORE,
            }
            append_event(events_path, event)
            print(json.dumps(event, sort_keys=True), flush=True)
            if accepted:
                break
        if not cycle_accepted:
            break

    payload = run_dir / "best.npy"
    replay_score, replay_convolution, replay_argmax = exact_metrics(f)
    gate_cleared = bool(replay_score < TARGET_SCORE)
    if gate_cleared:
        write_candidate(run_dir / "candidate.json", f)
    summary = {
        "input": str(args.input.resolve()),
        "initial_score": initial_score,
        "initial_argmax": initial_argmax,
        "best_score": replay_score,
        "gain": initial_score - replay_score,
        "leader_score": LEADER_SCORE,
        "target_score": TARGET_SCORE,
        "gate_gap": replay_score - TARGET_SCORE,
        "gate_cleared": gate_cleared,
        "n": len(f),
        "sum": float(np.sum(f)),
        "integral": float(np.sum(f) * 0.5 / len(f)),
        "finite": bool(np.isfinite(f).all()),
        "argmax": replay_argmax,
        "max_convolution": float(np.max(replay_convolution)),
        "min_convolution": float(np.min(replay_convolution)),
        "basis_dimensions": basis.shape[1],
        "attempted_models": attempted_models,
        "accepted_steps": accepted_steps,
        "payload": str(payload.resolve()),
        "payload_sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
        "raw_values_sha256": hashlib.sha256(f.tobytes()).hexdigest(),
        "candidate": str((run_dir / "candidate.json").resolve()) if gate_cleared else None,
        "verifier_sha256": VERIFIER_SHA256,
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0 if gate_cleared else 2


if __name__ == "__main__":
    raise SystemExit(main())
