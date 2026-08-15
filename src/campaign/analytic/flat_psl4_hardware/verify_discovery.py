#!/usr/bin/env python3
"""Recheck exact arithmetic and symmetry claims for published discoveries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DISCOVERIES = ROOT / "discoveries"
EXPECTED_DISCOVERIES = ("psl4_class_04.json", "psl4_class_05.json")
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


def validate_discovery(path: Path, fixture_classes: set[str]) -> tuple[dict, str]:
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("schema") != "psl4-metal-discovered-class-v1":
        raise AssertionError(f"discovery schema mismatch: {path.name}")
    bits = record["answer_bits"]
    if len(bits) != 70 or set(bits) - {"0", "1"}:
        raise AssertionError(f"answer is not a 70-bit sequence: {path.name}")
    if sha256_bytes(bits.encode()) != record["answer_bits_sha256"]:
        raise AssertionError(f"answer hash mismatch: {path.name}")

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
        raise AssertionError(f"exact PSL mismatch: {path.name}")
    if sha256_bytes(compact_json(correlations)) != record["autocorrelations_sha256"]:
        raise AssertionError(f"autocorrelation hash mismatch: {path.name}")

    canonical_bits = canonical(bits)
    if canonical_bits != bits or not record["canonical_under_eight_symmetries"]:
        raise AssertionError(
            f"answer is not the canonical symmetry representative: {path.name}"
        )
    if canonical_bits in fixture_classes:
        raise AssertionError(f"answer duplicates a retained public fixture: {path.name}")
    if not record["symmetry_distinct_from_retained_public_fixtures"]:
        raise AssertionError(f"fixture-distinct claim missing: {path.name}")

    payload = {"coefficients": coefficients}
    arena = record["arena_replay"]
    if sha256_bytes(compact_json(payload)) != arena["candidate_sha256"]:
        raise AssertionError(f"Arena candidate hash mismatch: {path.name}")
    gate = arena["leader_score"] - arena["min_improvement"]
    clears = arena["score"] <= gate
    if clears is not arena["clears_first_place_gate"] or clears:
        raise AssertionError(f"Arena gate arithmetic mismatch: {path.name}")
    if arena["margin"] != arena["leader_score"] - arena["score"]:
        raise AssertionError(f"Arena margin mismatch: {path.name}")

    cpu = record["cpu_replay"]
    metal = record["metal_replay"]
    if cpu["counters"] != metal["counters"]:
        raise AssertionError(f"CPU/Metal counter mismatch: {path.name}")
    if cpu["counters"]["valid_leaves"] != 1:
        raise AssertionError(f"expected exactly one valid leaf: {path.name}")

    summary = {
        "answer_bits_sha256": record["answer_bits_sha256"],
        "arena_score": arena["score"],
        "clears_first_place_gate": clears,
        "cpu_metal_counters_match": True,
        "exact_peak_sidelobe": observed_peak,
        "name": path.stem,
    }
    return summary, canonical_bits


def main() -> int:
    paths = [DISCOVERIES / name for name in EXPECTED_DISCOVERIES]
    missing = [path.name for path in paths if not path.is_file()]
    unexpected = sorted(
        path.name
        for path in DISCOVERIES.glob("psl4_class_*.json")
        if path.name not in EXPECTED_DISCOVERIES
    )
    if missing or unexpected:
        raise AssertionError(
            f"discovery inventory mismatch: missing={missing}, unexpected={unexpected}"
        )

    fixture_classes = {canonical(value) for value in PUBLIC_FIXTURES}
    summaries = []
    seen_classes: dict[str, str] = {}
    for path in paths:
        summary, canonical_bits = validate_discovery(path, fixture_classes)
        if canonical_bits in seen_classes:
            raise AssertionError(
                f"published discoveries are symmetry-equivalent: "
                f"{seen_classes[canonical_bits]} and {path.name}"
            )
        seen_classes[canonical_bits] = path.name
        summaries.append(summary)

    newest = json.loads(paths[-1].read_text(encoding="utf-8"))
    if newest.get("symmetry_distinct_from_retained_discoveries") is not True:
        raise AssertionError("newest discovery lacks retained-class distinction claim")
    corpus = newest.get("corpus_replay", {})
    if corpus != {
        "database_sha256": (
            "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"
        ),
        "flat_polynomials_solution_count": 24,
        "symmetry_match_count": 0,
    }:
        raise AssertionError("newest discovery corpus-replay summary mismatch")

    result = {
        "all_cpu_metal_counters_match": True,
        "all_exact_peak_sidelobes": 4,
        "any_clears_first_place_gate": any(
            item["clears_first_place_gate"] for item in summaries
        ),
        "class_summaries": summaries,
        "discovered_class_count": len(summaries),
        "pairwise_symmetry_distinct": len(seen_classes) == len(summaries),
        "retained_corpus_solution_count": corpus["flat_polynomials_solution_count"],
        "retained_corpus_symmetry_match_count": corpus["symmetry_match_count"],
        "status": "pass",
        "symmetry_distinct_public_fixture_count": len(PUBLIC_FIXTURES),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
