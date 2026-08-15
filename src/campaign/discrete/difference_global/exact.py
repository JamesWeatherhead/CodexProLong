#!/usr/bin/env python3
"""Exact primitives shared by the global Difference Bases experiments.

The Arena verifier uses a dense NumPy array.  These experiments use a Python
integer as the characteristic bitset instead, then replay every retained
frontier through the pinned live verifier.  Bit ``d`` means that ``d`` occurs
as an absolute difference.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
LIVE = ROOT.parent / "checkpoints" / "difference-bases-live.json"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def normalized(values: Iterable[int]) -> list[int]:
    result = sorted(set(int(value) for value in values))
    if not result:
        raise ValueError("a difference basis cannot be empty")
    shift = result[0]
    return [value - shift for value in result]


def difference_bits(values: Iterable[int]) -> int:
    ordered = normalized(values)
    bits = 1
    for index, first in enumerate(ordered[:-1]):
        for second in ordered[index + 1 :]:
            bits |= 1 << (second - first)
    return bits


def first_missing(bits: int) -> int:
    """Return the least nonnegative zero bit; bit zero must be present."""
    if not bits & 1:
        raise ValueError("difference bit zero must be present")
    return ((~bits) & (bits + 1)).bit_length() - 1


def coverage(values: Iterable[int]) -> int:
    return first_missing(difference_bits(values)) - 1


def exact_score(values: Iterable[int]) -> tuple[Fraction, int, list[int]]:
    ordered = normalized(values)
    covered = coverage(ordered)
    return Fraction(len(ordered) ** 2, covered), covered, ordered


def load_live() -> dict[str, Any]:
    snapshot = json.loads(LIVE.read_text(encoding="utf-8"))
    problem = snapshot["problem"]
    verifier = str(problem["verifier"])
    verifier_sha256 = hashlib.sha256(verifier.encode()).hexdigest()
    namespace: dict[str, Any] = {}
    exec(compile(verifier, "pinned_difference_bases_verifier.py", "exec"), namespace)
    leader = snapshot["solutions"][0]
    leader_values = normalized(leader["data"]["set"])
    leader_fraction, leader_coverage, leader_values = exact_score(leader_values)
    replay = float(namespace["evaluate"]({"set": leader_values}))
    if replay != float(leader["score"]) or replay != float(leader_fraction):
        raise RuntimeError("pinned verifier does not reproduce frozen leader")
    return {
        "snapshot": snapshot,
        "evaluate": namespace["evaluate"],
        "verifier_sha256": verifier_sha256,
        "leader_id": int(leader["id"]),
        "leader_agent": leader.get("agentName"),
        "leader_values": leader_values,
        "leader_payload_sha256": sha256_json({"set": leader_values}),
        "leader_fraction": leader_fraction,
        "leader_score": replay,
        "leader_coverage": leader_coverage,
        "min_improvement": float(problem["minImprovement"]),
        "gate_score": replay - float(problem["minImprovement"]),
    }


def replay(values: Iterable[int], live: dict[str, Any]) -> dict[str, Any]:
    fraction, covered, ordered = exact_score(values)
    payload = {"set": ordered}
    verifier_score = float(live["evaluate"](payload))
    if verifier_score != float(fraction):
        raise RuntimeError("bitset score disagrees with pinned live verifier")
    return {
        "size": len(ordered),
        "coverage": covered,
        "score_fraction": f"{fraction.numerator}/{fraction.denominator}",
        "score": verifier_score,
        "gate_score": live["gate_score"],
        "gate_cleared": verifier_score < live["gate_score"],
        "payload_sha256": sha256_json(payload),
        "payload": payload,
    }


def required_coverage(size: int, live: dict[str, Any]) -> int:
    """Least coverage whose float score safely clears the live gate."""
    covered = max(1, int(size * size / live["gate_score"]) - 2)
    while float(Fraction(size * size, covered)) >= live["gate_score"]:
        covered += 1
    return covered
