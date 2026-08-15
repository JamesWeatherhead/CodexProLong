#!/usr/bin/env python3
"""Exact full-horizon audit for the 127849-reach PNT candidates.

This is deliberately separate from the active optimizer and its fast float64
replayer.  It checks every integer state through ``10 * max_key`` using two
exact rational models:

* the submitted JSON decimal lexemes with exact normalization; and
* the exact binary64 coefficients produced by the verifier's parse, clip, and
  Python-sum normalization steps.

The decimal audit uses one common power-of-ten denominator and compares exact
integer numerators at every state.  It therefore corrects cumulative float64
drift in the earlier diagnostic receipt.  ``--official`` evaluates each
candidate in a new Python subprocess.  ``--refresh-live`` makes public GETs
only.  There is no submit, post, vote, or GitHub mutation path in this file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "reach_extend_127849_global_best.json"
HARDENED = ROOT / "reach_extend_127849_fullrange.json"
LIVE_CACHE = ROOT / "checkpoints" / "live.json"
RECEIPT = ROOT / "checkpoints" / "reach_extend_127849_exact_audit.json"

SOURCE_FILE_SHA256 = "44375c51913101f82f974117f588b7c9cdefbed05461a84d84634e2c0aacb693"
SOURCE_CANONICAL_SHA256 = "781490f6af8ae8719e43492748cd4557d1080b282657c6148960263835b9f3e2"
HARDENED_FILE_SHA256 = "d43c5531d562d06981a55829deb1c579a87a7c02405d69688dcc79e7f45f22c1"
HARDENED_CANONICAL_SHA256 = "4082fb8c9b71a034e9d56e7aa53d3ed86e5bf159513192f6af05a4b9c04ae9e5"
VERIFIER_SHA256 = "fd76a069b269a521d6ded609bd79185bf859df778283bebc37719dfd15b1ded6"

BASE_URL = "https://einsteinarena.com"
SLUG = "prime-number-theorem"
PROBLEM_ID = 7
VERIFIER_LIMIT = Fraction(10001, 10000)
IDEAL_LIMIT = Fraction(1, 1)
EXPECTED_EXACT_DECIMAL_ARGMAX = 1_254_707
PRIOR_LEADER_ID = 2470
PRIOR_LEADER_AGENT = "NumaroTech"
PRIOR_LEADER_SCORE = 0.9976488835182795
EXPECTED_MIN_IMPROVEMENT = 1e-6
EVALUATED_SUBMISSION_ID = 2506
EVALUATED_SUBMISSION_AGENT = "CodexProLong"
EVALUATED_SUBMISSION_SCORE = 0.9976572852677297
USER_AGENT = "Codex-read-only-pnt-exact-audit/1.0"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(
                json.dumps(
                    value,
                    ensure_ascii=False,
                    allow_nan=False,
                    indent=2,
                    sort_keys=True,
                ).encode("utf-8")
            )
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_candidate(
    path: Path, expected_file_sha256: str, expected_canonical_sha256: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_bytes = path.read_bytes()
    if sha256_bytes(raw_bytes) != expected_file_sha256:
        raise RuntimeError(f"candidate file changed: {path}")
    standard = json.loads(raw_bytes)
    lexical = json.loads(
        raw_bytes,
        parse_float=Decimal,
        parse_int=int,
        object_pairs_hook=reject_duplicate_keys,
    )
    if sha256_bytes(canonical(standard)) != expected_canonical_sha256:
        raise RuntimeError(f"candidate canonical payload changed: {path}")
    if set(standard) != {"partial_function"} or set(lexical) != {"partial_function"}:
        raise ValueError(f"unexpected candidate root keys: {path}")
    return standard, lexical


def validate_labels(raw: dict[str, Any]) -> list[str]:
    if not raw or len(raw) > 2_000:
        raise ValueError("partial_function must have 1..2000 entries")
    labels = list(raw)
    keys: list[int] = []
    for label in labels:
        key = int(label)
        if label != str(key) or key <= 0:
            raise ValueError(f"noncanonical positive-integer key: {label!r}")
        keys.append(key)
    if len(set(keys)) != len(keys):
        raise ValueError("keys collide after integer parsing")
    return labels


def fraction_packet(value: Fraction) -> dict[str, Any]:
    text = f"{value.numerator}/{value.denominator}"
    return {
        "denominator": str(value.denominator),
        "numerator": str(value.numerator),
        "sha256": sha256_bytes(text.encode("ascii")),
    }


def decimal_text(value: Fraction, precision: int = 90) -> str:
    with localcontext() as context:
        context.prec = precision
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def exact_decimal_horizon(lexical: dict[str, Any]) -> dict[str, Any]:
    raw = lexical["partial_function"]
    labels = validate_labels(raw)
    if "1" in raw:
        raise ValueError("frozen candidates are expected to let the verifier insert key 1")
    keys = [int(label) for label in labels]
    values = [
        max(Decimal(-10), min(Decimal(10), Decimal(raw[label]))) for label in labels
    ]
    if any(not value.is_finite() for value in values):
        raise ValueError("nonfinite value")

    decimal_places = max(max(0, -value.as_tuple().exponent) for value in values)
    scale = 10**decimal_places
    scaled_values = [int(value * scale) for value in values]
    if any(
        Decimal(scaled) / Decimal(scale) != value
        for scaled, value in zip(scaled_values, values, strict=True)
    ):
        raise AssertionError("common decimal scale did not preserve a coordinate")

    max_key = max(keys)
    upper = 10 * max_key
    events = [0] * (upper + 1)
    event_update_count = 0
    for key, value in zip(keys, scaled_values, strict=True):
        event_update_count += upper // key
        for point in range(key, upper + 1, key):
            events[point] += value

    # If T = sum f(k)/k = P/Q, then the normalized value at integer m is
    # C_m/scale - mP/(scale Q).  Multiplication by scale*Q lets every one
    # of the 1.28M comparisons be performed exactly with Python integers.
    normalization = sum(
        (
            Fraction(value, scale * key)
            for key, value in zip(keys, scaled_values, strict=True)
        ),
        Fraction(0),
    )
    p = normalization.numerator
    q = normalization.denominator
    pd = p * scale
    cumulative = 0
    best_numerator: int | None = None
    best_point = -1
    second_numerator: int | None = None
    second_point = -1
    for point in range(1, upper + 1):
        cumulative += events[point]
        numerator = cumulative * q - point * pd
        if best_numerator is None or numerator > best_numerator:
            second_numerator, second_point = best_numerator, best_point
            best_numerator, best_point = numerator, point
        elif second_numerator is None or numerator > second_numerator:
            second_numerator, second_point = numerator, point

    assert best_numerator is not None and second_numerator is not None
    common_denominator = scale * q
    maximum = Fraction(best_numerator, common_denominator)
    runner_up = Fraction(second_numerator, common_denominator)
    verifier_margin = VERIFIER_LIMIT - maximum
    ideal_margin = IDEAL_LIMIT - maximum
    scale_to_ideal = IDEAL_LIMIT / maximum
    if best_point != EXPECTED_EXACT_DECIMAL_ARGMAX:
        raise AssertionError(
            f"exact decimal argmax changed: {best_point} != {EXPECTED_EXACT_DECIMAL_ARGMAX}"
        )

    return {
        "all_real_points_covered_in_finite_horizon": True,
        "breakpoint_reason": (
            "All submitted keys are integers, so every floor sum is constant "
            "on each interval [m,m+1)."
        ),
        "common_decimal_places": decimal_places,
        "event_update_count": event_update_count,
        "exact_argmax": best_point,
        "exact_maximum": fraction_packet(maximum),
        "exact_maximum_decimal": decimal_text(maximum),
        "exact_runner_up_arg": second_point,
        "exact_runner_up_gap": fraction_packet(maximum - runner_up),
        "exact_runner_up_gap_decimal": decimal_text(maximum - runner_up),
        "exact_verifier_limit_margin": fraction_packet(verifier_margin),
        "exact_verifier_limit_margin_decimal": decimal_text(verifier_margin),
        "exact_ideal_limit_margin": fraction_packet(ideal_margin),
        "exact_ideal_limit_margin_decimal": decimal_text(ideal_margin),
        "finite_horizon_scale_to_ideal_limit": fraction_packet(scale_to_ideal),
        "finite_horizon_scale_to_ideal_limit_decimal": decimal_text(scale_to_ideal),
        "full_horizon_upper_inclusive": upper,
        "key_count": len(keys),
        "max_key": max_key,
        "normalization_total": fraction_packet(normalization),
        "normalization_total_decimal": decimal_text(normalization),
        "satisfies_ideal_leq_1_on_finite_horizon": ideal_margin >= 0,
        "satisfies_verifier_leq_1_0001_on_finite_horizon": verifier_margin >= 0,
    }


def exact_binary64_horizon(standard: dict[str, Any]) -> dict[str, Any]:
    raw = standard["partial_function"]
    labels = validate_labels(raw)
    parsed = {
        int(label): float(np.clip(float(raw[label]), -10.0, 10.0))
        for label in labels
    }
    if any(not math.isfinite(value) for value in parsed.values()):
        raise ValueError("nonfinite binary64 value")
    normalization = sum(value / key for key, value in parsed.items())
    parsed[1] = parsed.get(1, 0.0) - normalization

    fractions = {key: Fraction.from_float(value) for key, value in parsed.items()}
    # Every binary64 denominator is a power of two, so the largest denominator
    # is a common denominator for all exact coefficients.
    common_denominator = max(value.denominator for value in fractions.values())
    if any(common_denominator % value.denominator for value in fractions.values()):
        raise AssertionError("binary64 denominators were not nested powers of two")
    scaled_values = {
        key: value.numerator * (common_denominator // value.denominator)
        for key, value in fractions.items()
    }
    max_key = max(parsed)
    upper = 10 * max_key
    events = [0] * (upper + 1)
    event_update_count = 0
    for key, value in scaled_values.items():
        event_update_count += upper // key
        for point in range(key, upper + 1, key):
            events[point] += value

    cumulative = 0
    best: int | None = None
    best_point = -1
    second: int | None = None
    second_point = -1
    for point in range(1, upper + 1):
        cumulative += events[point]
        if best is None or cumulative > best:
            second, second_point = best, best_point
            best, best_point = cumulative, point
        elif second is None or cumulative > second:
            second, second_point = cumulative, point
    assert best is not None and second is not None

    maximum = Fraction(best, common_denominator)
    verifier_margin = VERIFIER_LIMIT - maximum
    return {
        "common_binary_denominator_power": common_denominator.bit_length() - 1,
        "event_update_count_including_normalized_key_1": event_update_count,
        "exact_argmax": best_point,
        "exact_maximum": fraction_packet(maximum),
        "exact_maximum_decimal": decimal_text(maximum),
        "exact_runner_up_arg": second_point,
        "exact_runner_up_gap_decimal": decimal_text(
            Fraction(best - second, common_denominator)
        ),
        "exact_verifier_limit_margin": fraction_packet(verifier_margin),
        "exact_verifier_limit_margin_decimal": decimal_text(verifier_margin),
        "normalization_key_1_binary64": repr(parsed[1]),
        "normalization_total_binary64": repr(normalization),
        "satisfies_verifier_leq_1_0001_on_finite_horizon": verifier_margin >= 0,
    }


def verifier_objective(standard: dict[str, Any]) -> float:
    raw = standard["partial_function"]
    labels = validate_labels(raw)
    parsed = {
        int(label): np.clip(float(raw[label]), -10.0, 10.0) for label in labels
    }
    normalization = sum(value / key for key, value in parsed.items())
    parsed[1] = parsed.get(1, 0.0) - normalization
    keys = np.asarray(list(parsed), dtype=np.float64)
    values = np.asarray(list(parsed.values()), dtype=np.float64)
    return float(-np.sum(values * np.log(keys) / keys))


def http_get_json(path: str) -> tuple[Any, str, str]:
    request = urllib.request.Request(
        BASE_URL + path,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    value = json.loads(raw)
    return value, sha256_bytes(raw), sha256_bytes(canonical(value))


FRESH_EVALUATOR = r"""
import json
import sys

packet = json.load(sys.stdin)
namespace = {}
exec(compile(packet["verifier"], "live_prime_number_theorem_verifier.py", "exec"), namespace)
score = float(namespace["evaluate"](packet["payload"]))
print(json.dumps({"score": score}, allow_nan=True))
"""


def fresh_process_evaluate(verifier: str, payload: dict[str, Any]) -> float:
    process = subprocess.run(
        [sys.executable, "-c", FRESH_EVALUATOR],
        input=json.dumps({"payload": payload, "verifier": verifier}),
        text=True,
        capture_output=True,
        check=True,
        timeout=600,
    )
    result = json.loads(process.stdout)
    return float(result["score"])


def selected_fields(value: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {key: value[key] for key in fields if key in value}


def load_live(
    refresh: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if refresh:
        problem, problem_raw_sha, problem_canonical_sha = http_get_json(
            f"/api/problems/{SLUG}"
        )
        board, board_raw_sha, board_canonical_sha = http_get_json(
            f"/api/leaderboard?problem_id={PROBLEM_ID}&limit=100"
        )
        best, best_raw_sha, best_canonical_sha = http_get_json(
            f"/api/solutions/best?problem_id={PROBLEM_ID}&limit=100"
        )
        submission, submission_raw_sha, submission_canonical_sha = http_get_json(
            f"/api/solutions/{EVALUATED_SUBMISSION_ID}"
        )
        prior, prior_raw_sha, prior_canonical_sha = http_get_json(
            f"/api/solutions/{PRIOR_LEADER_ID}"
        )
        if not isinstance(board, list) or not board:
            raise RuntimeError("live leaderboard is empty")
        if not isinstance(best, list) or not best:
            raise RuntimeError("live best-solution list is empty")
        if (
            int(submission.get("id", -1)) != EVALUATED_SUBMISSION_ID
            or submission.get("status") != "evaluated"
            or float(submission.get("score")) != EVALUATED_SUBMISSION_SCORE
        ):
            raise RuntimeError("evaluated submission #2506 changed")
        if (
            int(prior.get("id", -1)) != PRIOR_LEADER_ID
            or prior.get("status") != "evaluated"
            or float(prior.get("score")) != PRIOR_LEADER_SCORE
        ):
            raise RuntimeError("historical leader #2470 changed")
        current_solution = selected_fields(
            best[0], ("agentName", "createdAt", "id", "score")
        )
        public_state = {
            "current_best_solution": current_solution,
            "evaluated_submission": selected_fields(
                submission,
                ("createdAt", "error", "evaluatedAt", "id", "score", "status"),
            ),
            "evaluated_submission_agent": EVALUATED_SUBMISSION_AGENT,
            "evaluated_submission_is_current_best": (
                int(current_solution.get("id", -1)) == EVALUATED_SUBMISSION_ID
            ),
            "historical_prior_leader": {
                **selected_fields(
                    prior,
                    ("createdAt", "error", "evaluatedAt", "id", "score", "status"),
                ),
                "agentName": PRIOR_LEADER_AGENT,
            },
            "validated_by_public_get": True,
        }
        live_evidence = {
            "best_solutions_canonical_sha256": best_canonical_sha,
            "best_solutions_raw_response_sha256": best_raw_sha,
            "external_actions": "public GET only",
            "leaderboard_canonical_sha256": board_canonical_sha,
            "leaderboard_raw_response_sha256": board_raw_sha,
            "problem_canonical_sha256": problem_canonical_sha,
            "problem_raw_response_sha256": problem_raw_sha,
            "prior_solution_canonical_sha256": prior_canonical_sha,
            "prior_solution_raw_response_sha256": prior_raw_sha,
            "refreshed": True,
            "submission_canonical_sha256": submission_canonical_sha,
            "submission_raw_response_sha256": submission_raw_sha,
        }
        return problem, board[0], public_state, live_evidence

    cache = json.loads(LIVE_CACHE.read_text(encoding="utf-8"))
    cached_leader = selected_fields(
        cache["leader"], ("agentName", "createdAt", "id", "score")
    )
    cached_board_leader = {
        "agentName": cached_leader.get("agentName", PRIOR_LEADER_AGENT),
        "bestScore": cached_leader["score"],
        "rank": 1,
    }
    public_state = {
        "current_best_solution": cached_leader,
        "evaluated_submission": {
            "id": EVALUATED_SUBMISSION_ID,
            "score": EVALUATED_SUBMISSION_SCORE,
            "status": "expected; use --refresh-live to validate",
        },
        "evaluated_submission_agent": EVALUATED_SUBMISSION_AGENT,
        "evaluated_submission_is_current_best": None,
        "historical_prior_leader": {
            "agentName": PRIOR_LEADER_AGENT,
            "id": PRIOR_LEADER_ID,
            "score": PRIOR_LEADER_SCORE,
        },
        "validated_by_public_get": False,
    }
    live_evidence = {
        "cache_file_sha256": sha256_file(LIVE_CACHE),
        "external_actions": "none (offline cache)",
        "refreshed": False,
    }
    return cache["problem"], cached_board_leader, public_state, live_evidence


def audit_candidate(
    path: Path,
    expected_file_sha256: str,
    expected_canonical_sha256: str,
    verifier: str,
    official: bool,
    historical_leader_score: float,
    historical_gate_score: float,
    current_leader_score: float,
    current_new_submission_gate: float,
) -> dict[str, Any]:
    standard, lexical = load_candidate(
        path, expected_file_sha256, expected_canonical_sha256
    )
    decimal_audit = exact_decimal_horizon(lexical)
    binary_audit = exact_binary64_horizon(standard)
    score = verifier_objective(standard)
    official_score = fresh_process_evaluate(verifier, standard) if official else None
    if official_score is not None and official_score != score:
        raise AssertionError(f"fresh verifier score mismatch for {path}")
    if not decimal_audit["satisfies_verifier_leq_1_0001_on_finite_horizon"]:
        raise AssertionError(f"decimal full-horizon verifier constraint failed: {path}")
    if not binary_audit["satisfies_verifier_leq_1_0001_on_finite_horizon"]:
        raise AssertionError(f"binary64-coefficient full-horizon constraint failed: {path}")

    scale_to_ideal = Fraction(
        int(decimal_audit["finite_horizon_scale_to_ideal_limit"]["numerator"]),
        int(decimal_audit["finite_horizon_scale_to_ideal_limit"]["denominator"]),
    )
    with localcontext() as context:
        context.prec = 60
        ideal_scaled_score = Decimal(str(score)) * (
            Decimal(scale_to_ideal.numerator) / Decimal(scale_to_ideal.denominator)
        )
    return {
        "canonical_payload_sha256": expected_canonical_sha256,
        "exact_binary64_coefficient_horizon": binary_audit,
        "exact_decimal_lexeme_horizon": decimal_audit,
        "file_sha256": expected_file_sha256,
        "fresh_process_official_score": official_score,
        "fresh_process_official_score_ran": official,
        "equals_current_leader_score": score == current_leader_score,
        "historical_pre_submission_gate_cleared": score > historical_gate_score,
        "historical_pre_submission_gate_margin": score - historical_gate_score,
        "ideal_leq_1_finite_horizon_scaled_score": str(ideal_scaled_score),
        "ideal_leq_1_finite_horizon_scaled_score_clears_gate": (
            ideal_scaled_score > Decimal(str(historical_gate_score))
        ),
        "historical_leader_improvement": score - historical_leader_score,
        "path": str(path.relative_to(ROOT.parent.parent.parent)),
        "score_minus_current_leader": score - current_leader_score,
        "verifier_model_score": score,
        "would_clear_current_new_submission_gate": score > current_new_submission_gate,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-live",
        action="store_true",
        help="refresh the problem and leaderboard with public GET requests",
    )
    parser.add_argument(
        "--official",
        action="store_true",
        help="run each live verifier evaluation in a fresh Python subprocess",
    )
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    problem, current_leader, public_state, live_evidence = load_live(args.refresh_live)
    verifier = str(problem["verifier"])
    verifier_sha256 = sha256_bytes(verifier.encode("utf-8"))
    if verifier_sha256 != VERIFIER_SHA256:
        raise RuntimeError(
            f"live/cached verifier changed: {verifier_sha256} != {VERIFIER_SHA256}"
        )
    if problem["scoring"] != "maximize":
        raise RuntimeError("unexpected scoring direction")
    min_improvement = float(problem["minImprovement"])
    if min_improvement != EXPECTED_MIN_IMPROVEMENT:
        raise RuntimeError("live/cached minImprovement changed")
    historical_gate_score = PRIOR_LEADER_SCORE + min_improvement
    current_leader_score = float(
        current_leader.get("bestScore", current_leader.get("score"))
    )
    current_new_submission_gate = current_leader_score + min_improvement
    current_leader_summary = selected_fields(
        current_leader,
        ("agentName", "bestScore", "createdAt", "id", "rank", "score", "submissions"),
    )

    source = audit_candidate(
        SOURCE,
        SOURCE_FILE_SHA256,
        SOURCE_CANONICAL_SHA256,
        verifier,
        args.official,
        PRIOR_LEADER_SCORE,
        historical_gate_score,
        current_leader_score,
        current_new_submission_gate,
    )
    hardened = audit_candidate(
        HARDENED,
        HARDENED_FILE_SHA256,
        HARDENED_CANONICAL_SHA256,
        verifier,
        args.official,
        PRIOR_LEADER_SCORE,
        historical_gate_score,
        current_leader_score,
        current_new_submission_gate,
    )
    if not source["historical_pre_submission_gate_cleared"] or not hardened[
        "historical_pre_submission_gate_cleared"
    ]:
        raise AssertionError("candidate no longer clears the historical acceptance gate")

    receipt = {
        "analytic_caveat": {
            "all_x_ge_1_proven": False,
            "description_ideal_limit": 1,
            "hardened_satisfies_ideal_leq_1_on_finite_horizon": hardened[
                "exact_decimal_lexeme_horizon"
            ]["satisfies_ideal_leq_1_on_finite_horizon"],
            "reason": (
                "The exact audit proves the verifier's finite horizon and 1.0001 "
                "tolerance, not the stronger all-x>=1 inequality <=1 in the "
                "problem description."
            ),
            "source_satisfies_ideal_leq_1_on_finite_horizon": source[
                "exact_decimal_lexeme_horizon"
            ]["satisfies_ideal_leq_1_on_finite_horizon"],
        },
        "conclusion": {
            "evaluated_submission_2506_is_current_best": public_state[
                "evaluated_submission_is_current_best"
            ],
            "hardened_cleared_historical_acceptance_gate": hardened[
                "historical_pre_submission_gate_cleared"
            ],
            "hardened_verifier_horizon_valid": True,
            "recommended_payload": str(HARDENED.relative_to(ROOT)),
            "source_cleared_historical_acceptance_gate": source[
                "historical_pre_submission_gate_cleared"
            ],
            "source_required_scaling_for_verifier_horizon": False,
            "source_verifier_horizon_valid": True,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "current_snapshot": {
            "leader": current_leader_summary,
            "new_submission_required_score": current_new_submission_gate,
        },
        "evaluated_submission_evidence": public_state,
        "historical_acceptance_gate": {
            "leader": {
                "agentName": PRIOR_LEADER_AGENT,
                "id": PRIOR_LEADER_ID,
                "score": PRIOR_LEADER_SCORE,
            },
            "min_improvement": min_improvement,
            "required_score": historical_gate_score,
        },
        "hardened": hardened,
        "live_evidence": live_evidence,
        "models": {
            "binary64": (
                "Exact Fractions of coefficients after verifier float parsing, "
                "clipping, and Python-sum key-1 normalization."
            ),
            "decimal": (
                "Exact Fractions of submitted finite-decimal JSON lexemes with "
                "exact key-1 normalization; this is the mathematical payload model "
                "whose argmax is 1,254,707."
            ),
            "official": (
                "Unmodified hash-pinned verifier, including its fixed 10^7-sample "
                "binary64 matrix computation, run in fresh subprocesses."
            ),
        },
        "schema_version": 1,
        "source": source,
        "verifier": {
            "actual_constraint_limit": 1.0001,
            "hash_unchanged": True,
            "sha256": verifier_sha256,
        },
    }
    atomic_json(args.receipt.resolve(), receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
