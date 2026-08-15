#!/usr/bin/env python3
"""Clean-room exact helpers for Bober/Landau PNT certificates."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction
from functools import reduce


LOG_TERMS = 100


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def canonical_factorial(numerator: list[int], denominator: list[int]):
    """Cancel cross-side terms and divide the remaining total gcd."""
    positive = Counter(numerator)
    negative = Counter(denominator)
    for value in set(positive).intersection(negative):
        count = min(positive[value], negative[value])
        positive[value] -= count
        negative[value] -= count
    a = sorted(positive.elements())
    b = sorted(negative.elements())
    if not a or not b:
        raise ValueError("factorial ratio cancelled completely")
    divisor = reduce(math.gcd, a + b)
    a = [value // divisor for value in a]
    b = [value // divisor for value in b]
    if len(b) != len(a) + 1:
        raise ValueError("factorial-ratio height is not one")
    if sum(a) != sum(b):
        raise ValueError("factorial-ratio parameters are not balanced")
    if set(a).intersection(b):
        raise ValueError("canonical factorial ratio retains a common term")
    return a, b


def map_to_arena(numerator: list[int], denominator: list[int]):
    """Apply Bober's m=M/q map and combine repeated support indices."""
    a, b = canonical_factorial(numerator, denominator)
    period_parameter = math.lcm(*(a + b))
    coefficients = Counter()
    for value in a:
        coefficients[period_parameter // value] += 1
    for value in b:
        coefficients[period_parameter // value] -= 1
    coefficients = {
        key: coefficients[key] for key in sorted(coefficients) if coefficients[key]
    }
    normalization_numerator = sum(
        value * (period_parameter // key)
        for key, value in coefficients.items()
    )
    if normalization_numerator != 0:
        raise ValueError("mapped Arena coefficients are not exactly normalized")
    if not coefficients or max(abs(value) for value in coefficients.values()) > 10:
        raise ValueError("mapped coefficients violate the Arena value bounds")
    return a, b, period_parameter, coefficients


def atanh_log_interval(value: Fraction, terms: int = LOG_TERMS):
    """Exact rational bounds for log(value), for 1 <= value <= 2."""
    if value < 1 or value > 2:
        raise ValueError("atanh log reduction expects a value in [1,2]")
    z = (value - 1) / (value + 1)
    z_squared = z * z
    power = z
    partial = Fraction(0)
    for index in range(terms):
        partial += power / (2 * index + 1)
        power *= z_squared
    lower = 2 * partial
    if z == 0:
        return lower, lower
    remainder = 2 * power / ((2 * terms + 1) * (1 - z_squared))
    return lower, lower + remainder


def log_interval(integer: int, terms: int = LOG_TERMS):
    """Rigorous rational lower/upper bounds for log(integer)."""
    if integer < 1:
        raise ValueError("log input must be positive")
    if integer == 1:
        return Fraction(0), Fraction(0)
    exponent = integer.bit_length() - 1
    log_two_low, log_two_high = atanh_log_interval(Fraction(2), terms)
    reduced = Fraction(integer, 1 << exponent)
    reduced_low, reduced_high = atanh_log_interval(reduced, terms)
    return (
        exponent * log_two_low + reduced_low,
        exponent * log_two_high + reduced_high,
    )


def score_interval(numerator: list[int], denominator: list[int]):
    """Rigorous rational bounds for the canonical Arena score."""
    a, b, period_parameter, _ = map_to_arena(numerator, denominator)
    low = Fraction(0)
    high = Fraction(0)
    for value in a:
        value_low, value_high = log_interval(value)
        low += value * value_low
        high += value * value_high
    for value in b:
        value_low, value_high = log_interval(value)
        low -= value * value_high
        high -= value * value_low
    return low / period_parameter, high / period_parameter


def decimal_score(numerator: list[int], denominator: list[int], precision: int = 90):
    a, b, period_parameter, _ = map_to_arena(numerator, denominator)
    with localcontext() as context:
        context.prec = precision
        return (
            sum(Decimal(value) * Decimal(value).ln() for value in a)
            - sum(Decimal(value) * Decimal(value).ln() for value in b)
        ) / Decimal(period_parameter)


def fraction_decimal(value: Fraction, precision: int = 90) -> str:
    with localcontext() as context:
        context.prec = precision
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def period_replay(coefficients: dict[int, int]):
    """Check every integer state of the exact normalized period."""
    period = math.lcm(*coefficients)
    normalization = sum(Fraction(value, key) for key, value in coefficients.items())
    if normalization != 0:
        raise ValueError("floor sum is not periodic because normalization is nonzero")
    values = [
        sum(value * (point // key) for key, value in coefficients.items())
        for point in range(period)
    ]
    return {
        "period": period,
        "states_checked": period,
        "minimum": min(values),
        "maximum": max(values),
        "ones": sum(value == 1 for value in values),
        "zeros": sum(value == 0 for value in values),
        "other_values": sorted(set(values).difference((0, 1))),
    }

def clean_room_live_mirror(payload: dict):
    """Mirror the written live formula and exhaust its finite integer horizon.

    This routine does not import or execute downloaded verifier source.  Its
    full-grid check is stronger than the verifier's fixed random sample because
    every submitted key is an integer.
    """
    raw = payload.get("partial_function")
    if not isinstance(raw, dict) or not raw or len(raw) > 2000:
        raise ValueError("partial_function must contain 1..2000 entries")
    parsed: dict[int, float] = {}
    for raw_key, raw_value in raw.items():
        key = int(raw_key)
        value = float(raw_value)
        if key < 1 or not math.isfinite(value):
            raise ValueError("payload contains a nonpositive key or nonfinite value")
        parsed[key] = min(10.0, max(-10.0, value))
    total = sum(value / key for key, value in parsed.items())
    parsed[1] = parsed.get(1, 0.0) - total
    maximum_key = max(parsed)
    values = {
        point: sum(value * (point // key) for key, value in parsed.items())
        for point in range(1, 10 * maximum_key + 1)
    }
    score = -sum(value * math.log(key) / key for key, value in parsed.items())
    return {
        "parsed_coefficients": {str(key): parsed[key] for key in sorted(parsed)},
        "derived_f1_binary64": parsed[1],
        "full_integer_horizon": 10 * maximum_key,
        "horizon_states_checked": 10 * maximum_key,
        "horizon_minimum_binary64": min(values.values()),
        "horizon_maximum_binary64": max(values.values()),
        "horizon_argmax_first": min(
            point for point, value in values.items() if value == max(values.values())
        ),
        "passes_live_threshold": max(values.values()) <= 1.0001,
        "score_binary64": score,
    }
