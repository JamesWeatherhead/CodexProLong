#!/usr/bin/env python3
"""Independent replay checks for a frozen carry-potential run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from solver import (
    DEFAULT_INPUT,
    ROOT,
    build_reduction,
    canonical_bytes,
    repository_relative,
    sha256_bytes,
    sha256_file,
    solve_reduction,
    write_json,
)


def verify_event_chain(path: Path) -> dict[str, Any]:
    previous = "0" * 64
    count = 0
    for count, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        event = json.loads(line)
        if event["sequence"] != count:
            raise ValueError(f"event sequence mismatch at {count}")
        if event["previous_hash"] != previous:
            raise ValueError(f"event chain mismatch at {count}")
        observed_hash = event.pop("hash")
        expected_hash = sha256_bytes(canonical_bytes(event))
        if observed_hash != expected_hash:
            raise ValueError(f"event hash mismatch at {count}")
        previous = observed_hash
    return {"events": count, "last_hash": previous}


def campaign_root() -> Path:
    # .../campaign/discrete/difference_carry_potentials -> .../campaign
    return ROOT.parents[1]


def audit(run_dir: Path, input_path: Path, seconds: float) -> dict[str, Any]:
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    for name, expected in manifest["files"].items():
        observed = sha256_file(run_dir / name)
        if observed != expected:
            raise ValueError(f"run file hash mismatch for {name}: {observed} != {expected}")
    chain = verify_event_chain(run_dir / "events.jsonl")
    if config["input_sha256"] != sha256_file(input_path):
        raise ValueError("frozen input hash mismatch")

    reduction = build_reduction(input_path)
    if (run_dir / "model.pb").read_bytes() != reduction.model_bytes:
        raise ValueError("reconstructed model bytes differ from frozen model")
    if canonical_bytes(summary["facts"]) != canonical_bytes(reduction.facts):
        raise ValueError("reconstructed exact facts differ from frozen summary")
    if checkpoint["model_sha256"] != reduction.facts["model_sha256"]:
        raise ValueError("checkpoint model hash mismatch")
    if checkpoint["last_event_hash"] != chain["last_hash"]:
        raise ValueError("checkpoint event hash mismatch")

    verifier_hash = reduction.inputs["problem"]["verifier_sha256"]
    verifier_path = (
        campaign_root()
        / "state"
        / "problems"
        / "difference-bases"
        / f"{verifier_hash}.py"
    )
    if sha256_file(verifier_path) != verifier_hash:
        raise ValueError("literal frozen verifier hash mismatch")

    replay = solve_reduction(reduction, seconds=seconds, seed=config["seed"])
    if replay["status"] != "INFEASIBLE":
        raise ValueError(f"fresh solve did not reproduce INFEASIBLE: {replay['status']}")
    if summary["outcome"] != "bounded_no_go" or summary["candidate_written"]:
        raise ValueError("summary outcome is not the frozen no-go")
    candidate_names = sorted(
        path.name for path in run_dir.iterdir() if "candidate" in path.name.lower()
    )
    if candidate_names:
        raise ValueError(f"unexpected candidate-like files: {candidate_names}")

    return {
        "schema": 1,
        "ok": True,
        "run_dir": repository_relative(run_dir),
        "path_encoding": "repository-relative",
        "verifier_sha256": verifier_hash,
        "input_sha256": sha256_file(input_path),
        "model_sha256": reduction.facts["model_sha256"],
        "run_manifest_files_verified": len(manifest["files"]),
        "event_chain": chain,
        "fresh_status": replay["status"],
        "fresh_wall_time_seconds": replay["wall_time_seconds"],
        "candidate_like_files": candidate_names,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    receipt = audit(args.run_dir, args.input, args.seconds)
    if args.output:
        if ROOT not in args.output.resolve().parents:
            raise ValueError("audit output must remain inside the isolated subtree")
        write_json(args.output, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
