#!/usr/bin/env python3
"""Exact two-stream throughput study for the Metal PSL-4 engine."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import resource
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import benchmark


ROOT = Path(__file__).resolve().parent
RECEIPT = ROOT / "runs" / "20260815T093000Z" / "receipt.json"
FIXTURES = {
    0: ROOT / "fixtures" / "shard0_reference.tsv",
    1: ROOT / "fixtures" / "shard1_reference.tsv",
}
SAMPLE = ROOT / "fixtures" / "completed_shard_sample.tsv"
JOURNAL_FIELDS = (
    "nodes",
    "leaves",
    "central_rejects",
    "strong_cheap_prunes",
    "exact_checks",
    "exact_prunes",
)


def load_reference(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            answers = [] if row["answer"] == "-" else row["answer"].split(",")
            record = {
                field: int(row[field]) for field in ("task_index", *JOURNAL_FIELDS)
            }
            record["valid_leaves"] = len(answers)
            record["answers"] = answers
            records.append(record)
    return records


def compare(shard: int, observed: dict[str, Any]) -> dict[str, Any]:
    expected = load_reference(FIXTURES[shard])
    tasks = observed.get("tasks", [])
    if len(tasks) != len(expected):
        raise AssertionError(f"shard {shard} task-count mismatch")
    fields = ("task_index", *JOURNAL_FIELDS, "valid_leaves", "answers")
    mismatches = []
    for wanted, got in zip(expected, tasks):
        differences = {
            field: {"expected": wanted[field], "observed": got.get(field)}
            for field in fields
            if wanted[field] != got.get(field)
        }
        if differences:
            mismatches.append({"task_index": wanted["task_index"], "fields": differences})
    if mismatches:
        raise AssertionError(f"shard {shard} mismatches: {mismatches[:3]}")
    expected_totals = {
        field: sum(record[field] for record in expected)
        for field in (*JOURNAL_FIELDS, "valid_leaves")
    }
    for field, value in expected_totals.items():
        if observed["aggregate"].get(field) != value:
            raise AssertionError(f"shard {shard} aggregate mismatch: {field}")
    return {
        "task_count": len(expected),
        "counter_mismatches": 0,
        "reference_sha256": benchmark.sha256(FIXTURES[shard]),
        "totals": expected_totals,
    }


def run_pair(binary: Path) -> tuple[dict[int, dict[str, Any]], float]:
    processes: dict[int, subprocess.Popen[str]] = {}
    started = time.perf_counter()
    for shard in (0, 1):
        processes[shard] = subprocess.Popen(
            [str(binary), "--task-shards", "8192", "--task-shard", str(shard)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    outputs: dict[int, dict[str, Any]] = {}
    try:
        for shard, process in processes.items():
            stdout, stderr = process.communicate(timeout=180)
            if process.returncode != 0:
                raise RuntimeError(f"concurrent shard {shard} failed: {stderr}")
            if stderr.strip():
                raise RuntimeError(f"concurrent shard {shard} emitted stderr: {stderr}")
            outputs[shard] = json.loads(stdout)
    except BaseException:
        for process in processes.values():
            if process.poll() is None:
                process.kill()
        raise
    return outputs, time.perf_counter() - started


def load_sample() -> list[dict[str, Any]]:
    rows = []
    with SAMPLE.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            rows.append(
                {
                    "shard": int(row["shard"]),
                    "tasks": int(row["tasks"]),
                    "nodes": int(row["nodes"]),
                    "solver_seconds": float(row["solver_seconds"]),
                    "fresh_from_empty": bool(int(row["fresh_from_empty"])),
                }
            )
    return rows


def write_new(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"append-only output exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    arguments = parser.parse_args()
    frozen = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if frozen["source_sha256"] != benchmark.sha256(ROOT / "psl4_metal_bfs.mm"):
        raise RuntimeError("frozen shard-0 receipt uses a different source")
    compare(0, frozen["shard0"])

    with tempfile.TemporaryDirectory(prefix="psl4-metal-concurrency-") as directory:
        binary = Path(directory) / "psl4_metal_bfs"
        build = benchmark.compile_engine(binary)
        shard1, shard1_stderr, shard1_wall = benchmark.run_engine(
            binary, ["--task-shards", "8192", "--task-shard", "1"], timeout=180
        )
        if shard1_stderr:
            raise RuntimeError(f"single-stream shard 1 emitted stderr: {shard1_stderr}")
        shard1_comparison = compare(1, shard1)
        pair, pair_wall = run_pair(binary)
        pair_comparison = {str(shard): compare(shard, result) for shard, result in pair.items()}

    sample = load_sample()
    nodes = [row["nodes"] for row in sample]
    fresh_seconds = [row["solver_seconds"] for row in sample if row["fresh_from_empty"]]
    total_pair_nodes = sum(pair[shard]["aggregate"]["nodes"] for shard in (0, 1))
    pair_nodes_per_second = total_pair_nodes / pair_wall
    shard0_wall = frozen["shard0_external_wall_seconds"]
    single_nodes = (
        frozen["shard0"]["aggregate"]["nodes"] + shard1["aggregate"]["nodes"]
    )
    single_wall = shard0_wall + shard1_wall
    single_nodes_per_second = single_nodes / single_wall
    mean_nodes = statistics.fmean(nodes)
    cpu_seconds_per_shard = statistics.fmean(fresh_seconds)
    cpu_eta_seconds = cpu_seconds_per_shard * 8192 / 8
    pair_eta_seconds = mean_nodes * 8192 / pair_nodes_per_second
    single_eta_seconds = mean_nodes * 8192 / single_nodes_per_second
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    payload = {
        "schema": "psl4-metal-concurrency-benchmark-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "pass",
        "source_sha256": frozen["source_sha256"],
        "binary_sha256": build["binary_sha256"],
        "shard0_frozen_receipt_sha256": benchmark.sha256(RECEIPT),
        "single_stream": {
            "shard0_external_wall_seconds": shard0_wall,
            "shard1_external_wall_seconds": shard1_wall,
            "combined_nodes": single_nodes,
            "nodes_per_second": single_nodes_per_second,
            "whole_run_eta_hours": single_eta_seconds / 3600,
            "shard1_aggregate": shard1["aggregate"],
            "shard1_comparison": shard1_comparison,
        },
        "two_stream": {
            "external_wall_seconds": pair_wall,
            "combined_nodes": total_pair_nodes,
            "nodes_per_second": pair_nodes_per_second,
            "throughput_gain_vs_single": pair_nodes_per_second / single_nodes_per_second,
            "whole_run_eta_hours": pair_eta_seconds / 3600,
            "comparison": pair_comparison,
            "aggregates": {
                str(shard): pair[shard]["aggregate"] for shard in (0, 1)
            },
        },
        "task_size_skew": {
            "sample_sha256": benchmark.sha256(SAMPLE),
            "sample_shards": len(sample),
            "mean_nodes": mean_nodes,
            "min_nodes": min(nodes),
            "max_nodes": max(nodes),
            "population_stdev_nodes": statistics.pstdev(nodes),
            "coefficient_of_variation": statistics.pstdev(nodes) / mean_nodes,
            "two_stream_eta_min_sample_hours": min(nodes) * 8192 / pair_nodes_per_second / 3600,
            "two_stream_eta_max_sample_hours": max(nodes) * 8192 / pair_nodes_per_second / 3600,
        },
        "active_cpu_8_worker_reference": {
            "fresh_shards": len(fresh_seconds),
            "mean_solver_seconds_per_shard": cpu_seconds_per_shard,
            "whole_run_eta_days": cpu_eta_seconds / 86400,
            "two_stream_speedup_vs_8_worker_eta": cpu_eta_seconds / pair_eta_seconds,
        },
        "resource_stability": {
            "two_concurrent_processes_completed": True,
            "child_max_resident_set_size_bytes": usage.ru_maxrss,
            "child_major_page_faults": usage.ru_majflt,
            "child_swaps": usage.ru_nswap,
            "physical_memory_bytes": frozen["machine"]["physical_memory_bytes"],
            "recommended_streams": 2,
            "three_or_four_streams_tested": False,
            "reason_not_tested": (
                "two is the largest concurrency level directly tested; this "
                "receipt makes no memory-safety claim for untested levels"
            ),
            "measurement_scope": (
                "ru_maxrss is the maximum resident size of a directly launched "
                "bare-engine child, not aggregate concurrent GPU allocation"
            ),
        },
    }
    if arguments.out:
        write_new(arguments.out.resolve(), payload)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
