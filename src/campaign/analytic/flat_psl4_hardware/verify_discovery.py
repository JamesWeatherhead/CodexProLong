#!/usr/bin/env python3
"""Recheck the exact arithmetic and symmetry claims for the discovered class."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DISCOVERY = ROOT / "discoveries" / "psl4_class_04.json"
PUBLIC_FIXTURES = (
    "1001011001011001010100110011001100001010110101000000000010111100011111",
    "1010110101101010101110011001110110010111100111100110110110000000001111",
    "1000000101010100010010000011011011110011100011010010001100110111101001",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def compact_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def transform(bits: str, reverse: bool, alternate: bool, negate: bool) -> str:
    result = []
    for index in range(len(bits)):
        source = len(bits) - 1 - index if reverse else index
        value = bits[source] == "1"
        if alternate and index % 2:
            value = not value
        if negate:
            value = not value
        result.append("1" if value else "0")
    return "".join(result)


def canonical(bits: str) -> str:
    return min(
        transform(bits, reverse, alternate, negate)
        for reverse in (False, True)
        for alternate in (False, True)
        for negate in (False, True)
    )


def main() -> int:
    record = json.loads(DISCOVERY.read_text(encoding="utf-8"))
    if record.get("schema") != "psl4-metal-discovered-class-v1":
        raise AssertionError("discovery schema mismatch")
    bits = record["answer_bits"]
    if len(bits) != 70 or set(bits) - {"0", "1"}:
        raise AssertionError("answer is not a 70-bit sequence")
    if sha256_bytes(bits.encode()) != record["answer_bits_sha256"]:
        raise AssertionError("answer hash mismatch")

    coefficients = [1 if bit == "1" else -1 for bit in bits]
    correlations = [
        sum(
            coefficients[index] * coefficients[index + lag]
            for index in range(len(coefficients) - lag)
        )
        for lag in range(1, len(coefficients))
    ]
    observed_peak = max(map(abs, correlations))
    if observed_peak != 4 or record["exact_peak_sidelobe"] != 4:
        raise AssertionError("exact PSL mismatch")
    if sha256_bytes(compact_json(correlations)) != record["autocorrelations_sha256"]:
        raise AssertionError("autocorrelation hash mismatch")
    if canonical(bits) != bits or not record["canonical_under_eight_symmetries"]:
        raise AssertionError("answer is not the canonical symmetry representative")
    if canonical(bits) in {canonical(value) for value in PUBLIC_FIXTURES}:
        raise AssertionError("answer duplicates a retained public fixture")
    if not record["symmetry_distinct_from_retained_public_fixtures"]:
        raise AssertionError("fixture-distinct claim missing")

    payload = {"coefficients": coefficients}
    arena = record["arena_replay"]
    if sha256_bytes(compact_json(payload)) != arena["candidate_sha256"]:
        raise AssertionError("Arena candidate hash mismatch")
    gate = arena["leader_score"] - arena["min_improvement"]
    clears = arena["score"] <= gate
    if clears is not arena["clears_first_place_gate"] or clears:
        raise AssertionError("Arena gate arithmetic mismatch")
    if arena["margin"] != arena["leader_score"] - arena["score"]:
        raise AssertionError("Arena margin mismatch")

    cpu = record["cpu_replay"]
    metal = record["metal_replay"]
    if cpu["counters"] != metal["counters"]:
        raise AssertionError("CPU/Metal counter mismatch")
    if cpu["counters"]["valid_leaves"] != 1:
        raise AssertionError("expected exactly one valid leaf")

    result = {
        "answer_bits_sha256": record["answer_bits_sha256"],
        "arena_score": arena["score"],
        "clears_first_place_gate": clears,
        "cpu_metal_counters_match": True,
        "exact_peak_sidelobe": 4,
        "status": "pass",
        "symmetry_distinct_public_fixture_count": len(PUBLIC_FIXTURES),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
