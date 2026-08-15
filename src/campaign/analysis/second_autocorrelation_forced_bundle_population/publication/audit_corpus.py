#!/usr/bin/env python3
"""Read the complete frozen Arena C2 corpus without retaining coefficient data.

The output is deliberately metadata-only: every construction JSON, thread body,
and reply body is decoded and hashed, but no candidate values or discussion
bodies are copied into this lane.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any


TAGS: dict[str, str] = {
    "active_lag": r"active[- ]?(?:max|lag)|near[- ]?max|kink",
    "bundle_remez": r"bundle|remez|equioscillat|minimax|chebyshev",
    "comb": r"comb|triplet|tooth|teeth",
    "dinkelbach": r"dinkelbach",
    "fft": r"\bfft\b|fourier|spectral",
    "gradient": r"gradient|adam|l[- ]?bfgs|powell|newton",
    "multiscale": r"upsampl|resampl|resolution|coarse[- ]?to[- ]?fine|multigrid|multi[- ]?scale",
    "packet": r"packet|run[- ]?weight|interval|block",
    "phase": r"phase|shift|spacing|chirp",
    "population": r"population|evolution|basin|restart|respawn|random",
    "support": r"support|birth|insert|relocat|split|merge|prun|zero[- ]?weight",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tags(text: str) -> list[str]:
    return [name for name, pattern in TAGS.items() if re.search(pattern, text, re.I)]


def float64_sha256(values: list[Any]) -> str:
    numbers = array.array("d", (float(value) for value in values))
    if sys.byteorder != "little":
        numbers.byteswap()
    return sha256_bytes(numbers.tobytes())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    database = args.database.resolve()
    output = args.output.resolve()
    if output.parent != Path(__file__).resolve().parent:
        raise SystemExit("output must remain in this isolated lane")

    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    problem = connection.execute(
        "SELECT * FROM problems WHERE slug=?",
        ("second-autocorrelation-inequality",),
    ).fetchone()
    if problem is None:
        raise SystemExit("C2 problem missing")
    problem_id = int(problem["id"])

    construction_rows = connection.execute(
        "SELECT * FROM solutions WHERE problem_id=? ORDER BY id", (problem_id,)
    ).fetchall()
    constructions: list[dict[str, Any]] = []
    total_values = 0
    for row in construction_rows:
        raw = str(row["record_json"])
        record = json.loads(raw)
        values = record.get("data", {}).get("values")
        if not isinstance(values, list):
            raise RuntimeError(f"solution {row['id']} has no values list")
        minimum = min(float(value) for value in values)
        maximum = max(float(value) for value in values)
        finite = all(float("-inf") < float(value) < float("inf") for value in values)
        total_values += len(values)
        constructions.append(
            {
                "id": int(row["id"]),
                "agent_name": str(row["agent_name"]),
                "score": row["score"],
                "created_at": row["created_at"],
                "record_sha256_from_corpus": str(row["record_sha256"]),
                "record_text_sha256": sha256_bytes(raw.encode("utf-8")),
                "record_bytes": len(raw.encode("utf-8")),
                "value_count": len(values),
                "value_float64_le_sha256": float64_sha256(values),
                "minimum": minimum,
                "maximum": maximum,
                "all_finite": finite,
                "all_nonnegative": minimum >= 0.0,
            }
        )
        # The public coefficient vector must not survive this loop iteration.
        del values, record, raw

    thread_rows = connection.execute(
        """
        SELECT * FROM threads
        WHERE problem_id=? OR source_problem_id=? OR problem_slug=?
        ORDER BY id
        """,
        (problem_id, problem_id, "second-autocorrelation-inequality"),
    ).fetchall()
    threads: list[dict[str, Any]] = []
    replies: list[dict[str, Any]] = []
    for thread in thread_rows:
        body = str(thread["body"])
        reply_rows = connection.execute(
            "SELECT * FROM replies WHERE thread_id=? ORDER BY id", (thread["id"],)
        ).fetchall()
        threads.append(
            {
                "id": int(thread["id"]),
                "agent_name": str(thread["agent_name"]),
                "title": str(thread["title"]),
                "body_utf8_sha256": sha256_bytes(body.encode("utf-8")),
                "body_characters": len(body),
                "method_tags": tags(str(thread["title"]) + "\n" + body),
                "declared_reply_count": int(thread["reply_count"]),
                "captured_reply_count": len(reply_rows),
            }
        )
        for reply in reply_rows:
            reply_body = str(reply["body"])
            replies.append(
                {
                    "id": int(reply["id"]),
                    "thread_id": int(reply["thread_id"]),
                    "parent_reply_id": reply["parent_reply_id"],
                    "agent_name": str(reply["agent_name"]),
                    "body_utf8_sha256": sha256_bytes(reply_body.encode("utf-8")),
                    "body_characters": len(reply_body),
                    "method_tags": tags(reply_body),
                }
            )

    corpus_sha256 = sha256_bytes(database.read_bytes())
    latest_score = max(float(row["score"]) for row in construction_rows)
    gate = latest_score + float(problem["min_improvement"])
    tag_counts = {
        tag: sum(tag in row["method_tags"] for row in threads + replies)
        for tag in TAGS
    }
    result = {
        "schema": 1,
        "scope": {
            "database": str(database),
            "database_sha256": corpus_sha256,
            "problem_id": problem_id,
            "problem_slug": str(problem["slug"]),
            "verifier_sha256": str(problem["verifier_sha256"]),
            "construction_rows_fully_decoded": len(constructions),
            "construction_values_fully_decoded": total_values,
            "thread_bodies_fully_read": len(threads),
            "reply_bodies_fully_read": len(replies),
            "coefficient_values_retained": 0,
        },
        "frontier": {
            "public_leader": latest_score,
            "minimum_improvement": float(problem["min_improvement"]),
            "strict_gate": gate,
        },
        "method_tag_counts": tag_counts,
        "constructions": constructions,
        "threads": threads,
        "replies": replies,
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": "PASS",
                "output": str(output),
                "scope": result["scope"],
                "frontier": result["frontier"],
                "method_tag_counts": tag_counts,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
