#!/usr/bin/env python3
"""Create the conservative include/exclude manifest for this frozen subtree."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
OUTPUT = HERE / "PUBLICATION_MANIFEST.json"
INCOMPLETE_RUNS = {
    "runs/20260815T_CODIM2_FULL",
    "runs/SMOKE_20B",
    "runs/SMOKE_20C",
}


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
    for prefix in INCOMPLETE_RUNS:
        if relative == prefix or relative.startswith(prefix + "/"):
            return (
                "exclude",
                "smoke or interrupted run superseded by a complete run",
                "Original generated work, but intentionally omitted as transient output.",
            )
    if relative == "recovered_claudeevolve_strict.json":
        return (
            "exclude",
            "verbatim third-party coordinate table",
            "Indexed upstream repository declared Apache-2.0; include only with the upstream Apache-2.0 license and attribution. Conservative public mirror excludes the bytes.",
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
        "Original campaign work; publish under the destination repository license. Paper/source quotations are not embedded, only links and short factual descriptions.",
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
        "policy": "conservative public mirror; coordinate bytes with uncertain or third-party provenance excluded",
        "dependencies_not_copied": [
            {
                "item": "EinsteinArena circle-packing verifier",
                "sha256": "2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab",
                "license": "MIT in vinid/einstein-arena; retain its license if copied",
            },
            {
                "item": "ClaudeEvolve recovered paper table",
                "license": "indexed upstream repository declared Apache-2.0; raw table excluded from the mirror",
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
