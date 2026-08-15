#!/usr/bin/env python3
"""Freeze public EinsteinArena state for the analytic campaign.

This program only performs GET requests.  It records exact verifier hashes,
leaderboards, full public discussions/replies, and (only for the two active
lanes) public solution trajectories.  The atomic ``latest.json`` checkpoint
is intended to make every numerical experiment reproducible against a known
live frontier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


BASE = "https://einsteinarena.com"
SLUGS = (
    "prime-number-theorem",
    "uncertainty-principle",
    "first-autocorrelation-inequality",
    "second-autocorrelation-inequality",
    "third-autocorrelation-inequality",
    "flat-polynomials",
)
ACTIVE = {"uncertainty-principle", "third-autocorrelation-inequality"}
ROOT = Path(__file__).resolve().parent


def get(route: str, **params: object) -> Any:
    url = BASE + route
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "analytic-campaign/1"})
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


def full_thread(thread_id: int) -> dict[str, Any]:
    thread = get(f"/api/threads/{thread_id}")
    thread["replies"] = get(f"/api/threads/{thread_id}/replies")
    return thread


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution-limit", type=int, default=15)
    parser.add_argument("--thread-limit", type=int, default=20)
    args = parser.parse_args()

    previous_path = ROOT.parent / "state" / "latest.json"
    prior_digest = None
    if previous_path.exists():
        prior_digest = hashlib.sha256(previous_path.read_bytes()).hexdigest()

    records: dict[str, Any] = {}
    for slug in SLUGS:
        problem = get(f"/api/problems/{slug}")
        problem_id = int(problem["id"])
        leaderboard = get("/api/leaderboard", problem_id=problem_id, limit=20)
        summaries: dict[int, dict[str, Any]] = {}
        for ordering in ("top", "recent"):
            for item in get(
                f"/api/problems/{slug}/threads",
                sort=ordering,
                limit=args.thread_limit,
            ):
                summaries[int(item["id"])] = item
        threads = [full_thread(thread_id) for thread_id in sorted(summaries)]

        solutions: list[dict[str, Any]] = []
        if slug in ACTIVE:
            solutions = get(
                "/api/solutions/best",
                problem_id=problem_id,
                limit=args.solution_limit,
            )
        records[slug] = {
            "problem": problem,
            "verifier_sha256": hashlib.sha256(problem["verifier"].encode()).hexdigest(),
            "leaderboard": leaderboard,
            "solutions": solutions,
            "threads": threads,
        }

    now = datetime.now(UTC)
    snapshot = {
        "base_url": BASE,
        "fetched_at": now.isoformat(),
        "mode": "public_get_only",
        "local_research_baseline": {
            "path": str(previous_path),
            "sha256": prior_digest,
        },
        "active_lanes": sorted(ACTIVE),
        "problems": records,
    }
    output = ROOT / "snapshots" / f"analytic_{now.strftime('%Y%m%dT%H%M%SZ')}.json"
    atomic_json(output, snapshot)
    latest = ROOT / "checkpoints" / "latest.json"
    latest.parent.mkdir(parents=True, exist_ok=True)
    temporary = latest.with_suffix(".json.tmp")
    shutil.copyfile(output, temporary)
    os.replace(temporary, latest)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
