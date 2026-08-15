#!/usr/bin/env python3
"""Copy the exact allowlist into both repository layouts and replay offline."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST_NAME = "PUBLICATION_MANIFEST.json"
LAYOUTS = (
    "campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z",
    "src/campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def forbidden_tokens() -> tuple[bytes, ...]:
    return (
        b"/" + b"Users" + b"/" + b"jacweath",
        b"api" + b"_key",
        b"authorization" + b": bearer",
        b"sk-" + b"proj-",
    )


def validate_source() -> tuple[dict[str, object], list[str]]:
    manifest_path = HERE / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != "heilbronn-gamma-monodromy-publication-v1":
        raise AssertionError("unexpected publication manifest schema")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise AssertionError("manifest files must be a list")
    paths = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
            raise AssertionError("file entries must be exactly {path,bytes,sha256}")
        relative = entry["path"]
        relpath = Path(relative)
        if relpath.is_absolute() or ".." in relpath.parts or relative in paths:
            raise AssertionError(f"unsafe or duplicate allowlist path: {relative}")
        path = HERE / relpath
        if path.is_symlink() or not path.is_file():
            raise AssertionError(f"allowlist entry is not a regular file: {relative}")
        if path.stat().st_size != entry["bytes"] or sha256_file(path) != entry["sha256"]:
            raise AssertionError(f"allowlist digest mismatch: {relative}")
        if hasattr(os, "listxattr") and os.listxattr(path):
            raise AssertionError(f"extended attributes remain on: {relative}")
        payload = path.read_bytes().lower()
        if any(token in payload for token in forbidden_tokens()):
            raise AssertionError(f"private path or credential marker in: {relative}")
        paths.append(relative)

    observed = {
        str(path.relative_to(HERE))
        for path in HERE.rglob("*")
        if path.is_file() and "__pycache__" not in path.relative_to(HERE).parts
    }
    expected = set(paths) | {MANIFEST_NAME}
    if observed != expected:
        raise AssertionError(
            f"publication closure mismatch: extra={sorted(observed-expected)}, "
            f"missing={sorted(expected-observed)}"
        )

    classes = manifest["license"]["classes"]
    classified = [path for record in classes.values() for path in record["paths"]]
    if len(classified) != len(set(classified)) or set(classified) != set(paths):
        raise AssertionError("license classes do not partition the exact allowlist")
    for source in manifest["provenance"]["excluded_private_sources"]:
        if source["included"] or source["license_id"] != "NOASSERTION":
            raise AssertionError("private-source provenance boundary is incomplete")
    if manifest["network_required"] or manifest["third_party_source_bytes_included"]:
        raise AssertionError("publication boundary unexpectedly widened")
    return manifest, paths


def copied_tree_files(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}


def main() -> int:
    manifest, paths = validate_source()
    outcomes = []
    with tempfile.TemporaryDirectory(prefix=".publication-selftest-", dir=HERE) as raw:
        temporary = Path(raw)
        for index, layout in enumerate(LAYOUTS):
            repository = temporary / f"repo-{index}"
            destination = repository / layout
            destination.mkdir(parents=True)
            for relative in (*paths, MANIFEST_NAME):
                source = HERE / relative
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            expected = set(paths) | {MANIFEST_NAME}
            if copied_tree_files(destination) != expected:
                raise AssertionError(f"copied allowlist closure failed for {layout}")

            environment = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "LANG": "C",
                "LC_ALL": "C",
            }
            completed = subprocess.run(
                [sys.executable, "-I", "-B", str(destination / "public_replay.py")],
                cwd=repository,
                env=environment,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            receipt = json.loads(completed.stdout)
            if (
                receipt["status"] != "PASS"
                or not receipt["publication_manifest_verified"]
                or receipt["legal_gate_clearers"] != 0
            ):
                raise AssertionError(f"copied replay verdict failed for {layout}")
            if copied_tree_files(destination) != expected:
                raise AssertionError(f"copied replay wrote files for {layout}")
            outcomes.append(
                {
                    "layout": layout,
                    "status": receipt["status"],
                    "generic_roots": receipt["generic_roots_replayed"],
                    "target_roots": receipt["distinct_successful_target_roots"],
                    "gate_clearers": receipt["legal_gate_clearers"],
                }
            )

    result = {
        "schema": "heilbronn-gamma-monodromy-copied-selftest-v1",
        "status": "PASS",
        "allowlisted_files": len(paths),
        "manifest_sha256": sha256_file(HERE / MANIFEST_NAME),
        "layouts": outcomes,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
