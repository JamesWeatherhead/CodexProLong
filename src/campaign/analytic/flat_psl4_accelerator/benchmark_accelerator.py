#!/usr/bin/env python3
"""Append-only paired benchmark for the frozen and accelerated PSL-4 engines."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import build_accelerator


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUNS = HERE / "runs"
FIXED_BITS = (
    "1001011001011001010100110011001100001010110101000000000010111100011111"
)
CANONICAL_ANSWER = (
    "0000011100001011111111110101001010111100110011001101010110010110010110"
)
COUNTER_KEYS = (
    "nodes",
    "leaves",
    "strong_cheap_prunes",
    "exact_checks",
    "exact_prunes",
    "classes",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_output(command: list[str]) -> str:
    return subprocess.run(
        command, check=True, capture_output=True, text=True
    ).stdout.strip()


def parse_done(stderr: str) -> dict[str, Any]:
    rows = [line for line in stderr.splitlines() if line.startswith("DONE ")]
    if len(rows) != 1:
        raise RuntimeError(f"expected one DONE row, found {len(rows)}")
    parsed: dict[str, Any] = {}
    for key, value in re.findall(r"([a-z_]+)=([^ ]+)", rows[0]):
        if key == "seconds":
            parsed[key] = float(value)
        else:
            parsed[key] = int(value)
    return parsed


def run_solver(binary: Path, node_limit: int, label: str) -> dict[str, Any]:
    command = [
        str(binary),
        "--split-depth",
        "12",
        "--threads",
        "1",
        "--max-tasks",
        "1",
        "--near-bits",
        FIXED_BITS,
        "--strong-switch-depth",
        "24",
        "--strong-exact-stride",
        "1",
    ]
    if node_limit:
        command.extend(["--node-limit", str(node_limit)])
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return {
        "command": [f"<{label}-binary>", *command[1:]],
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "done": parse_done(completed.stderr),
    }


def assert_equivalent(base: dict[str, Any], accelerated: dict[str, Any]) -> None:
    for key in COUNTER_KEYS:
        left = base["done"][key]
        right = accelerated["done"][key]
        if left != right:
            raise RuntimeError(f"counter mismatch for {key}: {left} != {right}")
    if base["stdout"] != accelerated["stdout"]:
        raise RuntimeError("canonical answer output differs")


def atomic_json(path: Path, value: Any) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capped-repetitions", type=int, default=3)
    parser.add_argument("--node-limit", type=int, default=5_000_000)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.capped_repetitions < 1 or args.node_limit < 1:
        raise ValueError("capped repetitions and node limit must be positive")

    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = args.run_id or timestamp
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    with tempfile.TemporaryDirectory(prefix="psl4-benchmark-") as name:
        temporary = Path(name)
        accelerated_source = temporary / "psl4_accelerated.cpp"
        base_binary = temporary / "psl4_base"
        accelerated_binary = temporary / "psl4_accelerated"
        subprocess.run(
            [
                "python3",
                str(HERE / "build_accelerator.py"),
                "--output",
                str(accelerated_source),
            ],
            check=True,
        )
        compiler = [
            "clang++",
            "-std=c++20",
            "-O3",
            "-DNDEBUG",
            "-march=native",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
        ]
        subprocess.run(
            compiler + [str(build_accelerator.BASE), "-o", str(base_binary)],
            check=True,
        )
        subprocess.run(
            compiler + [str(accelerated_source), "-o", str(accelerated_binary)],
            check=True,
        )
        base_self_test = subprocess.run(
            [str(base_binary), "--self-test"],
            check=True,
            capture_output=True,
            text=True,
        )
        accelerated_self_test = subprocess.run(
            [str(accelerated_binary), "--self-test"],
            check=True,
            capture_output=True,
            text=True,
        )

        capped: list[dict[str, Any]] = []
        for repetition in range(args.capped_repetitions):
            # Alternate order so systematic thermal drift does not always favor
            # the same engine.
            if repetition % 2 == 0:
                base = run_solver(base_binary, args.node_limit, "base")
                accelerated = run_solver(
                    accelerated_binary, args.node_limit, "accelerated"
                )
            else:
                accelerated = run_solver(
                    accelerated_binary, args.node_limit, "accelerated"
                )
                base = run_solver(base_binary, args.node_limit, "base")
            assert_equivalent(base, accelerated)
            capped.append(
                {
                    "repetition": repetition + 1,
                    "base": base,
                    "accelerated": accelerated,
                    "speedup": base["done"]["seconds"]
                    / accelerated["done"]["seconds"],
                }
            )

        full: dict[str, Any] | None = None
        if args.full:
            base = run_solver(base_binary, 0, "base")
            accelerated = run_solver(accelerated_binary, 0, "accelerated")
            assert_equivalent(base, accelerated)
            if accelerated["stdout"].strip() != CANONICAL_ANSWER:
                raise RuntimeError("full benchmark returned an unexpected class")
            full = {
                "base": base,
                "accelerated": accelerated,
                "speedup": base["done"]["seconds"]
                / accelerated["done"]["seconds"],
            }

        record = {
            "schema": "flat-psl4-accelerator-benchmark-v1",
            "created_utc": timestamp,
            "run_id": run_id,
            "host": {
                "platform": platform.platform(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
            "compiler": {
                "command_prefix": compiler,
                "version": command_output(["clang++", "--version"]),
            },
            "sources": {
                "base": str(build_accelerator.BASE.relative_to(REPO)),
                "base_sha256": sha256(build_accelerator.BASE),
                "patch_sha256": sha256(build_accelerator.PATCH),
                "accelerated_sha256": sha256(accelerated_source),
            },
            "self_tests": {
                "base_stderr": base_self_test.stderr,
                "accelerated_stderr": accelerated_self_test.stderr,
            },
            "fixed_bits": FIXED_BITS,
            "canonical_answer": CANONICAL_ANSWER,
            "node_limit": args.node_limit,
            "capped": capped,
            "full": full,
            "scope": (
                "Architecture benchmark on one fixed split-depth-12 task; "
                "not a complete 730810-task enumeration."
            ),
        }
        atomic_json(run_dir / "benchmark.json", record)
        digest = sha256(run_dir / "benchmark.json")
        print(f"receipt={run_dir / 'benchmark.json'}")
        print(f"sha256={digest}")


if __name__ == "__main__":
    main()
