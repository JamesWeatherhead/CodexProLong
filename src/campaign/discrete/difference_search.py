#!/usr/bin/env python3
"""Exhaust legal one-edit moves around the live Difference Bases leader."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

import numpy as np


ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "checkpoints" / "difference-bases-live.json"
CHECKPOINT = ROOT / "checkpoints" / "difference-search.json"
BEST = ROOT / "candidates" / "difference-best.json"


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


def load_live() -> tuple[dict[str, Any], str, Callable[[dict[str, Any]], float]]:
    snapshot = json.loads(LIVE.read_text(encoding="utf-8"))
    problem = snapshot["problem"]
    verifier = problem["verifier"]
    digest = hashlib.sha256(verifier.encode()).hexdigest()
    leader = snapshot["solutions"][0]
    namespace: dict[str, Any] = {}
    exec(compile(verifier, "live_difference_verifier.py", "exec"), namespace)
    return leader, digest, namespace["evaluate"]


def coverage(values: list[int]) -> int:
    maximum = values[-1] - values[0]
    seen = np.zeros(maximum + 2, dtype=np.bool_)
    array = np.asarray(values, dtype=np.int64)
    for index, value in enumerate(array[:-1]):
        seen[array[index + 1 :] - value] = True
    missing = np.flatnonzero(~seen[1:])
    return int(missing[0]) if len(missing) else maximum + 1


def score(values: list[int]) -> tuple[float, int]:
    v = coverage(values)
    return (len(values) ** 2 / v if v else float("inf")), v


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-every", type=int, default=10)
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()
    if args.checkpoint_every < 1:
        raise SystemExit("--checkpoint-every must be positive")

    leader, verifier_hash, live_evaluate = load_live()
    baseline = sorted(set(int(x) for x in leader["data"]["set"]))
    baseline_payload = {"set": baseline}
    baseline_hash = hashlib.sha256(canonical(baseline_payload)).hexdigest()
    baseline_live = float(live_evaluate(baseline_payload))
    baseline_score, baseline_v = score(baseline)
    if baseline_live != baseline_score or baseline_live != float(leader["score"]):
        raise RuntimeError("local evaluator does not reproduce the pinned live leader")

    state = {
        "schema": 1,
        "verifier_sha256": verifier_hash,
        "leader_payload_sha256": baseline_hash,
        "baseline_score": baseline_live,
        "baseline_coverage": baseline_v,
        "next_remove_index": 0,
        "remove_candidates_checked": 0,
        "swap_candidates_checked": 0,
        "best_delete": None,
        "best_swap": None,
        "complete": False,
    }
    if CHECKPOINT.exists() and not args.restart:
        previous = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        for key in ("verifier_sha256", "leader_payload_sha256"):
            if previous.get(key) != state[key]:
                raise RuntimeError(f"checkpoint {key} does not match live snapshot")
        state.update(previous)
        if state["complete"]:
            print(json.dumps(state, indent=2, sort_keys=True))
            return

    best_payload: dict[str, Any] | None = None
    if BEST.exists():
        best_payload = json.loads(BEST.read_text(encoding="utf-8"))

    target = baseline_v + 1
    baseline_set = set(baseline)
    baseline_array = np.asarray(baseline, dtype=np.int64)
    difference_counts = np.zeros(baseline[-1] - baseline[0] + 1, dtype=np.uint16)
    for index, value in enumerate(baseline_array[:-1]):
        difference_counts[baseline_array[index + 1 :] - value] += 1
    for remove_index in range(int(state["next_remove_index"]), len(baseline)):
        removed = baseline[remove_index]
        remaining = baseline[:remove_index] + baseline[remove_index + 1 :]
        remaining_set = baseline_set - {removed}
        remaining_array = np.asarray(remaining, dtype=np.int64)
        removed_contribution = np.bincount(
            np.abs(remaining_array - removed), minlength=len(difference_counts)
        )[: len(difference_counts)]
        after_remove = difference_counts.astype(np.int32) - removed_contribution
        missing_after_remove = np.flatnonzero(after_remove[1 : baseline_v + 1] == 0)
        delete_v = int(missing_after_remove[0]) if len(missing_after_remove) else baseline_v
        delete_score = len(remaining) ** 2 / delete_v if delete_v else float("inf")
        state["remove_candidates_checked"] += 1
        delete_record = {"removed": removed, "score": delete_score, "coverage": delete_v}
        if state["best_delete"] is None or delete_score < state["best_delete"]["score"]:
            state["best_delete"] = delete_record

        additions: set[int] = set()
        for witness in remaining:
            additions.add(witness + target)
            if witness >= target:
                additions.add(witness - target)
        additions.difference_update(remaining_set)

        for added in sorted(additions):
            state["swap_candidates_checked"] += 1
            new_differences = np.unique(np.abs(remaining_array - added))
            required = np.append(missing_after_remove + 1, target)
            if not np.all(np.isin(required, new_differences, assume_unique=False)):
                continue
            candidate = sorted([*remaining, added])
            candidate_score, candidate_v = score(candidate)
            if candidate_v < target:
                raise RuntimeError("deficit filter admitted a prefix-breaking swap")
            live_score = float(live_evaluate({"set": candidate}))
            if live_score != candidate_score:
                raise RuntimeError("live verifier/local score disagreement")
            record = {
                "removed": removed,
                "added": added,
                "score": live_score,
                "coverage": candidate_v,
            }
            if state["best_swap"] is None or live_score < state["best_swap"]["score"]:
                state["best_swap"] = record
                best_payload = {"set": candidate}
                atomic_json(BEST, best_payload)

        state["next_remove_index"] = remove_index + 1
        if state["next_remove_index"] % args.checkpoint_every == 0:
            atomic_json(CHECKPOINT, state)

    # Exhaust all legal one-add moves that can cover the first missing value.
    one_add_best = None
    additions: set[int] = set()
    for witness in baseline:
        additions.add(witness + target)
        if witness >= target:
            additions.add(witness - target)
    additions.difference_update(baseline_set)
    for added in sorted(additions):
        new_differences = np.abs(baseline_array - added)
        seen = difference_counts > 0
        if int(np.max(new_differences)) >= len(seen):
            seen = np.pad(seen, (0, int(np.max(new_differences)) - len(seen) + 2))
        seen[new_differences] = True
        missing = np.flatnonzero(~seen[1:])
        candidate_v = int(missing[0]) if len(missing) else len(seen) - 1
        candidate_score = (len(baseline) + 1) ** 2 / candidate_v
        if one_add_best is None or candidate_score < one_add_best["score"]:
            one_add_best = {"added": added, "score": candidate_score, "coverage": candidate_v}
    state["one_add_candidates_checked"] = len(additions)
    state["best_add"] = one_add_best
    state["gate_score"] = baseline_live - 1e-9
    state["gate_cleared"] = bool(
        state["best_swap"] and state["best_swap"]["score"] < state["gate_score"]
    )
    state["complete"] = True
    atomic_json(CHECKPOINT, state)
    print(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
