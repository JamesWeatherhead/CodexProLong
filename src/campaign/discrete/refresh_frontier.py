#!/usr/bin/env python3
"""Read-only EinsteinArena frontier snapshot for discrete constructions.

This program only issues GET requests.  It never submits solutions or writes to
the arena.  Local snapshot files are replaced atomically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CREDENTIALS = Path.home() / ".config" / "einsteinarena" / "credentials.json"
OUR_AGENT = "CodexProLong"
ATTACK_TARGETS = ("difference-bases", "flat-polynomials")
DISCRETE_SLUGS = (
    "difference-bases",
    "flat-polynomials",
    "prime-number-theorem",
    "kissing-number-d11",
    "kissing-number-d11-605",
    "kissing-number-d12-842",
)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True).encode("utf-8"))
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class ArenaReader:
    def __init__(self) -> None:
        credentials = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
        self.base = str(credentials.get("base_url", "https://einsteinarena.com")).rstrip("/")
        self.headers = {"Authorization": f"Bearer {credentials['api_key']}"}

    def get(self, path: str) -> Any:
        request = urllib.request.Request(self.base + path, headers=self.headers, method="GET")
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)


def compact_solution(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("data")
    return {
        "id": row.get("id"),
        "agent_name": row.get("agentName"),
        "score": row.get("score"),
        "created_at": row.get("createdAt"),
        "payload_sha256": sha256_json(data) if data is not None else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--thread-limit", type=int, default=100)
    parser.add_argument("--solution-limit", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.thread_limit <= 200 or not 1 <= args.solution_limit <= 500:
        raise SystemExit("limits are outside the supported bounds")

    arena = ArenaReader()
    problems = arena.get("/api/problems")
    by_slug: dict[str, dict[str, Any]] = {}
    frontier: dict[str, Any] = {}

    for summary in problems:
        slug = summary["slug"]
        detail = arena.get(f"/api/problems/{urllib.parse.quote(slug)}")
        verifier = detail["verifier"]
        leader_rows = arena.get(
            f"/api/solutions/best?problem_id={detail['id']}&limit=1"
        )
        own_rows = arena.get(
            "/api/solutions/best?"
            + urllib.parse.urlencode(
                {
                    "problem_id": detail["id"],
                    "agent_name": OUR_AGENT,
                    "limit": args.solution_limit,
                }
            )
        )
        entry = {
            "id": detail["id"],
            "slug": slug,
            "title": detail["title"],
            "scoring": detail["scoring"],
            "min_improvement": detail["minImprovement"],
            "evaluation_mode": detail["evaluationMode"],
            "verifier_sha256": hashlib.sha256(verifier.encode("utf-8")).hexdigest(),
            "leader": compact_solution(leader_rows[0]) if leader_rows else None,
            "our_best": compact_solution(own_rows[0]) if own_rows else None,
            "our_rank": None,
            "our_rank_status": "unranked" if not own_rows else "rank_requires_full_board",
        }
        frontier[slug] = entry
        if slug in ATTACK_TARGETS:
            top = arena.get(
                f"/api/solutions/best?problem_id={detail['id']}&limit={args.solution_limit}"
            )
            top_threads = arena.get(
                f"/api/problems/{slug}/threads?sort=top&limit={args.thread_limit}"
            )
            recent_threads = arena.get(
                f"/api/problems/{slug}/threads?sort=recent&limit={args.thread_limit}"
            )
            thread_ids = sorted({int(row["id"]) for row in top_threads + recent_threads})
            threads = []
            for thread_id in thread_ids:
                thread = arena.get(f"/api/threads/{thread_id}")
                thread["replies"] = arena.get(f"/api/threads/{thread_id}/replies")
                threads.append(thread)
            by_slug[slug] = {
                "problem": detail,
                "solutions": top,
                "threads": threads,
            }

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    snapshot = {
        "generated_at": now,
        "source": "read-only EinsteinArena GET API",
        "our_agent": OUR_AGENT,
        "active_problem_count": len(problems),
        "discrete_slugs": list(DISCRETE_SLUGS),
        "attack_targets": list(ATTACK_TARGETS),
        "frontier": frontier,
    }
    atomic_json(ROOT / "checkpoints" / "frontier.json", snapshot)
    for slug, value in by_slug.items():
        atomic_json(ROOT / "checkpoints" / f"{slug}-live.json", value)
    print(json.dumps(snapshot, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
