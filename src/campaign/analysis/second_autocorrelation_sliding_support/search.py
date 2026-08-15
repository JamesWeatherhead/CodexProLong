#!/usr/bin/env python3
"""Native C2 support insertion with joint packet relocation.

This is a bounded, deterministic heuristic inspired by Sliding Frank--Wolfe:

1. compute the exact one-sided C2 log-objective certificate on the native grid;
2. insert a packet at a certificate-selected off-support location;
3. use a bounded discrete outer search to relocate the new and existing
   packets, jointly re-optimizing every amplitude against the actual nonsmooth
   C2 max-ratio after each support configuration;
4. let only the unchanged frozen verifier decide acceptance.

The literature convergence theorems concern convex optimization over measures
and do not apply here.  This file borrows the operator pattern, not a guarantee.
Every run artifact is append-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.optimize import minimize
from scipy.signal import find_peaks, oaconvolve


ROOT = Path(__file__).resolve().parent
ARENA = ROOT.parents[2]
VERIFIER = (
    ARENA
    / "campaign/state/problems/second-autocorrelation-inequality"
    / "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768.py"
)
VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
DEFAULT_SEED = (
    ARENA
    / "campaign/c2_simpletes_transfer/runs/20260815T045500Z-repeat/best.npy"
)
SEED_VALUES_SHA256 = "8ad79d6fa04b566b852138709d959df928a7ec7cd36143d03a80901c1b485e34"
PUBLIC_LEADER = 0.963588110582029
MIN_IMPROVEMENT = 1.0e-5
STRICT_GATE = PUBLIC_LEADER + MIN_IMPROVEMENT
RANDOM_SEED = 2026081503


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_values(values: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()


def check_verifier_hash() -> None:
    if sha256_file(VERIFIER) != VERIFIER_SHA256:
        raise RuntimeError("frozen verifier hash mismatch")


def exact_score(values: np.ndarray) -> float:
    """Clean-room mirror of the hash-pinned C2 scoring formula.

    The downloaded verifier is hashed but never imported or executed on host.
    Submission-grade acceptance remains the Docker controller's job.
    """

    function = np.asarray(values, dtype=np.float64)
    if function.ndim != 1 or np.any(function < -1.0e-6):
        raise ValueError("invalid C2 function")
    function = np.maximum(function, 0.0)
    if float(np.sum(function)) == 0.0:
        raise ValueError("function must have positive integral")
    convolution = oaconvolve(function, function, mode="full")
    intervals = np.diff(np.linspace(-0.5, 0.5, len(convolution) + 2))
    padded = np.concatenate(([0.0], convolution, [0.0]))
    left = padded[:-1]
    right = padded[1:]
    l2_squared = float(
        np.sum((intervals / 3.0) * (left**2 + left * right + right**2))
    )
    l1_norm = float(np.sum(np.abs(convolution)) / (len(convolution) + 1))
    infinity_norm = float(np.max(np.abs(convolution)))
    return float(l2_squared / (l1_norm * infinity_norm))


def write_json_once(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def write_npy_once(path: Path, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        np.save(handle, np.asarray(values, dtype=np.float64), allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())


def append_jsonl(path: Path, value: Any) -> None:
    with path.open("ab") as handle:
        handle.write((json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode())
        handle.flush()
        os.fsync(handle.fileno())


def normalize_mass(values: np.ndarray, mass: float) -> np.ndarray:
    result = np.maximum(np.asarray(values, dtype=np.float64), 0.0)
    total = float(result.sum())
    if not np.isfinite(total) or total <= 0.0:
        raise RuntimeError("invalid candidate mass")
    return np.ascontiguousarray(result * (mass / total))


def c2_log_and_gradient(values: np.ndarray) -> tuple[float, np.ndarray, dict[str, Any]]:
    """Return log(C2), an exact unique-max branch gradient, and diagnostics."""

    convolution = oaconvolve(values, values, mode="full")
    numerator = float(
        (2.0 * np.dot(convolution, convolution) + np.dot(convolution[:-1], convolution[1:]))
        / 3.0
    )
    mass = float(values.sum())
    active_lag = int(np.argmax(convolution))
    maximum = float(convolution[active_lag])
    if numerator <= 0.0 or mass <= 0.0 or maximum <= 0.0:
        raise RuntimeError("invalid C2 components")

    kernel = 4.0 * convolution / (3.0 * numerator)
    kernel[:-1] += convolution[1:] / (3.0 * numerator)
    kernel[1:] += convolution[:-1] / (3.0 * numerator)
    kernel[active_lag] -= 1.0 / maximum
    gradient = 2.0 * oaconvolve(kernel, values[::-1], mode="valid") - 2.0 / mass
    score = numerator / (mass * mass * maximum)
    diagnostics = {
        "score": float(score),
        "active_lag": active_lag,
        "maximum": maximum,
        "numerator": numerator,
        "mass": mass,
        "near_active_lags_1e12": int(
            np.count_nonzero(convolution >= maximum * (1.0 - 1.0e-12))
        ),
    }
    return float(math.log(score)), np.asarray(gradient, dtype=np.float64), diagnostics


def shifted_slices(
    start: int, length: int, shift: float, n: int
) -> tuple[slice, slice, float]:
    integer = math.floor(shift)
    fraction = float(shift - integer)
    low = start + integer
    high = low + length
    if low < 0 or high + 1 > n:
        raise RuntimeError("shifted atom left the native domain")
    return slice(low, high), slice(low + 1, high + 1), fraction


def deposit(
    output: np.ndarray,
    template: np.ndarray,
    start: int,
    shift: float,
    amplitude: float,
) -> None:
    left, right, fraction = shifted_slices(start, template.size, shift, output.size)
    output[left] += amplitude * (1.0 - fraction) * template
    output[right] += amplitude * fraction * template


@dataclass(frozen=True)
class Atom:
    kind: str
    template_start: int
    target_start: int
    length: int
    shift_bound: int
    initial_direction: int

    def as_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "template_start": self.template_start,
            "target_start": self.target_start,
            "length": self.length,
            "shift_bound": self.shift_bound,
            "initial_direction": self.initial_direction,
        }


@dataclass(frozen=True)
class TrialSpec:
    width: int
    movable_count: int
    oracle_rank: int
    certificate: float
    donor_start: int
    target_start: int
    potential_material_births: int
    atoms: tuple[Atom, ...]

    def as_json(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "movable_count": self.movable_count,
            "oracle_rank": self.oracle_rank,
            "certificate": self.certificate,
            "donor_start": self.donor_start,
            "target_start": self.target_start,
            "potential_material_births": self.potential_material_births,
            "atoms": [atom.as_json() for atom in self.atoms],
        }


def top_peak_starts(values: np.ndarray, width: int, shift_bound: int) -> list[int]:
    distance = max(width, 256)
    peaks, _ = find_peaks(values, distance=distance)
    peaks = np.unique(np.append(peaks, int(np.argmax(values))))
    half = width // 2
    starts = peaks - half
    valid = (starts >= shift_bound + 1) & (
        starts + width + shift_bound + 1 <= values.size
    )
    starts = starts[valid]
    order = np.argsort(values[peaks[valid]])[::-1]
    return [int(starts[index]) for index in order]


def directional_shift_derivatives(
    gradient: np.ndarray, template: np.ndarray, start: int
) -> tuple[float, float]:
    base = float(np.dot(gradient[start : start + template.size], template))
    right = float(
        np.dot(
            gradient[start + 1 : start + template.size + 1]
            - gradient[start : start + template.size],
            template,
        )
    )
    left_derivative = float(
        np.dot(
            gradient[start : start + template.size]
            - gradient[start - 1 : start + template.size - 1],
            template,
        )
    )
    # A negative move improves to first order when left_derivative is negative.
    return base, right if right >= -left_derivative else left_derivative


def intervals_overlap(a: int, b: int, c: int, d: int) -> bool:
    return max(a, c) < min(b, d)


def choose_movable_atoms(
    values: np.ndarray,
    gradient: np.ndarray,
    width: int,
    shift_bound: int,
    count: int,
    target_start: int,
) -> tuple[Atom, ...]:
    candidates: list[tuple[float, int, int]] = []
    for start in top_peak_starts(values, width, shift_bound)[:512]:
        template = values[start : start + width]
        if float(template.sum()) <= 1.0e-12:
            continue
        amp, signed_shift_derivative = directional_shift_derivatives(
            gradient, template, start
        )
        right = float(
            np.dot(
                gradient[start + 1 : start + width + 1]
                - gradient[start : start + width],
                template,
            )
        )
        left = float(
            np.dot(
                gradient[start : start + width]
                - gradient[start - 1 : start + width - 1],
                template,
            )
        )
        direction = 1 if right >= -left else -1
        priority = abs(amp) * 0.5 + max(right, -left, 0.0) * shift_bound
        if signed_shift_derivative == 0.0 and amp == 0.0:
            continue
        candidates.append((float(priority), start, direction))

    atoms: list[Atom] = []
    expanded_target = (
        target_start - shift_bound - 1,
        target_start + width + shift_bound + 1,
    )
    for _, start, direction in sorted(candidates, reverse=True):
        expanded = (start - shift_bound - 1, start + width + shift_bound + 1)
        if intervals_overlap(*expanded, *expanded_target):
            continue
        if any(
            intervals_overlap(
                *expanded,
                other.target_start - shift_bound - 1,
                other.target_start + width + shift_bound + 1,
            )
            for other in atoms
        ):
            continue
        atoms.append(
            Atom(
                kind="existing",
                template_start=start,
                target_start=start,
                length=width,
                shift_bound=shift_bound,
                initial_direction=direction,
            )
        )
        if len(atoms) == count:
            break
    if len(atoms) < count:
        raise RuntimeError(f"only found {len(atoms)} disjoint movable atoms for {count}")
    return tuple(atoms)


def oracle_pairs(
    values: np.ndarray,
    gradient: np.ndarray,
    width: int,
    shift_bound: int,
    pair_count: int,
    material_threshold: float,
) -> list[tuple[float, int, int, int]]:
    support = values > material_threshold
    pairs: list[tuple[float, int, int, int]] = []
    donors = top_peak_starts(values, width, shift_bound)[:8]
    for donor_start in donors:
        template = values[donor_start : donor_start + width]
        donor_support = template > material_threshold
        donor_support_count = int(np.count_nonzero(donor_support))
        if donor_support_count == 0:
            continue
        correlations = oaconvolve(gradient, template[::-1], mode="valid")
        # Apply the off-support constraint *before* ranking.  The strongest
        # unconstrained correlations are existing spikes; the linear oracle
        # must instead select a location that creates new material support.
        birth_counts = np.rint(
            oaconvolve(
                (~support).astype(np.float64),
                donor_support[::-1].astype(np.float64),
                mode="valid",
            )
        ).astype(np.int64)
        minimum_births = max(1, int(math.ceil(0.2 * donor_support_count)))
        eligible = birth_counts >= minimum_births
        eligible[: shift_bound + 1] = False
        eligible[values.size - width - shift_bound :] = False
        donor_low = max(0, donor_start - 2 * width + 1)
        donor_high = min(eligible.size, donor_start + 2 * width)
        eligible[donor_low:donor_high] = False
        eligible_indices = np.flatnonzero(eligible)
        if eligible_indices.size == 0:
            continue
        take = min(20000, eligible_indices.size)
        local = np.argpartition(correlations[eligible_indices], -take)[-take:]
        indices = eligible_indices[local]
        indices = indices[np.argsort(correlations[indices])[::-1]]
        found_for_donor = 0
        for target_start_raw in indices:
            target_start = int(target_start_raw)
            if target_start < shift_bound + 1:
                continue
            if target_start + width + shift_bound + 1 > values.size:
                continue
            if abs(target_start - donor_start) < 2 * width:
                continue
            potential_births = int(
                np.count_nonzero(donor_support & ~support[target_start : target_start + width])
            )
            if potential_births < minimum_births:
                continue
            if any(abs(target_start - existing[2]) < width for existing in pairs):
                continue
            pairs.append(
                (
                    float(correlations[target_start]),
                    donor_start,
                    target_start,
                    potential_births,
                )
            )
            found_for_donor += 1
            if found_for_donor == 3:
                break
    pairs.sort(reverse=True)
    selected: list[tuple[float, int, int, int]] = []
    for pair in pairs:
        if any(abs(pair[2] - prior[2]) < width for prior in selected):
            continue
        selected.append(pair)
        if len(selected) == pair_count:
            break
    if len(selected) < pair_count:
        raise RuntimeError(f"only found {len(selected)} oracle pairs for width {width}")
    return selected


def make_specs(
    values: np.ndarray,
    widths: Iterable[int],
    movable_counts: Iterable[int],
    pair_count: int,
) -> tuple[list[TrialSpec], dict[str, Any]]:
    log_score, gradient, diagnostics = c2_log_and_gradient(values)
    del log_score
    material_threshold = float(values.max() * 1.0e-10)
    specs: list[TrialSpec] = []
    for width in widths:
        if width % 2 == 0 or width < 3:
            raise ValueError("widths must be odd and at least 3")
        shift_bound = max(2, min(512, width // 4))
        pairs = oracle_pairs(
            values,
            gradient,
            width,
            shift_bound,
            pair_count,
            material_threshold,
        )
        for oracle_rank, (certificate, donor_start, target_start, births) in enumerate(pairs):
            for movable_count in movable_counts:
                existing = choose_movable_atoms(
                    values,
                    gradient,
                    width,
                    shift_bound,
                    movable_count,
                    target_start,
                )
                birth_template = values[donor_start : donor_start + width]
                right = float(
                    np.dot(
                        gradient[target_start + 1 : target_start + width + 1]
                        - gradient[target_start : target_start + width],
                        birth_template,
                    )
                )
                left = float(
                    np.dot(
                        gradient[target_start : target_start + width]
                        - gradient[target_start - 1 : target_start + width - 1],
                        birth_template,
                    )
                )
                birth_direction = 1 if right >= -left else -1
                birth = Atom(
                    kind="birth",
                    template_start=donor_start,
                    target_start=target_start,
                    length=width,
                    shift_bound=shift_bound,
                    initial_direction=birth_direction,
                )
                specs.append(
                    TrialSpec(
                        width=width,
                        movable_count=movable_count,
                        oracle_rank=oracle_rank,
                        certificate=certificate,
                        donor_start=donor_start,
                        target_start=target_start,
                        potential_material_births=births,
                        atoms=existing + (birth,),
                    )
                )
    return specs, {
        "seed_gradient_min": float(gradient.min()),
        "seed_gradient_max": float(gradient.max()),
        "material_threshold": material_threshold,
        "seed_components": diagnostics,
    }


class JointObjective:
    def __init__(self, seed: np.ndarray, atoms: tuple[Atom, ...]):
        self.seed = seed
        self.atoms = atoms
        self.templates = [
            seed[atom.template_start : atom.template_start + atom.length].copy()
            for atom in atoms
        ]
        self.background = seed.copy()
        for atom in atoms:
            if atom.kind == "existing":
                self.background[
                    atom.target_start : atom.target_start + atom.length
                ] = 0.0
        self.calls = 0
        self.active_lags: set[int] = set()

    def initial_and_bounds(self) -> tuple[np.ndarray, list[tuple[float, float]]]:
        initial: list[float] = []
        bounds: list[tuple[float, float]] = []
        for atom in self.atoms:
            if atom.kind == "existing":
                initial.extend([1.0, 1.0e-3 * atom.initial_direction])
                bounds.extend([(0.25, 2.0), (-atom.shift_bound, atom.shift_bound)])
            else:
                # A small positive initialization lets L-BFGS see both joint
                # amplitude/location derivatives; zero remains an allowed exit.
                initial.extend([1.0e-3, 1.0e-3 * atom.initial_direction])
                bounds.extend([(0.0, 2.0), (-atom.shift_bound, atom.shift_bound)])
        return np.asarray(initial, dtype=np.float64), bounds

    def build(self, parameters: np.ndarray) -> np.ndarray:
        output = self.background.copy()
        for index, (atom, template) in enumerate(zip(self.atoms, self.templates, strict=True)):
            amplitude = float(parameters[2 * index])
            shift = float(parameters[2 * index + 1])
            deposit(output, template, atom.target_start, shift, amplitude)
        if not np.isfinite(output).all() or np.any(output < 0.0):
            raise RuntimeError("joint parameterization produced invalid values")
        return output

    def __call__(self, parameters: np.ndarray) -> tuple[float, np.ndarray]:
        values = self.build(parameters)
        log_score, gradient, diagnostics = c2_log_and_gradient(values)
        self.calls += 1
        self.active_lags.add(int(diagnostics["active_lag"]))
        parameter_gradient: list[float] = []
        for index, (atom, template) in enumerate(zip(self.atoms, self.templates, strict=True)):
            amplitude = float(parameters[2 * index])
            shift = float(parameters[2 * index + 1])
            left, right, fraction = shifted_slices(
                atom.target_start, atom.length, shift, values.size
            )
            left_dot = float(np.dot(gradient[left], template))
            right_dot = float(np.dot(gradient[right], template))
            amplitude_gradient = (1.0 - fraction) * left_dot + fraction * right_dot
            shift_gradient = amplitude * (right_dot - left_dot)
            parameter_gradient.extend([amplitude_gradient, shift_gradient])
        return -log_score, -np.asarray(parameter_gradient, dtype=np.float64)


def topology(seed: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    candidate_scaled = normalize_mass(candidate, float(seed.sum()))
    threshold = float(seed.max() * 1.0e-10)
    before = seed > threshold
    after = candidate_scaled > threshold
    return {
        "material_threshold": threshold,
        "material_births": int(np.count_nonzero(after & ~before)),
        "material_deaths": int(np.count_nonzero(before & ~after)),
        "material_support_xor": int(np.count_nonzero(after ^ before)),
        "l1_moved_fraction": float(np.abs(candidate_scaled - seed).sum() / seed.sum()),
        "nonzero": int(np.count_nonzero(candidate_scaled)),
    }


def genuine_topology(metrics: dict[str, Any]) -> bool:
    return bool(
        metrics["material_births"] >= 1
        and metrics["material_support_xor"] >= 2
        and metrics["l1_moved_fraction"] >= 1.0e-6
    )


def discrete_configurations(
    seed: np.ndarray, spec: TrialSpec
) -> list[dict[str, Any]]:
    """Finite support-location configurations for the nonlinear outer search."""

    atom_count = len(spec.atoms)
    bound = spec.atoms[0].shift_bound
    middle = max(2, bound // 4)
    scales = sorted({1, middle, bound})
    configurations: list[dict[str, Any]] = []

    def add(name: str, shifts: list[int], birth_mass_floor: float) -> None:
        configurations.append(
            {
                "name": name,
                "shifts": shifts,
                "birth_mass_floor": birth_mass_floor,
            }
        )

    zeros = [0] * atom_count
    for floor in (0.0, 1.0e-6, 1.0e-5):
        add(f"insert_only_floor_{floor:g}", zeros.copy(), floor)
    for scale in scales:
        shifts = [atom.initial_direction * scale for atom in spec.atoms]
        floors = (0.0, 1.0e-6) if scale == 1 else (1.0e-6,)
        for floor in floors:
            add(f"joint_all_scale_{scale}_floor_{floor:g}", shifts.copy(), floor)

    # A simultaneous but sparser relocation guards against destructive motion
    # of every sharp incumbent atom at once.  The birth and alternating half of
    # the existing set move together, with all weights still jointly resolved.
    half_shifts = [
        atom.initial_direction * middle
        if atom.kind == "birth" or index % 2 == 0
        else 0
        for index, atom in enumerate(spec.atoms)
    ]
    add("joint_alternating_middle_floor_1e-6", half_shifts, 1.0e-6)

    template_mass = float(
        seed[spec.donor_start : spec.donor_start + spec.width].sum()
    )
    for configuration in configurations:
        floor = float(configuration["birth_mass_floor"])
        minimum_amplitude = floor * float(seed.sum()) / template_mass
        configuration["birth_amplitude_floor"] = minimum_amplitude
    return [
        configuration
        for configuration in configurations
        if float(configuration["birth_amplitude_floor"]) <= 2.0
    ]


def optimize_fixed_support(
    seed: np.ndarray,
    spec: TrialSpec,
    configuration: dict[str, Any],
    maxiter: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Jointly resolve all atom weights for one discrete support configuration."""

    objective = JointObjective(seed, spec.atoms)
    shifts = np.asarray(configuration["shifts"], dtype=np.float64)
    atom_count = len(spec.atoms)

    def amplitudes_objective(amplitudes: np.ndarray) -> tuple[float, np.ndarray]:
        parameters = np.empty(2 * atom_count, dtype=np.float64)
        parameters[0::2] = amplitudes
        parameters[1::2] = shifts
        value, gradient = objective(parameters)
        return value, gradient[0::2]

    initial = np.ones(atom_count, dtype=np.float64)
    minimum_birth_amplitude = float(configuration["birth_amplitude_floor"])
    initial[-1] = minimum_birth_amplitude
    bounds = [(0.0, 2.0)] * (atom_count - 1) + [
        (minimum_birth_amplitude, 2.0)
    ]
    result = minimize(
        amplitudes_objective,
        initial,
        method="L-BFGS-B",
        jac=True,
        bounds=bounds,
        options={
            "maxiter": maxiter,
            "maxls": 12,
            "ftol": 1.0e-15,
            "gtol": 1.0e-10,
            "maxfun": max(40, maxiter * 6),
        },
    )
    parameters = np.empty(2 * atom_count, dtype=np.float64)
    parameters[0::2] = result.x
    parameters[1::2] = shifts
    candidate = normalize_mass(objective.build(parameters), float(seed.sum()))
    final_internal_score = c2_log_and_gradient(candidate)[2]["score"]
    birth_template_mass = float(
        seed[spec.donor_start : spec.donor_start + spec.width].sum()
    )
    metadata = {
        "configuration": configuration,
        "parameters": [float(value) for value in parameters],
        "amplitudes": [float(value) for value in result.x],
        "integer_shifts": [int(value) for value in shifts],
        "optimizer_success": bool(result.success),
        "optimizer_status": int(result.status),
        "optimizer_message": str(result.message),
        "optimizer_iterations": int(result.nit),
        "optimizer_function_evaluations": int(result.nfev),
        "objective_calls": objective.calls,
        "active_lags_seen": sorted(objective.active_lags),
        "optimizer_reported_score": float(math.exp(-float(result.fun))),
        "final_internal_score": float(final_internal_score),
        "birth_amplitude": float(result.x[-1]),
        "birth_shift": int(shifts[-1]),
        "birth_template_mass": birth_template_mass,
        "inserted_mass_fraction_before_global_normalization": float(
            result.x[-1] * birth_template_mass / seed.sum()
        ),
    }
    return candidate, metadata


def optimize_trial(
    seed: np.ndarray,
    spec: TrialSpec,
    maxiter: int,
) -> list[tuple[np.ndarray, dict[str, Any]]]:
    return [
        optimize_fixed_support(seed, spec, configuration, maxiter)
        for configuration in discrete_configurations(seed, spec)
    ]


def gradient_check(seed: np.ndarray, spec: TrialSpec) -> dict[str, Any]:
    objective = JointObjective(seed, spec.atoms)
    parameters, bounds = objective.initial_and_bounds()
    parameters = parameters.copy()
    for index, (low, high) in enumerate(bounds):
        parameters[index] = min(high - 0.01, max(low + 0.01, parameters[index]))
    value, analytic = objective(parameters)
    epsilon = 1.0e-6
    checks: list[dict[str, float]] = []
    for index in range(min(6, parameters.size)):
        plus = parameters.copy()
        minus = parameters.copy()
        plus[index] += epsilon
        minus[index] -= epsilon
        plus_value, _ = objective(plus)
        minus_value, _ = objective(minus)
        numeric = (plus_value - minus_value) / (2.0 * epsilon)
        absolute_error = abs(float(analytic[index]) - numeric)
        checks.append(
            {
                "index": float(index),
                "analytic": float(analytic[index]),
                "numeric": float(numeric),
                "absolute_error": absolute_error,
            }
        )
    return {"objective": value, "epsilon": epsilon, "checks": checks}


def parse_ints(value: str) -> tuple[int, ...]:
    return tuple(int(item) for item in value.split(",") if item)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--widths", default="65,257,1025,5455")
    parser.add_argument("--movable-counts", default="4,8")
    parser.add_argument("--pair-count", type=int, default=2)
    parser.add_argument("--maxiter", type=int, default=24)
    parser.add_argument("--gradient-check", action="store_true")
    args = parser.parse_args()

    run = ROOT / "runs" / args.run_id
    run.mkdir(parents=True, exist_ok=False)
    events = run / "events.jsonl"
    check_verifier_hash()
    seed = np.load(args.input, allow_pickle=False).astype(np.float64)
    seed = normalize_mass(seed, float(seed.sum()))
    if sha256_values(seed) != SEED_VALUES_SHA256:
        raise RuntimeError("seed value hash mismatch")
    seed_score = exact_score(seed)
    if seed_score != 0.9635881192968997:
        raise RuntimeError(f"unexpected frozen seed score: {seed_score}")
    write_npy_once(run / "seed.npy", seed)

    specs, certificate_audit = make_specs(
        seed,
        parse_ints(args.widths),
        parse_ints(args.movable_counts),
        args.pair_count,
    )
    input_manifest = {
        "input_origin": str(args.input.resolve()),
        "input_file_sha256": sha256_file(args.input),
        "input_values_sha256": sha256_values(seed),
        "seed_score": seed_score,
        "public_leader": PUBLIC_LEADER,
        "minimum_improvement": MIN_IMPROVEMENT,
        "strict_gate": STRICT_GATE,
        "verifier_sha256": VERIFIER_SHA256,
        "random_seed": RANDOM_SEED,
        "certificate_audit": certificate_audit,
        "configuration": {
            "widths": list(parse_ints(args.widths)),
            "movable_counts": list(parse_ints(args.movable_counts)),
            "pair_count": args.pair_count,
            "maxiter": args.maxiter,
        },
    }
    write_json_once(run / "input_manifest.json", input_manifest)
    write_json_once(run / "specs.json", [spec.as_json() for spec in specs])
    append_jsonl(events, {"event": "start", "spec_count": len(specs), **input_manifest})

    if args.gradient_check:
        check = gradient_check(seed, specs[0])
        write_json_once(run / "gradient_check.json", check)

    best_score = seed_score
    best_values = seed
    best_event: dict[str, Any] = {"kind": "seed", "score": seed_score}
    best_topology_score = -math.inf
    best_topology_values: np.ndarray | None = None
    best_topology_event: dict[str, Any] | None = None
    gate_events: list[dict[str, Any]] = []

    evaluation_count = 0
    for trial_index, spec in enumerate(specs, start=1):
        for candidate, optimization in optimize_trial(seed, spec, args.maxiter):
            evaluation_count += 1
            score = exact_score(candidate)
            verifier_minus_internal = float(score - optimization["final_internal_score"])
            if abs(verifier_minus_internal) > 5.0e-10:
                raise RuntimeError("internal objective and frozen verifier disagree")
            metrics = topology(seed, candidate)
            is_topology = genuine_topology(metrics)
            clears_gate = bool(score >= STRICT_GATE and is_topology)
            event = {
                "event": "evaluate",
                "evaluation": evaluation_count,
                "trial": trial_index,
                "spec": spec.as_json(),
                "optimization": optimization,
                "score": score,
                "verifier_minus_internal": verifier_minus_internal,
                "gain_from_seed": float(score - seed_score),
                "gap_to_gate": float(STRICT_GATE - score),
                "candidate_values_sha256": sha256_values(candidate),
                "topology": metrics,
                "genuine_topology": is_topology,
                "clears_gate": clears_gate,
            }
            append_jsonl(events, event)
            print(json.dumps(event, sort_keys=True), flush=True)
            if score > best_score:
                best_score = score
                best_values = candidate
                best_event = event
            if is_topology and score > best_topology_score:
                best_topology_score = score
                best_topology_values = candidate
                best_topology_event = event
            if clears_gate:
                gate_events.append(event)
                write_npy_once(
                    run / f"gate_candidate_{evaluation_count:03d}.npy", candidate
                )

    write_npy_once(run / "retained.npy", best_values)
    if best_topology_values is not None:
        write_npy_once(run / "best_topology.npy", best_topology_values)
    summary = {
        "mode": "native nonlinear support insertion plus joint packet relocation",
        "seed_score": seed_score,
        "best_score": best_score,
        "best_gain_from_seed": float(best_score - seed_score),
        "best_gap_to_gate": float(STRICT_GATE - best_score),
        "best_values_sha256": sha256_values(best_values),
        "best_event": best_event,
        "best_topology_score": None if best_topology_values is None else best_topology_score,
        "best_topology_gap_to_gate": (
            None
            if best_topology_values is None
            else float(STRICT_GATE - best_topology_score)
        ),
        "best_topology_values_sha256": (
            None if best_topology_values is None else sha256_values(best_topology_values)
        ),
        "best_topology_event": best_topology_event,
        "genuine_topology_definition": {
            "minimum_material_births": 1,
            "minimum_material_support_xor": 2,
            "minimum_l1_moved_fraction": 1.0e-6,
        },
        "trial_count": len(specs),
        "evaluation_count": evaluation_count,
        "gate_clearer_count": len(gate_events),
        "gate_cleared": bool(gate_events),
        "public_leader": PUBLIC_LEADER,
        "strict_gate": STRICT_GATE,
        "verifier_sha256": VERIFIER_SHA256,
    }
    write_json_once(run / "summary.json", summary)
    append_jsonl(events, {"event": "complete", "summary": summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
