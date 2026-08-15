#!/usr/bin/env python3
"""Freeze the public C2 top-three trajectory as validated float64 arrays."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from urllib.parse import quote
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
URL = "https://einsteinarena.com/api/solutions/best?problem_id=3&limit=3"
REFERENCE_AGENTS = ("Hyra", "MLAI-Yonsei", "NelsonFrontier")
HISTORY_URL = (
    "https://einsteinarena.com/api/solutions/best?problem_id=3&limit=8"
    "&agent_name=ClaudeExplorer"
)


def atomic_npy(path: Path, values: np.ndarray) -> None:
    fd, name = tempfile.mkstemp(prefix=path.stem + ".", suffix=".npy", dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        with temporary.open("wb") as handle:
            np.save(handle, values, allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(URL, headers={"User-Agent": "c2-secondary/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        rows = json.load(response)
    if not isinstance(rows, list) or len(rows) < 3:
        raise RuntimeError("C2 top-three trajectory unavailable")

    metadata: list[dict[str, object]] = []
    for rank, row in enumerate(rows[:3], start=1):
        values = np.asarray(row["data"]["values"], dtype=np.float64)
        if values.ndim != 1 or values.size == 0 or values.size > 2_000_000:
            raise RuntimeError(f"invalid shape at rank {rank}: {values.shape}")
        if not np.isfinite(values).all() or float(np.min(values)) < 0.0:
            raise RuntimeError(f"invalid values at rank {rank}")
        solution_id = int(row["id"])
        atomic_npy(ROOT / f"public_{solution_id}.npy", values)
        metadata.append(
            {
                "rank": rank,
                "id": solution_id,
                "agent_name": row.get("agentName"),
                "score": float(row["score"]),
                "created_at": row.get("createdAt"),
                "n": int(values.size),
                "nonzero": int(np.count_nonzero(values)),
                "minimum": float(np.min(values)),
                "maximum": float(np.max(values)),
                "values_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
            }
        )

    snapshot = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "endpoint": URL,
        "solutions": metadata,
        "references": [],
        "claudeexplorer_history": [],
    }
    for agent_name in REFERENCE_AGENTS:
        url = (
            "https://einsteinarena.com/api/solutions/best?problem_id=3&limit=1"
            f"&agent_name={quote(agent_name)}"
        )
        request = urllib.request.Request(url, headers={"User-Agent": "c2-secondary/1"})
        with urllib.request.urlopen(request, timeout=300) as response:
            reference_rows = json.load(response)
        if not isinstance(reference_rows, list) or len(reference_rows) != 1:
            raise RuntimeError(f"missing public reference for {agent_name}")
        row = reference_rows[0]
        values = np.asarray(row["data"]["values"], dtype=np.float64)
        if values.ndim != 1 or values.size == 0 or values.size > 2_000_000:
            raise RuntimeError(f"invalid reference shape for {agent_name}")
        if not np.isfinite(values).all() or float(np.min(values)) < 0.0:
            raise RuntimeError(f"invalid reference values for {agent_name}")
        solution_id = int(row["id"])
        atomic_npy(ROOT / f"reference_{agent_name}_{solution_id}.npy", values)
        snapshot["references"].append(
            {
                "id": solution_id,
                "agent_name": row.get("agentName"),
                "score": float(row["score"]),
                "created_at": row.get("createdAt"),
                "n": int(values.size),
                "nonzero": int(np.count_nonzero(values)),
                "minimum": float(np.min(values)),
                "maximum": float(np.max(values)),
                "values_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
            }
        )
    request = urllib.request.Request(HISTORY_URL, headers={"User-Agent": "c2-secondary/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        history_rows = json.load(response)
    if not isinstance(history_rows, list):
        raise RuntimeError("invalid ClaudeExplorer history")
    for row in history_rows:
        values = np.asarray(row["data"]["values"], dtype=np.float64)
        if values.ndim != 1 or values.size == 0 or values.size > 2_000_000:
            raise RuntimeError("invalid ClaudeExplorer history shape")
        if not np.isfinite(values).all() or float(np.min(values)) < 0.0:
            raise RuntimeError("invalid ClaudeExplorer history values")
        solution_id = int(row["id"])
        atomic_npy(ROOT / f"history_ClaudeExplorer_{solution_id}.npy", values)
        snapshot["claudeexplorer_history"].append(
            {
                "id": solution_id,
                "score": float(row["score"]),
                "created_at": row.get("createdAt"),
                "n": int(values.size),
                "nonzero": int(np.count_nonzero(values)),
                "minimum": float(np.min(values)),
                "maximum": float(np.max(values)),
                "values_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
            }
        )
    atomic_json(ROOT / "public_trajectory.json", snapshot)
    print(json.dumps(snapshot, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
