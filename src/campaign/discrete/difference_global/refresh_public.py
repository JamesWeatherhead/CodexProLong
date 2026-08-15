#!/usr/bin/env python3
"""Freeze the complete public Difference Bases corpus using GET requests only."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from exact import ROOT, atomic_json


BASE = "https://einsteinarena.com"
SLUG = "difference-bases"
LATEST = ROOT / "checkpoints" / "public_latest.json"


def get(route: str, **parameters: object) -> Any:
    url = BASE + route
    if parameters:
        url += "?" + urllib.parse.urlencode(parameters)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "difference-global-read-only-audit/1"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 200:
            raise RuntimeError(f"GET {url} returned HTTP {response.status}")
        return json.load(response)


def main() -> int:
    problem = get(f"/api/problems/{SLUG}")
    problem_id = int(problem["id"])
    leaderboard = get("/api/leaderboard", problem_id=problem_id, limit=100)
    solutions = get("/api/solutions/best", problem_id=problem_id, limit=500)

    summaries: dict[int, dict[str, Any]] = {}
    for ordering in ("top", "recent"):
        for summary in get(
            f"/api/problems/{SLUG}/threads", sort=ordering, limit=500
        ):
            summaries[int(summary["id"])] = summary
    threads = []
    for thread_id in sorted(summaries):
        detail = get(f"/api/threads/{thread_id}")
        # The endpoint silently defaults to 20, so request a bound above the
        # public replyCount.  Without this, the two oldest technical threads
        # are truncated even though their summaries are present.
        replies = get(f"/api/threads/{thread_id}/replies", limit=500)
        threads.append({"detail": detail, "replies": replies})

    now = datetime.now(UTC)
    snapshot = {
        "schema": 1,
        "mode": "public_get_only",
        "base_url": BASE,
        "fetched_at": now.isoformat(),
        "problem": problem,
        "verifier_sha256": hashlib.sha256(problem["verifier"].encode()).hexdigest(),
        "leaderboard": leaderboard,
        "solutions": solutions,
        "threads": threads,
        "counts": {
            "leaderboard": len(leaderboard),
            "solutions": len(solutions),
            "threads": len(threads),
            "replies": sum(len(thread["replies"]) for thread in threads),
        },
    }
    dated = ROOT / "snapshots" / f"public_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    atomic_json(dated, snapshot)
    atomic_json(LATEST, snapshot)
    print(dated)
    print(json.dumps(snapshot["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
