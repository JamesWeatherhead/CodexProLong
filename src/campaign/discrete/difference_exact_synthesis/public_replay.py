#!/usr/bin/env python3
"""Network-free, verifier-free replay of the carry-exact formula packet.

This public replayer intentionally does not load the Arena corpus snapshot or
execute downloaded verifier code. It rebuilds all 19 CP-SAT formulas from the
small attributed residue-core input, checks their deterministic protobuf
hashes against the frozen event journals, and audits the recorded closure
scope. CP-SAT did not emit DRAT/LRAT certificates, so an INFEASIBLE status
remains a solver receipt rather than an independently checkable proof object.
"""

from __future__ import annotations

import gc
import json
from collections import Counter
from pathlib import Path
from typing import Any

import carry_exact_csp as csp
import complete_capacity_closure as capacity


HERE = Path(__file__).resolve().parent
DIRECT = HERE / "runs/20260815T063528Z_height7_full_support"
CAPACITY = HERE / "runs/20260815T073000Z_complete_capacity_closure"
HISTORICAL_CARRY_SOURCE_SHA256 = (
    "6704fa33ff1046cb3b8af03bf48d9b8476beb49c858b87d9af5ba89e81ef4508"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def frozen_inputs() -> dict[str, Any]:
    packet = read_json(HERE / "frozen_inputs.json")
    residues = [int(value) for value in packet["core"]["residues"]]
    if packet["core"]["modulus"] != csp.MODULUS:
        raise RuntimeError("modulus drift")
    if csp.sha256_json(residues) != packet["core"]["residues_sha256"]:
        raise RuntimeError("residue hash drift")
    if len(residues) != 90 or residues != sorted(set(residues)):
        raise RuntimeError("residue core shape drift")
    counts = Counter(
        (first - second) % csp.MODULUS
        for first in residues
        for second in residues
        if first != second
    )
    if set(counts) != set(range(1, csp.MODULUS)) or set(counts.values()) != {1}:
        raise RuntimeError("residue core is not a perfect cyclic difference set")
    return {
        "residues": residues,
        "gate_score": float(packet["leader"]["gate_score"]),
        "packet": packet,
    }


def validate_run(run: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    config = read_json(run / "config.json")
    events = read_events(run / "events.jsonl")
    summary = read_json(run / "summary.json")
    if csp.sha256_file(run / "events.jsonl") != summary["events_sha256"]:
        raise RuntimeError(f"event journal hash drift: {run}")
    if config["config_sha256"] != summary["config_sha256"]:
        raise RuntimeError(f"config/summary mismatch: {run}")
    if any(event["config_sha256"] != config["config_sha256"] for event in events):
        raise RuntimeError(f"event/config mismatch: {run}")
    return config, events, summary


def rebuild_formula(
    residues: list[int],
    *,
    total: int,
    target: int,
    event: dict[str, Any],
    complete_nonempty: bool,
) -> dict[str, Any]:
    if complete_nonempty:
        model, _, _, metadata = capacity.build_complete_model(residues, total, target, 7)
    else:
        model, _, _, metadata = csp.build_model(residues, total, target, 7)
    serialized = model.Proto().SerializeToString(deterministic=True)
    rebuilt_hash = csp.sha256_bytes(serialized)
    rebuilt_bytes = len(serialized)
    if rebuilt_hash != event["model_sha256"] or rebuilt_bytes != event["model_bytes"]:
        raise RuntimeError(f"formula hash drift for total={total}, target={target}")
    if csp.sha256_json(metadata) != csp.sha256_json(event["metadata"]):
        raise RuntimeError(f"formula metadata drift for total={total}, target={target}")
    del model
    gc.collect()
    return {
        "total": total,
        "target": target,
        "status": event["status"],
        "model_sha256": rebuilt_hash,
        "model_bytes": rebuilt_bytes,
    }


def main() -> int:
    inputs = frozen_inputs()
    direct_config, direct_events, direct_summary = validate_run(DIRECT)
    capacity_config, capacity_events, capacity_summary = validate_run(CAPACITY)

    if direct_config["source_sha256"] != HISTORICAL_CARRY_SOURCE_SHA256:
        raise RuntimeError("direct historical source pin drift")
    if capacity_config["carry_source_sha256"] != HISTORICAL_CARRY_SOURCE_SHA256:
        raise RuntimeError("capacity historical carry-source pin drift")
    if csp.sha256_file(Path(capacity.__file__)) != capacity_config["source_sha256"]:
        raise RuntimeError("capacity source hash drift")
    if direct_config["residues_sha256"] != inputs["packet"]["core"]["residues_sha256"]:
        raise RuntimeError("direct input hash drift")
    if capacity_config["public_snapshot_sha256"] != inputs["packet"]["source"]["public_snapshot_sha256"]:
        raise RuntimeError("capacity input provenance drift")
    if not direct_summary["all_requested_completed"]:
        raise RuntimeError("direct run incomplete")
    if direct_summary["status_counts"] != {"INFEASIBLE": 12}:
        raise RuntimeError("direct run status drift")
    if not capacity_summary["all_cases_infeasible"]:
        raise RuntimeError("capacity closure status drift")

    direct_by_total = {int(event["total_size"]): event for event in direct_events}
    rebuilt = []
    for total in range(360, 372):
        target = csp.required_coverage(total, inputs["gate_score"])
        event = direct_by_total[total]
        if event["target_coverage"] != target or event["status"] != "INFEASIBLE":
            raise RuntimeError(f"direct semantic drift at {total}")
        rebuilt.append(
            rebuild_formula(
                inputs["residues"],
                total=total,
                target=target,
                event=event,
                complete_nonempty=False,
            )
        )

    capacity_by_range = {
        (int(event["low_size"]), int(event["high_size"])): event
        for event in capacity_events
    }
    closed = set(range(360, 372))
    for low, high in capacity.CASES:
        event = capacity_by_range[(low, high)]
        target = csp.required_coverage(low, inputs["gate_score"])
        if event["capacity"] != high or event["target_coverage"] != target:
            raise RuntimeError(f"capacity semantic drift at {low}-{high}")
        if event["status"] != "INFEASIBLE":
            raise RuntimeError(f"capacity status drift at {low}-{high}")
        item = rebuild_formula(
            inputs["residues"],
            total=high,
            target=target,
            event=event,
            complete_nonempty=True,
        )
        item["closed_range"] = [low, high]
        rebuilt.append(item)
        closed.update(range(low, high + 1))

    if closed != set(range(320, 412)):
        raise RuntimeError("finite closure is not exactly sizes 320..411")
    target_412 = csp.required_coverage(412, inputs["gate_score"])
    if target_412 < 8 * csp.MODULUS + 1:
        raise RuntimeError("size-412 structural ceiling drift")

    output = {
        "status": "pass",
        "formula_count": len(rebuilt),
        "all_recorded_statuses": "INFEASIBLE",
        "finite_closed_sizes": [320, 411],
        "structural_closed_sizes": [412, 720],
        "residues_sha256": inputs["packet"]["core"]["residues_sha256"],
        "historical_solver_source_sha256": HISTORICAL_CARRY_SOURCE_SHA256,
        "public_solver_source_sha256": csp.sha256_file(Path(csp.__file__)),
        "direct_events_sha256": csp.sha256_file(DIRECT / "events.jsonl"),
        "capacity_events_sha256": csp.sha256_file(CAPACITY / "events.jsonl"),
        "scope_caveat": (
            "Formula hashes and solver receipts replay; no DRAT/LRAT proof was emitted, "
            "and the claim is confined to the fixed modulo-8011 shell-0..7 family."
        ),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
