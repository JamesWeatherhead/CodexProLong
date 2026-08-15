#!/usr/bin/env python3
"""Screen Bober's complete height-one factorial-ratio classification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter
from pathlib import Path

from landau_core import (
    canonical_factorial,
    canonical_json,
    clean_room_live_mirror,
    decimal_score,
    fraction_decimal,
    map_to_arena,
    period_replay,
    score_interval,
    sha256_json,
)


HERE = Path(__file__).resolve().parent
TABLE = HERE / "bober_sporadic_52.json"
CHECKPOINT = HERE / "family_search_checkpoint.json"
PAYLOAD = HERE / "best_payload.json"
RECEIPT = HERE / "screen_receipt.json"
VERIFIER_SHA256 = "fd76a069b269a521d6ded609bd79185bf859df778283bebc37719dfd15b1ded6"
LIVE_LEADER = "0.9976572852677297"
LIVE_GATE = "0.9976582852677297"
HISTORICAL_GATE = "0.9976498835182795"


def atomic_json(path: Path, value: object) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(".{}.{}.tmp".format(path.name, os.getpid()))
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def family_parameters(family: int, a: int, b: int):
    if family == 1:
        return [a + b], [a, b]
    if family == 2:
        return [2 * a, b], [a, 2 * b, a - b]
    if family == 3:
        return [2 * a, 2 * b], [a, b, a + b]
    raise ValueError("unknown family")


def quick_score(numerator: list[int], denominator: list[int]) -> float:
    a, b, period_parameter, _ = map_to_arena(numerator, denominator)
    return (
        sum(value * math.log(value) for value in a)
        - sum(value * math.log(value) for value in b)
    ) / period_parameter


def family_search(family: int, bound: int):
    best = None
    evaluated = 0
    for a in range(1, bound + 1):
        if family == 2:
            b_values = range(1, a)
        else:
            b_values = range(a, bound + 1)
        for b in b_values:
            if math.gcd(a, b) != 1:
                continue
            numerator, denominator = family_parameters(family, a, b)
            score = quick_score(numerator, denominator)
            evaluated += 1
            candidate = (score, -a, -b, a, b, numerator, denominator)
            if best is None or candidate > best:
                best = candidate
    if best is None:
        raise RuntimeError("family search evaluated no candidates")
    _, _, _, a, b, numerator, denominator = best
    canonical_a, canonical_b, period_parameter, coefficients = map_to_arena(
        numerator, denominator
    )
    low, high = score_interval(numerator, denominator)
    return {
        "family": family,
        "parameter_bound_inclusive": bound,
        "coprime_pairs_evaluated": evaluated,
        "best_parameters": {"a": a, "b": b},
        "raw_numerator": numerator,
        "raw_denominator": denominator,
        "canonical_numerator": canonical_a,
        "canonical_denominator": canonical_b,
        "M": period_parameter,
        "coefficients": {str(key): value for key, value in coefficients.items()},
        "score_decimal": str(decimal_score(numerator, denominator)),
        "rigorous_score_lower": fraction_decimal(low),
        "rigorous_score_upper": fraction_decimal(high),
    }


def validate_sporadic(rows: list[dict]):
    if [row["line"] for row in rows] != list(range(1, 53)):
        raise ValueError("expected Bober sporadic rows 1..52")
    results = []
    for row in rows:
        raw_a = [int(value) for value in row["numerator"]]
        raw_b = [int(value) for value in row["denominator"]]
        if len(raw_b) != len(raw_a) + 1:
            raise ValueError("sporadic row has wrong height")
        if sum(raw_a) != sum(raw_b):
            raise ValueError("sporadic row is unbalanced")
        if math.gcd(*raw_a, *raw_b) != 1:
            raise ValueError("sporadic row is not primitive")
        if Counter(raw_a) & Counter(raw_b):
            raise ValueError("sporadic row contains an uncancelled common term")
        a, b, period_parameter, coefficients = map_to_arena(raw_a, raw_b)
        replay = period_replay(coefficients)
        if replay["minimum"] != 0 or replay["maximum"] != 1:
            raise ValueError("sporadic row is not exactly {0,1}-valued")
        if replay["other_values"]:
            raise ValueError("sporadic row has a value outside {0,1}")
        low, high = score_interval(a, b)
        results.append(
            {
                "line": row["line"],
                "numerator": a,
                "denominator": b,
                "M": period_parameter,
                "coefficients": {
                    str(key): value for key, value in coefficients.items()
                },
                "period_replay": replay,
                "score_decimal": str(decimal_score(a, b)),
                "rigorous_score_lower": fraction_decimal(low),
                "rigorous_score_upper": fraction_decimal(high),
                "_low": low,
                "_high": high,
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bound", type=int, default=2000)
    args = parser.parse_args()
    if args.bound < 3:
        raise ValueError("bound must be at least 3 to include each global maximizer")

    table = json.loads(TABLE.read_text(encoding="utf-8"))
    sporadic = validate_sporadic(table["sporadic"])
    ranked = sorted(sporadic, key=lambda row: row["_low"], reverse=True)
    best = ranked[0]
    if best["line"] != 31:
        raise RuntimeError("unexpected sporadic maximizer")
    margins = [best["_low"] - row["_high"] for row in sporadic if row is not best]
    if min(margins) <= 0:
        raise RuntimeError("rational log intervals do not isolate the sporadic maximum")

    families = []
    for family in (1, 2, 3):
        families.append(family_search(family, args.bound))
        atomic_json(
            CHECKPOINT,
            {
                "bound": args.bound,
                "completed_families": families,
                "status": "complete" if family == 3 else "running",
            },
        )
    expected = {1: (1, 1), 2: (3, 1), 3: (1, 1)}
    for result in families:
        parameters = result["best_parameters"]
        if (parameters["a"], parameters["b"]) != expected[result["family"]]:
            raise RuntimeError("bounded family maximizer did not match analytic maximizer")

    exact_coefficients = {int(key): value for key, value in best["coefficients"].items()}
    raw_payload = {
        "partial_function": {
            str(key): float(value)
            for key, value in exact_coefficients.items()
            if key != 1
        }
    }
    atomic_json(PAYLOAD, raw_payload)
    # Replay the exact serialized key order.  The live normalizer uses Python's
    # insertion-order summation, so this removes even an irrelevant one-ulp
    # ambiguity in the derived f(1).
    raw_payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    live_mirror = clean_room_live_mirror(raw_payload)
    if not live_mirror["passes_live_threshold"]:
        raise RuntimeError("best Bober payload fails the clean-room live mirror")
    if live_mirror["horizon_maximum_binary64"] > 1.0:
        raise RuntimeError("best payload needs verifier tolerance")

    best_score = decimal_score(best["numerator"], best["denominator"])
    for row in sporadic:
        row.pop("_low")
        row.pop("_high")
    receipt = {
        "schema_version": 1,
        "classification": {
            "source": table["source"],
            "sporadic_rows_checked": len(sporadic),
            "sporadic_table_sha256": hashlib.sha256(TABLE.read_bytes()).hexdigest(),
            "all_sporadic_periods_replayed_exactly": True,
            "all_sporadic_values_exactly_zero_or_one": True,
            "largest_sporadic_period": max(row["period_replay"]["period"] for row in sporadic),
        },
        "bounded_family_search": {
            "bound_each_parameter_inclusive": args.bound,
            "results": families,
            "analytic_global_maxima": {
                "family_1": "(a,b)=(1,1); entropy bound S<=log(2)/(ab)",
                "family_2": "(a,b)=(3,1); if d=a-b and bd>=3 then S<=3log(2)/(bd)<=log(2), while bd<=2 is checked exactly",
                "family_3": "(a,b)=(1,1); entropy bound S<=2log(2)/(ab), with ab<=2 checked exactly",
            },
        },
        "best_classified_certificate": {
            "kind": "sporadic",
            "bober_line": best["line"],
            "numerator": best["numerator"],
            "denominator": best["denominator"],
            "M": best["M"],
            "coefficients_including_f1": best["coefficients"],
            "score_decimal": str(best_score),
            "rigorous_score_lower": best["rigorous_score_lower"],
            "rigorous_score_upper": best["rigorous_score_upper"],
            "minimum_rigorous_margin_over_other_51_sporadics": fraction_decimal(
                min(margins)
            ),
            "period_replay": best["period_replay"],
            "payload_file": PAYLOAD.name,
            "payload_file_sha256": hashlib.sha256(PAYLOAD.read_bytes()).hexdigest(),
            "payload_canonical_sha256": sha256_json(raw_payload),
        },
        "live_clean_room_replay": {
            "verifier_sha256_refreshed_2026_08_15": VERIFIER_SHA256,
            "verifier_code_executed": False,
            "solution_schema": "partial_function: object mapping positive integer strings to float values",
            "min_improvement": "0.000001",
            "leader_score": LIVE_LEADER,
            "new_submission_gate": LIVE_GATE,
            "historical_gate": HISTORICAL_GATE,
            "result": live_mirror,
            "gap_to_live_gate": str(best_score - decimal_score_text(LIVE_GATE)),
            "gap_to_historical_gate": str(
                best_score - decimal_score_text(HISTORICAL_GATE)
            ),
        },
        "sporadic_results": sporadic,
        "conclusion": "Bober's complete height-one factorial-ratio class is globally valid but cannot clear either Arena gate; line 31 is Chebyshev's certificate.",
        "external_actions": "GET-only primary-source and live-metadata reads; no writes",
    }
    atomic_json(RECEIPT, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


def decimal_score_text(value: str):
    from decimal import Decimal

    return Decimal(value)


if __name__ == "__main__":
    raise SystemExit(main())
