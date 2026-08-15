#!/usr/bin/env python3
"""Exact typed first-pair DFS for low-boundary Heilbronn q-grid families."""

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
from hypergraph_dfs import SearchStopped, bit_indices, precompute_compatibility
from lattice_bnb import (
    COUNT,
    DEFAULT_SNAPSHOT,
    SLUG,
    atomic_json,
    barycentric_grid,
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


@dataclass
class Counters:
    nodes: int = 0
    capacity_prunes: int = 0
    color_prunes: int = 0


class TypedPairSearch:
    def __init__(
        self,
        grid: np.ndarray,
        minimum_numerator: int,
        side_counts: tuple[int, int, int],
        deadline: float,
        node_limit: int,
    ) -> None:
        self.grid = grid
        self.minimum_numerator = minimum_numerator
        self.side_counts = side_counts
        self.required = (*side_counts, COUNT - sum(side_counts))
        if self.required[-1] < 0:
            raise ValueError("side counts exceed total point count")
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
        ordered_categories = tuple(
            category
            for category, count in enumerate(self.required)
            for _ in range(count)
        )
        if len(ordered_categories) != COUNT:
            raise ValueError("typed category order does not contain 11 points")
        self.prefix_categories = ordered_categories[:2]
        self.root_pairs = self.build_root_pairs()
        prefix_counts = [0, 0, 0, 0]
        for category in self.prefix_categories:
            prefix_counts[category] += 1
        self.remaining_required = tuple(
            required - used
            for required, used in zip(self.required, prefix_counts, strict=True)
        )
        self.counters = Counters()
        self.solution: tuple[int, ...] | None = None

    def build_root_pairs(self) -> list[tuple[int, int]]:
        first_category, second_category = self.prefix_categories
        first_vertices = list(bit_indices(self.category_masks[first_category]))
        second_vertices = list(bit_indices(self.category_masks[second_category]))
        if first_category == second_category:
            return list(itertools.combinations(first_vertices, 2))
        return list(itertools.product(first_vertices, second_vertices))

    def check_limits(self) -> None:
        if (
            self.counters.nodes >= self.node_limit
            or time.perf_counter() >= self.deadline
        ):
            raise SearchStopped

    def adjacency(self, vertex: int, chosen: tuple[int, ...], mask: int) -> int:
        result = mask
        for selected in chosen:
            result &= self.compatibility[selected][vertex]
        return result

    def color_upper_bound(self, mask: int, chosen: tuple[int, ...]) -> int:
        uncolored = mask
        colors = 0
        while uncolored:
            colors += 1
            available = uncolored
            while available:
                bit = available & -available
                vertex = bit.bit_length() - 1
                uncolored ^= bit
                available &= ~bit
                available &= ~self.adjacency(vertex, chosen, mask)
        return colors

    def search_category(
        self,
        category: int,
        chosen: tuple[int, ...],
        available: int,
        current: tuple[int, ...],
    ) -> bool:
        self.counters.nodes += 1
        if not self.counters.nodes & 1023:
            self.check_limits()
        remaining = self.remaining_required[category] - len(current)
        if remaining == 0:
            if category == len(self.remaining_required) - 1:
                self.solution = chosen
                return True
            return self.search_category(category + 1, chosen, available, ())

        candidates = available & self.category_masks[category]
        if candidates.bit_count() < remaining:
            self.counters.capacity_prunes += 1
            return False
        if self.color_upper_bound(candidates, chosen) < remaining:
            self.counters.color_prunes += 1
            return False

        while candidates:
            bit = candidates & -candidates
            vertex = bit.bit_length() - 1
            candidates ^= bit
            category_prefix = self.category_masks[category] & ((1 << (vertex + 1)) - 1)
            next_available = available & ~category_prefix
            for selected in chosen:
                next_available &= self.compatibility[selected][vertex]
            feasible_capacity = True
            for future in range(category, len(self.remaining_required)):
                needed = self.remaining_required[future]
                if future == category:
                    needed -= len(current) + 1
                if (next_available & self.category_masks[future]).bit_count() < needed:
                    feasible_capacity = False
                    break
            if not feasible_capacity:
                self.counters.capacity_prunes += 1
                continue
            if self.search_category(
                category,
                chosen + (vertex,),
                next_available & ~(1 << vertex),
                current + (vertex,),
            ):
                return True
        return False

    def root_available(self, root: tuple[int, int]) -> int:
        available = self.all_mask & self.compatibility[root[0]][root[1]]
        for vertex in root:
            available &= ~(1 << vertex)
        for category in set(self.prefix_categories):
            last = max(
                vertex
                for vertex, vertex_category in zip(
                    root, self.prefix_categories, strict=True
                )
                if vertex_category == category
            )
            lower = self.category_masks[category] & ((1 << (last + 1)) - 1)
            available &= ~lower
        return available

    def run(
        self, start_root: int = 0, end_root: int | None = None
    ) -> tuple[str, int, int, int]:
        total = len(self.root_pairs)
        limit = total if end_root is None else min(end_root, total)
        if not 0 <= start_root <= limit:
            raise ValueError("root interval must satisfy 0 <= start <= end")
        completed = start_root
        try:
            for root_index in range(start_root, limit):
                self.check_limits()
                root = self.root_pairs[root_index]
                available = self.root_available(root)
                if self.search_category(0, root, available, ()):
                    return "feasible", root_index + 1, limit, total
                completed = root_index + 1
        except SearchStopped:
            return "unresolved", completed, limit, total
        status = (
            "infeasible" if start_root == 0 and limit == total else "segment_infeasible"
        )
        return status, completed, limit, total


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--denominators", type=parse_ints, default=parse_ints("30"))
    parser.add_argument("--side-counts", type=parse_ints, required=True)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--node-limit", type=int, default=100_000_000)
    parser.add_argument("--start-root", type=int, default=0)
    parser.add_argument("--end-root", type=int)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    parser.add_argument("--stamp")
    args = parser.parse_args()
    if len(args.side_counts) != 3 or sum(args.side_counts) > COUNT:
        raise ValueError("--side-counts requires three counts summing to at most 11")
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
        family="noncorner barycentric q-grid; typed first-pair partition",
        side_counts=side_counts,
    )

    records = []
    best_score = -np.inf
    best_payload: dict[str, object] | None = None
    for denominator in args.denominators:
        started = time.perf_counter()
        minimum_numerator = threshold_numerator(target, denominator)
        grid = barycentric_grid(denominator)
        search = TypedPairSearch(
            grid,
            minimum_numerator,
            side_counts,
            started + args.time_limit,
            args.node_limit,
        )
        precompute_seconds = time.perf_counter() - started
        status, completed, end_root, total_roots = search.run(
            args.start_root, args.end_root
        )
        record: dict[str, Any] = {
            "denominator": denominator,
            "minimum_numerator": minimum_numerator,
            "minimum_grid_score": minimum_numerator / (denominator * denominator),
            "grid_point_count": int(grid.shape[0]),
            "status": status,
            "prefix_categories": list(search.prefix_categories),
            "start_typed_pair": args.start_root,
            "end_typed_pair_exclusive": end_root,
            "completed_typed_pairs": completed,
            "total_typed_pairs": total_roots,
            "precompute_seconds": precompute_seconds,
            "elapsed_seconds": time.perf_counter() - started,
            "nodes": search.counters.nodes,
            "capacity_prunes": search.counters.capacity_prunes,
            "color_prunes": search.counters.color_prunes,
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
        "mode": "exact typed first-pair determinant-hypergraph DFS",
        "family": "noncorner barycentric lattice with fixed side counts",
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
