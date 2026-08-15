#!/usr/bin/env python3
"""Repair coordinate-free nearest-public metadata after the RMS assignment fix.

Candidate coordinates, payload hashes, verifier scores, and search events are
never changed.  Only nearest-public IDs/distances and summaries are rebuilt.
This is a private campaign-tree maintenance command; raw runs remain excluded
from the publication allowlist.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    raise RuntimeError("repair_rms_metadata requires Python >= 3.11")

import numpy as np

from global_search import (
    HERE,
    SNAPSHOT,
    append_jsonl,
    atomic_json,
    d3_rms_distance,
    sha256_path,
)


CANONICAL_RUNS = (
    HERE / "runs/global-20260815T100000Z-v2",
    HERE / "runs/continuation-20260815T103000Z-v2",
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def atomic_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def public_basins(public: list[dict[str, object]]) -> list[np.ndarray]:
    representatives: list[np.ndarray] = []
    for item in public:
        points = np.asarray(item["data"]["points"], dtype=np.float64)  # type: ignore[index]
        if any(d3_rms_distance(points, previous) <= 1e-8 for previous in representatives):
            continue
        representatives.append(points)
    return representatives


def repair_run(run_dir: Path, public: list[dict[str, object]], basin_count: int) -> dict[str, object]:
    run_dir = run_dir.resolve()
    results_path = run_dir / "results.jsonl"
    summary_path = run_dir / "summary.json"
    records = read_jsonl(results_path)
    before_results_hash = sha256_path(results_path)
    changed_records = 0
    for record in records:
        points = np.asarray(record["points"], dtype=np.float64)
        distances = [
            d3_rms_distance(points, np.asarray(item["data"]["points"], dtype=np.float64))  # type: ignore[index]
            for item in public
        ]
        nearest = int(np.argmin(distances))
        nearest_id = int(public[nearest]["id"])
        nearest_distance = float(distances[nearest])
        if (
            record.get("nearest_public_solution_id") != nearest_id
            or record.get("nearest_public_d3_rms") != nearest_distance
        ):
            changed_records += 1
        record["nearest_public_solution_id"] = nearest_id
        record["nearest_public_d3_rms"] = nearest_distance
    if changed_records:
        atomic_jsonl(results_path, records)
    after_results_hash = sha256_path(results_path)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    scores = np.asarray([float(record["verifier_score"]) for record in records])
    distances = np.asarray([float(record["nearest_public_d3_rms"]) for record in records])
    best_id = int(np.argmax(scores))
    distinct_ids = np.flatnonzero(distances > 1e-4)
    best_distinct_id = int(distinct_ids[np.argmax(scores[distinct_ids])]) if len(distinct_ids) else None
    selected_parents = {
        (int(record["parent_rank"]), str(record["template_id"]))
        for record in records
        if record["phase"] == "death_rebirth"
    }
    summary.update(
        {
            "best_record": {key: value for key, value in records[best_id].items() if key != "points"},
            "best_distinct_record": (
                {key: value for key, value in records[best_distinct_id].items() if key != "points"}
                if best_distinct_id is not None
                else None
            ),
            "records_distinct_from_public_1e_4": int(np.sum(distances > 1e-4)),
            "results_sha256": after_results_hash,
            "d3_distinct_public_basins": basin_count,
            "mutation_parents_selected": len(selected_parents),
            "mutation_public_parents_selected": sum(
                template_id.startswith("public-") for _rank, template_id in selected_parents
            ),
            "mutation_template_parents_selected": sum(
                not template_id.startswith("public-") for _rank, template_id in selected_parents
            ),
            "rms_metadata_repair": {
                "assignment_cost": "squared_euclidean",
                "before_results_sha256": before_results_hash,
                "after_results_sha256": after_results_hash,
                "candidate_coordinates_changed": False,
                "payload_hashes_changed": False,
                "verifier_scores_changed": False,
                "records_with_nearest_metadata_changed": changed_records,
            },
        }
    )
    atomic_json(summary_path, summary)
    if changed_records:
        append_jsonl(
            run_dir / "events.jsonl",
            {
                "event": "nearest_public_rms_metadata_repaired",
                "assignment_cost": "squared_euclidean",
                "before_results_sha256": before_results_hash,
                "after_results_sha256": after_results_hash,
                "records_changed": changed_records,
            },
        )
    return {
        "run": run_dir.name,
        "records": len(records),
        "changed_records": changed_records,
        "before_results_sha256": before_results_hash,
        "after_results_sha256": after_results_hash,
        "summary_sha256": sha256_path(summary_path),
        "minimum_true_d3_rms": float(np.min(distances)),
        "d3_distinct_public_basins": basin_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs="*", type=Path, default=list(CANONICAL_RUNS))
    args = parser.parse_args()
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    public = list(snapshot["solutions"])
    basins = public_basins(public)
    results = [repair_run(path, public, len(basins)) for path in args.run_dirs]
    print(json.dumps({"status": "ok", "metric": "true_d3_rms", "runs": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
