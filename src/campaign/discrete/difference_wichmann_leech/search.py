#!/usr/bin/env python3
"""Exact Wichmann complete-ruler sweep for the Arena difference-bases task.

The implementation is clean-room.  It uses the gap word in Definition 16 of
Saarela--Vanhatalo (2026), checks selected constructions with integer bitsets,
and mirrors the frozen Arena verifier formula without importing verifier code.

For a nondegenerate Wichmann ruler ``w1(r,s)`` the gaps are

    1^r, r+1, (2r+1)^r, (4r+3)^s, (2r+2)^(r+1), 1^r.

The extended ruler appends ``(r+1)^i, j`` with ``1 <= j <= r+1``.
Only integer arithmetic is used until the literal verifier-compatible float is
reported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "difference-wichmann-leech-v1"
VERIFIER_SHA256 = "a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585"
LEADER_SCORE = 2.639027469506608
MIN_IMPROVEMENT = 1e-9
STRICT_GATE = LEADER_SCORE - MIN_IMPROVEMENT
MAX_MARKS = 2000
FOCUS_MARKS = 360
FOCUS_REQUIRED_COVERAGE = 49_110
NEAR_WINDOW = (49_000, 49_200)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    raw = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(raw, encoding="utf-8")
    os.replace(temporary, path)


def append_jsonl(path: Path, value: Any) -> None:
    raw = canonical_bytes(value) + b"\n"
    with path.open("ab") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def repeat(value: int, count: int) -> list[int]:
    if count < 0:
        raise ValueError("repeat count must be nonnegative")
    return [value] * count


def wichmann_gaps(r: int, s: int, i: int = 0, j: int = 0) -> list[int]:
    """Return the positive-gap representation of ``w1(r,s,i,j)``.

    ``j=0`` means that no final partial gap is appended.  If ``j>0``, the
    source restriction ``j <= r+1`` is enforced.  The novel lane uses r>=1;
    r=0 is retained only as an explicit degenerate control.
    """

    if r < 0 or s < 0 or i < 0:
        raise ValueError("r, s, and i must be nonnegative")
    if j < 0 or j > r + 1:
        raise ValueError("j must satisfy 0 <= j <= r+1")
    gaps = [
        *repeat(1, r),
        r + 1,
        *repeat(2 * r + 1, r),
        *repeat(4 * r + 3, s),
        *repeat(2 * r + 2, r + 1),
        *repeat(1, r),
        *repeat(r + 1, i),
    ]
    if j:
        gaps.append(j)
    if any(gap <= 0 for gap in gaps):
        raise AssertionError("the clean-room representation must be positive")
    return gaps


def wichmann_marks(r: int, s: int, i: int = 0, j: int = 0) -> list[int]:
    marks = [0]
    for gap in wichmann_gaps(r, s, i, j):
        marks.append(marks[-1] + gap)
    return marks


def base_cardinality(r: int, s: int) -> int:
    return 4 * r + s + 3


def base_length(r: int, s: int) -> int:
    return 4 * r * (r + s + 2) + 3 * s + 3


def extension_parameters(extra_marks: int, r: int) -> tuple[int, int]:
    """Maximize extension length for a fixed number of added marks."""

    if extra_marks < 0:
        raise ValueError("extra_marks must be nonnegative")
    if extra_marks == 0:
        return 0, 0
    return extra_marks - 1, r + 1


def maximum_length(r: int, s: int, total_marks: int) -> int:
    m0 = base_cardinality(r, s)
    if total_marks < m0:
        raise ValueError("total_marks is smaller than the base ruler")
    return base_length(r, s) + (total_marks - m0) * (r + 1)


def difference_bitset(marks: Iterable[int]) -> int:
    """Return a bitset whose bit d is one iff d is a nonnegative difference."""

    basis = sorted(set(int(value) for value in marks))
    if not basis or basis[0] < 0:
        raise ValueError("marks must be a nonempty set of nonnegative integers")
    mark_mask = 0
    for value in basis:
        mark_mask |= 1 << value
    differences = 0
    for value in basis:
        differences |= mark_mask >> value
    return differences


def first_missing_positive(differences: int, limit: int) -> int | None:
    """Return the first absent bit in 1..limit, or None if all are present."""

    if limit < 1:
        return None
    wanted = (1 << limit) - 1
    missing = (~(differences >> 1)) & wanted
    if missing == 0:
        return None
    lowest = missing & -missing
    return lowest.bit_length()


def literal_evaluate(marks: Iterable[int]) -> tuple[int, Fraction, float]:
    """Mirror the frozen verifier on an integer payload."""

    basis = sorted(set(int(value) for value in marks))
    if 0 not in basis:
        basis.insert(0, 0)
    if len(basis) > MAX_MARKS:
        raise ValueError("Arena schema allows at most 2000 unique elements")
    if not basis or basis[0] < 0:
        raise ValueError("Arena marks must be nonnegative")
    differences = difference_bitset(basis)
    maximum_difference = basis[-1] - basis[0]
    missing = first_missing_positive(differences, maximum_difference)
    coverage = maximum_difference if missing is None else missing - 1
    if coverage < 1:
        raise ValueError("the verifier score would be infinity")
    exact = Fraction(len(basis) ** 2, coverage)
    return coverage, exact, float(exact)


def minimum_coverage_for_float_gate(cardinality: int) -> int:
    """Find the literal integer coverage needed for Python-float gate passage."""

    estimate = max(1, math.floor(cardinality * cardinality / STRICT_GATE))
    while float(cardinality * cardinality / estimate) >= STRICT_GATE:
        estimate += 1
    while estimate > 1 and float(cardinality * cardinality / (estimate - 1)) < STRICT_GATE:
        estimate -= 1
    return estimate


@dataclass(frozen=True)
class FormulaChoice:
    label: str
    r: int
    s: int
    extra_marks: int

    @property
    def i(self) -> int:
        return extension_parameters(self.extra_marks, self.r)[0]

    @property
    def j(self) -> int:
        return extension_parameters(self.extra_marks, self.r)[1]

    @property
    def cardinality(self) -> int:
        return base_cardinality(self.r, self.s) + self.extra_marks

    @property
    def formula_length(self) -> int:
        return maximum_length(self.r, self.s, self.cardinality)

    @property
    def formula_score(self) -> Fraction:
        return Fraction(self.cardinality**2, self.formula_length)


def validated_record(choice: FormulaChoice) -> dict[str, Any]:
    marks = wichmann_marks(choice.r, choice.s, choice.i, choice.j)
    coverage, exact, score = literal_evaluate(marks)
    if len(marks) != choice.cardinality:
        raise AssertionError("formula cardinality disagrees with generated marks")
    if coverage != choice.formula_length or marks[-1] != choice.formula_length:
        raise AssertionError("exact bitset replay does not establish completeness")
    if exact != choice.formula_score:
        raise AssertionError("formula score disagrees with literal replay")
    required = minimum_coverage_for_float_gate(len(marks))
    return {
        **asdict(choice),
        "i": choice.i,
        "j": choice.j,
        "cardinality": len(marks),
        "maximum_mark": marks[-1],
        "coverage": coverage,
        "all_differences_1_through_v_bitset_verified": True,
        "score_exact_numerator": exact.numerator,
        "score_exact_denominator": exact.denominator,
        "score_float": score,
        "strict_gate": STRICT_GATE,
        "gate_clearing": score < STRICT_GATE,
        "minimum_coverage_for_gate_at_this_cardinality": required,
        "coverage_deficit_to_gate": max(0, required - coverage),
        "payload_sha256": sha256_value({"set": marks}),
        "marks_sha256": sha256_value(marks),
        "first_mark": marks[0],
        "last_mark": marks[-1],
    }


def choice_key(choice: FormulaChoice) -> tuple[Fraction, int, int, int, int]:
    return (
        choice.formula_score,
        choice.cardinality,
        choice.formula_length,
        choice.r,
        choice.s,
    )


def run_sweep(max_marks: int = MAX_MARKS) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if max_marks < 7 or max_marks > MAX_MARKS:
        raise ValueError("max_marks must be in 7..2000")

    global_best: FormulaChoice | None = None
    size_best: FormulaChoice | None = None
    near_best: FormulaChoice | None = None
    floor_best: FormulaChoice | None = None
    enumerated = 0
    parameter_hash = hashlib.sha256()

    for r in range(1, (max_marks - 3) // 4 + 1):
        for s in range(0, max_marks - 4 * r - 2):
            m0 = base_cardinality(r, s)
            length0 = base_length(r, s)
            enumerated += 1
            parameter_hash.update(f"{r},{s},{m0},{length0}\n".encode("ascii"))

            base = FormulaChoice("nondegenerate_global_best", r, s, 0)
            if global_best is None or choice_key(base) < choice_key(global_best):
                global_best = base

            if m0 <= FOCUS_MARKS <= max_marks:
                size = FormulaChoice("size_360_best", r, s, FOCUS_MARKS - m0)
                if size_best is None or choice_key(size) < choice_key(size_best):
                    size_best = size

            step = r + 1
            near_extra = max(0, (NEAR_WINDOW[0] - length0 + step - 1) // step)
            if m0 + near_extra <= max_marks:
                near = FormulaChoice("near_49k_window_best", r, s, near_extra)
                if near.formula_length <= NEAR_WINDOW[1]:
                    if near_best is None or choice_key(near) < choice_key(near_best):
                        near_best = near

            floor_extra = max(
                0, (FOCUS_REQUIRED_COVERAGE - length0 + step - 1) // step
            )
            if m0 + floor_extra <= max_marks:
                floor = FormulaChoice(
                    "coverage_at_least_49110_best", r, s, floor_extra
                )
                if floor_best is None or choice_key(floor) < choice_key(floor_best):
                    floor_best = floor

    if None in (global_best, size_best, near_best, floor_best):
        raise AssertionError("bounded sweep failed to populate every frontier")

    # r=0,s=1 is the degenerate {0,1,4,6} control already used by the prior
    # Singer four-block lane.  It is not counted as a novel Wichmann result.
    control = FormulaChoice("degenerate_r0_known_four_mark_control", 0, 1, 0)
    choices = [control, global_best, size_best, near_best, floor_best]
    records = [validated_record(choice) for choice in choices]

    proof = {
        "schema_version": SCHEMA_VERSION,
        "max_marks": max_marks,
        "nondegenerate_parameter_pairs_enumerated": enumerated,
        "enumerated_parameter_tuple_sha256": parameter_hash.hexdigest(),
        "r_range": [1, (max_marks - 3) // 4],
        "s_constraint": "0 <= s and 4*r+s+3 <= max_marks",
        "extension_reduction": {
            "base_marks": "m0=4*r+s+3",
            "base_length": "L0=4*r*(r+s+2)+3*s+3",
            "maximum_length_with_e_extra_marks": "L=L0+e*(r+1)",
            "fixed_base_monotonicity": (
                "Writing m=m0+e and L=(r+1)m+c gives "
                "c=L0-(r+1)m0=r*(3*s+1)+2*s>0 for r>=1; "
                "therefore m^2/L is strictly increasing in e."
            ),
            "consequence": (
                "The global optimum has e=0. For a coverage floor/window, "
                "the smallest feasible e is optimal for each (r,s)."
            ),
        },
        "near_window": list(NEAR_WINDOW),
        "coverage_floor": FOCUS_REQUIRED_COVERAGE,
        "focus_cardinality": FOCUS_MARKS,
        "all_selected_records_exact_bitset_verified": all(
            record["all_differences_1_through_v_bitset_verified"]
            for record in records
        ),
        "any_gate_clearer": any(record["gate_clearing"] for record in records),
    }
    return proof, records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-marks", type=int, default=MAX_MARKS)
    args = parser.parse_args()

    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite append-only run directory: {output}")
    output.mkdir(parents=True)

    config = {
        "schema_version": SCHEMA_VERSION,
        "max_marks": args.max_marks,
        "focus_marks": FOCUS_MARKS,
        "focus_required_coverage": FOCUS_REQUIRED_COVERAGE,
        "near_window": list(NEAR_WINDOW),
        "leader_score": LEADER_SCORE,
        "min_improvement": MIN_IMPROVEMENT,
        "strict_gate": STRICT_GATE,
        "verifier_sha256": VERIFIER_SHA256,
    }
    atomic_json(output / "config.json", config)
    append_jsonl(output / "events.jsonl", {"event": "config", **config})

    proof, records = run_sweep(args.max_marks)
    append_jsonl(output / "events.jsonl", {"event": "sweep_proof", **proof})
    for record in records:
        append_jsonl(output / "events.jsonl", {"event": "frontier", **record})

    summary = {
        "schema_version": SCHEMA_VERSION,
        "config": config,
        "proof": proof,
        "frontier": records,
        "outcome": "gate_clearer" if proof["any_gate_clearer"] else "quantified_no_go",
    }
    atomic_json(output / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if proof["any_gate_clearer"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
