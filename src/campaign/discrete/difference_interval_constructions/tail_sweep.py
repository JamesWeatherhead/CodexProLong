#!/usr/bin/env python3
"""Exhaust the positive-k tail copies in the Theorem-4.7 construction."""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np

import search


HERE = Path(__file__).resolve().parent


def best_affine_windows(
    residues: list[int], modulus: int, maximum_extra: int
) -> list[dict[str, int]]:
    """Maximize each arc containing exactly k residues, for k=0..maximum."""
    base = np.asarray(residues, dtype=np.int64)
    count = len(residues)
    best = [
        {
            "extra": extra,
            "arc": -1,
            "multiplier": -1,
            "boundary_index": -1,
            "boundary_residue": -1,
        }
        for extra in range(maximum_extra + 1)
    ]
    for multiplier in range(1, modulus):
        if math.gcd(multiplier, modulus) != 1:
            continue
        scaled = np.sort((base * multiplier) % modulus)
        gaps = np.diff(np.concatenate((scaled, scaled[:1] + modulus)))
        doubled = np.concatenate((gaps, gaps))
        cumulative = np.concatenate(([0], np.cumsum(doubled, dtype=np.int64)))
        for extra, record in enumerate(best):
            width = extra + 1
            sums = cumulative[width : width + count] - cumulative[:count]
            index = int(np.argmax(sums))
            arc = int(sums[index])
            if arc > record["arc"]:
                record.update(
                    arc=arc,
                    multiplier=multiplier,
                    boundary_index=index,
                    boundary_residue=int(scaled[index]),
                )
    return best


def tail_candidate(
    residues: list[int], modulus: int, window: dict[str, int]
) -> tuple[list[int], list[int]]:
    multiplier = window["multiplier"]
    boundary = window["boundary_residue"]
    scaled = sorted((multiplier * value) % modulus for value in residues)
    representatives = sorted(((value - boundary) % modulus) or modulus for value in scaled)
    delta = window["arc"] - 1
    early = [value for value in representatives if value <= delta]
    if len(early) != window["extra"]:
        raise RuntimeError(
            f"expected {window['extra']} early residues, recovered {len(early)}"
        )
    values = {
        representative + modulus * height
        for representative in representatives
        for height in search.HEIGHTS
    }
    values.update(value + 7 * modulus for value in early)
    origin = min(values)
    return sorted(value - origin for value in values), early


def scan(q: int, maximum_extra: int) -> dict[str, Any]:
    started = time.monotonic()
    residues, polynomial_a, polynomial_b = search.generate_singer(q)
    modulus = q * q + q + 1
    maximum_extra = min(maximum_extra, q, 2000 - 4 * (q + 1))
    windows = best_affine_windows(residues, modulus, maximum_extra)
    records = []
    for window in windows:
        candidate, early = tail_candidate(residues, modulus, window)
        coverage, score = search.literal_evaluate(candidate)
        predicted_floor = 6 * modulus + window["arc"] - 1
        if coverage < predicted_floor:
            raise RuntimeError(
                f"q={q} k={window['extra']}: {coverage} < {predicted_floor}"
            )
        records.append(
            {
                **window,
                "delta": window["arc"] - 1,
                "early_residues": early,
                "cardinality": len(candidate),
                "coverage": coverage,
                "predicted_floor": predicted_floor,
                "score": score,
                "gap_to_gate": score - search.TARGET,
                "candidate_sha256": search.canonical_sha256(candidate),
                "gate_clearing": score < search.TARGET,
            }
        )
    return {
        "q": q,
        "modulus": modulus,
        "polynomial_a": polynomial_a,
        "polynomial_b": polynomial_b,
        "residue_sha256": search.canonical_sha256(residues),
        "maximum_extra": maximum_extra,
        "records": records,
        "best": min(records, key=lambda item: item["score"]),
        "elapsed_seconds": time.monotonic() - started,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--q", default="53,61,89,97,103,151")
    parser.add_argument("--maximum-extra", type=int, default=20)
    parser.add_argument("--checkpoint", type=Path, default=HERE / "tail_checkpoint.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    q_values = search.parse_q_values(args.q)
    output: dict[str, Any] = {
        "method": "Theorem-4.7 exhaustive affine delta_k tail-copy sweep",
        "scope": {
            "q_requested": q_values,
            "q_completed": [],
            "maximum_extra_requested": args.maximum_extra,
            "prime_orders_only": True,
            "height_basis": list(search.HEIGHTS),
        },
        "live": {
            "leader": search.LEADER,
            "min_improvement": search.MIN_IMPROVEMENT,
            "target_strictly_below": search.TARGET,
            "verifier_sha256": search.VERIFIER_SHA256,
        },
        "q_records": [],
        "best": None,
        "gate_clearing": False,
    }
    started = time.monotonic()
    for q in q_values:
        q_record = scan(q, args.maximum_extra)
        output["q_records"].append(q_record)
        output["scope"]["q_completed"].append(q)
        candidates = [
            record
            for item in output["q_records"]
            for record in item["records"]
        ]
        best = min(candidates, key=lambda item: item["score"])
        output["best"] = best
        output["gate_clearing"] = bool(best["gate_clearing"])
        output["elapsed_seconds"] = time.monotonic() - started
        search.atomic_json(args.checkpoint, output)
        print(
            f"q={q} best-k={q_record['best']['extra']} "
            f"score={q_record['best']['score']:.15g} "
            f"coverage={q_record['best']['coverage']}",
            flush=True,
        )
        if output["gate_clearing"]:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
