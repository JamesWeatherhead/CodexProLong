#!/usr/bin/env python3
"""Refresh the live verifier/leader and replay the local candidate."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
CREDENTIALS = Path.home() / ".config" / "einsteinarena" / "credentials.json"
CANDIDATE = ROOT / "candidate.json"
RESULT = ROOT / "checkpoints" / "optimization.json"
PROOF = ROOT / "checkpoints" / "reproduction.json"


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
    headers = {"Authorization": f"Bearer {credentials['api_key']}"}

    def get(path: str) -> Any:
        request = urllib.request.Request(base + path, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    problem = get("/api/problems/edges-vs-triangles")
    leader = get("/api/solutions/best?problem_id=13&agent_name=CHRONOS&limit=1")[0]
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    if verifier_hash != result["verifier_sha256"] or int(leader["id"]) != result["leader_id"]:
        raise RuntimeError("live verifier or leader changed")
    namespace: dict[str, Any] = {}
    exec(compile(problem["verifier"], "current_live_edges_verifier.py", "exec"), namespace)
    leader_score = float(namespace["evaluate"](leader["data"]))
    candidate_score = float(namespace["evaluate"](candidate))
    if leader_score != result["leader_score"] or candidate_score != result["candidate_score"]:
        raise RuntimeError("current live replay differs from optimization checkpoint")
    weights = np.asarray(candidate["weights"], dtype=np.float64)
    proof = {
        "verified_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "external_actions": "GET only",
        "verifier_sha256": verifier_hash,
        "leader_id": leader["id"],
        "leader_score": leader_score,
        "candidate_path": str(CANDIDATE),
        "candidate_payload_sha256": hashlib.sha256(canonical(candidate)).hexdigest(),
        "candidate_score": candidate_score,
        "score_improvement": candidate_score - leader_score,
        "gate_cleared": candidate_score - leader_score > 1e-6,
        "shape": list(weights.shape),
        "all_finite": bool(np.isfinite(weights).all()),
        "all_nonnegative": bool(np.all(weights >= 0.0)),
        "optimization_checkpoint_sha256": hashlib.sha256(RESULT.read_bytes()).hexdigest(),
    }
    atomic_json(PROOF, proof)
    print(json.dumps(proof, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
