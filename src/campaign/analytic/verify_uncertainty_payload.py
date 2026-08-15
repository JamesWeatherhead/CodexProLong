#!/usr/bin/env python3
"""Independent frozen/live replay for the k=25 uncertainty payload (GET only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
BASE = "https://einsteinarena.com"


def get(route: str, **params: object) -> Any:
    url = BASE + route
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "analytic-replay/1"})
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


def evaluate(code: str, payload: dict[str, Any]) -> float:
    namespace: dict[str, Any] = {}
    exec(code, namespace)
    return float(namespace["evaluate"](payload))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--payload", type=Path, default=ROOT / "payloads" / "uncertainty-k25.json"
    )
    parser.add_argument(
        "--snapshot", type=Path, default=ROOT / "checkpoints" / "latest.json"
    )
    args = parser.parse_args()

    payload_bytes = args.payload.read_bytes()
    payload = json.loads(payload_bytes)
    roots = payload["laguerre_double_roots"]
    if not (
        len(roots) == 25
        and len(set(roots)) == 25
        and all(0 < value <= 300 for value in roots)
    ):
        raise RuntimeError("payload schema check failed")

    snapshot = json.loads(args.snapshot.read_text())
    frozen = snapshot["problems"]["uncertainty-principle"]["problem"]
    live = get("/api/problems/uncertainty-principle")
    leaderboard = get("/api/leaderboard", problem_id=9, limit=3)
    frozen_hash = hashlib.sha256(frozen["verifier"].encode()).hexdigest()
    live_hash = hashlib.sha256(live["verifier"].encode()).hexdigest()
    frozen_score = evaluate(frozen["verifier"], payload)
    live_score = evaluate(live["verifier"], payload)
    incumbent = float(leaderboard[0]["bestScore"])
    gate = incumbent - float(live["minImprovement"])

    receipt = {
        "verified_at": datetime.now(UTC).isoformat(),
        "mode": "public_get_and_local_evaluate_only",
        "slug": "uncertainty-principle",
        "payload_path": str(args.payload.resolve()),
        "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
        "root_count": len(roots),
        "frozen_verifier_sha256": frozen_hash,
        "live_verifier_sha256": live_hash,
        "frozen_score": frozen_score,
        "live_score": live_score,
        "scores_bit_identical": frozen_score.hex() == live_score.hex(),
        "leader": leaderboard[0],
        "min_improvement": float(live["minImprovement"]),
        "strict_gate": gate,
        "improvement": incumbent - live_score,
        "safety_below_gate": gate - live_score,
        "gate_cleared": live_score < gate,
    }
    if frozen_hash != live_hash or frozen_score.hex() != live_score.hex():
        raise RuntimeError(json.dumps(receipt, sort_keys=True))
    atomic_json(ROOT / "receipts" / "uncertainty-k25-verification.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
