#!/usr/bin/env python3
"""Certify the public Erdős step function with exact integer arithmetic.

The JSON payload is parsed as IEEE-754 binary64, exactly as the frozen Arena
verifier parses it.  Every resulting float is then converted to an exact
dyadic rational.  No floating-point arithmetic is used for the certified
normalization, overlap scores, maximization, or reported upper bound.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, localcontext
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "artifacts/wins/erdos-min-overlap.json"
RECEIPT = ROOT / "artifacts/receipts/erdos-min-overlap.json"
VERIFIER = ROOT / "artifacts/verifiers/erdos-min-overlap.json"
FRONTIER = ROOT / "data/frontier.json"
OUTPUT = ROOT / "artifacts/certificates/erdos-min-overlap-continuous.json"
PUBLISHED_REFERENCE = Decimal("0.38087131058")
DECIMAL_PLACES = 40
CERTIFICATE_GENERATED_AT = "2026-08-15T16:43:14Z"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def common_integer_payload(values: list[float]) -> tuple[list[int], int, int]:
    """Return common-denominator numerators X, their sum T, and denominator D."""
    ratios = [value.as_integer_ratio() for value in values]
    denominators = [denominator for _, denominator in ratios]
    if any(denominator <= 0 or denominator & (denominator - 1) for denominator in denominators):
        raise AssertionError("binary64 denominator is not a power of two")
    common_denominator = max(denominators)
    numerators = [
        numerator * (common_denominator // denominator)
        for numerator, denominator in ratios
    ]
    return numerators, sum(numerators), common_denominator


def exact_overlap_numerators(
    numerators: list[int], total: int, mass: int
) -> list[tuple[int, int]]:
    """Return ``(lag, numerator)`` for every score over denominator ``total**2``."""
    n = len(numerators)
    scores: list[tuple[int, int]] = []
    for lag in range(-(n - 1), n):
        if lag >= 0:
            start, stop, other_offset = lag, n, -lag
        else:
            start, stop, other_offset = 0, n + lag, -lag
        source_mass = sum(numerators[start:stop])
        product_mass = sum(
            numerators[index] * numerators[index + other_offset]
            for index in range(start, stop)
        )
        scores.append((lag, total * source_mass - mass * product_mass))
    return scores


def decimal_ratio(
    numerator: int, denominator: int, *, places: int, rounding: str
) -> str:
    quantum = Decimal(1).scaleb(-places)
    with localcontext() as context:
        context.prec = max(100, len(str(abs(numerator))) + places + 10)
        context.rounding = rounding
        value = Decimal(numerator) / Decimal(denominator)
        return format(value.quantize(quantum, rounding=rounding), "f")


def build_certificate() -> dict[str, object]:
    payload_raw = PAYLOAD.read_bytes()
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    snapshot = json.loads(VERIFIER.read_text(encoding="utf-8"))
    frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
    payload = json.loads(payload_raw)
    values = payload["values"]

    if not isinstance(values, list) or not values or len(values) % 2:
        raise AssertionError("payload must contain a nonempty even-length list")
    if any(not isinstance(value, float) or not math.isfinite(value) for value in values):
        raise AssertionError("payload is not a finite binary64 vector")
    if any(value < 0.0 or value > 1.0 for value in values):
        raise AssertionError("payload violates the input box")
    if sha256(payload_raw) != receipt["artifact_sha256"]:
        raise AssertionError("payload byte hash does not match receipt")

    verifier_source = snapshot["problem"]["verifier"].encode("utf-8")
    verifier_sha = sha256(verifier_source)
    if verifier_sha != snapshot["verifier_sha256"] or verifier_sha != receipt["verifier_sha256"]:
        raise AssertionError("frozen verifier source hash mismatch")

    n = len(values)
    mass = n // 2
    integers, total, common_denominator = common_integer_payload(values)
    scores = exact_overlap_numerators(integers, total, mass)
    best_numerator_unreduced = max(numerator for _, numerator in scores)
    maximizing_lags = [
        lag for lag, numerator in scores if numerator == best_numerator_unreduced
    ]
    denominator_unreduced = total * total
    divisor = math.gcd(best_numerator_unreduced, denominator_unreduced)
    best_numerator = best_numerator_unreduced // divisor
    best_denominator = denominator_unreduced // divisor

    minimum_normalized_numerator = mass * min(integers)
    maximum_normalized_numerator = mass * max(integers)
    in_box = minimum_normalized_numerator >= 0 and maximum_normalized_numerator <= total
    if not in_box:
        raise AssertionError("exact normalization leaves the unit box")

    prior = Decimal(str(receipt["leader_score"]))
    arena_gate = Decimal(str(float(receipt["leader_score"] - receipt["min_improvement"])))
    exact_upper = decimal_ratio(
        best_numerator,
        best_denominator,
        places=DECIMAL_PLACES,
        rounding=ROUND_CEILING,
    )
    upper_decimal = Decimal(exact_upper)

    with localcontext() as context:
        context.prec = 100
        prior_improvement_numerator = (
            int(prior.scaleb(-prior.as_tuple().exponent)) * best_denominator
            - best_numerator * (10 ** -prior.as_tuple().exponent)
        )
        prior_improvement_denominator = best_denominator * (10 ** -prior.as_tuple().exponent)
        published_scale = 10 ** -PUBLISHED_REFERENCE.as_tuple().exponent
        published_integer = int(PUBLISHED_REFERENCE * published_scale)
        published_improvement_numerator = (
            published_integer * best_denominator
            - best_numerator * published_scale
        )
        published_improvement_denominator = best_denominator * published_scale

    source_sha = sha256(Path(__file__).read_bytes())
    return {
        "schema_version": 1,
        "generated_at": CERTIFICATE_GENERATED_AT,
        "source_snapshot_generated_at": frontier["generated_at"],
        "mathematical_claim": (
            "The explicitly normalized 3,584-step density has continuous "
            "minimum-overlap objective at most the rigorous decimal bound below."
        ),
        "n": n,
        "domain_interval": "[0, 2]",
        "interval_width": f"1/{mass}",
        "exact_common_binary_denominator": str(common_denominator),
        "exact_payload_integer_sum": str(total),
        "exact_max_numerator": str(best_numerator),
        "exact_max_denominator": str(best_denominator),
        "rigorous_decimal_upper_bound": exact_upper,
        "maximizing_lags": maximizing_lags,
        "prior_arena_leader": str(prior),
        "arena_strict_gate": str(arena_gate),
        "improvement_over_prior_arena_leader": decimal_ratio(
            prior_improvement_numerator,
            prior_improvement_denominator,
            places=DECIMAL_PLACES,
            rounding=ROUND_FLOOR,
        ),
        "published_reference_upper_bound": str(PUBLISHED_REFERENCE),
        "improvement_over_published_reference": decimal_ratio(
            published_improvement_numerator,
            published_improvement_denominator,
            places=DECIMAL_PLACES,
            rounding=ROUND_FLOOR,
        ),
        "comparisons": {
            "below_prior_arena_leader": upper_decimal < prior,
            "clears_frozen_arena_gate": upper_decimal < arena_gate,
            "below_published_reference_upper_bound": upper_decimal < PUBLISHED_REFERENCE,
        },
        "payload_sha256": sha256(payload_raw),
        "canonical_candidate_sha256": receipt["candidate_sha256"],
        "verifier_sha256": verifier_sha,
        "certificate_source_sha256": source_sha,
        "domain_checks": {
            "finite_binary64_payload": True,
            "payload_length": n,
            "exact_integral_after_normalization": "1",
            "exact_normalized_values_in_unit_interval": in_box,
            "minimum_normalized_value_upper_decimal": decimal_ratio(
                minimum_normalized_numerator,
                total,
                places=DECIMAL_PLACES,
                rounding=ROUND_CEILING,
            ),
            "maximum_normalized_value_upper_decimal": decimal_ratio(
                maximum_normalized_numerator,
                total,
                places=DECIMAL_PLACES,
                rounding=ROUND_CEILING,
            ),
            "all_grid_lags_evaluated": 2 * n - 1,
        },
        "continuous_reduction": (
            "For a step function and shifted step-function complement, interval "
            "intersection lengths are affine between consecutive grid shifts. "
            "Their weighted sum is therefore affine there, so every continuous "
            "maximum occurs at a grid boundary."
        ),
        "arithmetic": (
            "IEEE-754 values are converted with as_integer_ratio(), lifted to a "
            "common power-of-two denominator, normalized exactly, and scored "
            "with Python integers over all 2n-1 lags."
        ),
    }


def encoded_certificate() -> bytes:
    return (json.dumps(build_certificate(), indent=2, sort_keys=True) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail unless the checked-in certificate matches a fresh exact computation",
    )
    args = parser.parse_args()
    expected = encoded_certificate()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != expected:
            raise SystemExit("Erdős continuous certificate is stale")
        print(f"continuous certificate OK: {OUTPUT.relative_to(ROOT)}")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(expected)
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
