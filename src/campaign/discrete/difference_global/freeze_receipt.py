#!/usr/bin/env python3
"""Recompute every retained frontier and freeze a compact audit receipt."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from exact import ROOT, atomic_json, load_live, replay
from relative_graph_search import Parameters, construct


REPO = ROOT.parents[2]
OUTPUT = ROOT / "checkpoints" / "audit_receipt.json"
PUBLIC = ROOT / "checkpoints" / "public_latest.json"
RELATIVE = ROOT / "checkpoints" / "relative_graph.json"
PATCH = ROOT / "checkpoints" / "sparse_patch.json"
PATCH_CANDIDATE = ROOT / "candidates" / "sparse_patch_best.json"


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(REPO))


def main() -> int:
    live = load_live()
    public = read(PUBLIC)
    if public["verifier_sha256"] != live["verifier_sha256"]:
        raise RuntimeError("fresh public verifier differs from pinned local verifier")
    if public["counts"] != {
        "leaderboard": 12,
        "solutions": 23,
        "threads": 11,
        "replies": 78,
    }:
        raise RuntimeError("public corpus counts changed; refresh and re-audit")
    public_leader = public["solutions"][0]
    if int(public_leader["id"]) != live["leader_id"]:
        raise RuntimeError("public leader changed")

    relative = read(RELATIVE)
    if not relative["complete"] or relative["verifier_sha256"] != live["verifier_sha256"]:
        raise RuntimeError("relative search is not frozen against the live verifier")
    checked_records = []
    for record in relative["records"]:
        parameters = Parameters.from_dict(record["parameters"])
        result = replay(construct(parameters), live)
        for key in ("coverage", "score", "payload_sha256", "size", "gate_cleared"):
            if result[key] != record[key]:
                raise RuntimeError(f"relative record mismatch for {key}")
        checked_records.append(result)
    raw_best = max(relative["records"], key=lambda item: item["coverage"])
    normalized_best = max(
        relative["records"],
        key=lambda item: Fraction(item["coverage"], item["required_coverage"]),
    )

    patch = read(PATCH)
    candidate = read(PATCH_CANDIDATE)
    if not patch["complete"] or patch["verifier_sha256"] != live["verifier_sha256"]:
        raise RuntimeError("sparse patch is not frozen against the live verifier")
    patch_replay = replay(candidate["payload"]["set"], live)
    for key in ("coverage", "score", "payload_sha256", "size", "gate_cleared"):
        if patch_replay[key] != candidate["receipt"][key]:
            raise RuntimeError(f"sparse-patch candidate mismatch for {key}")
        if patch_replay[key] != patch["best"][key]:
            raise RuntimeError(f"sparse-patch checkpoint mismatch for {key}")

    prior_paths = {
        "one_edit": REPO / "campaign/discrete/checkpoints/difference-search.json",
        "two_swap": REPO / "campaign/discrete/difference_bases/checkpoints/two_swap.json",
        "block_repair": REPO
        / "campaign/discrete/difference_bases/checkpoints/block_repair.json",
    }
    prior = {name: read(path) for name, path in prior_paths.items()}
    if any(not value["complete"] for value in prior.values()):
        raise RuntimeError("a prerequisite local neighborhood audit is incomplete")
    if any(value["verifier_sha256"] != live["verifier_sha256"] for value in prior.values()):
        raise RuntimeError("a prerequisite audit used another verifier")

    source_paths = [
        ROOT / "README.md",
        ROOT / "HANDOFF.md",
        ROOT / "PROVENANCE.md",
        ROOT / "exact.py",
        ROOT / "relative_graph_search.py",
        ROOT / "sparse_patch_search.py",
        ROOT / "refresh_public.py",
        ROOT / "test_exact.py",
        ROOT / "freeze_receipt.py",
        RELATIVE,
        PATCH,
        ROOT / "candidates" / "relative_graph_best.json",
        PATCH_CANDIDATE,
    ]
    receipt = {
        "schema": 1,
        "mode": "local_exact_replay_plus_public_get_only",
        "verifier_sha256": live["verifier_sha256"],
        "leader": {
            "id": live["leader_id"],
            "agent": live["leader_agent"],
            "score": live["leader_score"],
            "score_fraction": "129600/49109",
            "size": 360,
            "coverage": live["leader_coverage"],
            "payload_sha256": live["leader_payload_sha256"],
            "gate_score": live["gate_score"],
        },
        "public_corpus": {
            "fetched_at": public["fetched_at"],
            "counts": public["counts"],
            "snapshot_sha256": digest(PUBLIC),
        },
        "relative_search": {
            "retained_records_replayed": len(checked_records),
            "budgets": relative["budgets"],
            "raw_best": raw_best,
            "size_normalized_best": normalized_best,
            "checkpoint_sha256": digest(RELATIVE),
        },
        "sparse_patch": {
            "children_evaluated": sum(
                int(record.get("children_evaluated", 0)) for record in patch["records"]
            ),
            "depth": candidate["depth"],
            "best": patch["best"],
            "checkpoint_sha256": digest(PATCH),
            "candidate_sha256": digest(PATCH_CANDIDATE),
        },
        "prior_closed_neighborhoods": {
            name: {
                "path": rel(path),
                "sha256": digest(path),
                "gate_cleared": prior[name]["gate_cleared"],
            }
            for name, path in prior_paths.items()
        },
        "publish_safe_artifacts": {
            rel(path): digest(path) for path in source_paths
        },
        "excluded_unlicensed_full_text": [
            rel(PUBLIC),
            rel(ROOT / "snapshots" / "public_20260815T040127Z.json"),
        ],
        "gate_cleared": False,
    }
    atomic_json(OUTPUT, receipt)
    print(OUTPUT)
    print(json.dumps({"sha256": digest(OUTPUT), "gate_cleared": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
