#!/usr/bin/env python3
"""Freeze the public C1 leader without credentials or external mutations."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
URL = "https://einsteinarena.com/api/solutions/best?problem_id=2&limit=5"


def main() -> int:
    request = urllib.request.Request(URL, headers={"User-Agent": "c1-root-lane/1"})
    with urllib.request.urlopen(request, timeout=240) as response:
        rows = json.load(response)
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("public C1 trajectory is missing")
    arrays = [np.asarray(row["data"]["values"], dtype=np.float64) for row in rows]
    for values in arrays:
        if values.ndim != 1 or not values.size or values.size > 2_000_000:
            raise RuntimeError("invalid solution shape")
        if not np.isfinite(values).all() or np.min(values) < 0:
            raise RuntimeError("invalid solution domain")
    ROOT.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="leader.", suffix=".npy", dir=ROOT)
    os.close(fd)
    temporary = Path(name)
    try:
        with temporary.open("wb") as handle:
            np.save(handle, arrays[0], allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, ROOT / "leader.npy")
    finally:
        temporary.unlink(missing_ok=True)
    metadata = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "endpoint": URL,
        "solutions": [
            {
                "id": int(row["id"]),
                "agent_name": row.get("agentName"),
                "score": float(row["score"]),
                "created_at": row.get("createdAt"),
                "n": int(values.size),
                "nonzero": int(np.count_nonzero(values)),
                "values_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
            }
            for row, values in zip(rows, arrays)
        ],
    }
    output = ROOT / "snapshot.json"
    temp_output = output.with_suffix(".json.tmp")
    with temp_output.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_output, output)
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

