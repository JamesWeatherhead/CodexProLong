#!/usr/bin/env python3
"""Verifier-exact finite-mass terminal-cluster split search for C2.

The live construction has a 70.85% graded main component, a long void, and a
29.15% terminal spike/comb component. This search makes a discontinuous macro
topology change: a finite fraction of the entire terminal component is moved
into the void as either a translated coherent copy or a mirrored coherent
copy. Terminal mass is preserved exactly. This is distinct from exhausted
cell/packet-birth continuation.
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
DEFAULT_INPUT = ROOT.parent / "c2_secondary/runs/20260815T004948Z-birth/best.npy"
PUBLIC_SCORE = 0.963588110582029
STRICT_GATE = 0.963598110582029
VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
TERMINAL_START = 1_737_964


def literal_live_score(values: np.ndarray) -> float:
    f = np.array(values, dtype=np.float64)
    n_points = len(values)
    if f.shape != (n_points,):
        raise ValueError(f"Expected shape ({n_points},), got {f.shape}")
    if np.any(f < -1e-6):
        raise ValueError("Function must be non-negative.")
    f_nonneg = np.maximum(f, 0.0)
    if np.sum(f_nonneg) == 0:
        raise ValueError("Function must have positive integral.")
    convolution = oaconvolve(f_nonneg, f_nonneg, mode="full")
    num_conv_points = len(convolution)
    x_points = np.linspace(-0.5, 0.5, num_conv_points + 2)
    x_intervals = np.diff(x_points)
    y_points = np.concatenate(([0], convolution, [0]))
    y1 = y_points[:-1]
    y2 = y_points[1:]
    l2_norm_squared = float(
        np.sum((x_intervals / 3) * (y1**2 + y1 * y2 + y2**2))
    )
    norm_1 = np.sum(np.abs(convolution)) / (num_conv_points + 1)
    norm_inf = np.max(np.abs(convolution))
    return float(l2_norm_squared / (norm_1 * norm_inf))


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


def translate_without_wrap(values: np.ndarray, shift: int) -> np.ndarray:
    result = np.zeros_like(values)
    if shift < 0:
        result[:shift] = values[-shift:]
    elif shift > 0:
        result[shift:] = values[:-shift]
    else:
        result[:] = values
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--stamp")
    args = parser.parse_args()

    seed = np.maximum(np.load(args.input, allow_pickle=False).astype(np.float64), 0.0)
    if seed.ndim != 1 or seed.size > 2_000_000 or not np.isfinite(seed).all():
        raise ValueError("invalid seed")
    if TERMINAL_START >= seed.size:
        raise ValueError("terminal split lies outside seed")

    main_component = seed.copy()
    terminal = np.zeros_like(seed)
    terminal[TERMINAL_START:] = main_component[TERMINAL_START:]
    main_component[TERMINAL_START:] = 0.0
    terminal_mirrored = np.zeros_like(seed)
    terminal_mirrored[TERMINAL_START:] = terminal[TERMINAL_START:][::-1]

    seed_score = literal_live_score(seed)
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_npy(run_dir / "seed.npy", seed)
    atomic_npy(run_dir / "best.npy", seed)

    best = seed.copy()
    best_score = seed_score
    best_spec: dict[str, object] = {"family": "seed", "shift": 0, "fraction": 0.0}
    evaluations = 0
    family_best: dict[str, dict[str, object]] = {}

    shifts = (-340_000, -300_000, -260_000, -220_000, -180_000,
              -140_000, -100_000, -60_000, -20_000)
    fractions = (1e-8, 3e-8, 1e-7, 3e-7, 1e-6, 3e-6, 1e-5,
                 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 2e-2,
                 5e-2, 1e-1, 2e-1, 3.5e-1, 5e-1, 7e-1, 9e-1)

    for family, source in (("translated", terminal), ("mirrored", terminal_mirrored)):
        family_record: dict[str, object] = {
            "score": -1.0,
            "shift": 0,
            "fraction": 0.0,
        }
        for shift in shifts:
            copy = translate_without_wrap(source, shift)
            if not np.isclose(copy.sum(), terminal.sum(), rtol=0.0, atol=1e-8):
                raise RuntimeError("macro-copy translation truncated mass")
            for fraction in fractions:
                candidate = main_component + (1.0 - fraction) * terminal + fraction * copy
                score = literal_live_score(candidate)
                evaluations += 1
                accepted = score > best_score
                if score > float(family_record["score"]):
                    family_record = {
                        "score": score,
                        "shift": shift,
                        "fraction": fraction,
                    }
                if accepted:
                    best = candidate
                    best_score = score
                    best_spec = {
                        "family": family,
                        "shift": shift,
                        "fraction": fraction,
                    }
                    atomic_npy(run_dir / "best.npy", best)
                append_event(
                    events,
                    {
                        "event": "evaluate",
                        "evaluation": evaluations,
                        "family": family,
                        "shift": shift,
                        "fraction": fraction,
                        "score": score,
                        "gain_from_seed": score - seed_score,
                        "accepted": accepted,
                    },
                )
        family_best[family] = family_record
        print(json.dumps({"family": family, "best": family_record}, sort_keys=True), flush=True)

    replay = literal_live_score(np.load(run_dir / "best.npy", allow_pickle=False))
    if replay != best_score:
        raise RuntimeError(f"exact replay mismatch: {replay} != {best_score}")
    summary = {
        "mode": "finite-mass terminal spike/comb split",
        "input": str(args.input.resolve()),
        "n": int(seed.size),
        "terminal_start": TERMINAL_START,
        "terminal_mass_fraction": float(terminal.sum() / seed.sum()),
        "seed_score": seed_score,
        "best_score": best_score,
        "gain_from_seed": best_score - seed_score,
        "gain_from_public": best_score - PUBLIC_SCORE,
        "strict_gate": STRICT_GATE,
        "gap_to_gate": STRICT_GATE - best_score,
        "gate_cleared": bool(best_score >= STRICT_GATE),
        "evaluations": evaluations,
        "best_spec": best_spec,
        "family_best": family_best,
        "payload": str((run_dir / "best.npy").resolve()),
        "values_sha256": hashlib.sha256(best.tobytes()).hexdigest(),
        "verifier_sha256": VERIFIER_SHA256,
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, {"event": "complete", "summary": summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
