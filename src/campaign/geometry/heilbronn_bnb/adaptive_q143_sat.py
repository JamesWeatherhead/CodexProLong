#!/usr/bin/env python3
"""Checkpointed exact adaptive q=143 Heilbronn search using SAT.

Each public geometry is rounded to the q-grid and receives small per-label
hexagonal windows.  Exact forbidden determinant triples become guarded CNF
clauses.  Unsatisfiable cores choose which label windows are expanded next;
the active triple topology itself is never fixed.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from lattice_bnb import (
    COUNT,
    DEFAULT_SNAPSHOT,
    SLUG,
    atomic_json,
    determinant_numerator,
    exact_grid_score,
    load_snapshot,
    selected_payload,
    threshold_numerator,
)
from pysat.solvers import Solver
from scipy.spatial import ConvexHull, QhullError

DENOMINATOR = 143
RADIUS_SCHEDULE = (2, 3, 5, 8)


def append_event(path: Path, **event: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def cartesian_to_barycentric(points: list[list[float]]) -> np.ndarray:
    cartesian = np.asarray(points, dtype=np.float64)
    third = 2.0 * cartesian[:, 1] / math.sqrt(3.0)
    second = cartesian[:, 0] - 0.5 * third
    first = 1.0 - second - third
    barycentric = np.column_stack((first, second, third))
    barycentric[np.abs(barycentric) < 1e-12] = 0.0
    if np.any(barycentric < -1e-9):
        raise ValueError("public seed lies outside the equilateral triangle")
    return np.maximum(barycentric, 0.0)


def nearest_grid(barycentric: np.ndarray, denominator: int) -> np.ndarray:
    rounded = []
    for row in barycentric:
        scaled = row * denominator
        base = np.floor(scaled + 1e-12).astype(np.int64)
        needed = denominator - int(base.sum())
        if needed < 0 or needed > 2:
            raise ValueError("invalid largest-remainder rounding state")
        order = np.argsort(-(scaled - base))
        base[order[:needed]] += 1
        if np.any(base < 0) or int(base.sum()) != denominator:
            raise ValueError("rounded barycentric point is invalid")
        rounded.append(base)
    return np.asarray(rounded, dtype=np.int64)


def canonical_center_key(grid: np.ndarray) -> tuple[tuple[int, int, int], ...]:
    variants = []
    for permutation in itertools.permutations(range(3)):
        variants.append(
            tuple(sorted(tuple(map(int, row)) for row in grid[:, permutation]))
        )
    return min(variants)


def distinct_public_seeds(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    by_key: dict[tuple[tuple[int, int, int], ...], dict[str, Any]] = {}
    for solution in snapshot["solutions"]:
        center = nearest_grid(
            cartesian_to_barycentric(solution["data"]["points"]), DENOMINATOR
        )
        key = canonical_center_key(center)
        if key not in by_key:
            by_key[key] = {
                "representative_id": int(solution["id"]),
                "public_ids": [],
                "public_score": float(solution["score"]),
                "center": center.tolist(),
                "canonical_key_sha256": hashlib.sha256(
                    json.dumps(key, separators=(",", ":")).encode()
                ).hexdigest(),
            }
        by_key[key]["public_ids"].append(int(solution["id"]))
    return sorted(
        by_key.values(),
        key=lambda seed: (-seed["public_score"], seed["representative_id"]),
    )


def hex_window(center: np.ndarray, radius: int) -> np.ndarray:
    points = set()
    for delta_first in range(-radius, radius + 1):
        for delta_second in range(-radius, radius + 1):
            delta_third = -delta_first - delta_second
            if max(abs(delta_first), abs(delta_second), abs(delta_third)) > radius:
                continue
            point = center + (delta_first, delta_second, delta_third)
            if np.all(point >= 0):
                points.add(tuple(int(value) for value in point))
    return np.asarray(sorted(points), dtype=np.int64)


def hull_vertices(domain: np.ndarray) -> np.ndarray:
    if domain.shape[0] <= 2:
        return domain
    try:
        hull = ConvexHull(domain[:, 1:].astype(np.float64))
    except QhullError:
        return domain
    return domain[np.unique(hull.vertices)]


def signed_determinant(
    first: np.ndarray, second: np.ndarray, third: np.ndarray
) -> np.ndarray:
    delta_second = second[..., 1:] - first[1:]
    delta_third = third[..., 1:] - first[1:]
    return (
        delta_second[..., 0] * delta_third[..., 1]
        - delta_second[..., 1] * delta_third[..., 0]
    )


def triple_needs_clauses(
    first: np.ndarray,
    second: np.ndarray,
    third: np.ndarray,
    threshold: int,
) -> bool:
    values = []
    for point_first in hull_vertices(first):
        for point_second in hull_vertices(second):
            values.extend(
                signed_determinant(
                    point_first, point_second, hull_vertices(third)
                ).tolist()
            )
    minimum = min(values)
    maximum = max(values)
    return not (minimum >= threshold or maximum <= -threshold)


def next_radius(radius: int) -> int:
    index = RADIUS_SCHEDULE.index(radius)
    return RADIUS_SCHEDULE[min(index + 1, len(RADIUS_SCHEDULE) - 1)]


class ClauseLimit(Exception):
    pass


def solve_stage(
    center: np.ndarray,
    radii: tuple[int, ...],
    threshold: int,
    conflict_budget: int,
    clause_limit: int,
    stage_seconds: float,
) -> tuple[dict[str, Any], np.ndarray | None]:
    started = time.perf_counter()
    deadline = started + stage_seconds
    domains = [hex_window(center[index], radii[index]) for index in range(COUNT)]
    offsets = []
    next_variable = 1
    for domain in domains:
        offsets.append(next_variable)
        next_variable += domain.shape[0]

    clause_count = 0
    clause_hash = hashlib.sha256()
    group_selectors: dict[int, tuple[int, int, int]] = {}
    constrained_triples = 0
    forbidden_combinations = 0
    examined_combinations = 0
    skipped_safe_triples = 0

    def add_clause(solver: Solver, literals: list[int]) -> None:
        nonlocal clause_count
        clause_count += 1
        if clause_count > clause_limit:
            raise ClauseLimit
        solver.add_clause(literals)
        clause_hash.update(" ".join(map(str, literals)).encode())
        clause_hash.update(b" 0\n")

    solver = Solver(name="cadical153")
    try:
        for label, domain in enumerate(domains):
            variables = list(range(offsets[label], offsets[label] + len(domain)))
            add_clause(solver, variables)
            for first, second in itertools.combinations(variables, 2):
                add_clause(solver, [-first, -second])

        # Coincident labeled points are outside the intended domain.
        for first_label, second_label in itertools.combinations(range(COUNT), 2):
            second_lookup = {
                tuple(point): index for index, point in enumerate(domains[second_label])
            }
            for first_index, point in enumerate(domains[first_label]):
                second_index = second_lookup.get(tuple(point))
                if second_index is not None:
                    add_clause(
                        solver,
                        [
                            -(offsets[first_label] + first_index),
                            -(offsets[second_label] + second_index),
                        ],
                    )

        for triple in itertools.combinations(range(COUNT), 3):
            if time.perf_counter() >= deadline:
                raise TimeoutError
            first_label, second_label, third_label = triple
            first_domain = domains[first_label]
            second_domain = domains[second_label]
            third_domain = domains[third_label]
            if not triple_needs_clauses(
                first_domain, second_domain, third_domain, threshold
            ):
                skipped_safe_triples += 1
                continue

            bad: list[tuple[int, int, int]] = []
            for first_index, first in enumerate(first_domain):
                for second_index, second in enumerate(second_domain):
                    values = determinant_numerator(first, second, third_domain)
                    examined_combinations += len(values)
                    for third_index in np.flatnonzero(values < threshold):
                        bad.append((first_index, second_index, int(third_index)))
                if time.perf_counter() >= deadline:
                    raise TimeoutError
            if not bad:
                continue
            constrained_triples += 1
            forbidden_combinations += len(bad)
            selector = next_variable
            next_variable += 1
            group_selectors[selector] = triple
            for first_index, second_index, third_index in bad:
                add_clause(
                    solver,
                    [
                        -selector,
                        -(offsets[first_label] + first_index),
                        -(offsets[second_label] + second_index),
                        -(offsets[third_label] + third_index),
                    ],
                )

        assumptions = list(group_selectors)
        build_seconds = time.perf_counter() - started
        solver.conf_budget(conflict_budget)
        solve_started = time.perf_counter()
        satisfiable = solver.solve_limited(assumptions=assumptions)
        solve_seconds = time.perf_counter() - solve_started
        statistics = solver.accum_stats()

        selected_grid = None
        core_triples: list[tuple[int, int, int]] = []
        if satisfiable is True:
            positive = {literal for literal in solver.get_model() if literal > 0}
            indices = []
            for label, domain in enumerate(domains):
                matches = [
                    index
                    for index in range(len(domain))
                    if offsets[label] + index in positive
                ]
                if len(matches) != 1:
                    raise RuntimeError("SAT model violates exactly-one encoding")
                indices.append(matches[0])
            selected_grid = np.asarray(
                [domains[label][indices[label]] for label in range(COUNT)],
                dtype=np.int64,
            )
            status = "satisfiable"
        elif satisfiable is False:
            core = list(solver.get_core() or assumptions)
            # Deletion minimization; inconclusive budgeted checks retain a group.
            for selector in list(core):
                trial = [item for item in core if item != selector]
                solver.conf_budget(max(1000, conflict_budget // 10))
                if solver.solve_limited(assumptions=trial) is False:
                    core = trial
            core_triples = sorted(group_selectors[item] for item in core)
            status = "unsatisfiable"
        else:
            status = "unresolved_conflict_budget"

        result = {
            "status": status,
            "radii": radii,
            "domain_sizes": [len(domain) for domain in domains],
            "candidate_variable_count": int(sum(map(len, domains))),
            "selector_variable_count": len(group_selectors),
            "clause_count": clause_count,
            "clause_sha256": clause_hash.hexdigest(),
            "constrained_triple_count": constrained_triples,
            "skipped_safe_triple_count": skipped_safe_triples,
            "forbidden_combination_count": forbidden_combinations,
            "examined_combination_count": examined_combinations,
            "build_seconds": build_seconds,
            "solve_seconds": solve_seconds,
            "solver": "CaDiCaL 1.5.3 via python-sat",
            "conflict_budget": conflict_budget,
            "solver_statistics": statistics,
            "unsat_core_triples": core_triples,
            "unsat_core_labels": sorted(
                set(itertools.chain.from_iterable(core_triples))
            ),
        }
        return result, selected_grid
    except ClauseLimit:
        return (
            {
                "status": "resource_pruned_clause_limit",
                "radii": radii,
                "domain_sizes": [len(domain) for domain in domains],
                "candidate_variable_count": int(sum(map(len, domains))),
                "clause_count": clause_count,
                "clause_limit": clause_limit,
                "clause_sha256_prefix": clause_hash.hexdigest(),
                "constrained_triple_count": constrained_triples,
                "skipped_safe_triple_count": skipped_safe_triples,
                "forbidden_combination_count": forbidden_combinations,
                "examined_combination_count": examined_combinations,
                "elapsed_seconds": time.perf_counter() - started,
            },
            None,
        )
    except TimeoutError:
        return (
            {
                "status": "resource_pruned_build_timeout",
                "radii": radii,
                "domain_sizes": [len(domain) for domain in domains],
                "candidate_variable_count": int(sum(map(len, domains))),
                "clause_count": clause_count,
                "clause_sha256_prefix": clause_hash.hexdigest(),
                "constrained_triple_count": constrained_triples,
                "skipped_safe_triple_count": skipped_safe_triples,
                "forbidden_combination_count": forbidden_combinations,
                "examined_combination_count": examined_combinations,
                "elapsed_seconds": time.perf_counter() - started,
            },
            None,
        )
    finally:
        solver.delete()


def initial_state(seeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "seed_index": index,
            "radii": [RADIUS_SCHEDULE[0]] * COUNT,
            "stage_index": 0,
            "last_core": None,
            "unchanged_core_count": 0,
            "done": False,
        }
        for index in range(len(seeds))
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    parser.add_argument("--stamp")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--max-seeds", type=int, default=10)
    parser.add_argument("--max-stages", type=int, default=4)
    parser.add_argument("--conflict-budget", type=int, default=50_000)
    parser.add_argument("--clause-limit", type=int, default=8_000_000)
    parser.add_argument("--stage-seconds", type=float, default=120.0)
    args = parser.parse_args()

    snapshot, live_score, target, verifier_hash = load_snapshot(args.snapshot)
    threshold = threshold_numerator(target, DENOMINATOR)
    seeds = distinct_public_seeds(snapshot)[: args.max_seeds]
    snapshot_hash = hashlib.sha256(args.snapshot.read_bytes()).hexdigest()

    if args.resume is not None:
        run_dir = args.resume.resolve()
        checkpoint = json.loads((run_dir / "checkpoint.json").read_text())
        if (
            checkpoint["snapshot_sha256"] != snapshot_hash
            or checkpoint["verifier_sha256"] != verifier_hash
        ):
            raise ValueError("resume checkpoint does not match frozen snapshot")
        states = checkpoint["states"]
        records = checkpoint["records"]
        if len(states) != len(seeds):
            raise ValueError("resume seed inventory differs")
    else:
        stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = args.run_root / stamp / SLUG
        run_dir.mkdir(parents=True, exist_ok=False)
        states = initial_state(seeds)
        records: list[dict[str, Any]] = []

    events = run_dir / "events.jsonl"
    if not events.exists():
        append_event(
            events,
            event="start",
            snapshot=str(args.snapshot.resolve()),
            snapshot_sha256=snapshot_hash,
            verifier_sha256=verifier_hash,
            live_score=live_score,
            target=target,
            denominator=DENOMINATOR,
            threshold_numerator=threshold,
            distinct_seed_count=len(seeds),
            dependency="python-sat==1.9.dev14",
        )
    else:
        append_event(events, event="resume", existing_records=len(records))

    best_payload = None
    best_score = -np.inf
    for state in states:
        seed_index = int(state["seed_index"])
        if state["done"]:
            continue
        seed = seeds[seed_index]
        center = np.asarray(seed["center"], dtype=np.int64)
        while not state["done"] and state["stage_index"] < args.max_stages:
            radii = tuple(map(int, state["radii"]))
            result, selected = solve_stage(
                center,
                radii,
                threshold,
                args.conflict_budget,
                args.clause_limit,
                args.stage_seconds,
            )
            result.update(
                {
                    "seed_index": seed_index,
                    "stage_index": int(state["stage_index"]),
                    "representative_public_id": seed["representative_id"],
                    "equivalent_public_ids": seed["public_ids"],
                    "public_score": seed["public_score"],
                    "canonical_key_sha256": seed["canonical_key_sha256"],
                }
            )

            if selected is not None:
                if len({tuple(point) for point in selected}) != COUNT:
                    raise RuntimeError("SAT candidate contains coincident points")
                exact_numerator, score = exact_grid_score(
                    selected, np.arange(COUNT), DENOMINATOR
                )
                if exact_numerator < threshold:
                    raise RuntimeError("SAT candidate fails exact determinant replay")
                payload = selected_payload(selected, np.arange(COUNT), DENOMINATOR)
                payload_path = run_dir / (
                    f"candidate_seed{seed_index:02d}_stage{state['stage_index']:02d}.json"
                )
                atomic_json(payload_path, {"points": payload["points"]})
                result.update(
                    {
                        "exact_minimum_numerator": exact_numerator,
                        "exact_score": score,
                        "barycentric_integer_points": selected.tolist(),
                        "payload": str(payload_path.resolve()),
                        "gate_clearing": bool(score > target),
                    }
                )
                if score > best_score:
                    best_score = score
                    best_payload = payload_path
                    atomic_json(run_dir / "best.json", {"points": payload["points"]})
                state["done"] = True
            elif result["status"] == "unsatisfiable":
                signature = result["unsat_core_triples"]
                if signature == state["last_core"]:
                    state["unchanged_core_count"] += 1
                else:
                    state["unchanged_core_count"] = 1
                state["last_core"] = signature
                labels = result["unsat_core_labels"]
                changed = False
                for label in labels:
                    expanded = next_radius(int(state["radii"][label]))
                    if expanded != state["radii"][label]:
                        state["radii"][label] = expanded
                        changed = True
                if state["unchanged_core_count"] >= 2 or not changed:
                    state["done"] = True
            else:
                state["done"] = True

            state["stage_index"] += 1
            if state["stage_index"] >= args.max_stages:
                state["done"] = True
            records.append(result)
            checkpoint = {
                "snapshot_sha256": snapshot_hash,
                "verifier_sha256": verifier_hash,
                "denominator": DENOMINATOR,
                "threshold_numerator": threshold,
                "states": states,
                "records": records,
            }
            atomic_json(run_dir / "checkpoint.json", checkpoint)
            append_event(events, event="stage_complete", **result)

    summary = {
        "slug": SLUG,
        "mode": "exact adaptive labeled-window SAT on the q=143 barycentric grid",
        "snapshot": str(args.snapshot.resolve()),
        "snapshot_sha256": snapshot_hash,
        "verifier_sha256": verifier_hash,
        "live_score": live_score,
        "target_strictly_above": target,
        "denominator": DENOMINATOR,
        "minimum_numerator": threshold,
        "minimum_grid_score": threshold / (DENOMINATOR * DENOMINATOR),
        "public_solution_count": len(snapshot["solutions"]),
        "d3_and_rounding_distinct_seed_count": len(seeds),
        "records": records,
        "status_counts": {
            status: sum(record["status"] == status for record in records)
            for status in sorted({record["status"] for record in records})
        },
        "states": states,
        "best_exact_grid_score": None if best_payload is None else best_score,
        "gate_clearing": bool(best_payload is not None and best_score > target),
        "payload": None if best_payload is None else str(best_payload.resolve()),
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, event="complete", summary=summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
