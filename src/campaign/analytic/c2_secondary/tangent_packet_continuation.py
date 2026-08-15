#!/usr/bin/env python3
"""Project the #2415->#2416 velocity onto a multiresolution contact tangent.

The correction variables are packet multipliers (comb rows split into phase
chunks), not two million independent coordinates.  A matrix-free LSMR solve
keeps the directional derivative of the leading convolution contacts nearly
equal, after which every trial is replayed with the exact float64 verifier
algebra and improvements are checkpointed atomically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.signal import oaconvolve
from scipy.sparse.linalg import LinearOperator, lsmr


ROOT = Path(__file__).resolve().parent
VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
PUBLIC_SCORE = 0.963588110582029
TARGET_SCORE = 0.963598110582029


def exact_components(values: np.ndarray) -> tuple[float, np.ndarray]:
    values = np.maximum(np.asarray(values, dtype=np.float64), 0.0)
    convolution = oaconvolve(values, values, mode="full")
    numerator = (
        2.0 * np.dot(convolution, convolution)
        + np.dot(convolution[:-1], convolution[1:])
    ) / 3.0
    score = numerator / (np.sum(values) ** 2 * np.max(convolution))
    return float(score), convolution


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


def packet_ids(n: int, period: int, splits: int) -> tuple[np.ndarray, int]:
    indices = np.arange(n, dtype=np.int64)
    rows = indices // period
    phases = ((indices % period) * splits) // period
    ids = (rows * splits + phases).astype(np.int32)
    return ids, int(ids[-1]) + 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous", type=Path, default=ROOT / "public_2415.npy")
    parser.add_argument("--current", type=Path, default=ROOT / "public_2416.npy")
    parser.add_argument("--period", type=int, default=5455)
    parser.add_argument("--splits", type=int, default=4)
    parser.add_argument("--contacts", type=int, default=2048)
    parser.add_argument("--ridge", type=float, default=1e-3)
    parser.add_argument("--maxiter", type=int, default=80)
    parser.add_argument(
        "--steps",
        default=(
            "-0.03,-0.01,-0.003,-0.001,-0.0003,-0.0001,-0.00003,-0.00001,"
            "-0.000003,-0.000001,0.000001,0.000003,0.00001,0.00003,0.0001,"
            "0.0003,0.001,0.003,0.01,0.03,0.1,0.3"
        ),
    )
    args = parser.parse_args()

    current = np.maximum(np.load(args.current, allow_pickle=False).astype(np.float64), 0.0)
    previous = np.maximum(np.load(args.previous, allow_pickle=False).astype(np.float64), 0.0)
    if current.shape != previous.shape:
        raise RuntimeError("trajectory arrays must have the same shape")
    # Remove the irrelevant scale component from the historical velocity.
    previous *= np.sum(current) / np.sum(previous)
    velocity = current - previous
    velocity -= current * (np.sum(velocity) / np.sum(current))

    seed_score, convolution = exact_components(current)
    k = min(args.contacts, convolution.size)
    contacts = np.argpartition(convolution, -k)[-k:]
    contacts = contacts[np.argsort(convolution[contacts])[::-1]]
    ids, variable_count = packet_ids(current.size, args.period, args.splits)
    packet_mass = np.bincount(ids, weights=current, minlength=variable_count)

    velocity_convolution = 2.0 * oaconvolve(current, velocity, mode="full")
    contact_rhs_raw = -velocity_convolution[contacts]
    contact_scale = max(float(np.std(contact_rhs_raw)), 1.0)
    sqrt_ridge = float(np.sqrt(args.ridge))
    mass_scale = max(float(np.linalg.norm(packet_mass)), 1.0)

    # Unknown is [packet multipliers, common contact derivative].
    unknown_count = variable_count + 1
    output_count = k + variable_count + 1

    def matvec(unknown: np.ndarray) -> np.ndarray:
        multipliers = unknown[:-1]
        common = unknown[-1]
        delta = current * multipliers[ids]
        delta_convolution = 2.0 * oaconvolve(current, delta, mode="full")
        contacts_part = (delta_convolution[contacts] - common) / contact_scale
        ridge_part = sqrt_ridge * multipliers
        mass_part = np.array([np.dot(packet_mass, multipliers) / mass_scale])
        return np.concatenate((contacts_part, ridge_part, mass_part))

    def rmatvec(output: np.ndarray) -> np.ndarray:
        contact_weights = output[:k] / contact_scale
        impulses = np.zeros(convolution.size, dtype=np.float64)
        impulses[contacts] = contact_weights
        full_gradient = 2.0 * oaconvolve(impulses, current[::-1], mode="valid")
        multiplier_gradient = np.bincount(
            ids, weights=current * full_gradient, minlength=variable_count
        )
        multiplier_gradient += sqrt_ridge * output[k : k + variable_count]
        multiplier_gradient += output[-1] * packet_mass / mass_scale
        common_gradient = -float(np.sum(contact_weights))
        return np.concatenate((multiplier_gradient, [common_gradient]))

    operator = LinearOperator(
        (output_count, unknown_count),
        matvec=matvec,
        rmatvec=rmatvec,
        dtype=np.float64,
    )
    rhs = np.concatenate(
        (contact_rhs_raw / contact_scale, np.zeros(variable_count + 1, dtype=np.float64))
    )
    solution = lsmr(operator, rhs, atol=1e-8, btol=1e-8, maxiter=args.maxiter)
    multipliers = solution[0][:-1]
    correction = current * multipliers[ids]
    direction = velocity + correction
    direction -= current * (np.sum(direction) / np.sum(current))

    projected_convolution = 2.0 * oaconvolve(current, direction, mode="full")
    contact_values = projected_convolution[contacts]
    diagnostics = {
        "seed_score": seed_score,
        "public_score": PUBLIC_SCORE,
        "target_score": TARGET_SCORE,
        "period": args.period,
        "splits": args.splits,
        "variables": variable_count,
        "contacts": k,
        "ridge": args.ridge,
        "lsmr_istop": int(solution[1]),
        "lsmr_iterations": int(solution[2]),
        "lsmr_residual_norm": float(solution[3]),
        "velocity_relative_norm": float(np.linalg.norm(velocity) / np.linalg.norm(current)),
        "direction_relative_norm": float(np.linalg.norm(direction) / np.linalg.norm(current)),
        "raw_contact_std": float(np.std(velocity_convolution[contacts])),
        "projected_contact_std": float(np.std(contact_values)),
        "projected_contact_range": float(np.ptp(contact_values)),
    }
    print(json.dumps(diagnostics, sort_keys=True), flush=True)

    run_dir = ROOT / "runs" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-tangent")
    run_dir.mkdir(parents=True, exist_ok=False)
    atomic_npy(run_dir / "direction.npy", direction)
    best = current.copy()
    best_score = seed_score
    events: list[dict[str, object]] = []
    for step in [float(value) for value in args.steps.split(",")]:
        candidate = np.maximum(current + step * direction, 0.0)
        candidate_score, _ = exact_components(candidate)
        event = {
            "step": step,
            "score": candidate_score,
            "gain": candidate_score - seed_score,
            "nonzero": int(np.count_nonzero(candidate)),
        }
        events.append(event)
        print(json.dumps(event, sort_keys=True), flush=True)
        if candidate_score > best_score:
            best = candidate
            best_score = candidate_score
            atomic_npy(run_dir / "best.npy", best)

    if not (run_dir / "best.npy").exists():
        atomic_npy(run_dir / "best.npy", best)
    payload_hash = hashlib.sha256(best.tobytes()).hexdigest()
    summary = {
        **diagnostics,
        "best_score": best_score,
        "gain": best_score - seed_score,
        "gate_cleared": best_score >= TARGET_SCORE,
        "gap_to_target": TARGET_SCORE - best_score,
        "best_values_sha256": payload_hash,
        "verifier_sha256": VERIFIER_SHA256,
        "events": events,
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
