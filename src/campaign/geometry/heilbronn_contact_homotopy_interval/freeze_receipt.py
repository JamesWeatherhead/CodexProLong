#!/usr/bin/env python3
"""Verify or explicitly freeze a compact receipt and public allowlist."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIRECT = HERE / "runs/20260815T111000Z-distant-exchange-v2"
PSEUDO = HERE / "runs/20260815T111000Z-pseudo-v1"
ALLOWLIST = (
    ".gitignore",
    "README.md",
    "HANDOFF.md",
    "requirements.txt",
    "literature.json",
    "contact_homotopy.py",
    "pseudo_arclength.py",
    "replay.py",
    "public_replay.py",
    "freeze_receipt.py",
    "receipt.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> object:
    return json.loads(path.read_text())


def rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def encode(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def atomic_write(path: Path, data: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(HERE, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--write",
        action="store_true",
        help="atomically write the recomputed receipt and manifest",
    )
    actions.add_argument(
        "--private-check",
        action="store_true",
        help="recompute from excluded canonical runs without writing",
    )
    return parser.parse_args()


def run_record(run: Path) -> dict[str, object]:
    summary = load(run / "summary.json")
    replay = load(run / "independent_replay.json")
    assert isinstance(summary, dict) and isinstance(replay, dict)
    assert replay["status"] == "PASS"
    replay = dict(replay)
    replay["run"] = str(run.relative_to(HERE))
    files = {}
    for name in (
        "config.json",
        "events.jsonl",
        "results.jsonl",
        "polish.jsonl",
        "summary.json",
        "best.json",
        "independent_replay.json",
    ):
        path = run / name
        if path.exists():
            files[name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    return {
        "run": str(run.relative_to(HERE)),
        "summary": summary,
        "independent_replay": replay,
        "files": files,
    }


def build_packet() -> tuple[dict[str, object], dict[str, object]]:
    direct_rows = rows(DIRECT / "results.jsonl")
    pseudo_rows = rows(PSEUDO / "results.jsonl")
    polish_rows = rows(DIRECT / "polish.jsonl")
    direct_complete = [row for row in direct_rows if row["status"] == "complete"]
    direct_domain = [row for row in direct_complete if row["intended_domain"]]
    pseudo_complete = [row for row in pseudo_rows if row["status"] == "complete"]
    best_domain = max(direct_domain, key=lambda row: float(row["score"]))
    maximum_direct = max(direct_complete, key=lambda row: float(row["score"]))
    maximum_pseudo = max(pseudo_complete, key=lambda row: float(row["score"]))
    receipt = {
        "schema": "heilbronn-distant-contact-homotopy-receipt-v1",
        "generated_at": load(PSEUDO / "summary.json")["completed_at"],
        "problem": "heilbronn-triangles",
        "n": 11,
        "direction": "maximize",
        "live_leader": 0.036529889880030156,
        "strict_gate": 0.036529890880030155,
        "verifier_sha256": "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d",
        "corpus": {
            "database_sha256": "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb",
            "solutions_read": 17,
            "threads_read": 4,
            "replies_read": 23,
            "all_heilbronn_handoffs_read": True,
        },
        "scope": {
            "active_triples": 17,
            "all_inactive_triples": 148,
            "excluded_prior_low_area_pool": 58,
            "excluded_prior_inactive_triples": 41,
            "distant_inactive_triples": 107,
            "labelled_exchange_tasks": 1819,
            "homotopy": "(1-t)*(signed_det_out-z)-t*(signed_det_in-z)=0",
            "preserved_equalities_per_task": "16 triangle + 6 boundary",
        },
        "direct": {
            "status_counts": dict(Counter(str(row["status"]) for row in direct_rows)),
            "domain_valid_endpoints": len(direct_domain),
            "best_domain_endpoint": {
                key: best_domain[key]
                for key in (
                    "task_id",
                    "outgoing",
                    "incoming",
                    "score",
                    "system_z",
                    "minimum_domain_slack",
                    "endpoint_sha256",
                )
            },
            "maximum_score_any_endpoint": {
                key: maximum_direct[key]
                for key in (
                    "task_id",
                    "outgoing",
                    "incoming",
                    "score",
                    "system_z",
                    "minimum_domain_slack",
                    "intended_domain",
                    "endpoint_sha256",
                )
            },
            "polished_count": len(polish_rows),
            "polished_successes": sum(bool(row["success"]) for row in polish_rows),
            "polished_incumbent_basin_count_at_0_0365": sum(
                float(row["score"]) >= 0.0365 for row in polish_rows
            ),
            "best_polished_score": max(float(row["score"]) for row in polish_rows),
            "best_distinct_polished_score_below_0_0365": max(
                float(row["score"]) for row in polish_rows if float(row["score"]) < 0.0365
            ),
            "gate_clearers": 0,
        },
        "pseudo_arclength": {
            "status_counts": dict(Counter(str(row["status"]) for row in pseudo_rows)),
            "paths_with_folds": sum(int(row.get("folds", 0)) > 0 for row in pseudo_rows),
            "detected_folds": sum(int(row.get("folds", 0)) for row in pseudo_rows),
            "recovered_endpoints": len(pseudo_complete),
            "domain_valid_endpoints": sum(bool(row["intended_domain"]) for row in pseudo_complete),
            "maximum_score_any_endpoint": {
                key: maximum_pseudo[key]
                for key in (
                    "task_id",
                    "source_task_id",
                    "outgoing",
                    "incoming",
                    "score",
                    "system_z",
                    "minimum_domain_slack",
                    "intended_domain",
                    "endpoint_sha256",
                    "folds",
                )
            },
            "gate_clearers": 0,
        },
        "combined": {
            "endpoint_roots_reached": len(direct_complete) + len(pseudo_complete),
            "bounded_branches_explored": len(direct_rows),
            "paths_unresolved_past_caps": len(pseudo_rows) - len(pseudo_complete),
            "best_candidate_is_unchanged_incumbent": True,
            "new_candidate": False,
            "controller_verify_called": False,
            "external_actions": [],
        },
        "literature": load(HERE / "literature.json"),
        "runs": [run_record(DIRECT), run_record(PSEUDO)],
        "superseded_exclusions": [
            "runs/SMOKE",
            "runs/PSEUDO_SMOKE",
            "runs/20260815T110500Z-distant-exchange",
        ],
        "scope_caveat": (
            "The result is a bounded real-path census, not a complex-path/root "
            "enumeration, interval proof of path completeness, or global upper bound."
        ),
        "next_route": (
            "Complex gamma-homotopy/monodromy enumeration of isolated target roots "
            "followed by real/domain filtering and interval Krawczyk certification; "
            "otherwise proof-producing barycentric MIQCP/interval branch-and-bound "
            "with orientation-count constraints."
        ),
    }
    receipt_bytes = encode(receipt)
    manifest_files = {}
    for relative in ALLOWLIST:
        path = HERE / relative
        if relative == "receipt.json":
            manifest_files[relative] = {
                "bytes": len(receipt_bytes),
                "sha256": sha256_bytes(receipt_bytes),
            }
        else:
            manifest_files[relative] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    manifest = {
        "schema": "heilbronn-distant-contact-publication-manifest-v1",
        "generated_at": receipt["generated_at"],
        "include": manifest_files,
        "exclude": ["runs/**", "__pycache__/**", "*.pyc"],
        "raw_coordinates_included": False,
        "third_party_source_included": False,
        "external_writes": [],
    }
    return receipt, manifest


def validate_public_packet() -> tuple[dict[str, object], dict[str, object]]:
    receipt_path = HERE / "receipt.json"
    manifest_path = HERE / "PUBLICATION_MANIFEST.json"
    receipt = load(receipt_path)
    manifest = load(manifest_path)
    assert isinstance(receipt, dict) and isinstance(manifest, dict)
    if (
        receipt.get("schema") != "heilbronn-distant-contact-homotopy-receipt-v1"
        or manifest.get("schema")
        != "heilbronn-distant-contact-publication-manifest-v1"
    ):
        raise RuntimeError("publication envelope mismatch")
    include = manifest.get("include")
    if not isinstance(include, dict) or set(include) != set(ALLOWLIST):
        raise RuntimeError("publication allowlist mismatch")
    for relative, metadata in include.items():
        path = HERE / relative
        if (
            not path.is_file()
            or not isinstance(metadata, dict)
            or path.stat().st_size != metadata.get("bytes")
            or sha256(path) != metadata.get("sha256")
        ):
            raise RuntimeError(f"publication hash mismatch: {relative}")
    observed = {
        str(path.relative_to(HERE))
        for path in HERE.rglob("*")
        if path.is_file()
        and "runs" not in path.relative_to(HERE).parts
        and "__pycache__" not in path.relative_to(HERE).parts
        and path.suffix != ".pyc"
        and path.name != "PUBLICATION_EXPORT.json"
    }
    expected = set(ALLOWLIST) | {"PUBLICATION_MANIFEST.json"}
    if observed != expected:
        raise RuntimeError(
            f"publication file-set mismatch: extra={sorted(observed-expected)}, "
            f"missing={sorted(expected-observed)}"
        )
    return receipt, manifest


def main() -> int:
    args = parse_args()
    if args.write or args.private_check:
        receipt, manifest = build_packet()
        receipt_bytes = encode(receipt)
        manifest_bytes = encode(manifest)
        receipt_path = HERE / "receipt.json"
        manifest_path = HERE / "PUBLICATION_MANIFEST.json"
        if args.write:
            atomic_write(receipt_path, receipt_bytes)
            atomic_write(manifest_path, manifest_bytes)
        else:
            if receipt_path.read_bytes() != receipt_bytes:
                raise RuntimeError("receipt.json differs from private recomputation")
            if manifest_path.read_bytes() != manifest_bytes:
                raise RuntimeError("manifest differs from private recomputation")
    else:
        receipt, manifest = validate_public_packet()
    print(
        json.dumps(
            {
                "receipt_sha256": sha256(HERE / "receipt.json"),
                "manifest": manifest,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
