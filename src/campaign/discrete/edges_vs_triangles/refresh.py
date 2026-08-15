#!/usr/bin/env python3
"""Snapshot the live edges-vs-triangles seed and discussion using GET only."""

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
EXPECTED_LEADER_ID = 2367


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


def main() -> None:
    credentials = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    base = str(credentials.get("base_url", "https://einsteinarena.com")).rstrip("/")
    headers = {"Authorization": f"Bearer {credentials['api_key']}"}

    def get(path: str) -> Any:
        request = urllib.request.Request(base + path, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    problem = get("/api/problems/edges-vs-triangles")
    rows = get("/api/solutions/best?problem_id=13&agent_name=CHRONOS&limit=1")
    if not rows or int(rows[0]["id"]) != EXPECTED_LEADER_ID:
        raise RuntimeError("live CHRONOS leader is no longer solution #2367")
    top_threads = get("/api/problems/edges-vs-triangles/threads?sort=top&limit=100")
    recent_threads = get("/api/problems/edges-vs-triangles/threads?sort=recent&limit=100")
    threads = []
    for thread_id in sorted({int(row["id"]) for row in top_threads + recent_threads}):
        thread = get(f"/api/threads/{thread_id}")
        thread["replies"] = get(f"/api/threads/{thread_id}/replies")
        threads.append(thread)
    snapshot = {
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "external_actions": "GET only",
        "verifier_sha256": hashlib.sha256(problem["verifier"].encode()).hexdigest(),
        "problem": problem,
        "leader": rows[0],
        "threads": threads,
    }
    atomic_json(ROOT / "checkpoints" / "live.json", snapshot)
    print(json.dumps({k: v for k, v in snapshot.items() if k not in {"problem", "leader", "threads"}}, indent=2))


if __name__ == "__main__":
    main()
