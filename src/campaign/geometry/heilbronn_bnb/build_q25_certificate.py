#!/usr/bin/env python3
"""Build a coverage certificate for the exhaustive q=25 family closure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lattice_bnb import DEFAULT_SNAPSHOT, atomic_json, load_snapshot, parse_ints

EXPECTED_PATTERNS = {
    (2, 2, 2),
    (2, 2, 1),
    (2, 2, 0),
    (2, 1, 1),
    (2, 1, 0),
    (2, 0, 0),
    (1, 1, 1),
    (1, 1, 0),
    (1, 0, 0),
    (0, 0, 0),
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def entry_result(
    path: Path, counts: tuple[int, int, int], denominator: int
) -> dict[str, Any]:
    document = load_json(path)
    if "results" in document:
        matches = [
            result
            for result in document["results"]
            if result["denominator"] == denominator
        ]
        if len(matches) != 1 or matches[0]["status"] != "infeasible":
            raise ValueError(f"{path}: q={denominator} is not proven infeasible")
        record = matches[0]
        verifier_hash = document["verifier_sha256"]
        target = float(document["target_strictly_above"])
        minimum_numerator = int(record["minimum_numerator"])
        mode = document["mode"]
        nodes = int(record["nodes"])
    else:
        if not document.get("complete") or document["status"] != "infeasible":
            raise ValueError(f"{path}: aggregate is incomplete")
        if tuple(document["side_counts"]) != counts:
            raise ValueError(f"{path}: side-count mismatch")
        verifier_hash = document["verifier_sha256"]
        target = float(document["target_strictly_above"])
        minimum_numerator = int(document["minimum_numerator"])
        mode = document["mode"]
        nodes = int(
            document.get(
                "total_audit_nodes_including_repeated_partial_work",
                document.get("total_audit_nodes", 0),
            )
        )
    return {
        "side_counts": list(counts),
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "verifier_sha256": verifier_hash,
        "target": target,
        "minimum_numerator": minimum_numerator,
        "mode": mode,
        "audit_nodes": nodes,
    }


def parse_entry(value: str) -> tuple[tuple[int, int, int], Path]:
    counts_text, separator, path_text = value.partition(":")
    if not separator:
        raise argparse.ArgumentTypeError("entry must be COUNTS:PATH")
    counts = tuple(parse_ints(counts_text))
    if len(counts) != 3:
        raise argparse.ArgumentTypeError("entry counts require three integers")
    return counts, Path(path_text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--denominator", type=int, default=25)
    parser.add_argument("--corner", type=Path, required=True)
    parser.add_argument("--entry", type=parse_entry, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    snapshot, live_score, target, verifier_hash = load_snapshot(args.snapshot)
    entries = [
        entry_result(path, counts, args.denominator) for counts, path in args.entry
    ]
    found_patterns = {tuple(entry["side_counts"]) for entry in entries}
    if found_patterns != EXPECTED_PATTERNS or len(entries) != len(EXPECTED_PATTERNS):
        raise ValueError(
            f"pattern coverage mismatch: found {sorted(found_patterns)}, "
            f"expected {sorted(EXPECTED_PATTERNS)}"
        )

    corner = load_json(args.corner)
    if not corner.get("complete") or corner["status"] != "infeasible":
        raise ValueError("corner-family certificate is incomplete")
    expected_numerator = int(corner["minimum_numerator"])
    if int(corner["denominator"]) != args.denominator:
        raise ValueError("corner-family denominator mismatch")
    for entry in entries:
        if entry["verifier_sha256"] != verifier_hash:
            raise ValueError("entry verifier hash mismatch")
        if entry["target"] != target:
            raise ValueError("entry target mismatch")
        if entry["minimum_numerator"] != expected_numerator:
            raise ValueError("entry threshold mismatch")
    if corner["verifier_sha256"] != verifier_hash:
        raise ValueError("corner verifier hash mismatch")

    output = {
        "slug": "heilbronn-triangles",
        "status": "proved_infeasible",
        "scope": "all 11-point configurations on the full barycentric q=25 grid",
        "denominator": args.denominator,
        "grid_point_count": (args.denominator + 1) * (args.denominator + 2) // 2,
        "live_score": live_score,
        "target_strictly_above": target,
        "minimum_numerator": expected_numerator,
        "minimum_grid_score": expected_numerator
        / (args.denominator * args.denominator),
        "verifier_sha256": verifier_hash,
        "snapshot": str(args.snapshot.resolve()),
        "snapshot_sha256": hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
        "coverage_argument": [
            "A set containing a grid corner is covered by the exhaustive fixed-corner D3 search.",
            "Without corners, each grid point lies on at most one outer side.",
            "Three selected points on one side have zero determinant, so every positive-threshold set has side counts at most two.",
            "D3 permutes the three sides; the ten sorted side-count triples listed below exhaust {0,1,2}^3 modulo that action.",
        ],
        "corner_family": {
            "path": str(args.corner.resolve()),
            "sha256": hashlib.sha256(args.corner.read_bytes()).hexdigest(),
            "audit_nodes": int(
                corner["total_audit_nodes_including_repeated_partial_work"]
            ),
        },
        "noncorner_side_count_families": sorted(
            entries, key=lambda entry: entry["side_counts"], reverse=True
        ),
        "public_solution_count": len(snapshot["solutions"]),
        "public_thread_count": len(snapshot["threads"]),
        "total_audit_nodes": int(
            sum(entry["audit_nodes"] for entry in entries)
            + corner["total_audit_nodes_including_repeated_partial_work"]
        ),
        "gate_clearing_candidate": None,
    }
    atomic_json(args.output, output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
