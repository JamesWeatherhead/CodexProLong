#!/usr/bin/env python3
"""Snapshot live geometry metadata using public GET endpoints only."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


BASE = "https://einsteinarena.com"
SLUGS = [
    "kissing-number-d11",
    "kissing-number-d11-605",
    "kissing-number-d12",
    "kissing-number-d12-842",
    "circles-rectangle",
    "tammes-problem",
    "min-distance-ratio-2d",
    "thomson-problem",
    "circle-packing",
    "heilbronn-triangles",
]


def get(path: str, **params: object) -> object:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def main() -> int:
    records = []
    for slug in SLUGS:
        problem = get(f"/api/problems/{slug}")
        problem_id = problem["id"]
        top = get("/api/leaderboard", problem_id=problem_id, limit=5)
        best = get("/api/solutions/best", problem_id=problem_id, limit=3)
        threads = {}
        for ordering in ("top", "recent"):
            for thread in get(f"/api/problems/{slug}/threads", sort=ordering, limit=20):
                threads[thread["id"]] = thread
        records.append(
            {
                "slug": slug,
                "id": problem_id,
                "title": problem["title"],
                "scoring": problem["scoring"],
                "minImprovement": problem["minImprovement"],
                "solutionSchema": problem["solutionSchema"],
                "verifier_sha256": hashlib.sha256(problem["verifier"].encode()).hexdigest(),
                "leaderboard": top,
                "bestSolutions": [
                    {key: item[key] for key in ("id", "agentName", "score", "createdAt")}
                    for item in best
                ],
                "threads": list(threads.values()),
            }
        )
    snapshot = {"fetchedAt": datetime.now(UTC).isoformat(), "problems": records}
    output = Path(__file__).parent / "snapshots" / f"geometry_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, output)
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
