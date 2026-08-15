#!/usr/bin/env python3
"""Materialize a corpus manifest as a searchable, self-contained SQLite DB."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def read_json(root: Path, ref: dict[str, Any]) -> Any:
    with gzip.open(root / str(ref["object"]), "rt", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    manifest_path = args.manifest
    if manifest_path is None:
        latest = json.loads((args.root / "latest.json").read_text(encoding="utf-8"))
        manifest_path = args.root / latest["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output = args.output or manifest_path.with_name("corpus.sqlite3")
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    database = sqlite3.connect(temporary)
    try:
        database.executescript(
            """
            PRAGMA journal_mode = OFF;
            PRAGMA synchronous = OFF;
            PRAGMA temp_store = MEMORY;
            PRAGMA foreign_keys = ON;

            CREATE TABLE metadata (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
            CREATE TABLE problems (
                id INTEGER PRIMARY KEY,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                scoring TEXT NOT NULL,
                min_improvement REAL NOT NULL,
                evaluation_mode TEXT NOT NULL,
                solution_schema_json TEXT NOT NULL,
                verifier TEXT NOT NULL,
                verifier_sha256 TEXT NOT NULL
            );
            CREATE TABLE leaderboard (
                problem_id INTEGER NOT NULL REFERENCES problems(id),
                rank INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                best_score REAL,
                submissions INTEGER NOT NULL,
                PRIMARY KEY (problem_id, rank)
            );
            CREATE TABLE solutions (
                id INTEGER PRIMARY KEY,
                problem_id INTEGER NOT NULL REFERENCES problems(id),
                agent_name TEXT NOT NULL,
                score REAL,
                created_at TEXT,
                record_sha256 TEXT NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE solution_statuses (
                id INTEGER PRIMARY KEY,
                status TEXT,
                score REAL,
                error TEXT,
                created_at TEXT,
                evaluated_at TEXT,
                record_json TEXT NOT NULL
            );
            CREATE TABLE threads (
                id INTEGER PRIMARY KEY,
                problem_id INTEGER,
                source_problem_id INTEGER,
                problem_slug TEXT,
                agent_name TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT,
                score REAL,
                reply_count INTEGER NOT NULL,
                record_sha256 TEXT NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE replies (
                id INTEGER PRIMARY KEY,
                thread_id INTEGER NOT NULL REFERENCES threads(id),
                parent_reply_id INTEGER,
                agent_name TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT,
                record_sha256 TEXT NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE recent_activity (
                sequence INTEGER PRIMARY KEY,
                record_json TEXT NOT NULL
            );
            CREATE TABLE agents (
                name TEXT PRIMARY KEY,
                stats_json TEXT NOT NULL
            );
            CREATE TABLE static_documents (
                path TEXT PRIMARY KEY,
                content_type TEXT,
                sha256 TEXT NOT NULL,
                body BLOB NOT NULL
            );
            CREATE TABLE http_responses (
                sequence INTEGER PRIMARY KEY,
                fetched_at TEXT NOT NULL,
                method TEXT NOT NULL,
                url TEXT NOT NULL,
                status INTEGER NOT NULL,
                content_type TEXT,
                etag TEXT,
                last_modified TEXT,
                sha256 TEXT NOT NULL,
                bytes INTEGER NOT NULL,
                object_path TEXT NOT NULL
            );
            CREATE TABLE web_pages (
                url TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                status INTEGER NOT NULL,
                content_type TEXT,
                sha256 TEXT NOT NULL,
                body BLOB NOT NULL
            );
            CREATE VIRTUAL TABLE discussion_fts USING fts5(
                kind UNINDEXED,
                record_id UNINDEXED,
                problem_slug,
                agent_name,
                title,
                body,
                tokenize='porter unicode61'
            );
            CREATE INDEX idx_solutions_problem_score ON solutions(problem_id, score);
            CREATE INDEX idx_solutions_agent ON solutions(agent_name);
            CREATE INDEX idx_threads_problem ON threads(problem_id);
            CREATE INDEX idx_replies_thread ON replies(thread_id);
            CREATE INDEX idx_http_url ON http_responses(url);
            """
        )
        database.executemany(
            "INSERT INTO metadata(key, value_json) VALUES (?, ?)",
            [
                ("schema_version", json.dumps(manifest["schema_version"])),
                ("base_url", json.dumps(manifest["base_url"])),
                ("snapshot", json.dumps(manifest["snapshot"])),
                ("coverage", json.dumps(manifest["coverage"], sort_keys=True)),
                ("manifest_path", json.dumps(str(manifest_path.resolve()))),
            ],
        )

        slug_to_id: dict[str, int] = {}
        for slug, item in manifest["problems"].items():
            detail = read_json(args.root, item["detail_record"])
            problem_id = int(detail["id"])
            slug_to_id[slug] = problem_id
            database.execute(
                """INSERT INTO problems VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    problem_id,
                    slug,
                    detail["title"],
                    detail["description"],
                    detail["scoring"],
                    float(detail["minImprovement"]),
                    detail["evaluationMode"],
                    json.dumps(detail["solutionSchema"], sort_keys=True),
                    detail["verifier"],
                    item["verifier_sha256"],
                ),
            )
            for row in item["leaderboard"]:
                database.execute(
                    "INSERT INTO leaderboard VALUES (?, ?, ?, ?, ?)",
                    (
                        problem_id,
                        int(row["rank"]),
                        row["agentName"],
                        row.get("bestScore"),
                        int(row.get("submissions", 0)),
                    ),
                )
            for ref in item["solutions"]:
                row = read_json(args.root, ref)
                database.execute(
                    "INSERT INTO solutions VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        int(row["id"]),
                        problem_id,
                        row["agentName"],
                        row.get("score"),
                        row.get("createdAt"),
                        ref["sha256"],
                        json.dumps(row, ensure_ascii=False, sort_keys=True),
                    ),
                )

        for solution_id, item in manifest["solution_statuses"].items():
            row = read_json(args.root, item["record"])
            database.execute(
                "INSERT INTO solution_statuses VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    int(solution_id),
                    row.get("status"),
                    row.get("score"),
                    row.get("error"),
                    row.get("createdAt"),
                    row.get("evaluatedAt"),
                    json.dumps(row, ensure_ascii=False, sort_keys=True),
                ),
            )

        for thread_id, item in manifest["threads"].items():
            row = read_json(args.root, item["detail"])
            problem_slug = item.get("problem_slug")
            problem_id = slug_to_id.get(problem_slug) if problem_slug else None
            database.execute(
                "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(thread_id),
                    problem_id,
                    row.get("problemId"),
                    problem_slug,
                    row["agentName"],
                    row["title"],
                    row["body"],
                    row.get("createdAt"),
                    row.get("score"),
                    int(item["reply_count"]),
                    item["detail"]["sha256"],
                    json.dumps(row, ensure_ascii=False, sort_keys=True),
                ),
            )
            database.execute(
                "INSERT INTO discussion_fts VALUES (?, ?, ?, ?, ?, ?)",
                ("thread", thread_id, problem_slug, row["agentName"], row["title"], row["body"]),
            )
            for ref in item["replies"]:
                reply = read_json(args.root, ref)
                database.execute(
                    "INSERT INTO replies VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        int(reply["id"]),
                        int(thread_id),
                        reply.get("parentReplyId"),
                        reply["agentName"],
                        reply["body"],
                        reply.get("createdAt"),
                        ref["sha256"],
                        json.dumps(reply, ensure_ascii=False, sort_keys=True),
                    ),
                )
                database.execute(
                    "INSERT INTO discussion_fts VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "reply",
                        str(reply["id"]),
                        problem_slug,
                        reply["agentName"],
                        row["title"],
                        reply["body"],
                    ),
                )

        database.executemany(
            "INSERT INTO agents VALUES (?, ?)",
            [
                (name, json.dumps(stats, sort_keys=True))
                for name, stats in manifest["agents"].items()
            ],
        )
        activity = read_json(args.root, manifest["activity_ref"])
        database.executemany(
            "INSERT INTO recent_activity VALUES (?, ?)",
            [
                (index, json.dumps(row, ensure_ascii=False, sort_keys=True))
                for index, row in enumerate(activity, start=1)
            ],
        )
        for path, ref in manifest["static"].items():
            with gzip.open(args.root / ref["object"], "rb") as handle:
                body = handle.read()
            database.execute(
                "INSERT INTO static_documents VALUES (?, ?, ?, ?)",
                (path, ref.get("content_type"), ref["sha256"], body),
            )
        database.executemany(
            "INSERT INTO http_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    row["sequence"],
                    row["fetched_at"],
                    row["method"],
                    row["url"],
                    row["status"],
                    row.get("content_type"),
                    row.get("etag"),
                    row.get("last_modified"),
                    row["sha256"],
                    row["bytes"],
                    row["object"],
                )
                for row in manifest["responses"]
            ],
        )
        pages_path = manifest_path.with_name("web_pages.json")
        if pages_path.exists():
            pages = json.loads(pages_path.read_text(encoding="utf-8"))
            for kind in ("pages", "assets"):
                for url, ref in pages[kind].items():
                    with gzip.open(args.root / ref["object"], "rb") as handle:
                        body = handle.read()
                    database.execute(
                        "INSERT INTO web_pages VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            url,
                            kind[:-1],
                            int(ref["status"]),
                            ref.get("content_type"),
                            ref["sha256"],
                            body,
                        ),
                    )
        database.commit()
        integrity = database.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {integrity}")
        database.execute("PRAGMA optimize")
        database.commit()
    finally:
        database.close()
    os.replace(temporary, output)
    latest_path = args.root / "latest.json"
    if latest_path.exists():
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        if (args.root / latest.get("manifest", "")).resolve() == manifest_path.resolve():
            latest["database"] = str(output.relative_to(args.root))
            latest["database_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
            latest_temporary = latest_path.with_suffix(".json.tmp")
            latest_temporary.write_text(
                json.dumps(latest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            os.replace(latest_temporary, latest_path)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
