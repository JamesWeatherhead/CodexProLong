#!/usr/bin/env python3
"""Checkpointed exact-grid Hamming-ball audit of the live flat leader."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterator

import numpy as np


ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "checkpoints" / "flat-polynomials-live.json"
CHECKPOINT = ROOT / "checkpoints" / "flat-search.json"
BEST = ROOT / "candidates" / "flat-best.json"
NUM_POINTS = 1_000_000


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True).encode())
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_live() -> tuple[dict[str, Any], str, Callable[[dict[str, Any]], float]]:
    snapshot = json.loads(LIVE.read_text(encoding="utf-8"))
    problem = snapshot["problem"]
    verifier = problem["verifier"]
    digest = hashlib.sha256(verifier.encode()).hexdigest()
    leader = snapshot["solutions"][0]
    namespace: dict[str, Any] = {}
    exec(compile(verifier, "live_flat_verifier.py", "exec"), namespace)
    return leader, digest, namespace["evaluate"]


def batches(iterator: Iterator[tuple[int, ...]], size: int) -> Iterator[list[tuple[int, ...]]]:
    while True:
        batch = list(itertools.islice(iterator, size))
        if not batch:
            return
        yield batch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-radius", type=int, default=4)
    parser.add_argument("--grid", type=int, default=512)
    parser.add_argument("--chunk", type=int, default=2048)
    parser.add_argument("--checkpoint-every", type=int, default=20)
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_radius <= 6:
        raise SystemExit("--max-radius must be in 1..6")
    if not 64 <= args.grid <= 16384 or not 32 <= args.chunk <= 16384:
        raise SystemExit("grid/chunk outside supported bounds")

    leader, verifier_hash, live_evaluate = load_live()
    coefficients = np.asarray(leader["data"]["coefficients"], dtype=np.float64)
    payload = {"coefficients": coefficients.astype(int).tolist()}
    leader_hash = hashlib.sha256(canonical(payload)).hexdigest()
    live_score = float(live_evaluate(payload))
    if live_score != float(leader["score"]):
        raise RuntimeError("pinned live verifier does not reproduce the leader score")

    state: dict[str, Any] = {
        "schema": 1,
        "verifier_sha256": verifier_hash,
        "leader_payload_sha256": leader_hash,
        "leader_score": live_score,
        "grid": args.grid,
        "chunk": args.chunk,
        "max_radius": args.max_radius,
        "processed": {str(radius): 0 for radius in range(1, args.max_radius + 1)},
        "survivors": 0,
        "exact_evaluations": 0,
        "best_exact": None,
        "best_grid_lower_bound": None,
        "complete": False,
    }
    if CHECKPOINT.exists() and not args.restart:
        previous = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        for key in (
            "verifier_sha256",
            "leader_payload_sha256",
            "grid",
            "chunk",
            "max_radius",
        ):
            if previous.get(key) != state[key]:
                raise RuntimeError(f"checkpoint {key} does not match this run")
        state.update(previous)
        if state["complete"]:
            print(json.dumps(state, indent=2, sort_keys=True))
            return

    # These are exact indices from the live verifier's million-point grid, so
    # every sampled maximum is a rigorous lower bound on the live score.
    sample_indices = np.floor(
        np.arange(args.grid, dtype=np.float64) * (NUM_POINTS - 1) / args.grid
    ).astype(np.int64)
    angles = 2 * np.pi * sample_indices / (NUM_POINTS - 1)
    z = np.exp(1j * angles)
    powers = np.arange(len(coefficients) - 1, -1, -1)
    basis = z[None, :] ** powers[:, None]
    base_values = coefficients @ basis
    normalization = math.sqrt(len(coefficients) + 1)
    gate_score = live_score - 1e-6

    best_payload = json.loads(BEST.read_text()) if BEST.exists() else None
    for radius in range(1, args.max_radius + 1):
        total = math.comb(len(coefficients), radius)
        already = int(state["processed"].get(str(radius), 0))
        if already >= total:
            continue
        combinations = itertools.islice(
            itertools.combinations(range(len(coefficients)), radius), already, None
        )
        for batch_index, batch in enumerate(batches(combinations, args.chunk), start=1):
            masks = np.zeros((len(batch), len(coefficients)), dtype=np.float64)
            for row, flipped in enumerate(batch):
                masks[row, list(flipped)] = coefficients[list(flipped)]
            values = base_values[None, :] - 2.0 * (masks @ basis)
            lower_bounds = np.max(np.abs(values), axis=1) / normalization
            local_min = float(np.min(lower_bounds))
            if state["best_grid_lower_bound"] is None or local_min < state["best_grid_lower_bound"]:
                state["best_grid_lower_bound"] = local_min

            promising = np.flatnonzero(lower_bounds < gate_score + 1e-10)
            state["survivors"] += int(len(promising))
            for row in promising:
                candidate = coefficients.copy()
                candidate[list(batch[int(row)])] *= -1
                candidate_payload = {"coefficients": candidate.astype(int).tolist()}
                exact = float(live_evaluate(candidate_payload))
                state["exact_evaluations"] += 1
                record = {
                    "radius": radius,
                    "flips": list(batch[int(row)]),
                    "grid_lower_bound": float(lower_bounds[int(row)]),
                    "score": exact,
                }
                if state["best_exact"] is None or exact < state["best_exact"]["score"]:
                    state["best_exact"] = record
                    best_payload = candidate_payload
                    atomic_json(BEST, candidate_payload)

            state["processed"][str(radius)] += len(batch)
            if batch_index % args.checkpoint_every == 0:
                atomic_json(CHECKPOINT, state)
        atomic_json(CHECKPOINT, state)

    state["gate_score"] = gate_score
    state["gate_cleared"] = bool(
        state["best_exact"] and state["best_exact"]["score"] < gate_score
    )
    state["complete"] = True
    atomic_json(CHECKPOINT, state)
    print(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
