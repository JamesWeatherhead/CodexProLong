#!/usr/bin/env python3
"""Exact pair-partitioned DFS for fully interior Heilbronn q-grid sets."""

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
from hypergraph_dfs import SearchStopped, precompute_compatibility
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


class InteriorPairSearch:
    def __init__(
        self,
        grid: np.ndarray,
        minimum_numerator: int,
        deadline: float,
        node_limit: int,
    ) -> None:
        self.grid = grid
        self.minimum_numerator = minimum_numerator
        self.deadline = deadline
        self.node_limit = node_limit
        self.compatibility = precompute_compatibility(grid, minimum_numerator)
        self.all_mask = (1 << grid.shape[0]) - 1
        self.root_pairs = list(itertools.combinations(range(grid.shape[0]), 2))
        self.counters = Counters()
        self.solution: tuple[int, ...] | None = None

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

    def search(self, chosen: tuple[int, ...], available: int) -> bool:
        self.counters.nodes += 1
        if not self.counters.nodes & 1023:
            self.check_limits()
        remaining = COUNT - len(chosen)
        if remaining == 0:
            self.solution = chosen
            return True
        if available.bit_count() < remaining:
            self.counters.capacity_prunes += 1
            return False
        if self.color_upper_bound(available, chosen) < remaining:
            self.counters.color_prunes += 1
            return False

        candidates = available
        while candidates:
            bit = candidates & -candidates
            vertex = bit.bit_length() - 1
            candidates ^= bit
            higher = self.all_mask & ~((1 << (vertex + 1)) - 1)
            next_available = available & higher
            for selected in chosen:
                next_available &= self.compatibility[selected][vertex]
            if next_available.bit_count() < remaining - 1:
                self.counters.capacity_prunes += 1
                continue
            if self.search(chosen + (vertex,), next_available):
                return True
        return False

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
                first, second = self.root_pairs[root_index]
                higher = self.all_mask & ~((1 << (second + 1)) - 1)
                available = higher & self.compatibility[first][second]
                if self.search((first, second), available):
                    return "feasible", root_index + 1, limit, total
                completed = root_index + 1
        except SearchStopped:
            return "unresolved", completed, limit, total
        status = (
            "infeasible" if start_root == 0 and limit == total else "segment_infeasible"
        )
        return status, completed, limit, total


def interior_grid(denominator: int) -> np.ndarray:
    grid = barycentric_grid(denominator)
    return grid[np.all(grid > 0, axis=1)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--denominators", type=parse_ints, default=parse_ints("25"))
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--node-limit", type=int, default=100_000_000)
    parser.add_argument("--start-root", type=int, default=0)
    parser.add_argument("--end-root", type=int)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    parser.add_argument("--stamp")
    args = parser.parse_args()

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
        family="fully interior barycentric q-grid; exhaustive first-pair partition",
    )

    records = []
    best_score = -np.inf
    best_payload: dict[str, object] | None = None
    for denominator in args.denominators:
        started = time.perf_counter()
        minimum_numerator = threshold_numerator(target, denominator)
        grid = interior_grid(denominator)
        search = InteriorPairSearch(
            grid,
            minimum_numerator,
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
            "interior_grid_point_count": int(grid.shape[0]),
            "status": status,
            "start_root_pair": args.start_root,
            "end_root_pair_exclusive": end_root,
            "completed_root_pairs": completed,
            "total_root_pairs": total_roots,
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
        "mode": "exact fully-interior first-pair determinant-hypergraph DFS",
        "family": "fully interior barycentric q-grid",
        "side_counts": [0, 0, 0],
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
