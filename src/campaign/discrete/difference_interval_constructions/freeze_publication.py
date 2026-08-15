#!/usr/bin/env python3
"""Create a conservative publication manifest for the frozen lane."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
OUTPUT = HERE / "PUBLICATION_MANIFEST.json"
SUPERSEDED = {
    "checkpoint_q97.json": "single-order checkpoint superseded by checkpoint_large.json",
    "prime_power_smoke.json": "smoke checkpoint superseded by prime_power_checkpoint.json",
}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def classify(relative: str) -> tuple[str, str, str]:
    if relative.startswith("__pycache__/") or relative.endswith((".pyc", ".pyo")):
        return (
            "exclude",
            "generated Python bytecode",
            "Generated cache; no source-distribution value.",
        )
    if relative in SUPERSEDED:
        return (
            "exclude",
            SUPERSEDED[relative],
            "Original generated campaign output; excluded only because an authoritative complete checkpoint supersedes it.",
        )
    return (
        "include",
        "frozen original source, documentation, or deterministic generated receipt/checkpoint",
        "Original campaign work; publish under the destination repository license. No third-party source, database, verifier, or candidate bytes are embedded.",
    )


def atomic_json(path: Path, value: object) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def main() -> int:
    entries = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path == OUTPUT:
            continue
        relative = path.relative_to(HERE).as_posix()
        decision, reason, licensing = classify(relative)
        entries.append(
            {
                "path": relative,
                "sha256": digest(path),
                "bytes": path.stat().st_size,
                "decision": decision,
                "reason": reason,
                "licensing": licensing,
            }
        )
    output = {
        "scope": HERE.relative_to(REPOSITORY).as_posix(),
        "policy": "conservative public mirror with transient checkpoints and generated caches excluded",
        "dependencies_not_copied": [
            {
                "item": "EinsteinArena difference-bases verifier",
                "sha256": "a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585",
                "license": "MIT in vinid/einstein-arena; retain its license if copied",
            },
            {
                "item": "frozen EinsteinArena public corpus database",
                "sha256": "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb",
                "license": "not copied; contains GET-readable public Arena text and submissions with no blanket relicensing asserted here",
            },
            {
                "item": "Banakh--Gavrylkiv paper",
                "doi": "10.1142/S0219498819500816",
                "license": "not copied; only bibliographic facts and a source link are included",
            },
            {
                "item": "SymPy runtime dependency",
                "license": "BSD-3-Clause; package bytes are not copied",
            },
        ],
        "include": [entry for entry in entries if entry["decision"] == "include"],
        "exclude": [entry for entry in entries if entry["decision"] == "exclude"],
    }
    atomic_json(OUTPUT, output)
    print(
        json.dumps(
            {
                "output": OUTPUT.relative_to(REPOSITORY).as_posix(),
                "include_count": len(output["include"]),
                "exclude_count": len(output["exclude"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
