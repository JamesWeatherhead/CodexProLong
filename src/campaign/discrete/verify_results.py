#!/usr/bin/env python3
"""Recheck live hashes/scores and certify local search completeness."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CREDENTIALS = Path.home() / ".config" / "einsteinarena" / "credentials.json"
AGENT = "CodexProLong"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

    report: dict[str, Any] = {
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        ),
        "external_actions": "GET only",
        "targets": {},
    }
    for slug in ("difference-bases", "flat-polynomials"):
        snapshot_path = ROOT / "checkpoints" / f"{slug}-live.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        live_problem = get(f"/api/problems/{slug}")
        live_verifier = live_problem["verifier"]
        verifier_hash = hashlib.sha256(live_verifier.encode()).hexdigest()
        expected_hash = hashlib.sha256(snapshot["problem"]["verifier"].encode()).hexdigest()
        if verifier_hash != expected_hash:
            raise RuntimeError(f"{slug} verifier changed")

        leader_rows = get(
            f"/api/solutions/best?problem_id={live_problem['id']}&limit=1"
        )
        leader = leader_rows[0]
        namespace: dict[str, Any] = {}
        exec(compile(live_verifier, f"live_{slug}_verifier.py", "exec"), namespace)
        replayed = float(namespace["evaluate"](leader["data"]))
        if replayed != float(leader["score"]):
            raise RuntimeError(f"{slug} live leader score did not replay exactly")
        own = get(
            "/api/solutions/best?"
            + urllib.parse.urlencode(
                {"problem_id": live_problem["id"], "agent_name": AGENT, "limit": 1}
            )
        )
        report["targets"][slug] = {
            "verifier_sha256": verifier_hash,
            "leader_id": leader["id"],
            "leader_agent": leader["agentName"],
            "leader_score": leader["score"],
            "leader_payload_sha256": hashlib.sha256(canonical(leader["data"])).hexdigest(),
            "replayed_score": replayed,
            "our_rank": "unranked" if not own else "ranked",
            "snapshot_sha256": file_sha256(snapshot_path),
        }

    difference_path = ROOT / "checkpoints" / "difference-search.json"
    difference = json.loads(difference_path.read_text(encoding="utf-8"))
    difference_live = json.loads(
        (ROOT / "checkpoints" / "difference-bases-live.json").read_text(encoding="utf-8")
    )
    basis = sorted(set(difference_live["solutions"][0]["data"]["set"]))
    target = int(difference["baseline_coverage"]) + 1
    swap_count = 0
    for index in range(len(basis)):
        remaining = basis[:index] + basis[index + 1 :]
        additions = {value + target for value in remaining}
        additions.update(value - target for value in remaining if value >= target)
        additions.difference_update(remaining)
        swap_count += len(additions)
    additions = {value + target for value in basis}
    additions.update(value - target for value in basis if value >= target)
    additions.difference_update(basis)
    if (
        not difference["complete"]
        or difference["remove_candidates_checked"] != len(basis)
        or difference["swap_candidates_checked"] != swap_count
        or difference["one_add_candidates_checked"] != len(additions)
    ):
        raise RuntimeError("difference search checkpoint is incomplete")
    report["targets"]["difference-bases"]["search"] = {
        "checkpoint_sha256": file_sha256(difference_path),
        "deletions": difference["remove_candidates_checked"],
        "swaps": difference["swap_candidates_checked"],
        "additions": difference["one_add_candidates_checked"],
        "best_swap": difference["best_swap"],
        "best_add": difference["best_add"],
        "gate_cleared": difference["gate_cleared"],
    }

    flat_path = ROOT / "checkpoints" / "flat-search.json"
    flat = json.loads(flat_path.read_text(encoding="utf-8"))
    expected = {
        str(radius): math.comb(70, radius)
        for radius in range(1, int(flat["max_radius"]) + 1)
    }
    if not flat["complete"] or flat["processed"] != expected:
        raise RuntimeError("flat search checkpoint is incomplete")
    report["targets"]["flat-polynomials"]["search"] = {
        "checkpoint_sha256": file_sha256(flat_path),
        "processed": flat["processed"],
        "sampled_lower_bound_minimum": flat["best_grid_lower_bound"],
        "survivors": flat["survivors"],
        "exact_evaluations": flat["exact_evaluations"],
        "gate_cleared": flat["gate_cleared"],
    }

    destination = ROOT / "checkpoints" / "reproduction.json"
    atomic_json(destination, report)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
