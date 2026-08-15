#!/usr/bin/env python3
"""Changed-shape flat-polynomial search outside the closed radius-five ball."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.spatial import cKDTree


ROOT = Path(__file__).resolve().parent
LIVE = ROOT.parent / "checkpoints" / "flat-polynomials-live.json"
CHECKPOINT = ROOT / "checkpoints" / "structured_search.json"
BEST_SURVIVOR = ROOT / "best_screen_survivor.json"
GATE_CANDIDATE = ROOT / "gate_candidate.json"
UNIQUE_GRID = 999_999


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
    verifier = snapshot["problem"]["verifier"]
    namespace: dict[str, Any] = {}
    exec(compile(verifier, "live_flat_polynomial_verifier.py", "exec"), namespace)
    return (
        snapshot["solutions"][0],
        hashlib.sha256(verifier.encode()).hexdigest(),
        namespace["evaluate"],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--chunk", type=int, default=1024)
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--mitm-neighbors", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    leader, verifier_hash, live_evaluate = load_live()
    coefficients = np.asarray(leader["data"]["coefficients"], dtype=np.float64)
    leader_payload = {"coefficients": coefficients.astype(int).tolist()}
    leader_hash = hashlib.sha256(canonical(leader_payload)).hexdigest()
    leader_score = float(live_evaluate(leader_payload))
    gate_score = leader_score - 1e-6
    if leader_score != float(leader["score"]):
        raise RuntimeError("pinned verifier does not reproduce the live leader")

    candidates: set[tuple[int, ...]] = set()
    family_stats: dict[str, dict[str, int]] = {}

    def add_family(name: str, iterable: Any) -> None:
        attempted = 0
        before = len(candidates)
        for raw in iterable:
            attempted += 1
            flips = tuple(sorted(set(map(int, raw))))
            # Radius <=5 is already exhaustively closed.  Global sign is an
            # exact symmetry and cannot clear a strict improvement gate.
            if 5 < len(flips) < len(coefficients):
                candidates.add(flips)
        family_stats[name] = {
            "attempted": attempted,
            "new_unique": len(candidates) - before,
        }

    # Run-boundary segments and two-segment symmetric differences.
    boundaries = [0]
    boundaries.extend(
        index
        for index in range(1, len(coefficients))
        if coefficients[index] != coefficients[index - 1]
    )
    boundaries.append(len(coefficients))
    run_segments = [
        tuple(range(left, right))
        for left_index, left in enumerate(boundaries[:-1])
        for right in boundaries[left_index + 1 :]
        if right - left > 5
    ]
    add_family("run_segments", run_segments)
    add_family(
        "paired_run_boundaries",
        (
            set(first) ^ set(second)
            for first_index, first in enumerate(run_segments[:-1])
            for second in run_segments[first_index + 1 :]
        ),
    )

    # Crossovers with the previous near-optimal public sequence.
    previous = np.asarray(leader_payload["coefficients"], dtype=np.int8)
    for row in json.loads(LIVE.read_text(encoding="utf-8"))["solutions"][1:]:
        candidate_coefficients = row["data"].get("coefficients")
        if candidate_coefficients is not None and len(candidate_coefficients) == 70:
            previous = np.asarray(candidate_coefficients, dtype=np.int8)
            break
    differing = set(np.flatnonzero(previous != coefficients).tolist())
    add_family(
        "near_leader_run_crossovers",
        (differing & set(segment) for segment in run_segments),
    )
    add_family(
        "near_leader_paired_crossovers",
        (
            differing & (set(first) ^ set(second))
            for first_index, first in enumerate(run_segments[:-1])
            for second in run_segments[first_index + 1 :]
        ),
    )

    # Cyclotomic/congruence masks: all nontrivial unions of residue classes.
    def residue_masks() -> Any:
        for modulus in range(2, 14):
            for residue_mask in range(1, (1 << modulus) - 1):
                yield (
                    index
                    for index in range(len(coefficients))
                    if residue_mask & (1 << (index % modulus))
                )

    add_family("cyclotomic_residue_masks", residue_masks())

    # Lag chains are arithmetic-progression analogues of run-boundary moves.
    def lag_chains() -> Any:
        for lag in range(2, 24):
            for residue in range(lag):
                chain = list(range(residue, len(coefficients), lag))
                for start in range(len(chain)):
                    for stop in range(start + 6, len(chain) + 1):
                        yield chain[start:stop]

    add_family("lag_chain_segments", lag_chains())

    # Correlation-sign endpoint masks at every lag.
    def lag_endpoint_masks() -> Any:
        for lag in range(1, len(coefficients)):
            products = coefficients[:-lag] * coefficients[lag:]
            for sign in (-1.0, 1.0):
                starts = np.flatnonzero(products == sign)
                yield starts
                yield np.unique(np.concatenate((starts, starts + lag)))
                yield starts + lag

    add_family("lag_correlation_masks", lag_endpoint_masks())

    # Meet in the middle at radius six.  Pair triples whose complex changes
    # cancel (or gently reduce the incumbent) at exact points around its peak.
    exponents = np.arange(len(coefficients) - 1, -1, -1)
    unique_values = np.zeros(UNIQUE_GRID, dtype=np.float64)
    unique_values[: len(coefficients)] = coefficients[::-1]
    leader_curve = UNIQUE_GRID * np.fft.ifft(unique_values)
    peak = int(np.argmax(np.abs(leader_curve)))
    fit_indices = np.asarray(
        sorted(
            {
                (peak + delta) % UNIQUE_GRID
                for delta in (-3000, -1500, -750, -300, 0, 300, 750, 1500, 3000)
            }
        ),
        dtype=np.int64,
    )
    fit_z = np.exp(2j * np.pi * fit_indices / UNIQUE_GRID)
    contribution = (
        coefficients[:, None] * fit_z[None, :] ** exponents[:, None]
    )
    triples = np.asarray(
        list(itertools.combinations(range(len(coefficients)), 3)), dtype=np.int16
    )
    triple_values = contribution[triples].sum(axis=1)
    scale = np.std(
        np.concatenate((triple_values.real, triple_values.imag), axis=0), axis=0
    )
    scale[scale == 0] = 1.0
    features = np.concatenate(
        (triple_values.real / scale, triple_values.imag / scale), axis=1
    )
    tree = cKDTree(features)
    base_fit = coefficients @ (fit_z[None, :] ** exponents[:, None])

    mitm: set[tuple[int, ...]] = set()
    for fraction in (0.0, 0.005, 0.01, 0.025, 0.05, 0.1):
        target = fraction * base_fit[None, :] - triple_values
        queries = np.concatenate(
            (target.real / scale, target.imag / scale), axis=1
        )
        _, neighbors = tree.query(
            queries, k=args.mitm_neighbors, workers=-1
        )
        if neighbors.ndim == 1:
            neighbors = neighbors[:, None]
        for first_index, neighbor_rows in enumerate(neighbors):
            first = set(map(int, triples[first_index]))
            for second_index in neighbor_rows:
                second = tuple(map(int, triples[int(second_index)]))
                if first.isdisjoint(second):
                    mitm.add(tuple(sorted((*first, *second))))
    add_family("lag_correlated_mitm_radius6", mitm)

    ordered_candidates = sorted(candidates)
    config = {
        "chunk": args.chunk,
        "mitm_neighbors": args.mitm_neighbors,
        "candidate_count": len(ordered_candidates),
        "family_stats": family_stats,
    }
    state: dict[str, Any] = {
        "schema": 1,
        "verifier_sha256": verifier_hash,
        "leader_payload_sha256": leader_hash,
        "leader_id": leader["id"],
        "leader_score": leader_score,
        "gate_score": gate_score,
        "config": config,
        "processed": 0,
        "literal_grid_survivors": 0,
        "exact_replays": 0,
        "exact_records": [],
        "top_literal_lower_bounds": [],
        "best_literal_lower_bound": None,
        "best_exact": None,
        "complete": False,
    }
    if CHECKPOINT.exists() and not args.restart:
        prior = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        for key in ("verifier_sha256", "leader_payload_sha256", "config"):
            if prior.get(key) != state[key]:
                raise RuntimeError(f"checkpoint {key} differs from this run")
        state.update(prior)
        if state["complete"]:
            print(json.dumps(state, indent=2, sort_keys=True))
            return

    # All indices below are literal points from the verifier's 999,999 unique
    # roots.  Their maximum is therefore a rigorous lower bound on full replay.
    literal_indices = set(
        np.floor(np.arange(512) * (UNIQUE_GRID - 1) / 512).astype(int).tolist()
    )
    for center in (peak, (-peak) % UNIQUE_GRID):
        literal_indices.update(
            (center + delta) % UNIQUE_GRID for delta in range(-6000, 6001, 50)
        )
    literal_indices_array = np.asarray(sorted(literal_indices), dtype=np.int64)
    literal_z = np.exp(2j * np.pi * literal_indices_array / UNIQUE_GRID)
    basis = literal_z[None, :] ** exponents[:, None]
    base_values = coefficients @ basis
    normalization = math.sqrt(len(coefficients) + 1)

    start = int(state["processed"])
    for batch_index, batch_start in enumerate(
        range(start, len(ordered_candidates), args.chunk), start=1
    ):
        batch = ordered_candidates[batch_start : batch_start + args.chunk]
        masks = np.zeros((len(batch), len(coefficients)), dtype=np.float64)
        for row, flips in enumerate(batch):
            masks[row, list(flips)] = coefficients[list(flips)]
        values = base_values[None, :] - 2.0 * (masks @ basis)
        lower_bounds = np.max(np.abs(values), axis=1) / normalization
        local_best = float(np.min(lower_bounds))
        if (
            state["best_literal_lower_bound"] is None
            or local_best < state["best_literal_lower_bound"]["value"]
        ):
            local_index = int(np.argmin(lower_bounds))
            state["best_literal_lower_bound"] = {
                "value": local_best,
                "flips": list(batch[local_index]),
                "radius": len(batch[local_index]),
            }
        local_top_count = min(25, len(batch))
        local_top = np.argpartition(lower_bounds, local_top_count - 1)[
            :local_top_count
        ]
        merged_top = list(state["top_literal_lower_bounds"])
        merged_top.extend(
            {
                "value": float(lower_bounds[int(row)]),
                "flips": list(batch[int(row)]),
                "radius": len(batch[int(row)]),
            }
            for row in local_top
        )
        merged_top.sort(key=lambda record: record["value"])
        state["top_literal_lower_bounds"] = merged_top[:50]
        survivors = np.flatnonzero(lower_bounds < gate_score)
        state["literal_grid_survivors"] += len(survivors)
        for row in survivors:
            flips = batch[int(row)]
            candidate = coefficients.copy()
            candidate[list(flips)] *= -1
            payload = {"coefficients": candidate.astype(int).tolist()}
            exact = float(live_evaluate(payload))
            state["exact_replays"] += 1
            record = {
                "score": exact,
                "literal_grid_lower_bound": float(lower_bounds[int(row)]),
                "flips": list(flips),
                "radius": len(flips),
            }
            state["exact_records"].append(record)
            if state["best_exact"] is None or exact < state["best_exact"]["score"]:
                state["best_exact"] = record
                atomic_json(BEST_SURVIVOR, payload)
            if exact < gate_score:
                atomic_json(GATE_CANDIDATE, payload)
        state["processed"] = batch_start + len(batch)
        if batch_index % args.checkpoint_every == 0:
            atomic_json(CHECKPOINT, state)

    state["gate_cleared"] = bool(
        state["best_exact"] and state["best_exact"]["score"] < gate_score
    )
    state["complete"] = True
    atomic_json(CHECKPOINT, state)
    print(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
