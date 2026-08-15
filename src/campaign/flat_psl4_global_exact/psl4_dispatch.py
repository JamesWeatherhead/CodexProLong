#!/usr/bin/env python3
"""Crash-safe multi-process dispatcher for the exact PSL-4 task universe.

The C++ enumerator owns the mathematical search and append-only task journal.
This launcher adds deterministic virtual sharding, process-level parallelism,
resume validation, and per-shard receipts without changing search order inside
any task.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MASK64 = (1 << 64) - 1


def splitmix64(value: int) -> int:
    """Match SplitMix64 in psl4_popcount.cpp exactly."""

    value = (value + 0x9E3779B97F4A7C15) & MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
    return (value ^ (value >> 31)) & MASK64


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


@dataclass(frozen=True)
class JournalSummary:
    complete_indices: frozenset[int]
    truncated_indices: frozenset[int]
    answers: frozenset[str]
    complete_nodes: int
    complete_seconds: float


def parse_journal(path: Path) -> JournalSummary:
    """Read the final state of every task in an append-only solver journal."""

    final: dict[int, tuple[str, int, float, frozenset[str]]] = {}
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.rstrip("\n")
                fields = line.split("\t")
                if len(fields) != 11 or fields[0] != "TASK":
                    raise ValueError(f"malformed journal row {path}:{line_number}")
                task_index = int(fields[1])
                nodes = int(fields[2])
                seconds = float(fields[8])
                status = fields[10]
                if status not in {"COMPLETE", "TRUNCATED"}:
                    raise ValueError(
                        f"unknown journal status {status!r} at {path}:{line_number}"
                    )
                answers = (
                    frozenset()
                    if fields[9] in {"", "-"}
                    else frozenset(fields[9].split(","))
                )
                final[task_index] = (status, nodes, seconds, answers)

    complete = frozenset(
        task_index
        for task_index, (status, _, _, _) in final.items()
        if status == "COMPLETE"
    )
    truncated = frozenset(
        task_index
        for task_index, (status, _, _, _) in final.items()
        if status == "TRUNCATED"
    )
    answers = frozenset(
        answer
        for status, _, _, task_answers in final.values()
        if status == "COMPLETE"
        for answer in task_answers
    )
    return JournalSummary(
        complete_indices=complete,
        truncated_indices=truncated,
        answers=answers,
        complete_nodes=sum(
            nodes for status, nodes, _, _ in final.values() if status == "COMPLETE"
        ),
        complete_seconds=sum(
            seconds
            for status, _, seconds, _ in final.values()
            if status == "COMPLETE"
        ),
    )


def expected_shard_counts(expected_tasks: int, virtual_shards: int) -> list[int]:
    counts = [0] * virtual_shards
    for task_index in range(expected_tasks):
        counts[splitmix64(task_index) % virtual_shards] += 1
    return counts


def validate_shard(
    summary: JournalSummary,
    *,
    shard: int,
    virtual_shards: int,
    expected_tasks: int,
    expected_count: int,
) -> None:
    if summary.truncated_indices:
        raise ValueError(
            f"shard {shard} has {len(summary.truncated_indices)} final TRUNCATED rows"
        )
    if len(summary.complete_indices) != expected_count:
        raise ValueError(
            f"shard {shard} has {len(summary.complete_indices)} complete tasks; "
            f"expected {expected_count}"
        )
    for task_index in summary.complete_indices:
        if not 0 <= task_index < expected_tasks:
            raise ValueError(f"out-of-range task {task_index} in shard {shard}")
        assigned = splitmix64(task_index) % virtual_shards
        if assigned != shard:
            raise ValueError(
                f"task {task_index} belongs to shard {assigned}, not shard {shard}"
            )


def stable_config(args: argparse.Namespace, binary: Path, source: Path) -> dict[str, Any]:
    return {
        "version": 1,
        "expected_tasks": args.expected_tasks,
        "virtual_shards": args.virtual_shards,
        "solver": {
            "binary_sha256": sha256_file(binary),
            "source_sha256": sha256_file(source),
            "split_depth": args.split_depth,
            "strong_switch_depth": args.strong_switch_depth,
            "strong_exact_stride": args.strong_exact_stride,
        },
    }


def ensure_config(path: Path, config: dict[str, Any]) -> None:
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            existing = json.load(handle)
        if existing != config:
            raise ValueError(
                "run configuration differs from the frozen manifest; use a new run directory"
            )
        return
    atomic_write_json(path, config)


def shard_paths(run_dir: Path, shard: int) -> tuple[Path, Path, Path, Path]:
    directory = run_dir / "shards" / f"{shard:06d}"
    return (
        directory / "journal.tsv",
        directory / "stdout.log",
        directory / "stderr.log",
        directory / "receipt.json",
    )


async def run_shard(
    *,
    shard: int,
    args: argparse.Namespace,
    binary: Path,
    run_dir: Path,
    expected_count: int,
    solver_hash: str,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    journal, stdout_path, stderr_path, receipt_path = shard_paths(run_dir, shard)
    journal.parent.mkdir(parents=True, exist_ok=True)

    if receipt_path.exists():
        with receipt_path.open("r", encoding="utf-8") as handle:
            receipt = json.load(handle)
        if receipt.get("journal_sha256") != sha256_file(journal):
            raise ValueError(f"shard {shard} receipt/journal hash mismatch")
        summary = parse_journal(journal)
        validate_shard(
            summary,
            shard=shard,
            virtual_shards=args.virtual_shards,
            expected_tasks=args.expected_tasks,
            expected_count=expected_count,
        )
        return {**receipt, "shard": shard, "resume_status": "already_complete"}

    command = [
        str(binary),
        "--split-depth",
        str(args.split_depth),
        "--threads",
        "1",
        "--task-shards",
        str(args.virtual_shards),
        "--task-shard",
        str(shard),
        "--strong-switch-depth",
        str(args.strong_switch_depth),
        "--strong-exact-stride",
        str(args.strong_exact_stride),
        "--journal",
        str(journal),
    ]

    async with semaphore:
        started = time.monotonic()
        with stdout_path.open("ab") as stdout_handle, stderr_path.open(
            "ab"
        ) as stderr_handle:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=stdout_handle, stderr=stderr_handle
            )
            try:
                return_code = await process.wait()
            except asyncio.CancelledError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=10)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                raise
        elapsed = time.monotonic() - started

    if return_code != 0:
        raise RuntimeError(
            f"shard {shard} solver exited {return_code}; see {stderr_path}"
        )
    summary = parse_journal(journal)
    validate_shard(
        summary,
        shard=shard,
        virtual_shards=args.virtual_shards,
        expected_tasks=args.expected_tasks,
        expected_count=expected_count,
    )
    receipt = {
        "version": 1,
        "generated_at": utc_now(),
        "shard": shard,
        "virtual_shards": args.virtual_shards,
        "expected_task_count": expected_count,
        "complete_task_count": len(summary.complete_indices),
        "complete_nodes": summary.complete_nodes,
        "solver_reported_seconds": summary.complete_seconds,
        "dispatcher_wall_seconds": elapsed,
        "answer_count": len(summary.answers),
        "answers_sha256": hashlib.sha256(
            "\n".join(sorted(summary.answers)).encode("ascii")
        ).hexdigest(),
        "journal_sha256": sha256_file(journal),
        "solver_binary_sha256": solver_hash,
        "status": "complete",
    }
    atomic_write_json(receipt_path, receipt)
    return {"shard": shard, **receipt}


async def dispatch(args: argparse.Namespace) -> None:
    binary = Path(args.binary).expanduser().resolve()
    source = Path(args.source).expanduser().resolve()
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError(f"solver binary is missing or not executable: {binary}")
    if not source.is_file():
        raise ValueError(f"solver source is missing: {source}")
    if args.virtual_shards <= 0:
        raise ValueError("virtual shards must be positive")
    end_shard = args.end_shard
    if end_shard is None:
        end_shard = args.virtual_shards
    if not 0 <= args.start_shard <= end_shard <= args.virtual_shards:
        raise ValueError("invalid shard interval")
    if args.workers <= 0:
        raise ValueError("workers must be positive")

    run_dir.mkdir(parents=True, exist_ok=True)
    config = stable_config(args, binary, source)
    ensure_config(run_dir / "config.json", config)
    counts = expected_shard_counts(args.expected_tasks, args.virtual_shards)
    solver_hash = config["solver"]["binary_sha256"]
    semaphore = asyncio.Semaphore(args.workers)
    work = [
        asyncio.create_task(
            run_shard(
                shard=shard,
                args=args,
                binary=binary,
                run_dir=run_dir,
                expected_count=counts[shard],
                solver_hash=solver_hash,
                semaphore=semaphore,
            )
        )
        for shard in range(args.start_shard, end_shard)
    ]

    finished = 0
    try:
        for future in asyncio.as_completed(work):
            result = await future
            finished += 1
            print(
                json.dumps(
                    {
                        "event": "shard_complete",
                        "finished": finished,
                        "selected": len(work),
                        **result,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
    except BaseException:
        for task in work:
            task.cancel()
        await asyncio.gather(*work, return_exceptions=True)
        raise

    if args.start_shard == 0 and end_shard == args.virtual_shards:
        total = 0
        answer_union: set[str] = set()
        journal_hashes: list[str] = []
        for shard, expected_count in enumerate(counts):
            journal, _, _, receipt_path = shard_paths(run_dir, shard)
            if not receipt_path.exists():
                raise ValueError(f"missing completion receipt for shard {shard}")
            summary = parse_journal(journal)
            validate_shard(
                summary,
                shard=shard,
                virtual_shards=args.virtual_shards,
                expected_tasks=args.expected_tasks,
                expected_count=expected_count,
            )
            total += len(summary.complete_indices)
            answer_union.update(summary.answers)
            journal_hashes.append(sha256_file(journal))
        if total != args.expected_tasks:
            raise ValueError(f"global coverage is {total}; expected {args.expected_tasks}")
        final = {
            "version": 1,
            "generated_at": utc_now(),
            "status": "complete",
            "expected_tasks": args.expected_tasks,
            "complete_tasks": total,
            "virtual_shards": args.virtual_shards,
            "answer_count": len(answer_union),
            "answers": sorted(answer_union),
            "journal_hash_root": hashlib.sha256(
                "\n".join(journal_hashes).encode("ascii")
            ).hexdigest(),
            "config_sha256": sha256_file(run_dir / "config.json"),
        }
        atomic_write_json(run_dir / "COMPLETE.json", final)
        print(json.dumps({"event": "global_complete", **final}, sort_keys=True))


def self_test() -> None:
    assert splitmix64(0) == 0xE220A8397B1DCDAF
    assert splitmix64(1) == 0x910A2DEC89025CC1
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        journal = root / "journal.tsv"
        journal.write_text(
            "TASK\t1\t10\t0\t0\t0\t0\t0\t0.1\t-\tTRUNCATED\n"
            "TASK\t2\t20\t0\t0\t0\t0\t0\t0.2\tABC\tCOMPLETE\n"
            "TASK\t1\t30\t0\t0\t0\t0\t0\t0.3\tDEF\tCOMPLETE\n",
            encoding="utf-8",
        )
        summary = parse_journal(journal)
        assert summary.complete_indices == frozenset({1, 2})
        assert not summary.truncated_indices
        assert summary.answers == frozenset({"ABC", "DEF"})
        assert summary.complete_nodes == 50
        payload_path = root / "atomic.json"
        atomic_write_json(payload_path, {"ok": True})
        assert json.loads(payload_path.read_text(encoding="utf-8")) == {"ok": True}
        counts = expected_shard_counts(1000, 17)
        assert sum(counts) == 1000
    print("SELF_TEST_OK")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary")
    parser.add_argument("--source")
    parser.add_argument("--run-dir")
    parser.add_argument("--virtual-shards", type=int, default=4096)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--start-shard", type=int, default=0)
    parser.add_argument("--end-shard", type=int)
    parser.add_argument("--expected-tasks", type=int, default=730810)
    parser.add_argument("--split-depth", type=int, default=12)
    parser.add_argument("--strong-switch-depth", type=int, default=24)
    parser.add_argument("--strong-exact-stride", type=int, default=1)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test and not all((args.binary, args.source, args.run_dir)):
        parser.error("--binary, --source, and --run-dir are required")
    return args


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    asyncio.run(dispatch(args))


if __name__ == "__main__":
    main()
