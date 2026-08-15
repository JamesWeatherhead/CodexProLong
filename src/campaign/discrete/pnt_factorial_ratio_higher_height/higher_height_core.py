#!/usr/bin/env python3
"""Clean-room exact helpers for higher-height Landau certificates."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
from fractions import Fraction
from functools import reduce

import numpy as np


LOG_TERMS = 110


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def canonical_signed_list(values: list[int]) -> dict[int, int]:
    """Combine/cancel a signed factorial list and divide its total gcd."""
    if not values or any(not isinstance(value, int) or value == 0 for value in values):
        raise ValueError("factorial-list entries must be nonzero integers")
    counts: Counter[int] = Counter()
    for value in values:
        counts[abs(value)] += 1 if value > 0 else -1
    counts = Counter({key: value for key, value in counts.items() if value})
    if not counts:
        raise ValueError("factorial list cancelled completely")
    divisor = reduce(math.gcd, counts)
    result: Counter[int] = Counter()
    for key, value in counts.items():
        result[key // divisor] += value
    result = Counter({key: value for key, value in result.items() if value})
    if sum(key * value for key, value in result.items()) != 0:
        raise ValueError("factorial list is not balanced")
    if -sum(result.values()) <= 0:
        raise ValueError("factorial-list height is not positive")
    return dict(sorted(result.items()))


def signed_list_from_counts(counts: dict[int, int]) -> list[int]:
    result: list[int] = []
    for key, value in sorted(counts.items()):
        result.extend([key] * max(value, 0))
        result.extend([-key] * max(-value, 0))
    return result


def height(counts: dict[int, int]) -> int:
    return -sum(counts.values())


def period(counts: dict[int, int]) -> int:
    return math.lcm(*counts)


def arena_coefficients(counts: dict[int, int]) -> dict[int, Fraction]:
    """Map q to Arena key M/q and normalize Landau height to one."""
    denominator = height(counts)
    modulus = period(counts)
    result: Counter[int] = Counter()
    for key, value in counts.items():
        result[modulus // key] += Fraction(value, denominator)
    result = Counter({key: value for key, value in result.items() if value})
    if sum((value / key for key, value in result.items()), Fraction(0)) != 0:
        raise AssertionError("Arena map lost exact zero mean")
    return dict(sorted(result.items()))


def exact_period_replay(counts: dict[int, int]) -> dict[str, object]:
    """Enumerate the complete Landau period with exact int64 recurrence."""
    modulus = period(counts)
    direct_bound = sum(abs(value) * key for key, value in counts.items())
    if direct_bound >= np.iinfo(np.int64).max:
        raise OverflowError("Landau curve exceeds the int64 proof bound")
    increments = np.zeros(modulus + 1, dtype=np.int64)
    for key, value in counts.items():
        step = modulus // key
        increments[step::step] += value
    curve = np.cumsum(increments, dtype=np.int64)[:modulus]
    low_at = int(np.argmin(curve))
    high_at = int(np.argmax(curve))
    low = int(curve[low_at])
    high = int(curve[high_at])
    return {
        "period": modulus,
        "states_checked": modulus,
        "minimum": low,
        "minimum_at": low_at,
        "maximum": high,
        "maximum_at": high_at,
        "height": height(counts),
        "distinct_values": sorted(map(int, np.unique(curve))),
        "is_integral_factorial_ratio": low >= 0 and high <= height(counts),
    }


def atanh_log_interval(value: Fraction, terms: int = LOG_TERMS):
    if value < 1 or value > 2:
        raise ValueError("atanh reduction expects a value in [1,2]")
    z = (value - 1) / (value + 1)
    z_squared = z * z
    power = z
    partial = Fraction(0)
    for index in range(terms):
        partial += power / (2 * index + 1)
        power *= z_squared
    lower = 2 * partial
    if not z:
        return lower, lower
    remainder = 2 * power / ((2 * terms + 1) * (1 - z_squared))
    return lower, lower + remainder


def log_interval(integer: int, terms: int = LOG_TERMS):
    if integer < 1:
        raise ValueError("log input must be positive")
    if integer == 1:
        return Fraction(0), Fraction(0)
    exponent = integer.bit_length() - 1
    two_low, two_high = atanh_log_interval(Fraction(2), terms)
    reduced_low, reduced_high = atanh_log_interval(
        Fraction(integer, 1 << exponent), terms
    )
    return exponent * two_low + reduced_low, exponent * two_high + reduced_high


def score_interval(counts: dict[int, int]):
    """Rigorous normalized Arena-score interval."""
    denominator = height(counts) * period(counts)
    low = Fraction(0)
    high = Fraction(0)
    for key, value in counts.items():
        key_low, key_high = log_interval(key)
        if value > 0:
            low += value * key * key_low
            high += value * key * key_high
        else:
            low += value * key * key_high
            high += value * key * key_low
    return low / denominator, high / denominator


def decimal_score(counts: dict[int, int], precision: int = 90) -> Decimal:
    with localcontext() as context:
        context.prec = precision
        numerator = sum(
            Decimal(value) * Decimal(key) * Decimal(key).ln()
            for key, value in counts.items()
        )
        return numerator / Decimal(height(counts) * period(counts))


def fraction_decimal(value: Fraction, precision: int = 90) -> str:
    with localcontext() as context:
        context.prec = precision
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def directed_fraction_decimal(
    value: Fraction, direction: str, precision: int = 90
) -> str:
    """Convert a Fraction with explicitly outward decimal rounding."""
    if direction not in ("lower", "upper"):
        raise ValueError("direction must be lower or upper")
    with localcontext() as context:
        context.prec = precision
        context.rounding = ROUND_FLOOR if direction == "lower" else ROUND_CEILING
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def payload(counts: dict[int, int]) -> dict[str, object]:
    coefficients = arena_coefficients(counts)
    if len(coefficients) > 2000:
        raise ValueError("Arena support limit exceeded")
    if any(abs(value) > 10 for value in coefficients.values()):
        raise ValueError("Arena coordinate limit exceeded")
    return {
        "partial_function": {
            str(key): float(value) for key, value in sorted(coefficients.items())
        }
    }


def clean_room_live_mirror(candidate: dict[str, object]) -> dict[str, object]:
    """Mirror the literal written verifier formula without importing it."""
    raw = candidate.get("partial_function")
    if not isinstance(raw, dict) or not raw or len(raw) > 2000:
        raise ValueError("partial_function must contain 1..2000 entries")
    parsed: dict[int, float] = {}
    for raw_key, raw_value in raw.items():
        key = int(raw_key)
        value = float(raw_value)
        if key < 1 or not math.isfinite(value):
            raise ValueError("invalid key/value")
        parsed[key] = min(10.0, max(-10.0, value))
    total = sum(value / key for key, value in parsed.items())
    parsed[1] = parsed.get(1, 0.0) - total
    maximum_key = max(parsed)
    curve = {
        point: sum(value * (point // key) for key, value in parsed.items())
        for point in range(1, 10 * maximum_key + 1)
    }
    maximum = max(curve.values())
    score = -sum(value * math.log(key) / key for key, value in parsed.items())
    return {
        "derived_f1_binary64": parsed[1],
        "full_integer_horizon": 10 * maximum_key,
        "horizon_states_checked": 10 * maximum_key,
        "horizon_minimum_binary64": min(curve.values()),
        "horizon_maximum_binary64": maximum,
        "horizon_argmax_first": min(
            point for point, value in curve.items() if value == maximum
        ),
        "passes_live_threshold": maximum <= 1.0001,
        "score_binary64": score,
    }
