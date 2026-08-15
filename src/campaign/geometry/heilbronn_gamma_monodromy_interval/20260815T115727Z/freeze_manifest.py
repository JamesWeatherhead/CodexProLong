#!/usr/bin/env python3
"""Generate the exact portable publication allowlist as the final file mutation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from public_replay import build_receipt

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "PUBLICATION_MANIFEST.json"
BUNDLE_ID = "heilbronn-gamma-monodromy-interval-20260815T115727Z"
CAMPAIGN_LAYOUT = (
    "campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z"
)
SRC_LAYOUT = (
    "src/campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z"
)
PUBLIC_FILES = (
    ".gitignore",
    "HANDOFF.md",
    "LICENSE",
    "PROVENANCE.md",
    "README.md",
    "audit.py",
    "bounded_monodromy.py",
    "bounded_result.json",
    "core.py",
    "derived_inputs.json",
    "exact_krawczyk.py",
    "freeze_manifest.py",
    "incumbent_krawczyk.json",
    "literature_sources.json",
    "public_replay.py",
    "publication_selftest.py",
    "replay.py",
    "replay_receipt.json",
    "requirements.txt",
    "target_manifest.json",
)
LICENSE_CLASSES = {
    "first-party-mit": {
        "license_id": "MIT",
        "description": "Project-authored source, documentation, and configuration.",
        "paths": [
            ".gitignore",
            "HANDOFF.md",
            "PROVENANCE.md",
            "README.md",
            "audit.py",
            "bounded_monodromy.py",
            "core.py",
            "exact_krawczyk.py",
            "freeze_manifest.py",
            "public_replay.py",
            "publication_selftest.py",
            "replay.py",
            "requirements.txt",
        ],
    },
    "mit-license-text": {
        "license_id": "MIT",
        "description": "License text governing first-party material and the manifest envelope.",
        "paths": ["LICENSE"],
    },
    "project-generated-factual-output": {
        "license_id": "NOASSERTION",
        "description": (
            "Project-generated numerical/factual output; no ownership claim over "
            "underlying mathematical or source facts."
        ),
        "paths": [
            "bounded_result.json",
            "incumbent_krawczyk.json",
            "replay_receipt.json",
            "target_manifest.json",
        ],
    },
    "source-derived-factual-projection": {
        "license_id": "NOASSERTION",
        "description": (
            "Compact numerical/integer projection; private source bytes are not included."
        ),
        "paths": ["derived_inputs.json"],
    },
    "bibliographic-facts-and-links": {
        "license_id": "NOASSERTION",
        "description": "Bibliographic facts, URLs, request IDs, and project scope notes only.",
        "paths": ["literature_sources.json"],
    },
}


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


def validate_allowlist() -> None:
    classified = [
        path for record in LICENSE_CLASSES.values() for path in record["paths"]
    ]
    if len(classified) != len(set(classified)) or set(classified) != set(PUBLIC_FILES):
        raise AssertionError("license classes must partition PUBLIC_FILES")
    for relative in PUBLIC_FILES:
        path = HERE / relative
        if path.is_symlink() or not path.is_file():
            raise AssertionError(f"not a regular publication file: {relative}")
        if hasattr(os, "listxattr") and os.listxattr(path):
            raise AssertionError(f"extended attributes remain on: {relative}")
        payload = path.read_bytes().lower()
        if any(token in payload for token in forbidden_tokens()):
            raise AssertionError(f"private path or credential marker in: {relative}")
        if path.suffix == ".json":
            json.loads(path.read_text())

    observed = {
        str(path.relative_to(HERE))
        for path in HERE.rglob("*")
        if path.is_file()
    }
    expected = set(PUBLIC_FILES)
    if OUTPUT.exists():
        expected.add(OUTPUT.name)
    if observed != expected:
        raise AssertionError(
            f"directory is not publication-closed: extra={sorted(observed-expected)}, "
            f"missing={sorted(expected-observed)}"
        )
    if json.loads((HERE / "replay_receipt.json").read_text()) != build_receipt():
        raise AssertionError("replay_receipt.json is stale")


def main() -> int:
    validate_allowlist()
    fixture = json.loads((HERE / "derived_inputs.json").read_text())
    entries = [
        {
            "path": relative,
            "bytes": (HERE / relative).stat().st_size,
            "sha256": sha256_file(HERE / relative),
        }
        for relative in PUBLIC_FILES
    ]
    private_sources = [
        {
            "logical_id": record["logical_id"],
            "sha256": record["sha256"],
            "included": False,
            "license_id": "NOASSERTION",
        }
        for record in fixture["private_source_provenance"]
    ]
    manifest = {
        "schema": "heilbronn-gamma-monodromy-publication-v1",
        "bundle_id": BUNDLE_ID,
        "claim_scope": {
            "problem": "heilbronn-triangles",
            "n": 11,
            "status": "BOUNDED_NO_CANDIDATE",
            "complete_root_enumeration": False,
            "global_upper_bound": False,
            "legal_gate_clearers": 0,
        },
        "files": entries,
        "include_policy": (
            "Publish exactly the listed regular files plus this manifest envelope. "
            "The manifest omits its own hash; report a detached SHA-256 after freezing."
        ),
        "excluded": [
            {"pattern": "PUBLICATION_MANIFEST.json:self-hash", "reason": "self-reference omitted"},
            {"pattern": "MANIFEST.json", "reason": "obsolete host-bound manifest removed"},
            {"pattern": "__pycache__/** and *.pyc", "reason": "generated bytecode"},
            {"pattern": ".venv/**", "reason": "runtime packages are not vendored"},
            {"pattern": ".publication-selftest-*/**", "reason": "ephemeral copied-layout test trees"},
            {"pattern": "raw private run/corpus/seed inputs", "reason": "hash-only provenance"},
            {"pattern": ".DS_Store, ._* and extended attributes", "reason": "platform metadata"},
            {"pattern": "all paths not listed in files", "reason": "deny-by-default allowlist"},
        ],
        "license": {
            "manifest_envelope_license_id": "MIT",
            "first_party_license_file": "LICENSE",
            "classes": LICENSE_CLASSES,
        },
        "provenance": {
            "excluded_private_sources": private_sources,
            "private_source_bytes_included": False,
            "prepublication_target_manifest_sha256": (
                "73eeb34b478c50cd468011812c83e267987f51a2889079ef56a5a29108f06e50"
            ),
            "transformations": [
                {
                    "id": "portable-derived-fixture",
                    "description": (
                        "Solver-refined active root plus integer projection of 619 "
                        "unresolved exchange records; no verbatim private rows."
                    ),
                    "output": "derived_inputs.json",
                },
                {
                    "id": "portable-target-audit",
                    "description": (
                        "Recompute all target bounds, symmetry orbits, and status aggregates "
                        "from derived_inputs.json."
                    ),
                    "output": "target_manifest.json",
                },
                {
                    "id": "stdlib-public-replay",
                    "description": (
                        "Recompute stored polynomial residuals, domain filters, root "
                        "separation, symmetry counts, and exact-rational Krawczyk inclusion."
                    ),
                    "output": "replay_receipt.json",
                },
            ],
            "historical_generation_environment": {
                "python": "CPython 3.12.13",
                "numpy": "2.5.2",
                "mpmath": "1.3.0",
                "platform": "macOS 26.5.1 arm64",
                "numpy_linear_algebra_backend": "Apple Accelerate",
            },
        },
        "runtime": {
            "public_replay": {
                "python": ">=3.9",
                "third_party_packages": [],
                "network": False,
                "writes": False,
            },
            "optional_scientific_generation": {
                "requirements_file": "requirements.txt",
                "packages_vendored": False,
                "byte_reproducible": False,
            },
        },
        "layouts": [CAMPAIGN_LAYOUT, SRC_LAYOUT],
        "entrypoints": [
            {
                "name": "campaign_replay",
                "argv": ["python3", "-B", f"{CAMPAIGN_LAYOUT}/public_replay.py"],
                "network": False,
                "writes": False,
                "expected_exit": 0,
            },
            {
                "name": "src_campaign_replay",
                "argv": ["python3", "-B", f"{SRC_LAYOUT}/public_replay.py"],
                "network": False,
                "writes": False,
                "expected_exit": 0,
            },
            {
                "name": "campaign_copied_allowlist_selftest",
                "argv": ["python3", "-B", f"{CAMPAIGN_LAYOUT}/publication_selftest.py"],
                "network": False,
                "writes": True,
                "write_scope": "ephemeral subtree beside packet; removed before exit",
                "expected_exit": 0,
            },
            {
                "name": "src_campaign_copied_allowlist_selftest",
                "argv": ["python3", "-B", f"{SRC_LAYOUT}/publication_selftest.py"],
                "network": False,
                "writes": True,
                "write_scope": "ephemeral subtree beside packet; removed before exit",
                "expected_exit": 0,
            },
        ],
        "network_required": False,
        "external_inputs_required_for_public_replay": [],
        "third_party_source_bytes_included": False,
        "machine_absolute_paths_included": False,
        "external_writes": [],
    }
    encoded = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    temporary = OUTPUT.with_name(f".{OUTPUT.name}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, OUTPUT)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"files": len(entries), "output": OUTPUT.name}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
