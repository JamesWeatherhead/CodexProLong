#!/usr/bin/env python3
"""Audit structural completeness and content hashes of a corpus snapshot."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


class AuditError(RuntimeError):
    pass


def read_object(root: Path, ref: dict[str, Any], *, verify: bool = True) -> bytes:
    path = root / str(ref["object"])
    with gzip.open(path, "rb") as handle:
        payload = handle.read()
    if verify:
        digest = hashlib.sha256(payload).hexdigest()
        if digest != ref["sha256"]:
            raise AuditError(f"hash mismatch for {path}: {digest} != {ref['sha256']}")
        if len(payload) != int(ref["bytes"]):
            raise AuditError(f"size mismatch for {path}")
    return payload


def read_json(root: Path, ref: dict[str, Any], *, verify: bool = True) -> Any:
    return json.loads(read_object(root, ref, verify=verify))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--skip-raw-object-hashes", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest
    if manifest_path is None:
        latest = json.loads((args.root / "latest.json").read_text(encoding="utf-8"))
        manifest_path = args.root / latest["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify = not args.skip_raw_object_hashes

    if int(manifest.get("schema_version", 0)) != 1:
        raise AuditError("unsupported manifest schema")

    object_refs: dict[str, dict[str, Any]] = {}
    for response in manifest["responses"]:
        object_refs[str(response["object"])] = response
    for problem in manifest["problems"].values():
        object_refs[str(problem["detail_record"]["object"])] = problem["detail_record"]
        for solution in problem["solutions"]:
            object_refs[str(solution["object"])] = solution
    for thread in manifest["threads"].values():
        object_refs[str(thread["detail"]["object"])] = thread["detail"]
        for reply in thread["replies"]:
            object_refs[str(reply["object"])] = reply
    for status in manifest["solution_statuses"].values():
        record = status["record"]
        object_refs[str(record["object"])] = record
    pages_path = manifest_path.with_name("web_pages.json")
    page_count = 0
    asset_count = 0
    if pages_path.exists():
        pages = json.loads(pages_path.read_text(encoding="utf-8"))
        page_count = int(pages["page_count"])
        asset_count = int(pages["asset_count"])
        if page_count != len(pages["pages"]) or asset_count != len(pages["assets"]):
            raise AuditError("web-page supplement count mismatch")
        for group in ("pages", "assets"):
            for ref in pages[group].values():
                object_refs[str(ref["object"])] = ref

    if verify:
        for ref in object_refs.values():
            read_object(args.root, ref, verify=True)

    solution_ids: set[int] = set()
    thread_ids: set[int] = set()
    reply_ids: set[int] = set()
    problem_report: dict[str, dict[str, int]] = {}
    for slug, problem in manifest["problems"].items():
        detail = read_json(args.root, problem["detail_record"], verify=False)
        if int(detail["id"]) != int(problem["id"]):
            raise AuditError(f"problem ID mismatch for {slug}")
        verifier_hash = hashlib.sha256(str(detail["verifier"]).encode()).hexdigest()
        if verifier_hash != problem["verifier_sha256"]:
            raise AuditError(f"verifier hash mismatch for {slug}")

        ordering_sets: dict[str, set[int]] = {}
        summaries: dict[int, dict[str, Any]] = {}
        for ordering, listing in problem["thread_lists"].items():
            ids = [int(value) for value in listing["ids"]]
            if len(ids) != len(set(ids)):
                raise AuditError(f"duplicate {ordering} thread IDs for {slug}")
            ordering_sets[ordering] = set(ids)
            page_rows: list[dict[str, Any]] = []
            for page in listing["pages"]:
                page_rows.extend(read_json(args.root, page, verify=False))
            if [int(row["id"]) for row in page_rows] != ids:
                raise AuditError(f"thread page/index mismatch for {slug}/{ordering}")
            summaries.update({int(row["id"]): row for row in page_rows})
        if ordering_sets.get("top") != ordering_sets.get("recent"):
            raise AuditError(f"top/recent exhaustive thread sets differ for {slug}")

        problem_solution_ids: list[int] = []
        for ref in problem["solutions"]:
            solution = read_json(args.root, ref, verify=False)
            solution_id = int(solution["id"])
            if solution_id in solution_ids:
                raise AuditError(f"duplicate solution ID {solution_id}")
            solution_ids.add(solution_id)
            problem_solution_ids.append(solution_id)
        if len(problem_solution_ids) != int(problem["solution_count"]):
            raise AuditError(f"solution count mismatch for {slug}")

        leaderboard_submissions = sum(
            int(row.get("submissions", 0)) for row in problem["leaderboard"]
        )
        problem_report[slug] = {
            "solutions": len(problem_solution_ids),
            "leaderboard_submission_sum": leaderboard_submissions,
            "threads": len(ordering_sets.get("recent", set())),
        }
        thread_ids.update(ordering_sets.get("recent", set()))

        for thread_id in ordering_sets.get("recent", set()):
            thread = manifest["threads"].get(str(thread_id))
            if thread is None:
                raise AuditError(f"missing thread detail {thread_id}")
            if thread.get("problem_slug") != slug:
                raise AuditError(f"problem mapping mismatch for thread {thread_id}")
            expected_replies = int(summaries[thread_id].get("replyCount", 0))
            if expected_replies != int(thread["reply_count"]):
                raise AuditError(f"reply count mismatch for thread {thread_id}")

    # ID enumeration can find approved threads outside current problem listings.
    manifest_thread_ids = {int(value) for value in manifest["threads"]}
    if not thread_ids.issubset(manifest_thread_ids):
        raise AuditError("a listed thread is absent from the thread corpus")
    for thread_id, thread in manifest["threads"].items():
        detail = read_json(args.root, thread["detail"], verify=False)
        if int(detail["id"]) != int(thread_id):
            raise AuditError(f"thread record mismatch for {thread_id}")
        local_reply_ids: list[int] = []
        for ref in thread["replies"]:
            reply = read_json(args.root, ref, verify=False)
            reply_id = int(reply["id"])
            if int(reply["threadId"]) != int(thread_id):
                raise AuditError(f"reply {reply_id} belongs to the wrong thread")
            if reply_id in reply_ids:
                raise AuditError(f"duplicate reply ID {reply_id}")
            reply_ids.add(reply_id)
            local_reply_ids.append(reply_id)
        if len(local_reply_ids) != int(thread["reply_count"]):
            raise AuditError(f"normalized reply count mismatch for thread {thread_id}")

    status_ids = {int(value) for value in manifest["solution_statuses"]}
    if manifest["coverage"]["solution_status_scan"]["enabled"]:
        if not solution_ids.issubset(status_ids):
            missing = sorted(solution_ids - status_ids)
            raise AuditError(f"best solutions missing public status rows: {missing[:10]}")

    report = {
        "verified": True,
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "raw_hashes_verified": verify,
        "unique_objects": len(object_refs),
        "problems": len(manifest["problems"]),
        "solutions": len(solution_ids),
        "threads": len(manifest_thread_ids),
        "replies": len(reply_ids),
        "agents": len(manifest["agents"]),
        "web_pages": page_count,
        "web_assets": asset_count,
        "per_problem": problem_report,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
