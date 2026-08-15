#!/usr/bin/env python3
"""Regenerate and independently replay a compact forced-bundle run receipt.

The checkpoint is reconstructed in memory from the clean-room source and the
recorded seed/configuration.  No NumPy payload is read or written.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

import forced_bundle as engine
import replay as independent


LANE = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    return parser.parse_args()


def checked_run(path: Path) -> Path:
    run = path.resolve()
    try:
        run.relative_to(LANE / "runs")
    except ValueError as error:
        raise SystemExit("run must be inside this source snapshot's runs directory") from error
    return run


def regenerate(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[np.ndarray]]:
    records: list[dict[str, Any]] = []
    final_arrays: list[np.ndarray] = []
    for member in range(int(config["population"])):
        spec = engine.make_spec(int(config["n"]), int(config["seed"]) + member)
        values = engine.spike_comb(spec)
        initial_score = engine.score_parts(values)["score"]
        history: list[dict[str, Any]] = []
        for step in range(int(config["steps"])):
            values, ridge = engine.ridge_balance(
                values,
                int(config["separation"]),
                float(config["ridge_loss"]),
            )
            values, bundle = engine.bundle_step(
                values,
                int(config["branches"]),
                int(config["separation"]),
            )
            history.append({"step": step, "ridge": ridge, "bundle": bundle})
        records.append(
            {
                "member": member,
                "spec": asdict(spec),
                "initial_score": initial_score,
                "final_score": engine.score_parts(values)["score"],
                "history": history,
            }
        )
        final_arrays.append(values)
    return records, final_arrays


def npy_sha256(values: np.ndarray) -> str:
    buffer = io.BytesIO()
    np.save(buffer, np.ascontiguousarray(values, dtype=np.float64), allow_pickle=False)
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def main() -> None:
    run = checked_run(parse_args().run)
    config: dict[str, Any] = json.loads((run / "config.json").read_text())
    summary: dict[str, Any] = json.loads((run / "summary.json").read_text())
    receipt: dict[str, Any] = json.loads((run / "independent_replay.json").read_text())

    if config.get("coefficient_inputs") != [] or summary.get("coefficient_inputs") != []:
        raise AssertionError("receipt is not a seed-only clean-room run")
    if independent.sha256_file(LANE / "forced_bundle.py") != summary["source_sha256"]:
        raise AssertionError("engine source hash mismatch")

    records, final_arrays = regenerate(config)
    if records != summary["members"]:
        raise AssertionError("regenerated member trace differs from authenticated summary")
    best_member = int(np.argmax([row["final_score"] for row in records]))
    if best_member != summary["best_member"]:
        raise AssertionError("best-member mismatch")
    best = np.ascontiguousarray(final_arrays[best_member], dtype=np.float64)

    checkpoint_sha256 = npy_sha256(best)
    value_sha256 = hashlib.sha256(np.ascontiguousarray(best, dtype="<f8").tobytes()).hexdigest()
    if checkpoint_sha256 != summary["checkpoint_sha256"]:
        raise AssertionError("in-memory NPY hash mismatch")
    if value_sha256 != summary["checkpoint_value_float64_le_sha256"]:
        raise AssertionError("in-memory value hash mismatch")

    score = independent.exact_formula(best)
    if not math.isclose(score, summary["best_score"], rel_tol=0.0, abs_tol=2e-15):
        raise AssertionError("independent score mismatch")
    if receipt.get("status") != "PASS" or not math.isclose(
        score, float(receipt["score"]), rel_tol=0.0, abs_tol=2e-15
    ):
        raise AssertionError("independent replay receipt mismatch")

    event_count, event_head = independent.verify_chain(run / "events.jsonl")
    if event_count != summary["event_count"] or event_head != summary["event_chain_head"]:
        raise AssertionError("event-chain mismatch")

    result = {
        "status": "PASS",
        "mode": "source_regeneration_without_checkpoint_file",
        "score": score,
        "gap_to_gate": summary["strict_gate"] - score,
        "gate_cleared": score > summary["strict_gate"],
        "checkpoint_sha256": checkpoint_sha256,
        "checkpoint_value_float64_le_sha256": value_sha256,
        "event_count": event_count,
        "event_chain_head": event_head,
        "candidate_files_read": [],
        "candidate_files_written": [],
        "arena_verifier_executed": False,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
