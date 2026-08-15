#!/usr/bin/env python3
"""Exact-replay support-growth harvester for a kinked C2 incumbent."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.signal import oaconvolve


ROOT = Path(__file__).resolve().parent


def components(f: np.ndarray) -> tuple[float, np.ndarray, float, float, float]:
    convolution = oaconvolve(f, f, mode="full")
    maximum = float(np.max(convolution))
    numerator = float(
        (
            2.0 * np.dot(convolution, convolution)
            + np.dot(convolution[:-1], convolution[1:])
        )
        / 3.0
    )
    mass = float(np.sum(f))
    return numerator / (mass * mass * maximum), convolution, numerator, mass, maximum


def score(f: np.ndarray) -> float:
    return components(f)[0]


def atomic_npy(path: Path, values: np.ndarray) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, values, allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "leader.npy")
    parser.add_argument("--rounds", type=int, default=60)
    parser.add_argument("--top-k", type=int, default=100)
    parser.add_argument("--beta", type=float, default=1e8)
    parser.add_argument(
        "--epsilons",
        default="1e-6,3e-6,1e-5,3e-5,1e-4,3e-4,1e-3",
    )
    args = parser.parse_args()

    epsilons = [float(value) for value in args.epsilons.split(",")]
    best = np.maximum(np.load(args.input, allow_pickle=False).astype(np.float64), 0.0)
    best_score = score(best)
    seed_score = best_score
    run_dir = ROOT / "runs" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-support")
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    atomic_npy(run_dir / "seed.npy", best)
    atomic_npy(run_dir / "best.npy", best)

    with events_path.open("a", encoding="utf-8") as events:
        for iteration in range(args.rounds):
            current_score, conv, numerator, mass, maximum = components(best)
            h_numerator = 4.0 * conv / (3.0 * numerator)
            h_numerator[:-1] += conv[1:] / (3.0 * numerator)
            h_numerator[1:] += conv[:-1] / (3.0 * numerator)
            logits = args.beta * (conv / maximum - 1.0)
            logits -= np.max(logits)
            dual = np.exp(logits)
            dual /= np.sum(dual)
            gradient = (
                2.0 * oaconvolve(h_numerator - dual / maximum, best[::-1], mode="valid")
                - 2.0 / mass
            )
            zero_indices = np.flatnonzero(best == 0.0)
            if not zero_indices.size:
                break
            order = np.argpartition(gradient[zero_indices], -args.top_k)[-args.top_k :]
            selected = zero_indices[order]

            round_best_score = current_score
            round_best: np.ndarray | None = None
            round_epsilon: float | None = None
            for epsilon in epsilons:
                candidate = best.copy()
                candidate[selected] = epsilon
                candidate_score = score(candidate)
                if candidate_score > round_best_score:
                    round_best_score = candidate_score
                    round_best = candidate
                    round_epsilon = epsilon

            accepted = round_best is not None
            if accepted:
                best = round_best
                best_score = round_best_score
                atomic_npy(run_dir / "best.npy", best)
            event = {
                "iteration": iteration,
                "accepted": accepted,
                "epsilon": round_epsilon,
                "score": best_score,
                "gain_from_seed": best_score - seed_score,
                "zero_count": int(np.count_nonzero(best == 0.0)),
                "dual_effective_size": float(1.0 / np.dot(dual, dual)),
                "selected_gradient_min": float(np.min(gradient[selected])),
                "selected_gradient_max": float(np.max(gradient[selected])),
            }
            events.write(json.dumps(event, sort_keys=True) + "\n")
            events.flush()
            print(json.dumps(event, sort_keys=True), flush=True)
            if not accepted:
                break

    summary = {
        "seed_score": seed_score,
        "best_score": best_score,
        "gain": best_score - seed_score,
        "target_score": seed_score + 1e-5,
        "gate_cleared": best_score >= seed_score + 1e-5,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

