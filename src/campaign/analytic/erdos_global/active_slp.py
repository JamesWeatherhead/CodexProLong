#!/usr/bin/env python3
"""Checkpointed active-set SLP for the Erdős minimum-overlap objective.

The acceptance score is always evaluated with literal ``numpy.correlate``.
HiGHS is used only to solve the linearized trust-region subproblem.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import highspy
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.sparse import csr_matrix


DEFAULT_SNAPSHOT = Path(__file__).parents[2] / (
    "erdos_root/snapshots/erdos-min-overlap_20260814T232154Z.json"
)
GATE = 0.38085857721583954


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_event(path: Path, value: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_values(path: Path) -> np.ndarray:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    values = np.asarray(payload["values"], dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise ValueError("payload values must be a finite vector")
    return values


def capped_simplex_projection(values: np.ndarray) -> np.ndarray:
    target = values.size / 2.0
    lower = -float(np.max(values)) - 1.0
    upper = 1.0 - float(np.min(values)) + 1.0
    for _ in range(70):
        midpoint = (lower + upper) / 2.0
        if float(np.sum(np.clip(values + midpoint, 0.0, 1.0))) < target:
            lower = midpoint
        else:
            upper = midpoint
    projected = np.clip(values + (lower + upper) / 2.0, 0.0, 1.0)
    residual = target - float(projected.sum())
    free = np.flatnonzero((projected > 1e-13) & (projected < 1.0 - 1e-13))
    if free.size and residual:
        projected[free] += residual / free.size
    return projected


def exact_profile(values: np.ndarray) -> np.ndarray:
    return np.correlate(values, 1.0 - values, mode="full") * (
        2.0 / values.size
    )


def exact_score(values: np.ndarray) -> float:
    return float(np.max(exact_profile(values)))


def active_gradient(values: np.ndarray, active: np.ndarray) -> np.ndarray:
    n = values.size
    lags = active - (n - 1)
    gradients = np.zeros((active.size, n), dtype=np.float64)
    for row, lag in enumerate(lags):
        second_start = max(0, -int(lag))
        second_stop = min(n, n - int(lag))
        second = np.arange(second_start, second_stop)
        first = second + lag
        gradients[row, first] += 1.0 - values[second]
        gradients[row, second] -= values[first]
    gradients *= 2.0 / n
    return gradients


def solve_linearization(
    values: np.ndarray,
    profile: np.ndarray,
    active_tolerance: float,
    trust: float,
    time_limit: float,
    threads: int,
) -> tuple[np.ndarray, dict[str, object]]:
    maximum = float(profile.max())
    active = np.flatnonzero(maximum - profile <= active_tolerance)
    gradients = active_gradient(values, active)

    # Scaling makes the physical score change and the LP epigraph variable O(1).
    score_scale = max(1e-12, trust * 1e-3)
    top = np.c_[gradients * (trust / score_scale), -np.ones(active.size)]
    equality = np.r_[np.ones(values.size), 0.0][None, :]
    matrix = csr_matrix(np.vstack((top, equality)))

    model = highspy.HighsLp()
    model.num_col_ = values.size + 1
    model.num_row_ = active.size + 1
    model.col_cost_ = np.r_[np.zeros(values.size), 1.0]
    model.col_lower_ = np.r_[
        np.maximum(-1.0, -values / trust), -highspy.kHighsInf
    ]
    model.col_upper_ = np.r_[
        np.minimum(1.0, (1.0 - values) / trust), highspy.kHighsInf
    ]
    model.row_lower_ = np.r_[
        np.full(active.size, -highspy.kHighsInf), 0.0
    ]
    model.row_upper_ = np.r_[
        (maximum - profile[active]) / score_scale, 0.0
    ]
    model.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    model.a_matrix_.start_ = matrix.indptr.astype(np.int32)
    model.a_matrix_.index_ = matrix.indices.astype(np.int32)
    model.a_matrix_.value_ = matrix.data

    solver = highspy.Highs()
    solver.setOptionValue("output_flag", False)
    solver.setOptionValue("solver", "ipm")
    solver.setOptionValue("run_crossover", "off")
    solver.setOptionValue("time_limit", time_limit)
    solver.setOptionValue("threads", threads)
    solver.passModel(model)
    solver.run()
    solution = np.asarray(solver.getSolution().col_value, dtype=np.float64)
    direction = trust * solution[:-1]
    diagnostics = {
        "model_status": str(solver.getModelStatus()),
        "active_count": int(active.size),
        "matrix_nonzeros": int(matrix.nnz),
        "trust": trust,
        "score_scale": score_scale,
        "predicted_delta": float(score_scale * solution[-1]),
        "direction_norm": float(np.linalg.norm(direction)),
        "direction_sum": float(direction.sum()),
    }
    return direction, diagnostics


def exact_line_search(
    values: np.ndarray, direction: np.ndarray
) -> tuple[np.ndarray, float, float]:
    def objective(alpha: float) -> float:
        candidate = capped_simplex_projection(values + alpha * direction)
        return exact_score(candidate)

    alphas = np.unique(
        np.r_[0.0, np.logspace(-8, -1, 29), np.linspace(0.1, 1.0, 37)]
    )
    scores = np.asarray([objective(float(alpha)) for alpha in alphas])
    best_index = int(np.argmin(scores))
    best_alpha = float(alphas[best_index])
    best_score = float(scores[best_index])
    if 0 < best_index < alphas.size - 1:
        result = minimize_scalar(
            objective,
            bounds=(float(alphas[best_index - 1]), float(alphas[best_index + 1])),
            method="bounded",
            options={"xatol": 1e-14, "maxiter": 200},
        )
        if float(result.fun) < best_score:
            best_alpha = float(result.x)
            best_score = float(result.fun)
    candidate = capped_simplex_projection(values + best_alpha * direction)
    return candidate, best_score, best_alpha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--stamp")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--active-tolerance", type=float, default=1e-5)
    parser.add_argument("--trust", type=float, default=1e-3)
    parser.add_argument("--time-limit", type=float, default=120.0)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()

    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    values = capped_simplex_projection(load_values(args.input))
    best_score = exact_score(values)
    initial_score = best_score
    trust = args.trust

    snapshot_bytes = args.snapshot.read_bytes()
    snapshot = json.loads(snapshot_bytes)
    verifier = snapshot["problem"]["verifier"]
    verifier_hash = hashlib.sha256(verifier.encode()).hexdigest()
    if verifier_hash != snapshot["verifier_sha256"]:
        raise ValueError("snapshot verifier hash mismatch")

    atomic_json(run_dir / "seed.json", {"values": values.tolist()})
    atomic_json(run_dir / "best.json", {"values": values.tolist()})
    append_event(
        events,
        {
            "event": "start",
            "input": str(args.input.resolve()),
            "n": int(values.size),
            "initial_score": initial_score,
            "gate": GATE,
            "verifier_sha256": verifier_hash,
        },
    )

    for iteration in range(1, args.iterations + 1):
        profile = exact_profile(values)
        direction, diagnostics = solve_linearization(
            values,
            profile,
            args.active_tolerance,
            trust,
            args.time_limit,
            args.threads,
        )
        candidate, score, alpha = exact_line_search(values, direction)
        accepted = score < best_score - 2e-15
        if accepted:
            values = candidate
            best_score = score
            atomic_json(run_dir / "best.json", {"values": values.tolist()})
            trust = min(args.trust, trust * 1.25)
        else:
            trust *= 0.25
        checkpoint = run_dir / f"checkpoint_{iteration:03d}.json"
        atomic_json(checkpoint, {"values": values.tolist()})
        append_event(
            events,
            {
                "event": "slp_iteration",
                "iteration": iteration,
                "accepted": accepted,
                "alpha": alpha,
                "line_score": score,
                "best_score": best_score,
                "next_trust": trust,
                **diagnostics,
            },
        )
        if trust < 1e-8 or best_score < GATE:
            break

    summary = {
        "mode": "literal-np-correlate active-set SLP",
        "input": str(args.input.resolve()),
        "n": int(values.size),
        "initial_score": initial_score,
        "best_score": best_score,
        "improvement": initial_score - best_score,
        "strict_gate": GATE,
        "gate_gap": best_score - GATE,
        "gate_clearing": bool(best_score < GATE),
        "verifier_sha256": verifier_hash,
        "payload": str((run_dir / "best.json").resolve()),
        "events": str(events.resolve()),
        "domain": {
            "minimum": float(values.min()),
            "maximum": float(values.max()),
            "sum": float(values.sum()),
            "finite": bool(np.isfinite(values).all()),
        },
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, {"event": "complete", "summary": summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
