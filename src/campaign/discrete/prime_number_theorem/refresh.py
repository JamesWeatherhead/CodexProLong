#!/usr/bin/env python3
"""Snapshot the live prime-number-theorem verifier, leader, and discussions.

This program performs authenticated GET requests only.  In particular, it has
no code path for submitting a solution or writing to EinsteinArena.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CREDENTIALS = Path.home() / ".config" / "einsteinarena" / "credentials.json"
EXPECTED_PROBLEM_ID = 7


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def atomic_json(path: Path, value: Any) -> None:
    """Write JSON atomically while preserving dictionary insertion order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, indent=2).encode())
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    credentials = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    base = str(credentials.get("base_url", "https://einsteinarena.com")).rstrip("/")
    headers = {"Authorization": f"Bearer {credentials['api_key']}"}

    def get(path: str) -> Any:
        request = urllib.request.Request(base + path, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    problem = get("/api/problems/prime-number-theorem")
    if int(problem["id"]) != EXPECTED_PROBLEM_ID:
        raise RuntimeError("live problem id changed")
    leaders = get(
        f"/api/solutions/best?problem_id={EXPECTED_PROBLEM_ID}"
        "&agent_name=NumaroTech&limit=1"
    )
    if not leaders:
        raise RuntimeError("NumaroTech leader was not found")
    leader = leaders[0]

    top = get("/api/problems/prime-number-theorem/threads?sort=top&limit=100")
    recent = get("/api/problems/prime-number-theorem/threads?sort=recent&limit=100")
    threads = []
    for thread_id in sorted({int(row["id"]) for row in top + recent}):
        thread = get(f"/api/threads/{thread_id}")
        thread["replies"] = get(f"/api/threads/{thread_id}/replies")
        threads.append(thread)

    payload = leader["data"]
    snapshot = {
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "external_actions": "GET only",
        "verifier_sha256": hashlib.sha256(problem["verifier"].encode()).hexdigest(),
        "leader_payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "problem": problem,
        "leader": leader,
        "threads": threads,
    }
    atomic_json(ROOT / "checkpoints" / "live.json", snapshot)
    print(
        json.dumps(
            {
                "verifier_sha256": snapshot["verifier_sha256"],
                "leader_id": leader["id"],
                "leader_score": leader["score"],
                "leader_payload_sha256": snapshot["leader_payload_sha256"],
                "thread_count": len(threads),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
