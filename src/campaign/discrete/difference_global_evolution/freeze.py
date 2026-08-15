#!/usr/bin/env python3
"""Generate the publication allowlist after all other packet files are frozen."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "PUBLICATION_MANIFEST.json"
INCLUDE = (
    "README.md",
    "HANDOFF.md",
    "PROVENANCE.md",
    "solver.py",
    "audit_run.py",
    "test_packet.py",
    "freeze.py",
    "receipt.json",
    "runs/20260815T091243Z_final600/config.json",
    "runs/20260815T091243Z_final600/events.jsonl",
    "runs/20260815T091243Z_final600/summary.json",
)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    files = {}
    for relative in INCLUDE:
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"missing allowlist input: {relative}")
        files[relative] = {
            "bytes": path.stat().st_size,
            "sha256": sha_file(path),
            "license": (
                "repository-authored clean-room code/documentation"
                if path.suffix in {".py", ".md"}
                else "repository-derived metadata; no construction arrays"
            ),
        }
    manifest = {
        "schema": "difference-global-evolution-publication-v1",
        "files": files,
        "excluded": [
            "runs/**/checkpoint.json (contains construction arrays)",
            "runs/smoke_20/**",
            "runs/20260815T090946Z_pilot300/**",
            "__pycache__/**",
            "all files not explicitly allowlisted above",
        ],
        "privacy": {
            "construction_arrays_included": False,
            "arena_snapshot_included": False,
            "verifier_source_included": False,
            "credentials_included": False,
        },
    }
    raw = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary = OUTPUT.with_name(f".{OUTPUT.name}.{os.getpid()}.tmp")
    temporary.write_text(raw, encoding="utf-8")
    os.replace(temporary, OUTPUT)
    print(sha_file(OUTPUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
