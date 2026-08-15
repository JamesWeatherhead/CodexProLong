#!/usr/bin/env python3
"""Independently harden and replay the changed-reach PNT candidate.

The optimizer separates only on the verifier's fixed Monte Carlo stream.  This
replayer additionally checks every integer state in the verifier's complete
``[1, 10 * max_key]`` horizon.  Because all submitted keys are integers, the
constraint is constant between consecutive integers.  A uniform scale supplies
an explicit full-horizon floating-point safety margin without changing support.

Only public GET requests are made.  There is no submission or discussion path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "reach_extend_127849_global_best.json"
OUTPUT = ROOT / "reach_extend_127849_fullrange.json"
RECEIPT = ROOT / "checkpoints" / "reach_extend_127849_fullrange_receipt.json"
BASE_URL = "https://einsteinarena.com"
SLUG = "prime-number-theorem"
PROBLEM_ID = 7
LIMIT = 1.0001


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, value: Any, *, sort_keys: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=sort_keys, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def get_json(path: str) -> Any:
    request = urllib.request.Request(
        BASE_URL + path,
        headers={"Accept": "application/json", "User-Agent": "pnt-replay/1"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def parse_payload(payload: dict[str, Any]) -> tuple[list[str], np.ndarray, np.ndarray]:
    raw = payload.get("partial_function")
    if not isinstance(raw, dict) or not raw or len(raw) > 2_000 or "1" in raw:
        raise ValueError("expected 1..2000 non-unit partial_function entries")
    labels = list(raw)
    keys = np.asarray([int(label) for label in labels], dtype=np.int64)
    values = np.asarray([float(raw[label]) for label in labels], dtype=np.float64)
    if np.any(keys <= 1) or len(set(map(int, keys))) != len(keys):
        raise ValueError("keys must be distinct integers greater than one")
    if not np.isfinite(values).all():
        raise ValueError("values must be finite")
    return labels, keys, np.clip(values, -10.0, 10.0)


def full_horizon(
    keys: np.ndarray, values: np.ndarray
) -> tuple[float, int, float, int]:
    upper = 10 * int(keys.max())
    # Match the verifier's ordered Python sum, including its f(1) adjustment.
    total = sum(float(value) / int(key) for key, value in zip(keys, values, strict=True))
    differences = np.empty(upper + 1, dtype=np.float64)
    differences[0] = 0.0
    differences[1:] = -total
    for key, value in zip(keys, values, strict=True):
        differences[int(key) :: int(key)] += float(value)
    curve = np.cumsum(differences)
    argmax = int(np.argmax(curve[1:])) + 1
    return float(curve[argmax]), argmax, float(total), upper


def objective(keys: np.ndarray, values: np.ndarray) -> float:
    return -float(np.sum(values * np.log(keys) / keys))


def official_evaluate(verifier: str, payload: dict[str, Any]) -> float:
    namespace: dict[str, Any] = {}
    exec(  # noqa: S102 - live source is hash-pinned in the receipt
        compile(verifier, "live_prime_number_theorem_verifier.py", "exec"), namespace
    )
    return float(namespace["evaluate"](payload))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument(
        "--target-max",
        type=float,
        default=1.00009999,
        help="full-horizon maximum after uniform scaling",
    )
    parser.add_argument("--official", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 < args.target_max < LIMIT:
        raise ValueError("target-max must be positive and strictly below 1.0001")
    source = json.loads(args.source.read_text(encoding="utf-8"))
    labels, keys, source_values = parse_payload(source)
    source_max, source_argmax, _, upper = full_horizon(keys, source_values)
    scale = min(1.0, args.target_max / source_max)
    hardened_values = source_values * scale
    hardened = {
        "partial_function": {
            label: float(value)
            for label, value in zip(labels, hardened_values, strict=True)
        }
    }
    hardened_max, hardened_argmax, normalization_total, _ = full_horizon(
        keys, hardened_values
    )
    if hardened_max >= LIMIT:
        raise RuntimeError("full-horizon hardening did not clear the strict limit")
    atomic_json(args.output.resolve(), hardened)

    problem = get_json(f"/api/problems/{SLUG}")
    query = urllib.parse.urlencode({"problem_id": PROBLEM_ID, "limit": 100})
    leaderboard = get_json(f"/api/leaderboard?{query}")
    if not isinstance(leaderboard, list) or not leaderboard:
        raise RuntimeError("live leaderboard is empty")
    verifier = str(problem["verifier"])
    verifier_hash = hashlib.sha256(verifier.encode()).hexdigest()
    leader = leaderboard[0]
    leader_score = float(leader.get("score", leader.get("bestScore")))
    min_improvement = float(problem.get("minImprovement", 0.0))
    score = objective(keys, hardened_values)
    official_score = official_evaluate(verifier, hardened) if args.official else None
    receipt = {
        "verified_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "external_actions": "public GET only",
        "source_path": str(args.source.resolve()),
        "source_sha256": hashlib.sha256(canonical(source)).hexdigest(),
        "source_full_horizon_max": source_max,
        "source_full_horizon_argmax": source_argmax,
        "candidate_path": str(args.output.resolve()),
        "candidate_sha256": hashlib.sha256(canonical(hardened)).hexdigest(),
        "raw_key_count": len(labels),
        "max_key": int(keys.max()),
        "full_horizon_upper": upper,
        "uniform_scale": scale,
        "normalization_total": normalization_total,
        "full_horizon_max": hardened_max,
        "full_horizon_argmax": hardened_argmax,
        "full_horizon_feasible": hardened_max < LIMIT,
        "verifier_sha256": verifier_hash,
        "leader_score": leader_score,
        "min_improvement": min_improvement,
        "gate_score": leader_score + min_improvement,
        "candidate_score": score,
        "gate_margin": score - leader_score - min_improvement,
        "official_verifier_score": official_score,
        "official_gate_cleared": (
            official_score is not None
            and np.isfinite(official_score)
            and official_score >= leader_score + min_improvement
        ),
    }
    atomic_json(args.receipt.resolve(), receipt, sort_keys=True)
    print(json.dumps(receipt, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
