#!/usr/bin/env python3
"""Build or check the coordinate-free publication receipt and allowlist.

Default operation is read-only. Pass --write explicitly to replace the two
generated JSON files. `--help` therefore cannot mutate the packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/20260815T105000Z-c540-descendants-v2"
FROZEN_AT = "2026-08-15T10:50:00Z"
INCLUDE = (
    ".gitignore",
    "HANDOFF.md",
    "LICENSE",
    "PROVENANCE.md",
    "README.md",
    "freeze_publication.py",
    "replay_exact.py",
    "requirements.txt",
    "search.py",
    "test_packet.py",
    "receipt.json",
)


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_atomic(path: Path, raw: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def build_receipt() -> dict[str, object]:
    replay = json.loads((RUN / "independent_replay.json").read_text(encoding="utf-8"))
    summary = json.loads((RUN / "summary.json").read_text(encoding="utf-8"))
    if replay["status"] != "pass" or replay["gate_clearer"]:
        raise ValueError("private replay does not describe the expected no-go")
    if replay["summary_sha256"] != sha256_file(RUN / "summary.json"):
        raise ValueError("private summary hash mismatch")
    if replay["events_sha256"] != sha256_file(RUN / "events.jsonl"):
        raise ValueError("private events hash mismatch")
    if replay["best_sha256"] != sha256_file(RUN / "best.json"):
        raise ValueError("private best hash mismatch")
    return {
        "schema_version": 1,
        "status": "frozen_quantified_no_go",
        "frozen_at": FROZEN_AT,
        "problem": {
            "slug": "thomson-problem",
            "n": 282,
            "scoring": "minimize",
            "leader": replay["leader"],
            "minimum_improvement": replay["minimum_improvement"],
            "target_at_or_below": replay["strict_target_at_or_below"],
            "verifier_sha256": replay["frozen_verifier_sha256"],
            "verifier_executed_on_host": False,
        },
        "scope": {
            "source_graph_count": replay["source_graph_count"],
            "trial_count": replay["trial_count"],
            "description": replay["source_graph_scope"],
            "source_graph_invariants": replay["source_graph_invariants"],
            "not_complete_c560_enumeration": True,
        },
        "result": {
            "source_retaining_count": replay["source_retaining_count"],
            "defect_free_final_count": replay["defect_free_final_count"],
            "distinct_final_exact_isomorphism_class_count": replay[
                "distinct_final_exact_isomorphism_class_count"
            ],
            "best_all": replay["best_all"],
            "best_all_gate_gap": replay["best_all_gate_gap"],
            "best_defect_free": replay["best_defect_free"],
            "best_defect_free_gate_gap": replay["best_defect_free_gate_gap"],
            "best_source_retaining": replay["best_source_retaining"],
            "best_source_retaining_gate_gap": replay[
                "best_source_retaining_gate_gap"
            ],
            "gate_clearer": False,
            "clamps_active": replay["clamps_active"],
            "maximum_candidate_norm_error": replay[
                "maximum_candidate_norm_error"
            ],
            "minimum_candidate_pair_distance": replay[
                "minimum_candidate_pair_distance"
            ],
            "maximum_recorded_score_delta": replay[
                "maximum_recorded_score_delta"
            ],
            "maximum_initial_score_delta": replay[
                "maximum_initial_score_delta"
            ],
        },
        "integrity": {
            "search_sha256": summary["search_sha256"],
            "replay_source_sha256": sha256_file(HERE / "replay_exact.py"),
            "events_sha256": replay["events_sha256"],
            "summary_sha256": replay["summary_sha256"],
            "best_payload_sha256": replay["best_sha256"],
            "independent_replay_sha256": sha256_file(
                RUN / "independent_replay.json"
            ),
            "prior_topology_summary_sha256": replay["prior_summary_sha256"],
            "input_graph_hashes": replay["input_manifest"],
            "networkx_version": replay["networkx_version"],
        },
        "research_routing": {
            "paperclip_document": "arx_1508.02878",
            "paperclip_lines": ["L24-L26", "L56-L59"],
            "exa_request_ids": [
                "192a855674e408bae177eb19607c7deb",
                "1fe873b3e6c2e82548027962b62db0fb",
            ],
            "response_bodies_retained": False,
        },
        "publication_boundary": {
            "candidate_coordinates_included": False,
            "private_graph_bytes_included": False,
            "third_party_source_or_binary_bytes_included": False,
            "frozen_verifier_bytes_included": False,
            "public_claim": (
                "coordinate-free metadata and authored methods for a bounded "
                "negative frontier; not a standalone numerical reproduction"
            ),
        },
    }


def file_entry(path: str, receipt_raw: bytes) -> dict[str, object]:
    if path == "receipt.json":
        raw = receipt_raw
    else:
        raw = (HERE / path).read_bytes()
    return {"path": path, "sha256": sha256_bytes(raw), "bytes": len(raw)}


def build_manifest(receipt_raw: bytes) -> dict[str, object]:
    return {
        "schema_version": 1,
        "packet": "thomson-c560-distant-pentagon-v2",
        "frozen_at": FROZEN_AT,
        "policy": "default deny; publish only the exact include list",
        "include": [file_entry(path, receipt_raw) for path in INCLUDE],
        "exclude": [
            {"path": "private_inputs/**", "reason": "private graph outputs"},
            {"path": "runs/**", "reason": "candidate coordinates and raw logs"},
            {"path": "private_generator/**", "reason": "GPL research inputs/tools"},
            {"path": "__pycache__/**", "reason": "generated interpreter cache"},
            {"path": "*.pyc", "reason": "generated interpreter cache"},
            {"path": "*.tmp", "reason": "incomplete atomic write"},
        ],
        "license": {
            "identifier": "MIT",
            "copyright": "Copyright (c) 2026 James Weatherhead",
            "third_party_bytes_included": False,
        },
        "result": {
            "gate_clearer": False,
            "best_score": 37148.1301703428,
            "target_at_or_below": 37147.29441746226,
        },
        "manifest_self_hash": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="atomically replace receipt.json and PUBLICATION_MANIFEST.json",
    )
    parser.add_argument(
        "--private-check",
        action="store_true",
        help="rebuild expected bytes from excluded private evidence without writing",
    )
    args = parser.parse_args()

    receipt_path = HERE / "receipt.json"
    manifest_path = HERE / "PUBLICATION_MANIFEST.json"
    if not args.write and not args.private_check:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["include"]:
            path = HERE / entry["path"]
            if path.stat().st_size != entry["bytes"]:
                raise ValueError(f"allowlisted size mismatch: {path}")
            if sha256_file(path) != entry["sha256"]:
                raise ValueError(f"allowlisted hash mismatch: {path}")
        print(f"receipt_sha256={sha256_file(receipt_path)}")
        print(f"manifest_sha256={sha256_file(manifest_path)}")
        return 0

    receipt_raw = canonical_bytes(build_receipt())
    manifest_raw = canonical_bytes(build_manifest(receipt_raw))
    if args.write:
        write_atomic(receipt_path, receipt_raw)
        write_atomic(manifest_path, manifest_raw)
        print(f"receipt_sha256={sha256_bytes(receipt_raw)}")
        print(f"manifest_sha256={sha256_bytes(manifest_raw)}")
        return 0

    if receipt_path.read_bytes() != receipt_raw:
        raise ValueError("receipt.json is stale; inspect and rerun with --write")
    if manifest_path.read_bytes() != manifest_raw:
        raise ValueError("PUBLICATION_MANIFEST.json is stale; inspect and rerun with --write")
    print(f"receipt_sha256={sha256_bytes(receipt_raw)}")
    print(f"manifest_sha256={sha256_bytes(manifest_raw)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
