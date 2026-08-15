#!/usr/bin/env python3
"""Coordinated support-exchange search around the fixed-stream feasible point.

This is deliberately not one-column pricing or column generation.  Every
screen fixes a complete, pre-generated support topology containing a 4-, 8-,
or 12-key exchange.  The fixed-row LP is only a relaxation; promising
topologies are rebuilt and cut against the complete official sampled-integer
stream before the unmodified verifier is invoked.
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
from typing import Any, Iterable

import numpy as np
from scipy.optimize._highspy._core import _Highs

from audit import LIMIT, direct_rows, recurrence_curve


ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "checkpoints" / "live.json"
DATABASE = ROOT / "checkpoints" / "database.json"
OPTIMIZATION = ROOT / "checkpoints" / "optimization.json"
MASK = ROOT / "checkpoints" / "sampled_grid.npy"
BASE_PAYLOAD = ROOT / "best_feasible.json"
EVENTS = ROOT / "checkpoints" / "group_exchange.jsonl"
BEST = ROOT / "group_exchange_candidate.json"


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


def append_event(value: dict[str, Any]) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(EVENTS, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(descriptor, "ab") as handle:
            handle.write(canonical(value) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        os.close(descriptor)
        raise


def coefficients(rows: np.ndarray, keys: np.ndarray) -> np.ndarray:
    return -((rows[:, None] % keys[None, :]) / keys[None, :])


def add_rows(
    highs: _Highs,
    rows: np.ndarray,
    variable_keys: np.ndarray,
    added_keys: np.ndarray,
    base_curve: np.ndarray,
    safety: float,
) -> None:
    keys = np.concatenate((variable_keys, added_keys))
    matrix = coefficients(rows, keys)
    width = len(keys)
    starts = np.arange(0, (len(rows) + 1) * width, width, dtype=np.int32)
    indices = np.tile(np.arange(width, dtype=np.int32), len(rows))
    highs.addRows(
        len(rows),
        np.full(len(rows), -np.inf),
        LIMIT - safety - base_curve[rows],
        matrix.size,
        starts,
        indices,
        matrix.ravel(),
    )


def make_model(
    base_keys: np.ndarray,
    base_values: np.ndarray,
    flexible: np.ndarray,
    removed: tuple[int, ...],
    added: tuple[int, ...],
    rows: np.ndarray,
    base_curve: np.ndarray,
    eta: float,
    added_bound: float,
    safety: float,
    *,
    solver: str,
) -> _Highs:
    removed_set = set(removed)
    variable_keys = base_keys[flexible]
    variable_base = base_values[flexible]
    lower = np.maximum(-10.0 - variable_base, -eta)
    upper = np.minimum(10.0 - variable_base, eta)
    key_to_index = {int(key): index for index, key in enumerate(variable_keys)}
    for key in removed_set:
        if key not in key_to_index:
            raise ValueError(f"removed key {key} is outside the flexible set")
        index = key_to_index[key]
        lower[index] = -variable_base[index]
        upper[index] = -variable_base[index]
    added_array = np.asarray(added, dtype=np.int64)
    keys = np.concatenate((variable_keys, added_array))
    costs = np.log(keys) / keys
    lower = np.concatenate((lower, np.full(len(added), -added_bound)))
    upper = np.concatenate((upper, np.full(len(added), added_bound)))

    highs = _Highs()
    highs.setOptionValue("output_flag", False)
    highs.setOptionValue("solver", solver)
    highs.setOptionValue("run_crossover", "on")
    highs.setOptionValue("primal_feasibility_tolerance", 1e-9)
    highs.setOptionValue("dual_feasibility_tolerance", 1e-9)
    highs.addCols(
        len(keys),
        costs,
        lower,
        upper,
        0,
        np.zeros(len(keys) + 1, dtype=np.int32),
        np.empty(0, dtype=np.int32),
        np.empty(0, dtype=np.float64),
    )
    add_rows(highs, rows, variable_keys, added_array, base_curve, safety)
    return highs


def normalize_group(values: Iterable[int], support: set[int], maximum: int) -> tuple[int, ...] | None:
    group = tuple(sorted(set(map(int, values))))
    if not group or len(group) != len(tuple(values)):
        return None
    if min(group) < 2 or max(group) > maximum or support.intersection(group):
        return None
    return group


def generate_topologies(
    base_keys: np.ndarray,
    base_values: np.ndarray,
    database: dict[str, Any],
    sizes: list[int],
) -> list[dict[str, Any]]:
    support = set(map(int, base_keys))
    maximum = int(base_keys.max())
    removable_order = [
        int(base_keys[index])
        for index in np.argsort(np.abs(base_values))
        if int(base_keys[index]) != maximum
    ]
    removals: dict[int, list[tuple[str, tuple[int, ...]]]] = {}
    for size in sizes:
        choices = [("smallest", tuple(removable_order[:size]))]
        if len(removable_order) >= 3 * size:
            choices.append(("small_2", tuple(removable_order[size : 2 * size])))
            choices.append(("small_3", tuple(removable_order[2 * size : 3 * size])))
        removals[size] = choices

    additions: dict[int, list[tuple[str, tuple[int, ...]]]] = {size: [] for size in sizes}
    tail = np.asarray(sorted(key for key in support if key >= 112_000), dtype=np.int64)
    shifts = (-97, -43, -19, -7, -3, -1, 1, 3, 7, 19, 43, 97)
    for size in sizes:
        step = max(1, size // 2)
        for start in range(0, len(tail) - size + 1, step):
            window = tail[start : start + size]
            for shift in shifts:
                group = normalize_group(window + shift, support, maximum)
                if group is not None:
                    additions[size].append((f"tail_shift_{shift:+d}", group))

    # Fill individual large gaps with an entire coordinated bundle.
    ordered = np.asarray(sorted(support), dtype=np.int64)
    gaps = sorted(
        ((int(right - left), int(left), int(right)) for left, right in zip(ordered[:-1], ordered[1:], strict=True)),
        reverse=True,
    )
    for size in sizes:
        for _, left, right in gaps[:80]:
            raw = np.rint(np.linspace(left, right, size + 2)[1:-1]).astype(np.int64)
            group = normalize_group(raw, support, maximum)
            if group is not None:
                additions[size].append(("gap_fill", group))

    # Public historical basins provide group priors without single-key prices.
    historical_ids = (2467, 2459, 2434, 2397, 2394, 2392, 2386)
    rows_by_id = {int(row["id"]): row for row in database["solutions"]}
    for historical_id in historical_ids:
        raw = rows_by_id[historical_id]["data"]["partial_function"]
        absent = sorted(set(map(int, raw)) - support)
        for size in sizes:
            for start in range(0, len(absent) - size + 1, size):
                group = normalize_group(absent[start : start + size], support, maximum)
                if group is not None:
                    additions[size].append((f"historical_{historical_id}", group))

    # Partial reversals of the observed 21-for-21 and 54-for-54 basin changes.
    special: list[dict[str, Any]] = []
    for historical_id in (2467, 2459, 2434):
        historical = set(map(int, rows_by_id[historical_id]["data"]["partial_function"]))
        current_only = sorted(support - historical)
        old_only = sorted(historical - support)
        for size in sizes:
            for start in range(0, min(len(current_only), len(old_only)) - size + 1, size):
                special.append(
                    {
                        "family": f"historical_reverse_{historical_id}",
                        "removed": tuple(current_only[start : start + size]),
                        "added": tuple(old_only[start : start + size]),
                    }
                )

    topologies: list[dict[str, Any]] = []
    for size in sizes:
        seen_additions: set[tuple[int, ...]] = set()
        for family, added in additions[size]:
            if added in seen_additions:
                continue
            seen_additions.add(added)
            for removal_name, removed in removals[size]:
                topologies.append(
                    {
                        "family": f"{family}:{removal_name}",
                        "removed": removed,
                        "added": added,
                    }
                )
    topologies.extend(special)
    for topology in topologies:
        identifying = {
            "family": topology["family"],
            "removed": topology["removed"],
            "added": topology["added"],
        }
        topology["id"] = hashlib.sha256(canonical(identifying)).hexdigest()[:20]
    unique = {topology["id"]: topology for topology in topologies}
    return list(unique.values())


def payload_from_solution(
    raw: dict[str, float],
    base_keys: np.ndarray,
    base_values: np.ndarray,
    flexible: np.ndarray,
    removed: tuple[int, ...],
    added: tuple[int, ...],
    solution: np.ndarray,
) -> dict[str, Any]:
    removed_set = set(removed)
    partial: dict[str, float] = {}
    adjusted = base_values.copy()
    adjusted[flexible] += solution[: len(flexible)]
    for key, value in zip(base_keys, adjusted, strict=True):
        if int(key) not in removed_set:
            partial[str(int(key))] = float(value)
    for key, value in zip(added, solution[len(flexible) :], strict=True):
        partial[str(int(key))] = float(value)
    if len(partial) != len(raw):
        raise RuntimeError("support exchange did not preserve raw cardinality")
    return {"partial_function": partial}


def exact_live_evaluate(verifier: str, payload: dict[str, Any]) -> float:
    namespace: dict[str, Any] = {}
    exec(compile(verifier, "live_prime_number_verifier.py", "exec"), namespace)
    return float(namespace["evaluate"](payload))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", default="4,8,12")
    parser.add_argument("--max-groups", type=int, default=300)
    parser.add_argument("--relaxed-rows", type=int, default=700)
    parser.add_argument("--flexible-limit", type=int, default=450)
    parser.add_argument("--eta", type=float, default=0.003)
    parser.add_argument("--added-bound", type=float, default=2.0)
    parser.add_argument("--screen-safety", type=float, default=3e-10)
    parser.add_argument("--full-safety", type=float, default=5e-9)
    parser.add_argument("--fixed-row-topologies", type=int, default=60)
    parser.add_argument("--full-topologies", type=int, default=8)
    parser.add_argument("--cut-batch", type=int, default=500)
    parser.add_argument("--max-cut-rounds", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sizes = [int(item) for item in args.sizes.split(",") if item]
    if not sizes or min(sizes) < 4 or any(size > 32 for size in sizes):
        raise SystemExit("exchange sizes must be between 4 and 32")

    live = json.loads(LIVE.read_text(encoding="utf-8"))
    database = json.loads(DATABASE.read_text(encoding="utf-8"))
    optimization = json.loads(OPTIMIZATION.read_text(encoding="utf-8"))
    base_payload = json.loads(BASE_PAYLOAD.read_text(encoding="utf-8"))
    raw = base_payload["partial_function"]
    base_keys = np.fromiter((int(key) for key in raw), dtype=np.int64)
    base_values = np.fromiter(raw.values(), dtype=np.float64)
    base_score = -float(np.dot(base_values, np.log(base_keys) / base_keys))
    base_hash = hashlib.sha256(canonical(base_payload)).hexdigest()
    mask = np.load(MASK, allow_pickle=False)
    if len(raw) != 2000 or int(base_keys.max()) != int(live["leader"]["data"]["partial_function"] and max(map(int, live["leader"]["data"]["partial_function"]))):
        raise RuntimeError("base support cardinality or reach changed")
    if len(mask) != 10 * int(base_keys.max()) + 1:
        raise RuntimeError("official sampled grid does not match candidate reach")
    base_curve = recurrence_curve(base_keys, base_values)
    sampled_rows = np.flatnonzero(mask)
    initial_rows = np.asarray(optimization["constraint_rows"], dtype=np.int64)
    leader_score = float(live["leader"]["score"])
    gate_score = leader_score + float(live["problem"]["minImprovement"])
    leader_raw = live["leader"]["data"]["partial_function"]
    leader_keys = np.fromiter((int(key) for key in leader_raw), dtype=np.int64)
    leader_values = np.fromiter(leader_raw.values(), dtype=np.float64)
    eligible = np.flatnonzero(
        (leader_keys <= int(optimization["config"]["key_limit"]))
        | (np.abs(leader_values) < float(optimization["config"]["absolute_value_limit"]))
    )
    if not np.array_equal(base_keys, leader_keys):
        raise RuntimeError("base and leader key orders differ")

    topologies = generate_topologies(base_keys, base_values, database, sizes)
    eligible_keys = set(map(int, base_keys[eligible]))
    topologies = [
        topology
        for topology in topologies
        if set(topology["removed"]).issubset(eligible_keys)
    ]
    # Stratify before truncating.  The generator naturally emits all tail
    # translations first, which would otherwise crowd gap-fill and historical
    # basin bundles out of a bounded run.
    topology_buckets: dict[tuple[int, str, str], list[dict[str, Any]]] = {}
    for topology in topologies:
        family = topology["family"]
        if ":" in family:
            addition_family, removal_family = family.rsplit(":", 1)
        else:
            addition_family, removal_family = family, "paired"
        bucket = (len(topology["removed"]), removal_family, addition_family)
        topology_buckets.setdefault(bucket, []).append(topology)
    interleaved = []
    for index in range(max(map(len, topology_buckets.values()), default=0)):
        for bucket in sorted(topology_buckets):
            if index < len(topology_buckets[bucket]):
                interleaved.append(topology_buckets[bucket][index])
    topologies = interleaved[: args.max_groups]
    required_removals = {
        key for topology in topologies for key in topology["removed"]
    }
    leader_delta = np.abs(base_values - leader_values)
    preferred = list(
        map(
            int,
            eligible[
                np.argsort(leader_delta[eligible])[::-1]
            ],
        )
    )
    removal_indices = {
        int(index) for index in eligible if int(base_keys[index]) in required_removals
    }
    # Preserve every forced-removal coordinate, then seed a bounded set of the
    # highest-leverage low keys before filling by movement in the exact-feasible
    # incumbent.  This makes --flexible-limit an actual cap instead of silently
    # expanding to hundreds of keys <=500.
    low_key_indices = sorted(
        (int(index) for index in eligible if int(base_keys[index]) <= 500),
        key=lambda index: int(base_keys[index]),
    )[:64]
    mandatory_indices = set(removal_indices)
    for index in low_key_indices:
        if len(mandatory_indices) >= args.flexible_limit:
            break
        mandatory_indices.add(index)
    flexible_indices = list(sorted(mandatory_indices))
    for index in preferred:
        if index not in mandatory_indices:
            flexible_indices.append(index)
        if len(flexible_indices) >= max(args.flexible_limit, len(mandatory_indices)):
            break
    flexible = np.asarray(sorted(set(flexible_indices)), dtype=np.int64)
    config = {
        "sizes": sizes,
        "max_groups": args.max_groups,
        "relaxed_rows": args.relaxed_rows,
        "flexible_limit": args.flexible_limit,
        "flexible_count": len(flexible),
        "flexible_keys_sha256": hashlib.sha256(base_keys[flexible].tobytes()).hexdigest(),
        "eta": args.eta,
        "added_bound": args.added_bound,
        "screen_safety": args.screen_safety,
        "full_safety": args.full_safety,
        "fixed_row_topologies": args.fixed_row_topologies,
        "topology_selection": "round_robin_size_removal_addition_family_v1",
        "flexible_selection": "all_removals_plus_64_low_keys_then_incumbent_delta_v1",
        "fixed_selection": "round_robin_exchange_size_and_removal_family_v1",
        "full_topologies": args.full_topologies,
        "cut_batch": args.cut_batch,
        "max_cut_rounds": args.max_cut_rounds,
        "topology_ids": [topology["id"] for topology in topologies],
    }
    run_id = hashlib.sha256(
        canonical(
            {
                "config": config,
                "verifier": live["verifier_sha256"],
                "base": base_hash,
                "database": database["solutions_sha256"],
            }
        )
    ).hexdigest()[:20]
    completed: dict[str, dict[str, Any]] = {}
    if EVENTS.exists():
        for line in EVENTS.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("run_id") == run_id and event.get("kind") == "screen":
                completed[event["topology_id"]] = event
    append_event(
        {
            "kind": "run_start",
            "run_id": run_id,
            "verifier_sha256": live["verifier_sha256"],
            "leader_id": live["leader"]["id"],
            "leader_score": leader_score,
            "gate_score": gate_score,
            "base_score": base_score,
            "base_payload_sha256": base_hash,
            "database_sha256": database["solutions_sha256"],
            "config": config,
            "external_actions": "none",
        }
    )

    screens = list(completed.values())
    relaxed_count = min(args.relaxed_rows, len(initial_rows))
    relaxed_rows = initial_rows[
        np.argpartition(base_curve[initial_rows], -relaxed_count)[-relaxed_count:]
    ]
    # One persistent master makes the group screen practical: only the complete
    # removal bounds and bundled addition columns change between topologies.
    screen_master = make_model(
        base_keys,
        base_values,
        flexible,
        (),
        (),
        relaxed_rows,
        base_curve,
        args.eta,
        args.added_bound,
        args.screen_safety,
        solver="ipm",
    )
    screen_master.run()
    if screen_master.modelStatusToString(screen_master.getModelStatus()) != "Optimal":
        raise RuntimeError("relaxed base master failed")
    screen_master.setOptionValue("solver", "simplex")
    screen_master.setOptionValue("presolve", "off")
    screen_master.setOptionValue("simplex_strategy", 1)
    variable_keys = base_keys[flexible]
    variable_base = base_values[flexible]
    variable_costs = np.log(variable_keys) / variable_keys
    normal_lower = np.maximum(-10.0 - variable_base, -args.eta)
    normal_upper = np.minimum(10.0 - variable_base, args.eta)
    variable_index = {int(key): index for index, key in enumerate(variable_keys)}
    row_indices = np.arange(len(relaxed_rows), dtype=np.int32)
    for number, topology in enumerate(topologies, start=1):
        if topology["id"] in completed:
            continue
        started = time.monotonic()
        removal_indices = np.asarray(
            [variable_index[key] for key in topology["removed"]], dtype=np.int32
        )
        removal_values = -variable_base[removal_indices]
        screen_master.changeColsBounds(
            len(removal_indices), removal_indices, removal_values, removal_values
        )
        for key in topology["added"]:
            column = coefficients(relaxed_rows, np.asarray([key], dtype=np.int64))[:, 0]
            screen_master.addCol(
                float(math.log(key) / key),
                -args.added_bound,
                args.added_bound,
                len(relaxed_rows),
                row_indices,
                column,
            )
        screen_master.run()
        status = screen_master.modelStatusToString(screen_master.getModelStatus())
        gain = -float(screen_master.getObjectiveValue()) if status == "Optimal" else None
        event = {
            "kind": "screen",
            "run_id": run_id,
            "topology_id": topology["id"],
            "family": topology["family"],
            "removed": list(topology["removed"]),
            "added": list(topology["added"]),
            "status": status,
            "fixed_row_score_gain_from_base": gain,
            "fixed_row_score_upper_bound": base_score + gain if gain is not None else None,
            "gate_possible": bool(gain is not None and base_score + gain > gate_score),
            "elapsed_seconds": time.monotonic() - started,
        }
        append_event(event)
        screens.append(event)
        print(
            f"screen {number}/{len(topologies)} {topology['family']} "
            f"score={event['fixed_row_score_upper_bound']} gate={event['gate_possible']}",
            flush=True,
        )
        added_count = len(topology["added"])
        screen_master.deleteCols(
            added_count,
            np.arange(
                screen_master.getNumCol() - added_count,
                screen_master.getNumCol(),
                dtype=np.int32,
            ),
        )
        screen_master.changeColsBounds(
            len(removal_indices),
            removal_indices,
            normal_lower[removal_indices],
            normal_upper[removal_indices],
        )

    viable = [event for event in screens if event.get("gate_possible")]
    viable.sort(key=lambda event: event["fixed_row_score_upper_bound"], reverse=True)
    append_event(
        {
            "kind": "screen_summary",
            "run_id": run_id,
            "screened": len(screens),
            "viable": len(viable),
            "best_fixed_row_score_upper_bound": max(
                (event["fixed_row_score_upper_bound"] for event in screens if event["fixed_row_score_upper_bound"] is not None),
                default=None,
            ),
        }
    )

    by_id = {topology["id"]: topology for topology in topologies}
    fixed_screens: list[dict[str, Any]] = []
    prior_fixed: dict[str, dict[str, Any]] = {}
    if EVENTS.exists():
        for line in EVENTS.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("run_id") == run_id and event.get("kind") == "fixed_screen":
                prior_fixed[event["topology_id"]] = event
    fixed_master = make_model(
        base_keys,
        base_values,
        flexible,
        (),
        (),
        initial_rows,
        base_curve,
        args.eta,
        args.added_bound,
        args.screen_safety,
        # This fixed-row relaxation is extremely degenerate.  HiGHS' IPM can
        # spend minutes in crossover here, while dual simplex reaches the same
        # reusable-master optimum promptly.
        solver="simplex",
    )
    fixed_master.run()
    if fixed_master.modelStatusToString(fixed_master.getModelStatus()) != "Optimal":
        raise RuntimeError("fixed-row base master failed")
    fixed_master.setOptionValue("solver", "simplex")
    fixed_master.setOptionValue("presolve", "off")
    fixed_master.setOptionValue("simplex_strategy", 1)
    fixed_row_indices = np.arange(len(initial_rows), dtype=np.int32)
    fixed_buckets: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for event in viable:
        topology = by_id[event["topology_id"]]
        removal_family = topology["family"].rsplit(":", 1)[-1]
        fixed_buckets.setdefault((len(topology["removed"]), removal_family), []).append(event)
    fixed_candidates: list[dict[str, Any]] = []
    for index in range(max(map(len, fixed_buckets.values()), default=0)):
        for bucket in sorted(fixed_buckets):
            if index < len(fixed_buckets[bucket]):
                fixed_candidates.append(fixed_buckets[bucket][index])
                if len(fixed_candidates) >= args.fixed_row_topologies:
                    break
        if len(fixed_candidates) >= args.fixed_row_topologies:
            break
    for coarse in fixed_candidates:
        topology = by_id[coarse["topology_id"]]
        if topology["id"] in prior_fixed:
            fixed_screens.append(prior_fixed[topology["id"]])
            continue
        started = time.monotonic()
        removal_indices = np.asarray(
            [variable_index[key] for key in topology["removed"]], dtype=np.int32
        )
        removal_values = -variable_base[removal_indices]
        fixed_master.changeColsBounds(
            len(removal_indices), removal_indices, removal_values, removal_values
        )
        for key in topology["added"]:
            column = coefficients(initial_rows, np.asarray([key], dtype=np.int64))[:, 0]
            fixed_master.addCol(
                float(math.log(key) / key),
                -args.added_bound,
                args.added_bound,
                len(initial_rows),
                fixed_row_indices,
                column,
            )
        fixed_master.run()
        status = fixed_master.modelStatusToString(fixed_master.getModelStatus())
        gain = -float(fixed_master.getObjectiveValue()) if status == "Optimal" else None
        event = {
            "kind": "fixed_screen",
            "run_id": run_id,
            "topology_id": topology["id"],
            "family": topology["family"],
            "removed": list(topology["removed"]),
            "added": list(topology["added"]),
            "status": status,
            "fixed_row_score_gain_from_base": gain,
            "fixed_row_score_upper_bound": base_score + gain if gain is not None else None,
            "gate_possible": bool(gain is not None and base_score + gain > gate_score),
            "elapsed_seconds": time.monotonic() - started,
        }
        append_event(event)
        fixed_screens.append(event)
        print(
            f"fixed {topology['family']} score={event['fixed_row_score_upper_bound']} "
            f"gate={event['gate_possible']}",
            flush=True,
        )
        added_count = len(topology["added"])
        fixed_master.deleteCols(
            added_count,
            np.arange(
                fixed_master.getNumCol() - added_count,
                fixed_master.getNumCol(),
                dtype=np.int32,
            ),
        )
        fixed_master.changeColsBounds(
            len(removal_indices),
            removal_indices,
            normal_lower[removal_indices],
            normal_upper[removal_indices],
        )
    fixed_viable = [event for event in fixed_screens if event.get("gate_possible")]
    fixed_viable.sort(key=lambda event: event["fixed_row_score_upper_bound"], reverse=True)
    append_event(
        {
            "kind": "fixed_screen_summary",
            "run_id": run_id,
            "screened": len(fixed_screens),
            "viable": len(fixed_viable),
            "best_fixed_row_score_upper_bound": max(
                (
                    event["fixed_row_score_upper_bound"]
                    for event in fixed_screens
                    if event["fixed_row_score_upper_bound"] is not None
                ),
                default=None,
            ),
        }
    )
    best_exact: dict[str, Any] | None = None
    for screen in fixed_viable[: args.full_topologies]:
        topology = by_id[screen["topology_id"]]
        row_order = list(map(int, initial_rows))
        row_set = set(row_order)
        full_history = []
        solution: np.ndarray | None = None
        curve: np.ndarray | None = None
        stable = False
        for round_index in range(args.max_cut_rounds):
            started = time.monotonic()
            highs = make_model(
                base_keys,
                base_values,
                flexible,
                topology["removed"],
                topology["added"],
                np.asarray(row_order, dtype=np.int64),
                base_curve,
                args.eta,
                args.added_bound,
                args.full_safety,
                solver="ipm",
            )
            highs.run()
            status = highs.modelStatusToString(highs.getModelStatus())
            if status != "Optimal":
                full_history.append({"round": round_index, "status": status})
                break
            solution = np.asarray(highs.getSolution().col_value, dtype=np.float64)
            variable_keys = base_keys[flexible]
            curve = base_curve + recurrence_curve(variable_keys, solution[: len(flexible)], upper=len(base_curve) - 1)
            curve += recurrence_curve(np.asarray(topology["added"], dtype=np.int64), solution[len(flexible) :], upper=len(base_curve) - 1)
            sampled_values = curve[mask]
            sampled_maximum = float(sampled_values.max())
            gain = -float(highs.getObjectiveValue())
            violating = sampled_rows[sampled_values > LIMIT - args.full_safety]
            ranked = violating[np.argsort(curve[violating])[::-1]]
            new_rows = [int(row) for row in ranked if int(row) not in row_set][: args.cut_batch]
            record = {
                "round": round_index,
                "status": status,
                "constraint_count": len(row_order),
                "score": base_score + gain,
                "score_gain_from_base": gain,
                "sampled_max": sampled_maximum,
                "new_cut_count": len(new_rows),
                "elapsed_seconds": time.monotonic() - started,
            }
            full_history.append(record)
            append_event(
                {
                    "kind": "full_cut_round",
                    "run_id": run_id,
                    "topology_id": topology["id"],
                    **record,
                }
            )
            if not new_rows:
                stable = sampled_maximum <= LIMIT - args.full_safety
                break
            row_order.extend(new_rows)
            row_set.update(new_rows)

        exact_record: dict[str, Any] = {
            "kind": "full_result",
            "run_id": run_id,
            "topology_id": topology["id"],
            "family": topology["family"],
            "removed": list(topology["removed"]),
            "added": list(topology["added"]),
            "stable": stable,
            "rounds": len(full_history),
            "history": full_history,
            "live_score": None,
            "gate_cleared": False,
        }
        if stable and solution is not None and curve is not None:
            payload = payload_from_solution(raw, base_keys, base_values, flexible, topology["removed"], topology["added"], solution)
            # Recurrence is used for separation; direct rows remove cumulative drift.
            top_count = min(100_000, len(sampled_rows))
            top = sampled_rows[np.argpartition(curve[sampled_rows], -top_count)[-top_count:]]
            candidate_keys = np.fromiter((int(key) for key in payload["partial_function"]), dtype=np.int64)
            candidate_values = np.fromiter(payload["partial_function"].values(), dtype=np.float64)
            direct_max = float(direct_rows(top, candidate_keys, candidate_values).max())
            score = -float(np.dot(candidate_values, np.log(candidate_keys) / candidate_keys))
            exact_record.update(
                {
                    "direct_sampled_max": direct_max,
                    "fixed_stream_score": score,
                    "payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
                }
            )
            if direct_max <= LIMIT - args.full_safety / 2 and score > gate_score:
                live_score = exact_live_evaluate(live["problem"]["verifier"], payload)
                exact_record["live_score"] = live_score
                exact_record["gate_cleared"] = bool(live_score > gate_score)
                if exact_record["gate_cleared"]:
                    candidate = {
                        "payload": payload,
                        "payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(),
                        "live_score": live_score,
                        "leader_score": leader_score,
                        "gate_score": gate_score,
                        "verifier_sha256": live["verifier_sha256"],
                        "topology": {
                            "family": topology["family"],
                            "removed": list(topology["removed"]),
                            "added": list(topology["added"]),
                        },
                    }
                    atomic_json(BEST, candidate)
                    if best_exact is None or live_score > best_exact["live_score"]:
                        best_exact = candidate
        append_event(exact_record)
        print(json.dumps(exact_record, sort_keys=True), flush=True)

    append_event(
        {
            "kind": "run_complete",
            "run_id": run_id,
            "screened": len(screens),
            "viable": len(viable),
            "fixed_screened": len(fixed_screens),
            "fixed_viable": len(fixed_viable),
            "full_attempted": min(len(fixed_viable), args.full_topologies),
            "gate_cleared": best_exact is not None,
            "best_live_score": None if best_exact is None else best_exact["live_score"],
        }
    )
    print(
        json.dumps(
            {
                "run_id": run_id,
                "screened": len(screens),
                "viable": len(viable),
                "fixed_screened": len(fixed_screens),
                "fixed_viable": len(fixed_viable),
                "best_fixed_row_score_upper_bound": max(
                    (
                        event["fixed_row_score_upper_bound"]
                        for event in fixed_screens
                        if event["fixed_row_score_upper_bound"] is not None
                    ),
                    default=None,
                ),
                "gate_cleared": best_exact is not None,
                "best_live_score": None if best_exact is None else best_exact["live_score"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
