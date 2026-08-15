#!/usr/bin/env python3
"""Independent replay and publication-safe freeze for the global Heilbronn lane."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sqlite3
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    raise RuntimeError("audit_packet requires Python >= 3.11")

import numpy as np

from global_search import (
    CAMPAIGN,
    EXPECTED_VERIFIER_SHA256,
    HERE,
    SNAPSHOT,
    VERIFIER,
    atomic_json,
    d3_rms_distance,
    load_evaluate,
    sha256_path,
    verifier_score,
)


CORPUS = CAMPAIGN / "research_corpus/snapshots/20260815T003306Z/corpus.sqlite3"
PRIOR_FILES = (
    CAMPAIGN / "HANDOFF.md",
    CAMPAIGN / "geometry/HANDOFF.md",
    CAMPAIGN / "geometry/heilbronn_bnb/HANDOFF.md",
    CAMPAIGN / "geometry/heilbronn_bnb/ADAPTIVE_Q143.md",
    CAMPAIGN / "geometry/heilbronn_rational_mesh_global/HANDOFF.md",
    CAMPAIGN / "geometry/heilbronn_q143_cegis/HANDOFF.md",
    CAMPAIGN / "geometry/heilbronn_active_refine.py",
    CAMPAIGN / "geometry/heilbronn_topology_search.py",
    CAMPAIGN / "literature_asset_hunt/HANDOFF.md",
)
SUPERSEDED_RUNS = (
    HERE / "runs/global-20260815T100000Z",
    HERE / "runs/continuation-20260815T103000Z",
)


def payload_sha256(points: object) -> str:
    encoded = json.dumps({"points": points}, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def public_record(record: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in record.items() if key != "points"}


def independent_formula_score(points: np.ndarray) -> float:
    """Recompute the 165-triple objective without solver or verifier helpers."""

    areas = []
    for first, second, third in itertools.combinations(range(11), 3):
        u = points[second] - points[first]
        v = points[third] - points[first]
        areas.append(abs(u[0] * v[1] - u[1] * v[0]) / 2.0)
    return float(min(areas) / (np.sqrt(3.0) / 4.0))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise RuntimeError(f"invalid JSONL {path}:{line_number}: {error}") from error
    return records


def audit_run(
    run_dir: Path, public: list[dict[str, object]], public_basin_count: int
) -> tuple[dict[str, object], list[dict[str, object]]]:
    run_dir = run_dir.resolve()
    if HERE not in run_dir.parents:
        raise RuntimeError(f"run is outside isolated subtree: {run_dir}")
    required = ("inputs.json", "events.jsonl", "results.jsonl", "summary.json")
    for name in required:
        if not (run_dir / name).is_file():
            raise RuntimeError(f"incomplete run missing {name}: {run_dir}")
    inputs = json.loads((run_dir / "inputs.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    if inputs["verifier_sha256"] != EXPECTED_VERIFIER_SHA256:
        raise RuntimeError("run verifier hash mismatch")
    if inputs["snapshot_sha256"] != sha256_path(SNAPSHOT):
        raise RuntimeError("run snapshot hash mismatch")
    records = read_jsonl(run_dir / "results.jsonl")
    evaluate_a = load_evaluate()
    evaluate_b = load_evaluate()
    mismatches: list[dict[str, object]] = []
    formula_deltas: list[float] = []
    for index, record in enumerate(records):
        points = np.asarray(record["points"], dtype=np.float64)
        first = verifier_score(evaluate_a, points)
        second = verifier_score(evaluate_b, points.copy())
        formula = independent_formula_score(points)
        formula_deltas.append(abs(formula - first))
        public_distances = [
            d3_rms_distance(points, np.asarray(item["data"]["points"], dtype=np.float64))  # type: ignore[index]
            for item in public
        ]
        nearest = int(np.argmin(public_distances))
        checks = {
            "payload_hash": payload_sha256(record["points"]) == record["payload_sha256"],
            "first_score": first == float(record["verifier_score"]),
            "second_score": second == float(record["independent_replay_score"]),
            "replay_agreement": first == second,
            "independent_formula": abs(formula - first) <= 2e-16,
            "true_rms_nearest_id": int(record["nearest_public_solution_id"]) == int(public[nearest]["id"]),
            "true_rms_nearest_distance": float(record["nearest_public_d3_rms"]) == float(public_distances[nearest]),
            "strict_gate": bool(first > float(inputs["strict_target"])) == bool(record["strict_gate_clearer"]),
        }
        if not all(checks.values()):
            mismatches.append({"record": index, "checks": checks})
    if mismatches:
        raise RuntimeError(f"candidate replay mismatches: {mismatches[:3]}")
    scores = [float(record["verifier_score"]) for record in records]
    if int(summary["polished_records"]) != len(records):
        raise RuntimeError("summary record count mismatch")
    if int(summary["gate_clearers"]) != sum(score > float(inputs["strict_target"]) for score in scores):
        raise RuntimeError("summary gate count mismatch")
    actual_hashes = {name: sha256_path(run_dir / name) for name in required}
    if summary["results_sha256"] != actual_hashes["results.jsonl"]:
        raise RuntimeError("summary results hash mismatch")
    if int(summary["d3_distinct_public_basins"]) != public_basin_count:
        raise RuntimeError("summary public-basin count mismatch")
    selected_parents = {
        (int(record["parent_rank"]), str(record["template_id"]))
        for record in records
        if record["phase"] == "death_rebirth"
    }
    selected_public = sum(template_id.startswith("public-") for _rank, template_id in selected_parents)
    if (
        int(summary["mutation_parents_selected"]) != len(selected_parents)
        or int(summary["mutation_public_parents_selected"]) != selected_public
        or int(summary["mutation_template_parents_selected"]) != len(selected_parents) - selected_public
    ):
        raise RuntimeError("summary mutation-parent composition mismatch")
    parameters = inputs["parameters"]
    inferred_mutation_members = (
        len(parameters["mutation_depths"])
        * int(parameters["mutation_parents"])
        * int(parameters["mutation_population"])
    )
    run_receipt = {
        "run": run_dir.name,
        "inputs_sha256": actual_hashes["inputs.json"],
        "events_sha256": actual_hashes["events.jsonl"],
        "results_sha256": actual_hashes["results.jsonl"],
        "summary_sha256": actual_hashes["summary.json"],
        "records": len(records),
        "template_population_members": int(summary.get("template_population_members", 0)),
        "mutation_population_members": int(
            summary.get("mutation_population_members", inferred_mutation_members)
        ),
        "best_score": max(scores),
        "minimum_true_d3_rms": min(float(record["nearest_public_d3_rms"]) for record in records),
        "gate_clearers": sum(score > float(inputs["strict_target"]) for score in scores),
        "d3_distinct_public_basins": public_basin_count,
        "mutation_parents_selected": len(selected_parents),
        "mutation_public_parents_selected": selected_public,
        "mutation_template_parents_selected": len(selected_parents) - selected_public,
        "rms_metadata_repair": summary.get("rms_metadata_repair"),
        "all_payload_hashes_match": True,
        "all_fresh_verifier_replays_match": True,
        "all_independent_formula_replays_match": True,
        "max_independent_formula_delta": max(formula_deltas),
        "summary_precompletion_event_hash": summary.get("events_sha256"),
        "summary_precompletion_hash_differs_from_final": summary.get("events_sha256") != actual_hashes["events.jsonl"],
    }
    return run_receipt, records


def prior_audit(d3_distinct_public_basins: int) -> dict[str, object]:
    database_hash = sha256_path(CORPUS)
    connection = sqlite3.connect(CORPUS)
    connection.row_factory = sqlite3.Row
    try:
        solutions = connection.execute(
            "SELECT id, record_sha256 FROM solutions WHERE problem_id=15 ORDER BY id"
        ).fetchall()
        threads = connection.execute(
            "SELECT id, record_sha256 FROM threads WHERE problem_slug='heilbronn-triangles' ORDER BY id"
        ).fetchall()
        replies = connection.execute(
            "SELECT r.id, r.record_sha256 FROM replies r JOIN threads t ON t.id=r.thread_id "
            "WHERE t.problem_slug='heilbronn-triangles' ORDER BY r.id"
        ).fetchall()
    finally:
        connection.close()
    discussion_digest = hashlib.sha256(
        "\n".join(row["record_sha256"] for row in [*threads, *replies]).encode()
    ).hexdigest()
    return {
        "corpus_sqlite_sha256": database_hash,
        "public_solutions_read": len(solutions),
        "d3_distinct_public_basins": d3_distinct_public_basins,
        "public_solution_ids": [int(row["id"]) for row in solutions],
        "threads_read": len(threads),
        "thread_records": [dict(row) for row in threads],
        "replies_read": len(replies),
        "reply_records": [dict(row) for row in replies],
        "discussion_record_sha256": discussion_digest,
        "prior_files": [
            {"path": str(path.relative_to(CAMPAIGN)), "sha256": sha256_path(path)}
            for path in PRIOR_FILES
        ],
        "closed_families_not_repeated": {
            "q25_full_grid": "all side-count orbits; 51,494,145 exact DFS nodes",
            "q30_partial_and_complete_orbits": "121,384,089 audited DFS nodes",
            "q143_adaptive_cells": "44 release scenarios in the follow-on closure",
            "q144_to_q220_finite_cells": "72 distinct finite labeled domains",
            "incumbent_active_face": "17 active triples + 6 boundary contacts",
            "public_continuous_search": "2,471,800 asymmetric/depth-1-to-3 replacement starts",
        },
    }


def mapping_bug_impact(run_dirs: list[Path], corrected_records: list[dict[str, object]], target: float) -> dict[str, object]:
    """Privately quantify discarded runs; never imply public replayability."""

    common: dict[str, object] = {
        "root_cause": (
            "Public boundary contacts were inferred in domain-slack order C/B/A, then reconstructed as "
            "zero-barycentric modes A/B/C. The fix applies the explicit permutation (2,1,0)."
        ),
        "publicly_replayable": False,
        "evidence_scope": (
            "Private audit over excluded raw v1 run payloads. Public receipt replay checks the scope label "
            "and hash pins only; it cannot recompute the v1 counts or before/after comparison."
        ),
    }
    corrected_by_name = {path.name: path.resolve() for path in run_dirs}
    required_corrected = {
        "global-20260815T100000Z-v2",
        "continuation-20260815T103000Z-v2",
    }
    if set(corrected_by_name) != required_corrected:
        return common | {
            "status": "not_recomputed_for_noncanonical_reproduction",
            "superseded_results_excluded_from_frontier": True,
            "audited_run_names": sorted(corrected_by_name),
        }
    old_records: list[dict[str, object]] = []
    old_global: list[dict[str, object]] = []
    affected_members = 0
    affected_records = 0
    private_artifact_hashes: list[dict[str, str]] = []
    for old_dir in SUPERSEDED_RUNS:
        for name in ("inputs.json", "results.jsonl", "summary.json"):
            private_artifact_hashes.append(
                {
                    "path": f"runs/{old_dir.name}/{name}",
                    "sha256": sha256_path(old_dir / name),
                }
            )
        inputs = json.loads((old_dir / "inputs.json").read_text(encoding="utf-8"))
        records = read_jsonl(old_dir / "results.jsonl")
        old_records.extend(records)
        if old_dir.name == "global-20260815T100000Z":
            old_global = records
        public_groups = {
            (int(record["depth"]), int(record["parent_rank"]), str(record["template_id"]))
            for record in records
            if record["phase"] == "death_rebirth" and str(record["template_id"]).startswith("public-")
        }
        affected_members += len(public_groups) * int(inputs["parameters"]["mutation_population"])
        affected_records += sum(
            record["phase"] == "death_rebirth" and str(record["template_id"]).startswith("public-")
            for record in records
        )
    corrected_global = read_jsonl(corrected_by_name["global-20260815T100000Z-v2"] / "results.jsonl")
    old_template = [record for record in old_global if record["phase"] == "template"]
    corrected_template = [record for record in corrected_global if record["phase"] == "template"]
    template_payload_score_equal = [
        (record["payload_sha256"], record["verifier_score"], record["independent_replay_score"])
        for record in old_template
    ] == [
        (record["payload_sha256"], record["verifier_score"], record["independent_replay_score"])
        for record in corrected_template
    ]
    if not template_payload_score_equal:
        raise RuntimeError("boundary fix unexpectedly changed template payloads or scores")
    old_best = max(float(record["verifier_score"]) for record in old_records)
    corrected_best = max(float(record["verifier_score"]) for record in corrected_records)
    total_members = 0
    for corrected_dir in corrected_by_name.values():
        summary = json.loads((corrected_dir / "summary.json").read_text(encoding="utf-8"))
        total_members += int(summary["template_population_members"]) + int(summary["mutation_population_members"])
    return common | {
        "status": "private_nonreplayable_audit",
        "superseded_runs": [path.name for path in SUPERSEDED_RUNS],
        "superseded_results_excluded_from_frontier": True,
        "private_artifact_hashes": private_artifact_hashes,
        "potentially_affected_public_parent_members": affected_members,
        "potentially_affected_public_parent_records": affected_records,
        "outside_bug_scope_members": total_members - affected_members,
        "outside_bug_scope_records": len(old_records) - affected_records,
        "template_phase_payload_score_records_equal": len(old_template),
        "template_phase_payload_score_equality": template_payload_score_equal,
        "superseded_best_score": old_best,
        "corrected_best_score": corrected_best,
        "best_score_delta_after_fix": corrected_best - old_best,
        "superseded_strict_target_shortfall": target - old_best,
        "corrected_strict_target_shortfall": target - corrected_best,
    }


def secrets_clean(paths: list[Path]) -> tuple[bool, list[str]]:
    forbidden = ("g" + "xl_", "bdb" + "7ada8-", "EXA_" + "API_KEY=", "Authorization:" + " Bearer")
    hits = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in forbidden:
            if token in text:
                hits.append(f"{path.name}:{token}")
    return not hits, hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", nargs="+", type=Path)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the canonical private receipt to publication/receipt.json",
    )
    parser.add_argument(
        "--receipt-out",
        type=Path,
        help="write a reproduction receipt inside this subtree instead of stdout",
    )
    args = parser.parse_args()
    if args.write and args.receipt_out is not None:
        parser.error("choose either --write or --receipt-out")
    if sha256_path(VERIFIER) != EXPECTED_VERIFIER_SHA256:
        raise RuntimeError("frozen verifier changed")
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    public = list(snapshot["solutions"])
    public_basins: list[np.ndarray] = []
    for item in public:
        points = np.asarray(item["data"]["points"], dtype=np.float64)
        if any(d3_rms_distance(points, previous) <= 1e-8 for previous in public_basins):
            continue
        public_basins.append(points)
    if len(public_basins) != 13:
        raise RuntimeError(f"expected 13 D3-distinct public basins, found {len(public_basins)}")
    run_receipts = []
    all_records: list[dict[str, object]] = []
    for run_dir in args.run_dirs:
        receipt, records = audit_run(run_dir, public, len(public_basins))
        run_receipts.append(receipt)
        all_records.extend(records)
    if not all_records:
        raise RuntimeError("no candidate records")
    leader = float(snapshot["solutions"][0]["score"])
    min_improvement = float(snapshot["problem"]["minImprovement"])
    target = leader + min_improvement
    all_records.sort(key=lambda record: float(record["verifier_score"]), reverse=True)
    distinct = [record for record in all_records if float(record["nearest_public_d3_rms"]) > 1e-4]
    source_files = [
        HERE / "global_search.py",
        HERE / "audit_packet.py",
        HERE / "test_packet.py",
        HERE / "repair_rms_metadata.py",
        HERE / "public_replay.py",
        HERE / "freeze_publication.py",
        HERE / "requirements.txt",
        HERE / ".gitignore",
        HERE / "README.md",
        HERE / "HANDOFF.md",
        HERE / "LICENSE",
    ]
    existing_source_files = [path for path in source_files if path.is_file()]
    clean, secret_hits = secrets_clean(existing_source_files)
    if not clean:
        raise RuntimeError(f"secret-like material found: {secret_hits}")
    receipt = {
        "schema_version": 2,
        "status": "strict_gate_clearer" if any(record["strict_gate_clearer"] for record in all_records) else "frozen_bounded_frontier",
        "claim_scope": (
            "Bounded continuous topology search only; not a proof of global optimality and not a closure "
            "of all evolutionary, MIQCP, interval, or continuous Heilbronn searches."
        ),
        "verifier_sha256": EXPECTED_VERIFIER_SHA256,
        "snapshot_sha256": sha256_path(SNAPSHOT),
        "leader": leader,
        "min_improvement": min_improvement,
        "strict_target": target,
        "nearest_public_metric": "minimum D3-invariant RMS under squared-cost Hungarian assignment",
        "public_solutions": len(public),
        "d3_distinct_public_basins": len(public_basins),
        "runs": run_receipts,
        "total_annealed_population_members": sum(
            int(run["template_population_members"]) + int(run["mutation_population_members"])
            for run in run_receipts
        ),
        "total_polished_records": len(all_records),
        "strict_gate_clearers": sum(bool(record["strict_gate_clearer"]) for record in all_records),
        "best_record": public_record(all_records[0]),
        "best_distinct_record": public_record(distinct[0]) if distinct else None,
        "minimum_true_d3_rms_over_retained_records": min(
            float(record["nearest_public_d3_rms"]) for record in all_records
        ),
        "all_candidate_payload_hashes_replayed": True,
        "all_candidate_scores_replayed_twice": True,
        "all_candidate_165_triangle_formula_replays_match": True,
        "boundary_mapping_regression": mapping_bug_impact(args.run_dirs, all_records, target),
        "prior_artifact_audit": prior_audit(len(public_basins)),
        "runtime_boundary": {
            "python": ">=3.11",
            "private_full_reproduction_requirements": "requirements.txt",
            "public_receipt_replay_dependencies": "Python >=3.11 standard library only",
        },
        "public_receipt_replay": {
            "path": "src/campaign/geometry/heilbronn_flow_topology_global/public_replay.py",
            "network_required": False,
            "campaign_snapshot_required": False,
            "raw_runs_required": False,
            "corpus_required": False,
            "numpy_scipy_torch_required": False,
            "downloaded_or_local_verifier_executed": False,
            "assurance_scope": (
                "Checks manifest bytes, receipt arithmetic, hash pins, scope labels, and absence of candidate arrays; "
                "it does not recompute geometric scores without the excluded coordinates and verifier."
            ),
        },
        "literature": [
            {
                "title": "Solving the Heilbronn Triangle Problem using Global Optimization Methods",
                "method": (
                    "MIQCP/QCP, bound tightening, symmetry breaking, adaptive discretization; "
                    "surveyed recursive rectangle-cell branch-and-bound"
                ),
                "paperclip": "https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L7-L22,L27-L79,L89-L97,L168-L176",
            },
            {
                "title": "Flow-based Extremal Mathematical Structure Discovery",
                "method": "smooth absolute value, annealed soft-min, stochastic relaxation, L-BFGS-B, active SLSQP",
                "paperclip": "https://paperclip.gxl.ai/citations/papers/arx_2601.18005#L1",
                "primary": "https://arxiv.org/html/2601.18005",
            },
            {
                "title": "Mathematical exploration and discovery at scale",
                "method": "evolutionary point proposals projected into the equilateral triangle",
                "paperclip": "https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L624-L640",
            },
            {
                "title": "GigaEvo",
                "method": "MAP-Elites, lineage-aware mutation, Halton/annealing/critical-triangle refinement",
                "paperclip": "https://paperclip.gxl.ai/citations/papers/arx_2511.17592#L1-L20,L33-L46,L76-L98",
            },
            {
                "title": "From Computational Certification to Exact Coordinates",
                "method": "MINLP certification followed by exact symbolic active-equation recovery",
                "paperclip": "https://paperclip.gxl.ai/citations/papers/arx_2603.11107#L1",
                "primary": "https://arxiv.org/html/2603.11107",
            },
        ],
        "publication_secret_scan_clean": clean,
    }
    output = HERE / "publication/receipt.json" if args.write else args.receipt_out
    if output is not None:
        output = output.resolve()
        if HERE != output.parent and HERE not in output.parents:
            raise RuntimeError(f"receipt output is outside isolated subtree: {output}")
        atomic_json(output, receipt)
    else:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
