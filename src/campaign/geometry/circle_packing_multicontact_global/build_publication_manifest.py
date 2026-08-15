#!/usr/bin/env python3
"""Build the deterministic public allowlist and exact local exclusion ledger."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
MANIFEST = HERE / "PUBLICATION_MANIFEST.json"
ROOT_RELATIVE = HERE.relative_to(REPOSITORY).as_posix()

INCLUDE_LICENSES = {
    "README.md": "codexprolong-mit",
    "HANDOFF.md": "codexprolong-mit",
    "PROVENANCE.md": "codexprolong-mit",
    "LICENSES.md": "codexprolong-mit",
    "codim3_pivots.py": "codexprolong-mit",
    "public_verifier_formula.py": "codexprolong-mit",
    "replay_public.py": "codexprolong-mit",
    "test_public_replay.py": "codexprolong-mit",
    "build_publication_manifest.py": "codexprolong-mit",
    "verify_publication.py": "codexprolong-mit",
    "receipt_v2.json": "codexprolong-generated-mit",
    "artifacts/20260815T074600Z_CANONICAL_STRAT2000_V2_best_changed.json": (
        "codexprolong-generated-mit"
    ),
    "artifacts/20260815T074700Z_NEUTRAL_STRAT1000_V2_best_changed.json": (
        "codexprolong-generated-mit"
    ),
    "reference/frozen_verifier.py.b64": "einstein-arena-mit",
    "reference/EINSTEIN_ARENA_LICENSE.txt": "einstein-arena-mit",
    "reference/CODEXPROLONG_LICENSE.txt": "codexprolong-mit",
}

LICENSES = {
    "codexprolong-mit": {
        "name": "MIT License",
        "copyright": "Copyright (c) 2026 James Weatherhead",
        "source": "reference/CODEXPROLONG_LICENSE.txt",
        "applies_to": "original source, tests, and prose",
    },
    "codexprolong-generated-mit": {
        "name": "MIT License",
        "copyright": "Copyright (c) 2026 James Weatherhead",
        "source": "reference/CODEXPROLONG_LICENSE.txt",
        "applies_to": "locally generated receipts and candidate coordinates",
    },
    "einstein-arena-mit": {
        "name": "MIT License",
        "copyright": "Copyright (c) 2026 EinsteinArena",
        "source": "reference/EINSTEIN_ARENA_LICENSE.txt",
        "upstream_commit": "98073fca26654d048d70acdfe1e319a23e8e41c6",
        "applies_to": "base64-wrapped frozen verifier reference and license notice",
    },
    "excluded-derived": {
        "name": "Derived build artifact; not published",
        "source": "corresponding local source",
        "applies_to": "Python bytecode/cache files",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def record(relative: str, license_id: str, reason: str | None = None) -> dict[str, Any]:
    path = HERE / relative
    if not path.is_file():
        raise RuntimeError(f"manifest path is not a file: {relative}")
    result: dict[str, Any] = {
        "path": f"{ROOT_RELATIVE}/{relative}",
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "license_id": license_id,
    }
    if reason is not None:
        result["reason"] = reason
    return result


def excluded_class(relative: str) -> tuple[str, str]:
    if "/__pycache__/" in f"/{relative}" or relative.endswith(".pyc"):
        return "excluded-derived", "generated interpreter cache"
    if relative == "receipt.json":
        return "codexprolong-generated-mit", "superseded pre-citation-correction receipt"
    if relative.startswith("artifacts/"):
        return "codexprolong-generated-mit", "superseded non-V2 compact artifact"
    if relative.startswith("runs/"):
        return (
            "codexprolong-generated-mit",
            "private raw run stream; compact hash-pinned receipt and payload are published",
        )
    if relative in {"freeze_receipt.py", "test_codim3_pivots.py"}:
        return (
            "codexprolong-mit",
            "private full-run reproduction helper with non-allowlisted campaign dependencies",
        )
    return "codexprolong-mit", "not selected for the minimal public packet"


def main() -> int:
    included = [
        record(relative, license_id)
        for relative, license_id in sorted(INCLUDE_LICENSES.items())
    ]
    existing = {
        path.relative_to(HERE).as_posix()
        for path in HERE.rglob("*")
        if path.is_file() and path != MANIFEST
    }
    unknown_includes = set(INCLUDE_LICENSES) - existing
    if unknown_includes:
        raise RuntimeError(f"missing allowlist files: {sorted(unknown_includes)}")
    excluded: list[dict[str, Any]] = []
    for relative in sorted(existing - set(INCLUDE_LICENSES)):
        license_id, reason = excluded_class(relative)
        excluded.append(record(relative, license_id, reason))

    manifest = {
        "schema": "codexprolong-publication-manifest-v1",
        "frozen_date": "2026-08-15",
        "root": ROOT_RELATIVE,
        "hash_algorithm": "sha256",
        "self": {
            "path": f"{ROOT_RELATIVE}/PUBLICATION_MANIFEST.json",
            "license_id": "codexprolong-mit",
            "hash_note": "self hash is reported out-of-band after deterministic generation",
        },
        "licenses": LICENSES,
        "allowlist": included,
        "excluded_local_files": excluded,
        "scope_note": (
            "The exclusion ledger is exact for files below root at generation time; "
            "out-of-tree temporary files and unrelated campaign paths are outside scope."
        ),
        "public_commands": [
            f"python3 {ROOT_RELATIVE}/test_public_replay.py",
            f"python3 {ROOT_RELATIVE}/replay_public.py",
            f"python3 {ROOT_RELATIVE}/verify_publication.py",
        ],
        "security": {
            "downloaded_verifier_dynamic_import_or_exec": False,
            "verifier_reference_handling": (
                "base64-decode in memory solely for SHA-256; never write, import, compile, "
                "evaluate, or execute"
            ),
            "public_paths": "repository-relative",
            "external_writes": [],
        },
    }
    atomic_json(MANIFEST, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
