#!/usr/bin/env python3
"""Checkpointed rank-lift/SROCR topology escape for signed C3.

This is a deliberately nonlocal complement to the local all-lag bundle runs.
For a fixed partition ``label[p]`` it writes

    f[p] = baseline[p] * a[label[p]]

and lifts the block multipliers to ``X = a a^T``.  Every selected coefficient
of ``convolve(f, f)`` is then a linear functional of ``X``.  An augmented
matrix ``Z = [a; 1] [a; 1]^T`` permits mass, amplitude, and explicit topology
constraints while sequential rank-one constraint relaxation (SROCR) pushes a
semidefinite relaxation back toward rank one.

The constraint set is enlarged with exact full-grid FFT peak discovery after
every solve.  FFT is proposal machinery only: candidates eligible for the
frontier are replayed with literal float64 ``numpy.convolve`` and ``best.npy``
changes only after such an exact strict improvement.

Method basis (line-pinned campaign literature audit):

* Lin, Chang & Su, arXiv:2504.06038, lines 3, 14, 95--129: peak
  sidelobe minimization as a finite SDP with a rank-one constraint and SROCR.
* Gaitan & Madrid, arXiv:2512.18188, lines 78--80: equality intersections of
  neighboring convolution coefficients in a related minimax problem.  This is
  motivation for active-peak exchange, not a theorem about signed C3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import cvxpy as cp
import numpy as np
from scipy.signal import fftconvolve


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "runs-102400" / "20260815T011534Z" / "best.npy"
VERIFIER_SHA256 = "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9"
LEADER_SCORE = 1.4515718638902069
TARGET_SCORE = 1.4515618638902069


@dataclass
class Candidate:
    label: str
    multipliers: np.ndarray
    values: np.ndarray
    screen_score: float
    sign_flips: int
    rank_ratio: float | None


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
    if result.ndim != 1 or not np.isfinite(result).all():
        raise ValueError("candidate must be a finite vector")
    if not np.isfinite(mass) or abs(mass) < 1e-12:
        raise ValueError("candidate has zero or non-finite mass")
    return result * (len(result) / mass)


def exact_metrics(values: np.ndarray) -> tuple[float, int, float, float]:
    f = normalize(values)
    convolution = np.convolve(f, f, mode="full")
    maximum = float(np.max(convolution))
    score = float(abs(2.0 * len(f) * maximum / float(np.sum(f)) ** 2))
    return score, int(np.argmax(convolution)), maximum, float(np.min(convolution))


def screen(values: np.ndarray) -> tuple[float, np.ndarray]:
    f = normalize(values)
    convolution = fftconvolve(f, f, mode="full")
    score = float(abs(2.0 * len(f) * float(np.max(convolution)) / np.sum(f) ** 2))
    return score, convolution


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_numbers(text: str, cast: type[float] | type[int]) -> list[float] | list[int]:
    return [cast(value) for value in text.split(",") if value]


def top_indices(values: np.ndarray, count: int) -> np.ndarray:
    count = min(max(1, count), len(values))
    indices = np.argpartition(values, -count)[-count:]
    return indices[np.argsort(values[indices])[::-1]]


def make_partition(
    baseline: np.ndarray,
    blocks: int,
    kind: str,
    support_count: int,
    cell_width: int,
) -> tuple[np.ndarray, list[int], dict[str, object]]:
    n = len(baseline)
    positions = np.arange(n, dtype=np.int64)
    if blocks < 3:
        raise ValueError("--blocks must be at least 3")
    if kind == "periodic":
        labels = positions % blocks
        forced: list[int] = []
        metadata: dict[str, object] = {"kind": kind}
    elif kind == "contiguous":
        labels = np.minimum(positions * blocks // n, blocks - 1)
        forced = []
        metadata = {"kind": kind}
    elif kind == "unequal-energy":
        energy = np.abs(baseline) ** 2 + np.finfo(np.float64).eps
        cumulative = np.cumsum(energy)
        thresholds = cumulative[-1] * np.arange(1, blocks) / blocks
        boundaries = np.searchsorted(cumulative, thresholds, side="left") + 1
        labels = np.searchsorted(boundaries, positions, side="right").astype(np.int64)
        forced = []
        metadata = {
            "kind": kind,
            "minimum_cell_width": int(np.min(np.diff(np.r_[0, boundaries, n]))),
            "maximum_cell_width": int(np.max(np.diff(np.r_[0, boundaries, n]))),
        }
    elif kind == "support-periodic":
        if support_count < 2 or support_count >= n:
            raise ValueError("support-periodic requires 2 <= support-count < n")
        weak = np.argsort(np.abs(baseline), kind="stable")[:support_count]
        labels = 1 + (positions // max(1, cell_width)) % (blocks - 1)
        labels[weak] = 0
        forced = [0]
        metadata = {
            "kind": kind,
            "support_count": support_count,
            "support_indices": [int(value) for value in weak],
            "cell_width": cell_width,
        }
    else:
        raise ValueError(f"unknown partition kind: {kind}")
    counts = np.bincount(labels, minlength=blocks)
    if np.any(counts == 0):
        raise ValueError(f"partition contains empty classes: {np.flatnonzero(counts == 0)}")
    metadata["class_size_min"] = int(np.min(counts))
    metadata["class_size_max"] = int(np.max(counts))
    return labels, forced, metadata


def mass_fractions(baseline: np.ndarray, labels: np.ndarray, blocks: int) -> np.ndarray:
    return np.bincount(labels, weights=baseline, minlength=blocks) / len(baseline)


def mass_correct(
    multipliers: np.ndarray,
    fractions: np.ndarray,
    adjustable: np.ndarray | None = None,
) -> np.ndarray:
    result = np.asarray(multipliers, dtype=np.float64).copy()
    if adjustable is None:
        adjustable = np.ones(len(result), dtype=bool)
    denominator = float(np.sum(fractions[adjustable]))
    if abs(denominator) < 1e-12:
        raise ValueError("cannot correct mass on the selected classes")
    correction = (1.0 - float(fractions @ result)) / denominator
    result[adjustable] += correction
    return result


def seed_multipliers(
    baseline: np.ndarray,
    labels: np.ndarray,
    blocks: int,
    forced: list[int],
    forced_value: float,
) -> tuple[np.ndarray, float, np.ndarray]:
    fractions = mass_fractions(baseline, labels, blocks)
    if forced:
        proposal = np.ones(blocks, dtype=np.float64)
        proposal[forced] = forced_value
        adjustable = np.ones(blocks, dtype=bool)
        adjustable[forced] = False
        proposal = mass_correct(proposal, fractions, adjustable)
        score, convolution = screen(baseline * proposal[labels])
        return proposal, score, convolution

    # For partitions without a dedicated weak-support class, test every
    # one-class death and retain the least damaging topology change.
    best: tuple[float, np.ndarray, np.ndarray] | None = None
    for index in range(blocks):
        proposal = np.ones(blocks, dtype=np.float64)
        proposal[index] = forced_value
        adjustable = np.ones(blocks, dtype=bool)
        adjustable[index] = False
        try:
            proposal = mass_correct(proposal, fractions, adjustable)
        except ValueError:
            continue
        score, convolution = screen(baseline * proposal[labels])
        if best is None or score < best[0]:
            best = (score, proposal, convolution)
            forced[:] = [index]
    if best is None:
        raise RuntimeError("no feasible one-class topology seed")
    return best[1], best[0], best[2]


def lag_matrix(
    baseline: np.ndarray,
    labels: np.ndarray,
    blocks: int,
    lags: Iterable[int],
    reference_max: float,
) -> tuple[np.ndarray, list[int]]:
    n = len(baseline)
    ordered = sorted({int(lag) for lag in lags})
    matrix = np.empty((len(ordered), blocks * blocks), dtype=np.float64)
    for row, lag in enumerate(ordered):
        lower = max(0, lag - (n - 1))
        upper = min(n - 1, lag)
        left = np.arange(lower, upper + 1, dtype=np.int64)
        right = lag - left
        flat = labels[left] * blocks + labels[right]
        matrix[row] = np.bincount(
            flat,
            weights=baseline[left] * baseline[right],
            minlength=blocks * blocks,
        ) / reference_max
    return matrix, ordered


def extract_rank_one(
    lifted: np.ndarray,
    fractions: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    symmetric = (lifted + lifted.T) * 0.5
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    clipped = np.clip(eigenvalues, 0.0, None)
    ratio = float(clipped[-1] / max(float(np.sum(clipped)), 1e-300))
    direction = eigenvectors[:, -1].copy()
    if direction[-1] < 0.0:
        direction *= -1.0
    if abs(direction[-1]) < 1e-9:
        multipliers = symmetric[:-1, -1].copy()
    else:
        multipliers = direction[:-1] / direction[-1]
    mass = float(fractions @ multipliers)
    if abs(mass) < 1e-12:
        multipliers = symmetric[:-1, -1].copy()
        mass = float(fractions @ multipliers)
    if abs(mass) < 1e-12:
        raise RuntimeError("rank-one extraction has zero mass")
    multipliers /= mass
    augmented = np.r_[multipliers, 1.0]
    return multipliers, augmented / np.linalg.norm(augmented), ratio


def solve_stage(
    baseline: np.ndarray,
    labels: np.ndarray,
    fractions: np.ndarray,
    forced: list[int],
    forced_value: float,
    active: set[int],
    reference_max: float,
    multipliers: np.ndarray,
    direction: np.ndarray,
    rank_fraction: float,
    amplitude: float,
    proximal: float,
    solver_eps: float,
    solver_iters: int,
) -> tuple[np.ndarray, np.ndarray, float, float, str, list[int]]:
    blocks = len(multipliers)
    matrix, ordered = lag_matrix(
        baseline, labels, blocks, active, reference_max
    )
    lifted = cp.Variable((blocks + 1, blocks + 1), symmetric=True)
    threshold = cp.Variable()
    vector = lifted[:blocks, blocks]
    square = lifted[:blocks, :blocks]
    constraints: list[cp.Constraint] = [
        lifted >> 0,
        lifted[blocks, blocks] == 1.0,
        fractions @ vector == 1.0,
        vector >= -amplitude,
        vector <= amplitude,
        cp.diag(square) <= amplitude * amplitude,
        threshold >= 0.5,
        matrix @ cp.reshape(square, (blocks * blocks,), order="C") <= threshold,
        cp.sum(cp.multiply(np.outer(direction, direction), lifted))
        >= rank_fraction * cp.trace(lifted),
    ]
    for index in forced:
        constraints.append(vector[index] <= forced_value)
    objective = cp.Minimize(
        threshold + proximal * cp.sum_squares(vector - multipliers) / blocks
    )
    problem = cp.Problem(objective, constraints)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        problem.solve(
            solver="SCS",
            eps=solver_eps,
            max_iters=solver_iters,
            verbose=False,
            warm_start=True,
        )
    if lifted.value is None or threshold.value is None:
        raise RuntimeError(f"SROCR solve failed with status {problem.status}")
    extracted, new_direction, ratio = extract_rank_one(lifted.value, fractions)
    return (
        extracted,
        new_direction,
        ratio,
        float(threshold.value),
        str(problem.status),
        ordered,
    )


def make_candidate(
    label: str,
    baseline: np.ndarray,
    labels: np.ndarray,
    multipliers: np.ndarray,
    rank_ratio: float | None,
) -> tuple[Candidate, np.ndarray]:
    values = normalize(baseline * multipliers[labels])
    score, convolution = screen(values)
    flips = int(np.count_nonzero(np.signbit(values) != np.signbit(baseline)))
    return Candidate(label, multipliers.copy(), values, score, flips, rank_ratio), convolution


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs-rank-lift")
    parser.add_argument(
        "--partition",
        choices=("periodic", "contiguous", "unequal-energy", "support-periodic"),
        default="support-periodic",
    )
    parser.add_argument("--blocks", type=int, default=64)
    parser.add_argument("--support-count", type=int, default=8)
    parser.add_argument("--cell-width", type=int, default=1)
    parser.add_argument("--forced-value", type=float, default=-1.0)
    parser.add_argument("--rank-schedule", default="0.97,0.99,0.997,0.999")
    parser.add_argument("--cuts-per-stage", type=int, default=4)
    parser.add_argument("--active-count", type=int, default=128)
    parser.add_argument("--cut-count", type=int, default=128)
    parser.add_argument("--uniform-lags", type=int, default=257)
    parser.add_argument("--amplitude", type=float, default=4.0)
    parser.add_argument("--proximal", type=float, default=1e-6)
    parser.add_argument("--solver-eps", type=float, default=5e-5)
    parser.add_argument("--solver-iters", type=int, default=20_000)
    parser.add_argument("--violation-tol", type=float, default=1e-5)
    parser.add_argument("--exact-window", type=float, default=0.1)
    parser.add_argument("--homotopy", default="0.500001,0.6,0.75,0.9,1.0")
    args = parser.parse_args()
    if args.cuts_per_stage < 1 or args.active_count < 1 or args.cut_count < 1:
        raise ValueError("cut and active counts must be positive")
    if args.forced_value >= 0.0:
        raise ValueError("--forced-value must be negative to change topology")

    baseline = normalize(np.load(args.input, allow_pickle=False).astype(np.float64))
    baseline_score, baseline_argmax, baseline_max, baseline_min = exact_metrics(baseline)
    _, baseline_fft = screen(baseline)
    reference_max = float(np.max(baseline_fft))
    labels, forced, partition_metadata = make_partition(
        baseline,
        args.blocks,
        args.partition,
        args.support_count,
        args.cell_width,
    )
    fractions = mass_fractions(baseline, labels, args.blocks)
    multipliers, seed_score, seed_convolution = seed_multipliers(
        baseline,
        labels,
        args.blocks,
        forced,
        args.forced_value,
    )
    seed, _ = make_candidate(
        "topology-seed", baseline, labels, multipliers, rank_ratio=1.0
    )

    run_dir = args.run_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "baseline.npy", baseline)
    atomic_npy(run_dir / "seed.npy", seed.values)
    atomic_npy(run_dir / "seed-multipliers.npy", multipliers)
    atomic_npy(run_dir / "best.npy", baseline)

    active = set(top_indices(baseline_fft, args.active_count).tolist())
    active.update(top_indices(seed_convolution, args.active_count).tolist())
    if args.uniform_lags > 0:
        active.update(
            np.linspace(
                0,
                len(baseline_fft) - 1,
                args.uniform_lags,
                dtype=np.int64,
            ).tolist()
        )
    augmented = np.r_[multipliers, 1.0]
    direction = augmented / np.linalg.norm(augmented)
    candidates: list[Candidate] = [seed]
    iterations = 0

    for stage, rank_fraction in enumerate(
        parse_numbers(args.rank_schedule, float), start=1
    ):
        for cut in range(1, args.cuts_per_stage + 1):
            iterations += 1
            previous = multipliers.copy()
            try:
                (
                    multipliers,
                    direction,
                    ratio,
                    threshold,
                    status,
                    ordered_lags,
                ) = solve_stage(
                    baseline,
                    labels,
                    fractions,
                    forced,
                    args.forced_value,
                    active,
                    reference_max,
                    previous,
                    direction,
                    rank_fraction,
                    args.amplitude,
                    args.proximal,
                    args.solver_eps,
                    args.solver_iters,
                )
            except RuntimeError as error:
                append_event(
                    events_path,
                    {
                        "event": "solver_failure",
                        "stage": stage,
                        "cut": cut,
                        "rank_fraction": rank_fraction,
                        "error": str(error),
                    },
                )
                break
            candidate, convolution = make_candidate(
                f"stage-{stage:02d}-cut-{cut:02d}",
                baseline,
                labels,
                multipliers,
                ratio,
            )
            candidates.append(candidate)
            normalized_peak = convolution / reference_max
            violating = np.flatnonzero(
                normalized_peak > threshold * (1.0 + args.violation_tol)
            )
            if len(violating):
                ordered_violating = violating[
                    np.argsort(normalized_peak[violating])[::-1]
                ]
                additions = [
                    int(value)
                    for value in ordered_violating
                    if int(value) not in active
                ][: args.cut_count]
            else:
                additions = []
            active.update(additions)
            stage_dir = run_dir / f"stage-{stage:02d}-cut-{cut:02d}"
            stage_dir.mkdir()
            atomic_npy(stage_dir / "multipliers.npy", multipliers)
            atomic_npy(stage_dir / "candidate.npy", candidate.values)
            checkpoint = {
                "stage": stage,
                "cut": cut,
                "rank_fraction_constraint": rank_fraction,
                "rank_ratio": ratio,
                "solver_status": status,
                "relaxed_threshold_ratio": threshold,
                "screen_score": candidate.screen_score,
                "sign_flips": candidate.sign_flips,
                "active_lags": len(active),
                "active_lags_before_addition": len(ordered_lags),
                "violating_lags": len(violating),
                "added_lags": additions,
                "multiplier_min": float(np.min(multipliers)),
                "multiplier_max": float(np.max(multipliers)),
                "forced_multipliers": [float(multipliers[index]) for index in forced],
            }
            atomic_json(stage_dir / "checkpoint.json", checkpoint)
            append_event(events_path, {"event": "srocr_stage", **checkpoint})
            print(json.dumps(checkpoint, sort_keys=True), flush=True)
            if not additions:
                break

    final = candidates[-1]
    for alpha in parse_numbers(args.homotopy, float):
        mixed = 1.0 + alpha * (final.multipliers - 1.0)
        mixed = mass_correct(mixed, fractions)
        candidate, _ = make_candidate(
            f"homotopy-{alpha:.12g}", baseline, labels, mixed, final.rank_ratio
        )
        if candidate.sign_flips:
            candidates.append(candidate)

    # Exact direct replay is deliberately bounded: replay the topology seed,
    # the best screened topology candidate, and any screened baseline-beater.
    topology_candidates = [candidate for candidate in candidates if candidate.sign_flips]
    topology_candidates.sort(key=lambda candidate: candidate.screen_score)
    exact_queue: list[Candidate] = []
    exact_labels: set[str] = set()
    for candidate in [seed, *topology_candidates[:1]]:
        if candidate.label not in exact_labels:
            exact_queue.append(candidate)
            exact_labels.add(candidate.label)
    for candidate in topology_candidates:
        if candidate.screen_score < baseline_score and candidate.label not in exact_labels:
            exact_queue.append(candidate)
            exact_labels.add(candidate.label)
    exact_queue = [
        candidate
        for candidate in exact_queue
        if candidate.screen_score <= baseline_score + args.exact_window
    ]

    best = baseline.copy()
    best_score = baseline_score
    exact_records: list[dict[str, object]] = []
    for index, candidate in enumerate(exact_queue, start=1):
        path = run_dir / f"exact-candidate-{index:02d}.npy"
        atomic_npy(path, candidate.values)
        score, argmax, maximum, minimum = exact_metrics(candidate.values)
        accepted = score < best_score
        if accepted:
            best = candidate.values.copy()
            best_score = score
            atomic_npy(run_dir / "best.npy", best)
        record = {
            "label": candidate.label,
            "screen_score": candidate.screen_score,
            "exact_score": score,
            "argmax": argmax,
            "max_convolution": maximum,
            "min_convolution": minimum,
            "sign_flips": candidate.sign_flips,
            "rank_ratio": candidate.rank_ratio,
            "accepted": accepted,
            "path": str(path),
            "sha256": sha256(path),
        }
        exact_records.append(record)
        append_event(events_path, {"event": "exact_replay", **record})
        print(json.dumps(record, sort_keys=True), flush=True)

    payload = run_dir / "best.npy"
    best_score, best_argmax, best_max, best_min = exact_metrics(best)
    summary = {
        "reproduction_command": [
            sys.executable,
            str(Path(__file__).resolve()),
            *sys.argv[1:],
        ],
        "input": str(args.input.resolve()),
        "partition": partition_metadata,
        "blocks": args.blocks,
        "forced_classes": forced,
        "forced_value": args.forced_value,
        "baseline_score": baseline_score,
        "baseline_argmax": baseline_argmax,
        "baseline_max_convolution": baseline_max,
        "baseline_min_convolution": baseline_min,
        "seed_screen_score": seed_score,
        "best_topology_screen_score": topology_candidates[0].screen_score,
        "best_score": best_score,
        "best_argmax": best_argmax,
        "best_max_convolution": best_max,
        "best_min_convolution": best_min,
        "gain": baseline_score - best_score,
        "target_score": TARGET_SCORE,
        "leader_score": LEADER_SCORE,
        "gate_gap": best_score - TARGET_SCORE,
        "gate_cleared": best_score < TARGET_SCORE,
        "iterations": iterations,
        "active_lags_final": len(active),
        "exact_replays": exact_records,
        "payload": str(payload),
        "payload_sha256": sha256(payload),
        "verifier_sha256": VERIFIER_SHA256,
        "literature": [
            {
                "title": "Unimodular Waveform Design that Minimizes PSL of Ambiguity Function over A Continuous Doppler Frequency Shift Region of Interest",
                "citation": "https://paperclip.gxl.ai/citations/papers/arx_2504.06038#L3,L14,L95-L129",
                "use": "rank-lifted peak minimax with sequential rank-one relaxation",
            },
            {
                "title": "On suprema of convolutions on discrete cubes",
                "citation": "https://paperclip.gxl.ai/citations/papers/arx_2512.18188#L78-L80",
                "use": "related-problem motivation for active convolution-coefficient equality exchange only",
            },
        ],
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
