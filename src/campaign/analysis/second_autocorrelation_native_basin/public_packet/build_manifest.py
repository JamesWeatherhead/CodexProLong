#!/usr/bin/env python3
"""Regenerate the exact C2 public allowlist as the final content write.

Copyright (c) 2026 C2 Native Basin contributors. MIT License.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PACKET = Path(__file__).resolve().parent
LANE = PACKET.parent
MANIFEST = PACKET / "manifest.json"
PUBLIC_FILES = {
    "DEPENDENCIES.md",
    "H100_PLAN.md",
    "LICENSE",
    "NOTICE.md",
    "README.md",
    "build_manifest.py",
    "c2_cleanroom.py",
    "configs/h100_phase_a.json",
    "configs/h100_phase_b.json",
    "copy_allowlist_test.py",
    "evidence.json",
    "h100_preflight.py",
    "provenance.json",
    "replay_public.py",
    "requirements-test.txt",
    "scan_packet.py",
    "test_packet.py",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def license_class(relative: str) -> str:
    if relative == "LICENSE":
        return "MIT-License-Text"
    if relative.endswith(".json") or relative == "manifest.json":
        return "Factual-Metadata"
    if relative == "requirements-test.txt":
        return "Dependency-Declaration"
    return "MIT-Original"


def media_type(relative: str) -> str:
    suffix = Path(relative).suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix in {".md", ".txt"} or relative == "LICENSE":
        return "text/plain; charset=utf-8"
    if suffix == ".py":
        return "text/x-python; charset=utf-8"
    raise ValueError(f"unclassified public media type: {relative}")


def exclusion_reason(relative: str) -> str:
    path = Path(relative)
    if path.suffix.lower() in {".pyc", ".pyo"} or "__pycache__" in path.parts:
        return "cache_or_compiled_bytecode"
    if path.suffix.lower() in {".npy", ".npz", ".pt", ".pth"}:
        return "large_array_or_model_state"
    if "source_snapshot" in path.parts:
        return "redundant_internal_source_snapshot"
    if "runs" in path.parts:
        return "raw_internal_run_log_or_receipt"
    if path.name in {"native_basin.py", "replay.py", "test_native_basin.py"}:
        return "internal_code_with_private_verifier_or_state_boundary"
    if path.name == "launch_h100.sh":
        return "internal_launcher_for_nonpublic_acceptance_path"
    if path.name == ".gitignore":
        return "workspace_control_not_public_artifact"
    if path.name == "literature.json":
        return "superseded_working_provenance_metadata"
    if path.name == "receipt.json":
        return "superseded_internal_receipt"
    if path.suffix.lower() in {".md", ".json", ".jsonl"}:
        return "internal_working_document_superseded_or_private"
    return "not_required_and_not_cleared_for_publication"


def build_manifest() -> dict[str, Any]:
    actual_public = {
        path.relative_to(PACKET).as_posix()
        for path in PACKET.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual_public != PUBLIC_FILES:
        raise RuntimeError(
            "public source file-set differs from the declared allowlist: "
            f"missing={sorted(PUBLIC_FILES - actual_public)}, "
            f"extra={sorted(actual_public - PUBLIC_FILES)}"
        )

    allowlist: list[dict[str, Any]] = []
    for relative in sorted(PUBLIC_FILES):
        path = PACKET / relative
        if path.is_symlink():
            raise RuntimeError(f"public symlink refused: {relative}")
        allowlist.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "media_type": media_type(relative),
                "license_class": license_class(relative),
                "origin": "original_publication_packet",
            }
        )
    allowlist.append(
        {
            "path": "manifest.json",
            "bytes": None,
            "sha256": None,
            "media_type": "application/json",
            "license_class": "Factual-Metadata",
            "origin": "generated_allowlist_manifest",
            "self_reference": "content hash and byte size intentionally null",
        }
    )
    allowlist.sort(key=lambda entry: entry["path"])

    excluded: list[dict[str, Any]] = []
    for path in sorted(LANE.rglob("*")):
        if not path.is_file() or PACKET in path.parents:
            continue
        relative = path.relative_to(LANE).as_posix()
        excluded.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "reason": exclusion_reason(relative),
                "distribution_status": "excluded_not_distributed",
            }
        )

    reason_counts: Counter[str] = Counter()
    reason_bytes: defaultdict[str, int] = defaultdict(int)
    for entry in excluded:
        reason_counts[entry["reason"]] += 1
        reason_bytes[entry["reason"]] += entry["bytes"]
    by_reason = {
        reason: {"files": reason_counts[reason], "bytes": reason_bytes[reason]}
        for reason in sorted(reason_counts)
    }
    included_bytes_without_manifest = sum(
        entry["bytes"] for entry in allowlist if entry["bytes"] is not None
    )
    return {
        "schema": 1,
        "packet": {
            "name": "second_autocorrelation_native_basin_public_packet",
            "snapshot_date": "2026-08-15",
            "hash_algorithm": "SHA-256",
            "path_base": "public_packet/",
            "self_hash_policy": "manifest.json is allowlisted but omits its own recursive content hash and byte size; report its detached SHA-256 after generation",
        },
        "policy": {
            "default_deny": True,
            "maximum_public_file_bytes": 1000000,
            "large_arrays_allowed": False,
            "upstream_or_third_party_bytes_allowed": False,
            "caches_allowed": False,
            "private_absolute_paths_allowed": False,
            "provider_credentials_allowed": False,
            "unclear_licensing_allowed": False,
            "network_required_for_replay": False,
            "downloaded_verifier_execution_allowed": False,
        },
        "inventory": {
            "allowlisted_files_including_manifest": len(allowlist),
            "allowlisted_bytes_excluding_manifest": included_bytes_without_manifest,
            "excluded_files": len(excluded),
            "excluded_bytes": sum(entry["bytes"] for entry in excluded),
            "excluded_by_reason": by_reason,
        },
        "allowlist": allowlist,
        "excluded_lane_files": excluded,
    }


def main() -> int:
    manifest = build_manifest()
    payload = json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary = MANIFEST.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(MANIFEST)
    print(
        json.dumps(
            {
                "status": "WROTE_MANIFEST_LAST",
                "manifest_sha256": sha256_file(MANIFEST),
                "manifest_bytes": MANIFEST.stat().st_size,
                "allowlisted_files": len(manifest["allowlist"]),
                "excluded_files": len(manifest["excluded_lane_files"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
