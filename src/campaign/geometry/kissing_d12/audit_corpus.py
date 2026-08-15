#!/usr/bin/env python3
"""Inventory every retained d12 construction and discussion from the corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np

from reproduce import CAMPAIGN, CORPUS_SHA256, HERE, VERIFIER_SHA256, append_event


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def audit_vectors(vectors: Any) -> dict[str, Any]:
    x = np.asarray(vectors, dtype=np.float64)
    shape_valid = x.shape == (841, 12)
    finite = bool(np.isfinite(x).all())
    if not shape_valid or not finite:
        return {
            "shape": list(x.shape),
            "shape_valid": shape_valid,
            "finite": finite,
        }

    norm2 = np.einsum("ij,ij->i", x, x)
    nonzero = bool(np.all(norm2 > 0))
    if not nonzero:
        return {
            "shape": list(x.shape),
            "shape_valid": True,
            "finite": True,
            "nonzero": False,
        }
    unit = x / np.sqrt(norm2)[:, None]
    # Avoid platform BLAS warnings observed for these modest dense products.
    gram = np.einsum("ik,jk->ij", unit, unit, optimize=False)
    rows, cols = np.triu_indices(len(x), 1)
    dots = gram[rows, cols]
    violating = dots > 0.5
    violating_dots = np.minimum(dots[violating], 1.0)
    overlap = np.sum(2.0 - 2.0 * np.sqrt(np.maximum(0.0, 2.0 - 2.0 * violating_dots)))

    raw_gram = np.einsum("ik,jk->ij", x, x, optimize=False)
    raw_dist2 = norm2[:, None] + norm2[None, :] - 2.0 * raw_gram
    np.fill_diagonal(raw_dist2, np.inf)
    min_flat = int(np.argmin(raw_dist2))
    min_pair = [int(value) for value in np.unravel_index(min_flat, raw_dist2.shape)]
    return {
        "shape": [841, 12],
        "shape_valid": True,
        "finite": True,
        "nonzero": True,
        "min_squared_norm_float": float(np.min(norm2)),
        "max_squared_norm_float": float(np.max(norm2)),
        "min_raw_squared_distance_float": float(np.min(raw_dist2)),
        "min_raw_pair_zero_based_float": min_pair,
        "raw_exact_condition_margin_float": float(np.min(raw_dist2) - np.max(norm2)),
        "max_normalized_dot_float": float(np.max(dots)),
        "normalized_pairs_above_half_float": int(np.count_nonzero(violating)),
        "near_duplicate_pairs_float": int(np.count_nonzero(dots > 1.0 - 1e-12)),
        "normalized_overlap_loss_float": float(overlap),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    if args.run_dir:
        run_dir = args.run_dir.resolve()
    else:
        run_dir = sorted((HERE / "runs").iterdir())[-1]

    latest = json.loads((CAMPAIGN / "research_corpus" / "latest.json").read_text())
    database = CAMPAIGN / "research_corpus" / latest["database"]
    database_hash = digest(database.read_bytes())
    if database_hash != latest["database_sha256"] or database_hash != CORPUS_SHA256:
        raise ValueError("corpus database hash does not match pinned snapshot")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    problem = connection.execute(
        "SELECT * FROM problems WHERE slug = ?", ("kissing-number-d12",)
    ).fetchone()
    if problem is None or problem["verifier_sha256"] != VERIFIER_SHA256:
        raise ValueError("unexpected problem or verifier snapshot")

    rows = connection.execute(
        """
        SELECT id, agent_name, score, created_at, record_sha256, record_json
        FROM solutions WHERE problem_id = ? ORDER BY score, id
        """,
        (problem["id"],),
    ).fetchall()
    solutions = []
    for row in rows:
        record = json.loads(row["record_json"])
        payload = record["data"]
        solutions.append(
            {
                "solution_id": row["id"],
                "agent_name": row["agent_name"],
                "published_score": row["score"],
                "created_at": row["created_at"],
                "record_sha256": row["record_sha256"],
                "payload_sha256": digest(canonical(payload)),
                "vector_audit": audit_vectors(payload.get("vectors")),
            }
        )

    thread_rows = connection.execute(
        """
        SELECT id, agent_name, title, created_at, score, reply_count,
               record_sha256, body
        FROM threads WHERE problem_id = ? ORDER BY id
        """,
        (problem["id"],),
    ).fetchall()
    threads = []
    total_replies = 0
    for thread in thread_rows:
        replies = connection.execute(
            """
            SELECT id, parent_reply_id, agent_name, created_at, record_sha256, body
            FROM replies WHERE thread_id = ? ORDER BY id
            """,
            (thread["id"],),
        ).fetchall()
        total_replies += len(replies)
        if len(replies) != thread["reply_count"]:
            raise ValueError(f"thread {thread['id']} reply count mismatch")
        threads.append(
            {
                "thread_id": thread["id"],
                "agent_name": thread["agent_name"],
                "title": thread["title"],
                "created_at": thread["created_at"],
                "score": thread["score"],
                "reply_count": thread["reply_count"],
                "record_sha256": thread["record_sha256"],
                "body_sha256": digest(thread["body"].encode("utf-8")),
                "replies": [
                    {
                        "reply_id": reply["id"],
                        "parent_reply_id": reply["parent_reply_id"],
                        "agent_name": reply["agent_name"],
                        "created_at": reply["created_at"],
                        "record_sha256": reply["record_sha256"],
                        "body_sha256": digest(reply["body"].encode("utf-8")),
                    }
                    for reply in replies
                ],
            }
        )

    leaderboard = [
        dict(row)
        for row in connection.execute(
            """
            SELECT rank, agent_name, best_score, submissions
            FROM leaderboard WHERE problem_id = ? ORDER BY rank
            """,
            (problem["id"],),
        ).fetchall()
    ]
    connection.close()

    report = {
        "schema_version": 1,
        "scope": "complete retained corpus for kissing-number-d12",
        "snapshot": latest["snapshot"],
        "corpus_database_relative_path": str(database.relative_to(CAMPAIGN)),
        "corpus_database_sha256": database_hash,
        "verifier_sha256": problem["verifier_sha256"],
        "problem_id": problem["id"],
        "scoring": problem["scoring"],
        "min_improvement": problem["min_improvement"],
        "leaderboard": leaderboard,
        "retained_solution_count": len(solutions),
        "thread_count": len(threads),
        "reply_count": total_replies,
        "solutions": solutions,
        "threads": threads,
        "audit_note": (
            "All retained payloads and all discussion bodies/replies were read; "
            "body text is represented here by its immutable corpus record/body hashes. "
            "Float diagnostics are screening only and do not execute the verifier."
        ),
    }
    output = run_dir / "retained_corpus_audit.json"
    atomic_json(output, report)

    event_file = run_dir / "events.jsonl"
    last = json.loads(event_file.read_text().splitlines()[-1])
    last_hash = append_event(
        event_file,
        {
            "event": "retained_corpus_audited",
            "audit_relative_path": str(output.relative_to(CAMPAIGN)),
            "audit_sha256": digest(output.read_bytes()),
            "retained_solution_count": len(solutions),
            "thread_count": len(threads),
            "reply_count": total_replies,
        },
        last["event_sha256"],
    )
    print(
        json.dumps(
            {
                "audit": str(output),
                "audit_sha256": digest(output.read_bytes()),
                "last_event_sha256": last_hash,
                "retained_solution_count": len(solutions),
                "thread_count": len(threads),
                "reply_count": total_replies,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
