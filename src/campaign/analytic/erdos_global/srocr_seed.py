#!/usr/bin/env python3
"""Coarse lifted/SROCR seed experiment for Erdős minimum overlap.

This is deliberately a seed generator, not a verifier surrogate.  Every
extracted vector is projected onto the capped simplex and scored with literal
``numpy.correlate``.  The SDP uses a Shor lift plus McCormick envelopes; SROCR
gradually concentrates the lifted trace in the preceding leading eigenspace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import cvxpy as cp
import numpy as np


DEFAULT_SNAPSHOT = Path(__file__).parents[2] / (
    "erdos_root/snapshots/erdos-min-overlap_20260814T232154Z.json"
)
LEADER_ID = 2440
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


def capped_simplex_projection(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    target = values.size / 2.0
    lower = -float(values.max()) - 1.0
    upper = 1.0 - float(values.min()) + 1.0
    for _ in range(70):
        midpoint = (lower + upper) / 2.0
        if float(np.clip(values + midpoint, 0.0, 1.0).sum()) < target:
            lower = midpoint
        else:
            upper = midpoint
    projected = np.clip(values + (lower + upper) / 2.0, 0.0, 1.0)
    residual = target - float(projected.sum())
    free = np.flatnonzero((projected > 1e-12) & (projected < 1.0 - 1e-12))
    if free.size and residual:
        projected[free] += residual / free.size
    return projected


def exact_score(values: np.ndarray) -> float:
    values = capped_simplex_projection(values)
    profile = np.correlate(values, 1.0 - values, mode="full")
    # Preserve the verifier's operation order as well as its expression.
    return float(profile.max() / values.size * 2.0)


def periodic_integral(values: np.ndarray, points: np.ndarray) -> np.ndarray:
    n = values.size
    periods = np.floor(points).astype(np.int64)
    fractions = points - periods
    scaled = fractions * n
    indices = np.minimum(np.floor(scaled).astype(np.int64), n - 1)
    offsets = scaled - indices
    cumulative = np.r_[0.0, np.cumsum(values) / n]
    return (
        periods * float(values.mean())
        + cumulative[indices]
        + offsets * values[indices] / n
    )


def rebin_periodic(values: np.ndarray, output_size: int) -> np.ndarray:
    edges = np.arange(output_size + 1, dtype=np.float64) / output_size
    integrals = periodic_integral(values, edges)
    return capped_simplex_projection(output_size * np.diff(integrals))


def solve_lifted(
    n: int,
    direction: np.ndarray,
    weight: float,
    eps: float,
    max_iters: int,
) -> tuple[np.ndarray, np.ndarray, float, float, str]:
    lifted = cp.Variable((n + 1, n + 1), symmetric=True)
    products = lifted[:n, :n]
    values = lifted[:n, n]
    epigraph = cp.Variable()
    column = cp.reshape(values, (n, 1), order="C")
    row = cp.reshape(values, (1, n), order="C")
    constraints = [
        lifted >> 0,
        lifted[n, n] == 1.0,
        values >= 0.0,
        values <= 1.0,
        cp.sum(values) == n / 2.0,
        cp.diag(products) <= values,
        products >= 0.0,
        products <= column,
        products <= row,
        products >= column + row - 1.0,
        cp.quad_form(direction, lifted) >= weight * cp.trace(lifted),
    ]
    for lag in range(-(n - 1), n):
        second_start = max(0, -lag)
        second_stop = min(n, n - lag)
        second = np.arange(second_start, second_stop)
        first = second + lag
        overlap = cp.sum(values[first]) - cp.sum(products[first, second])
        constraints.append(overlap * (2.0 / n) <= epigraph)

    problem = cp.Problem(cp.Minimize(epigraph), constraints)
    problem.solve(
        solver="SCS",
        eps=eps,
        max_iters=max_iters,
        verbose=False,
        warm_start=False,
    )
    if lifted.value is None:
        raise RuntimeError(f"SROCR subproblem failed: {problem.status}")
    matrix = (lifted.value + lifted.value.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    leading = eigenvectors[:, -1]
    ratio = float(eigenvalues[-1] / eigenvalues.sum())
    candidate = capped_simplex_projection(np.asarray(values.value))
    return candidate, leading, ratio, float(problem.value), str(problem.status)


def initial_vectors(
    leader: np.ndarray, n: int, random_seeds: int
) -> list[tuple[str, np.ndarray]]:
    vectors = [("public_rebin", rebin_periodic(leader, n))]
    for seed in range(random_seeds):
        rng = np.random.default_rng(seed)
        binary = np.r_[np.zeros(n // 2), np.ones(n - n // 2)]
        rng.shuffle(binary)
        vectors.append((f"balanced_binary_{seed}", binary))
    return vectors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--stamp")
    parser.add_argument("--n", type=int, default=64)
    parser.add_argument("--random-seeds", type=int, default=3)
    parser.add_argument("--stages", type=int, default=4)
    parser.add_argument("--initial-weight", type=float, default=0.9)
    parser.add_argument("--weight-step", type=float, default=0.005)
    parser.add_argument("--eps", type=float, default=3e-6)
    parser.add_argument("--max-iters", type=int, default=50000)
    args = parser.parse_args()
    if args.n < 4 or args.n % 2:
        raise ValueError("n must be an even integer at least four")

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    verifier = snapshot["problem"]["verifier"]
    verifier_hash = hashlib.sha256(verifier.encode()).hexdigest()
    if verifier_hash != snapshot["verifier_sha256"]:
        raise ValueError("snapshot verifier hash mismatch")
    solution = next(item for item in snapshot["solutions"] if item["id"] == LEADER_ID)
    leader = np.asarray(solution["data"]["values"], dtype=np.float64)

    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    results: list[dict[str, object]] = []

    # The unconditioned relaxation is included explicitly because it exposes
    # whether the SDP has a useful global leading eigenspace or the symmetric
    # constant-function degeneracy.
    constant_direction = np.r_[np.zeros(args.n), 1.0]
    relaxed, leading, ratio, objective, status = solve_lifted(
        args.n, constant_direction, 0.0, args.eps, args.max_iters
    )
    relaxation = {
        "status": status,
        "epigraph": objective,
        "rank_ratio": ratio,
        "extracted_exact_score": exact_score(relaxed),
        "minimum": float(relaxed.min()),
        "maximum": float(relaxed.max()),
    }
    relaxation_payload = run_dir / "unconditioned_extracted.json"
    atomic_json(relaxation_payload, {"values": relaxed.tolist()})
    relaxation["payload"] = str(relaxation_payload.resolve())
    append_event(events, {"event": "unconditioned_relaxation", **relaxation})

    for name, initial in initial_vectors(leader, args.n, args.random_seeds):
        initial = capped_simplex_projection(initial)
        direction = np.r_[initial, 1.0]
        direction /= np.linalg.norm(direction)
        weight = args.initial_weight
        best = initial.copy()
        best_score = exact_score(best)
        stages: list[dict[str, object]] = []
        for stage in range(1, args.stages + 1):
            candidate, direction, ratio, objective, status = solve_lifted(
                args.n, direction, weight, args.eps, args.max_iters
            )
            score = exact_score(candidate)
            stage_payload = run_dir / f"{name}_stage_{stage:02d}.json"
            atomic_json(stage_payload, {"values": candidate.tolist()})
            if score < best_score:
                best = candidate.copy()
                best_score = score
            record = {
                "stage": stage,
                "weight": weight,
                "rank_ratio": ratio,
                "relaxed_epigraph": objective,
                "exact_score": score,
                "payload": str(stage_payload.resolve()),
                "status": status,
            }
            stages.append(record)
            append_event(events, {"event": "srocr_stage", "seed": name, **record})
            if ratio >= 0.999999:
                break
            weight = min(1.0, ratio + args.weight_step)

        payload = run_dir / f"{name}.json"
        atomic_json(payload, {"values": best.tolist()})
        results.append(
            {
                "seed": name,
                "initial_exact_score": exact_score(initial),
                "best_coarse_exact_score": best_score,
                "payload": str(payload.resolve()),
                "stages": stages,
                "rebinned_scores": {
                    "n1024": exact_score(rebin_periodic(best, 1024)),
                    "n3584": exact_score(rebin_periodic(best, 3584)),
                },
            }
        )

    best_result = min(results, key=lambda item: float(item["best_coarse_exact_score"]))
    summary = {
        "mode": "coarse Shor-McCormick lift plus SROCR",
        "n": args.n,
        "verifier_sha256": verifier_hash,
        "strict_gate": GATE,
        "unconditioned_relaxation": relaxation,
        "best_seed": best_result["seed"],
        "best_coarse_exact_score": best_result["best_coarse_exact_score"],
        "best_payload": best_result["payload"],
        "results": results,
        "conclusion": (
            "The lifted experiment is a seed screen only; no result is accepted "
            "without literal np.correlate replay and subsequent fine-grid polish."
        ),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, {"event": "complete", "summary": summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
