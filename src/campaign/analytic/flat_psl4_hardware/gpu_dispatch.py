#!/usr/bin/env python3
"""Crash-resumable, isolated journaling for the exact Metal PSL-4 engine."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable


PACKET = Path(__file__).resolve().parent
SOURCE = PACKET / "psl4_metal_bfs.mm"
EXPECTED_TASKS = 730_810
EXPECTED_SPLITMIX_1 = 0x910A2DEC89025CC1
SELF_TEST_MARKER = "SELFTEST random_parents=1408 fixtures=3"
RUN_NAME = re.compile(
    r"^psl4-metal-run-[0-9]{8}T[0-9]{6}Z(?:-[a-z0-9][a-z0-9-]{0,31})?$"
)
COUNTER_FIELDS = (
    "nodes",
    "leaves",
    "central_rejects",
    "valid_leaves",
    "strong_cheap_prunes",
    "exact_checks",
    "exact_prunes",
)
BUILD_FLAGS = (
    "-std=c++20",
    "-O3",
    "-DNDEBUG",
    "-fobjc-arc",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-framework Foundation",
    "-framework Metal",
)
CONFIG_FIXED = {
    "schema": "psl4-metal-isolated-run-v2",
    "expected_tasks": EXPECTED_TASKS,
    "split_depth": 12,
    "strong_switch_depth": 24,
    "strong_exact_stride": 1,
    "build_flags": list(BUILD_FLAGS),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def ensure_directory(path: Path, mode: int = 0o700) -> None:
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    if not cursor.is_dir() or cursor.is_symlink():
        raise RuntimeError(f"unsafe directory ancestor: {cursor}")
    for directory in reversed(missing):
        try:
            os.mkdir(directory, mode)
            fsync_directory(directory.parent)
        except FileExistsError:
            pass
        if not directory.is_dir() or directory.is_symlink():
            raise RuntimeError(f"unsafe directory: {directory}")


def write_once(path: Path, data: bytes, mode: int = 0o444) -> None:
    ensure_directory(path.parent)
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
            raise RuntimeError(f"write-once collision at {path}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != data:
                raise RuntimeError(f"write-once collision at {path}")
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def splitmix64(value: int) -> int:
    mask = (1 << 64) - 1
    value = (value + 0x9E3779B97F4A7C15) & mask
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & mask
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & mask
    return value ^ (value >> 31)


def expected_indices(virtual_shards: int, shard: int) -> list[int]:
    if splitmix64(1) != EXPECTED_SPLITMIX_1:
        raise RuntimeError("Python SplitMix64 sentinel failed")
    return [
        index
        for index in range(EXPECTED_TASKS)
        if splitmix64(index) % virtual_shards == shard
    ]


def run_checked(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=timeout
    )


def _existing_ancestors(path: Path) -> list[Path]:
    result: list[Path] = []
    cursor = path
    while True:
        if cursor.exists() or cursor.is_symlink():
            result.append(cursor)
        if cursor == cursor.parent:
            break
        cursor = cursor.parent
    return result


def validate_run_root(raw: Path) -> Path:
    """Return a canonical, narrowly named run root or fail before any write."""
    lexical = Path(os.path.abspath(os.path.expanduser(str(raw))))
    existing_ancestors = _existing_ancestors(lexical)
    for ancestor in existing_ancestors:
        if ancestor.is_symlink():
            raise RuntimeError(f"run path contains a symlink ancestor: {ancestor}")
        metadata = ancestor.stat()
        if (
            metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            and not metadata.st_mode & stat.S_ISVTX
        ):
            raise RuntimeError(f"run path contains a writable unsafe ancestor: {ancestor}")
    resolved = lexical.resolve(strict=False)
    if not RUN_NAME.fullmatch(resolved.name):
        raise RuntimeError(
            "run root name must match psl4-metal-run-YYYYMMDDTHHMMSSZ[-label]"
        )
    packet = PACKET.resolve()
    if resolved == packet or packet in resolved.parents:
        raise RuntimeError("run root must not be the packet or one of its descendants")
    forbidden_parts = {"flat_psl4_global_exact", ".git", ".codex", "campaign"}
    if any(part in forbidden_parts for part in resolved.parts):
        raise RuntimeError("run root is inside canonical source/state")
    broad = {Path("/"), Path.home().resolve(), Path("/private/tmp"), Path("/tmp")}
    if resolved in broad or len(resolved.parts) < 3:
        raise RuntimeError("run root is too broad")
    parent = resolved.parent
    if not parent.is_dir() or parent.is_symlink():
        raise RuntimeError("run-root parent must be an existing real directory")
    parent_mode = parent.stat().st_mode
    if parent_mode & (stat.S_IWGRP | stat.S_IWOTH) and not parent_mode & stat.S_ISVTX:
        raise RuntimeError("run-root parent is writable by others without the sticky bit")
    if resolved.exists():
        metadata = resolved.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise RuntimeError("existing run root is not a caller-owned real directory")
    return resolved


def validate_config(config: dict[str, Any], *, virtual_shards: int | None = None) -> None:
    required_keys = set(CONFIG_FIXED) | {
        "created_at",
        "virtual_shards",
        "source_sha256",
        "packet_source_sha256",
        "binary_sha256",
    }
    if set(config) != required_keys:
        raise RuntimeError("run config field set mismatch")
    for key, expected in CONFIG_FIXED.items():
        if config.get(key) != expected:
            raise RuntimeError(f"run config pin mismatch: {key}")
    if (
        type(config.get("virtual_shards")) is not int
        or config["virtual_shards"] <= 0
        or (virtual_shards is not None and config["virtual_shards"] != virtual_shards)
    ):
        raise RuntimeError("virtual-shard count differs from run config")
    for key in ("source_sha256", "packet_source_sha256", "binary_sha256"):
        if not isinstance(config.get(key), str) or not re.fullmatch(
            r"[0-9a-f]{64}", config[key]
        ):
            raise RuntimeError(f"invalid config digest: {key}")
    if config["source_sha256"] != config["packet_source_sha256"]:
        raise RuntimeError("archived source is not pinned to the packet source")
    if not isinstance(config.get("created_at"), str):
        raise RuntimeError("invalid config timestamp")


def _replace_binary(temporary: Path, binary: Path) -> None:
    os.chmod(temporary, 0o555)
    descriptor = os.open(temporary, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, binary)
    fsync_directory(binary.parent)


def _remove_interrupted_setup_temps(directory: Path, pattern: re.Pattern[str]) -> None:
    removed = False
    for path in directory.iterdir():
        if not pattern.fullmatch(path.name):
            continue
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise RuntimeError(f"unsafe interrupted setup temporary: {path}")
        path.unlink()
        removed = True
    if removed:
        fsync_directory(directory)


def validate_engine_result(payload: dict[str, Any], task_index: int) -> dict[str, Any]:
    envelope_keys = {
        "schema", "device", "has_unified_memory", "thread_execution_width",
        "max_buffer_length", "compile_seconds", "task_generation_seconds",
        "selection_mode", "candidate_tasks", "selected_before_limit", "max_tasks",
        "truncated", "split_depth", "strong_switch_depth", "strong_exact_stride",
        "virtual_shards", "virtual_shard", "tasks", "aggregate", "answers",
    }
    if set(payload) != envelope_keys:
        raise RuntimeError("engine envelope field set mismatch")
    required = {
        "schema": "psl4-metal-bfs-batch-v1",
        "selection_mode": "task-index",
        "candidate_tasks": EXPECTED_TASKS,
        "selected_before_limit": 1,
        "max_tasks": 0,
        "truncated": False,
        "split_depth": 12,
        "strong_switch_depth": 24,
        "strong_exact_stride": 1,
        "virtual_shards": 0,
        "virtual_shard": 0,
    }
    differences = {
        key: {"expected": expected, "observed": payload.get(key)}
        for key, expected in required.items()
        if payload.get(key) != expected
    }
    tasks = payload.get("tasks")
    if differences or not isinstance(tasks, list) or len(tasks) != 1:
        raise RuntimeError(f"engine envelope mismatch: {differences}")
    if not isinstance(payload.get("device"), str) or not payload["device"]:
        raise RuntimeError("invalid Metal device")
    if type(payload.get("has_unified_memory")) is not bool:
        raise RuntimeError("invalid unified-memory field")
    for field in ("thread_execution_width", "max_buffer_length"):
        if type(payload.get(field)) is not int or payload[field] <= 0:
            raise RuntimeError(f"invalid engine field: {field}")
    for field in ("compile_seconds", "task_generation_seconds"):
        if not isinstance(payload.get(field), (int, float)) or not math.isfinite(
            payload[field]
        ) or payload[field] < 0:
            raise RuntimeError(f"invalid engine timing: {field}")
    task = tasks[0]
    task_keys = {
        "task_index", "nodes", "leaves", "central_rejects", "valid_leaves",
        "strong_cheap_prunes", "exact_checks", "exact_prunes", "peak_frontier",
        "metal_dispatches", "frontier_seconds", "metal_seconds", "total_seconds",
        "answers",
    }
    if set(task) != task_keys or task.get("task_index") != task_index:
        raise RuntimeError("engine task field/index mismatch")
    for field in COUNTER_FIELDS + ("peak_frontier", "metal_dispatches"):
        if type(task.get(field)) is not int or task[field] < 0:
            raise RuntimeError(f"invalid task counter: {field}")
    for field in ("frontier_seconds", "metal_seconds", "total_seconds"):
        if not isinstance(task.get(field), (int, float)) or not math.isfinite(
            task[field]
        ) or task[field] < 0:
            raise RuntimeError(f"invalid task timing: {field}")
    answers = task.get("answers")
    if not isinstance(answers, list) or answers != sorted(set(answers)) or any(
        not isinstance(answer, str)
        or len(answer) != 70
        or set(answer) - {"0", "1"}
        for answer in answers
    ):
        raise RuntimeError("invalid canonical answer list")
    if (
        task["central_rejects"] > task["leaves"]
        or task["valid_leaves"] > task["leaves"]
        or task["valid_leaves"] < len(answers)
    ):
        raise RuntimeError("invalid leaf/canonical-answer counts")
    aggregate = payload.get("aggregate")
    aggregate_keys = {
        "task_count", "nodes", "leaves", "central_rejects", "valid_leaves",
        "strong_cheap_prunes", "exact_checks", "exact_prunes", "peak_frontier",
        "metal_dispatches", "frontier_seconds", "metal_seconds",
        "total_seconds_excluding_compile", "total_seconds_including_compile",
        "peak_dispatch_children", "classes",
    }
    if not isinstance(aggregate, dict) or set(aggregate) != aggregate_keys:
        raise RuntimeError("engine aggregate field set mismatch")
    if aggregate.get("task_count") != 1:
        raise RuntimeError("engine aggregate task count mismatch")
    for field in COUNTER_FIELDS + ("peak_frontier", "metal_dispatches"):
        if aggregate.get(field) != task[field]:
            raise RuntimeError(f"engine aggregate mismatch: {field}")
    if aggregate.get("classes") != len(answers) or payload.get("answers") != answers:
        raise RuntimeError("engine answer aggregate mismatch")
    for field in (
        "frontier_seconds", "metal_seconds", "total_seconds_excluding_compile",
        "total_seconds_including_compile",
    ):
        if not isinstance(aggregate.get(field), (int, float)) or not math.isfinite(
            aggregate[field]
        ) or aggregate[field] < 0:
            raise RuntimeError(f"invalid aggregate timing: {field}")
    if type(aggregate.get("peak_dispatch_children")) is not int or aggregate[
        "peak_dispatch_children"
    ] < 0:
        raise RuntimeError("invalid peak dispatch count")
    return task


def _compile_under_lock(run_dir: Path, virtual_shards: int) -> tuple[Path, dict[str, Any]]:
    artifacts = run_dir / "artifacts"
    ensure_directory(artifacts)
    _remove_interrupted_setup_temps(
        run_dir, re.compile(r"\.(?:config\.json|initialization\.json)\.[0-9]+\.tmp")
    )
    _remove_interrupted_setup_temps(
        artifacts, re.compile(r"\.psl4_metal_bfs(?:\.mm)?\.[0-9]+\.tmp")
    )
    binary = artifacts / "psl4_metal_bfs"
    archived_source = artifacts / "psl4_metal_bfs.mm"
    config_path = run_dir / "config.json"
    packet_source_sha = sha256(SOURCE)
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        validate_config(config, virtual_shards=virtual_shards)
        if (
            config["packet_source_sha256"] != packet_source_sha
            or not archived_source.is_file()
            or archived_source.is_symlink()
            or sha256(archived_source) != config["source_sha256"]
            or not binary.is_file()
            or binary.is_symlink()
            or sha256(binary) != config["binary_sha256"]
        ):
            raise RuntimeError("initialized source/binary/config pin mismatch")
        return binary, config

    allowed = {".setup.lock", "artifacts"}
    extras = {path.name for path in run_dir.iterdir()} - allowed
    if extras:
        raise RuntimeError(f"unexpected pre-initialization entries: {sorted(extras)}")
    artifact_extras = {path.name for path in artifacts.iterdir()} - {
        "psl4_metal_bfs.mm", "psl4_metal_bfs"
    }
    if artifact_extras:
        raise RuntimeError(f"unexpected interrupted artifacts: {sorted(artifact_extras)}")
    write_once(archived_source, SOURCE.read_bytes(), 0o444)
    temporary = artifacts / f".psl4_metal_bfs.{os.getpid()}.tmp"
    command = [
        "clang++", "-std=c++20", "-O3", "-DNDEBUG", "-fobjc-arc", "-Wall",
        "-Wextra", "-Wpedantic", str(archived_source), "-framework", "Foundation",
        "-framework", "Metal", "-o", str(temporary),
    ]
    completed = run_checked(command, timeout=60)
    if completed.stderr.strip():
        raise RuntimeError(f"compiler emitted diagnostics:\n{completed.stderr}")
    _replace_binary(temporary, binary)
    config = {
        **CONFIG_FIXED,
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "virtual_shards": virtual_shards,
        "source_sha256": sha256(archived_source),
        "packet_source_sha256": packet_source_sha,
        "binary_sha256": sha256(binary),
    }
    validate_config(config, virtual_shards=virtual_shards)
    write_once(config_path, canonical_json(config), 0o444)
    return binary, config


def validate_initialization(
    receipt: dict[str, Any], config: dict[str, Any], config_sha256: str
) -> None:
    required_keys = {
        "schema", "created_at", "status", "config_sha256", "source_sha256",
        "binary_sha256", "self_test", "self_test_marker", "engine_sha256", "engine",
    }
    if set(receipt) != required_keys or any(
        (
            receipt.get("schema") != "psl4-metal-initialization-v1",
            receipt.get("status") != "complete",
            receipt.get("config_sha256") != config_sha256,
            receipt.get("source_sha256") != config["source_sha256"],
            receipt.get("binary_sha256") != config["binary_sha256"],
            receipt.get("self_test") is not True,
            receipt.get("self_test_marker") != SELF_TEST_MARKER,
        )
    ):
        raise RuntimeError("initialization receipt mismatch")
    if not isinstance(receipt.get("created_at"), str):
        raise RuntimeError("invalid initialization timestamp")
    engine = receipt.get("engine")
    if not isinstance(engine, dict):
        raise RuntimeError("missing initialization engine evidence")
    validate_engine_result(engine, 0)
    if receipt.get("engine_sha256") != hashlib.sha256(canonical_json(engine)).hexdigest():
        raise RuntimeError("initialization engine hash mismatch")


def initialize(run_dir: Path, virtual_shards: int) -> tuple[Path, dict[str, Any]]:
    ensure_directory(run_dir, 0o700)
    lock_path = run_dir / ".setup.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    with os.fdopen(descriptor, "a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        binary, config = _compile_under_lock(run_dir, virtual_shards)
        config_sha = sha256(run_dir / "config.json")
        init_path = run_dir / "initialization.json"
        if not init_path.exists():
            completed = run_checked(
                [str(binary), "--self-test", "--task-index", "0"], timeout=300
            )
            if SELF_TEST_MARKER not in completed.stderr:
                raise RuntimeError("required Metal self-test did not pass")
            engine = json.loads(completed.stdout)
            validate_engine_result(engine, 0)
            receipt = {
                "schema": "psl4-metal-initialization-v1",
                "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "status": "complete",
                "config_sha256": config_sha,
                "source_sha256": config["source_sha256"],
                "binary_sha256": config["binary_sha256"],
                "self_test": True,
                "self_test_marker": SELF_TEST_MARKER,
                "engine_sha256": hashlib.sha256(canonical_json(engine)).hexdigest(),
                "engine": engine,
            }
            write_once(init_path, canonical_json(receipt), 0o444)
        stored = json.loads(init_path.read_text(encoding="utf-8"))
        validate_initialization(stored, config, config_sha)
        ensure_directory(run_dir / "shards")
        config = dict(config)
        config["_config_sha256"] = config_sha
        return binary, config


def validate_task_receipt(
    receipt: dict[str, Any], *, task_index: int, shard: int, config: dict[str, Any]
) -> dict[str, Any]:
    required_keys = {
        "schema", "created_at", "task_index", "shard", "virtual_shards",
        "config_sha256", "source_sha256", "binary_sha256", "external_wall_seconds",
        "engine_stderr", "engine_sha256", "engine",
    }
    if set(receipt) != required_keys or any(
        (
            receipt.get("schema") != "psl4-metal-task-receipt-v2",
            receipt.get("task_index") != task_index,
            receipt.get("shard") != shard,
            receipt.get("virtual_shards") != config["virtual_shards"],
            splitmix64(task_index) % config["virtual_shards"] != shard,
            receipt.get("config_sha256") != config["_config_sha256"],
            receipt.get("source_sha256") != config["source_sha256"],
            receipt.get("binary_sha256") != config["binary_sha256"],
            receipt.get("engine_stderr") != "",
        )
    ):
        raise RuntimeError(f"task receipt mismatch for {task_index}")
    wall = receipt.get("external_wall_seconds")
    if not isinstance(wall, (int, float)) or not math.isfinite(wall) or wall <= 0:
        raise RuntimeError("invalid task external wall")
    engine = receipt.get("engine")
    if not isinstance(engine, dict) or receipt.get("engine_sha256") != hashlib.sha256(
        canonical_json(engine)
    ).hexdigest():
        raise RuntimeError("task engine hash mismatch")
    return validate_engine_result(engine, task_index)


def run_task(
    binary: Path,
    task_index: int,
    shard: int,
    config: dict[str, Any],
    task_path: Path,
) -> dict[str, Any]:
    if task_path.exists():
        receipt = json.loads(task_path.read_text(encoding="utf-8"))
        validate_task_receipt(receipt, task_index=task_index, shard=shard, config=config)
        return receipt
    started = time.perf_counter()
    completed = run_checked([str(binary), "--task-index", str(task_index)], timeout=300)
    external_wall = time.perf_counter() - started
    if completed.stderr.strip():
        raise RuntimeError(f"task {task_index} emitted stderr: {completed.stderr}")
    engine = json.loads(completed.stdout)
    validate_engine_result(engine, task_index)
    receipt = {
        "schema": "psl4-metal-task-receipt-v2",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "task_index": task_index,
        "shard": shard,
        "virtual_shards": config["virtual_shards"],
        "config_sha256": config["_config_sha256"],
        "source_sha256": config["source_sha256"],
        "binary_sha256": config["binary_sha256"],
        "external_wall_seconds": external_wall,
        "engine_stderr": "",
        "engine_sha256": hashlib.sha256(canonical_json(engine)).hexdigest(),
        "engine": engine,
    }
    write_once(task_path, canonical_json(receipt), 0o444)
    stored = json.loads(task_path.read_text(encoding="utf-8"))
    validate_task_receipt(stored, task_index=task_index, shard=shard, config=config)
    return stored


def task_line(receipt: dict[str, Any]) -> str:
    task = receipt["engine"]["tasks"][0]
    answers = ",".join(task["answers"]) if task["answers"] else "-"
    fields: Iterable[Any] = (
        "TASK", task["task_index"], task["nodes"], task["leaves"],
        task["central_rejects"], task["strong_cheap_prunes"], task["exact_checks"],
        task["exact_prunes"], receipt["external_wall_seconds"], answers, "COMPLETE",
    )
    return "\t".join(str(value) for value in fields)


def ordered_receipt_set_hash(indices: list[int], paths: list[Path]) -> str:
    rows = [f"{index:06d}\t{sha256(path)}" for index, path in zip(indices, paths)]
    return hashlib.sha256(("\n".join(rows) + ("\n" if rows else "")).encode()).hexdigest()


def finalize_shard(
    run_dir: Path,
    virtual_shards: int,
    shard: int,
    indices: list[int],
    receipts: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    if [receipt["task_index"] for receipt in receipts] != indices:
        raise RuntimeError("receipt order/task membership mismatch")
    shard_dir = run_dir / "shards" / f"{shard:06d}"
    task_paths = [shard_dir / "tasks" / f"{index:06d}.json" for index in indices]
    journal = ("\n".join(task_line(receipt) for receipt in receipts) + "\n").encode()
    journal_path = shard_dir / "journal.tsv"
    write_once(journal_path, journal, 0o444)
    totals = {
        field: sum(receipt["engine"]["tasks"][0][field] for receipt in receipts)
        for field in COUNTER_FIELDS
    }
    answers = sorted(
        {answer for receipt in receipts for answer in receipt["engine"]["tasks"][0]["answers"]}
    )
    indices_sha256 = hashlib.sha256(
        (",".join(str(index) for index in indices) + "\n").encode()
    ).hexdigest()
    answers_sha256 = hashlib.sha256(
        ("\n".join(answers) + ("\n" if answers else "")).encode()
    ).hexdigest()
    receipt = {
        "schema": "psl4-metal-shard-receipt-v2",
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "complete",
        "virtual_shards": virtual_shards,
        "shard": shard,
        "expected_task_count": len(indices),
        "complete_task_count": len(receipts),
        "task_indices_sha256": indices_sha256,
        "task_receipts_sha256": ordered_receipt_set_hash(indices, task_paths),
        "config_sha256": sha256(run_dir / "config.json"),
        "source_sha256": config["source_sha256"],
        "binary_sha256": config["binary_sha256"],
        "journal_sha256": sha256(journal_path),
        "totals": totals,
        "answer_count": len(answers),
        "answers_sha256": answers_sha256,
    }
    receipt_path = shard_dir / "receipt.json"
    if receipt_path.exists():
        stored = json.loads(receipt_path.read_text(encoding="utf-8"))
        comparison = dict(stored)
        comparison.pop("created_at", None)
        expected = dict(receipt)
        expected.pop("created_at", None)
        if comparison != expected:
            raise RuntimeError("stored shard receipt mismatch")
        return stored
    write_once(receipt_path, canonical_json(receipt), 0o444)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--virtual-shards", type=int, default=8192)
    parser.add_argument("--shard", type=int)
    parser.add_argument("--init-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()

    try:
        run_dir = validate_run_root(arguments.run_dir)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    if arguments.virtual_shards <= 0:
        raise SystemExit("invalid virtual-shard count")
    if arguments.init_only and arguments.shard is not None:
        raise SystemExit("--init-only and --shard are mutually exclusive")
    if not arguments.init_only and arguments.shard is None:
        raise SystemExit("--shard is required unless --init-only is used")
    if arguments.shard is not None and not 0 <= arguments.shard < arguments.virtual_shards:
        raise SystemExit("invalid virtual-shard selection")
    indices = [] if arguments.shard is None else expected_indices(
        arguments.virtual_shards, arguments.shard
    )
    if arguments.dry_run:
        print(json.dumps({
            "run_dir": str(run_dir),
            "virtual_shards": arguments.virtual_shards,
            "shard": arguments.shard,
            "task_count": len(indices),
            "task_indices": indices,
        }, sort_keys=True))
        return 0

    binary, config = initialize(run_dir, arguments.virtual_shards)
    if arguments.init_only:
        print((run_dir / "initialization.json").read_text(encoding="utf-8"), end="")
        return 0
    assert arguments.shard is not None
    shard_dir = run_dir / "shards" / f"{arguments.shard:06d}"
    ensure_directory(shard_dir / "tasks")
    lock_path = shard_dir / ".shard.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    with os.fdopen(descriptor, "a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        receipts = [
            run_task(
                binary, task_index, arguments.shard, config,
                shard_dir / "tasks" / f"{task_index:06d}.json",
            )
            for task_index in indices
        ]
        receipt = finalize_shard(
            run_dir, arguments.virtual_shards, arguments.shard, indices, receipts, config
        )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
