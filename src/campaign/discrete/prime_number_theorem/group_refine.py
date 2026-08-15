#!/usr/bin/env python3
"""Full-support refinement of coordinated support exchanges.

`group_exchange.py` cheaply screens hundreds of fixed support topologies in a
bounded compensation subspace.  This second-stage tool takes the best of those
topologies and reoptimizes *all* 1,187 verifier-eligible incumbent coordinates
at once.  It is therefore a topology search, not one-column pricing: every LP
has at least four old support points fixed to zero and the same number of new
support points present.  Any fixed-row gate clearer is separated against the
entire pinned sampled-integer stream before the unchanged verifier is called.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize._highspy._core import _Highs

from audit import LIMIT, direct_rows, recurrence_curve


ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "checkpoints" / "live.json"
OPTIMIZATION = ROOT / "checkpoints" / "optimization.json"
MASK = ROOT / "checkpoints" / "sampled_grid.npy"
EXCHANGE_EVENTS = ROOT / "checkpoints" / "group_exchange.jsonl"
EVENTS = ROOT / "checkpoints" / "group_refine.jsonl"
BEST = ROOT / "group_refine_candidate.json"
FEASIBLE = ROOT / "group_refine_feasible.json"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def append_event(value: dict[str, Any]) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(EVENTS, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "ab") as handle:
        handle.write(canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def atomic_json(path: Path, value: Any) -> None:
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True).encode() + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def coefficients(rows: np.ndarray, keys: np.ndarray) -> np.ndarray:
    return -((rows[:, None] % keys[None, :]) / keys[None, :])


def add_rows(
    highs: _Highs,
    rows: np.ndarray,
    keys: np.ndarray,
    leader_curve: np.ndarray,
    safety: float,
) -> None:
    matrix = coefficients(rows, keys)
    width = len(keys)
    starts = np.arange(0, (len(rows) + 1) * width, width, dtype=np.int32)
    indices = np.tile(np.arange(width, dtype=np.int32), len(rows))
    highs.addRows(
        len(rows),
        np.full(len(rows), -np.inf),
        LIMIT - safety - leader_curve[rows],
        matrix.size,
        starts,
        indices,
        matrix.ravel(),
    )


def exact_live_evaluate(verifier: str, payload: dict[str, Any]) -> float:
    namespace: dict[str, Any] = {}
    exec(compile(verifier, "live_prime_number_verifier.py", "exec"), namespace)
    return float(namespace["evaluate"](payload))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--top-count", type=int, default=24)
    parser.add_argument(
        "--target-ids",
        default="",
        help="comma-separated topology ids; overrides top-count",
    )
    parser.add_argument("--eta", type=float, default=0.01)
    parser.add_argument("--added-bound", type=float, default=2.0)
    parser.add_argument("--safety", type=float, default=5e-9)
    parser.add_argument("--cut-batch", type=int, default=500)
    parser.add_argument("--max-cut-rounds", type=int, default=30)
    parser.add_argument(
        "--force-full",
        action="store_true",
        help="separate selected topologies even when the fixed-row upper bound misses the gate",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.top_count < 1 or args.eta <= 0 or args.safety <= 0:
        raise SystemExit("top-count, eta, and safety must be positive")

    live = json.loads(LIVE.read_text(encoding="utf-8"))
    optimization = json.loads(OPTIMIZATION.read_text(encoding="utf-8"))
    exchange = [json.loads(line) for line in EXCHANGE_EVENTS.read_text().splitlines()]
    source_start = next(
        (
            event
            for event in exchange
            if event.get("run_id") == args.source_run_id
            and event.get("kind") == "run_start"
        ),
        None,
    )
    if source_start is None:
        raise SystemExit(f"unknown exchange run {args.source_run_id}")
    if source_start["verifier_sha256"] != live["verifier_sha256"]:
        raise RuntimeError("source exchange run used a different verifier")
    fixed = [
        event
        for event in exchange
        if event.get("run_id") == args.source_run_id
        and event.get("kind") == "fixed_screen"
        and event.get("status") == "Optimal"
    ]
    unique: dict[str, dict[str, Any]] = {}
    for event in sorted(
        fixed,
        key=lambda item: item["fixed_row_score_upper_bound"],
        reverse=True,
    ):
        unique.setdefault(event["topology_id"], event)
    if args.target_ids:
        requested = [item for item in args.target_ids.split(",") if item]
        missing = [item for item in requested if item not in unique]
        if missing:
            raise RuntimeError(f"unknown or incomplete fixed topology ids: {missing}")
        targets = [unique[item] for item in requested]
    else:
        targets = list(unique.values())[: args.top_count]
    if not targets:
        raise RuntimeError("source run has no completed fixed screens")
    if any(len(event["added"]) < 4 for event in targets):
        raise RuntimeError("refinement target is not a group exchange")

    raw = live["leader"]["data"]["partial_function"]
    all_keys = np.fromiter((int(key) for key in raw), dtype=np.int64)
    leader_values = np.fromiter(raw.values(), dtype=np.float64)
    leader_curve = recurrence_curve(all_keys, leader_values)
    mask = np.load(MASK, allow_pickle=False)
    sampled_rows = np.flatnonzero(mask)
    if len(mask) != 10 * int(all_keys.max()) + 1:
        raise RuntimeError("pinned sampled stream has the wrong reach")
    selected = np.flatnonzero(
        (all_keys <= int(optimization["config"]["key_limit"]))
        | (
            np.abs(leader_values)
            < float(optimization["config"]["absolute_value_limit"])
        )
    )
    keys = all_keys[selected]
    base = leader_values[selected]
    key_to_column = {int(key): index for index, key in enumerate(keys)}
    if any(
        key not in key_to_column
        for target in targets
        for key in target["removed"]
    ):
        raise RuntimeError("a forced removal is outside the eligible support")
    rows = np.asarray(optimization["constraint_rows"], dtype=np.int64)
    row_set = set(map(int, rows))
    row_order = list(map(int, rows))
    leader_score = float(live["leader"]["score"])
    gate_score = leader_score + float(live["problem"]["minImprovement"])
    config = {
        "source_run_id": args.source_run_id,
        "target_ids": [target["topology_id"] for target in targets],
        "top_count": len(targets),
        "selected_count": len(selected),
        "selected_sha256": hashlib.sha256(keys.tobytes()).hexdigest(),
        "eta": args.eta,
        "added_bound": args.added_bound,
        "safety": args.safety,
        "cut_batch": args.cut_batch,
        "max_cut_rounds": args.max_cut_rounds,
        "force_full": args.force_full,
        "recurrence_stability_tolerance": 1e-11,
        "feasible_receipt_version": 1,
        "target_solver": "fresh_ipm_then_simplex_cuts_v1",
    }
    run_id = hashlib.sha256(
        canonical({"config": config, "verifier": live["verifier_sha256"]})
    ).hexdigest()[:20]
    completed = {
        event["topology_id"]
        for event in (
            json.loads(line) for line in EVENTS.read_text().splitlines()
        )
        if event.get("run_id") == run_id and event.get("kind") == "refine_result"
    } if EVENTS.exists() else set()
    append_event(
        {
            "kind": "run_start",
            "run_id": run_id,
            "verifier_sha256": live["verifier_sha256"],
            "leader_id": live["leader"]["id"],
            "leader_score": leader_score,
            "gate_score": gate_score,
            "config": config,
            "external_actions": "none",
        }
    )

    costs = np.log(keys) / keys
    normal_lower = np.maximum(-10.0 - base, -args.eta)
    normal_upper = np.minimum(10.0 - base, args.eta)
    highs = _Highs()
    highs.setOptionValue("output_flag", False)
    highs.setOptionValue("solver", "ipm")
    highs.setOptionValue("run_crossover", "on")
    highs.setOptionValue("primal_feasibility_tolerance", 1e-9)
    highs.setOptionValue("dual_feasibility_tolerance", 1e-9)
    highs.addCols(
        len(keys),
        costs,
        normal_lower,
        normal_upper,
        0,
        np.zeros(len(keys) + 1, dtype=np.int32),
        np.empty(0, dtype=np.int32),
        np.empty(0, dtype=np.float64),
    )
    add_rows(highs, rows, keys, leader_curve, args.safety)
    started = time.monotonic()
    highs.run()
    status = highs.modelStatusToString(highs.getModelStatus())
    if status != "Optimal":
        raise RuntimeError(f"base full-support master failed: {status}")
    append_event(
        {
            "kind": "base_master",
            "run_id": run_id,
            "status": status,
            "score_upper_bound": leader_score - float(highs.getObjectiveValue()),
            "elapsed_seconds": time.monotonic() - started,
        }
    )
    highs.setOptionValue("solver", "simplex")
    highs.setOptionValue("presolve", "off")
    highs.setOptionValue("simplex_strategy", 1)

    best_live: dict[str, Any] | None = None
    for number, target in enumerate(targets, start=1):
        if target["topology_id"] in completed:
            continue
        removed = tuple(map(int, target["removed"]))
        added = tuple(map(int, target["added"]))
        removal_columns = np.asarray(
            [key_to_column[key] for key in removed], dtype=np.int32
        )
        removal_values = -base[removal_columns]
        highs.changeColsBounds(
            len(removal_columns), removal_columns, removal_values, removal_values
        )
        current_rows = np.asarray(row_order, dtype=np.int64)
        current_row_indices = np.arange(len(current_rows), dtype=np.int32)
        for key in added:
            column = coefficients(current_rows, np.asarray([key]))[:, 0]
            highs.addCol(
                float(math.log(key) / key),
                -args.added_bound,
                args.added_bound,
                len(current_rows),
                current_row_indices,
                column,
            )

        # Deleting and adding columns leaves a highly degenerate simplex basis.
        # Reusing that basis made later bundle solves much slower than the first.
        # Discard only solver state (the accumulated valid rows remain), solve the
        # new topology by IPM/crossover, then use simplex solely for new cuts.
        highs.clearSolver()
        highs.setOptionValue("solver", "ipm")
        highs.setOptionValue("presolve", "on")

        history: list[dict[str, Any]] = []
        stable = False
        payload: dict[str, Any] | None = None
        direct_max: float | None = None
        score: float | None = None
        for round_index in range(args.max_cut_rounds):
            started = time.monotonic()
            highs.run()
            status = highs.modelStatusToString(highs.getModelStatus())
            if status != "Optimal":
                history.append({"round": round_index, "status": status})
                break
            solution = np.asarray(highs.getSolution().col_value, dtype=np.float64)
            score_upper = leader_score - float(highs.getObjectiveValue())
            delta = solution[: len(keys)]
            curve = leader_curve + recurrence_curve(
                keys, delta, upper=len(leader_curve) - 1
            )
            curve += recurrence_curve(
                np.asarray(added), solution[len(keys) :], upper=len(leader_curve) - 1
            )
            sampled_max = float(curve[mask].max())
            new_rows: list[int] = []
            if score_upper > gate_score or args.force_full:
                violating = sampled_rows[curve[mask] > LIMIT - args.safety]
                ranked = violating[np.argsort(curve[violating])[::-1]]
                new_rows = [
                    int(row) for row in ranked if int(row) not in row_set
                ][: args.cut_batch]
            record = {
                "round": round_index,
                "status": status,
                "constraint_count": len(row_order),
                "score_upper_bound": score_upper,
                "sampled_max": sampled_max,
                "new_cut_count": len(new_rows),
                "elapsed_seconds": time.monotonic() - started,
            }
            history.append(record)
            append_event(
                {
                    "kind": "refine_round",
                    "run_id": run_id,
                    "topology_id": target["topology_id"],
                    **record,
                }
            )
            if score_upper <= gate_score and not args.force_full:
                break
            if new_rows:
                all_model_keys = np.concatenate((keys, np.asarray(added)))
                add_rows(
                    highs,
                    np.asarray(new_rows),
                    all_model_keys,
                    leader_curve,
                    args.safety,
                )
                row_order.extend(new_rows)
                row_set.update(new_rows)
                highs.setOptionValue("solver", "simplex")
                highs.setOptionValue("presolve", "off")
                highs.setOptionValue("simplex_strategy", 1)
                continue
            # HiGHS can land a few ulps above its row RHS.  Accept only that
            # solver-scale discrepancy here; the independently accumulated
            # direct-row check below still enforces half the safety margin.
            stable = sampled_max <= LIMIT - args.safety + 1e-11
            if stable:
                adjusted = leader_values.copy()
                adjusted[selected] += delta
                partial = {
                    key: float(value)
                    for key, value in zip(raw, adjusted, strict=True)
                    if int(key) not in set(removed)
                }
                for key, value in zip(added, solution[len(keys) :], strict=True):
                    partial[str(key)] = float(value)
                payload = {"partial_function": partial}
                payload_keys = np.fromiter(map(int, partial), dtype=np.int64)
                payload_values = np.fromiter(partial.values(), dtype=np.float64)
                score = -float(
                    np.dot(payload_values, np.log(payload_keys) / payload_keys)
                )
                top_count = min(100_000, len(sampled_rows))
                top = sampled_rows[
                    np.argpartition(curve[sampled_rows], -top_count)[-top_count:]
                ]
                direct_max = float(
                    direct_rows(top, payload_keys, payload_values).max()
                )
            break

        result: dict[str, Any] = {
            "kind": "refine_result",
            "run_id": run_id,
            "topology_id": target["topology_id"],
            "family": target["family"],
            "removed": list(removed),
            "added": list(added),
            "stable": stable,
            "history": history,
            "fixed_stream_score": score,
            "direct_sampled_max": direct_max,
            "payload_sha256": None,
            "live_score": None,
            "gate_cleared": False,
        }
        if payload is not None:
            payload_hash = hashlib.sha256(canonical(payload)).hexdigest()
            result["payload_sha256"] = payload_hash
            if (
                score is not None
                and (score > gate_score or args.force_full)
                and direct_max is not None
                and direct_max <= LIMIT - args.safety / 2
            ):
                live_score = exact_live_evaluate(live["problem"]["verifier"], payload)
                result["live_score"] = live_score
                result["gate_cleared"] = bool(live_score > gate_score)
                feasible_receipt = {
                    "payload": payload,
                    "payload_sha256": payload_hash,
                    "live_score": live_score,
                    "fixed_stream_score": score,
                    "direct_sampled_max": direct_max,
                    "leader_score": leader_score,
                    "gate_score": gate_score,
                    "verifier_sha256": live["verifier_sha256"],
                    "run_id": run_id,
                    "topology": {
                        "family": target["family"],
                        "removed": list(removed),
                        "added": list(added),
                    },
                }
                prior_feasible = (
                    json.loads(FEASIBLE.read_text(encoding="utf-8"))
                    if FEASIBLE.exists()
                    else None
                )
                if (
                    math.isfinite(live_score)
                    and (
                        prior_feasible is None
                        or live_score > float(prior_feasible["live_score"])
                    )
                ):
                    atomic_json(FEASIBLE, feasible_receipt)
                if result["gate_cleared"]:
                    receipt = feasible_receipt
                    atomic_json(BEST, receipt)
                    if best_live is None or live_score > best_live["live_score"]:
                        best_live = receipt
        append_event(result)
        print(
            f"refine {number}/{len(targets)} {target['family']} "
            f"upper={history[-1].get('score_upper_bound')} "
            f"live={result['live_score']}",
            flush=True,
        )

        added_count = len(added)
        highs.deleteCols(
            added_count,
            np.arange(
                highs.getNumCol() - added_count,
                highs.getNumCol(),
                dtype=np.int32,
            ),
        )
        highs.changeColsBounds(
            len(removal_columns),
            removal_columns,
            normal_lower[removal_columns],
            normal_upper[removal_columns],
        )

    append_event(
        {
            "kind": "run_complete",
            "run_id": run_id,
            "target_count": len(targets),
            "gate_cleared": best_live is not None,
            "best_live_score": None if best_live is None else best_live["live_score"],
        }
    )
    print(
        json.dumps(
            {
                "run_id": run_id,
                "target_count": len(targets),
                "gate_cleared": best_live is not None,
                "best_live_score": (
                    None if best_live is None else best_live["live_score"]
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
