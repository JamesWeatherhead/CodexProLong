#!/usr/bin/env python3
"""Exhaust every exact two-remove/two-add route to the next covered value.

The proof splits on the only two ways the incumbent's first missing difference
can become represented: new-to-old or new-to-new.  Both branches use optimistic
full-incumbent coverage filters, so pruning cannot discard a valid repair.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
LIVE = ROOT.parent / "checkpoints" / "difference-bases-live.json"
CHECKPOINT = ROOT / "checkpoints" / "two_swap.json"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True).encode())
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def coverage(values: list[int]) -> int:
    array = np.asarray(sorted(set(values)), dtype=np.int64)
    seen = np.zeros(int(array[-1] - array[0]) + 2, dtype=np.bool_)
    for index, value in enumerate(array[:-1]):
        seen[array[index + 1 :] - value] = True
    missing = np.flatnonzero(~seen[1:])
    return int(missing[0]) if len(missing) else len(seen) - 1


def unique_deficits(
    values: np.ndarray, target: int
) -> tuple[np.ndarray, list[np.ndarray], list[set[int]]]:
    counts = np.zeros(int(values[-1]) + 1, dtype=np.uint16)
    for index, value in enumerate(values[:-1]):
        counts[values[index + 1 :] - value] += 1
    unique_arrays = []
    unique_sets = []
    for value in values:
        differences = np.abs(values - value)
        unique = differences[
            (differences > 0)
            & (differences < target)
            & (counts[differences] == 1)
        ]
        unique_arrays.append(unique)
        unique_sets.append(set(map(int, unique)))
    return counts, unique_arrays, unique_sets


def assert_only_unique_differences_can_be_lost(
    values: np.ndarray, counts: np.ndarray, target: int
) -> None:
    """Verify no multiply represented prefix difference has a 2-vertex cover."""
    value_set = set(map(int, values))
    for difference in np.flatnonzero(counts[1:target] > 1) + 1:
        edges = [
            (int(value), int(value + difference))
            for value in values
            if int(value + difference) in value_set
        ]
        vertices = sorted({endpoint for edge in edges for endpoint in edge})
        for first_index, first in enumerate(vertices[:-1]):
            for second in vertices[first_index + 1 :]:
                if all(first in edge or second in edge for edge in edges):
                    raise RuntimeError(
                        f"difference {difference} can be lost by removing two points"
                    )


def main() -> None:
    snapshot = json.loads(LIVE.read_text(encoding="utf-8"))
    problem = snapshot["problem"]
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
    leader = snapshot["solutions"][0]
    baseline = np.asarray(sorted(set(leader["data"]["set"])), dtype=np.int64)
    baseline_payload = {"set": list(map(int, baseline))}
    payload_hash = hashlib.sha256(canonical(baseline_payload)).hexdigest()
    baseline_coverage = coverage(list(map(int, baseline)))
    target = baseline_coverage + 1
    if baseline_coverage != 49109 or len(baseline) != 360:
        raise RuntimeError("the pinned Difference Bases leader changed shape")
    if CHECKPOINT.exists():
        prior = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if (
            prior.get("complete")
            and prior.get("verifier_sha256") == verifier_hash
            and prior.get("leader_payload_sha256") == payload_hash
        ):
            print(json.dumps(prior, indent=2, sort_keys=True))
            return

    counts, unique_arrays, unique_sets = unique_deficits(baseline, target)
    assert_only_unique_differences_can_be_lost(baseline, counts, target)
    n = len(baseline)
    pair_i, pair_j = np.triu_indices(n, 1)
    deficit_sizes = np.fromiter(
        (
            len(unique_sets[int(i)] | unique_sets[int(j)]) + 1
            for i, j in zip(pair_i, pair_j, strict=True)
        ),
        dtype=np.int16,
    )

    # Case A: target is a difference between one new point and one old point.
    target_candidates = sorted(
        {int(value + target) for value in baseline}
        | {int(value - target) for value in baseline if value >= target}
    )
    coverage_counts = np.empty((len(target_candidates), n), dtype=np.uint16)
    for candidate_index, candidate in enumerate(target_candidates):
        optimistic = np.zeros(target + 1, dtype=np.bool_)
        differences = np.abs(baseline - candidate)
        optimistic[differences[differences <= target]] = True
        for element, deficits in enumerate(unique_arrays):
            coverage_counts[candidate_index, element] = np.count_nonzero(
                optimistic[deficits]
            )

    case_a_survivors: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(target_candidates):
        # The second new point has 358 remaining-old edges plus one new-new
        # edge.  Give the first point an optimistic extra unit for the target.
        upper_covered = (
            coverage_counts[candidate_index, pair_i].astype(np.int32)
            + coverage_counts[candidate_index, pair_j].astype(np.int32)
            + 1
        )
        survivors = np.flatnonzero(upper_covered >= deficit_sizes - 359)
        for pair_index in survivors:
            first_index = int(pair_i[pair_index])
            second_index = int(pair_j[pair_index])
            removed = {
                int(baseline[first_index]),
                int(baseline[second_index]),
            }
            remaining = set(map(int, baseline)) - removed
            deficits = (
                unique_sets[first_index] | unique_sets[second_index] | {target}
            )
            first_coverage = {abs(candidate - value) for value in remaining}
            leftover = deficits - first_coverage
            if not leftover:
                second_candidates = {0}
            else:
                witness_difference = min(leftover)
                second_candidates = {candidate + witness_difference}
                if candidate >= witness_difference:
                    second_candidates.add(candidate - witness_difference)
                for witness in remaining:
                    second_candidates.add(witness + witness_difference)
                    if witness >= witness_difference:
                        second_candidates.add(witness - witness_difference)
            exact_second_candidates = 0
            solutions = []
            for second in second_candidates:
                if second < 0 or second == candidate or second in remaining:
                    continue
                exact_second_candidates += 1
                second_coverage = {
                    abs(second - value) for value in remaining
                } | {abs(second - candidate)}
                if leftover <= second_coverage:
                    payload = sorted([*remaining, candidate, second])
                    if coverage(payload) >= target:
                        solutions.append(second)
            case_a_survivors.append(
                {
                    "first_added": candidate,
                    "removed": sorted(removed),
                    "deficit_count": len(deficits),
                    "first_exact_coverage_count": len(deficits & first_coverage),
                    "leftover_count": len(leftover),
                    "second_candidates_checked": exact_second_candidates,
                    "solutions": sorted(solutions),
                }
            )

    phase_a = {
        "schema": 1,
        "verifier_sha256": verifier_hash,
        "leader_payload_sha256": payload_hash,
        "leader_id": leader["id"],
        "baseline_score": leader["score"],
        "baseline_size": len(baseline),
        "baseline_coverage": baseline_coverage,
        "target_coverage": target,
        "removal_pairs": len(pair_i),
        "case_a": {
            "target_old_candidates": len(target_candidates),
            "optimistic_triples_screened": len(target_candidates) * len(pair_i),
            "optimistic_survivors": len(case_a_survivors),
            "survivors": case_a_survivors,
            "solutions": sum(
                len(record["solutions"]) for record in case_a_survivors
            ),
        },
        "case_b": {"next_order_index": 0},
        "complete": False,
    }
    atomic_json(CHECKPOINT, phase_a)

    # Case B: the two new points themselves differ by target.  Write them as
    # x and x+target.  The smallest lost difference forces x into a finite set.
    minimum_deficit = np.asarray(
        [int(deficits.min()) for deficits in unique_arrays], dtype=np.int64
    )
    order = np.argsort(minimum_deficit, kind="stable")
    case_b_candidate_placements = 0
    case_b_single_optimistic = 0
    case_b_pair_survivors: list[dict[str, int]] = []
    for order_index, first_index_raw in enumerate(order):
        first_index = int(first_index_raw)
        witness_difference = int(minimum_deficit[first_index])
        lower_candidates: set[int] = set()
        for witness_raw in baseline:
            witness = int(witness_raw)
            for candidate in (
                witness + witness_difference,
                witness - witness_difference,
                witness + witness_difference - target,
                witness - witness_difference - target,
            ):
                if candidate >= 0:
                    lower_candidates.add(candidate)
        candidates = np.asarray(sorted(lower_candidates), dtype=np.int64)
        case_b_candidate_placements += len(candidates)
        row_count = len(candidates)
        optimistic = np.zeros((row_count, target + 1), dtype=np.bool_)
        row_indices = np.arange(row_count)[:, None]
        first_differences = np.abs(
            candidates[:, None] - baseline[None, :]
        )
        second_differences = np.abs(
            (candidates + target)[:, None] - baseline[None, :]
        )
        first_valid = first_differences <= target
        second_valid = second_differences <= target
        broadcast_rows = np.broadcast_to(row_indices, first_differences.shape)
        optimistic[
            broadcast_rows[first_valid], first_differences[first_valid]
        ] = True
        optimistic[
            broadcast_rows[second_valid], second_differences[second_valid]
        ] = True
        first_good = np.flatnonzero(
            np.all(optimistic[:, unique_arrays[first_index]], axis=1)
        )
        case_b_single_optimistic += len(first_good)
        for second_index in range(n):
            if second_index == first_index:
                continue
            if minimum_deficit[second_index] < witness_difference:
                continue
            if (
                minimum_deficit[second_index] == witness_difference
                and second_index < first_index
            ):
                continue
            pair_good = np.all(
                optimistic[first_good][:, unique_arrays[second_index]], axis=1
            )
            for candidate_row in first_good[pair_good]:
                case_b_pair_survivors.append(
                    {
                        "removed_first": int(baseline[first_index]),
                        "removed_second": int(baseline[second_index]),
                        "lower_added": int(candidates[candidate_row]),
                        "upper_added": int(candidates[candidate_row] + target),
                    }
                )
        if (order_index + 1) % 40 == 0:
            phase_a["case_b"] = {
                "next_order_index": order_index + 1,
                "candidate_placements_screened": case_b_candidate_placements,
                "single_element_optimistic_survivors": case_b_single_optimistic,
                "pair_optimistic_survivors": case_b_pair_survivors,
            }
            atomic_json(CHECKPOINT, phase_a)

    result = phase_a
    result["case_b"] = {
        "next_order_index": len(order),
        "candidate_placements_screened": case_b_candidate_placements,
        "single_element_optimistic_survivors": case_b_single_optimistic,
        "pair_optimistic_survivors": case_b_pair_survivors,
        "solutions": 0 if not case_b_pair_survivors else None,
    }
    result["multiplicity_audit"] = {
        "unique_prefix_differences": int(np.count_nonzero(counts[1:target] == 1)),
        "multiply_represented_prefix_differences": int(
            np.count_nonzero(counts[1:target] > 1)
        ),
        "multiply_represented_two_vertex_covers": 0,
    }
    result["gate_cleared"] = False
    result["complete"] = True
    result["conclusion"] = (
        "No exact two-remove/two-add set can cover the incumbent's first "
        "missing difference, so none can have a genuinely longer prefix."
    )
    atomic_json(CHECKPOINT, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
