#!/usr/bin/env python3
"""Exact determinant-hypergraph DFS for a structured Heilbronn lattice family.

The search chooses two non-corner q-grid points on each outer side and five
interior points.  A branch retains only future vertices compatible with every
already-selected pair, so each pruned bit is an exact forbidden active face.
Clique-color bounds in the conditional compatibility graph provide an upper
bound on how many points a category can still contribute.  D3 symmetry makes
the first side pair canonical.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from lattice_bnb import (
    COUNT,
    DEFAULT_SNAPSHOT,
    SLUG,
    atomic_json,
    barycentric_grid,
    determinant_numerator,
    exact_grid_score,
    load_snapshot,
    parse_ints,
    selected_payload,
    threshold_numerator,
)


def append_event(path: Path, **event: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def bit_indices(mask: int):
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


def side_code(
    grid: np.ndarray,
    selected: tuple[int, ...],
    denominator: int,
    side: int,
) -> tuple[int, ...]:
    coordinates = [coordinate for coordinate in range(3) if coordinate != side]
    values = tuple(sorted(int(grid[index, coordinates[0]]) for index in selected))
    reflected = tuple(sorted(denominator - value for value in values))
    return min(values, reflected)


def raw_side_code(
    grid: np.ndarray, selected: tuple[int, ...], side: int
) -> tuple[int, ...]:
    coordinates = [coordinate for coordinate in range(3) if coordinate != side]
    return tuple(sorted(int(grid[index, coordinates[0]]) for index in selected))


def precompute_compatibility(
    grid: np.ndarray, minimum_numerator: int
) -> list[list[int]]:
    count = grid.shape[0]
    compatibility = [[0] * count for _ in range(count)]
    for first in range(count - 1):
        remaining = np.arange(first + 1, count, dtype=np.int64)
        for second in remaining:
            numerators = determinant_numerator(
                grid[first],
                grid[second],
                grid,
            )
            mask = 0
            for third in np.flatnonzero(numerators >= minimum_numerator):
                mask |= 1 << int(third)
            compatibility[first][int(second)] = mask
            compatibility[int(second)][first] = mask
    return compatibility


@dataclass
class Counters:
    nodes: int = 0
    candidate_count_prunes: int = 0
    color_bound_prunes: int = 0
    symmetry_prunes: int = 0
    leaves: int = 0


class SearchStopped(Exception):
    pass


class HypergraphSearch:
    def __init__(
        self,
        grid: np.ndarray,
        denominator: int,
        minimum_numerator: int,
        deadline: float,
        node_limit: int,
        side_counts: tuple[int, int, int],
    ) -> None:
        self.grid = grid
        self.denominator = denominator
        self.minimum_numerator = minimum_numerator
        self.deadline = deadline
        self.node_limit = node_limit
        self.compatibility = precompute_compatibility(grid, minimum_numerator)
        self.all_mask = (1 << grid.shape[0]) - 1
        self.category_masks = [
            sum(1 << int(index) for index in np.flatnonzero(grid[:, coordinate] == 0))
            for coordinate in range(3)
        ]
        self.category_masks.append(
            sum(1 << int(index) for index in np.flatnonzero(np.all(grid > 0, axis=1)))
        )
        self.side_counts = side_counts
        self.required = (*side_counts, COUNT - sum(side_counts))
        if self.required[-1] < 0:
            raise ValueError("side counts exceed the total point count")
        self.equal_side_counts = len(set(side_counts)) == 1
        self.reflection_reduction = side_counts[1] == side_counts[2]
        self.counters = Counters()
        self.solution: tuple[int, ...] | None = None

    def conditional_adjacency(
        self, vertex: int, chosen: tuple[int, ...], category_mask: int
    ) -> int:
        adjacency = category_mask
        for selected in chosen:
            adjacency &= self.compatibility[selected][vertex]
        return adjacency

    def color_upper_bound(self, mask: int, chosen: tuple[int, ...]) -> int:
        """Greedy proper coloring: any compatible clique uses <= colors."""
        uncolored = mask
        colors = 0
        while uncolored:
            colors += 1
            available = uncolored
            while available:
                bit = available & -available
                vertex = bit.bit_length() - 1
                uncolored ^= bit
                adjacency = self.conditional_adjacency(vertex, chosen, mask)
                available &= ~bit
                available &= ~adjacency
        return colors

    def check_limits(self) -> None:
        if (
            self.counters.nodes >= self.node_limit
            or time.perf_counter() >= self.deadline
        ):
            raise SearchStopped

    def search_category(
        self,
        category: int,
        chosen: tuple[int, ...],
        available: int,
        current: tuple[int, ...],
        root_code: tuple[int, ...],
    ) -> bool:
        self.counters.nodes += 1
        if not self.counters.nodes & 1023:
            self.check_limits()

        remaining = self.required[category] - len(current)
        if remaining == 0:
            if category in (1, 2):
                code = side_code(self.grid, current, self.denominator, category)
                if self.equal_side_counts and code < root_code:
                    self.counters.symmetry_prunes += 1
                    return False
            if category == len(self.required) - 1:
                self.counters.leaves += 1
                self.solution = chosen
                return True
            return self.search_category(
                category + 1,
                chosen,
                available,
                (),
                root_code,
            )

        candidates = available & self.category_masks[category]
        if candidates.bit_count() < remaining:
            self.counters.candidate_count_prunes += 1
            return False
        if (
            remaining >= 2
            and candidates.bit_count() >= remaining + 2
            and self.color_upper_bound(candidates, chosen) < remaining
        ):
            self.counters.color_bound_prunes += 1
            return False

        while candidates:
            bit = candidates & -candidates
            vertex = bit.bit_length() - 1
            candidates ^= bit
            # Increasing labels only within a category.
            category_prefix = self.category_masks[category] & ((1 << (vertex + 1)) - 1)
            next_available = available & ~category_prefix
            for selected in chosen:
                next_available &= self.compatibility[selected][vertex]

            # Necessary capacity in every current/future category.
            feasible_capacity = True
            for future in range(category, len(self.required)):
                needed = self.required[future]
                if future == category:
                    needed -= len(current) + 1
                if (next_available & self.category_masks[future]).bit_count() < needed:
                    feasible_capacity = False
                    break
            if not feasible_capacity:
                self.counters.candidate_count_prunes += 1
                continue
            if self.search_category(
                category,
                chosen + (vertex,),
                next_available & ~(1 << vertex),
                current + (vertex,),
                root_code,
            ):
                return True
        return False

    def internally_compatible(self, selected: tuple[int, ...]) -> bool:
        for first, second, third in itertools.combinations(selected, 3):
            if not (self.compatibility[first][second] & (1 << third)):
                return False
        return True

    def root_sets(self) -> list[tuple[int, ...]]:
        side = list(bit_indices(self.category_masks[0]))
        roots = []
        for selected in itertools.combinations(side, self.required[0]):
            if not self.internally_compatible(selected):
                continue
            raw = raw_side_code(self.grid, selected, 0)
            reflected = tuple(sorted(self.denominator - value for value in raw))
            if self.reflection_reduction and raw > reflected:
                continue
            roots.append(selected)
        return sorted(
            roots,
            key=lambda item: side_code(self.grid, item, self.denominator, 0),
        )

    def run(
        self, start_root: int = 0, end_root: int | None = None
    ) -> tuple[str, int, int, int]:
        roots = self.root_sets()
        limit = len(roots) if end_root is None else min(end_root, len(roots))
        if not 0 <= start_root <= limit:
            raise ValueError("root interval must satisfy 0 <= start <= end")
        completed = start_root
        try:
            for root_index in range(start_root, limit):
                self.check_limits()
                selected = roots[root_index]
                available = self.all_mask
                for first, second in itertools.combinations(selected, 2):
                    available &= self.compatibility[first][second]
                for vertex in selected:
                    available &= ~(1 << vertex)
                root_code = side_code(self.grid, selected, self.denominator, 0)
                if self.search_category(
                    1,
                    selected,
                    available,
                    (),
                    root_code,
                ):
                    return "feasible", root_index + 1, limit, len(roots)
                completed = root_index + 1
        except SearchStopped:
            return "unresolved", completed, limit, len(roots)
        status = (
            "infeasible"
            if start_root == 0 and limit == len(roots)
            else "segment_infeasible"
        )
        return status, completed, limit, len(roots)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument(
        "--denominators", type=parse_ints, default=parse_ints("8,10,12,14,16,18,20")
    )
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--node-limit", type=int, default=10_000_000)
    parser.add_argument("--side-counts", type=parse_ints, default=parse_ints("2,2,2"))
    parser.add_argument("--start-root", type=int, default=0)
    parser.add_argument(
        "--end-root",
        type=int,
        help="exclusive side-zero root-set bound for disjoint resumable segments",
    )
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    parser.add_argument("--stamp")
    args = parser.parse_args()
    if len(args.side_counts) != 3 or sum(args.side_counts) > COUNT:
        raise ValueError(
            "--side-counts must contain three nonnegative counts summing to at most 11"
        )
    side_counts = tuple(args.side_counts)

    snapshot, live_score, target, verifier_hash = load_snapshot(args.snapshot)
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    append_event(
        events,
        event="start",
        snapshot=str(args.snapshot.resolve()),
        snapshot_sha256=hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
        verifier_sha256=verifier_hash,
        live_score=live_score,
        target=target,
        side_counts=side_counts,
    )

    records = []
    best_score = -np.inf
    best_payload: dict[str, object] | None = None
    for denominator in args.denominators:
        minimum_numerator = threshold_numerator(target, denominator)
        grid = barycentric_grid(denominator)
        started = time.perf_counter()
        search = HypergraphSearch(
            grid,
            denominator,
            minimum_numerator,
            started + args.time_limit,
            args.node_limit,
            side_counts,
        )
        precompute_seconds = time.perf_counter() - started
        status, completed_roots, end_root, total_roots = search.run(
            args.start_root, args.end_root
        )
        elapsed = time.perf_counter() - started
        record: dict[str, Any] = {
            "denominator": denominator,
            "minimum_numerator": minimum_numerator,
            "minimum_grid_score": minimum_numerator / (denominator * denominator),
            "grid_point_count": int(grid.shape[0]),
            "root_set_count": total_roots,
            "start_root_set": args.start_root,
            "end_root_set_exclusive": end_root,
            "completed_root_sets": completed_roots,
            "status": status,
            "precompute_seconds": precompute_seconds,
            "elapsed_seconds": elapsed,
            "nodes": search.counters.nodes,
            "candidate_count_prunes": search.counters.candidate_count_prunes,
            "color_bound_prunes": search.counters.color_bound_prunes,
            "symmetry_prunes": search.counters.symmetry_prunes,
            "leaves": search.counters.leaves,
        }
        if search.solution is not None:
            selected = np.asarray(search.solution, dtype=np.int64)
            exact_numerator, score = exact_grid_score(grid, selected, denominator)
            payload = selected_payload(grid, selected, denominator)
            record.update(
                {
                    "selected_indices": selected.tolist(),
                    "barycentric_integer_points": payload["barycentric_integer_points"],
                    "exact_minimum_numerator": exact_numerator,
                    "exact_score": score,
                }
            )
            if score > best_score:
                best_score = score
                best_payload = {"points": payload["points"]}
                atomic_json(run_dir / "best.json", best_payload)
        records.append(record)
        atomic_json(run_dir / f"q{denominator:03d}.json", record)
        atomic_json(run_dir / "checkpoint.json", {"completed": records})
        append_event(events, event="denominator_complete", **record)

    summary = {
        "slug": SLUG,
        "mode": "exact determinant-hypergraph branch-and-bound",
        "family": "barycentric lattice with fixed non-corner side counts",
        "side_counts": side_counts,
        "snapshot": str(args.snapshot.resolve()),
        "public_solution_count": len(snapshot["solutions"]),
        "public_thread_count": len(snapshot["threads"]),
        "verifier_sha256": verifier_hash,
        "live_score": live_score,
        "target_strictly_above": target,
        "denominators": args.denominators,
        "proved_infeasible": [
            record["denominator"]
            for record in records
            if record["status"] == "infeasible"
        ],
        "unresolved": [
            record["denominator"]
            for record in records
            if record["status"] == "unresolved"
        ],
        "feasible": [
            record["denominator"]
            for record in records
            if record["status"] == "feasible"
        ],
        "total_nodes": int(sum(record["nodes"] for record in records)),
        "best_exact_grid_score": None if best_payload is None else best_score,
        "gate_clearing": bool(best_payload is not None and best_score > target),
        "payload": None
        if best_payload is None
        else str((run_dir / "best.json").resolve()),
        "results": records,
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, event="complete", summary=summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
