#!/usr/bin/env python3
"""Exact q-grid branch-and-bound for Heilbronn configurations with a corner.

Any corner-containing configuration is D3-equivalent to one containing the
fixed first corner.  The remaining ten points are selected from the full grid.
Determinant-compatible bitsets and conditional graph coloring bound every
branch; no continuous/local optimization is used.
"""

from __future__ import annotations

import argparse
import hashlib
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


class CornerSearch:
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
        self, start_root: int = 1, end_root: int | None = None
    ) -> tuple[str, int, int, int]:
        # The grid is reordered so index zero is the fixed corner.  Splitting
        # on the least-indexed additional point makes long cases resumable.
        limit = (
            self.grid.shape[0]
            if end_root is None
            else min(end_root, self.grid.shape[0])
        )
        if not 1 <= start_root <= limit:
            raise ValueError("root interval must satisfy 1 <= start <= end")
        completed = start_root
        try:
            for vertex in range(start_root, limit):
                self.check_limits()
                higher = self.all_mask & ~((1 << (vertex + 1)) - 1)
                available = higher & self.compatibility[0][vertex]
                if self.search((0, vertex), available):
                    return "feasible", vertex + 1, limit, self.grid.shape[0]
                completed = vertex + 1
        except SearchStopped:
            return "unresolved", completed, limit, self.grid.shape[0]
        status = (
            "infeasible"
            if start_root == 1 and limit == self.grid.shape[0]
            else "segment_infeasible"
        )
        return status, completed, limit, self.grid.shape[0]


def corner_first_grid(denominator: int) -> np.ndarray:
    grid = barycentric_grid(denominator, include_corners=True)
    match = np.flatnonzero(np.all(grid == (denominator, 0, 0), axis=1))
    if match.size != 1:
        raise RuntimeError("fixed corner missing from grid")
    corner = int(match[0])
    ordering = np.concatenate(([corner], np.delete(np.arange(grid.shape[0]), corner)))
    return grid[ordering]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument(
        "--denominators", type=parse_ints, default=parse_ints("8,10,12,14,16,18,20")
    )
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--node-limit", type=int, default=50_000_000)
    parser.add_argument("--start-root", type=int, default=1)
    parser.add_argument(
        "--end-root",
        type=int,
        help="exclusive second-vertex root bound for disjoint resumable segments",
    )
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
        family="full barycentric q-grid with one fixed outer corner",
    )

    records = []
    best_score = -np.inf
    best_payload: dict[str, object] | None = None
    for denominator in args.denominators:
        started = time.perf_counter()
        minimum_numerator = threshold_numerator(target, denominator)
        grid = corner_first_grid(denominator)
        search = CornerSearch(
            grid,
            minimum_numerator,
            started + args.time_limit,
            args.node_limit,
        )
        precompute_seconds = time.perf_counter() - started
        status, completed_roots, end_root, total_roots = search.run(
            args.start_root, args.end_root
        )
        record: dict[str, Any] = {
            "denominator": denominator,
            "minimum_numerator": minimum_numerator,
            "minimum_grid_score": minimum_numerator / (denominator * denominator),
            "grid_point_count": int(grid.shape[0]),
            "status": status,
            "start_root": args.start_root,
            "end_root_exclusive": end_root,
            "completed_roots": completed_roots,
            "total_roots": total_roots,
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
        "mode": "exact corner-family determinant-hypergraph branch-and-bound",
        "family": "full barycentric lattice with a D3-fixed outer corner",
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
