#!/usr/bin/env python3
"""Audit every frozen EinsteinArena C3 construction and discussion record.

This is deliberately a metadata/structure audit.  It reads all candidate
vectors, all thread bodies, and all reply bodies from the immutable campaign
SQLite snapshot, but it does not execute downloaded verifier code or write to
the Arena.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
LATEST = CAMPAIGN / "research_corpus" / "latest.json"
PROBLEM_ID = 4
PROBLEM_SLUG = "third-autocorrelation-inequality"

METHOD_PATTERNS: dict[str, str] = {
    "active_set_or_lp": r"active[- ]set|\bLP\b|linear program|equioscillat",
    "smooth_or_gradient": r"smooth|max|gradient|L-BFGS|Adam|subgradient",
    "fourier_or_spectral": r"Fourier|spectral|frequency|Gerchberg|phase",
    "rank_or_sdp": r"rank[- ]?one|\bSDP\b|semidefinite",
    "resolution_change": r"upsampl|rebin|resolution|discret",
    "sign_or_topology": r"sign[- ]?flip|antisym|negative|topolog|orthant",
    "block_or_repeat": r"block|repeat|pair[- ]split|Kronecker",
    "newton_or_second_order": r"Newton|Hessian|second[- ]order|semismooth",
    "polynomial_square": r"polynomial square|square root|spectral factor",
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
    path.parent.mkdir(parents=True, exist_ok=True)
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


def vector_features(values: list[float]) -> dict[str, Any]:
    vector = np.asarray(values, dtype=np.float64)
    if vector.ndim != 1 or not vector.size or not np.isfinite(vector).all():
        raise ValueError("corpus C3 construction is not a finite nonempty vector")
    signs = np.signbit(vector)
    reverse = vector[::-1]
    norm_sq = float(np.dot(vector, vector))
    reflection_cosine = (
        float(np.dot(vector, reverse) / norm_sq) if norm_sq else None
    )
    return {
        "n": int(vector.size),
        "sum": float(np.sum(vector)),
        "minimum": float(np.min(vector)),
        "maximum": float(np.max(vector)),
        "negative_fraction": float(np.mean(vector < 0.0)),
        "sign_changes": int(np.count_nonzero(signs[1:] != signs[:-1])),
        "reflection_cosine": reflection_cosine,
        "values_float64_sha256": hashlib.sha256(vector.tobytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", type=Path, default=LATEST)
    parser.add_argument("--output", type=Path, default=HERE / "corpus_audit.json")
    args = parser.parse_args()

    latest = json.loads(args.latest.read_text(encoding="utf-8"))
    database = args.latest.parent / latest["database"]
    database_hash = sha256_file(database)
    if database_hash != latest["database_sha256"]:
        raise RuntimeError("frozen corpus database hash mismatch")

    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    problem = connection.execute(
        "SELECT * FROM problems WHERE id=? AND slug=?", (PROBLEM_ID, PROBLEM_SLUG)
    ).fetchone()
    if problem is None:
        raise RuntimeError("frozen corpus does not contain the C3 problem")

    constructions: list[dict[str, Any]] = []
    value_hash_to_ids: dict[str, list[int]] = defaultdict(list)
    solution_records = connection.execute(
        "SELECT * FROM solutions WHERE problem_id=? ORDER BY id", (PROBLEM_ID,)
    ).fetchall()
    for row in solution_records:
        record = json.loads(row["record_json"])
        values = record.get("data", {}).get("values")
        if not isinstance(values, list):
            raise RuntimeError(f"solution {row['id']} lacks data.values")
        features = vector_features(values)
        value_hash_to_ids[features["values_float64_sha256"]].append(int(row["id"]))
        constructions.append(
            {
                "id": int(row["id"]),
                "score": float(row["score"]),
                "record_sha256": row["record_sha256"],
                **features,
            }
        )

    threads = connection.execute(
        "SELECT * FROM threads WHERE problem_id=? ORDER BY id", (PROBLEM_ID,)
    ).fetchall()
    replies = connection.execute(
        """
        SELECT replies.* FROM replies
        JOIN threads ON threads.id=replies.thread_id
        WHERE threads.problem_id=? ORDER BY replies.thread_id,replies.id
        """,
        (PROBLEM_ID,),
    ).fetchall()
    discussion_records: list[dict[str, Any]] = []
    for row in threads:
        discussion_records.append(
            {
                "kind": "thread",
                "id": int(row["id"]),
                "thread_id": int(row["id"]),
                "title": row["title"],
                "agent_name": row["agent_name"],
                "body": row["body"],
                "record_sha256": row["record_sha256"],
            }
        )
    for row in replies:
        discussion_records.append(
            {
                "kind": "reply",
                "id": int(row["id"]),
                "thread_id": int(row["thread_id"]),
                "title": "",
                "agent_name": row["agent_name"],
                "body": row["body"],
                "record_sha256": row["record_sha256"],
            }
        )

    taxonomy: dict[str, dict[str, Any]] = {}
    for label, pattern in METHOD_PATTERNS.items():
        matches = [
            record
            for record in discussion_records
            if re.search(pattern, record["title"] + "\n" + record["body"], re.I)
        ]
        taxonomy[label] = {
            "record_count": len(matches),
            "thread_ids": sorted({record["thread_id"] for record in matches}),
        }

    duplicate_groups = [
        {"values_float64_sha256": digest, "solution_ids": ids}
        for digest, ids in sorted(value_hash_to_ids.items())
        if len(ids) > 1
    ]
    construction_digest = sha256_json(
        [
            {
                "id": item["id"],
                "record_sha256": item["record_sha256"],
                "values_float64_sha256": item["values_float64_sha256"],
            }
            for item in constructions
        ]
    )
    discussion_digest = sha256_json(
        [
            {
                "kind": item["kind"],
                "id": item["id"],
                "thread_id": item["thread_id"],
                "record_sha256": item["record_sha256"],
                "body_sha256": hashlib.sha256(item["body"].encode("utf-8")).hexdigest(),
            }
            for item in discussion_records
        ]
    )

    audit = {
        "schema": 1,
        "problem": {
            "id": int(problem["id"]),
            "slug": problem["slug"],
            "scoring": problem["scoring"],
            "minimum_improvement": float(problem["min_improvement"]),
            "verifier_sha256": problem["verifier_sha256"],
        },
        "corpus": {
            "snapshot": latest["snapshot"],
            "database": str(database.relative_to(CAMPAIGN)),
            "database_sha256": database_hash,
            "all_c3_constructions_read": len(constructions),
            "all_c3_threads_read": len(threads),
            "all_c3_replies_read": len(replies),
            "construction_index_sha256": construction_digest,
            "discussion_index_sha256": discussion_digest,
        },
        "constructions": constructions,
        "duplicate_value_groups": duplicate_groups,
        "discussion_method_taxonomy": taxonomy,
        "scope_note": (
            "Every frozen C3 data.values array and every captured C3 thread/reply "
            "body was parsed. Feature summaries replace raw third-party candidate bytes; "
            "construction author labels and timestamps are intentionally omitted."
        ),
    }
    if any(not math.isfinite(item["score"]) for item in constructions):
        raise RuntimeError("non-finite frozen score")
    atomic_json(args.output, audit)
    print(json.dumps(audit["corpus"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
