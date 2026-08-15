#!/usr/bin/env python3
"""Validate and freeze the exact three-seed PSL-4 neighborhood receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
VERIFIER_SHA256 = "ff991bd84aec2b5b5d44f58a68dba00f961e01d517ec1de3225e0902f0f2fce2"
VERIFIER = (
    CAMPAIGN / "state" / "problems" / "flat-polynomials" / f"{VERIFIER_SHA256}.py"
)
LEADER_SCORE = 1.2807274949642549
GATE_SCORE = LEADER_SCORE - 1e-6
SEEDS = {
    "leukhin": "1001011001011001010100110011001100001010110101000000000010111100011111",
    "dimitrov": "1010110101101010101110011001110110010111100111100110110110000000001111",
    "pslrk": "1000000101010100010010000011011011110011100011010010001100110111101001",
}
JOURNALS = {label: HERE / "runs" / f"near-{label}-24.jsonl" for label in SEEDS}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def canonical_bits(bits: str) -> str:
    values = [1 if bit == "1" else -1 for bit in bits]
    images: list[str] = []
    for reverse in (False, True):
        for alternate in (False, True):
            for negate in (False, True):
                image = []
                for index in range(len(values)):
                    source = len(values) - 1 - index if reverse else index
                    value = values[source]
                    if alternate and index % 2:
                        value = -value
                    if negate:
                        value = -value
                    image.append("1" if value > 0 else "0")
                images.append("".join(image))
    return min(images)


def max_abs_autocorrelation(bits: str) -> int:
    values = [1 if bit == "1" else -1 for bit in bits]
    return max(
        abs(
            sum(
                values[index] * values[index + lag]
                for index in range(len(values) - lag)
            )
        )
        for lag in range(1, len(values))
    )


def parse_journal(label: str, path: Path) -> dict[str, Any]:
    rows = []
    seen: set[int] = set()
    answers: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split("\t")
        if len(fields) != 7 or fields[0] != "TASK":
            raise ValueError(f"{path}:{number}: malformed task row")
        task = int(fields[1])
        if task in seen:
            raise ValueError(f"{path}:{number}: duplicate task {task}")
        seen.add(task)
        task_answers = [] if fields[6] == "-" else fields[6].split(",")
        for bits in task_answers:
            if len(bits) != 70 or set(bits) - {"0", "1"}:
                raise ValueError(f"{path}:{number}: invalid class bits")
            if max_abs_autocorrelation(bits) > 4:
                raise ValueError(f"{path}:{number}: invalid PSL-4 class")
            answers.add(bits)
        rows.append(
            {
                "task": task,
                "nodes": int(fields[2]),
                "cheap_prunes": int(fields[3]),
                "exact_prunes": int(fields[4]),
                "task_seconds": float(fields[5]),
                "answers": task_answers,
            }
        )
    if len(rows) != 24:
        raise ValueError(f"{path}: expected 24 completed tasks, got {len(rows)}")
    expected = canonical_bits(SEEDS[label])
    if answers != {expected}:
        raise ValueError(f"{path}: expected only seed class {expected}, got {answers}")
    return {
        "label": label,
        "seed_bits": SEEDS[label],
        "canonical_seed_class": expected,
        "journal": f"runs/{path.name}",
        "journal_sha256": sha256(path),
        "task_count": len(rows),
        "task_ids": sorted(seen),
        "nodes": sum(row["nodes"] for row in rows),
        "cheap_prunes": sum(row["cheap_prunes"] for row in rows),
        "exact_prunes": sum(row["exact_prunes"] for row in rows),
        "sum_task_seconds": sum(row["task_seconds"] for row in rows),
        "max_task_seconds": max(row["task_seconds"] for row in rows),
        "class_count": len(answers),
        "classes": sorted(answers),
        "novel_class_count": len(answers - {expected}),
    }


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def build_receipt() -> dict[str, Any]:
    verifier_bytes = VERIFIER.read_bytes()
    actual_verifier_hash = hashlib.sha256(verifier_bytes).hexdigest()
    if actual_verifier_hash != VERIFIER_SHA256:
        raise ValueError(f"verifier hash changed: {actual_verifier_hash}")
    namespace: dict[str, Any] = {}
    exec(compile(verifier_bytes, str(VERIFIER), "exec"), namespace)  # noqa: S102

    runs = [parse_journal(label, JOURNALS[label]) for label in SEEDS]
    classes = sorted({bits for run in runs for bits in run["classes"]})
    class_replays = []
    for bits in classes:
        payload = {"coefficients": [1 if bit == "1" else -1 for bit in bits]}
        score = float(namespace["evaluate"](payload))
        class_replays.append(
            {
                "canonical_bits": bits,
                "max_abs_aperiodic_autocorrelation": max_abs_autocorrelation(bits),
                "payload_sha256": hashlib.sha256(canonical_json(payload)).hexdigest(),
                "verifier_score": score,
                "gap_to_gate": score - GATE_SCORE,
                "clears_gate": score < GATE_SCORE,
            }
        )

    return {
        "schema_version": 1,
        "status": "bounded_no_gate_clearer",
        "problem": "flat-polynomials",
        "size": 70,
        "psl_bound": 4,
        "live_leader_score": LEADER_SCORE,
        "strict_gate_score": GATE_SCORE,
        "verifier_sha256": actual_verifier_hash,
        "search_source": "psl4_exact.cpp",
        "search_source_sha256": sha256(HERE / "psl4_exact.cpp"),
        "regression_test": "tests/test_exact_bound.py",
        "regression_test_sha256": sha256(HERE / "tests" / "test_exact_bound.py"),
        "configuration": {
            "split_depth": 12,
            "assigned_outer_positions_per_task": 24,
            "total_viable_split_tasks": 678165,
            "selected_tasks_per_seed": 24,
            "threads": 6,
            "moment_depth": 0,
            "selection": "stable sort by assigned-border Hamming distance to seed",
            "symmetry_quotient": ["negation", "reversal", "alternation"],
        },
        "runs": runs,
        "aggregate": {
            "task_count": sum(run["task_count"] for run in runs),
            "nodes": sum(run["nodes"] for run in runs),
            "cheap_prunes": sum(run["cheap_prunes"] for run in runs),
            "exact_prunes": sum(run["exact_prunes"] for run in runs),
            "unique_classes": len(classes),
            "novel_classes": sum(run["novel_class_count"] for run in runs),
        },
        "class_replays": class_replays,
        "any_gate_clearer": any(row["clears_gate"] for row in class_replays),
        "scope": (
            "This closes exactly the 24 nearest viable split-depth-12 tasks for "
            "each of three published seed classes. It is not an exhaustive "
            "enumeration of all 678165 viable split tasks or all length-70 PSL-4 classes."
        ),
        "paperclip_citations": [
            "https://paperclip.gxl.ai/citations/papers/arx_2306.07156#L9-L12,L64-L74",
            "https://paperclip.gxl.ai/citations/papers/arx_1907.09464#L23,L32-L38,L79-L85",
            "https://paperclip.gxl.ai/citations/papers/arx_cond-mat9605050#L28-L67",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE / "receipt.json")
    args = parser.parse_args()
    receipt = build_receipt()
    atomic_json(args.output, receipt)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "tasks": receipt["aggregate"]["task_count"],
                "nodes": receipt["aggregate"]["nodes"],
                "unique_classes": receipt["aggregate"]["unique_classes"],
                "any_gate_clearer": receipt["any_gate_clearer"],
                "receipt_sha256": sha256(args.output),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
