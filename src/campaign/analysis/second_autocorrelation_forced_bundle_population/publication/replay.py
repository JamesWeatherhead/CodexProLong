#!/usr/bin/env python3
"""Independent compact replay for a bounded forced-bundle pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import oaconvolve


LANE = Path(__file__).resolve().parent


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exact_formula(values: np.ndarray) -> float:
    f = np.maximum(np.asarray(values, dtype=np.float64), 0.0)
    if f.ndim != 1 or not np.all(np.isfinite(f)) or np.sum(f) <= 0:
        raise ValueError("invalid checkpoint")
    g = oaconvolve(f, f, mode="full")
    numerator = 2.0 * np.dot(g, g) + np.dot(g[:-1], g[1:])
    return float(numerator / (3.0 * np.sum(g) * np.max(g)))


def verify_chain(path: Path) -> tuple[int, str]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    previous = "0" * 64
    for sequence, row in enumerate(rows):
        event_sha256 = row.pop("event_sha256")
        if row["sequence"] != sequence or row["previous_sha256"] != previous:
            raise AssertionError("event sequence or predecessor mismatch")
        encoded = json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
        expected = hashlib.sha256(previous.encode("ascii") + encoded).hexdigest()
        if event_sha256 != expected:
            raise AssertionError("event hash mismatch")
        previous = event_sha256
    return len(rows), previous


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run = args.run.resolve()
    try:
        run.relative_to(LANE / "runs")
    except ValueError as error:
        raise SystemExit("run must be inside the isolated lane's runs directory") from error
    summary: dict[str, Any] = json.loads((run / "summary.json").read_text())
    checkpoint = run / str(summary["checkpoint"])
    if sha256_file(checkpoint) != summary["checkpoint_sha256"]:
        raise AssertionError("checkpoint file hash mismatch")
    values = np.load(checkpoint, allow_pickle=False)
    value_hash = hashlib.sha256(np.ascontiguousarray(values, dtype="<f8").tobytes()).hexdigest()
    if value_hash != summary["checkpoint_value_float64_le_sha256"]:
        raise AssertionError("checkpoint value hash mismatch")
    score = exact_formula(values)
    if not math.isclose(score, summary["best_score"], rel_tol=0.0, abs_tol=2e-15):
        raise AssertionError((score, summary["best_score"]))
    event_count, event_head = verify_chain(run / "events.jsonl")
    if event_count != summary["event_count"] or event_head != summary["event_chain_head"]:
        raise AssertionError("event-chain summary mismatch")
    result = {
        "status": "PASS",
        "run": str(run),
        "score": score,
        "gap_to_gate": summary["strict_gate"] - score,
        "gate_cleared": score > summary["strict_gate"],
        "checkpoint_sha256": summary["checkpoint_sha256"],
        "event_count": event_count,
        "event_chain_head": event_head,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
