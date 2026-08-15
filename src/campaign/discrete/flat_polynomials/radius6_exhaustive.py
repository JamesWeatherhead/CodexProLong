#!/usr/bin/env python3
"""Checkpointed exhaustive literal-verifier-grid screen at Hamming radius six."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
LIVE = ROOT.parent / "checkpoints" / "flat-polynomials-live.json"
SOURCE = ROOT / "radius6.cpp"
BINARY = ROOT / "checkpoints" / "radius6"
CHECKPOINT = ROOT / "checkpoints" / "radius6_exhaustive.json"
CANDIDATE = ROOT / "radius6_candidate.json"
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


def load_live() -> tuple[dict[str, Any], str, Any]:
    snapshot = json.loads(LIVE.read_text(encoding="utf-8"))
    verifier = snapshot["problem"]["verifier"]
    namespace: dict[str, Any] = {}
    exec(compile(verifier, "live_flat_polynomial_verifier.py", "exec"), namespace)
    return snapshot["solutions"][0], hashlib.sha256(verifier.encode()).hexdigest(), namespace["evaluate"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--first-begin", type=int, default=0)
    parser.add_argument("--first-end", type=int, default=65)
    return parser.parse_args()


def compile_binary() -> None:
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    if BINARY.exists() and BINARY.stat().st_mtime_ns >= SOURCE.stat().st_mtime_ns:
        return
    subprocess.run(
        ["clang++", "-O3", "-std=c++17", "-DNDEBUG", str(SOURCE), "-o", str(BINARY)],
        check=True,
    )


def run_first(sequence: str, first: int, gate: float, peak: int) -> dict[str, Any]:
    result = subprocess.run(
        [str(BINARY), sequence, str(first), str(first + 1), repr(gate), str(peak)],
        check=True,
        capture_output=True,
        text=True,
    )
    record: dict[str, Any] = {"first": first, "survivors": []}
    for line in result.stdout.splitlines():
        fields = line.split()
        if not fields:
            continue
        if fields[0] == "SURVIVOR":
            record["survivors"].append(
                {"flips": list(map(int, fields[1:7])), "literal_lower_bound": float(fields[7])}
            )
        elif fields[0] == "PROCESSED":
            record["processed"] = int(fields[1])
        elif fields[0] == "SURVIVORS":
            record["reported_survivors"] = int(fields[1])
        elif fields[0] == "GRID_POINTS":
            record["grid_points"] = int(fields[1])
        elif fields[0] == "MIN_CERTIFICATE":
            record["minimum_rejection_certificate"] = float(fields[1])
            record["minimum_rejection_mask"] = list(map(int, fields[2:8]))
    if record.get("reported_survivors") != len(record["survivors"]):
        raise RuntimeError(f"survivor parse mismatch for first={first}")
    if record.get("processed") != math.comb(69 - first, 5):
        raise RuntimeError(f"combination-count mismatch for first={first}")
    return record


def main() -> None:
    args = parse_args()
    if not 0 <= args.first_begin <= args.first_end <= 65 or args.workers < 1:
        raise SystemExit("invalid range or worker count")
    compile_binary()
    leader, verifier_hash, live_evaluate = load_live()
    coefficients = np.asarray(leader["data"]["coefficients"], dtype=np.int8)
    payload = {"coefficients": coefficients.astype(int).tolist()}
    payload_hash = hashlib.sha256(canonical(payload)).hexdigest()
    leader_score = float(live_evaluate(payload))
    if leader_score != float(leader["score"]):
        raise RuntimeError("pinned verifier does not reproduce the live leader")
    gate = leader_score - 1e-6

    padded = np.zeros(UNIQUE_GRID, dtype=np.float64)
    padded[: len(coefficients)] = coefficients[::-1]
    curve = UNIQUE_GRID * np.fft.ifft(padded)
    peak = int(np.argmax(np.abs(curve)))
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    config = {
        "first_begin": args.first_begin,
        "first_end": args.first_end,
        "expected_candidates": sum(math.comb(69 - first, 5) for first in range(args.first_begin, args.first_end)),
        "source_sha256": source_hash,
        "literal_grid": "512 coarse plus +/-6000 step 50 about peak and conjugate",
    }
    state: dict[str, Any] = {
        "schema": 1,
        "verifier_sha256": verifier_hash,
        "leader_payload_sha256": payload_hash,
        "leader_id": leader["id"],
        "leader_score": leader_score,
        "gate_score": gate,
        "peak_index": peak,
        "config": config,
        "completed_first_indices": [],
        "processed": 0,
        "literal_grid_survivors": 0,
        "exact_replays": 0,
        "exact_records": [],
        "minimum_rejection_certificate": None,
        "gate_cleared": False,
        "complete": False,
    }
    if CHECKPOINT.exists() and not args.restart:
        prior = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        for key in ("verifier_sha256", "leader_payload_sha256", "peak_index", "config"):
            if prior.get(key) != state[key]:
                raise RuntimeError(f"checkpoint {key} differs from this run")
        state.update(prior)
        if state["complete"]:
            print(json.dumps(state, indent=2, sort_keys=True))
            return

    sequence = ",".join(map(str, payload["coefficients"]))
    completed = set(map(int, state["completed_first_indices"]))
    pending = [first for first in range(args.first_begin, args.first_end) if first not in completed]

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_first, sequence, first, gate, peak): first
            for first in pending
        }
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            first = int(record["first"])
            for survivor in record["survivors"]:
                candidate_coefficients = coefficients.copy()
                candidate_coefficients[survivor["flips"]] *= -1
                candidate_payload = {"coefficients": candidate_coefficients.astype(int).tolist()}
                exact = float(live_evaluate(candidate_payload))
                exact_record = {**survivor, "exact_score": exact, "first": first}
                state["exact_records"].append(exact_record)
                state["exact_replays"] += 1
                if exact < gate:
                    state["gate_cleared"] = True
                    candidate_record = {
                        "payload": candidate_payload,
                        "payload_sha256": hashlib.sha256(canonical(candidate_payload)).hexdigest(),
                        "score": exact,
                        "leader_score": leader_score,
                        "gate_score": gate,
                        "flips": survivor["flips"],
                    }
                    atomic_json(CANDIDATE, candidate_record)
            state["processed"] += int(record["processed"])
            state["literal_grid_survivors"] += len(record["survivors"])
            certificate = record.get("minimum_rejection_certificate")
            if certificate is not None and (
                state["minimum_rejection_certificate"] is None
                or certificate < state["minimum_rejection_certificate"]["value"]
            ):
                state["minimum_rejection_certificate"] = {
                    "value": certificate,
                    "flips": record["minimum_rejection_mask"],
                }
            completed.add(first)
            state["completed_first_indices"] = sorted(completed)
            atomic_json(CHECKPOINT, state)
            print(
                f"first={first:02d} processed={record['processed']} total={state['processed']} "
                f"survivors={len(record['survivors'])}",
                flush=True,
            )

    state["complete"] = len(completed) == args.first_end - args.first_begin
    if state["complete"] and state["processed"] != config["expected_candidates"]:
        raise RuntimeError("final combination count mismatch")
    state["exact_records"].sort(key=lambda row: row["exact_score"])
    atomic_json(CHECKPOINT, state)
    print(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
