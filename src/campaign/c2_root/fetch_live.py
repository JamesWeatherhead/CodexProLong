#!/usr/bin/env python3
"""Atomically freeze the public C2 leader and its immediate trajectory."""

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
URL = "https://einsteinarena.com/api/solutions/best?problem_id=3&limit=3"


def main() -> int:
    request = urllib.request.Request(URL, headers={"User-Agent": "c2-root-lane/1"})
    with urllib.request.urlopen(request, timeout=240) as response:
        rows = json.load(response)
    if not isinstance(rows, list) or len(rows) < 2:
        raise RuntimeError("public C2 trajectory is missing")

    ROOT.mkdir(parents=True, exist_ok=True)
    arrays: list[np.ndarray] = []
    metadata: list[dict[str, object]] = []
    for row in rows:
        values = np.asarray(row["data"]["values"], dtype=np.float64)
        if values.ndim != 1 or not values.size or values.size > 2_000_000:
            raise RuntimeError("invalid public solution shape")
        if not np.isfinite(values).all() or np.min(values) < 0:
            raise RuntimeError("invalid public solution domain")
        arrays.append(values)
        metadata.append(
            {
                "id": int(row["id"]),
                "agent_name": row.get("agentName"),
                "score": float(row["score"]),
                "created_at": row.get("createdAt"),
                "n": int(values.size),
                "nonzero": int(np.count_nonzero(values)),
                "values_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
            }
        )

    fd, temporary_name = tempfile.mkstemp(prefix="leader.", suffix=".npy", dir=ROOT)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as handle:
            np.save(handle, arrays[0], allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, ROOT / "leader.npy")
    finally:
        temporary.unlink(missing_ok=True)

    snapshot = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "endpoint": URL,
        "solutions": metadata,
    }
    output = ROOT / "snapshot.json"
    tmp = output.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, output)
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

