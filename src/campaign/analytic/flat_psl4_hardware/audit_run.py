#!/usr/bin/env python3
"""Independent, read-only consistency/completeness audit of a Metal PSL-4 run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from gpu_dispatch import (
    COUNTER_FIELDS,
    EXPECTED_TASKS,
    PACKET,
    SOURCE,
    canonical_json,
    expected_indices,
    ordered_receipt_set_hash,
    sha256,
    splitmix64,
    task_line,
    validate_config,
    validate_engine_result,
    validate_initialization,
)


HEX64 = re.compile(r"[0-9a-f]{64}")
SHARD_NAME = re.compile(r"[0-9]{6,}")
TASK_NAME = re.compile(r"[0-9]{6}\.json")


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"expected a regular file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return payload


def require_protected_file(path: Path, *, executable: bool = False) -> None:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise RuntimeError(f"unsafe file type/owner: {path}")
    if metadata.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        raise RuntimeError(f"durable evidence remains writable: {path}")
    if executable and not metadata.st_mode & stat.S_IXUSR:
        raise RuntimeError(f"binary is not executable: {path}")


def require_exact_entries(directory: Path, allowed: set[str]) -> None:
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError(f"expected a real directory: {directory}")
    observed = {entry.name for entry in directory.iterdir()}
    extras = observed - allowed
    if extras:
        raise RuntimeError(f"unexpected entries in {directory}: {sorted(extras)}")


def index_hash(indices: list[int]) -> str:
    return hashlib.sha256(
        (",".join(str(index) for index in indices) + "\n").encode()
    ).hexdigest()


def answer_hash(answers: list[str]) -> str:
    return hashlib.sha256(
        ("\n".join(answers) + ("\n" if answers else "")).encode()
    ).hexdigest()


def validate_task_receipt_independent(
    receipt: dict[str, Any],
    *,
    path: Path,
    task_index: int,
    shard: int,
    config: dict[str, Any],
    config_sha: str,
) -> dict[str, Any]:
    required_keys = {
        "schema", "created_at", "task_index", "shard", "virtual_shards",
        "config_sha256", "source_sha256", "binary_sha256", "external_wall_seconds",
        "engine_stderr", "engine_sha256", "engine",
    }
    if set(receipt) != required_keys:
        raise RuntimeError(f"task receipt field set mismatch: {path}")
    required = {
        "schema": "psl4-metal-task-receipt-v2",
        "task_index": task_index,
        "shard": shard,
        "virtual_shards": config["virtual_shards"],
        "config_sha256": config_sha,
        "source_sha256": config["source_sha256"],
        "binary_sha256": config["binary_sha256"],
        "engine_stderr": "",
    }
    differences = {
        key: {"expected": value, "observed": receipt.get(key)}
        for key, value in required.items()
        if receipt.get(key) != value
    }
    if differences or splitmix64(task_index) % config["virtual_shards"] != shard:
        raise RuntimeError(f"task receipt provenance mismatch: {path}: {differences}")
    if not isinstance(receipt.get("created_at"), str):
        raise RuntimeError(f"invalid task timestamp: {path}")
    wall = receipt.get("external_wall_seconds")
    if type(wall) not in (int, float) or not (0 < float(wall) < float("inf")):
        raise RuntimeError(f"invalid task wall time: {path}")
    engine = receipt.get("engine")
    if not isinstance(engine, dict) or receipt.get("engine_sha256") != hashlib.sha256(
        canonical_json(engine)
    ).hexdigest():
        raise RuntimeError(f"task engine digest mismatch: {path}")
    validate_engine_result(engine, task_index)
    require_protected_file(path)
    return receipt


def validate_shard_receipt(
    receipt: dict[str, Any],
    *,
    path: Path,
    shard: int,
    indices: list[int],
    task_paths: list[Path],
    task_receipts: list[dict[str, Any]],
    journal_path: Path,
    config: dict[str, Any],
    config_sha: str,
) -> None:
    expected_journal = (
        "\n".join(task_line(receipt) for receipt in task_receipts) + "\n"
    ).encode()
    if journal_path.is_symlink() or journal_path.read_bytes() != expected_journal:
        raise RuntimeError(f"journal records do not reconstruct: {journal_path}")
    require_protected_file(journal_path)
    totals = {
        field: sum(item["engine"]["tasks"][0][field] for item in task_receipts)
        for field in COUNTER_FIELDS
    }
    answers = sorted(
        {
            answer
            for item in task_receipts
            for answer in item["engine"]["tasks"][0]["answers"]
        }
    )
    expected = {
        "schema": "psl4-metal-shard-receipt-v2",
        "status": "complete",
        "virtual_shards": config["virtual_shards"],
        "shard": shard,
        "expected_task_count": len(indices),
        "complete_task_count": len(indices),
        "task_indices_sha256": index_hash(indices),
        "task_receipts_sha256": ordered_receipt_set_hash(indices, task_paths),
        "config_sha256": config_sha,
        "source_sha256": config["source_sha256"],
        "binary_sha256": config["binary_sha256"],
        "journal_sha256": hashlib.sha256(expected_journal).hexdigest(),
        "totals": totals,
        "answer_count": len(answers),
        "answers_sha256": answer_hash(answers),
    }
    if set(receipt) != set(expected) | {"created_at"}:
        raise RuntimeError(f"shard receipt field set mismatch: {path}")
    differences = {
        key: {"expected": value, "observed": receipt.get(key)}
        for key, value in expected.items()
        if receipt.get(key) != value
    }
    if differences or not isinstance(receipt.get("created_at"), str):
        raise RuntimeError(f"shard receipt reconstruction mismatch: {path}: {differences}")
    require_protected_file(path)


def audit(run_dir: Path) -> dict[str, Any]:
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise RuntimeError("run directory must be a real directory")
    require_exact_entries(
        run_dir,
        {".setup.lock", "artifacts", "config.json", "initialization.json", "shards"},
    )
    artifacts = run_dir / "artifacts"
    require_exact_entries(artifacts, {"psl4_metal_bfs", "psl4_metal_bfs.mm"})
    config_path = run_dir / "config.json"
    config = load_json(config_path)
    validate_config(config)
    config_sha = sha256(config_path)
    require_protected_file(config_path)

    binary = artifacts / "psl4_metal_bfs"
    archived_source = artifacts / "psl4_metal_bfs.mm"
    require_protected_file(binary, executable=True)
    require_protected_file(archived_source)
    packet_source_sha = sha256(SOURCE)
    if (
        sha256(binary) != config["binary_sha256"]
        or sha256(archived_source) != config["source_sha256"]
        or packet_source_sha != config["packet_source_sha256"]
        or config["source_sha256"] != packet_source_sha
    ):
        raise RuntimeError("frozen source/binary/config pin mismatch")

    init_path = run_dir / "initialization.json"
    initialization = load_json(init_path)
    validate_initialization(initialization, config, config_sha)
    require_protected_file(init_path)

    virtual_shards = config["virtual_shards"]
    expected_nonempty_shards = len(
        {splitmix64(index) % virtual_shards for index in range(EXPECTED_TASKS)}
    )
    observed: set[int] = set()
    duplicate_indices: list[int] = []
    misplaced_indices: list[int] = []
    task_receipt_count = 0
    complete_shards = 0
    task_receipt_hashes: list[str] = []
    shard_receipt_hashes: list[str] = []
    shards_root = run_dir / "shards"
    require_exact_entries(
        shards_root,
        {entry.name for entry in shards_root.iterdir() if SHARD_NAME.fullmatch(entry.name)},
    )
    shard_dirs = sorted(shards_root.iterdir())
    for shard_dir in shard_dirs:
        if shard_dir.is_symlink() or not shard_dir.is_dir() or not SHARD_NAME.fullmatch(
            shard_dir.name
        ):
            raise RuntimeError(f"invalid shard directory: {shard_dir}")
        shard = int(shard_dir.name)
        if not 0 <= shard < virtual_shards or shard_dir.name != f"{shard:06d}":
            raise RuntimeError(f"out-of-range/noncanonical shard directory: {shard_dir}")
        require_exact_entries(shard_dir, {".shard.lock", "tasks", "journal.tsv", "receipt.json"})
        task_dir = shard_dir / "tasks"
        task_entries = sorted(task_dir.iterdir())
        task_receipts: list[dict[str, Any]] = []
        task_paths: list[Path] = []
        shard_indices: list[int] = []
        for task_path in task_entries:
            if (
                task_path.is_symlink()
                or not task_path.is_file()
                or not TASK_NAME.fullmatch(task_path.name)
            ):
                raise RuntimeError(f"invalid task receipt filename/type: {task_path}")
            index = int(task_path.stem)
            if not 0 <= index < EXPECTED_TASKS or task_path.name != f"{index:06d}.json":
                raise RuntimeError(f"invalid/noncanonical task index filename: {task_path}")
            receipt = validate_task_receipt_independent(
                load_json(task_path),
                path=task_path,
                task_index=index,
                shard=shard,
                config=config,
                config_sha=config_sha,
            )
            if receipt["task_index"] != index:
                raise RuntimeError(f"task index/filename mismatch: {task_path}")
            if splitmix64(index) % virtual_shards != shard:
                misplaced_indices.append(index)
            if index in observed:
                duplicate_indices.append(index)
            observed.add(index)
            shard_indices.append(index)
            task_paths.append(task_path)
            task_receipts.append(receipt)
            task_receipt_count += 1
            task_receipt_hashes.append(sha256(task_path))

        shard_receipt_path = shard_dir / "receipt.json"
        journal_path = shard_dir / "journal.tsv"
        if shard_receipt_path.exists():
            if not journal_path.exists():
                raise RuntimeError(f"complete shard lacks journal: {shard_dir}")
            expected = expected_indices(virtual_shards, shard)
            if shard_indices != expected:
                raise RuntimeError(f"complete shard {shard} has a task-set mismatch")
            validate_shard_receipt(
                load_json(shard_receipt_path),
                path=shard_receipt_path,
                shard=shard,
                indices=expected,
                task_paths=task_paths,
                task_receipts=task_receipts,
                journal_path=journal_path,
                config=config,
                config_sha=config_sha,
            )
            complete_shards += 1
            shard_receipt_hashes.append(sha256(shard_receipt_path))
        elif journal_path.exists():
            raise RuntimeError(f"incomplete shard has a finalized journal: {shard_dir}")

    missing_count = EXPECTED_TASKS - len(observed)
    complete = (
        missing_count == 0
        and task_receipt_count == EXPECTED_TASKS
        and not duplicate_indices
        and not misplaced_indices
        and complete_shards == expected_nonempty_shards
    )
    digest_payload = {
        "config_sha256": config_sha,
        "initialization_sha256": sha256(init_path),
        "task_receipt_hashes": sorted(task_receipt_hashes),
        "shard_receipt_hashes": sorted(shard_receipt_hashes),
    }
    return {
        "schema": "psl4-metal-run-audit-v2",
        "status": "complete" if complete else "incomplete",
        "expected_tasks": EXPECTED_TASKS,
        "task_receipt_count": task_receipt_count,
        "unique_task_count": len(observed),
        "missing_task_count": missing_count,
        "duplicate_task_count": len(duplicate_indices),
        "misplaced_task_count": len(misplaced_indices),
        "expected_shards": virtual_shards,
        "expected_nonempty_shards": expected_nonempty_shards,
        "complete_shards": complete_shards,
        "exactly_once": complete,
        "initialization_self_test": "verified",
        "artifact_set_sha256": hashlib.sha256(canonical_json(digest_payload)).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    arguments = parser.parse_args()
    result = audit(arguments.run_dir.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "complete" and not arguments.allow_incomplete:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
