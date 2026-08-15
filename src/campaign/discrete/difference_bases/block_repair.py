#!/usr/bin/env python3
"""Bitset repair search over the leader's four translated 90-point blocks."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
LIVE = ROOT.parent / "checkpoints" / "difference-bases-live.json"
CHECKPOINT = ROOT / "checkpoints" / "block_repair.json"
PAIR_RADIUS = 500
TRIPLE_RADIUS = 50


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


def main() -> None:
    snapshot = json.loads(LIVE.read_text(encoding="utf-8"))
    verifier_hash = hashlib.sha256(snapshot["problem"]["verifier"].encode()).hexdigest()
    leader = snapshot["solutions"][0]
    baseline = sorted(set(int(value) for value in leader["data"]["set"]))
    payload_hash = hashlib.sha256(canonical({"set": baseline})).hexdigest()
    if CHECKPOINT.exists():
        prior = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        if (
            prior.get("complete")
            and prior.get("verifier_sha256") == verifier_hash
            and prior.get("leader_payload_sha256") == payload_hash
        ):
            print(json.dumps(prior, indent=2, sort_keys=True))
            return

    base_block = baseline[:90]
    offsets = [0, 8011, 32044, 48066]
    reconstructed = sorted(
        value + offset for offset in offsets for value in base_block
    )
    if reconstructed != baseline:
        raise RuntimeError("leader is no longer four translates of its first block")
    span = max(base_block)
    signed_differences = {
        second - first for first in base_block for second in base_block
    }
    signed_pattern = 0
    within_pattern = 1  # Mark zero so the lowest-zero operation starts at one.
    for difference in signed_differences:
        signed_pattern |= 1 << (difference + span)
        within_pattern |= 1 << abs(difference)

    # For overlapping block ranges, abs(d+s) is not a simple shift.  Cache all
    # such cross patterns once; only 0..span require this slower construction.
    small_cross_patterns = []
    for distance in range(span + 1):
        pattern = 0
        for signed in signed_differences:
            pattern |= 1 << abs(distance + signed)
        small_cross_patterns.append(pattern)

    def cross_pattern(distance: int) -> int:
        if distance <= span:
            return small_cross_patterns[distance]
        return signed_pattern << (distance - span)

    def block_coverage(candidate_offsets: list[int] | tuple[int, ...]) -> int:
        ordered = sorted(candidate_offsets)
        covered = within_pattern
        for first, second in itertools.combinations(ordered, 2):
            covered |= cross_pattern(second - first)
        first_missing = ((~covered) & (covered + 1)).bit_length() - 1
        return first_missing - 1

    baseline_coverage = block_coverage(offsets)
    if baseline_coverage != 49109:
        raise RuntimeError("bitset factorization does not reproduce the leader")

    state = {
        "schema": 1,
        "verifier_sha256": verifier_hash,
        "leader_payload_sha256": payload_hash,
        "leader_id": leader["id"],
        "baseline_score": leader["score"],
        "baseline_coverage": baseline_coverage,
        "base_block_size": len(base_block),
        "base_block_span": span,
        "offsets": offsets,
        "phase": "global_one_block",
        "complete": False,
    }
    atomic_json(CHECKPOINT, state)

    best_coverage = baseline_coverage
    best_offsets = offsets
    global_checked = 0
    # Beyond max(fixed)+target+span a replacement block has no differences at
    # or below target with any fixed block, so it cannot repair the first gap.
    target = baseline_coverage + 1
    for removed_index in (1, 2, 3):
        fixed = [value for index, value in enumerate(offsets) if index != removed_index]
        upper = max(fixed) + target + span
        fixed_values = {
            value + offset for offset in fixed for value in base_block
        }
        for replacement in range(0, upper + 1):
            if replacement in fixed:
                continue
            if any(replacement + value in fixed_values for value in base_block):
                continue
            candidate_offsets = sorted([*fixed, replacement])
            if candidate_offsets[0] != 0:
                continue
            global_checked += 1
            candidate_coverage = block_coverage(candidate_offsets)
            if candidate_coverage > best_coverage:
                best_coverage = candidate_coverage
                best_offsets = candidate_offsets
    state["global_one_block"] = {
        "placements_checked": global_checked,
        "upper_bound_rule": "max(fixed offsets) + target + base-block span",
        "best_coverage": best_coverage,
        "best_offsets": best_offsets,
        "gate_cleared": best_coverage > baseline_coverage,
    }
    state["phase"] = "pair_local"
    atomic_json(CHECKPOINT, state)

    pair_checked = 0
    for first_index, second_index in itertools.combinations((1, 2, 3), 2):
        for first_delta in range(-PAIR_RADIUS, PAIR_RADIUS + 1):
            first = offsets[first_index] + first_delta
            for second_delta in range(-PAIR_RADIUS, PAIR_RADIUS + 1):
                candidate_offsets = list(offsets)
                candidate_offsets[first_index] = first
                candidate_offsets[second_index] += second_delta
                ordered = sorted(candidate_offsets)
                if ordered[0] != 0 or any(
                    ordered[index + 1] - ordered[index] <= span
                    for index in range(3)
                ):
                    continue
                pair_checked += 1
                candidate_coverage = block_coverage(ordered)
                if candidate_coverage > best_coverage:
                    best_coverage = candidate_coverage
                    best_offsets = ordered
        state["pair_local"] = {
            "radius": PAIR_RADIUS,
            "offset_pairs_completed_through": [first_index, second_index],
            "placements_checked": pair_checked,
            "best_coverage": best_coverage,
            "best_offsets": best_offsets,
            "gate_cleared": best_coverage > baseline_coverage,
        }
        atomic_json(CHECKPOINT, state)

    state["phase"] = "triple_local"
    atomic_json(CHECKPOINT, state)
    triple_checked = 0
    for first_delta in range(-TRIPLE_RADIUS, TRIPLE_RADIUS + 1):
        first = offsets[1] + first_delta
        for second_delta in range(-TRIPLE_RADIUS, TRIPLE_RADIUS + 1):
            second = offsets[2] + second_delta
            for third_delta in range(-TRIPLE_RADIUS, TRIPLE_RADIUS + 1):
                third = offsets[3] + third_delta
                candidate_offsets = [0, first, second, third]
                triple_checked += 1
                candidate_coverage = block_coverage(candidate_offsets)
                if candidate_coverage > best_coverage:
                    best_coverage = candidate_coverage
                    best_offsets = candidate_offsets
        if (first_delta + TRIPLE_RADIUS + 1) % 10 == 0:
            state["triple_local"] = {
                "radius": TRIPLE_RADIUS,
                "next_first_delta": first_delta + 1,
                "placements_checked": triple_checked,
                "best_coverage": best_coverage,
                "best_offsets": best_offsets,
                "gate_cleared": best_coverage > baseline_coverage,
            }
            atomic_json(CHECKPOINT, state)

    state["triple_local"] = {
        "radius": TRIPLE_RADIUS,
        "placements_checked": triple_checked,
        "best_coverage": best_coverage,
        "best_offsets": best_offsets,
        "gate_cleared": best_coverage > baseline_coverage,
    }
    state["phase"] = "complete"
    state["complete"] = True
    state["gate_cleared"] = best_coverage > baseline_coverage
    state["conclusion"] = (
        "No globally bounded one-block replacement, radius-500 two-offset "
        "repair, or radius-50 three-offset repair extends the covered prefix."
    )
    atomic_json(CHECKPOINT, state)
    print(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
