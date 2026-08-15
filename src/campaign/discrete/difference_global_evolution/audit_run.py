#!/usr/bin/env python3
"""Independent exact replay for a frozen Difference Bases evolution run.

This module intentionally does not import solver.py.  It recomputes every
retained construction using Python integer bitsets, verifies all recorded
hashes/metrics, and emits a compact receipt without construction arrays.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Sequence


CARDINALITY = 360
TARGET = 49_110
TAIL = 2_048
LEADER_SCORE = 2.639027469506608
MIN_IMPROVEMENT = 1e-9
STRICT_GATE = LEADER_SCORE - MIN_IMPROVEMENT
TARGET_MASK = ((1 << (TARGET + 1)) - 1) ^ 1
TAIL_MASK = ((1 << (TARGET + TAIL + 1)) - 1) ^ ((1 << (TARGET + 1)) - 1)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha_value(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    raw = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(raw, encoding="utf-8")
    os.replace(temporary, path)


def difference_bits(values: Sequence[int]) -> int:
    marks = 0
    for value in values:
        marks |= 1 << value
    covered = 1
    for value in values:
        covered |= marks >> value
    return covered


def first_missing(bits: int) -> int:
    return ((~bits) & (bits + 1)).bit_length() - 1


def exact_metrics(raw_values: Iterable[Any]) -> tuple[tuple[int, ...], dict[str, Any], int]:
    values = tuple(raw_values)
    if any(type(value) is not int for value in values):
        raise AssertionError("all marks must be literal JSON integers")
    if len(values) != CARDINALITY or len(set(values)) != CARDINALITY:
        raise AssertionError("construction must contain 360 distinct marks")
    if tuple(sorted(values)) != values or values[0] != 0:
        raise AssertionError("construction must be sorted and normalized")
    if any(value < 0 for value in values):
        raise AssertionError("marks must be nonnegative")
    bits = difference_bits(values)
    coverage = first_missing(bits) - 1
    missing = (TARGET_MASK & ~bits).bit_count()
    exact = Fraction(CARDINALITY**2, coverage)
    metrics = {
        "missing_target": missing,
        "coverage": coverage,
        "tail_present": (TAIL_MASK & bits).bit_count(),
        "maximum_mark": values[-1],
        "score_numerator": exact.numerator,
        "score_denominator": exact.denominator,
        "score_float": float(exact),
        "gate_clearing": float(exact) < STRICT_GATE,
        "marks_sha256": sha_value(list(values)),
        "payload_sha256": sha_value({"set": list(values)}),
    }
    return values, metrics, bits


def verify_record(record: dict[str, Any]) -> tuple[tuple[int, ...], dict[str, Any], int]:
    values, metrics, bits = exact_metrics(record["set"])
    for key, expected in metrics.items():
        if record.get(key) != expected:
            raise AssertionError(
                f"record {record.get('origin')} field {key}: "
                f"{record.get(key)!r} != {expected!r}"
            )
    return values, metrics, bits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--solver", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    solver = args.solver.resolve()
    paths = {
        name: run_dir / name
        for name in ("config.json", "events.jsonl", "checkpoint.json", "summary.json")
    }
    for path in (*paths.values(), solver):
        if not path.is_file():
            raise SystemExit(f"missing replay input: {path}")

    config = json.loads(paths["config.json"].read_text(encoding="utf-8"))
    checkpoint = json.loads(paths["checkpoint.json"].read_text(encoding="utf-8"))
    summary = json.loads(paths["summary.json"].read_text(encoding="utf-8"))
    config_hash = sha_value(config)
    source_hash = sha_file(solver)
    if config_hash != summary["config_sha256"] or config_hash != checkpoint["config_sha256"]:
        raise AssertionError("config hash mismatch")
    if source_hash != config["source_sha256"] or source_hash != summary["source_sha256"]:
        raise AssertionError("solver source hash mismatch")
    if checkpoint["source_sha256"] != source_hash:
        raise AssertionError("checkpoint source hash mismatch")
    if checkpoint["next_iteration"] != summary["completed_iterations"]:
        raise AssertionError("checkpoint/summary iteration mismatch")

    named_records = {
        "current": checkpoint["current"],
        "best": checkpoint["best"],
        "target_best": checkpoint["target_best"],
    }
    retained = []
    for name, record in named_records.items():
        values, metrics, bits = verify_record(record)
        retained.append((name, record, values, metrics, bits))
    for index, record in enumerate(checkpoint["archive"]):
        values, metrics, bits = verify_record(record)
        retained.append((f"archive[{index}]", record, values, metrics, bits))

    best_record = named_records["best"]
    target_record = named_records["target_best"]
    if best_record["payload_sha256"] != summary["best"]["payload_sha256"]:
        raise AssertionError("best checkpoint/summary mismatch")
    if target_record["payload_sha256"] != summary["target_basin_best"]["payload_sha256"]:
        raise AssertionError("target-best checkpoint/summary mismatch")
    if not any((bits >> TARGET) & 1 for _n, _r, _v, _m, bits in retained):
        raise AssertionError("no retained target-covered state")

    incumbent_values = next(
        values for name, _record, values, _metrics, _bits in retained if name == "best"
    )
    incumbent_set = set(incumbent_values)
    max_retained_change = max(
        len(incumbent_set - set(values)) for _n, _r, values, _m, _b in retained
    )

    compact_files = {
        name: {"sha256": sha_file(path), "bytes": path.stat().st_size}
        for name, path in paths.items()
    }
    compact_files["solver.py"] = {
        "sha256": source_hash,
        "bytes": solver.stat().st_size,
    }
    receipt = {
        "schema": "difference-global-evolution-audit-v1",
        "status": "exact_replay_passed",
        "files": compact_files,
        "pins": {
            "verifier_sha256": config["verifier_sha256"],
            "snapshot_sha256": config["snapshot_sha256"],
            "leader_id": config["leader_id"],
            "leader_payload_sha256": config["leader_payload_sha256"],
            "strict_gate": config["strict_gate"],
            "target": TARGET,
            "cardinality": CARDINALITY,
        },
        "run": {
            "seed": config["seed"],
            "iterations": summary["completed_iterations"],
            "elapsed_seconds": summary["elapsed_seconds"],
            "proposals": summary["stats"]["proposals"],
            "accepted": summary["stats"]["accepted"],
            "operator_calls": summary["stats"]["operator_calls"],
            "operator_accepts": summary["stats"]["operator_accepts"],
            "target_improvements": summary["stats"]["target_improvements"],
            "maximum_accepted_changed_marks": summary["stats"]["max_changed_marks"],
            "maximum_retained_changed_marks": max_retained_change,
            "retained_records_replayed": len(retained),
        },
        "incumbent": {
            key: best_record[key]
            for key in (
                "payload_sha256",
                "marks_sha256",
                "missing_target",
                "coverage",
                "score_numerator",
                "score_denominator",
                "score_float",
                "gate_clearing",
            )
        },
        "target_basin_frontier": {
            key: target_record[key]
            for key in (
                "payload_sha256",
                "marks_sha256",
                "missing_target",
                "coverage",
                "tail_present",
                "maximum_mark",
                "score_numerator",
                "score_denominator",
                "score_float",
                "gate_clearing",
            )
        },
        "gate": {
            "required_coverage_at_360": TARGET,
            "incumbent_gap_in_coverage": TARGET - best_record["coverage"],
            "target_basin_missing_difference_count": target_record["missing_target"],
            "cleared": bool(summary["gate_clearer"]),
        },
        "conclusion": (
            "The bounded changed-core evolutionary/LNS run produced no strict "
            "gate-clearer. Every retained construction was independently "
            "recomputed with exact Python-integer difference bitsets."
        ),
    }
    atomic_json(args.output.resolve(), receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
