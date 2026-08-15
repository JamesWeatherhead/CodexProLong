#!/usr/bin/env python3
"""Freeze and clean-room test the explicit public allowlist.

Run this last, after the private numerical audit has written
``publication/receipt.json``.  The copied test uses only this allowlist in the
same ``src/campaign/...`` layout used by the public repository.
"""

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

if sys.version_info < (3, 11):
    raise RuntimeError("freeze_publication requires Python >= 3.11")


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "PUBLICATION_MANIFEST.json"
PUBLIC_LAYOUT = Path("src/campaign/geometry/heilbronn_flow_topology_global")
INCLUDE = (
    ".gitignore",
    "HANDOFF.md",
    "LICENSE",
    "README.md",
    "audit_packet.py",
    "freeze_publication.py",
    "global_search.py",
    "public_replay.py",
    "repair_rms_metadata.py",
    "requirements.txt",
    "test_packet.py",
    "publication/receipt.json",
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
        "reason": "original source, documentation, dependency declaration, or coordinate-free receipt",
    }


def build_manifest() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "scope": "publish-safe Heilbronn global-topology source and coordinate-free receipt",
        "public_layout_root": str(PUBLIC_LAYOUT),
        "policy": "explicit allowlist; all files outside it are excluded",
        "include": [include_entry(relative) for relative in INCLUDE],
        "exclude": [
            {
                "path": "PUBLICATION_MANIFEST.json",
                "reason": "a manifest cannot contain its own cryptographic digest",
            },
            {"path": "runs/", "reason": "raw generated coordinate arrays and verbose private logs"},
            {"path": "__pycache__/ and *.pyc", "reason": "generated interpreter caches"},
            {"path": "all files outside the explicit include list", "reason": "conservative publication boundary"},
        ],
        "dependencies_not_copied": [
            {
                "item": "frozen EinsteinArena Heilbronn verifier",
                "sha256": "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d",
                "public_replay_behavior": "hash pin checked; verifier bytes absent and never executed",
            },
            {
                "item": "frozen public solution snapshot",
                "sha256": "e6332c0715a82c9e62d9029385a7db1cab46549bf482ff65dca30e9ee5468d90",
                "public_replay_behavior": "hash pin checked; snapshot bytes absent",
            },
            {
                "item": "private research corpus and raw v1/v2 runs",
                "public_replay_behavior": "absent; private-only audit scope is explicit in receipt",
            },
        ],
        "runtime": {
            "python": ">=3.11",
            "public_replay": "standard library only",
            "private_full_reproduction": "requirements.txt",
        },
        "copied_allowlist_audit": {
            "command": "python3.11 -I src/campaign/geometry/heilbronn_flow_topology_global/public_replay.py",
            "status": "passed-before-canonical-manifest-write",
            "network_required": False,
            "campaign_snapshot_required": False,
            "raw_runs_required": False,
            "corpus_required": False,
            "third_party_packages_required": False,
            "downloaded_or_local_verifier_executed": False,
        },
        "secrets_scanned": True,
        "third_party_candidate_bytes_included": False,
    }


def audit_copy(manifest: dict[str, Any]) -> str:
    with tempfile.TemporaryDirectory(prefix=".public-copy-", dir=HERE) as raw:
        repository = Path(raw) / "repository"
        target = repository / PUBLIC_LAYOUT
        for entry in manifest["include"]:
            destination = target / entry["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HERE / entry["path"], destination)
        atomic_json(target / "PUBLICATION_MANIFEST.json", manifest)
        atomic_json(
            target / "PUBLICATION_EXPORT.json",
            {
                "schema_version": 1,
                "canonical_manifest": "geometry/heilbronn_flow_topology_global/PUBLICATION_MANIFEST.json",
                "canonical_manifest_sha256": "copied-layout-test-does-not-self-pin-manifest",
                "policy": "simulated no-rewrite export for copied-layout testing",
                "files": [
                    {
                        "path": entry["path"],
                        "canonical_sha256": entry["sha256"],
                        "canonical_bytes": entry["bytes"],
                        "public_sha256": entry["sha256"],
                        "public_bytes": entry["bytes"],
                        "portable_path_rewrite": False,
                    }
                    for entry in manifest["include"]
                ],
            },
        )
        environment = dict(os.environ)
        environment["PYTHONNOUSERSITE"] = "1"
        completed = subprocess.run(
            [sys.executable, "-I", str(target / "public_replay.py")],
            cwd=repository,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return completed.stdout.strip()


def main() -> int:
    manifest = build_manifest()
    copied_output = audit_copy(manifest)
    atomic_json(MANIFEST, manifest)
    print(
        json.dumps(
            {
                "status": "ok",
                "manifest": str(MANIFEST),
                "manifest_sha256": sha256_file(MANIFEST),
                "included_files": len(manifest["include"]),
                "copied_public_layout_test": json.loads(copied_output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
