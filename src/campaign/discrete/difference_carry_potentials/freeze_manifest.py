#!/usr/bin/env python3
"""Normalize and freeze the portable publication packet as the final step."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from solver import (
    ROOT,
    atomic_write,
    canonical_bytes,
    sha256_bytes,
    sha256_file,
    write_json,
)


PACKET_RELPATH = "campaign/discrete/difference_carry_potentials"
RUN_RELPATH = "runs/20260815T121057Z"
RUN = ROOT / RUN_RELPATH
ALLOWLIST = [
    "LICENSE",
    "README.md",
    "HANDOFF.md",
    "PROVENANCE.md",
    "EXA_PROVENANCE.json",
    "audit.py",
    "cleanroom_replay.py",
    "copied_allowlist_test.py",
    "freeze_manifest.py",
    "frozen_inputs.json",
    "solver.py",
    "test_packet.py",
    "test_solver.py",
    f"{RUN_RELPATH}/audit.json",
    f"{RUN_RELPATH}/checkpoint.json",
    f"{RUN_RELPATH}/cleanroom_replay.json",
    f"{RUN_RELPATH}/config.json",
    f"{RUN_RELPATH}/events.jsonl",
    f"{RUN_RELPATH}/manifest.json",
    f"{RUN_RELPATH}/model.pb",
    f"{RUN_RELPATH}/summary.json",
]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_frozen_journal() -> None:
    """Remove machine-local paths without changing model or solve payload."""

    config_path = RUN / "config.json"
    config = load_json(config_path)
    config["input"] = f"{PACKET_RELPATH}/frozen_inputs.json"
    config["path_encoding"] = "repository-relative"
    config["reproduction_command"] = (
        f".venv/bin/python {PACKET_RELPATH}/solver.py "
        f"--input {PACKET_RELPATH}/frozen_inputs.json "
        f"--seconds {config['seconds']} --seed {config['seed']}"
    )
    write_json(config_path, config)

    events_path = RUN / "events.jsonl"
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(events) != 2 or events[0].get("type") != "config" or events[1].get("type") != "solve":
        raise ValueError("unexpected frozen event journal")
    events[0]["payload"] = config
    previous = "0" * 64
    for sequence, event in enumerate(events, start=1):
        event["sequence"] = sequence
        event["previous_hash"] = previous
        event.pop("hash", None)
        event["hash"] = sha256_bytes(canonical_bytes(event))
        previous = event["hash"]
    atomic_write(
        events_path,
        b"".join(canonical_bytes(event) + b"\n" for event in events)
    )

    checkpoint_path = RUN / "checkpoint.json"
    checkpoint = load_json(checkpoint_path)
    checkpoint["last_event_hash"] = previous
    write_json(checkpoint_path, checkpoint)

    run_files = [
        "checkpoint.json", "config.json", "events.jsonl", "model.pb", "summary.json"
    ]
    run_manifest = {
        "schema": 1,
        "files": {name: sha256_file(RUN / name) for name in run_files},
    }
    write_json(RUN / "manifest.json", run_manifest)

    audit_path = RUN / "audit.json"
    audit = load_json(audit_path)
    audit["run_dir"] = f"{PACKET_RELPATH}/{RUN_RELPATH}"
    audit["path_encoding"] = "repository-relative"
    audit["event_chain"] = {"events": len(events), "last_hash": previous}
    audit["run_manifest_files_verified"] = len(run_files)
    write_json(audit_path, audit)


def license_class(name: str) -> str:
    authored = {
        "LICENSE",
        "README.md",
        "HANDOFF.md",
        "PROVENANCE.md",
        "EXA_PROVENANCE.json",
        "audit.py",
        "cleanroom_replay.py",
        "copied_allowlist_test.py",
        "freeze_manifest.py",
        "solver.py",
        "test_packet.py",
        "test_solver.py",
    }
    if name in authored:
        return "MIT-authored"
    if name == "frozen_inputs.json":
        return "attributed-factual-metadata-no-ownership-claim"
    return "derived-formula-or-run-metadata-no-candidate-array"


def publication_manifest() -> dict[str, Any]:
    missing = [name for name in ALLOWLIST if not (ROOT / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing allowlisted files: {missing}")
    entries = []
    for name in sorted(ALLOWLIST):
        path = ROOT / name
        entries.append(
            {
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "license_class": license_class(name),
            }
        )
    return {
        "schema": "difference-carry-potentials-publication-v2",
        "packet": "difference-carry-potentials",
        "path_encoding": "packet-relative allowlist; embedded run paths are repository-relative",
        "files": entries,
        "entrypoints": {
            "stdlib_integrity": "test_packet.py",
            "independent_exact_replay": "cleanroom_replay.py",
            "copied_layouts": "copied_allowlist_test.py",
        },
        "scope": {
            "ambient_group": "integers",
            "modulus": 8011,
            "cardinality": 360,
            "residue_support": "exactly a global translate of the attributed 90-residue core",
            "height_supports": "arbitrary finite nonempty independent subsets of Z with total size 360; no height bound or common shape",
            "closed_claim": "no set in this family has every positive difference 1..49110",
        },
        "proof_boundary": {
            "necessary_relaxation": "1043 [-6,6] edges plus the unique [-7,5] edge",
            "omitted_constraints": "2961 [-6,5] edges and every residue-zero requirement",
            "solver_result": "INFEASIBLE",
            "certificate_kind": "deterministic CP-SAT formula plus two reconstruction/replay implementations; no DRAT/LRAT certificate",
        },
        "excluded": [
            "PUBLICATION_MANIFEST.json and byte-identical MANIFEST.json alias (self-describing envelope)",
            "__pycache__/ and *.pyc",
            "all files not explicitly listed",
            "all campaign state except factual hashes embedded in frozen_inputs.json",
            "the full public solution payload and every candidate array",
            "verifier source, credentials, corpus snapshot, and discussion bodies",
        ],
        "privacy": {
            "arena_snapshot_included": False,
            "full_public_solution_payload_included": False,
            "candidate_array_included": False,
            "credentials_included": False,
            "verifier_source_included": False,
            "machine_absolute_paths_included": False,
        },
        "license_boundary": {
            "mit_file": "LICENSE",
            "mit_scope": "repository-authored clean-room code and documentation only",
            "derived_core_scope": "attributed factual residue metadata; no ownership or license assertion over Arena API content",
        },
    }


def main() -> None:
    normalize_frozen_journal()
    manifest = publication_manifest()
    write_json(ROOT / "PUBLICATION_MANIFEST.json", manifest)
    write_json(ROOT / "MANIFEST.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
