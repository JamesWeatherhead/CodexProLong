#!/usr/bin/env python3
"""Audit and merge disjoint exact corner-search root intervals."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lattice_bnb import atomic_json


def read_summary(path: Path, denominator: int) -> tuple[dict[str, Any], dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        summary = json.load(handle)
    matches = [
        record for record in summary["results"] if record["denominator"] == denominator
    ]
    if len(matches) != 1:
        raise ValueError(f"{path}: expected exactly one q={denominator} record")
    return summary, matches[0]


def merge_intervals(intervals: list[tuple[int, int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if end < start:
            raise ValueError(f"invalid interval [{start}, {end})")
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--denominator", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("summaries", nargs="+", type=Path)
    args = parser.parse_args()

    sources = []
    intervals = []
    verifier_hashes = set()
    targets = set()
    total_roots_set = set()
    minimum_numerators = set()
    total_nodes = 0
    for path in args.summaries:
        summary, record = read_summary(path, args.denominator)
        if record["status"] == "feasible":
            raise ValueError(f"{path}: segment contains a feasible configuration")
        start = int(record.get("start_root", 1))
        completed = int(record.get("completed_roots", start))
        intervals.append((start, completed))
        verifier_hashes.add(summary["verifier_sha256"])
        targets.add(float(summary["target_strictly_above"]))
        total_roots_set.add(int(record["total_roots"]))
        minimum_numerators.add(int(record["minimum_numerator"]))
        total_nodes += int(record["nodes"])
        sources.append(
            {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "status": record["status"],
                "certified_interval": [start, completed],
                "nodes": int(record["nodes"]),
            }
        )

    for name, values in (
        ("verifier hash", verifier_hashes),
        ("target", targets),
        ("root count", total_roots_set),
        ("minimum numerator", minimum_numerators),
    ):
        if len(values) != 1:
            raise ValueError(f"inconsistent {name}: {sorted(values)}")
    total_roots = total_roots_set.pop()
    minimum_numerator = minimum_numerators.pop()
    merged = merge_intervals(intervals)
    complete = merged == [[1, total_roots]]
    result = {
        "mode": "audited union of exact fixed-corner DFS root intervals",
        "denominator": args.denominator,
        "minimum_numerator": minimum_numerator,
        "minimum_grid_score": minimum_numerator / (args.denominator * args.denominator),
        "target_strictly_above": targets.pop(),
        "verifier_sha256": verifier_hashes.pop(),
        "root_domain": [1, total_roots],
        "merged_certified_intervals": merged,
        "complete": complete,
        "status": "infeasible" if complete else "incomplete",
        "total_audit_nodes_including_repeated_partial_work": total_nodes,
        "sources": sources,
    }
    atomic_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
