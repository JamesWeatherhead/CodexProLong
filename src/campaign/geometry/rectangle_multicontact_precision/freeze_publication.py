#!/usr/bin/env python3
"""Create the conservative public include/exclude manifest for this subtree."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
OUTPUT = HERE / "PUBLICATION_MANIFEST.json"
TRANSIENT_RUNS = {"runs/SMOKE_25", "runs/SMOKE_C3_100"}


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def classify(relative: str) -> tuple[str, str, str]:
    if relative.startswith("__pycache__/"):
        return (
            "exclude",
            "generated Python bytecode",
            "Generated cache; no source-distribution value.",
        )
    for prefix in TRANSIENT_RUNS:
        if relative == prefix or relative.startswith(prefix + "/"):
            return (
                "exclude",
                "smoke run superseded by a complete enumeration",
                "Original generated work, but intentionally omitted as transient output.",
            )
    if relative.startswith("runs/") and Path(relative).name in {
        "best.json",
        "best_changed.json",
    }:
        return (
            "exclude",
            "coordinate payload derived from a public Arena seed",
            "Arena submissions are publicly GET-readable, but no explicit license for user-submitted coordinates was located. Conservative mirror publishes hashes and aggregate results, not coordinate bytes.",
        )
    return (
        "include",
        "frozen source, documentation, aggregate receipt, or coordinate-free run log",
        "Original campaign work; publish under the destination repository license. Literature files contain links and factual descriptions, not copied paper text.",
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
        "policy": "conservative public mirror; coordinate bytes with unspecified Arena-submission licensing excluded",
        "dependencies_not_copied": [
            {
                "item": "EinsteinArena circles-rectangle verifier",
                "sha256": "c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9",
                "license": "MIT in vinid/einstein-arena; retain its license if copied",
            },
            {
                "item": "two public Arena seed coordinate payloads",
                "license": "publicly GET-readable; no explicit user-submission license located; bytes are outside this include set",
            },
        ],
        "include": [entry for entry in entries if entry["decision"] == "include"],
        "exclude": [entry for entry in entries if entry["decision"] == "exclude"],
    }
    atomic_json(OUTPUT, output)
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
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
