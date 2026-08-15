#!/usr/bin/env python3
"""Deterministic changed-core evolutionary/LNS search for Difference Bases.

This is deliberately not a fixed construction-family search.  It maintains
arbitrary 360-mark integer sets and combines:

* exact Python-integer difference bitsets;
* multi-mark ruin/recreate with regret-like greedy beam repair;
* random, fragility, related-coordinate, rank-block, and gap-block destroys;
* positive gap-sequence transfers and scrambles;
* mark and gap crossovers between the public Singer incumbent, a scaled
  Wichmann ruler, and the evolving archive; and
* simulated-annealing acceptance plus adaptive operator weights.

The target is feasibility for every difference 1..49110.  At cardinality 360
that is exactly the first strict-gate coverage.  Every retained candidate is
also scored by the literal Arena formula.  No verifier code is imported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np


SCHEMA_VERSION = "difference-global-evolution-v2"
CARDINALITY = 360
TARGET = 49_110
TAIL = 2_048
LEADER_SCORE = 2.639027469506608
MIN_IMPROVEMENT = 1e-9
STRICT_GATE = LEADER_SCORE - MIN_IMPROVEMENT
VERIFIER_SHA256 = "a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585"
EXPECTED_LEADER_PAYLOAD_SHA256 = (
    "02b16426d5a66feb480d79c7e1c7c26bb18ffb50730c5a2c76861584ec59183b"
)
TARGET_MASK = ((1 << (TARGET + 1)) - 1) ^ 1
TAIL_MASK = ((1 << (TARGET + TAIL + 1)) - 1) ^ ((1 << (TARGET + 1)) - 1)

OPERATORS = (
    "ruin_random",
    "ruin_fragile_low",
    "ruin_fragile_high",
    "ruin_coordinate",
    "ruin_rank_block",
    "ruin_corresponding",
    "gap_transfer",
    "gap_scramble",
    "global_target_swap",
    "mark_crossover",
    "gap_crossover",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def normalize(values: Iterable[int]) -> tuple[int, ...]:
    ordered = sorted(set(int(value) for value in values))
    if not ordered:
        raise ValueError("empty candidate")
    shift = ordered[0]
    result = tuple(value - shift for value in ordered)
    if result[0] != 0 or any(value < 0 for value in result):
        raise AssertionError("normalization failed")
    return result


def difference_bits(values: Sequence[int]) -> int:
    mark_bits = 0
    for value in values:
        mark_bits |= 1 << int(value)
    covered = 1
    for value in values:
        covered |= mark_bits >> int(value)
    return covered


def first_missing(bits: int) -> int:
    if not bits & 1:
        raise ValueError("bit zero must be present")
    return ((~bits) & (bits + 1)).bit_length() - 1


def iter_set_bits(bits: int) -> Iterable[int]:
    while bits:
        lowest = bits & -bits
        yield lowest.bit_length() - 1
        bits ^= lowest


@dataclass(frozen=True)
class Metrics:
    missing_target: int
    coverage: int
    tail_present: int
    maximum_mark: int
    score_numerator: int
    score_denominator: int
    score_float: float | None
    gate_clearing: bool

    def key(self) -> tuple[int, int, int, int]:
        return (
            self.missing_target,
            -min(self.coverage, TARGET + TAIL),
            -self.tail_present,
            self.maximum_mark,
        )

    def energy(self) -> float:
        prefix_penalty = (TARGET - min(self.coverage, TARGET)) / TARGET
        tail_bonus = self.tail_present / max(1, TAIL)
        return float(self.missing_target) + 0.10 * prefix_penalty - 0.002 * tail_bonus


def metrics_from_bits(values: Sequence[int], bits: int) -> Metrics:
    missing = TARGET_MASK & ~bits
    coverage = first_missing(bits) - 1
    if coverage:
        exact = Fraction(len(values) ** 2, coverage)
        score_numerator = exact.numerator
        score_denominator = exact.denominator
        score: float | None = float(exact)
    else:
        # The frozen verifier returns +inf when difference 1 is absent.  JSON
        # receipts remain standards-compliant by using null and denominator 0.
        score_numerator = len(values) ** 2
        score_denominator = 0
        score = None
    return Metrics(
        missing_target=missing.bit_count(),
        coverage=coverage,
        tail_present=(TAIL_MASK & bits).bit_count(),
        maximum_mark=int(values[-1]),
        score_numerator=score_numerator,
        score_denominator=score_denominator,
        score_float=score,
        gate_clearing=(
            len(values) == CARDINALITY
            and score is not None
            and score < STRICT_GATE
        ),
    )


def evaluate(values: Iterable[int]) -> tuple[tuple[int, ...], int, Metrics]:
    ordered = normalize(values)
    if len(ordered) != CARDINALITY:
        raise ValueError(f"candidate has {len(ordered)} rather than 360 marks")
    bits = difference_bits(ordered)
    return ordered, bits, metrics_from_bits(ordered, bits)


def payload_sha(values: Sequence[int]) -> str:
    return sha256_value({"set": list(values)})


@dataclass
class Individual:
    values: tuple[int, ...]
    bits: int
    metrics: Metrics
    origin: str

    def receipt(self, include_values: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "origin": self.origin,
            "payload_sha256": payload_sha(self.values),
            "marks_sha256": sha256_value(list(self.values)),
            **asdict(self.metrics),
        }
        if include_values:
            result["set"] = list(self.values)
        return result


def make_individual(values: Iterable[int], origin: str) -> Individual:
    ordered, bits, metrics = evaluate(values)
    return Individual(ordered, bits, metrics, origin)


def load_incumbent(snapshot_path: Path) -> tuple[Individual, dict[str, Any]]:
    snapshot_raw = snapshot_path.read_bytes()
    snapshot = json.loads(snapshot_raw)
    solutions = snapshot["solutions"]
    leader = min(solutions, key=lambda record: (float(record["score"]), int(record["id"])))
    incumbent = make_individual(leader["data"]["set"], "public_singer_incumbent")
    if payload_sha(incumbent.values) != EXPECTED_LEADER_PAYLOAD_SHA256:
        raise RuntimeError("frozen incumbent payload changed")
    if incumbent.metrics.coverage != 49_109 or incumbent.metrics.missing_target != 1:
        raise RuntimeError("frozen incumbent no longer has the expected exact frontier")
    return incumbent, {
        "snapshot_sha256": hashlib.sha256(snapshot_raw).hexdigest(),
        "leader_id": int(leader["id"]),
        "leader_agent": leader.get("agentName"),
        "leader_payload_sha256": payload_sha(incumbent.values),
        "leader_score": float(leader["score"]),
    }


def wichmann_marks(r: int, s: int) -> tuple[int, ...]:
    gaps = [
        *([1] * r),
        r + 1,
        *([2 * r + 1] * r),
        *([4 * r + 3] * s),
        *([2 * r + 2] * (r + 1)),
        *([1] * r),
    ]
    marks = [0]
    for gap in gaps:
        marks.append(marks[-1] + gap)
    if len(marks) != CARDINALITY:
        raise AssertionError("chosen Wichmann donor must have 360 marks")
    return tuple(marks)


def scaled_wichmann(maximum: int) -> Individual:
    base = wichmann_marks(59, 121)
    scale = maximum / base[-1]
    values = tuple(round(value * scale) for value in base)
    if len(set(values)) != CARDINALITY:
        raise AssertionError("scaled Wichmann marks collided")
    return make_individual(values, "scaled_wichmann_59_121")


def mark_crossover_values(
    first: Sequence[int], second: Sequence[int], cut: int
) -> tuple[int, ...]:
    selected = list(first[:cut])
    seen = set(selected)
    for value in reversed(second):
        if value not in seen:
            selected.append(int(value))
            seen.add(int(value))
            if len(selected) == CARDINALITY:
                break
    if len(selected) < CARDINALITY:
        for value in reversed(first):
            if value not in seen:
                selected.append(int(value))
                seen.add(int(value))
                if len(selected) == CARDINALITY:
                    break
    return normalize(selected)


def gap_crossover_values(
    first: Sequence[int], second: Sequence[int], start: int, stop: int
) -> tuple[int, ...]:
    first_gaps = np.diff(np.asarray(first, dtype=np.int64))
    second_gaps = np.diff(np.asarray(second, dtype=np.int64))
    child_gaps = first_gaps.copy()
    child_gaps[start:stop] = second_gaps[start:stop]
    values = np.concatenate((np.asarray([0], dtype=np.int64), np.cumsum(child_gaps)))
    return tuple(map(int, values))


def seed_population(incumbent: Individual, wichmann: Individual) -> list[Individual]:
    seeds = [incumbent, wichmann]
    for cut in (60, 90, 120, 180, 240, 300):
        values = mark_crossover_values(incumbent.values, wichmann.values, cut)
        seeds.append(make_individual(values, f"mark_crossover_cut_{cut}"))
    for start, stop in ((0, 30), (45, 90), (90, 180), (180, 270), (270, 359)):
        values = gap_crossover_values(incumbent.values, wichmann.values, start, stop)
        seeds.append(make_individual(values, f"gap_crossover_{start}_{stop}"))
    return seeds


def target_swap_seeds(
    incumbent: Individual, max_position: int, keep: int = 12
) -> list[Individual]:
    """Best exact one-coordinate entrances to the target-covered basin.

    The incumbent covers every value below TARGET, so after removing mark i
    the only possible deficits are TARGET plus differences whose sole witness
    touched i.  Enumerating all old--new witnesses of TARGET is therefore an
    exact screen, not a heuristic approximation.
    """
    array = np.asarray(incumbent.values, dtype=np.int64)
    counts = np.zeros(int(array[-1]) + 1, dtype=np.uint16)
    for index, value in enumerate(array[:-1]):
        counts[array[index + 1 :] - value] += 1
    unique: list[set[int]] = []
    for value in array:
        differences = np.abs(array - value)
        only = differences[
            (differences > 0)
            & (differences < TARGET)
            & (counts[differences] == 1)
        ]
        unique.append(set(map(int, only)))
    candidates = sorted(
        {
            int(value + TARGET)
            for value in array
            if int(value + TARGET) <= max_position
        }
        | {int(value - TARGET) for value in array if int(value) >= TARGET}
    )
    old = set(map(int, array))
    records: list[tuple[int, int, int, int]] = []
    for index, removed in enumerate(array):
        if index == 0:
            continue
        remaining = old - {int(removed)}
        deficits = unique[index] | {TARGET}
        for candidate in candidates:
            if candidate in remaining or candidate == int(removed):
                continue
            recovered = {abs(candidate - value) for value in remaining}
            leftover = deficits - recovered
            records.append(
                (
                    len(leftover),
                    min(leftover) if leftover else TARGET + 1,
                    int(removed),
                    int(candidate),
                )
            )
    records.sort()
    result: list[Individual] = []
    seen: set[str] = set()
    for _missing, _first, removed, candidate in records:
        values = old - {removed}
        values.add(candidate)
        child = make_individual(
            values, f"target_swap_remove_{removed}_add_{candidate}"
        )
        digest = payload_sha(child.values)
        if digest in seen or not ((child.bits >> TARGET) & 1):
            continue
        seen.add(digest)
        result.append(child)
        if len(result) >= keep:
            break
    if not result:
        raise RuntimeError("no target-covering one-swap entrance found")
    return result


def fragility(values: Sequence[int]) -> np.ndarray:
    array = np.asarray(values, dtype=np.int64)
    counts = np.zeros(TARGET + 1, dtype=np.uint16)
    for index, value in enumerate(array[:-1]):
        differences = array[index + 1 :] - value
        differences = differences[differences <= TARGET]
        counts[differences] += 1
    result = np.zeros(len(array), dtype=np.int32)
    for index, value in enumerate(array):
        differences = np.abs(array - value)
        differences = differences[(differences > 0) & (differences <= TARGET)]
        result[index] = np.count_nonzero(counts[differences] == 1)
    result[0] = np.iinfo(np.int32).max
    return result


def choose_destroy(
    values: Sequence[int], operator: str, k: int, rng: np.random.Generator
) -> np.ndarray:
    n = len(values)
    eligible = np.arange(1, n, dtype=np.int64)
    if operator == "ruin_random":
        return np.sort(rng.choice(eligible, size=k, replace=False))
    if operator in ("ruin_fragile_low", "ruin_fragile_high"):
        scores = fragility(values)
        jitter = rng.random(n) * 0.01
        order = np.argsort(scores + jitter)
        if operator == "ruin_fragile_high":
            order = order[::-1]
        order = order[order != 0]
        width = min(len(order), max(k, 4 * k))
        return np.sort(rng.choice(order[:width], size=k, replace=False))
    if operator == "ruin_coordinate":
        anchor = int(rng.integers(1, n))
        distances = np.abs(np.asarray(values, dtype=np.int64) - values[anchor])
        distances[0] = np.iinfo(np.int64).max
        return np.sort(np.argsort(distances)[:k])
    if operator == "ruin_rank_block":
        start = int(rng.integers(1, n - k + 1))
        return np.arange(start, start + k, dtype=np.int64)
    if operator == "ruin_corresponding":
        residue = int(rng.integers(0, 90))
        candidates = [residue + 90 * block for block in range(4)]
        candidates = [index for index in candidates if 0 < index < n]
        remaining = [index for index in eligible if index not in candidates]
        while len(candidates) < k:
            candidates.append(int(rng.choice(remaining)))
            remaining.remove(candidates[-1])
        return np.sort(np.asarray(candidates[:k], dtype=np.int64))
    raise ValueError(operator)


def add_point_bits(bits: int, values: Sequence[int], point: int) -> int:
    result = bits
    for value in values:
        difference = abs(int(point) - int(value))
        result |= 1 << difference
    return result


def partial_key(values: Sequence[int], bits: int) -> tuple[int, int, int, int]:
    missing = (TARGET_MASK & ~bits).bit_count()
    coverage = first_missing(bits) - 1
    tail = (TAIL_MASK & bits).bit_count()
    return missing, -min(coverage, TARGET + TAIL), -tail, int(values[-1])


def candidate_pool(
    remaining: Sequence[int],
    removed: Sequence[int],
    banned: set[int],
    donor: Sequence[int],
    bits: int,
    rng: np.random.Generator,
    max_position: int,
    pool_size: int,
) -> np.ndarray:
    occupied = set(map(int, remaining))
    priority: set[int] = set(int(value) for value in removed if int(value) not in banned)
    priority.update(map(int, donor))

    radii = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)
    for center in removed:
        for radius in radii:
            priority.add(int(center) - radius)
            priority.add(int(center) + radius)

    array = np.asarray(remaining, dtype=np.int64)
    gaps = np.diff(array)
    if len(gaps):
        largest = np.argsort(gaps)[-min(64, len(gaps)) :]
        for index in largest:
            left = int(array[index])
            right = int(array[index + 1])
            priority.update((left + (right - left) // 2, left + (right - left) // 3))

    missing_values = list(iter_set_bits(TARGET_MASK & ~bits))
    if len(missing_values) > 64:
        fixed = missing_values[:24] + missing_values[-16:]
        sample = rng.choice(
            np.asarray(missing_values[24:-16], dtype=np.int64),
            size=24,
            replace=False,
        )
        missing_values = fixed + list(map(int, sample))
    witness_count = min(80, len(array))
    witness_indices = np.linspace(0, len(array) - 1, witness_count, dtype=np.int64)
    witnesses = set(map(int, array[witness_indices]))
    if len(array) > witness_count:
        witnesses.update(
            map(int, rng.choice(array, size=min(40, len(array)), replace=False))
        )
    for difference in missing_values:
        for witness in witnesses:
            priority.add(witness + int(difference))
            priority.add(witness - int(difference))

    random_count = max(512, pool_size // 2)
    priority.update(map(int, rng.integers(1, max_position + 1, size=random_count)))
    allowed = sorted(
        value
        for value in priority
        if 0 < value <= max_position and value not in occupied and value not in banned
    )
    if len(allowed) > pool_size:
        donor_set = set(map(int, donor))
        old_set = set(map(int, removed)) - banned
        must = [value for value in allowed if value in donor_set or value in old_set]
        rest = [value for value in allowed if value not in donor_set and value not in old_set]
        budget = max(0, pool_size - len(must))
        if len(rest) > budget:
            selected = rng.choice(np.asarray(rest, dtype=np.int64), size=budget, replace=False)
            rest = list(map(int, selected))
        allowed = sorted(set(must + rest))
    return np.asarray(allowed, dtype=np.int64)


def repair_ruin(
    parent: Individual,
    donor: Individual,
    operator: str,
    rng: np.random.Generator,
    destroy_size: int,
    pool_size: int,
    beam_width: int,
    branch_factor: int,
    max_position: int,
) -> Individual:
    removed_indices = choose_destroy(parent.values, operator, destroy_size, rng)
    removed = tuple(parent.values[int(index)] for index in removed_indices)
    remaining = tuple(
        value for index, value in enumerate(parent.values) if index not in set(removed_indices)
    )
    force_changes = min(destroy_size, max(3, int(rng.integers(3, min(7, destroy_size + 1)))))
    banned = set(
        map(
            int,
            rng.choice(np.asarray(removed, dtype=np.int64), size=force_changes, replace=False),
        )
    )
    base_bits = difference_bits(remaining)
    pool = candidate_pool(
        remaining,
        removed,
        banned,
        donor.values,
        base_bits,
        rng,
        max_position,
        pool_size,
    )
    if len(pool) < destroy_size:
        raise RuntimeError("repair candidate pool is too small")

    beam: list[tuple[tuple[int, ...], int]] = [(remaining, base_bits)]
    for _depth in range(destroy_size):
        expanded: list[tuple[tuple[int, ...], int]] = []
        for values, bits in beam:
            occupied = set(values)
            available = pool[np.fromiter((int(x) not in occupied for x in pool), bool)]
            if len(available) == 0:
                continue
            missing_bool = np.zeros(TARGET + 1, dtype=np.bool_)
            missing_indices = np.fromiter(
                iter_set_bits(TARGET_MASK & ~bits), dtype=np.int64
            )
            missing_bool[missing_indices] = True
            current = np.asarray(values, dtype=np.int64)
            differences = np.abs(available[:, None] - current[None, :])
            clipped = differences <= TARGET
            benefits = np.zeros(len(available), dtype=np.int32)
            if np.any(clipped):
                rows = np.broadcast_to(
                    np.arange(len(available), dtype=np.int64)[:, None],
                    differences.shape,
                )
                valid_rows = rows[clipped]
                valid_differences = differences[clipped]
                benefits = np.bincount(
                    valid_rows,
                    weights=missing_bool[valid_differences].astype(np.int8),
                    minlength=len(available),
                ).astype(np.int32)
            # Tiny deterministic jitter diversifies equal-benefit branches.
            scores = benefits.astype(np.float64) + rng.random(len(available)) * 1e-4
            take = min(len(available), max(branch_factor * 3, branch_factor))
            top = np.argpartition(scores, -take)[-take:]
            top = top[np.argsort(scores[top])[::-1]][:branch_factor]
            for index in top:
                point = int(available[int(index)])
                child_values = tuple(sorted((*values, point)))
                child_bits = add_point_bits(bits, values, point)
                expanded.append((child_values, child_bits))
        if not expanded:
            raise RuntimeError("repair beam exhausted")
        unique: dict[tuple[int, ...], tuple[tuple[int, ...], int]] = {}
        for state in expanded:
            unique[state[0]] = state
        beam = sorted(unique.values(), key=lambda state: partial_key(*state))[:beam_width]

    best_values, best_bits = min(beam, key=lambda state: partial_key(*state))
    if len(best_values) != CARDINALITY:
        raise AssertionError("repair did not restore cardinality")
    metrics = metrics_from_bits(best_values, best_bits)
    return Individual(
        best_values,
        best_bits,
        metrics,
        f"{operator}_k{destroy_size}_forced{force_changes}",
    )


def exact_difference_counts(values: Sequence[int], maximum: int) -> np.ndarray:
    array = np.asarray(values, dtype=np.int64)
    counts = np.zeros(max(maximum + 1, int(array[-1]) + 1), dtype=np.uint16)
    for index, value in enumerate(array[:-1]):
        differences = array[index + 1 :] - value
        differences = differences[differences <= maximum]
        counts[differences] += 1
    return counts


def global_target_swap(
    parent: Individual,
    rng: np.random.Generator,
    max_position: int,
    removal_count: int,
    chunk_size: int,
    approximate_top: int,
) -> Individual:
    """Full-coordinate target-preserving large-neighborhood move.

    For each selected removal, screen *every* integer coordinate in
    [1,max_position].  NumPy multiplicity scores are only an optimistic
    ranking: every retained coordinate is re-evaluated with the literal
    Python-integer bitset before comparison.  Requiring TARGET to remain
    represented keeps the search in the deliberately damaged basin rather
    than allowing the trivial move back to the public incumbent.
    """
    array = np.asarray(parent.values, dtype=np.int64)
    counts = exact_difference_counts(array, TARGET)
    damage: list[tuple[int, int]] = []
    for index, value in enumerate(array):
        if index == 0:
            continue
        differences = np.abs(array - value)
        critical = int(
            np.count_nonzero(
                (differences > 0)
                & (differences <= TARGET)
                & (counts[differences] == 1)
            )
        )
        damage.append((critical, index))
    damage.sort()
    low_count = min(len(damage), max(1, (3 * removal_count) // 4))
    removal_indices = [index for _score, index in damage[:low_count]]
    remaining_indices = np.asarray(
        [index for _score, index in damage[low_count:]], dtype=np.int64
    )
    random_count = min(removal_count - len(removal_indices), len(remaining_indices))
    if random_count:
        removal_indices.extend(
            map(int, rng.choice(remaining_indices, size=random_count, replace=False))
        )

    removal_frontiers: list[list[Individual]] = []
    for removal_index in removal_indices:
        removed = int(array[removal_index])
        remaining = np.delete(array, removal_index)
        base_bits = difference_bits(remaining)
        missing_bits = TARGET_MASK & ~base_bits
        missing_bool = np.zeros(TARGET + 1, dtype=np.int16)
        missing_indices = np.fromiter(
            iter_set_bits(missing_bits), dtype=np.int64
        )
        missing_bool[missing_indices] = 1
        occupied = np.zeros(max_position + 1, dtype=np.bool_)
        occupied[remaining[remaining <= max_position]] = True
        if removed <= max_position:
            occupied[removed] = True  # force a genuine topology change
        exact_rows: dict[tuple[int, ...], Individual] = {}
        for low in range(1, max_position + 1, chunk_size):
            candidates = np.arange(
                low, min(max_position + 1, low + chunk_size), dtype=np.int64
            )
            differences = np.abs(candidates[:, None] - remaining[None, :])
            within = differences <= TARGET
            # This may count a missing difference twice if two remaining marks
            # witness it.  It is deliberately only a generous screen.
            approximate = (
                missing_bool[np.minimum(differences, TARGET)] * within
            ).sum(axis=1, dtype=np.int32)
            approximate[occupied[candidates]] = -1
            take = min(approximate_top, len(candidates))
            top = np.argpartition(approximate, -take)[-take:]
            for candidate_index in top:
                candidate = int(candidates[int(candidate_index)])
                bits = add_point_bits(base_bits, remaining, candidate)
                if not ((bits >> TARGET) & 1):
                    continue
                values = tuple(sorted((*map(int, remaining), candidate)))
                metrics = metrics_from_bits(values, bits)
                child = Individual(
                    values,
                    bits,
                    metrics,
                    f"global_target_swap_remove_{removed}_add_{candidate}",
                )
                prior = exact_rows.get(values)
                if prior is None or child.metrics.key() < prior.metrics.key():
                    exact_rows[values] = child
        if exact_rows:
            removal_frontiers.append(
                sorted(exact_rows.values(), key=lambda item: item.metrics.key())[:4]
            )
    if not removal_frontiers:
        raise RuntimeError("global target swap found no admissible coordinate")
    ordered = sorted(
        (item for frontier in removal_frontiers for item in frontier),
        key=lambda item: item.metrics.key(),
    )
    if rng.random() < 0.35:
        # Choose the exact best completion for a sampled removal even when it
        # crosses a higher-deficit saddle.  This is the changed-core component;
        # the annealer decides whether the quantified damage is acceptable.
        frontier = removal_frontiers[int(rng.integers(0, len(removal_frontiers)))]
        return frontier[int(rng.integers(0, len(frontier)))]
    # Randomized elite choice provides deterministic diversity under the
    # checkpointed RNG while never selecting below the best missing stratum.
    best_missing = ordered[0].metrics.missing_target
    elite = [item for item in ordered if item.metrics.missing_target == best_missing]
    return elite[int(rng.integers(0, min(4, len(elite))))]


def gap_transfer(parent: Individual, rng: np.random.Generator) -> Individual:
    gaps = np.diff(np.asarray(parent.values, dtype=np.int64))
    moves = int(rng.integers(3, 13))
    for _ in range(moves):
        donors = np.flatnonzero(gaps > 1)
        if len(donors) == 0:
            break
        donor = int(rng.choice(donors))
        receiver = int(rng.integers(0, len(gaps)))
        if donor == receiver:
            continue
        amount = int(rng.integers(1, min(int(gaps[donor]) - 1, 64) + 1))
        gaps[donor] -= amount
        gaps[receiver] += amount
    values = np.concatenate((np.asarray([0], dtype=np.int64), np.cumsum(gaps)))
    return make_individual(map(int, values), f"gap_transfer_{moves}")


def gap_scramble(parent: Individual, rng: np.random.Generator) -> Individual:
    gaps = np.diff(np.asarray(parent.values, dtype=np.int64))
    length = int(rng.integers(3, 25))
    start = int(rng.integers(0, len(gaps) - length + 1))
    segment = gaps[start : start + length].copy()
    rng.shuffle(segment)
    gaps[start : start + length] = segment
    values = np.concatenate((np.asarray([0], dtype=np.int64), np.cumsum(gaps)))
    return make_individual(map(int, values), f"gap_scramble_{start}_{length}")


def archive_insert(archive: list[Individual], child: Individual, limit: int) -> None:
    digest = payload_sha(child.values)
    if any(payload_sha(item.values) == digest for item in archive):
        return
    archive.append(child)
    # Preserve several distinct missing-count strata, then fill by exact key.
    archive.sort(key=lambda item: item.metrics.key())
    kept: list[Individual] = []
    strata: set[int] = set()
    for item in archive:
        if item.metrics.missing_target not in strata and len(kept) < limit // 2:
            kept.append(item)
            strata.add(item.metrics.missing_target)
    for item in archive:
        if item not in kept and len(kept) < limit:
            kept.append(item)
    archive[:] = kept


def choose_operator(weights: dict[str, float], rng: np.random.Generator) -> str:
    values = np.asarray([weights[name] for name in OPERATORS], dtype=np.float64)
    values /= values.sum()
    return str(rng.choice(np.asarray(OPERATORS, dtype=object), p=values))


def choose_donor(
    archive: Sequence[Individual], wichmann: Individual, rng: np.random.Generator
) -> Individual:
    if rng.random() < 0.35:
        return wichmann
    return archive[int(rng.integers(0, len(archive)))]


def propose(
    parent: Individual,
    archive: Sequence[Individual],
    wichmann: Individual,
    operator: str,
    rng: np.random.Generator,
    config: dict[str, Any],
) -> Individual:
    donor = choose_donor(archive, wichmann, rng)
    if operator.startswith("ruin_"):
        destroy_size = int(rng.choice(np.asarray(config["destroy_sizes"], dtype=np.int64)))
        return repair_ruin(
            parent,
            donor,
            operator,
            rng,
            destroy_size,
            int(config["pool_size"]),
            int(config["beam_width"]),
            int(config["branch_factor"]),
            int(config["max_position"]),
        )
    if operator == "gap_transfer":
        return gap_transfer(parent, rng)
    if operator == "gap_scramble":
        return gap_scramble(parent, rng)
    if operator == "global_target_swap":
        return global_target_swap(
            parent,
            rng,
            int(config["max_position"]),
            int(config["global_swap_removals"]),
            int(config["global_swap_chunk"]),
            int(config["global_swap_top"]),
        )
    if operator == "mark_crossover":
        cut = int(rng.integers(30, CARDINALITY - 30))
        return make_individual(
            mark_crossover_values(parent.values, donor.values, cut),
            f"mark_crossover_cut_{cut}_{donor.origin}",
        )
    if operator == "gap_crossover":
        length = int(rng.integers(8, 91))
        start = int(rng.integers(0, CARDINALITY - 1 - length + 1))
        return make_individual(
            gap_crossover_values(parent.values, donor.values, start, start + length),
            f"gap_crossover_{start}_{start + length}_{donor.origin}",
        )
    raise ValueError(operator)


def temperature(iteration: int, total: int, initial: float, floor: float) -> float:
    phase = (iteration % max(1, total // 5)) / max(1, total // 5)
    return floor + initial * (1.0 - phase) ** 2


def checkpoint_state(
    path: Path,
    config_hash: str,
    source_hash: str,
    iteration: int,
    rng: np.random.Generator,
    current: Individual,
    best: Individual,
    target_best: Individual,
    archive: Sequence[Individual],
    weights: dict[str, float],
    stats: dict[str, Any],
) -> None:
    atomic_json(
        path,
        {
            "schema_version": SCHEMA_VERSION,
            "config_sha256": config_hash,
            "source_sha256": source_hash,
            "next_iteration": iteration,
            "rng_state": rng.bit_generator.state,
            "current": current.receipt(include_values=True),
            "best": best.receipt(include_values=True),
            "target_best": target_best.receipt(include_values=True),
            "archive": [item.receipt(include_values=True) for item in archive],
            "operator_weights": weights,
            "stats": stats,
        },
    )


def individual_from_receipt(record: dict[str, Any]) -> Individual:
    item = make_individual(record["set"], str(record["origin"]))
    if payload_sha(item.values) != record["payload_sha256"]:
        raise RuntimeError("checkpoint individual hash mismatch")
    return item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--checkpoint-every", type=int, default=250)
    parser.add_argument("--pool-size", type=int, default=1_500)
    parser.add_argument("--beam-width", type=int, default=3)
    parser.add_argument("--branch-factor", type=int, default=3)
    parser.add_argument("--max-position", type=int, default=65_000)
    parser.add_argument("--archive-size", type=int, default=24)
    parser.add_argument("--temperature", type=float, default=250.0)
    parser.add_argument("--temperature-floor", type=float, default=5.0)
    parser.add_argument("--global-swap-removals", type=int, default=16)
    parser.add_argument("--global-swap-chunk", type=int, default=4_096)
    parser.add_argument("--global-swap-top", type=int, default=96)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.iterations <= 0:
        raise SystemExit("iterations must be positive")
    run_dir = args.run_dir.resolve()
    config_path = run_dir / "config.json"
    events_path = run_dir / "events.jsonl"
    checkpoint_path = run_dir / "checkpoint.json"
    summary_path = run_dir / "summary.json"
    source_hash = sha256_file(Path(__file__).resolve())

    incumbent, snapshot_meta = load_incumbent(args.snapshot.resolve())
    wichmann = scaled_wichmann(incumbent.values[-1])
    seeds = seed_population(incumbent, wichmann)
    targeted_seeds = target_swap_seeds(incumbent, args.max_position)
    seeds.extend(targeted_seeds)
    config = {
        "schema_version": SCHEMA_VERSION,
        "iterations": args.iterations,
        "seed": args.seed,
        "checkpoint_every": args.checkpoint_every,
        "pool_size": args.pool_size,
        "beam_width": args.beam_width,
        "branch_factor": args.branch_factor,
        "max_position": args.max_position,
        "archive_size": args.archive_size,
        "temperature": args.temperature,
        "temperature_floor": args.temperature_floor,
        "global_swap_removals": args.global_swap_removals,
        "global_swap_chunk": args.global_swap_chunk,
        "global_swap_top": args.global_swap_top,
        "destroy_sizes": [3, 4, 6, 8, 12, 16],
        "target": TARGET,
        "cardinality": CARDINALITY,
        "strict_gate": STRICT_GATE,
        "verifier_sha256": VERIFIER_SHA256,
        "source_sha256": source_hash,
        **snapshot_meta,
        "literature": {
            "paperclip_alns": "PMC11470144 lines 115-149",
            "paperclip_lns_exact_repair": "PMC12832582 lines 130-214",
            "golomb_hybrid_evolution": "Dotu--Van Hentenryck 2005, pp. 1-4",
        },
    }
    config_hash = sha256_value(config)
    rng = np.random.default_rng(args.seed)
    weights = {name: 1.0 for name in OPERATORS}
    # The pilot showed this exact full-coordinate operator was the only one to
    # cross changed-core saddles while retaining TARGET.  Bias, but do not
    # monopolize, the adaptive portfolio toward it.
    weights["global_target_swap"] = 3.0
    stats: dict[str, Any] = {
        "proposals": 0,
        "accepted": 0,
        "improvements": 0,
        "target_improvements": 0,
        "max_changed_marks": 0,
        "max_changed_receipt": None,
        "operator_calls": {name: 0 for name in OPERATORS},
        "operator_accepts": {name: 0 for name in OPERATORS},
        "operator_bests": {name: 0 for name in OPERATORS},
    }
    archive: list[Individual] = []
    for seed_item in seeds:
        archive_insert(archive, seed_item, args.archive_size)
    current = min(targeted_seeds, key=lambda item: item.metrics.key())
    best = min(seeds, key=lambda item: item.metrics.key())
    target_best = current
    start_iteration = 0

    if args.resume:
        if not checkpoint_path.exists() or not config_path.exists():
            raise SystemExit("resume requested without config/checkpoint")
        prior_config = json.loads(config_path.read_text(encoding="utf-8"))
        if sha256_value(prior_config) != config_hash:
            raise SystemExit("resume config differs from frozen run config")
        state = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if state["config_sha256"] != config_hash or state["source_sha256"] != source_hash:
            raise SystemExit("resume checkpoint source/config mismatch")
        start_iteration = int(state["next_iteration"])
        rng.bit_generator.state = state["rng_state"]
        current = individual_from_receipt(state["current"])
        best = individual_from_receipt(state["best"])
        target_best = individual_from_receipt(state["target_best"])
        archive = [individual_from_receipt(item) for item in state["archive"]]
        weights = {str(key): float(value) for key, value in state["operator_weights"].items()}
        stats = state["stats"]
    else:
        if run_dir.exists():
            raise SystemExit(f"refusing to overwrite run directory: {run_dir}")
        run_dir.mkdir(parents=True)
        atomic_json(config_path, config)
        append_jsonl(events_path, {"event": "config", "config_sha256": config_hash, **config})
        for seed_item in seeds:
            append_jsonl(events_path, {"event": "seed", **seed_item.receipt()})

    started = time.monotonic()
    next_iteration = start_iteration
    for iteration in range(start_iteration, args.iterations):
        next_iteration = iteration + 1
        if iteration and iteration % max(200, args.iterations // 10) == 0:
            # Deterministic reheating/restart from a rank-biased archive member.
            rank = min(len(archive) - 1, int(rng.geometric(0.35)) - 1)
            target_archive = [item for item in archive if (item.bits >> TARGET) & 1]
            target_archive.sort(key=lambda item: item.metrics.key())
            current = target_archive[min(len(target_archive) - 1, rank)]
        operator = choose_operator(weights, rng)
        stats["proposals"] += 1
        stats["operator_calls"][operator] += 1
        try:
            child = propose(current, archive, wichmann, operator, rng, config)
        except RuntimeError as error:
            append_jsonl(
                events_path,
                {"event": "operator_failure", "iteration": iteration, "operator": operator, "error": str(error)},
            )
            weights[operator] = max(0.1, 0.98 * weights[operator])
            continue

        delta = child.metrics.energy() - current.metrics.energy()
        temp = temperature(iteration, args.iterations, args.temperature, args.temperature_floor)
        preserves_target_basin = bool((child.bits >> TARGET) & 1)
        accepted = preserves_target_basin and (
            delta <= 0 or rng.random() < math.exp(-delta / max(temp, 1e-12))
        )
        reward = 0.0
        if accepted:
            current = child
            stats["accepted"] += 1
            stats["operator_accepts"][operator] += 1
            archive_insert(archive, child, args.archive_size)
            reward += 1.0
            changed = len(set(incumbent.values) - set(child.values))
            if changed > int(stats["max_changed_marks"]):
                stats["max_changed_marks"] = changed
                stats["max_changed_receipt"] = child.receipt()
                append_jsonl(
                    events_path,
                    {
                        "event": "core_distance",
                        "iteration": iteration,
                        "changed_marks": changed,
                        **child.receipt(),
                    },
                )
                reward += 0.5
        if preserves_target_basin and child.metrics.key() < target_best.metrics.key():
            target_best = child
            archive_insert(archive, child, args.archive_size)
            stats["target_improvements"] += 1
            reward += 8.0
            append_jsonl(
                events_path,
                {
                    "event": "target_best",
                    "iteration": iteration,
                    "operator": operator,
                    "temperature": temp,
                    **target_best.receipt(),
                },
            )
        if child.metrics.key() < best.metrics.key():
            best = child
            stats["improvements"] += 1
            stats["operator_bests"][operator] += 1
            reward += 8.0
            append_jsonl(
                events_path,
                {
                    "event": "best",
                    "iteration": iteration,
                    "operator": operator,
                    "temperature": temp,
                    **best.receipt(),
                },
            )
        weights[operator] = max(0.1, 0.97 * weights[operator] + 0.03 * (1.0 + reward))

        if best.metrics.gate_clearing:
            checkpoint_state(
                checkpoint_path,
                config_hash,
                source_hash,
                iteration + 1,
                rng,
                current,
                best,
                target_best,
                archive,
                weights,
                stats,
            )
            break
        if (iteration + 1) % args.checkpoint_every == 0:
            checkpoint_state(
                checkpoint_path,
                config_hash,
                source_hash,
                iteration + 1,
                rng,
                current,
                best,
                target_best,
                archive,
                weights,
                stats,
            )
            append_jsonl(
                events_path,
                {
                    "event": "checkpoint",
                    "next_iteration": iteration + 1,
                    "elapsed_seconds": time.monotonic() - started,
                    "best": best.receipt(),
                    "current": current.receipt(),
                    "archive_size": len(archive),
                    "operator_weights": weights,
                },
            )

    completed_iterations = next_iteration
    checkpoint_state(
        checkpoint_path,
        config_hash,
        source_hash,
        completed_iterations,
        rng,
        current,
        best,
        target_best,
        archive,
        weights,
        stats,
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "config_sha256": config_hash,
        "source_sha256": source_hash,
        "completed_iterations": completed_iterations,
        "elapsed_seconds": time.monotonic() - started,
        "baseline": incumbent.receipt(),
        "wichmann_donor": wichmann.receipt(),
        "best": best.receipt(include_values=best.metrics.gate_clearing),
        "target_basin_best": target_best.receipt(),
        "gate_clearer": best.metrics.gate_clearing,
        "archive_frontier": [item.receipt() for item in archive],
        "operator_weights": weights,
        "stats": stats,
        "outcome": "gate_clearer" if best.metrics.gate_clearing else "bounded_frontier",
    }
    atomic_json(summary_path, summary)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0 if best.metrics.gate_clearing else 2


if __name__ == "__main__":
    raise SystemExit(main())
