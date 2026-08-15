#!/usr/bin/env python3
"""Build a hashed summary of complete and partial q=30 orbit coverage."""

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


def parse_entry(value: str) -> tuple[tuple[int, int, int], Path]:
    counts_text, separator, path_text = value.partition(":")
    if not separator:
        raise argparse.ArgumentTypeError("entry must be COUNTS:PATH")
    counts = tuple(parse_ints(counts_text))
    if len(counts) != 3:
        raise argparse.ArgumentTypeError("entry counts require three integers")
    return counts, Path(path_text)


def normalize_entry(
    path: Path,
    counts: tuple[int, int, int],
    denominator: int,
    require_complete: bool,
) -> dict[str, Any]:
    document = load_json(path)
    if "side_counts" in document and tuple(document["side_counts"]) != counts:
        raise ValueError(f"{path}: side-count mismatch")
    if "results" in document:
        matches = [
            result
            for result in document["results"]
            if result["denominator"] == denominator
        ]
        if len(matches) != 1:
            raise ValueError(f"{path}: missing unique q={denominator} result")
        record = matches[0]
        complete = record["status"] == "infeasible"
        certified_roots = record.get("root_set_count", record.get("root_pair_count", 0))
        root_domain = [0, certified_roots]
        coverage_fraction = 1.0 if complete else 0.0
        nodes = int(record["nodes"])
        verifier_hash = document["verifier_sha256"]
        target = float(document["target_strictly_above"])
        minimum_numerator = int(record["minimum_numerator"])
        status = record["status"]
    else:
        complete = bool(document["complete"])
        root_domain = document["root_domain"]
        certified_roots = int(
            document.get(
                "certified_roots",
                sum(
                    end - start for start, end in document["merged_certified_intervals"]
                ),
            )
        )
        coverage_fraction = float(
            document.get(
                "coverage_fraction",
                certified_roots / (root_domain[1] - root_domain[0]),
            )
        )
        nodes = int(
            document.get(
                "total_audit_nodes_including_repeated_partial_work",
                document.get("total_audit_nodes", 0),
            )
        )
        verifier_hash = document["verifier_sha256"]
        target = float(document["target_strictly_above"])
        minimum_numerator = int(document["minimum_numerator"])
        status = document["status"]
    if require_complete and not complete:
        raise ValueError(f"{path}: expected complete proof")
    if not require_complete and complete:
        raise ValueError(f"{path}: expected a partial record")
    return {
        "side_counts": list(counts),
        "status": status,
        "complete": complete,
        "certified_roots": certified_roots,
        "root_domain": root_domain,
        "coverage_fraction": coverage_fraction,
        "audit_nodes": nodes,
        "minimum_numerator": minimum_numerator,
        "target": target,
        "verifier_sha256": verifier_hash,
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--denominator", type=int, default=30)
    parser.add_argument("--complete", type=parse_entry, action="append", default=[])
    parser.add_argument("--partial", type=parse_entry, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    snapshot, live_score, target, verifier_hash = load_snapshot(args.snapshot)
    complete = [
        normalize_entry(path, counts, args.denominator, True)
        for counts, path in args.complete
    ]
    partial = [
        normalize_entry(path, counts, args.denominator, False)
        for counts, path in args.partial
    ]
    entries = complete + partial
    patterns = {tuple(entry["side_counts"]) for entry in entries}
    if patterns != EXPECTED_PATTERNS or len(entries) != len(EXPECTED_PATTERNS):
        raise ValueError("q=30 side-count orbit manifest is incomplete or duplicated")
    minimum_numerators = {entry["minimum_numerator"] for entry in entries}
    if len(minimum_numerators) != 1:
        raise ValueError("inconsistent determinant thresholds")
    for entry in entries:
        if entry["verifier_sha256"] != verifier_hash or entry["target"] != target:
            raise ValueError("entry does not match frozen verifier/target")

    minimum_numerator = minimum_numerators.pop()
    output = {
        "slug": "heilbronn-triangles",
        "status": "partial_family_closure",
        "scope": "noncorner 11-point subsets of the barycentric q=30 grid",
        "denominator": args.denominator,
        "noncorner_grid_point_count": (args.denominator + 1)
        * (args.denominator + 2)
        // 2
        - 3,
        "live_score": live_score,
        "target_strictly_above": target,
        "minimum_numerator": minimum_numerator,
        "minimum_grid_score": minimum_numerator / (args.denominator * args.denominator),
        "verifier_sha256": verifier_hash,
        "snapshot": str(args.snapshot.resolve()),
        "snapshot_sha256": hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
        "complete_orbit_count": len(complete),
        "partial_orbit_count": len(partial),
        "complete_orbits": sorted(
            complete, key=lambda entry: entry["side_counts"], reverse=True
        ),
        "partial_orbits": sorted(
            partial, key=lambda entry: entry["side_counts"], reverse=True
        ),
        "total_audit_nodes": sum(entry["audit_nodes"] for entry in entries),
        "gate_clearing_candidate": None,
        "public_solution_count": len(snapshot["solutions"]),
        "public_thread_count": len(snapshot["threads"]),
    }
    atomic_json(args.output, output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
