#!/usr/bin/env python3
"""Create a full read-only checkpoint for one EinsteinArena problem."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


BASE = "https://einsteinarena.com"


def get(path: str, **params: object) -> object:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "geometry-campaign/1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    parser.add_argument("--solution-limit", type=int, default=100)
    parser.add_argument("--thread-limit", type=int, default=100)
    parser.add_argument("--output-root", type=Path, default=Path(__file__).parent / "snapshots")
    args = parser.parse_args()

    problem = get(f"/api/problems/{args.slug}")
    assert isinstance(problem, dict)
    problem_id = int(problem["id"])
    leaderboard = get("/api/leaderboard", problem_id=problem_id, limit=100)
    solutions = get("/api/solutions/best", problem_id=problem_id, limit=args.solution_limit)
    summaries: dict[int, dict[str, object]] = {}
    for ordering in ("top", "recent"):
        items = get(f"/api/problems/{args.slug}/threads", sort=ordering, limit=args.thread_limit)
        assert isinstance(items, list)
        for item in items:
            summaries[int(item["id"])] = item
    threads = []
    for thread_id in sorted(summaries):
        thread = get(f"/api/threads/{thread_id}")
        assert isinstance(thread, dict)
        thread["replies"] = get(f"/api/threads/{thread_id}/replies")
        threads.append(thread)

    now = datetime.now(UTC)
    snapshot = {
        "fetched_at": now.isoformat(),
        "mode": "public_get_only",
        "problem": problem,
        "verifier_sha256": hashlib.sha256(problem["verifier"].encode()).hexdigest(),
        "leaderboard": leaderboard,
        "solutions": solutions,
        "threads": threads,
    }
    output = args.output_root / f"{args.slug}_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    atomic_json(output, snapshot)
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
