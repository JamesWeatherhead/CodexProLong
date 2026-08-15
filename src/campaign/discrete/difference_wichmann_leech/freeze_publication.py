#!/usr/bin/env python3
"""Create and clean-room audit the conservative publication allowlist."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "PUBLICATION_MANIFEST.json"
RUN = "runs/20260815T084100Z_exact_sweep"
INCLUDE = (
    "HANDOFF.md",
    "PROVENANCE.md",
    "README.md",
    "freeze_publication.py",
    "local_verifier_audit.json",
    f"{RUN}/config.json",
    f"{RUN}/events.jsonl",
    f"{RUN}/summary.json",
    "search.py",
    "test_packet.py",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    raw = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(raw, encoding="utf-8")
    os.replace(temporary, path)


def include_entry(relative: str) -> dict[str, Any]:
    path = HERE / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "decision": "include",
        "reason": "original clean-room source, documentation, or deterministic receipt",
        "licensing": (
            "Original campaign work; publish under the destination repository "
            "license. No third-party PDF, verifier, corpus, program, or payload "
            "array is embedded."
        ),
    }


def build_manifest() -> dict[str, Any]:
    return {
        "scope": "campaign/discrete/difference_wichmann_leech",
        "policy": "explicit conservative allowlist; caches and all external bytes excluded",
        "include": [include_entry(relative) for relative in INCLUDE],
        "exclude": [
            {
                "path": "PUBLICATION_MANIFEST.json",
                "decision": "exclude-from-self-hash",
                "reason": "manifest cannot include its own cryptographic digest",
            },
            {
                "path": "__pycache__/",
                "decision": "exclude",
                "reason": "generated interpreter cache",
            },
            {
                "path": "all files outside the explicit include list",
                "decision": "exclude",
                "reason": "not required to reproduce this bounded result",
            },
        ],
        "dependencies_not_copied": [
            {
                "item": "EinsteinArena difference-bases verifier",
                "sha256": "a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585",
                "license": "MIT in vinid/einstein-arena; source not copied",
            },
            {
                "item": "frozen public Arena corpus",
                "sha256": "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb",
                "license": "GET-readable public data; no blanket relicensing asserted and bytes not copied",
            },
            {
                "item": "Saarela--Vanhatalo article PDF",
                "doi": "10.37236/13806",
                "sha256": "b6f32a562a4f421496b94c0c4ab61079df623e59afd8e32da0f1b06561475fce",
                "license": "CC BY 4.0; PDF not copied",
            },
            {
                "item": "Banakh--Gavrylkiv Paperclip full text",
                "arxiv": "1702.02631",
                "license": "not copied; line-pinned citation links only",
            },
        ],
        "copied_allowlist_audit": {
            "command": "python3 test_packet.py",
            "status": "passed-before-freeze",
            "network_required": False,
            "external_verifier_required": False,
        },
    }


def audit_copy(manifest: dict[str, Any]) -> str:
    with tempfile.TemporaryDirectory(prefix="difference-wichmann-publication-") as raw:
        target = Path(raw) / "difference_wichmann_leech"
        for entry in manifest["include"]:
            destination = target / entry["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERE / entry["path"], destination)
        atomic_json(target / "PUBLICATION_MANIFEST.json", manifest)
        completed = subprocess.run(
            [sys.executable, "test_packet.py"],
            cwd=target,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return completed.stdout.strip()


def main() -> int:
    manifest = build_manifest()
    audit_output = audit_copy(manifest)
    atomic_json(MANIFEST, manifest)
    print(
        json.dumps(
            {
                "manifest": str(MANIFEST),
                "manifest_sha256": sha256_file(MANIFEST),
                "included_files": len(manifest["include"]),
                "copied_allowlist_test": audit_output,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
