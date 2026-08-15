#!/usr/bin/env python3
"""Exact comb-frontier packet-birth coordinate search for C2.

Each move copies one coherent 5,455-cell comb packet into currently inactive
cells at a support frontier.  This is deliberately distinct from individual
run shifts and from a full-vector gradient polish.  Every accepted move is
rescored by SciPy float64 and checkpointed atomically.
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


ROOT = Path(__file__).resolve().parent
VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
PUBLIC_SCORE = 0.963588110582029
TARGET_SCORE = 0.963598110582029


def exact_score(values: np.ndarray) -> float:
    values = np.maximum(np.asarray(values, dtype=np.float64), 0.0)
    convolution = oaconvolve(values, values, mode="full")
    numerator = (
        2.0 * np.dot(convolution, convolution)
        + np.dot(convolution[:-1], convolution[1:])
    ) / 3.0
    return float(numerator / (np.sum(values) ** 2 * np.max(convolution)))


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


def packet_template(
    values: np.ndarray, period: int, source_row: int, target_row: int
) -> np.ndarray:
    n = values.size
    source_low = source_row * period
    source_high = min(source_low + period, n)
    target_low = target_row * period
    target_high = min(target_low + source_high - source_low, n)
    template = np.zeros_like(values)
    source = values[source_low : source_low + target_high - target_low]
    inactive = values[target_low:target_high] == 0.0
    template[target_low:target_high][inactive] = source[inactive]
    return template


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(
            "/Users/jacweath/EinsteinArena/campaign/c2_root/runs/"
            "20260814T231424Z-support/best.npy"
        ),
    )
    parser.add_argument("--period", type=int, default=5455)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--depth", type=int, default=10)
    parser.add_argument(
        "--alphas",
        default=(
            "1e-8,3e-8,1e-7,3e-7,1e-6,3e-6,1e-5,3e-5,1e-4,3e-4,"
            "1e-3,3e-3,1e-2,3e-2,1e-1,3e-1,5e-1,7.5e-1,1,1.25,1.5,2,3"
        ),
    )
    args = parser.parse_args()

    best = np.maximum(np.load(args.input, allow_pickle=False).astype(np.float64), 0.0)
    seed_score = exact_score(best)
    best_score = seed_score
    alpha_values = [float(value) for value in args.alphas.split(",")]
    # Main-ramp frontier and the opposite edge of the large dead band.
    moves = [(source, 245) for source in range(237, 245)]
    moves += [(source, 328) for source in range(329, 337)]
    # Propagate only after a coherent frontier packet exists.  Each successive
    # move is one whole-period birth, so the fine comb phase is preserved.
    moves += [(row, row + 1) for row in range(245, 245 + args.depth)]
    moves += [(row, row - 1) for row in range(328, 328 - args.depth, -1)]

    run_dir = ROOT / "runs" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-birth")
    run_dir.mkdir(parents=True, exist_ok=False)
    atomic_npy(run_dir / "seed.npy", best)
    atomic_npy(run_dir / "best.npy", best)
    events_path = run_dir / "events.jsonl"
    accepted_moves: list[dict[str, object]] = []

    with events_path.open("a", encoding="utf-8") as events:
        for pass_index in range(args.passes):
            accepted_this_pass = 0
            for source_row, target_row in moves:
                template = packet_template(best, args.period, source_row, target_row)
                template_mass = float(np.sum(template))
                move_score = best_score
                move_alpha = 0.0
                move_values: np.ndarray | None = None
                if template_mass > 0.0:
                    for alpha in alpha_values:
                        candidate = best + alpha * template
                        candidate_score = exact_score(candidate)
                        if candidate_score > move_score:
                            move_score = candidate_score
                            move_alpha = alpha
                            move_values = candidate
                accepted = move_values is not None
                if accepted:
                    best = move_values
                    best_score = move_score
                    accepted_this_pass += 1
                    atomic_npy(run_dir / "best.npy", best)
                    accepted_moves.append(
                        {
                            "pass": pass_index,
                            "source_row": source_row,
                            "target_row": target_row,
                            "alpha": move_alpha,
                            "score": best_score,
                        }
                    )
                event = {
                    "pass": pass_index,
                    "source_row": source_row,
                    "target_row": target_row,
                    "template_mass": template_mass,
                    "accepted": accepted,
                    "alpha": move_alpha,
                    "score": best_score,
                    "gain_from_seed": best_score - seed_score,
                }
                events.write(json.dumps(event, sort_keys=True) + "\n")
                events.flush()
                print(json.dumps(event, sort_keys=True), flush=True)
            if accepted_this_pass == 0:
                break

    replay_score = exact_score(np.load(run_dir / "best.npy", allow_pickle=False))
    if replay_score != best_score:
        raise RuntimeError(f"checkpoint replay mismatch: {replay_score} != {best_score}")
    best_hash = hashlib.sha256(best.tobytes()).hexdigest()
    summary = {
        "input": str(args.input.resolve()),
        "seed_score": seed_score,
        "best_score": best_score,
        "replay_score": replay_score,
        "gain_from_seed": best_score - seed_score,
        "gain_from_public": best_score - PUBLIC_SCORE,
        "target_score": TARGET_SCORE,
        "gap_to_target": TARGET_SCORE - best_score,
        "gate_cleared": best_score >= TARGET_SCORE,
        "n": int(best.size),
        "nonzero": int(np.count_nonzero(best)),
        "accepted_moves": accepted_moves,
        "values_sha256": best_hash,
        "verifier_sha256": VERIFIER_SHA256,
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
