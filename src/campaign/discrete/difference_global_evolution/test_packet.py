#!/usr/bin/env python3
"""Standalone copied-allowlist test for the public evolution packet."""

from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "PUBLICATION_MANIFEST.json"
STRICT_GATE = 2.6390274685066077


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def difference_bits(values: Iterable[int]) -> int:
    values = tuple(values)
    marks = 0
    for value in values:
        marks |= 1 << value
    result = 1
    for value in values:
        result |= marks >> value
    return result


def first_missing(bits: int) -> int:
    return ((~bits) & (bits + 1)).bit_length() - 1


def contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(contains_key(item, key) for item in value)
    return False


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["schema"] != "difference-global-evolution-publication-v1":
        raise AssertionError("unexpected publication schema")
    for relative, record in manifest["files"].items():
        path = ROOT / relative
        if not path.is_file():
            raise AssertionError(f"allowlisted file missing: {relative}")
        if path.stat().st_size != record["bytes"] or sha_file(path) != record["sha256"]:
            raise AssertionError(f"allowlisted hash/size mismatch: {relative}")

    receipt = json.loads((ROOT / "receipt.json").read_text(encoding="utf-8"))
    summary = json.loads(
        (ROOT / "runs/20260815T091243Z_final600/summary.json").read_text(
            encoding="utf-8"
        )
    )
    config = json.loads(
        (ROOT / "runs/20260815T091243Z_final600/config.json").read_text(
            encoding="utf-8"
        )
    )
    if receipt["status"] != "exact_replay_passed" or receipt["gate"]["cleared"]:
        raise AssertionError("receipt outcome mismatch")
    if summary["gate_clearer"] or summary["completed_iterations"] != 600:
        raise AssertionError("summary outcome mismatch")
    if receipt["files"]["solver.py"]["sha256"] != sha_file(ROOT / "solver.py"):
        raise AssertionError("receipt solver hash mismatch")
    for name in ("config.json", "events.jsonl", "summary.json"):
        path = ROOT / "runs/20260815T091243Z_final600" / name
        if receipt["files"][name]["sha256"] != sha_file(path):
            raise AssertionError(f"receipt run hash mismatch: {name}")
    if config["source_sha256"] != sha_file(ROOT / "solver.py"):
        raise AssertionError("config/source pin mismatch")

    public_json = [receipt, summary, config, manifest]
    if any(contains_key(value, "set") for value in public_json):
        raise AssertionError("public JSON unexpectedly contains a construction array")
    for line in (ROOT / "runs/20260815T091243Z_final600/events.jsonl").read_text(
        encoding="utf-8"
    ).splitlines():
        event = json.loads(line)
        if contains_key(event, "set"):
            raise AssertionError("public event contains a construction array")

    # Standalone clean-room formula sanity checks.
    synthetic = tuple(range(360))
    if first_missing(difference_bits(synthetic)) - 1 != 359:
        raise AssertionError("clean-room bitset formula failed synthetic check")
    if Fraction(360**2, 49_109) != Fraction(129_600, 49_109):
        raise AssertionError("exact incumbent fraction mismatch")
    first_gate = next(
        coverage
        for coverage in range(49_109, 49_200)
        if float(Fraction(360**2, coverage)) < STRICT_GATE
    )
    if first_gate != 49_110:
        raise AssertionError("gate boundary mismatch")

    text = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
        for relative in manifest["files"]
    )
    secret_patterns = (
        r"gxl_[A-Za-z0-9_-]{20,}",
        r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
    )
    if any(re.search(pattern, text) for pattern in secret_patterns):
        raise AssertionError("credential-like string found in public allowlist")
    print("difference_global_evolution public packet: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
