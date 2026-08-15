#!/usr/bin/env python3
"""Validate the frozen publication allowlist without writing files."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "PUBLICATION_MANIFEST.json"
FORBIDDEN_SUFFIXES = {
    ".bin",
    ".db",
    ".gz",
    ".npy",
    ".npz",
    ".pt",
    ".pth",
    ".sqlite",
    ".sqlite3",
    ".zip",
}
PRIVATE_PATH_MARKERS = (
    "/" + "Users" + "/",
    "/" + "home" + "/",
    "/private/" + "var/",
    "file" + "://",
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)
EXPECTED_EXCLUSIONS = {
    "campaign/analysis/second_autocorrelation_forced_bundle_population/runs/20260815T120831Z-reference-pilot/best.npy": "32f3e85f848da524de2c78de31062d2020c251272ef3e635eb4a4d541c76a5c3",
    "campaign/research_corpus/snapshots/20260815T003306Z/corpus.sqlite3": "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_json(value: Any, location: str) -> None:
    if isinstance(value, dict):
        if "values" in value:
            raise AssertionError(f"candidate-like JSON key at {location}")
        for key, child in value.items():
            inspect_json(child, f"{location}.{key}")
    elif isinstance(value, list):
        if len(value) > 512:
            raise AssertionError(f"oversized JSON array at {location}: {len(value)}")
        for index, child in enumerate(value):
            inspect_json(child, f"{location}[{index}]")
    elif isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9+/=]{4096,}", value):
        raise AssertionError(f"large encoded blob at {location}")


def main() -> None:
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    for marker in PRIVATE_PATH_MARKERS:
        if marker in manifest_text:
            raise AssertionError("private absolute path in publication manifest")
    for pattern in SECRET_PATTERNS:
        if pattern.search(manifest_text):
            raise AssertionError("credential-like token in publication manifest")
    manifest = json.loads(manifest_text)
    inspect_json(manifest, MANIFEST.name)
    entries = manifest["payload"]
    if not isinstance(entries, list) or not entries:
        raise AssertionError("payload must be a nonempty list")

    expected_paths: set[str] = set()
    for entry in entries:
        if set(entry) != {"path", "bytes", "sha256", "provenance"}:
            raise AssertionError(f"bad payload record: {entry}")
        relative = PurePosixPath(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != entry["path"]:
            raise AssertionError(f"nonportable path: {entry['path']}")
        if entry["path"] in expected_paths:
            raise AssertionError(f"duplicate path: {entry['path']}")
        expected_paths.add(entry["path"])

        path = ROOT / entry["path"]
        if path.is_symlink() or not path.is_file():
            raise AssertionError(f"missing or symlinked payload: {entry['path']}")
        if path.stat().st_size != entry["bytes"] or sha256_file(path) != entry["sha256"]:
            raise AssertionError(f"size/hash mismatch: {entry['path']}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise AssertionError(f"forbidden payload extension: {entry['path']}")

        text = path.read_text(encoding="utf-8")
        if "\x00" in text:
            raise AssertionError(f"NUL byte in text payload: {entry['path']}")
        for marker in PRIVATE_PATH_MARKERS:
            if marker in text:
                raise AssertionError(f"private absolute path in {entry['path']}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                raise AssertionError(f"credential-like token in {entry['path']}")

        if path.suffix == ".json":
            inspect_json(json.loads(text), entry["path"])
        elif path.suffix == ".jsonl":
            for line_number, line in enumerate(text.splitlines(), 1):
                if line:
                    inspect_json(json.loads(line), f"{entry['path']}:{line_number}")

    actual_paths = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    expected_with_manifest = expected_paths | {MANIFEST.name}
    if actual_paths != expected_with_manifest:
        raise AssertionError(
            {"unexpected": sorted(actual_paths - expected_with_manifest), "missing": sorted(expected_with_manifest - actual_paths)}
        )

    exclusions = {row["path"]: row["sha256"] for row in manifest["excluded_artifacts"]}
    for path, expected_hash in EXPECTED_EXCLUSIONS.items():
        if exclusions.get(path) != expected_hash:
            raise AssertionError(f"missing exact exclusion: {path}")
    policy = manifest["policy"]
    if policy["third_party_candidate_bytes_included"] is not False:
        raise AssertionError("third-party candidate byte policy is not false")
    if policy["checkpoint_payloads_included"] is not False:
        raise AssertionError("checkpoint payload policy is not false")
    if policy["verifier_source_included"] is not False or policy["arena_verifier_executed"] is not False:
        raise AssertionError("verifier boundary is not frozen")
    if policy["coefficient_values_retained_from_public_corpus"] != 0:
        raise AssertionError("public-corpus coefficient retention is nonzero")

    tree_material = "".join(
        f"{row['sha256']}  {row['bytes']}  {row['path']}\n" for row in sorted(entries, key=lambda item: item["path"])
    ).encode("utf-8")
    tree_hash = hashlib.sha256(tree_material).hexdigest()
    if tree_hash != manifest["payload_tree_sha256"]:
        raise AssertionError("payload tree hash mismatch")

    print(
        json.dumps(
            {
                "status": "PASS",
                "payload_files": len(entries),
                "payload_tree_sha256": tree_hash,
                "manifest_sha256": sha256_file(MANIFEST),
                "candidate_payload_files": 0,
                "private_paths": 0,
                "credential_tokens": 0,
                "arena_verifier_executed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
