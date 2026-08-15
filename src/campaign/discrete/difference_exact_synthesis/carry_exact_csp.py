#!/usr/bin/env python3
"""Carry-exact global support synthesis for Arena ``difference-bases``.

The frozen leader is a perfect cyclic difference set ``R`` modulo 8011,
lifted through four common heights.  This program keeps the 90 cyclic residue
columns but gives *each column* an arbitrary nonempty support among a bounded
set of integer heights.  Column cardinalities may be born or deleted subject
only to the requested total size.

The perfect-difference property makes the formulation exact and small.  For
each nonzero residue there is one ordered pair of columns.  Consequently every
integer-prefix requirement becomes a binary table constraint on those two
column supports, including the quotient carry.  No modular score proxy or
floating determinant is used.  Any model is rebuilt as an integer payload and
replayed through the pinned Arena verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence

from ortools.sat.python import cp_model


ROOT = Path(__file__).resolve().parent
FROZEN_INPUTS = ROOT / "frozen_inputs.json"
PINNED_PUBLIC_SHA256 = "6159d144ae3c57dc740cd4fd5b54e1a467589c44b355dcef98ceb4b0bc6d0d69"
PINNED_VERIFIER_SHA256 = "a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585"
PINNED_LEADER_ID = 634
PINNED_LEADER_SCORE = 2.639027469506608
MODULUS = 8011


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical(value))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical(value).decode())
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def normalized(values: Iterable[int]) -> list[int]:
    ordered = sorted(set(int(value) for value in values))
    if not ordered:
        raise ValueError("empty construction")
    shift = ordered[0]
    return [value - shift for value in ordered]


def exact_coverage(values: Iterable[int]) -> tuple[int, list[int]]:
    ordered = normalized(values)
    bits = 1
    for index, first in enumerate(ordered[:-1]):
        for second in ordered[index + 1 :]:
            bits |= 1 << (second - first)
    missing = ((~bits) & (bits + 1)).bit_length() - 1
    return missing - 1, ordered


def evaluate_formula(payload: dict[str, Any]) -> float:
    """Clean-room mirror of the pinned verifier's score formula.

    Generated candidates are integer sets of valid schema size. The frozen
    verifier hash remains a provenance pin, but downloaded verifier code is
    never imported or executed by this public source.
    """

    values = payload.get("set")
    if not isinstance(values, list) or not 2 <= len(values) <= 500:
        return float("inf")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        return float("inf")
    coverage, ordered = exact_coverage(values)
    if len(ordered) != len(values) or coverage <= 0:
        return float("inf")
    return float(Fraction(len(ordered) ** 2, coverage))


def load_inputs() -> dict[str, Any]:
    frozen = json.loads(FROZEN_INPUTS.read_text(encoding="utf-8"))
    if frozen["source"]["public_snapshot_sha256"] != PINNED_PUBLIC_SHA256:
        raise RuntimeError("public snapshot provenance drift")
    leader = frozen["leader"]
    residues = [int(value) for value in frozen["core"]["residues"]]
    if sha256_json(residues) != frozen["core"]["residues_sha256"]:
        raise RuntimeError("frozen residue hash drift")
    if len(residues) != 90:
        raise RuntimeError("leader is not a 90-column lift")
    counts = Counter((a - b) % MODULUS for a in residues for b in residues if a != b)
    if set(counts) != set(range(1, MODULUS)) or set(counts.values()) != {1}:
        raise RuntimeError("residue core is not a perfect cyclic difference set")
    verifier_score = float(leader["score"])
    coverage = int(leader["coverage"])
    if int(leader["size"]) != 360 or coverage != 49109:
        raise RuntimeError("leader summary drift")
    if verifier_score != float(Fraction(int(leader["size"]) ** 2, coverage)):
        raise RuntimeError("leader score arithmetic drift")
    if verifier_score != PINNED_LEADER_SCORE:
        raise RuntimeError("leader score pin drift")
    min_improvement = float(leader["min_improvement"])
    gate_score = float(leader["gate_score"])
    if gate_score != verifier_score - min_improvement:
        raise RuntimeError("gate arithmetic drift")
    return {
        "leader": leader,
        "leader_payload_sha256": leader["payload_sha256"],
        "leader_score": verifier_score,
        "leader_coverage": coverage,
        "min_improvement": min_improvement,
        "gate_score": gate_score,
        "residues": residues,
        "evaluate": evaluate_formula,
    }


def required_coverage(size: int, gate_score: float) -> int:
    """Least integer coverage whose literal verifier float clears the gate."""
    coverage = max(1, int(size * size / gate_score) - 2)
    while float(Fraction(size * size, coverage)) >= gate_score:
        coverage += 1
    return coverage


def patterns(height_max: int) -> list[tuple[int, ...]]:
    """All supports that can participate in a 12-difference pair relation.

    Singletons can never cover the mandatory cross-column targets, because
    even a full opposing support has only ``height_max + 1 <= 8`` pairs in the
    frozen experiment.  Omitting them is therefore an exact presolve, not a
    heuristic restriction.
    """
    if height_max < 7:
        raise ValueError("height_max must be at least 7 to expose the first carry")
    return [
        support
        for size in range(2, height_max + 2)
        for support in itertools.combinations(range(height_max + 1), size)
    ]


def cross_requirements(gap: int, target: int, modulus: int = MODULUS) -> frozenset[int]:
    """Required values of ``height(high)-height(low)`` for one residue gap."""
    if not 0 < gap < modulus:
        raise ValueError("gap must be a nonzero canonical residue difference")
    needed: set[int] = set()
    quotient = 0
    while quotient * modulus + gap <= target:
        needed.add(quotient)
        quotient += 1
    quotient = 0
    reverse_residue = modulus - gap
    while quotient * modulus + reverse_residue <= target:
        needed.add(-(quotient + 1))
        quotient += 1
    return frozenset(needed)


def same_column_requirements(target: int, modulus: int = MODULUS) -> tuple[int, ...]:
    return tuple(range(1, target // modulus + 1))


def relation(
    support_patterns: Sequence[tuple[int, ...]], required: frozenset[int]
) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for first_index, first in enumerate(support_patterns):
        for second_index, second in enumerate(support_patterns):
            if required <= {a - b for a in first for b in second}:
                result.append((first_index, second_index))
    return result


def build_model(
    residues: Sequence[int],
    total_size: int,
    target: int,
    height_max: int,
) -> tuple[cp_model.CpModel, list[Any], list[tuple[int, ...]], dict[str, Any]]:
    support_patterns = patterns(height_max)
    internal_differences = [
        {a - b for a in support for b in support} for support in support_patterns
    ]
    model = cp_model.CpModel()
    variables = [
        model.NewIntVar(0, len(support_patterns) - 1, f"support_{index}")
        for index in range(len(residues))
    ]
    sizes = []
    size_table = [(index, len(support)) for index, support in enumerate(support_patterns)]
    for index, variable in enumerate(variables):
        size = model.NewIntVar(2, height_max + 1, f"size_{index}")
        model.AddAllowedAssignments([variable, size], size_table)
        sizes.append(size)
    model.Add(sum(sizes) == total_size)

    relation_cache: dict[frozenset[int], list[tuple[int, int]]] = {}
    class_counts: Counter[str] = Counter()
    class_sizes: dict[str, int] = {}
    for high in range(len(residues)):
        for low in range(high):
            gap = residues[high] - residues[low]
            required = cross_requirements(gap, target)
            if any(abs(value) > height_max for value in required):
                allowed: list[tuple[int, int]] = []
            else:
                if required not in relation_cache:
                    relation_cache[required] = relation(support_patterns, required)
                allowed = relation_cache[required]
            key = ",".join(map(str, sorted(required)))
            class_counts[key] += 1
            class_sizes[key] = len(allowed)
            model.AddAllowedAssignments([variables[high], variables[low]], allowed)

    for difference in same_column_requirements(target):
        if difference > height_max:
            model.AddBoolOr([])
            continue
        indicators = []
        indicator_table = [
            (index, int(difference in differences))
            for index, differences in enumerate(internal_differences)
        ]
        for index, variable in enumerate(variables):
            indicator = model.NewBoolVar(f"internal_{difference}_{index}")
            model.AddAllowedAssignments([variable, indicator], indicator_table)
            indicators.append(indicator)
        model.AddBoolOr(indicators)

    metadata = {
        "pattern_count": len(support_patterns),
        "pattern_size_histogram": dict(
            sorted(Counter(map(len, support_patterns)).items())
        ),
        "cross_requirement_class_counts": dict(sorted(class_counts.items())),
        "cross_relation_tuple_counts": dict(sorted(class_sizes.items())),
        "same_column_requirements": list(same_column_requirements(target)),
    }
    return model, variables, support_patterns, metadata


def replay_candidate(
    residues: Sequence[int],
    selected: Sequence[tuple[int, ...]],
    inputs: dict[str, Any],
) -> dict[str, Any]:
    values = normalized(
        residue + MODULUS * height
        for residue, support in zip(residues, selected, strict=True)
        for height in support
    )
    coverage, values = exact_coverage(values)
    score_fraction = Fraction(len(values) ** 2, coverage)
    verifier_score = float(inputs["evaluate"]({"set": values}))
    if verifier_score != float(score_fraction):
        raise RuntimeError("bitset and frozen verifier disagree")
    return {
        "size": len(values),
        "coverage": coverage,
        "score": verifier_score,
        "score_fraction": f"{score_fraction.numerator}/{score_fraction.denominator}",
        "gate_score": inputs["gate_score"],
        "gate_cleared": verifier_score < inputs["gate_score"],
        "payload_sha256": sha256_json({"set": values}),
        "payload": {"set": values},
    }


def solve_total(
    total_size: int,
    inputs: dict[str, Any],
    height_max: int,
    seconds: float,
    workers: int,
) -> dict[str, Any]:
    target = required_coverage(total_size, inputs["gate_score"])
    model, variables, support_patterns, metadata = build_model(
        inputs["residues"], total_size, target, height_max
    )
    model_bytes = model.Proto().SerializeToString(deterministic=True)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = 0
    solver.parameters.log_search_progress = False
    started = time.monotonic()
    status = solver.Solve(model)
    elapsed = time.monotonic() - started
    result: dict[str, Any] = {
        "schema": 1,
        "total_size": total_size,
        "target_coverage": target,
        "target_quotient_remainder": list(divmod(target, MODULUS)),
        "height_max": height_max,
        "status": solver.StatusName(status),
        "wall_seconds": elapsed,
        "conflicts": solver.NumConflicts(),
        "branches": solver.NumBranches(),
        "model_bytes": len(model_bytes),
        "model_sha256": sha256_bytes(model_bytes),
        "metadata": metadata,
    }
    if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        selected = [support_patterns[solver.Value(variable)] for variable in variables]
        result["support_size_histogram"] = dict(
            sorted(Counter(map(len, selected)).items())
        )
        result["support_sha256"] = sha256_json(selected)
        result["replay"] = replay_candidate(inputs["residues"], selected, inputs)
        result["selected_supports"] = selected
    return result


def parse_totals(text: str) -> list[int]:
    totals: set[int] = set()
    for piece in text.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "-" in piece:
            first, last = map(int, piece.split("-", 1))
            totals.update(range(first, last + 1))
        else:
            totals.add(int(piece))
    if not totals:
        raise ValueError("no totals selected")
    return sorted(totals)


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--totals", default="360-371")
    parser.add_argument("--height-max", type=int, default=7)
    parser.add_argument("--seconds", type=float, default=180.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()

    inputs = load_inputs()
    totals = parse_totals(args.totals)
    source_sha256 = sha256_file(Path(__file__))
    config = {
        "schema": 1,
        "method": "carry_exact_arbitrary_column_support_cp_sat",
        "totals": totals,
        "height_max": args.height_max,
        "seconds_per_total": args.seconds,
        "workers": args.workers,
        "modulus": MODULUS,
        "residue_count": len(inputs["residues"]),
        "residues_sha256": sha256_json(inputs["residues"]),
        "leader_id": PINNED_LEADER_ID,
        "leader_score": inputs["leader_score"],
        "leader_coverage": inputs["leader_coverage"],
        "leader_payload_sha256": inputs["leader_payload_sha256"],
        "min_improvement": inputs["min_improvement"],
        "gate_score": inputs["gate_score"],
        "public_snapshot_sha256": PINNED_PUBLIC_SHA256,
        "verifier_sha256": PINNED_VERIFIER_SHA256,
        "source_sha256": source_sha256,
        "ortools_version": getattr(__import__("ortools"), "__version__", "unknown"),
    }
    config["config_sha256"] = sha256_json(config)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    config_path = args.run_dir / "config.json"
    if config_path.exists():
        if json.loads(config_path.read_text(encoding="utf-8")) != config:
            raise RuntimeError("resume config mismatch")
    else:
        atomic_json(config_path, config)

    events_path = args.run_dir / "events.jsonl"
    events = read_events(events_path)
    if any(event.get("config_sha256") != config["config_sha256"] for event in events):
        raise RuntimeError("event/config mismatch")
    by_total = {int(event["total_size"]): event for event in events}
    gate_clearer: dict[str, Any] | None = None
    for total in totals:
        if total in by_total:
            print(json.dumps({"resume_skip": total, "status": by_total[total]["status"]}))
            if by_total[total].get("replay", {}).get("gate_cleared"):
                gate_clearer = by_total[total]
                break
            continue
        result = solve_total(
            total, inputs, args.height_max, args.seconds, args.workers
        )
        result["config_sha256"] = config["config_sha256"]
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        append_jsonl(events_path, result)
        by_total[total] = result
        print(
            json.dumps(
                {
                    "total": total,
                    "target": result["target_coverage"],
                    "status": result["status"],
                    "seconds": result["wall_seconds"],
                    "gate_cleared": result.get("replay", {}).get("gate_cleared", False),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        if result.get("replay", {}).get("gate_cleared"):
            gate_clearer = result
            atomic_json(args.run_dir / "gate_clearer.json", result)
            break

    completed = [by_total[total] for total in totals if total in by_total]
    summary = {
        "schema": 1,
        "config_sha256": config["config_sha256"],
        "requested_totals": totals,
        "completed_totals": [event["total_size"] for event in completed],
        "status_counts": dict(sorted(Counter(event["status"] for event in completed).items())),
        "gate_cleared": gate_clearer is not None,
        "all_requested_completed": len(completed) == len(totals),
        "events_sha256": sha256_file(events_path),
    }
    atomic_json(args.run_dir / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["all_requested_completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
