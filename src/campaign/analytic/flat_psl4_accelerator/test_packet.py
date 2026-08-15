#!/usr/bin/env python3
"""Publication-safe deterministic regression for the PSL-4 accelerator packet."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import benchmark_accelerator as benchmark
import build_accelerator


HERE = Path(__file__).resolve().parent
BENCHMARK = HERE / "runs" / "20260815T080000Z" / "benchmark.json"
VERIFIER_REPLAY = (
    HERE / "runs" / "20260815T080000Z" / "verifier_replay_cleanroom.json"
)
BENCHMARK_SHA256 = "a8ceffa47fbea1095919a1cd28561cff32d58c12ac1828670ef0b29156baf6d5"
VERIFIER_REPLAY_SHA256 = "cbac86d9ee4d5695e93f40168202bd2e5df69959f3e2eff4f0f9d61722fd274b"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_hash(path: Path, expected: str) -> None:
    observed = sha256(path)
    if observed != expected:
        raise RuntimeError(f"hash mismatch for {path}: {observed} != {expected}")


def require_equivalent(left: dict[str, Any], right: dict[str, Any]) -> None:
    for key in benchmark.COUNTER_KEYS:
        if left["done"][key] != right["done"][key]:
            raise RuntimeError(f"recorded counter mismatch: {key}")
    if left["stdout"] != right["stdout"]:
        raise RuntimeError("recorded answer output mismatch")


def audit_frozen_receipts() -> None:
    require_hash(BENCHMARK, BENCHMARK_SHA256)
    require_hash(VERIFIER_REPLAY, VERIFIER_REPLAY_SHA256)
    record = json.loads(BENCHMARK.read_text())
    if record["sources"]["base_sha256"] != build_accelerator.BASE_SHA256:
        raise RuntimeError("benchmark base-source pin changed")
    if record["sources"]["patch_sha256"] != build_accelerator.PATCH_SHA256:
        raise RuntimeError("benchmark patch pin changed")
    if record["sources"]["accelerated_sha256"] != build_accelerator.OUTPUT_SHA256:
        raise RuntimeError("benchmark generated-source pin changed")
    for pair in record["capped"]:
        require_equivalent(pair["base"], pair["accelerated"])
        if pair["speedup"] <= 1.25:
            raise RuntimeError("recorded capped speedup is below 1.25x")
    full = record["full"]
    if full is None:
        raise RuntimeError("full exact task benchmark is missing")
    require_equivalent(full["base"], full["accelerated"])
    if full["accelerated"]["stdout"].strip() != benchmark.CANONICAL_ANSWER:
        raise RuntimeError("full task answer changed")
    if full["speedup"] <= 1.25:
        raise RuntimeError("recorded full-task speedup is below 1.25x")

    verifier = json.loads(VERIFIER_REPLAY.read_text())
    if verifier["answer_bits"] != benchmark.CANONICAL_ANSWER:
        raise RuntimeError("verifier replay answer changed")
    if verifier["exact_peak_sidelobe"] != 4:
        raise RuntimeError("verifier replay is not PSL-4")
    if (
        verifier["verifier_sha256"]
        != verifier["verifier_source_id"].split("/")[-1][:-3]
    ):
        raise RuntimeError("verifier filename/hash binding changed")


def live_differential() -> None:
    with tempfile.TemporaryDirectory(prefix="psl4-packet-test-") as name:
        temporary = Path(name)
        accelerated_source = temporary / "psl4_accelerated.cpp"
        base_binary = temporary / "base"
        accelerated_binary = temporary / "accelerated"
        subprocess.run(
            [
                "python3",
                str(HERE / "build_accelerator.py"),
                "--output",
                str(accelerated_source),
            ],
            check=True,
            capture_output=True,
            text=True,
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
        subprocess.run([str(base_binary), "--self-test"], check=True)
        subprocess.run([str(accelerated_binary), "--self-test"], check=True)
        base = benchmark.run_solver(base_binary, 100_000, "base")
        accelerated = benchmark.run_solver(
            accelerated_binary, 100_000, "accelerated"
        )
        benchmark.assert_equivalent(base, accelerated)

    subprocess.run(
        ["python3", str(HERE / "verify_answer.py")],
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> None:
    audit_frozen_receipts()
    live_differential()
    print("packet test OK: hashes, build, self-tests, 100k-node differential, verifier")


if __name__ == "__main__":
    main()
