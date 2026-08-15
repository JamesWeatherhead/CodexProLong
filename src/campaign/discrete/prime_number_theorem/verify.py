#!/usr/bin/env python3
"""Replay the strongest local payload through the unmodified live verifier.

Only authenticated GET requests are made.  There is deliberately no submit or
discussion endpoint in this file.
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
LIVE = ROOT / "checkpoints" / "live.json"
OPTIMIZATION = ROOT / "checkpoints" / "optimization.json"
PAYLOAD = ROOT / "best_feasible.json"
REPRODUCTION = ROOT / "checkpoints" / "reproduction.json"


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

    live = json.loads(LIVE.read_text(encoding="utf-8"))
    optimization = json.loads(OPTIMIZATION.read_text(encoding="utf-8"))
    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    problem = get("/api/problems/prime-number-theorem")
    leader = get("/api/solutions/best?problem_id=7&agent_name=NumaroTech&limit=1")[0]
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
    if verifier_hash != live["verifier_sha256"]:
        raise RuntimeError("live verifier changed")
    if int(leader["id"]) != int(live["leader"]["id"]):
        raise RuntimeError("live leader changed")
    if optimization["verifier_sha256"] != verifier_hash:
        raise RuntimeError("optimization checkpoint is stale")
    raw = payload.get("partial_function")
    if not isinstance(raw, dict) or not raw or len(raw) > 2000:
        raise ValueError("payload has an invalid partial_function")

    namespace: dict[str, Any] = {}
    exec(compile(problem["verifier"], "live_prime_number_verifier.py", "exec"), namespace)
    score = float(namespace["evaluate"](payload))
    result = {
        "verified_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "external_actions": "GET only",
        "verifier_sha256": verifier_hash,
        "leader_id": leader["id"],
        "leader_score": leader["score"],
        "candidate_path": str(PAYLOAD),
        "candidate_payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
        "raw_key_count": len(raw),
        "candidate_score": score,
        "score_improvement": score - float(leader["score"]),
        "gate_cleared": score - float(leader["score"]) > 1e-6,
        "optimization_checkpoint_sha256": hashlib.sha256(
            OPTIMIZATION.read_bytes()
        ).hexdigest(),
    }
    atomic_json(REPRODUCTION, result)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
