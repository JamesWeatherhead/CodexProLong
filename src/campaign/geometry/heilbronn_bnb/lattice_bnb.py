#!/usr/bin/env python3
"""Exact lattice-family branch-and-bound for Heilbronn triangle n=11.

The construction family places points on a barycentric q-grid.  Selecting 11
grid points with normalized area at least d/q^2 is a 0-1 hypergraph problem:
every grid triple of determinant below d is a forbidden face.  HiGHS then
branches over point selections with those faces as exact cuts.  This is a
discrete topology search, not a local coordinate restart.

The family fixes the strongest boundary pattern shared by the public frontier:
no outer corner and exactly two selected points on each side.  Equilateral D3
symmetry is reduced by ordering the three aggregate barycentric coordinates.
Downloaded verifier source is hashed but never executed on the host.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from datetime import UTC, datetime
from decimal import ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

SLUG = "heilbronn-triangles"
COUNT = 11
DEFAULT_SNAPSHOT = (
    Path(__file__).parents[1]
    / "snapshots"
    / "heilbronn-triangles_20260814T231406Z.json"
)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_event(path: Path, **event: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def parse_ints(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item.strip()]


def load_snapshot(path: Path) -> tuple[dict[str, Any], float, float, str]:
    with path.open(encoding="utf-8") as handle:
        snapshot = json.load(handle)
    problem = snapshot["problem"]
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
    if verifier_hash != snapshot["verifier_sha256"]:
        raise ValueError("snapshot verifier hash mismatch")
    live_score = float(snapshot["solutions"][0]["score"])
    target = live_score + float(problem["minImprovement"])
    return snapshot, live_score, target, verifier_hash


def barycentric_grid(denominator: int, *, include_corners: bool = False) -> np.ndarray:
    points = []
    for first in range(denominator + 1):
        for second in range(denominator - first + 1):
            third = denominator - first - second
            # Outer corners belong to two sides and are absent from every
            # competitive public topology in the frozen database.
            if not include_corners and max(first, second, third) == denominator:
                continue
            points.append((first, second, third))
    return np.asarray(points, dtype=np.int64)


def determinant_numerator(
    first: np.ndarray, second: np.ndarray, third: np.ndarray
) -> np.ndarray:
    """Exact normalized double-area numerator on the q-grid."""
    delta_second = second[..., 1:] - first[1:]
    delta_third = third[..., 1:] - first[1:]
    return np.abs(
        delta_second[..., 0] * delta_third[..., 1]
        - delta_second[..., 1] * delta_third[..., 0]
    )


def threshold_numerator(target: float, denominator: int) -> int:
    scaled = Decimal(str(target)) * Decimal(denominator * denominator)
    return int(scaled.to_integral_value(rounding=ROUND_FLOOR)) + 1


def build_model(
    grid: np.ndarray,
    denominator: int,
    minimum_numerator: int,
    selected_count: int,
) -> tuple[LinearConstraint, Bounds, np.ndarray, dict[str, int]]:
    variable_count = grid.shape[0]
    row_chunks: list[np.ndarray] = []
    column_chunks: list[np.ndarray] = []
    data_chunks: list[np.ndarray] = []
    forbidden_count = 0

    for first_id in range(variable_count - 2):
        first = grid[first_id]
        for second_id in range(first_id + 1, variable_count - 1):
            third_ids = np.arange(second_id + 1, variable_count, dtype=np.int64)
            numerators = determinant_numerator(
                first,
                grid[second_id],
                grid[third_ids],
            )
            bad_third_ids = third_ids[numerators < minimum_numerator]
            count = bad_third_ids.size
            if not count:
                continue
            rows = np.arange(forbidden_count, forbidden_count + count, dtype=np.int64)
            row_chunks.extend((rows, rows, rows))
            column_chunks.extend(
                (
                    np.full(count, first_id, dtype=np.int64),
                    np.full(count, second_id, dtype=np.int64),
                    bad_third_ids,
                )
            )
            data_chunks.extend(
                (
                    np.ones(count, dtype=np.float64),
                    np.ones(count, dtype=np.float64),
                    np.ones(count, dtype=np.float64),
                )
            )
            forbidden_count += count

    extra_rows = 6
    total_rows = forbidden_count + extra_rows
    lower = np.full(total_rows, -np.inf)
    upper = np.full(total_rows, np.inf)
    upper[:forbidden_count] = 2.0

    def add_dense_row(
        offset: int, coefficients: np.ndarray, low: float, high: float
    ) -> None:
        row = forbidden_count + offset
        nonzero = np.flatnonzero(coefficients)
        row_chunks.append(np.full(nonzero.size, row, dtype=np.int64))
        column_chunks.append(nonzero.astype(np.int64))
        data_chunks.append(coefficients[nonzero].astype(np.float64))
        lower[row] = low
        upper[row] = high

    add_dense_row(0, np.ones(variable_count), selected_count, selected_count)
    # Exactly two points on each side: barycentric coordinate zero.
    for coordinate in range(3):
        add_dense_row(
            1 + coordinate,
            (grid[:, coordinate] == 0).astype(np.float64),
            2.0,
            2.0,
        )
    # D3 canonical orientation: aggregate lambda_A >= lambda_B >= lambda_C.
    add_dense_row(4, grid[:, 0] - grid[:, 1], 0.0, np.inf)
    add_dense_row(5, grid[:, 1] - grid[:, 2], 0.0, np.inf)

    rows = np.concatenate(row_chunks)
    columns = np.concatenate(column_chunks)
    data = np.concatenate(data_chunks)
    matrix = coo_matrix(
        (data, (rows, columns)),
        shape=(total_rows, variable_count),
    ).tocsr()
    constraint = LinearConstraint(matrix, lower, upper)
    bounds = Bounds(np.zeros(variable_count), np.ones(variable_count))
    integrality = np.ones(variable_count, dtype=np.int8)
    statistics = {
        "grid_point_count": variable_count,
        "possible_triple_count": math.comb(variable_count, 3),
        "forbidden_face_count": forbidden_count,
        "constraint_count": total_rows,
        "nonzero_count": int(matrix.nnz),
    }
    return constraint, bounds, integrality, statistics


def selected_payload(
    grid: np.ndarray, selected: np.ndarray, denominator: int
) -> dict[str, object]:
    barycentric = grid[selected].astype(np.float64) / denominator
    # lambda_A*(0,0) + lambda_B*(1,0) + lambda_C*(1/2,sqrt(3)/2)
    points = np.column_stack(
        (
            barycentric[:, 1] + 0.5 * barycentric[:, 2],
            (np.sqrt(3.0) / 2.0) * barycentric[:, 2],
        )
    )
    return {
        "points": points.tolist(),
        "barycentric_integer_points": grid[selected].tolist(),
        "denominator": denominator,
    }


def exact_grid_score(
    grid: np.ndarray, selected: np.ndarray, denominator: int
) -> tuple[int, float]:
    minimum = denominator * denominator
    chosen = grid[selected]
    for first in range(COUNT - 2):
        for second in range(first + 1, COUNT - 1):
            numerators = determinant_numerator(
                chosen[first],
                chosen[second],
                chosen[second + 1 :],
            )
            minimum = min(minimum, int(np.min(numerators)))
    return minimum, minimum / (denominator * denominator)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument(
        "--denominators", type=parse_ints, default=parse_ints("8,10,12,14,16,18,20")
    )
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--node-limit", type=int, default=1_000_000)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    parser.add_argument("--stamp")
    args = parser.parse_args()

    snapshot, live_score, target, verifier_hash = load_snapshot(args.snapshot)
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    append_event(
        events,
        event="start",
        snapshot=str(args.snapshot.resolve()),
        snapshot_sha256=hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
        verifier_sha256=verifier_hash,
        live_score=live_score,
        target=target,
        family="barycentric q-grid; no corners; exactly two points per outer side",
    )

    results = []
    best_score = -np.inf
    best_payload: dict[str, object] | None = None
    solved_count = 0
    infeasible_count = 0
    unresolved_count = 0
    for denominator in args.denominators:
        started = time.perf_counter()
        minimum_numerator = threshold_numerator(target, denominator)
        grid = barycentric_grid(denominator)
        constraint, bounds, integrality, statistics = build_model(
            grid,
            denominator,
            minimum_numerator,
            COUNT,
        )
        build_seconds = time.perf_counter() - started
        solve_started = time.perf_counter()
        result = milp(
            np.zeros(grid.shape[0]),
            integrality=integrality,
            bounds=bounds,
            constraints=constraint,
            options={
                "disp": False,
                "presolve": True,
                "time_limit": args.time_limit,
                "node_limit": args.node_limit,
                "mip_rel_gap": 0.0,
            },
        )
        solve_seconds = time.perf_counter() - solve_started
        record: dict[str, object] = {
            "denominator": denominator,
            "minimum_numerator": minimum_numerator,
            "minimum_grid_score": minimum_numerator / (denominator * denominator),
            "build_seconds": build_seconds,
            "solve_seconds": solve_seconds,
            "status": int(result.status),
            "success": bool(result.success),
            "message": str(result.message),
            "mip_node_count": int(getattr(result, "mip_node_count", 0) or 0),
            "mip_gap": float(getattr(result, "mip_gap", 0.0) or 0.0),
            **statistics,
        }
        if result.x is not None:
            selected = np.flatnonzero(result.x > 0.5)
            record["selected_count"] = int(selected.size)
            if selected.size == COUNT:
                exact_numerator, score = exact_grid_score(grid, selected, denominator)
                payload = selected_payload(grid, selected, denominator)
                record.update(
                    {
                        "feasible": True,
                        "exact_minimum_numerator": exact_numerator,
                        "exact_score": score,
                        "selected_indices": selected.tolist(),
                        "payload": payload,
                    }
                )
                solved_count += 1
                if score > best_score:
                    best_score = score
                    best_payload = {"points": payload["points"]}
                    atomic_json(run_dir / "best.json", best_payload)
        else:
            record["feasible"] = False
            if result.status == 2:
                infeasible_count += 1
            else:
                unresolved_count += 1
        results.append(record)
        atomic_json(run_dir / f"q{denominator:03d}.json", record)
        atomic_json(run_dir / "checkpoint.json", {"completed": results})
        append_event(events, event="denominator_complete", **record)

    summary = {
        "slug": SLUG,
        "mode": "exact discrete active-topology branch-and-bound",
        "family": "barycentric lattice, two non-corner points per side",
        "snapshot": str(args.snapshot.resolve()),
        "public_solution_count": len(snapshot["solutions"]),
        "public_thread_count": len(snapshot["threads"]),
        "verifier_sha256": verifier_hash,
        "live_score": live_score,
        "target_strictly_above": target,
        "denominators": args.denominators,
        "feasible_denominator_count": solved_count,
        "proved_infeasible_denominator_count": infeasible_count,
        "unresolved_denominator_count": unresolved_count,
        "best_exact_grid_score": None if best_payload is None else best_score,
        "gate_clearing": bool(best_payload is not None and best_score > target),
        "payload": None
        if best_payload is None
        else str((run_dir / "best.json").resolve()),
        "results": results,
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, event="complete", summary=summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
