#!/usr/bin/env python3
"""Replay the frozen C3 asset receipt without network access."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import asset_replay as audit


def require_equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> int:
    receipt = json.loads(audit.RECEIPT.read_text())
    verifier = audit.load_verifier()

    require_equal(
        audit.sha256(audit.CORPUS.read_bytes()),
        receipt["frozen_arena_corpus"]["sha256"],
        "corpus sha256",
    )
    rows, _ = audit.corpus_rows()
    require_equal(
        len(rows), receipt["frozen_arena_corpus"]["c3_rows_checked"], "C3 row count"
    )

    artifact_groups = (
        "construction_sources",
        "program_artifacts",
        "license_artifacts",
    )
    checked_artifacts = 0
    for group in artifact_groups:
        for name, record in receipt[group].items():
            path = audit.REPO / record["cache_path"]
            require_equal(audit.sha256(path.read_bytes()), record["sha256"], f"{name} sha256")
            checked_artifacts += 1

    hyra_cache = audit.CACHE / "hyra-tree.json"
    hyra = json.loads(hyra_cache.read_text())
    canonical = json.dumps(hyra, sort_keys=True, separators=(",", ":")).encode()
    require_equal(
        audit.sha256(canonical),
        receipt["hyra_inventory"]["tree_canonical_sha256"],
        "Hyra tree canonical sha256",
    )
    require_equal(
        audit.sha256((audit.CACHE / "LICENSE-Hyra-results").read_bytes()),
        audit.HYRA_LICENSE_SHA256,
        "Hyra license sha256",
    )

    checked_payloads = 0
    for record in receipt["constructions"]:
        path = audit.REPO / record["payload_path"]
        require_equal(
            audit.sha256(path.read_bytes()),
            record["payload_file_sha256"],
            f"{record['label']} payload sha256",
        )
        values = np.load(path, allow_pickle=False).astype(np.float64)
        require_equal(
            audit.sha256(np.ascontiguousarray(values).tobytes()),
            record["values_sha256"],
            f"{record['label']} values sha256",
        )
        score = float(verifier.evaluate({"values": values.tolist()}))
        require_equal(score, record["score"], f"{record['label']} score")
        checked_payloads += 1

    frontier = np.load(audit.LOCAL_FRONTIER, allow_pickle=False).astype(np.float64)
    require_equal(
        audit.sha256(audit.LOCAL_FRONTIER.read_bytes()),
        receipt["frontier"]["local_file_sha256"],
        "frontier file sha256",
    )
    require_equal(
        float(verifier.evaluate({"values": frontier.tolist()})),
        receipt["frontier"]["local_score"],
        "frontier score",
    )

    summary = {
        "status": "ok",
        "network_used": False,
        "artifacts_checked": checked_artifacts + 2,
        "payloads_checked": checked_payloads,
        "c3_corpus_rows_checked": len(rows),
        "best_new_distinct": receipt["best_new_distinct"],
        "best_new_gap_to_local_frontier": receipt["best_new_gap_to_local_frontier"],
        "topology_transfer": receipt["topology_transfer"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
