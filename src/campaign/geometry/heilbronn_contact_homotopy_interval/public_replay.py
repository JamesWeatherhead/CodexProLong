#!/usr/bin/env python3
"""Standard-library replay of the coordinate-free publication packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    manifest = json.loads((HERE / "PUBLICATION_MANIFEST.json").read_text())
    receipt = json.loads((HERE / "receipt.json").read_text())
    for relative, expected in manifest["include"].items():
        path = HERE / relative
        if path.stat().st_size != expected["bytes"] or sha256(path) != expected["sha256"]:
            raise RuntimeError(f"allowlist mismatch: {relative}")
    scope = receipt["scope"]
    if scope["active_triples"] * scope["distant_inactive_triples"] != scope["labelled_exchange_tasks"]:
        raise RuntimeError("exchange arithmetic mismatch")
    direct = receipt["direct"]
    pseudo = receipt["pseudo_arclength"]
    if sum(direct["status_counts"].values()) != scope["labelled_exchange_tasks"]:
        raise RuntimeError("direct status total mismatch")
    if sum(pseudo["status_counts"].values()) != direct["status_counts"]["step_floor"] + direct["status_counts"]["singular_tangent"]:
        raise RuntimeError("pseudo source total mismatch")
    if receipt["combined"]["endpoint_roots_reached"] != direct["status_counts"]["complete"] + pseudo["recovered_endpoints"]:
        raise RuntimeError("endpoint total mismatch")
    if receipt["combined"]["paths_unresolved_past_caps"] != sum(pseudo["status_counts"].values()) - pseudo["recovered_endpoints"]:
        raise RuntimeError("cap total mismatch")
    if direct["gate_clearers"] or pseudo["gate_clearers"] or receipt["combined"]["new_candidate"]:
        raise RuntimeError("receipt unexpectedly claims a candidate")
    for run in receipt["runs"]:
        replay = run["independent_replay"]
        if replay["status"] != "PASS" or replay["gate_clearing"]:
            raise RuntimeError("run replay verdict mismatch")
        if replay["results_sha256"] != run["files"]["results.jsonl"]["sha256"]:
            raise RuntimeError("detached results hash mismatch")
    serialized = json.dumps(receipt, sort_keys=True).lower()
    forbidden = ("/users/", "api" + "_" + "key", "authorization" + ": bearer")
    if any(token in serialized for token in forbidden):
        raise RuntimeError("private path or credential marker in receipt")
    print(
        json.dumps(
            {
                "status": "PASS",
                "allowlisted_files": len(manifest["include"]),
                "direct_tasks": scope["labelled_exchange_tasks"],
                "pseudo_tasks": sum(pseudo["status_counts"].values()),
                "endpoint_roots_replayed": receipt["combined"]["endpoint_roots_reached"],
                "polishes_replayed": direct["polished_count"],
                "gate_clearers": 0,
                "receipt_sha256": sha256(HERE / "receipt.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
