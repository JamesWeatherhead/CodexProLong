#!/usr/bin/env python3
"""Create or verify the immutable receipt for the FINAL_V2 bounded screen."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from replay_receipt import audit


HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "receipt.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def build_receipt() -> dict[str, Any]:
    replay = audit()
    return {
        "schema": "einstein-arena.local-frontier-receipt.v1",
        "problem": "min-distance-ratio-2d",
        "classification": "bounded deterministic negative frontier; not a global proof",
        "run": "runs/FINAL_V2",
        "result": replay,
        "source_hashes": {
            "adjacent_topology_escape.py": sha256_file(HERE / "adjacent_topology_escape.py"),
            "assets.json": sha256_file(HERE / "assets.json"),
            "freeze_receipt.py": sha256_file(HERE / "freeze_receipt.py"),
            "replay_receipt.py": sha256_file(HERE / "replay_receipt.py"),
        },
        "provenance": {
            "paperclip_primary_lines": {
                "url": "https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L636-L640",
                "use": "formal max/min-distance problem, history, and reported n=16 numerical construction",
            },
            "primary_public_sources": [
                "https://erich-friedman.github.io/packing/maxmin/",
                "https://arxiv.org/abs/2601.05943",
                "https://www.renyi.hu/~p_erdos/1951-03.pdf",
            ],
            "upstream_license_handling": (
                "The Friedman page and GIFs state no reuse license. Image bytes are not "
                "redistributed; assets.json contains only factual pixel-center and colored-edge measurements."
            ),
            "live_get_only_revalidation": {
                "fetched_at": "2026-08-15T05:55:20Z",
                "problem_get_sha256": "0684c3210debd85f52db3719ec676acee742fe50b99f3e53abe924fce51720e7",
                "leaderboard_get_sha256": "8b0c5577392fab4aab1e4af5ae1f764bc733cdb0c284c3b19f819539075a4f91",
                "solutions_get_sha256": "56ef22237b118fe184066bde60ff5f541d4fce177f0b0edd7f00442b6741f3be",
                "threads_get_sha256": "d48e147bd8a9fe5a6f1e587c2e6920ef5c1f53ce4d1f3a046209e05312301191",
            },
        },
        "external_mutations": [],
        "publication": {
            "include": [
                "README.md",
                "HANDOFF.md",
                "adjacent_topology_escape.py",
                "assets.json",
                "freeze_receipt.py",
                "replay_receipt.py",
                "receipt.json",
                "runs/FINAL_V2/best.json",
                "runs/FINAL_V2/corpus_audit.json",
                "runs/FINAL_V2/events.jsonl",
                "runs/FINAL_V2/reconstructed_assets.json",
                "runs/FINAL_V2/summary.json",
            ],
            "exclude": ["__pycache__/", "runs/FINAL_V1/", "runs/SMOKE_DEATHS/"],
        },
    }


def main() -> int:
    raw = canonical(build_receipt())
    if RECEIPT.exists():
        if RECEIPT.read_bytes() != raw:
            raise RuntimeError("receipt exists but does not match reproducible reconstruction")
        print(f"verified immutable receipt {sha256_file(RECEIPT)}")
        return 0
    descriptor = os.open(RECEIPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        RECEIPT.unlink(missing_ok=True)
        raise
    print(f"created immutable receipt {sha256_file(RECEIPT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
