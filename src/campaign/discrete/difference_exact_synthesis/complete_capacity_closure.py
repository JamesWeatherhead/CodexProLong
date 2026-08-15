#!/usr/bin/env python3
"""Complete nonempty-support capacity closures for the eight-shell family.

Unlike the superseded exploratory capacity run, this model includes singleton
columns. Empty columns alone are omitted: because the residue core is a perfect
difference set, an empty column deletes the unique witness for every cyclic
difference involving that residue, so it cannot cover even the first complete
residue interval required by any case here.
"""

from __future__ import annotations

import argparse
import gc
import itertools
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from ortools.sat.python import cp_model

import carry_exact_csp as csp


CASES = (
    (320, 329),
    (330, 339),
    (340, 349),
    (350, 356),
    (357, 359),
    (372, 384),
    (385, 411),
)
PINNED_CARRY_SOURCE_SHA256 = "6704fa33ff1046cb3b8af03bf48d9b8476beb49c858b87d9af5ba89e81ef4508"


def complete_patterns(height_max: int) -> list[tuple[int, ...]]:
    return [
        support
        for size in range(1, height_max + 2)
        for support in itertools.combinations(range(height_max + 1), size)
    ]


def build_complete_model(
    residues: Sequence[int], total_size: int, target: int, height_max: int = 7
) -> tuple[cp_model.CpModel, list[Any], list[tuple[int, ...]], dict[str, Any]]:
    supports = complete_patterns(height_max)
    internal = [{a - b for a in s for b in s} for s in supports]
    model = cp_model.CpModel()
    variables = [
        model.NewIntVar(0, len(supports) - 1, f"support_{index}")
        for index in range(len(residues))
    ]
    sizes = []
    size_table = [(index, len(support)) for index, support in enumerate(supports)]
    for index, variable in enumerate(variables):
        size = model.NewIntVar(1, height_max + 1, f"size_{index}")
        model.AddAllowedAssignments([variable, size], size_table)
        sizes.append(size)
    model.Add(sum(sizes) == total_size)

    relation_cache: dict[frozenset[int], list[tuple[int, int]]] = {}
    class_counts: Counter[str] = Counter()
    class_sizes: dict[str, int] = {}
    for high in range(len(residues)):
        for low in range(high):
            required = csp.cross_requirements(residues[high] - residues[low], target)
            if required not in relation_cache:
                relation_cache[required] = csp.relation(supports, required)
            allowed = relation_cache[required]
            key = ",".join(map(str, sorted(required)))
            class_counts[key] += 1
            class_sizes[key] = len(allowed)
            model.AddAllowedAssignments([variables[high], variables[low]], allowed)

    for difference in csp.same_column_requirements(target):
        good = {index for index, diffs in enumerate(internal) if difference in diffs}
        indicator_table = [
            (index, int(index in good)) for index in range(len(supports))
        ]
        indicators = []
        for index, variable in enumerate(variables):
            indicator = model.NewBoolVar(f"internal_{difference}_{index}")
            model.AddAllowedAssignments([variable, indicator], indicator_table)
            indicators.append(indicator)
        model.AddBoolOr(indicators)

    metadata = {
        "pattern_count": len(supports),
        "pattern_size_histogram": dict(sorted(Counter(map(len, supports)).items())),
        "cross_requirement_class_counts": dict(sorted(class_counts.items())),
        "cross_relation_tuple_counts": dict(sorted(class_sizes.items())),
        "same_column_requirements": list(csp.same_column_requirements(target)),
    }
    return model, variables, supports, metadata


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=600.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    if csp.sha256_file(Path(csp.__file__)) != PINNED_CARRY_SOURCE_SHA256:
        raise RuntimeError("carry_exact_csp.py hash drift")
    inputs = csp.load_inputs()
    cases = [
        {
            "low_size": low,
            "high_size": high,
            "capacity": high,
            "target_coverage": csp.required_coverage(low, inputs["gate_score"]),
        }
        for low, high in CASES
    ]
    config = {
        "schema": 2,
        "method": "complete_nonempty_support_monotone_capacity_closure",
        "cases": cases,
        "height_max": 7,
        "pattern_count": 255,
        "minimum_column_size": 1,
        "maximum_family_capacity": 720,
        "seconds_per_case": args.seconds,
        "workers": args.workers,
        "carry_source_sha256": PINNED_CARRY_SOURCE_SHA256,
        "source_sha256": csp.sha256_file(Path(__file__)),
        "public_snapshot_sha256": csp.PINNED_PUBLIC_SHA256,
        "verifier_sha256": csp.PINNED_VERIFIER_SHA256,
        "leader_payload_sha256": inputs["leader_payload_sha256"],
        "gate_score": inputs["gate_score"],
    }
    config["config_sha256"] = csp.sha256_json(config)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    config_path = args.run_dir / "config.json"
    if config_path.exists():
        if json.loads(config_path.read_text(encoding="utf-8")) != config:
            raise RuntimeError("resume config mismatch")
    else:
        csp.atomic_json(config_path, config)

    events_path = args.run_dir / "events.jsonl"
    run_events = read_events(events_path)
    if any(event.get("config_sha256") != config["config_sha256"] for event in run_events):
        raise RuntimeError("event/config mismatch")
    completed = {
        (int(event["low_size"]), int(event["high_size"])): event
        for event in run_events
    }

    for case in cases:
        key = (case["low_size"], case["high_size"])
        if key in completed:
            print(json.dumps({"resume_skip": list(key), "status": completed[key]["status"]}))
            continue
        model, variables, supports, metadata = build_complete_model(
            inputs["residues"], case["capacity"], case["target_coverage"], 7
        )
        model_bytes = model.Proto().SerializeToString(deterministic=True)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = args.seconds
        solver.parameters.num_search_workers = args.workers
        solver.parameters.random_seed = 0
        started = time.monotonic()
        status = solver.Solve(model)
        event: dict[str, Any] = {
            "schema": 2,
            **case,
            "target_quotient_remainder": list(
                divmod(case["target_coverage"], csp.MODULUS)
            ),
            "height_max": 7,
            "minimum_column_size": 1,
            "status": solver.StatusName(status),
            "wall_seconds": time.monotonic() - started,
            "conflicts": solver.NumConflicts(),
            "branches": solver.NumBranches(),
            "model_bytes": len(model_bytes),
            "model_sha256": csp.sha256_bytes(model_bytes),
            "metadata": metadata,
            "config_sha256": config["config_sha256"],
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "closure_logic": (
                "a witness at any k in [low_size,high_size] can be padded with "
                "unused shell points to capacity=high_size without losing coverage"
            ),
        }
        if status in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            selected = [supports[solver.Value(variable)] for variable in variables]
            event["selected_supports"] = selected
            event["replay"] = csp.replay_candidate(inputs["residues"], selected, inputs)
        csp.append_jsonl(events_path, event)
        completed[key] = event
        print(
            json.dumps(
                {
                    "range": list(key),
                    "capacity": case["capacity"],
                    "target": case["target_coverage"],
                    "status": event["status"],
                    "seconds": event["wall_seconds"],
                },
                sort_keys=True,
            ),
            flush=True,
        )
        del model, solver, variables, supports
        gc.collect()

    ordered = [completed[case] for case in CASES]
    summary = {
        "schema": 2,
        "config_sha256": config["config_sha256"],
        "all_cases_completed": len(ordered) == len(CASES),
        "all_cases_infeasible": all(event["status"] == "INFEASIBLE" for event in ordered),
        "closed_ranges": [
            [event["low_size"], event["high_size"]]
            for event in ordered
            if event["status"] == "INFEASIBLE"
        ],
        "events_sha256": csp.sha256_file(events_path),
        "gate_cleared": any(
            event.get("replay", {}).get("gate_cleared", False) for event in ordered
        ),
        "structural_ceiling": {
            "first_unrepresentable_gate_size": 412,
            "required_coverage": csp.required_coverage(412, inputs["gate_score"]),
            "reason": (
                "the prefix includes 8*8011+1; the unique residue-1 pair needs "
                "height difference 8, outside shells 0..7"
            ),
        },
    }
    csp.atomic_json(args.run_dir / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["all_cases_infeasible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
