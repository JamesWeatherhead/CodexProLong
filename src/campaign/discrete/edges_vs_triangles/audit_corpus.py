#!/usr/bin/env python3
"""Audit every retained construction and discussion record for this problem.

This is deliberately independent of the downloaded verifier.  It implements
the published power-sum densities and slope-three envelope directly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
CAMPAIGN = ROOT.parents[1]
CORPUS_SHA256 = "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"
PROBLEM_ID = 13
SLUG = "edges-vs-triangles"


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True).encode())
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def curve(x: np.ndarray, r: int) -> np.ndarray:
    root = np.sqrt(np.maximum(0.0, (r - 1) * ((r - 1) - r * x)))
    small = (1.0 - root) / r
    large = (1.0 - small) / (r - 1)
    q2 = small**2 + (r - 1) * large**2
    q3 = small**3 + (r - 1) * large**3
    return 1.0 - 3.0 * q2 + 2.0 * q3


def curve_value(x: float) -> float:
    if x <= 0.5:
        return 0.0
    r = min(20, max(3, math.ceil(1.0 / (1.0 - x) - 1e-10)))
    return float(curve(np.array([x]), r)[0])


def analyze(weights_value: Any) -> dict[str, Any]:
    weights = np.asarray(weights_value, dtype=np.float64)
    if weights.ndim != 2 or weights.shape[1] != 20:
        return {"shape": list(weights.shape), "valid_shape": False}
    sums = np.sum(weights, axis=1)
    normalized = weights / sums[:, None]
    q2 = np.sum(normalized**2, axis=1)
    q3 = np.sum(normalized**3, axis=1)
    x = 1.0 - q2
    y = 1.0 - 3.0 * q2 + 2.0 * q3
    order = np.argsort(x)
    x, y = x[order], y[order]
    full_x = np.r_[0.0, x, 1.0]
    full_y = np.r_[0.0, y, 1.0]
    unique_x, indices = np.unique(full_x, return_index=True)
    full_x, full_y = unique_x, full_y[indices]
    area = 0.0
    for left in range(len(full_x) - 1):
        x0, x1 = full_x[left], full_x[left + 1]
        y0, y1 = full_y[left], full_y[left + 1]
        width = x1 - x0
        if width < 1e-9:
            continue
        if y0 > y1 + 1e-9:
            segment = y0 * width
        elif y0 + 3.0 * width <= y1 + 1e-9:
            segment = (2.0 * y0 + 3.0 * width) * width / 2.0
        else:
            rise = max(0.0, y1 - y0)
            ramp = min(width, rise / 3.0)
            segment = (y0 + y1) * ramp / 2.0 + y1 * (width - ramp)
        area += segment
    gap = float(np.max(np.diff(full_x)))
    expected = np.array([curve_value(float(value)) for value in x])
    support = np.sum(normalized > 1e-12, axis=1)
    return {
        "all_finite": bool(np.isfinite(normalized).all()),
        "all_nonnegative": bool(np.all(normalized >= 0.0)),
        "area": float(area),
        "curve_slack_max": float(np.max(y - expected)),
        "curve_slack_min": float(np.min(y - expected)),
        "max_gap": gap,
        "maximum_edge_density": float(np.max(x)),
        "minimum_edge_density": float(np.min(x)),
        "row_sum_error": float(np.max(np.abs(np.sum(normalized, axis=1) - 1.0))),
        "rows": int(weights.shape[0]),
        "score": float(-(area + 10.0 * gap)),
        "shape": list(weights.shape),
        "support_histogram": {
            str(value): int(np.sum(support == value)) for value in np.unique(support)
        },
        "valid_shape": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stamp", default="20260815T023000Z")
    parser.add_argument("--campaign-root", type=Path, default=CAMPAIGN)
    args = parser.parse_args()
    campaign = args.campaign_root.resolve()
    latest = json.loads((campaign / "research_corpus" / "latest.json").read_text())
    database = campaign / "research_corpus" / latest["database"]
    database_hash = hashlib.sha256(database.read_bytes()).hexdigest()
    if database_hash != CORPUS_SHA256 or latest["database_sha256"] != CORPUS_SHA256:
        raise RuntimeError("frozen corpus database differs from pinned audit input")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    problem = connection.execute(
        "SELECT * FROM problems WHERE id=? AND slug=?", (PROBLEM_ID, SLUG)
    ).fetchone()
    solution_rows = connection.execute(
        "SELECT * FROM solutions WHERE problem_id=? ORDER BY id", (PROBLEM_ID,)
    ).fetchall()
    thread_rows = connection.execute(
        """SELECT * FROM threads
           WHERE problem_id=? OR source_problem_id=? OR problem_slug=?
           ORDER BY id""",
        (PROBLEM_ID, PROBLEM_ID, SLUG),
    ).fetchall()
    thread_ids = [int(row["id"]) for row in thread_rows]
    placeholders = ",".join("?" for _ in thread_ids)
    reply_rows = connection.execute(
        f"SELECT * FROM replies WHERE thread_id IN ({placeholders}) ORDER BY id",
        thread_ids,
    ).fetchall()

    constructions = []
    for row in solution_rows:
        record = json.loads(row["record_json"])
        payload = record["data"]
        diagnostics = analyze(payload["weights"])
        constructions.append(
            {
                "agent_name": row["agent_name"],
                "created_at": row["created_at"],
                "diagnostics": diagnostics,
                "payload_sha256": hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest(),
                "record_bytes_read": len(row["record_json"].encode()),
                "record_sha256": row["record_sha256"],
                "reported_score": row["score"],
                "solution_id": int(row["id"]),
            }
        )

    audit = {
        "schema": 1,
        "stamp": args.stamp,
        "corpus_database": str(database),
        "corpus_database_sha256": database_hash,
        "problem": {
            "id": int(problem["id"]),
            "slug": problem["slug"],
            "min_improvement": problem["min_improvement"],
            "verifier_sha256": problem["verifier_sha256"],
        },
        "coverage": {
            "retained_constructions_read": len(solution_rows),
            "threads_read_in_full": len(thread_rows),
            "replies_read_in_full": len(reply_rows),
            "solution_ids": [int(row["id"]) for row in solution_rows],
            "thread_ids": thread_ids,
            "reply_ids": [int(row["id"]) for row in reply_rows],
            "solution_record_bytes_read": sum(
                len(row["record_json"].encode()) for row in solution_rows
            ),
            "thread_body_bytes_read": sum(
                len(row["body"].encode()) for row in thread_rows
            ),
            "reply_body_bytes_read": sum(
                len(row["body"].encode()) for row in reply_rows
            ),
        },
        "constructions": constructions,
        "threads": [
            {
                "id": int(row["id"]),
                "agent_name": row["agent_name"],
                "title": row["title"],
                "record_sha256": row["record_sha256"],
                "body_bytes_read": len(row["body"].encode()),
            }
            for row in thread_rows
        ],
        "replies": [
            {
                "id": int(row["id"]),
                "thread_id": int(row["thread_id"]),
                "agent_name": row["agent_name"],
                "record_sha256": row["record_sha256"],
                "body_bytes_read": len(row["body"].encode()),
            }
            for row in reply_rows
        ],
    }
    run_dir = ROOT / "runs" / args.stamp / "audit"
    atomic_json(run_dir / "corpus_audit.json", audit)
    top = max(constructions, key=lambda item: float(item["diagnostics"]["score"]))
    summary = {
        "schema": 1,
        "stamp": args.stamp,
        "corpus_database_sha256": database_hash,
        "construction_count": len(constructions),
        "thread_count": len(thread_rows),
        "reply_count": len(reply_rows),
        "best_solution_id": top["solution_id"],
        "best_recomputed_score": top["diagnostics"]["score"],
        "curve_exact_construction_count": sum(
            abs(float(item["diagnostics"]["curve_slack_max"])) < 1e-12
            and abs(float(item["diagnostics"]["curve_slack_min"])) < 1e-12
            for item in constructions
        ),
        "audit_path": str(run_dir / "corpus_audit.json"),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
