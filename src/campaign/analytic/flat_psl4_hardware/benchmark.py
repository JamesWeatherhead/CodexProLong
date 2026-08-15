#!/usr/bin/env python3
"""Compile, differentially replay, and benchmark the clean-room Metal engine."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import platform
import resource
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "psl4_metal_bfs.mm"
SHARD0_FIXTURE = ROOT / "fixtures" / "shard0_reference.tsv"
JOURNAL_COUNTER_FIELDS = (
    "nodes",
    "leaves",
    "central_rejects",
    "strong_cheap_prunes",
    "exact_checks",
    "exact_prunes",
)
COUNTER_FIELDS = (*JOURNAL_COUNTER_FIELDS, "valid_leaves")
HARD_TASK_INDEX = 351_916
HARD_TASK_EXPECTED: dict[str, Any] = {
    "task_index": HARD_TASK_INDEX,
    "nodes": 82_824_482,
    "leaves": 101,
    "central_rejects": 100,
    "valid_leaves": 1,
    "strong_cheap_prunes": 66_160_332,
    "exact_checks": 182_221_485,
    "exact_prunes": 100_048_090,
    "answers": [
        "0000011100001011111111110101001010111100110011001101010110010110010110"
    ],
}
FROZEN_PINS = {
    "base_cpp_sha256": "a9c7dfd13aeb06302d192215a49888552925f76b3a96e33b2450d16661363b42",
    "dispatcher_sha256": "59c659a4f582f87cf3f5f08fbe636973299ec738c1bcf2d0a4ee124dc43f2df2",
    "active_lag_patch_sha256": "2ad9e2387e92c5b8ef8217e5d616a4ff41bc6da960ce821c22d4c4563992b51b",
    "active_builder_sha256": "bb767120eba083324a4e033a6c8001d9e5e5c5680b67bb951cb881423fe50e22",
    "active_reference_sha256": "431ae5ed5c8800a0639cbd3cc7d298afc50d58b9b23e18a10634efd290f4c3ee",
    "canonical_shard0_journal_sha256": "36e09b797b978764074adc78f54b29272c6cde79d017292aca69b3abd6754a9d",
}
CPU_REFERENCE_SECONDS = {
    "hard_task_active_cpp": 53.2857,
    "shard0_solver": 2415.090370883,
    "shard0_dispatcher_wall": 2415.4550474579446,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_checked(command: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def compile_engine(binary: Path) -> dict[str, Any]:
    command = [
        "clang++",
        "-std=c++20",
        "-O3",
        "-DNDEBUG",
        "-fobjc-arc",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        str(SOURCE),
        "-framework",
        "Foundation",
        "-framework",
        "Metal",
        "-o",
        str(binary),
    ]
    completed = run_checked(command, timeout=60)
    if completed.stderr.strip():
        raise RuntimeError(f"compiler emitted diagnostics:\n{completed.stderr}")
    version = run_checked(["clang++", "--version"], timeout=15).stdout.splitlines()[0]
    return {
        "command": [
            "clang++",
            "-std=c++20",
            "-O3",
            "-DNDEBUG",
            "-fobjc-arc",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "psl4_metal_bfs.mm",
            "-framework",
            "Foundation",
            "-framework",
            "Metal",
            "-o",
            "<temporary-binary>",
        ],
        "compiler": version,
        "binary_sha256": sha256(binary),
    }


def run_engine(
    binary: Path, arguments: list[str], timeout: int = 180
) -> tuple[dict[str, Any], str, float]:
    started = time.perf_counter()
    completed = run_checked([str(binary), *arguments], timeout=timeout)
    elapsed = time.perf_counter() - started
    return json.loads(completed.stdout), completed.stderr.strip(), elapsed


def assert_task(observed: dict[str, Any], expected: dict[str, Any]) -> None:
    fields = ("task_index", *COUNTER_FIELDS, "answers")
    differences = {
        field: {"expected": expected[field], "observed": observed.get(field)}
        for field in fields
        if observed.get(field) != expected[field]
    }
    if differences:
        raise AssertionError(f"task mismatch: {json.dumps(differences, sort_keys=True)}")


def load_shard_fixture() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with SHARD0_FIXTURE.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            record: dict[str, Any] = {
                field: int(row[field])
                for field in ("task_index", *JOURNAL_COUNTER_FIELDS)
            }
            record["answers"] = [] if row["answer"] == "-" else row["answer"].split(",")
            record["valid_leaves"] = len(record["answers"])
            records.append(record)
    return records


def compare_shard(observed: dict[str, Any]) -> dict[str, Any]:
    expected = load_shard_fixture()
    observed_tasks = observed["tasks"]
    if len(observed_tasks) != len(expected):
        raise AssertionError(
            f"task count mismatch: expected {len(expected)}, observed {len(observed_tasks)}"
        )
    for observed_task, expected_task in zip(observed_tasks, expected):
        assert_task(observed_task, expected_task)

    expected_totals = {
        field: sum(record[field] for record in expected) for field in COUNTER_FIELDS
    }
    aggregate = observed["aggregate"]
    for field, value in expected_totals.items():
        if aggregate.get(field) != value:
            raise AssertionError(
                f"aggregate {field} mismatch: expected {value}, observed {aggregate.get(field)}"
            )
    if aggregate.get("task_count") != len(expected) or observed.get("answers") != []:
        raise AssertionError("aggregate task count or shard answer set mismatch")
    return {
        "reference_task_count": len(expected),
        "counter_mismatches": 0,
        "expected_totals": expected_totals,
        "reference_sha256": sha256(SHARD0_FIXTURE),
    }


def machine_metadata() -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }
    try:
        metadata["cpu"] = run_checked(
            ["sysctl", "-n", "machdep.cpu.brand_string"], timeout=10
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        metadata["cpu"] = "unavailable"
    for key, command in (
        ("macos_product_version", ["sw_vers", "-productVersion"]),
        ("sdk_version", ["xcrun", "--show-sdk-version"]),
        ("physical_memory_bytes", ["sysctl", "-n", "hw.memsize"]),
    ):
        try:
            value = run_checked(command, timeout=10).stdout.strip()
            metadata[key] = int(value) if key == "physical_memory_bytes" else value
        except (OSError, ValueError, subprocess.SubprocessError):
            metadata[key] = "unavailable"
    return metadata


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"append-only output already exists: {path}")
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
    parser.add_argument("--full", action="store_true", help="replay all 84 shard-0 tasks")
    parser.add_argument("--out", type=Path, help="append-only JSON receipt path")
    arguments = parser.parse_args()

    if platform.system() != "Darwin":
        raise SystemExit("this benchmark requires macOS and Metal")
    with tempfile.TemporaryDirectory(prefix="psl4-metal-bfs-") as directory:
        binary = Path(directory) / "psl4_metal_bfs"
        build = compile_engine(binary)
        hard, self_test_stderr, hard_external_wall = run_engine(
            binary, ["--self-test", "--task-index", str(HARD_TASK_INDEX)]
        )
        if len(hard["tasks"]) != 1:
            raise AssertionError("hard-task replay returned the wrong task count")
        assert_task(hard["tasks"][0], HARD_TASK_EXPECTED)

        result: dict[str, Any] = {
            "schema": "psl4-metal-hardware-benchmark-v1",
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "status": "pass",
            "mode": "full" if arguments.full else "quick",
            "source_sha256": sha256(SOURCE),
            "source_bytes": SOURCE.stat().st_size,
            "fixture_sha256": sha256(SHARD0_FIXTURE),
            "build": build,
            "machine": machine_metadata(),
            "frozen_pins": FROZEN_PINS,
            "self_test": {
                "status": "pass",
                "stderr": self_test_stderr,
                "random_parent_depth_cases": 1408,
                "public_psl4_fixtures": 3,
            },
            "hard_task": hard,
            "hard_task_external_wall_seconds": hard_external_wall,
            "cpu_reference_seconds": CPU_REFERENCE_SECONDS,
            "hard_task_pipeline_speedup_including_runtime_compile": (
                CPU_REFERENCE_SECONDS["hard_task_active_cpp"]
                / hard["aggregate"]["total_seconds_including_compile"]
            ),
            "hard_task_speedup_vs_cpu_external_wall": (
                CPU_REFERENCE_SECONDS["hard_task_active_cpp"] / hard_external_wall
            ),
        }
        if arguments.full:
            shard, shard_stderr, shard_external_wall = run_engine(
                binary,
                ["--task-shards", "8192", "--task-shard", "0"],
                timeout=300,
            )
            comparison = compare_shard(shard)
            result["shard0"] = shard
            result["shard0_external_wall_seconds"] = shard_external_wall
            result["shard0_comparison"] = comparison
            result["shard0_stderr"] = shard_stderr
            result["shard0_pipeline_speedup_vs_cpu_solver"] = (
                CPU_REFERENCE_SECONDS["shard0_solver"]
                / shard["aggregate"]["total_seconds_including_compile"]
            )
            result["shard0_speedup_vs_cpu_solver_external_wall"] = (
                CPU_REFERENCE_SECONDS["shard0_solver"] / shard_external_wall
            )
            result["shard0_speedup_vs_dispatcher_wall"] = (
                CPU_REFERENCE_SECONDS["shard0_dispatcher_wall"]
                / shard_external_wall
            )

        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        result["child_resource_usage"] = {
            "max_resident_set_size_bytes": usage.ru_maxrss,
            "major_page_faults": usage.ru_majflt,
            "swaps": usage.ru_nswap,
            "user_seconds": usage.ru_utime,
            "system_seconds": usage.ru_stime,
        }

    if arguments.out:
        write_new_json(arguments.out.resolve(), result)
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
