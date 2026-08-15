#!/usr/bin/env python3
"""Deterministically freeze the C3 receipt and exact publication manifest."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
RUN = HERE / "runs/20260815T124000Z"

ROLES: dict[str, tuple[str, str]] = {
    ".gitignore": ("publication hygiene", "first-party-mit"),
    "HANDOFF.md": ("bounded decision and migration boundary", "first-party-mit"),
    "LICENSE": ("MIT grant for first-party material", "first-party-mit"),
    "PROVENANCE_AND_RIGHTS.md": ("clean-room and rights boundary", "first-party-mit"),
    "README.md": ("overview and reproduction", "first-party-mit"),
    "audit_corpus.py": ("clean-room frozen-corpus metadata audit", "first-party-mit"),
    "corpus_audit.json": ("minimized factual corpus audit", "factual-noassertion"),
    "fourier_dual_newton.py": ("clean-room bounded numerical probes", "first-party-mit"),
    "freeze_receipt.py": ("deterministic receipt and manifest freezer", "first-party-mit"),
    "literature.json": ("bibliographic facts and provenance links", "bibliographic-noassertion"),
    "publication_selftest.py": ("standard-library manifest/privacy self-test", "first-party-mit"),
    "replay.py": ("portable event-log and optional private-input replay", "first-party-mit"),
    "requirements.txt": ("reference numerical dependencies", "first-party-mit"),
    "runs/20260815T124000Z/config.json": ("factual frozen run configuration", "factual-noassertion"),
    "runs/20260815T124000Z/events.jsonl": ("factual append-only probe events", "factual-noassertion"),
    "runs/20260815T124000Z/summary.json": ("factual bounded-run summary", "factual-noassertion"),
    "test_packet.py": ("numerical unit tests", "first-party-mit"),
    "test_publication.py": ("copied-allowlist dual-layout test", "first-party-mit"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def file_map() -> dict[str, str]:
    missing = [relative for relative in ROLES if not (HERE / relative).is_file()]
    if missing:
        raise RuntimeError(f"publication files missing: {missing}")
    return {relative: sha256_file(HERE / relative) for relative in sorted(ROLES)}


def main() -> int:
    summary = json.loads((RUN / "summary.json").read_text(encoding="utf-8"))
    config = json.loads((RUN / "config.json").read_text(encoding="utf-8"))
    corpus = json.loads((HERE / "corpus_audit.json").read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in (RUN / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    if summary["gate_cleared"]:
        raise RuntimeError("no-gate receipt cannot freeze a gate-clearing result")
    if summary["source_sha256"] != sha256_file(HERE / "fourier_dual_newton.py"):
        raise RuntimeError("frozen summary does not authenticate the published search source")
    if summary["config_sha256"] != sha256_file(RUN / "config.json"):
        raise RuntimeError("frozen config hash drift")
    if summary["events_sha256"] != sha256_file(RUN / "events.jsonl"):
        raise RuntimeError("frozen event hash drift")

    publication_files = file_map()
    receipt = {
        "schema": 2,
        "status": "bounded_no_gate",
        "problem": "third-autocorrelation-inequality",
        "verifier_sha256": config["verifier_sha256"],
        "baseline": {
            "path": config["input"],
            "artifact_sha256": config["input_artifact_sha256"],
            "values_float64_sha256": config["input_values_float64_sha256"],
            "official_score": config["official_baseline_score"],
            "n": config["n"],
        },
        "gate": {
            "leader": config["live_leader"],
            "minimum_improvement": config["minimum_improvement"],
            "strict_target": summary["strict_target"],
            "remaining_gap": summary["remaining_gate_gap"],
        },
        "bounded_search": {
            "cap_projection_trials": summary["cap_projection_trials"],
            "fourier_branch_candidates": summary["fourier_branch_candidates"],
            "newton_systems": summary["newton_systems"],
            "best_fft_screen_gain": summary["best_fft_screen_gain"],
            "maximum_newton_fft_gain": summary["maximum_newton_fft_gain"],
            "gate_cleared": False,
            "claim_limit": (
                "Deterministic FFT proposal screens only: not an optimality or "
                "stationarity certificate and not an official-verifier improvement."
            ),
        },
        "deterministic_rerun": {
            "event_rows": len(events),
            "config_sha256": summary["config_sha256"],
            "events_sha256": summary["events_sha256"],
            "summary_sha256": sha256_file(RUN / "summary.json"),
            "source_sha256": summary["source_sha256"],
        },
        "corpus": corpus["corpus"],
        "privacy": {
            "candidate_payloads_included": False,
            "third_party_coefficient_values_included": 0,
            "discussion_bodies_included": 0,
            "construction_author_labels_included": 0,
            "construction_timestamps_included": 0,
            "credentials_or_host_private_paths_included": False,
        },
        "external_mutations": [],
        "publication_files": publication_files,
        "reproduction_commands": {
            "portable_campaign_replay": "python3 -B campaign/analytic/c3_fourier_dual_newton/replay.py",
            "portable_src_campaign_replay": "python3 -B src/campaign/analytic/c3_fourier_dual_newton/replay.py",
            "campaign_copied_allowlist_test": "python3 -B campaign/analytic/c3_fourier_dual_newton/test_publication.py",
            "src_campaign_copied_allowlist_test": "python3 -B src/campaign/analytic/c3_fourier_dual_newton/test_publication.py",
            "private_input_replay": "python3 -B campaign/analytic/c3_fourier_dual_newton/replay.py --with-private-input",
        },
    }
    atomic_json(HERE / "receipt.json", receipt)

    rows = []
    for relative, (role, license_class) in ROLES.items():
        path = HERE / relative
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "role": role,
                "license_class": license_class,
            }
        )
    receipt_path = HERE / "receipt.json"
    rows.append(
        {
            "path": "receipt.json",
            "bytes": receipt_path.stat().st_size,
            "sha256": sha256_file(receipt_path),
            "role": "factual publication receipt",
            "license_class": "factual-noassertion",
        }
    )
    rows.sort(key=lambda row: row["path"])
    tree_material = [
        {"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"]}
        for row in rows
    ]
    latest = CAMPAIGN / "research_corpus/latest.json"
    manifest = {
        "schema": "einstein-arena-publication-manifest-v1",
        "bundle_id": "c3-fourier-dual-newton-20260815T124000Z",
        "classification": "public-safe-text-only-bounded-no-gate-not-a-candidate",
        "include_policy": "deny-by-default exact regular-file allowlist",
        "manifest_self_authentication": "self-hash omitted; report detached SHA-256 after freezing",
        "payload_tree_sha256": sha256_json(tree_material),
        "layouts": [
            "campaign/analytic/c3_fourier_dual_newton",
            "src/campaign/analytic/c3_fourier_dual_newton",
        ],
        "files": rows,
        "excluded": [
            {"pattern": "PUBLICATION_MANIFEST.json:self-hash", "reason": "self-reference omitted"},
            {"pattern": "all unlisted paths", "reason": "deny-by-default allowlist"},
            {"pattern": "__pycache__/** and *.py[cod]", "reason": "generated bytecode"},
            {"pattern": ".publication-selftest-*/**", "reason": "ephemeral copied-layout tests"},
            {"pattern": "*.npy, *.npz, *.pt, *.pth", "reason": "candidate/checkpoint payloads excluded"},
            {"pattern": "*.sqlite, *.sqlite3, *.db", "reason": "source corpus database excluded"},
            {"pattern": "hash-pinned verifier source", "reason": "recorded by SHA-256 only"},
            {"pattern": "credentials, environment dumps, host-private paths", "reason": "private material"},
        ],
        "entrypoints": [
            {
                "name": "campaign_portable_replay",
                "argv": ["python3", "-B", "campaign/analytic/c3_fourier_dual_newton/replay.py"],
                "network": False,
                "persistent_writes": False,
                "expected_exit": 0,
            },
            {
                "name": "src_campaign_portable_replay",
                "argv": ["python3", "-B", "src/campaign/analytic/c3_fourier_dual_newton/replay.py"],
                "network": False,
                "persistent_writes": False,
                "expected_exit": 0,
            },
            {
                "name": "dual_layout_copied_allowlist_test",
                "argv": ["python3", "-B", "campaign/analytic/c3_fourier_dual_newton/test_publication.py"],
                "network": False,
                "persistent_writes": False,
                "ephemeral_write_scope": "system temporary directory, removed before exit",
                "expected_exit": 0,
            },
        ],
        "external_inputs_required_for_portable_replay": [],
        "external_inputs_required_for_full_numerical_reproduction": [
            {
                "kind": "baseline_candidate_array",
                "path_relative_to_campaign": config["input"],
                "sha256": config["input_artifact_sha256"],
                "included": False,
            },
            {
                "kind": "verifier_source",
                "path_relative_to_campaign": (
                    "state/problems/third-autocorrelation-inequality/"
                    f"{config['verifier_sha256']}.py"
                ),
                "sha256": config["verifier_sha256"],
                "included": False,
            },
            {
                "kind": "frozen_corpus_database",
                "path_relative_to_campaign": corpus["corpus"]["database"],
                "sha256": corpus["corpus"]["database_sha256"],
                "included": False,
            },
            {
                "kind": "frozen_corpus_pointer",
                "path_relative_to_campaign": "research_corpus/latest.json",
                "sha256": sha256_file(latest),
                "included": False,
            },
        ],
        "policy": {
            "arena_verifier_executed_by_lane": False,
            "arena_submission_attempted": False,
            "candidate_payloads_included": False,
            "third_party_candidate_bytes_included": False,
            "verifier_source_included": False,
            "corpus_database_included": False,
            "network_required_for_portable_replay": False,
            "external_persistent_writes": [],
        },
        "license": {
            "first-party-mit": {
                "license_id": "MIT",
                "license_path": "LICENSE",
                "description": "campaign-authored source and documentation",
            },
            "factual-noassertion": {
                "license_id": "NOASSERTION",
                "description": "factual hashes, public identifiers, aggregate features, and numerical receipts",
            },
            "bibliographic-noassertion": {
                "license_id": "NOASSERTION",
                "description": "bibliographic facts, links, request IDs, and scope notes only",
            },
            "dependencies_vendored": False,
        },
        "reference_environment": {
            "python": "3.12.13",
            "numpy": "2.5.2",
            "scipy": "1.18.0",
            "requirements": "requirements.txt",
        },
        "external_writes": [],
    }
    atomic_json(HERE / "PUBLICATION_MANIFEST.json", manifest)
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "manifest_files": len(rows),
                "payload_tree_sha256": manifest["payload_tree_sha256"],
                "manifest_sha256": sha256_file(HERE / "PUBLICATION_MANIFEST.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
