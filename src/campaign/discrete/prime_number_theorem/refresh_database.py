#!/usr/bin/env python3
"""Pin the complete public PNT solution database using authenticated GET only."""

from __future__ import annotations

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
OUTPUT = ROOT / "checkpoints" / "database.json"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


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
    request = urllib.request.Request(
        base
        + "/api/solutions/best?"
        + urllib.parse.urlencode({"problem_id": 7, "limit": 500}),
        headers={"Authorization": f"Bearer {credentials['api_key']}"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        solutions = json.load(response)
    snapshot = {
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "external_actions": "GET only",
        "problem_id": 7,
        "solution_count": len(solutions),
        "solutions_sha256": hashlib.sha256(canonical(solutions)).hexdigest(),
        "solutions": solutions,
    }
    atomic_json(OUTPUT, snapshot)
    print(
        json.dumps(
            {
                "solution_count": len(solutions),
                "solutions_sha256": snapshot["solutions_sha256"],
                "leader_id": solutions[0]["id"],
                "leader_score": solutions[0]["score"],
                "external_actions": "GET only",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
