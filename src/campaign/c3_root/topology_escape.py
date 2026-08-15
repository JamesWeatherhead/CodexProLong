#!/usr/bin/env python3
"""Checkpointed topology-changing escape search for the signed C3 problem.

This program deliberately leaves the local 68-mode epigraph model.  It builds
several finite (rather than infinitesimal) basin changes:

* a self-reflection spectral crossover at the Nyquist edge;
* birth/death moves on low-energy contiguous sign blocks; and
* coordinated births in a new orthant at several globally low-amplitude cells;
* periodic support death/rebirth on one low-energy residue class;
* unequal-cell phase slips, which delete one cell at one end of an interval
  and duplicate the cell at the other end.
* cross-basin recombination, which superposes finite displacements from two
  independently polished sign orthants before an exact-replayed repolish.

FFT convolution is only a screening/proposal mechanism.  Selected seeds and
every optimizer stage are rescored with literal float64 ``numpy.convolve``.
Only strict improvements under that exact replay replace ``best.npy``.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.optimize import minimize
from scipy.signal import fftconvolve
from scipy.special import logsumexp


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "runs-102400" / "20260815T011534Z" / "best.npy"
VERIFIER_SHA256 = "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9"
LEADER_SCORE = 1.4515718638902069
TARGET_SCORE = 1.4515618638902069


@dataclass
class Seed:
    family: str
    label: str
    values: np.ndarray
    screen_score: float
    sign_flips: int
    sign_changes: int
    rms_change: float


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
    """Literal public-verifier algebra using direct float64 convolution."""
    f = normalize(values)
    convolution = np.convolve(f, f, mode="full")
    maximum = float(np.max(convolution))
    score = float(abs(2.0 * len(f) * maximum / float(np.sum(f)) ** 2))
    return score, int(np.argmax(convolution)), maximum, float(np.min(convolution))


def screen_score(values: np.ndarray) -> float:
    f = normalize(values)
    convolution = fftconvolve(f, f, mode="full")
    return float(abs(2.0 * len(f) * float(np.max(convolution)) / np.sum(f) ** 2))


def topology(values: np.ndarray, baseline: np.ndarray) -> tuple[int, int, float]:
    signs = np.signbit(values)
    baseline_signs = np.signbit(baseline)
    flips = int(np.count_nonzero(signs != baseline_signs))
    changes = int(np.count_nonzero(signs[1:] != signs[:-1]))
    rms = float(np.sqrt(np.mean((values - baseline) ** 2)))
    return flips, changes, rms


def make_seed(
    family: str, label: str, values: np.ndarray, baseline: np.ndarray
) -> Seed | None:
    candidate = normalize(values)
    flips, changes, rms = topology(candidate, baseline)
    if flips == 0:
        return None
    return Seed(
        family=family,
        label=label,
        values=candidate,
        screen_score=screen_score(candidate),
        sign_flips=flips,
        sign_changes=changes,
        rms_change=rms,
    )


def keep_best(heap: list[tuple[float, int, Seed]], seed: Seed, limit: int, serial: int) -> None:
    item = (-seed.screen_score, serial, seed)
    if len(heap) < limit:
        heapq.heappush(heap, item)
    elif item > heap[0]:
        heapq.heapreplace(heap, item)


def nyquist_seeds(baseline: np.ndarray, alphas: Iterable[float]) -> list[Seed]:
    spectrum = np.fft.rfft(baseline)
    reflected = np.fft.rfft(baseline[::-1])
    result: list[Seed] = []
    for alpha in alphas:
        proposal = spectrum.copy()
        proposal[-1] += alpha * (reflected[-1] - spectrum[-1])
        proposal[0] = spectrum[0]
        values = np.fft.irfft(proposal, len(baseline))
        seed = make_seed(
            "nyquist-reflection",
            f"nyquist-alpha-{alpha:.12g}",
            values,
            baseline,
        )
        if seed is not None:
            result.append(seed)
    return result


def block_seeds(
    baseline: np.ndarray,
    widths: Iterable[int],
    positions_per_width: int,
    keep_per_family: int,
) -> list[Seed]:
    heap: list[tuple[float, int, Seed]] = []
    serial = 0
    n = len(baseline)
    for width in widths:
        if width < 1 or width >= n:
            continue
        energy = np.convolve(baseline * baseline, np.ones(width), mode="valid")
        count = min(positions_per_width, len(energy))
        low_energy = np.argpartition(energy, count - 1)[:count]
        uniform = np.linspace(0, len(energy) - 1, count, dtype=np.int64)
        positions = np.unique(np.concatenate([low_energy, uniform]))
        for lower in positions:
            lower = int(lower)
            upper = lower + width
            for transform in ("center", "zero", "flip"):
                proposal = baseline.copy()
                if transform == "center":
                    proposal[lower:upper] -= np.mean(proposal[lower:upper])
                elif transform == "zero":
                    proposal[lower:upper] = 0.0
                else:
                    proposal[lower:upper] *= -1.0
                proposal = normalize(proposal)
                seed = make_seed(
                    "block-birth-death",
                    f"block-{transform}-w{width}-i{lower}",
                    proposal,
                    baseline,
                )
                if seed is not None:
                    serial += 1
                    keep_best(heap, seed, keep_per_family, serial)
    return [item[2] for item in sorted(heap, reverse=True)]


def coordinated_support_seeds(
    baseline: np.ndarray,
    counts: Iterable[int],
    transforms: Iterable[str],
) -> list[Seed]:
    """Change several weak cells together to enter a new sign orthant.

    Single-coordinate support flips were already tested in this campaign.  The
    point of this family is instead a *coordinated* support birth: the globally
    weakest ``count`` cells change at once and the subsequent signed-square
    polish optimizes inside that new orthant.  This is a finite topology move,
    while selecting low-amplitude cells keeps its exact starting penalty small.
    """
    order = np.argsort(np.abs(baseline), kind="stable")
    result: list[Seed] = []
    for count in counts:
        if count < 2 or count > len(baseline):
            continue
        indices = order[:count]
        for transform in transforms:
            proposal = baseline.copy()
            if transform == "flip":
                proposal[indices] *= -1.0
            elif transform == "zero-cross":
                # Cross the orthant boundary by a small but nonzero amount so
                # the signed-square reparameterization retains the new signs.
                proposal[indices] = -np.sign(proposal[indices]) * np.maximum(
                    np.abs(proposal[indices]), 1e-12
                )
            else:
                raise ValueError(f"unknown support transform: {transform}")
            seed = make_seed(
                "coordinated-support-birth",
                f"support-{transform}-k{count}",
                proposal,
                baseline,
            )
            if seed is not None:
                result.append(seed)
    return result


def periodic_support_seeds(
    baseline: np.ndarray,
    periods: Iterable[int],
    factor: float,
    class_pool: int,
) -> list[Seed]:
    """Kill and reverse one low-energy periodic residue class.

    Unlike the globally weakest-cell move, this retains a rigid multiresolution
    support pattern: all indices in one residue class modulo ``period`` cross
    zero together.  The small negative factor represents support death followed
    by birth into a new orthant; signed-square polishing can then regrow every
    selected cell independently without allowing it to cross back immediately.
    """
    if factor >= 0.0:
        raise ValueError("periodic support factor must be negative")
    positions = np.arange(len(baseline), dtype=np.int64)
    result: list[Seed] = []
    for period in periods:
        if period < 2 or period > len(baseline):
            continue
        residues = positions % period
        energy = np.bincount(residues, weights=baseline * baseline, minlength=period)
        count = min(max(1, class_pool), period)
        pool = np.argpartition(energy, count - 1)[:count]
        best: Seed | None = None
        for residue in pool:
            proposal = baseline.copy()
            proposal[residues == residue] *= factor
            seed = make_seed(
                "periodic-support-birth",
                f"periodic-p{period}-r{int(residue)}-factor{factor:.12g}",
                proposal,
                baseline,
            )
            if seed is not None and (best is None or seed.screen_score < best.screen_score):
                best = seed
        if best is not None:
            result.append(best)
    return result


def phase_slip_seeds(
    baseline: np.ndarray,
    widths: Iterable[int],
    alphas: Iterable[float],
    positions_per_width: int,
    keep_per_family: int,
) -> list[Seed]:
    """Search finite unequal-cell moves on bounded intervals.

    A left slip removes the interval's first sample, shifts the surviving
    samples left, and duplicates the final sample.  The right slip is the
    reverse operation.  Thus the vector length and exterior samples are held
    fixed while the partition topology inside the interval changes.
    """
    heap: list[tuple[float, int, Seed]] = []
    serial = 0
    n = len(baseline)
    for width in widths:
        if width < 2 or width > n:
            continue
        starts = np.linspace(0, n - width, positions_per_width, dtype=np.int64)
        for lower in np.unique(starts):
            lower = int(lower)
            upper = lower + width
            for direction in ("left", "right"):
                shifted = baseline.copy()
                if direction == "left":
                    shifted[lower : upper - 1] = baseline[lower + 1 : upper]
                    shifted[upper - 1] = baseline[upper - 1]
                else:
                    shifted[lower + 1 : upper] = baseline[lower : upper - 1]
                    shifted[lower] = baseline[lower]
                for alpha in alphas:
                    if alpha <= 0.0 or alpha > 1.0:
                        continue
                    proposal = normalize(baseline + alpha * (shifted - baseline))
                    seed = make_seed(
                        "unequal-cell-slip",
                        f"slip-{direction}-w{width}-i{lower}-a{alpha:.12g}",
                        proposal,
                        baseline,
                    )
                    if seed is not None:
                        serial += 1
                        keep_best(heap, seed, keep_per_family, serial)
    return [item[2] for item in sorted(heap, reverse=True)]


def boundary_slip_seeds(
    baseline: np.ndarray,
    widths: Iterable[int],
    explicit_starts: Iterable[int],
    positions_per_width: int,
    keep_per_family: int,
    crossing_epsilon: float,
    minimum_alpha: float,
) -> list[Seed]:
    """Cross the first sign boundary along each unequal-cell slip homotopy."""
    if crossing_epsilon <= 0.0:
        raise ValueError("boundary crossing epsilon must be positive")
    heap: list[tuple[float, int, Seed]] = []
    serial = 0
    n = len(baseline)
    for width in widths:
        if width < 2 or width > n:
            continue
        starts = np.unique(
            np.r_[
                np.linspace(0, n - width, positions_per_width, dtype=np.int64),
                np.asarray(list(explicit_starts), dtype=np.int64),
            ]
        )
        for lower in np.unique(starts):
            lower = int(lower)
            upper = lower + width
            if lower < 0 or upper > n:
                continue
            for direction in ("left", "right"):
                shifted = baseline.copy()
                if direction == "left":
                    shifted[lower : upper - 1] = baseline[lower + 1 : upper]
                    shifted[upper - 1] = baseline[upper - 1]
                else:
                    shifted[lower + 1 : upper] = baseline[lower : upper - 1]
                    shifted[lower] = baseline[lower]
                difference = shifted - baseline
                local = np.arange(lower, upper, dtype=np.int64)
                crossing = local[
                    (baseline[local] * difference[local] < 0.0)
                    & (difference[local] != 0.0)
                ]
                if not len(crossing):
                    continue
                thresholds = -baseline[crossing] / difference[crossing]
                feasible = thresholds[
                    (thresholds >= minimum_alpha) & (thresholds <= 1.0)
                ]
                if not len(feasible):
                    continue
                alpha = float(np.min(feasible) * (1.0 + crossing_epsilon))
                if alpha > 1.0:
                    continue
                proposal = normalize(baseline + alpha * difference)
                seed = make_seed(
                    "boundary-cell-slip",
                    f"boundary-{direction}-w{width}-i{lower}-a{alpha:.17g}",
                    proposal,
                    baseline,
                )
                if seed is not None:
                    serial += 1
                    keep_best(heap, seed, keep_per_family, serial)
    return [item[2] for item in sorted(heap, reverse=True)]


def recombination_seeds(
    baseline: np.ndarray,
    inputs: Iterable[Path],
    scales: Iterable[float],
) -> list[Seed]:
    """Superpose finite displacements learned in distinct polished basins.

    Each donor is interpreted relative to the current baseline.  Pairwise
    displacement addition can retain both donors' support births and therefore
    enters a combined orthant that no convex interpolation visits.  This is a
    proposal mechanism only: the ordinary exact seed replay and exact final
    replay remain the acceptance authority.
    """
    donors: list[np.ndarray] = []
    for input_path in inputs:
        donor = normalize(np.load(input_path, allow_pickle=False).astype(np.float64))
        if donor.shape != baseline.shape:
            raise ValueError(
                f"recombination donor {input_path} has shape {donor.shape}, "
                f"expected {baseline.shape}"
            )
        donors.append(donor)

    result: list[Seed] = []
    coefficients = list(scales)
    for left in range(len(donors)):
        for right in range(left + 1, len(donors)):
            left_delta = donors[left] - baseline
            right_delta = donors[right] - baseline
            for left_scale in coefficients:
                for right_scale in coefficients:
                    proposal = baseline + left_scale * left_delta + right_scale * right_delta
                    seed = make_seed(
                        "cross-basin-recombination",
                        (
                            f"recombine-d{left + 1}x{left_scale:.12g}-"
                            f"d{right + 1}x{right_scale:.12g}"
                        ),
                        proposal,
                        baseline,
                    )
                    if seed is not None:
                        result.append(seed)
    return result


def to_parameter(values: np.ndarray) -> np.ndarray:
    return np.sign(values) * np.sqrt(np.abs(values))


def from_parameter(parameter: np.ndarray) -> np.ndarray:
    return parameter * np.abs(parameter)


def polish_seed(
    seed: Seed,
    baseline: np.ndarray,
    betas: list[float],
    maxiter: int,
    maxcor: int,
    lock_stages: int,
    events_path: Path,
    seed_index: int,
) -> tuple[np.ndarray, float, int]:
    current = seed.values.copy()
    parameter = to_parameter(current)
    changed = np.signbit(current) != np.signbit(baseline)
    reference_max = float(np.max(np.convolve(baseline, baseline, mode="full")))
    evaluations = 0

    for stage, beta in enumerate(betas, start=1):

        def objective_gradient(u: np.ndarray) -> tuple[float, np.ndarray]:
            nonlocal evaluations
            evaluations += 1
            f = from_parameter(u)
            convolution = fftconvolve(f, f, mode="full")
            logits = beta * (convolution / reference_max - 1.0)
            log_partition = float(logsumexp(logits))
            weights = np.exp(logits - log_partition)
            smooth_max = reference_max * (1.0 + log_partition / beta)
            mass = float(np.sum(f))
            objective = float(np.log(smooth_max) - 2.0 * np.log(abs(mass)))
            gradient_f = (
                2.0 * fftconvolve(weights, f[::-1], mode="valid") / smooth_max
                - 2.0 / mass
            )
            return objective, gradient_f * (2.0 * np.abs(u))

        bounds: list[tuple[float | None, float | None]] | None = None
        if stage <= lock_stages:
            bounds = [(None, None)] * len(parameter)
            for index in np.flatnonzero(changed):
                bounds[int(index)] = (
                    (1e-12, None) if current[index] >= 0.0 else (None, -1e-12)
                )
        result = minimize(
            objective_gradient,
            parameter,
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            options={
                "maxiter": maxiter,
                "maxcor": maxcor,
                "ftol": 1e-15,
                "gtol": 1e-12,
                "maxls": 40,
            },
        )
        current = normalize(from_parameter(np.asarray(result.x, dtype=np.float64)))
        parameter = to_parameter(current)
        score, argmax, maximum, minimum = exact_metrics(current)
        flips, changes, rms = topology(current, baseline)
        event = {
            "event": "polish_stage",
            "seed_index": seed_index,
            "seed_family": seed.family,
            "seed_label": seed.label,
            "stage": stage,
            "beta": beta,
            "locked_topology": stage <= lock_stages,
            "score": score,
            "argmax": argmax,
            "max_convolution": maximum,
            "min_convolution": minimum,
            "sign_flips": flips,
            "sign_changes": changes,
            "rms_from_baseline": rms,
            "nit": int(result.nit),
            "nfev": int(result.nfev),
            "optimizer_status": int(result.status),
            "optimizer_message": str(result.message),
            "total_seed_evaluations": evaluations,
        }
        append_event(events_path, event)
        print(json.dumps(event, sort_keys=True), flush=True)
    final_score = exact_metrics(current)[0]
    return current, final_score, evaluations


def parse_numbers(text: str, cast: type[float] | type[int]) -> list[float] | list[int]:
    return [cast(value) for value in text.split(",") if value]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs-topology-escape")
    parser.add_argument("--betas", default="3e7,1e8,3e8,1e9")
    parser.add_argument("--maxiter", type=int, default=600)
    parser.add_argument("--maxcor", type=int, default=80)
    parser.add_argument("--lock-stages", type=int, default=1)
    parser.add_argument("--max-seeds", type=int, default=6)
    parser.add_argument("--family-keep", type=int, default=6)
    parser.add_argument("--screen-penalty", type=float, default=1e-4)
    parser.add_argument("--positions-per-width", type=int, default=96)
    parser.add_argument("--block-widths", default="2,4,8,16,32,64,128")
    parser.add_argument("--slip-widths", default="32,128,512,2048,8192,32768")
    parser.add_argument("--slip-alphas", default="0.25,0.5,0.75,1.0")
    parser.add_argument("--boundary-widths", default="")
    parser.add_argument("--boundary-positions", type=int, default=192)
    parser.add_argument("--boundary-starts", default="")
    parser.add_argument("--boundary-epsilon", type=float, default=1e-7)
    parser.add_argument("--boundary-min-alpha", type=float, default=1e-3)
    parser.add_argument("--nyquist-alphas", default="0.1,0.3,0.5,1.0,-0.1")
    parser.add_argument("--support-counts", default="2,4,8,16,32")
    parser.add_argument("--support-transforms", default="flip")
    parser.add_argument("--periodic-periods", default="12800,25600")
    parser.add_argument("--periodic-factor", type=float, default=-0.01)
    parser.add_argument("--periodic-class-pool", type=int, default=256)
    parser.add_argument("--recombine-inputs", default="")
    parser.add_argument("--recombine-scales", default="1.0")
    parser.add_argument(
        "--families",
        default="all",
        help="comma-separated family names, or 'all'",
    )
    parser.add_argument("--screen-only", action="store_true")
    args = parser.parse_args()
    if args.max_seeds < 1 or args.family_keep < 1:
        raise ValueError("seed limits must be positive")

    baseline = normalize(np.load(args.input, allow_pickle=False).astype(np.float64))
    baseline_score, baseline_argmax, baseline_max, baseline_min = exact_metrics(baseline)
    run_dir = args.run_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "baseline.npy", baseline)
    atomic_npy(run_dir / "best.npy", baseline)

    selected_families = {value for value in args.families.split(",") if value}

    def enabled(family: str) -> bool:
        return selected_families == {"all"} or family in selected_families

    candidates: list[Seed] = []
    if enabled("nyquist-reflection"):
        candidates.extend(
            nyquist_seeds(
                baseline,
                parse_numbers(args.nyquist_alphas, float),
            )
        )
    if enabled("coordinated-support-birth"):
        candidates.extend(
            coordinated_support_seeds(
                baseline,
                parse_numbers(args.support_counts, int),
                [value for value in args.support_transforms.split(",") if value],
            )
        )
    if enabled("periodic-support-birth"):
        candidates.extend(
            periodic_support_seeds(
                baseline,
                parse_numbers(args.periodic_periods, int),
                args.periodic_factor,
                args.periodic_class_pool,
            )
        )
    if enabled("block-birth-death"):
        candidates.extend(
            block_seeds(
                baseline,
                parse_numbers(args.block_widths, int),
                args.positions_per_width,
                args.family_keep,
            )
        )
    if enabled("unequal-cell-slip"):
        candidates.extend(
            phase_slip_seeds(
                baseline,
                parse_numbers(args.slip_widths, int),
                parse_numbers(args.slip_alphas, float),
                args.positions_per_width,
                args.family_keep,
            )
        )
    if enabled("boundary-cell-slip"):
        candidates.extend(
            boundary_slip_seeds(
                baseline,
                parse_numbers(args.boundary_widths, int),
                parse_numbers(args.boundary_starts, int),
                args.boundary_positions,
                args.family_keep,
                args.boundary_epsilon,
                args.boundary_min_alpha,
            )
        )
    if enabled("cross-basin-recombination"):
        candidates.extend(
            recombination_seeds(
                baseline,
                [Path(value) for value in args.recombine_inputs.split(",") if value],
                parse_numbers(args.recombine_scales, float),
            )
        )

    # Preserve family diversity instead of letting tiny one-coordinate moves
    # crowd every genuinely nonlocal seed out of the polish budget.
    selected: list[Seed] = []
    by_family: dict[str, list[Seed]] = {}
    for candidate in candidates:
        if candidate.screen_score <= baseline_score + args.screen_penalty:
            by_family.setdefault(candidate.family, []).append(candidate)
    for family in sorted(by_family):
        by_family[family].sort(key=lambda seed: seed.screen_score)
        selected.append(by_family[family][0])
    remaining = sorted(
        [seed for seeds in by_family.values() for seed in seeds if seed not in selected],
        key=lambda seed: seed.screen_score,
    )
    selected.extend(remaining[: max(0, args.max_seeds - len(selected))])
    selected = selected[: args.max_seeds]

    screening = {
        "reproduction_command": [
            sys.executable,
            str(Path(__file__).resolve()),
            *sys.argv[1:],
        ],
        "input": str(args.input.resolve()),
        "baseline_score": baseline_score,
        "baseline_argmax": baseline_argmax,
        "baseline_max_convolution": baseline_max,
        "baseline_min_convolution": baseline_min,
        "screened_candidates_retained": len(candidates),
        "selected": [
            {
                "family": seed.family,
                "label": seed.label,
                "screen_score": seed.screen_score,
                "screen_penalty": seed.screen_score - baseline_score,
                "sign_flips": seed.sign_flips,
                "sign_changes": seed.sign_changes,
                "rms_change": seed.rms_change,
            }
            for seed in selected
        ],
    }
    atomic_json(run_dir / "screening.json", screening)
    print(json.dumps(screening, indent=2, sort_keys=True), flush=True)

    best = baseline.copy()
    best_score = baseline_score
    total_evaluations = 0
    exact_seed_records: list[dict[str, object]] = []
    final_records: list[dict[str, object]] = []
    if not args.screen_only:
        for index, seed in enumerate(selected, start=1):
            seed_path = run_dir / f"seed-{index:02d}.npy"
            atomic_npy(seed_path, seed.values)
            seed_score, seed_argmax, _, _ = exact_metrics(seed.values)
            exact_seed_records.append(
                {
                    "index": index,
                    "family": seed.family,
                    "label": seed.label,
                    "score": seed_score,
                    "argmax": seed_argmax,
                    "sign_flips": seed.sign_flips,
                    "path": str(seed_path),
                }
            )
            final, final_score, evaluations = polish_seed(
                seed,
                baseline,
                parse_numbers(args.betas, float),
                args.maxiter,
                args.maxcor,
                args.lock_stages,
                events_path,
                index,
            )
            total_evaluations += evaluations
            final_path = run_dir / f"final-{index:02d}.npy"
            atomic_npy(final_path, final)
            final_flips, final_changes, final_rms = topology(final, baseline)
            final_records.append(
                {
                    "index": index,
                    "family": seed.family,
                    "label": seed.label,
                    "score": final_score,
                    "sign_flips": final_flips,
                    "sign_changes": final_changes,
                    "rms_from_baseline": final_rms,
                    "path": str(final_path),
                    "sha256": hashlib.sha256(final_path.read_bytes()).hexdigest(),
                }
            )
            if final_score < best_score:
                best = final.copy()
                best_score = final_score
                atomic_npy(run_dir / "best.npy", best)
                append_event(
                    events_path,
                    {
                        "event": "exact_accept",
                        "seed_index": index,
                        "score": best_score,
                        "gain": baseline_score - best_score,
                        "gate_gap": best_score - TARGET_SCORE,
                    },
                )

    payload = run_dir / "best.npy"
    best_score, best_argmax, best_max, best_min = exact_metrics(best)
    best_flips, best_changes, best_rms = topology(best, baseline)
    summary = {
        "reproduction_command": screening["reproduction_command"],
        "input": str(args.input.resolve()),
        "baseline_score": baseline_score,
        "best_score": best_score,
        "gain": baseline_score - best_score,
        "leader_score": LEADER_SCORE,
        "target_score": TARGET_SCORE,
        "gate_gap": best_score - TARGET_SCORE,
        "gate_cleared": best_score < TARGET_SCORE,
        "n": len(best),
        "sum": float(np.sum(best)),
        "finite": bool(np.isfinite(best).all()),
        "argmax": best_argmax,
        "max_convolution": best_max,
        "min_convolution": best_min,
        "sign_flips_from_baseline": best_flips,
        "sign_changes": best_changes,
        "rms_from_baseline": best_rms,
        "selected_seeds": exact_seed_records,
        "final_candidates": final_records,
        "best_topology_score": (
            min(record["score"] for record in final_records)
            if final_records
            else None
        ),
        "evaluations": total_evaluations,
        "screen_only": args.screen_only,
        "verifier_sha256": VERIFIER_SHA256,
        "payload": str(payload),
        "payload_sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
