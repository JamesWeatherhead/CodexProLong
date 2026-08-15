#!/usr/bin/env python3
"""Bounded screen of primary-source height-two/three factorial-ratio families."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections.abc import Callable, Iterable
from decimal import Decimal
from pathlib import Path
from typing import Any

from higher_height_core import (
    arena_coefficients,
    canonical_signed_list,
    clean_room_live_mirror,
    decimal_score,
    directed_fraction_decimal,
    exact_period_replay,
    height,
    payload,
    period,
    score_interval,
    signed_list_from_counts,
)


HERE = Path(__file__).resolve().parent
CHECKPOINT = HERE / "family_search_checkpoint.json"
RECEIPT = HERE / "family_search_receipt.json"
BEST_PAYLOAD = HERE / "best_payload.json"
LIVE_LEADER = Decimal("0.9976572852677297")
LIVE_GATE = Decimal("0.9976582852677297")
CHANGED_SUPPORT_FRONTIER = Decimal(
    "0.9700735582811269039224111546813584232761257686802398581542833971639969"
)
SKIPPED_PERIOD: dict[str, Any] = {
    "count": 0,
    "best_score_binary64": None,
    "best_family": None,
    "best_period": None,
    "best_parameters": None,
}


def atomic_json(path: Path, value: Any) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fast_candidate(values: list[int]) -> tuple[dict[int, int], float] | None:
    try:
        counts = canonical_signed_list(values)
    except ValueError:
        return None
    divisor = height(counts)
    if divisor not in (2, 3):
        return None
    modulus = period(counts)
    score = sum(value * key * math.log(key) for key, value in counts.items())
    return counts, score / (divisor * modulus)


def section3_two_parameter() -> dict[str, Callable[[int, int], list[int]]]:
    """Soundararajan equations (6)--(31), retaining their paper labels."""
    return {
        "S3-06": lambda a, b: [3*a, -a, -9*a, 2*b, -b, 7*a-b],
        "S3-07": lambda a, b: [a, -3*a, -4*a, 2*b, -b, 6*a-b],
        "S3-08": lambda a, b: [12*a, -3*a, -4*a, 2*b, -b, -(b+5*a)],
        "S3-09": lambda a, b: [3*a, 12*a, -a, -6*a, -b, -(8*a-b)],
        "S3-10": lambda a, b: [2*a, 12*a, -a, -4*a, -b, -(9*a-b)],
        # The displayed left side in the source omits -b, but its explicit
        # decomposition on the same line contains it.  Balance forces -b.
        "S3-11": lambda a, b: [a, 12*a, -2*a, -3*a, -b, -(8*a-b)],
        "S3-12": lambda a, b: [2*a, 12*a, -3*a, -4*a, -b, -(7*a-b)],
        "S3-13": lambda a, b: [3*a, 12*a, -4*a, -6*a, -b, -(5*a-b)],
        "S3-14": lambda a, b: [2*a, 3*a, -a, -4*a, -6*a, 2*b, -b, 6*a-b],
        "S3-15": lambda a, b: [a, 6*a, -2*a, -3*a, -12*a, 2*b, -b, 10*a-b],
        "S3-16": lambda a, b: [4*a, 6*a, -2*a, -3*a, -12*a, 2*b, -b, 7*a-b],
        "S3-17": lambda a, b: [2*a, 12*a, -a, -4*a, -6*a, 2*b, -b, -3*a-b],
        "S3-18": lambda a, b: [2*a, 3*a, 18*a, -a, -6*a, -9*a, -b, b-7*a],
        "S3-19": lambda a, b: [2*a, 3*a, 12*a, -a, -4*a, -6*a, -b, b-6*a],
        "S3-20": lambda a, b: [2*a, b, 6*b, -a, -4*a, -2*b, -3*b, -(2*b-3*a)],
        "S3-21": lambda a, b: [2*a, 3*b, -a, -4*a, -b, -(2*b-3*a)],
        "S3-22": lambda a, b: [a, b, 6*b, -2*a, -3*a, -2*b, -3*b, -(2*b-4*a)],
        "S3-23": lambda a, b: [a, 3*b, -2*a, -3*a, -b, -(2*b-4*a)],
        "S3-24": lambda a, b: [6*a, 2*b, 3*b, -2*a, -3*a, -b, -6*b, 2*b-a],
        "S3-25": lambda a, b: [6*a, b, -2*a, -3*a, -3*b, 2*b-a],
        "S3-26": lambda a, b: [3*a, b, 6*b, -a, -6*a, -2*b, -3*b, 4*a-2*b],
        "S3-27": lambda a, b: [3*a, 3*b, -a, -6*a, -b, 4*a-2*b],
        "S3-28": lambda a, b: [2*a, b, 6*b, -a, -6*a, -2*b, -3*b, 5*a-2*b],
        "S3-29": lambda a, b: [2*a, 3*b, -a, -6*a, -b, 5*a-2*b],
        "S3-30": lambda a, b: [2*a, 4*b, -a, -4*a, -b, 3*a-3*b],
        "S3-31": lambda a, b: [2*a, 2*b, 6*(a+b), -a, -4*a, -b, -4*b, -3*(a+b)],
    }


SECTION5_BASES: list[tuple[list[int], list[int]]] = [
    ([2,-3,-4],[3,-1]), ([10,-5,-6],[3,-1]), ([6,-3,-4],[3,-1]),
    ([10,-2,-5],[3,-1]), ([10,-4,-5],[3,-1]), ([6,-1,-4],[3,-1]),
    ([4,-1,-2],[3,-1]), ([6,-3,-4],[4,-1]), ([6,-2,-3],[5,-1]),
    ([6,-2,-3],[6,-1]), ([3,10,-1,-5,-6],[3,-1]),
    ([2,15,-1,-5,-6],[3,-1]), ([2,9,-1,-3,-4],[3,-1]),
    ([1,6,-2,-3,-3],[3,-1]), ([1,10,-3,-4,-5],[3,-1]),
    ([2,15,-3,-4,-5],[3,-1]), ([3,10,-2,-5,-9],[3,-1]),
    ([2,12,-1,-4,-6],[3,-1]), ([2,3,12,-1,-4,-6,-9],[3,-1]),
    ([2,-3,-4],[1,6,-2,-3]), ([10,-5,-6],[1,6,-2,-3]),
    ([6,-3,-4],[1,6,-2,-3]), ([10,-2,-5],[1,6,-2,-3]),
    ([10,-4,-5],[1,6,-2,-3]), ([6,-1,-4],[1,6,-2,-3]),
    ([6,-2,-3],[1,10,-2,-5]), ([3,10,-1,-5,-6],[1,6,-2,-3]),
    ([2,15,-1,-5,-6],[1,6,-2,-3]), ([2,9,-1,-3,-4],[1,6,-2,-3]),
    ([1,6,-2,-3,-3],[1,6,-2,-3]), ([1,10,-3,-4,-5],[1,6,-2,-3]),
    ([2,15,-3,-4,-5],[1,6,-2,-3]), ([3,10,-2,-5,-9],[1,6,-2,-3]),
    ([2,12,-1,-4,-6],[1,6,-2,-3]), ([2,3,12,-1,-4,-6,-9],[1,6,-2,-3]),
    ([4,-3],[1,4,-2]), ([3,-2],[1,4,-2]), ([1,4,-2,-2],[1,4,-2]),
    ([1,8,-3,-4],[1,4,-2]), ([2,3,8,-1,-4,-6],[1,4,-2]),
    ([3,-2],[2,3,-1]), ([3,-2],[1,6,-2]), ([3,-2],[3,4,-2]),
]


def section5_family(row: int, first: int, second: int) -> list[int]:
    base_a, base_b = SECTION5_BASES[row - 1]
    return (
        [first * value for value in base_a]
        + [second * value for value in base_b]
        + [-first * sum(base_a) - second * sum(base_b)]
    )


def audit_section5_bases() -> dict[str, Any]:
    """Verify the 43 table rows meet Theorem 1.4's height-one premise."""
    periods: list[int] = []
    for row, (base_a, base_b) in enumerate(SECTION5_BASES, start=1):
        sum_a = sum(base_a)
        sum_b = sum(base_b)
        if not sum_a or not sum_b or math.gcd(abs(sum_a), abs(sum_b)) != 1:
            raise AssertionError(f"Section 5 row {row} violates the coprime-sum premise")
        premise = canonical_signed_list(
            [sum_b * value for value in base_a]
            + [-sum_a * value for value in base_b]
        )
        if height(premise) != 1:
            raise AssertionError(f"Section 5 row {row} premise is not height one")
        replay = exact_period_replay(premise)
        if not replay["is_integral_factorial_ratio"]:
            raise AssertionError(f"Section 5 row {row} premise failed Landau replay")
        periods.append(int(replay["period"]))
    return {
        "rows": len(SECTION5_BASES),
        "all_coprime_nonzero_sums": True,
        "all_height_one_premises_exactly_replayed": True,
        "largest_premise_period": max(periods),
    }


def keep_best(
    best: dict[str, tuple[float, dict[int, int], dict[str, int]]],
    family: str,
    values: list[int],
    parameters: dict[str, int],
    max_period: int,
) -> bool:
    candidate = fast_candidate(values)
    if candidate is None:
        return False
    counts, score = candidate
    if period(counts) > max_period:
        SKIPPED_PERIOD["count"] += 1
        prior = SKIPPED_PERIOD["best_score_binary64"]
        if prior is None or score > prior:
            SKIPPED_PERIOD.update(
                {
                    "best_score_binary64": score,
                    "best_family": family,
                    "best_period": period(counts),
                    "best_parameters": parameters,
                }
            )
        return True
    old = best.get(family)
    if old is None or score > old[0] + 1e-15:
        best[family] = (score, counts, parameters)
    return True


def explicit_families(bound: int) -> Iterable[tuple[str, list[int], dict[str, int]]]:
    for first in range(1, bound + 1):
        for second in range(1, bound + 1):
            if math.gcd(first, second) != 1:
                continue
            yield "Wider", [3*first, -first, 3*second, -second, -(first+second), -(first+second)], {"a": first, "b": second}
            yield "Askey", [3*(first+second), 3*second, 2*first, 2*second, -(2*first+3*second), -(first+2*second), -(first+second), -first, -second, -second], {"m": first, "n": second}
            yield "Landau-Picon-height2", [4*first, 4*second, -(2*first+second), -(first+2*second), -first, -second], {"n": first, "k": second}


def candidate_packet(
    family: str, score: float, counts: dict[int, int], parameters: dict[str, int]
) -> dict[str, Any]:
    low, high = score_interval(counts)
    replay = exact_period_replay(counts)
    if not replay["is_integral_factorial_ratio"]:
        raise AssertionError(f"retained family {family} failed exact Landau replay")
    candidate_payload = payload(counts)
    mirror = clean_room_live_mirror(candidate_payload)
    return {
        "family": family,
        "parameters": parameters,
        "canonical_signed_list": signed_list_from_counts(counts),
        "canonical_counts": {str(key): value for key, value in counts.items()},
        "height": height(counts),
        "period": period(counts),
        "screen_score_binary64": score,
        "score_decimal": str(decimal_score(counts)),
        "score_interval": {
            "lower_decimal_directed": directed_fraction_decimal(low, "lower"),
            "upper_decimal_directed": directed_fraction_decimal(high, "upper"),
        },
        "exact_period_replay": replay,
        "arena_coefficients_rational": {
            str(key): f"{value.numerator}/{value.denominator}"
            for key, value in arena_coefficients(counts).items()
        },
        "clean_room_live_mirror": mirror,
        "payload": candidate_payload,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bound", type=int, default=160)
    parser.add_argument("--three-bound", type=int, default=36)
    parser.add_argument("--gessel-bound", type=int, default=18)
    parser.add_argument("--max-exact-period", type=int, default=10_000_000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if min(args.bound, args.three_bound, args.gessel_bound) < 1:
        raise ValueError("search bounds must be positive")
    SKIPPED_PERIOD.update(
        {
            "count": 0,
            "best_score_binary64": None,
            "best_family": None,
            "best_period": None,
            "best_parameters": None,
        }
    )
    best: dict[str, tuple[float, dict[int, int], dict[str, int]]] = {}
    section5_audit = audit_section5_bases()
    generated = 0
    height_matched = 0

    for label, function in section3_two_parameter().items():
        for first in range(1, args.bound + 1):
            for second in range(1, args.bound + 1):
                if math.gcd(first, second) != 1:
                    continue
                generated += 1
                height_matched += keep_best(
                    best, label, function(first, second),
                    {"a": first, "b": second}, args.max_exact_period,
                )

    signed_values = range(-args.bound, args.bound + 1)
    for row in range(1, len(SECTION5_BASES) + 1):
        for first in signed_values:
            if not first:
                continue
            for second in signed_values:
                if not second or math.gcd(abs(first), abs(second)) != 1:
                    continue
                generated += 1
                height_matched += keep_best(
                    best, f"S5-{row:02d}", section5_family(row, first, second),
                    {"a": first, "b": second}, args.max_exact_period,
                )

    for label, values, parameters in explicit_families(args.bound):
        generated += 1
        height_matched += keep_best(
            best, label, values, parameters, args.max_exact_period
        )

    for a in range(1, args.three_bound + 1):
        for b in range(1, args.three_bound + 1):
            for c in range(1, args.three_bound + 1):
                if math.gcd(math.gcd(a, b), c) != 1:
                    continue
                generated += 2
                height_matched += keep_best(
                    best, "S3-04-multinomial", [a+b+c, -a, -b, -c],
                    {"a": a, "b": b, "c": c}, args.max_exact_period,
                )
                height_matched += keep_best(
                    best, "S3-05-product", [2*a, -a, 2*b, -b, -c, -(a+b-c)],
                    {"a": a, "b": b, "c": c}, args.max_exact_period,
                )

    # Gessel's four-parameter height-three family, quoted verbatim in line 38.
    for k in range(1, args.gessel_bound + 1):
        for ell in range(1, args.gessel_bound + 1):
            for m in range(1, args.gessel_bound + 1):
                for n in range(1, args.gessel_bound + 1):
                    if math.gcd(math.gcd(k, ell), math.gcd(m, n)) != 1:
                        continue
                    generated += 1
                    values = [
                        k+2*ell, k+2*m, k+2*n, k+ell+m+n,
                        -k, -ell, -m, -n, -(k+ell+m),
                        -(k+ell+n), -(k+m+n),
                    ]
                    height_matched += keep_best(
                        best, "Gessel-height3", values,
                        {"k": k, "ell": ell, "m": m, "n": n},
                        args.max_exact_period,
                    )

    # Explicit products benchmark reducible compositions at heights two/three.
    chebyshev = [30, 1, -15, -10, -6]
    for repetitions in (2, 3):
        generated += 1
        height_matched += keep_best(
            best, f"Chebyshev-product-height{repetitions}", chebyshev * repetitions,
            {"repetitions": repetitions}, args.max_exact_period,
        )

    retained = [
        candidate_packet(family, score, counts, parameters)
        for family, (score, counts, parameters) in best.items()
    ]
    retained.sort(key=lambda item: Decimal(item["score_decimal"]), reverse=True)
    if not retained:
        raise RuntimeError("family search retained no exact-replayable candidate")
    winner = retained[0]
    atomic_json(BEST_PAYLOAD, winner["payload"])
    checkpoint = {
        "bounds": vars(args),
        "candidates_generated": generated,
        "height_two_or_three_candidates": height_matched,
        "families_with_exact_replayable_member": len(retained),
        "period_cap_skips": SKIPPED_PERIOD,
        "section5_input_audit": section5_audit,
        "per_family_best": retained,
    }
    atomic_json(CHECKPOINT, checkpoint)
    winner_score = Decimal(winner["score_decimal"])
    receipt = {
        "scope": "bounded primary-source height-two/three family enumeration",
        "bounds": vars(args),
        "candidates_generated": generated,
        "height_two_or_three_candidates": height_matched,
        "families_with_exact_replayable_member": len(retained),
        "period_cap_skips": SKIPPED_PERIOD,
        "section5_input_audit": section5_audit,
        "best": winner,
        "best_payload_sha256": sha256_file(BEST_PAYLOAD),
        "checkpoint_sha256": sha256_file(CHECKPOINT),
        "changed_support_frontier": str(CHANGED_SUPPORT_FRONTIER),
        "gap_to_changed_support_frontier": str(winner_score - CHANGED_SUPPORT_FRONTIER),
        "live_leader": str(LIVE_LEADER),
        "live_gate": str(LIVE_GATE),
        "gap_to_live_gate": str(winner_score - LIVE_GATE),
        "verifier_executed": False,
        "external_actions": "GET-only primary literature; no external mutations",
    }
    atomic_json(RECEIPT, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
