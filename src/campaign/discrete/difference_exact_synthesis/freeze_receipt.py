#!/usr/bin/env python3
"""Independently rebuild every carry-exact formula and freeze its receipt."""

from __future__ import annotations

import gc
import json
from pathlib import Path
from typing import Any

import carry_exact_csp as csp
import complete_capacity_closure


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
DIRECT = ROOT / "runs/20260815T063528Z_height7_full_support"
CAPACITY = ROOT / "runs/20260815T073000Z_complete_capacity_closure"
OUTPUT = ROOT / "receipt.json"
HISTORICAL_CARRY_SOURCE_SHA256 = (
    "6704fa33ff1046cb3b8af03bf48d9b8476beb49c858b87d9af5ba89e81ef4508"
)


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def relative(path: Path) -> str:
    return str(path.relative_to(REPO))


def validate_run_files(run: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    config = read(run / "config.json")
    run_events = events(run / "events.jsonl")
    summary = read(run / "summary.json")
    if csp.sha256_file(run / "events.jsonl") != summary["events_sha256"]:
        raise RuntimeError(f"events hash drift in {run}")
    if config["config_sha256"] != summary["config_sha256"]:
        raise RuntimeError(f"config/summary mismatch in {run}")
    if any(event["config_sha256"] != config["config_sha256"] for event in run_events):
        raise RuntimeError(f"event/config mismatch in {run}")
    return config, run_events, summary


def rebuild(
    residues: list[int],
    event: dict[str, Any],
    total: int,
    target: int,
    *,
    complete_nonempty: bool = False,
) -> dict[str, Any]:
    if complete_nonempty:
        model, _, _, metadata = complete_capacity_closure.build_complete_model(
            residues, total, target, 7
        )
    else:
        model, _, _, metadata = csp.build_model(residues, total, target, 7)
    serialized = model.Proto().SerializeToString(deterministic=True)
    rebuilt = {
        "model_sha256": csp.sha256_bytes(serialized),
        "model_bytes": len(serialized),
        "metadata": metadata,
    }
    for key in ("model_sha256", "model_bytes"):
        if rebuilt[key] != event[key]:
            raise RuntimeError(f"formula rebuild mismatch for {total}/{target}: {key}")
    # JSON round-tripping converts the integer keys of the pattern-size
    # histogram to strings. Canonical JSON equality is the intended check.
    if csp.sha256_json(rebuilt["metadata"]) != csp.sha256_json(event["metadata"]):
        raise RuntimeError(f"formula rebuild mismatch for {total}/{target}: metadata")
    del model
    gc.collect()
    return {
        "total": total,
        "target": target,
        "model_sha256": rebuilt["model_sha256"],
        "model_bytes": rebuilt["model_bytes"],
        "status": event["status"],
    }


def main() -> int:
    inputs = csp.load_inputs()
    direct_config, direct_events, direct_summary = validate_run_files(DIRECT)
    capacity_config, capacity_events, capacity_summary = validate_run_files(CAPACITY)

    if direct_config["source_sha256"] != HISTORICAL_CARRY_SOURCE_SHA256:
        raise RuntimeError("direct historical source pin drift")
    if capacity_config["carry_source_sha256"] != HISTORICAL_CARRY_SOURCE_SHA256:
        raise RuntimeError("capacity historical carry-source pin drift")
    if (
        csp.sha256_file(Path(complete_capacity_closure.__file__))
        != capacity_config["source_sha256"]
    ):
        raise RuntimeError("capacity source hash drift")
    if direct_config["verifier_sha256"] != csp.PINNED_VERIFIER_SHA256:
        raise RuntimeError("direct verifier pin drift")
    if capacity_config["verifier_sha256"] != csp.PINNED_VERIFIER_SHA256:
        raise RuntimeError("capacity verifier pin drift")
    if not direct_summary["all_requested_completed"]:
        raise RuntimeError("direct run incomplete")
    if direct_summary["status_counts"] != {"INFEASIBLE": 12}:
        raise RuntimeError("direct run is not a 12-formula closure")
    if not capacity_summary["all_cases_infeasible"]:
        raise RuntimeError("capacity run is not closed")

    direct_by_total = {int(event["total_size"]): event for event in direct_events}
    direct_rebuilds = []
    for total in range(360, 372):
        event = direct_by_total[total]
        target = csp.required_coverage(total, inputs["gate_score"])
        if event["target_coverage"] != target or event["status"] != "INFEASIBLE":
            raise RuntimeError(f"direct semantic drift at size {total}")
        direct_rebuilds.append(rebuild(inputs["residues"], event, total, target))

    capacity_by_range = {
        (int(event["low_size"]), int(event["high_size"])): event
        for event in capacity_events
    }
    capacity_rebuilds = []
    for low, high in complete_capacity_closure.CASES:
        event = capacity_by_range[(low, high)]
        target = csp.required_coverage(low, inputs["gate_score"])
        if event["capacity"] != high or event["target_coverage"] != target:
            raise RuntimeError(f"capacity semantic drift for {low}-{high}")
        if event["status"] != "INFEASIBLE":
            raise RuntimeError(f"capacity case is not closed for {low}-{high}")
        item = rebuild(
            inputs["residues"],
            event,
            high,
            target,
            complete_nonempty=True,
        )
        item["closed_range"] = [low, high]
        capacity_rebuilds.append(item)

    closed = set(range(360, 372))
    for low, high in complete_capacity_closure.CASES:
        closed.update(range(low, high + 1))
    if closed != set(range(320, 412)):
        raise RuntimeError("closed cardinalities are not exactly 320..411")

    target_412 = csp.required_coverage(412, inputs["gate_score"])
    if target_412 < 8 * csp.MODULUS + 1:
        raise RuntimeError("size-412 structural ceiling arithmetic drift")
    residue_one_witnesses = [
        (a, b)
        for a in inputs["residues"]
        for b in inputs["residues"]
        if a != b and (a - b) % csp.MODULUS == 1
    ]
    if len(residue_one_witnesses) != 1:
        raise RuntimeError("residue-1 witness is not unique")

    publish_paths = [
        ROOT / "README.md",
        ROOT / "HANDOFF.md",
        ROOT / "PROVENANCE.md",
        ROOT / "carry_exact_csp.py",
        ROOT / "complete_capacity_closure.py",
        ROOT / "test_carry_exact_csp.py",
        ROOT / "frozen_inputs.json",
        ROOT / "public_replay.py",
        ROOT / "freeze_receipt.py",
        DIRECT / "config.json",
        DIRECT / "events.jsonl",
        DIRECT / "summary.json",
        CAPACITY / "config.json",
        CAPACITY / "events.jsonl",
        CAPACITY / "summary.json",
    ]
    receipt = {
        "schema": 1,
        "claim": (
            "Within the frozen leader's 90-residue modulo-8011 core and arbitrary "
            "independent support subsets of shells 0..7, no cardinality 320..720 "
            "can clear the live gate: 320..411 are exact finite CP-SAT closures, "
            "and 412..720 require an unavailable height difference 8."
        ),
        "scope_caveat": (
            "This is not a global Difference Bases impossibility result; sizes below "
            "320, other shell ranges, changed residue cores, and non-quotient "
            "constructions remain outside the proof family. CP-SAT emitted no "
            "DRAT/LRAT certificate."
        ),
        "leader": {
            "id": csp.PINNED_LEADER_ID,
            "size": 360,
            "coverage": inputs["leader_coverage"],
            "score": inputs["leader_score"],
            "score_fraction": "129600/49109",
            "payload_sha256": inputs["leader_payload_sha256"],
            "min_improvement": inputs["min_improvement"],
            "gate_score": inputs["gate_score"],
        },
        "pins": {
            "verifier_sha256": csp.PINNED_VERIFIER_SHA256,
            "public_snapshot_sha256": csp.PINNED_PUBLIC_SHA256,
            "residues_sha256": direct_config["residues_sha256"],
            "ortools_version": direct_config["ortools_version"],
            "historical_solver_source_sha256": HISTORICAL_CARRY_SOURCE_SHA256,
            "public_solver_source_sha256": csp.sha256_file(Path(csp.__file__)),
        },
        "direct_closure": {
            "sizes": [360, 371],
            "formula_count": len(direct_rebuilds),
            "rebuilds": direct_rebuilds,
            "config_sha256": csp.sha256_file(DIRECT / "config.json"),
            "events_sha256": csp.sha256_file(DIRECT / "events.jsonl"),
            "summary_sha256": csp.sha256_file(DIRECT / "summary.json"),
        },
        "capacity_closure": {
            "formula_count": len(capacity_rebuilds),
            "rebuilds": capacity_rebuilds,
            "config_sha256": csp.sha256_file(CAPACITY / "config.json"),
            "events_sha256": csp.sha256_file(CAPACITY / "events.jsonl"),
            "summary_sha256": csp.sha256_file(CAPACITY / "summary.json"),
            "monotonicity": (
                "adding unused shell points preserves all existing differences"
            ),
        },
        "structural_ceiling": {
            "sizes": [412, 720],
            "size_412_required_coverage": target_412,
            "critical_integer": 8 * csp.MODULUS + 1,
            "unique_residue_one_witness": list(residue_one_witnesses[0]),
            "maximum_height_difference": 7,
        },
        "tests": {
            "command": (
                ".venv/bin/python campaign/discrete/difference_exact_synthesis/"
                "test_carry_exact_csp.py -v"
            ),
            "count": 6,
            "public_replay_command": (
                ".venv/bin/python campaign/discrete/difference_exact_synthesis/"
                "public_replay.py"
            ),
            "public_replay_formula_count": 19,
            "public_replay_status": "pass",
            "status": "pass",
        },
        "publish_safe_artifacts": {
            relative(path): csp.sha256_file(path) for path in publish_paths
        },
        "excluded_inputs": [
            "campaign/discrete/difference_global/checkpoints/public_latest.json",
            "all Arena full-discussion snapshots and third-party payload arrays",
            "campaign/discrete/difference_exact_synthesis/capacity_closure.py",
            "campaign/discrete/difference_exact_synthesis/runs/20260815T065500Z_capacity_closure/",
            "__pycache__/",
        ],
        "gate_cleared": False,
        "external_writes": False,
    }
    csp.atomic_json(OUTPUT, receipt)
    print(OUTPUT)
    print(
        json.dumps(
            {
                "receipt_sha256": csp.sha256_file(OUTPUT),
                "formulas_rebuilt": len(direct_rebuilds) + len(capacity_rebuilds),
                "gate_cleared": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
