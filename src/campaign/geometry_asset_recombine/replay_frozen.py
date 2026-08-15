#!/usr/bin/env python3
"""Independent literal replay of the three frozen recombination frontiers."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from datetime import UTC, datetime
from pathlib import Path


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
ENTRIES = [
    {
        "slug": "circle-packing",
        "payload": HERE / "runs/20260815T_RECOMB_CIRCLE/circle-packing/best.json",
        "summary": HERE / "runs/20260815T_RECOMB_CIRCLE/circle-packing/summary.json",
        "catalog": HERE / "runs/20260815T_RECOMB_CIRCLE/circle-packing/seed_catalog.jsonl",
        "events": HERE / "runs/20260815T_RECOMB_CIRCLE/circle-packing/events.jsonl",
        "verifier": CAMPAIGN / "state/problems/circle-packing/2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab.py",
        "verifier_sha256": "2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab",
        "target": 2.635983095360844,
        "direction": "max",
    },
    {
        "slug": "circles-rectangle",
        "payload": HERE / "runs/20260815T_RECOMB_RECT_R2/circles-rectangle/best.json",
        "summary": HERE / "runs/20260815T_RECOMB_RECT_R2/circles-rectangle/summary.json",
        "catalog": HERE / "runs/20260815T_RECOMB_RECT_R2/circles-rectangle/seed_catalog.jsonl",
        "events": HERE / "runs/20260815T_RECOMB_RECT_R2/circles-rectangle/events.jsonl",
        "verifier": CAMPAIGN / "state/problems/circles-rectangle/c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9.py",
        "verifier_sha256": "c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9",
        "target": 2.365832385307997,
        "direction": "max",
    },
    {
        "slug": "min-distance-ratio-2d",
        "payload": HERE / "runs/20260815T_RECOMB_MIN/min-distance-ratio-2d/best.json",
        "summary": HERE / "runs/20260815T_RECOMB_MIN/min-distance-ratio-2d/summary.json",
        "catalog": HERE / "runs/20260815T_RECOMB_MIN/min-distance-ratio-2d/seed_catalog.jsonl",
        "events": HERE / "runs/20260815T_RECOMB_MIN/min-distance-ratio-2d/events.jsonl",
        "verifier": CAMPAIGN / "state/problems/min-distance-ratio-2d/2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad.py",
        "verifier_sha256": "2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad",
        "target": 12.8892298077175,
        "direction": "min",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(entry: dict):
    actual = sha256(entry["verifier"])
    if actual != entry["verifier_sha256"]:
        raise RuntimeError(f"verifier hash mismatch for {entry['slug']}: {actual}")
    name = "independent_replay_" + entry["slug"].replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, entry["verifier"])
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {entry['verifier']}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate


def main() -> int:
    results = []
    for entry in ENTRIES:
        evaluate = load(entry)
        payload = json.loads(entry["payload"].read_text())
        score = float(evaluate(payload))
        target = float(entry["target"])
        margin = score - target if entry["direction"] == "max" else target - score
        results.append(
            {
                "slug": entry["slug"],
                "score": score,
                "target": target,
                "direction": entry["direction"],
                "gate_margin": margin,
                "strict_gate_clear": margin > 0,
                "payload": str(entry["payload"]),
                "payload_sha256": sha256(entry["payload"]),
                "verifier": str(entry["verifier"]),
                "verifier_sha256": sha256(entry["verifier"]),
                "summary_sha256": sha256(entry["summary"]),
                "catalog_sha256": sha256(entry["catalog"]),
                "events_sha256": sha256(entry["events"]),
                "search_summary": json.loads(entry["summary"].read_text()),
            }
        )
    receipt = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "replay_script_sha256": sha256(Path(__file__)),
        "all_verifiers_literal": True,
        "any_gate_clearer": any(item["strict_gate_clear"] for item in results),
        "results": results,
    }
    destination = HERE / "replay_receipt.json"
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, destination)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
