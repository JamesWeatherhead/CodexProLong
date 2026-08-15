#!/usr/bin/env python3
"""Measure the durable per-task dispatcher on exactly two reference shards."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import gpu_dispatch


ROOT = Path(__file__).resolve().parent
FIXTURES = {
    0: ROOT / "fixtures" / "shard0_reference.tsv",
    1: ROOT / "fixtures" / "shard1_reference.tsv",
}
SAMPLE = ROOT / "fixtures" / "completed_shard_sample.tsv"
ENGINE_CONCURRENCY_RECEIPT = ROOT / "runs" / "20260815T093000Z" / "concurrency_receipt.json"
FIELDS = (
    "nodes", "leaves", "central_rejects", "strong_cheap_prunes", "exact_checks",
    "exact_prunes",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_reference(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            answers = [] if row["answer"] == "-" else row["answer"].split(",")
            record = {field: int(row[field]) for field in ("task_index", *FIELDS)}
            record["valid_leaves"] = len(answers)
            record["answers"] = answers
            records.append(record)
    return records


def load_dispatched_tasks(run_dir: Path, shard: int) -> list[dict[str, Any]]:
    task_dir = run_dir / "shards" / f"{shard:06d}" / "tasks"
    return [
        json.loads(path.read_text(encoding="utf-8"))["engine"]["tasks"][0]
        for path in sorted(task_dir.glob("*.json"))
    ]


def compare(shard: int, observed: list[dict[str, Any]]) -> dict[str, Any]:
    expected = load_reference(FIXTURES[shard])
    fields = ("task_index", *FIELDS, "valid_leaves", "answers")
    if len(observed) != len(expected):
        raise RuntimeError(f"shard {shard} task-count mismatch")
    for wanted, got in zip(expected, observed):
        differences = {
            field: {"expected": wanted[field], "observed": got.get(field)}
            for field in fields
            if wanted[field] != got.get(field)
        }
        if differences:
            raise RuntimeError(
                f"shard {shard} task {wanted['task_index']} mismatch: {differences}"
            )
    return {
        "task_count": len(expected),
        "counter_or_answer_mismatches": 0,
        "reference_sha256": sha256(FIXTURES[shard]),
        "totals": {
            field: sum(record[field] for record in expected)
            for field in (*FIELDS, "valid_leaves")
        },
    }


def run(command: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=timeout, cwd=ROOT
    )


def run_pair(run_dir: Path) -> tuple[dict[int, dict[str, Any]], float]:
    processes: dict[int, subprocess.Popen[str]] = {}
    started = time.perf_counter()
    for shard in (0, 1):
        processes[shard] = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "gpu_dispatch.py"),
                "--run-dir",
                str(run_dir),
                "--virtual-shards",
                "8192",
                "--shard",
                str(shard),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    receipts: dict[int, dict[str, Any]] = {}
    try:
        for shard, process in processes.items():
            stdout, stderr = process.communicate(timeout=300)
            if process.returncode != 0:
                raise RuntimeError(f"dispatcher shard {shard} failed: {stderr}")
            receipts[shard] = json.loads(stdout)
    except BaseException:
        for process in processes.values():
            if process.poll() is None:
                process.kill()
        raise
    return receipts, time.perf_counter() - started


def load_sample() -> list[dict[str, Any]]:
    rows = []
    with SAMPLE.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            rows.append(
                {
                    "nodes": int(row["nodes"]),
                    "solver_seconds": float(row["solver_seconds"]),
                    "fresh": bool(int(row["fresh_from_empty"])),
                }
            )
    return rows


def write_new(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"write-once output exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(gpu_dispatch.canonical_json(payload))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        gpu_dispatch.fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="fresh structured run root to retain; omitted means a disposable test root",
    )
    parser.add_argument("--retained-relative-path")
    parser.add_argument("--audit-out", type=Path)
    arguments = parser.parse_args()
    if bool(arguments.run_dir) != bool(arguments.retained_relative_path):
        parser.error("--run-dir and --retained-relative-path must be supplied together")
    if arguments.audit_out and not arguments.run_dir:
        parser.error("--audit-out requires a retained --run-dir")
    temporary: tempfile.TemporaryDirectory[str] | None = None
    if arguments.run_dir:
        run_dir = arguments.run_dir.resolve()
        if run_dir.exists():
            raise FileExistsError(f"retained run root must be fresh: {run_dir}")
    else:
        temporary = tempfile.TemporaryDirectory(
            prefix="psl4-metal-dispatch-benchmark-", dir="/private/tmp"
        )
        run_dir = Path(temporary.name) / "psl4-metal-run-20260815T120300Z-benchmark"
    try:
        init = json.loads(
            run(
                [
                    sys.executable,
                    str(ROOT / "gpu_dispatch.py"),
                    "--run-dir",
                    str(run_dir),
                    "--virtual-shards",
                    "8192",
                    "--init-only",
                ]
            ).stdout
        )
        receipts, pair_wall = run_pair(run_dir)
        comparisons = {
            str(shard): compare(shard, load_dispatched_tasks(run_dir, shard))
            for shard in (0, 1)
        }
        audit = json.loads(
            run(
                [
                    sys.executable,
                    str(ROOT / "audit_run.py"),
                    "--run-dir",
                    str(run_dir),
                    "--allow-incomplete",
                ]
            ).stdout
        )
        config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        config_sha256 = sha256(run_dir / "config.json")
        initialization_sha256 = sha256(run_dir / "initialization.json")
        task_wall_sums = {
            str(shard): sum(
                json.loads(path.read_text(encoding="utf-8"))["external_wall_seconds"]
                for path in (run_dir / "shards" / f"{shard:06d}" / "tasks").glob("*.json")
            )
            for shard in (0, 1)
        }
    finally:
        if temporary is not None:
            temporary.cleanup()

    total_nodes = sum(receipts[shard]["totals"]["nodes"] for shard in (0, 1))
    nodes_per_second = total_nodes / pair_wall
    sample = load_sample()
    nodes = [row["nodes"] for row in sample]
    fresh_seconds = [row["solver_seconds"] for row in sample if row["fresh"]]
    mean_nodes = statistics.fmean(nodes)
    eta_seconds = mean_nodes * 8192 / nodes_per_second
    cpu_eta_seconds = statistics.fmean(fresh_seconds) * 8192 / 8
    engine_receipt = json.loads(ENGINE_CONCURRENCY_RECEIPT.read_text(encoding="utf-8"))
    memory = engine_receipt["resource_stability"]
    audit_evidence_sha256 = None
    if arguments.audit_out:
        audit_payload = {
            "schema": "psl4-metal-retained-validation-audit-v1",
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "status": "pass",
            "run_name": run_dir.name,
            "retained_relative_path": arguments.retained_relative_path,
            "audit": audit,
        }
        write_new(arguments.audit_out.resolve(), audit_payload)
        audit_evidence_sha256 = sha256(arguments.audit_out.resolve())
    payload = {
        "schema": "psl4-metal-durable-dispatcher-benchmark-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "pass",
        "scope": "exactly two reference shards; never a production run",
        "source_sha256": config["source_sha256"],
        "binary_sha256": config["binary_sha256"],
        "config_schema": config["schema"],
        "initialization_engine_sha256": init["engine_sha256"],
        "initialization_self_test": init["self_test_marker"],
        "virtual_shards": 8192,
        "shards": [0, 1],
        "task_receipts": audit["task_receipt_count"],
        "complete_shards": audit["complete_shards"],
        "comparison": comparisons,
        "task_external_wall_sums": task_wall_sums,
        "validation_provenance": {
            "retained": arguments.run_dir is not None,
            "run_name": run_dir.name,
            "retained_relative_path": arguments.retained_relative_path,
            "config_sha256": config_sha256,
            "initialization_sha256": initialization_sha256,
            "artifact_set_sha256": audit["artifact_set_sha256"],
            "audit_evidence_sha256": audit_evidence_sha256,
        },
        "two_stream": {
            "external_wall_seconds": pair_wall,
            "combined_nodes": total_nodes,
            "nodes_per_second": nodes_per_second,
            "whole_run_eta_hours": eta_seconds / 3600,
            "sample_min_eta_hours": min(nodes) * 8192 / nodes_per_second / 3600,
            "sample_max_eta_hours": max(nodes) * 8192 / nodes_per_second / 3600,
            "speedup_vs_active_8_worker_cpu_eta": cpu_eta_seconds / eta_seconds,
        },
        "memory_evidence": {
            "source_receipt_sha256": sha256(ENGINE_CONCURRENCY_RECEIPT),
            "direct_child_max_resident_size_bytes": memory[
                "child_max_resident_set_size_bytes"
            ],
            "direct_child_swaps": memory["child_swaps"],
            "physical_memory_bytes": memory["physical_memory_bytes"],
            "measurement_scope": memory["measurement_scope"],
            "tested_stream_ceiling": 2,
            "untested_streams": "no safety or throughput claim",
        },
        "task_size_sample": {
            "sha256": sha256(SAMPLE),
            "shards": len(nodes),
            "mean_nodes": mean_nodes,
            "min_nodes": min(nodes),
            "max_nodes": max(nodes),
        },
    }
    if arguments.out:
        write_new(arguments.out.resolve(), payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
