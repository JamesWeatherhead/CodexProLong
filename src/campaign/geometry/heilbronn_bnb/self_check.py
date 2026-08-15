#!/usr/bin/env python3
"""Independent small-instance and exact-arithmetic checks for the DFS."""

from __future__ import annotations

import argparse
import itertools
import time
from pathlib import Path

import numpy as np
from hypergraph_dfs import HypergraphSearch
from lattice_bnb import (
    COUNT,
    atomic_json,
    barycentric_grid,
    build_model,
    determinant_numerator,
    exact_grid_score,
)
from scipy.optimize import milp
from typed_pair_dfs import TypedPairSearch


def run_dfs(denominator: int, minimum_numerator: int) -> dict[str, object]:
    grid = barycentric_grid(denominator)
    search = HypergraphSearch(
        grid,
        denominator,
        minimum_numerator,
        time.perf_counter() + 30.0,
        20_000_000,
        (2, 2, 2),
    )
    status, completed, _, roots = search.run()
    record: dict[str, object] = {
        "denominator": denominator,
        "minimum_numerator": minimum_numerator,
        "status": status,
        "nodes": search.counters.nodes,
        "completed_roots": completed,
        "total_roots": roots,
    }
    if search.solution is not None:
        selected = np.asarray(search.solution, dtype=np.int64)
        exact_numerator, score = exact_grid_score(grid, selected, denominator)
        assert exact_numerator >= minimum_numerator
        assert len(selected) == COUNT
        for first, second, third in itertools.combinations(selected, 3):
            assert (
                int(determinant_numerator(grid[first], grid[second], grid[third]))
                >= minimum_numerator
            )
        record.update(
            exact_numerator=exact_numerator,
            exact_score=score,
            barycentric_integer_points=grid[selected].tolist(),
        )
    return record


def compare_typed_pair(
    denominator: int,
    minimum_numerator: int,
    side_counts: tuple[int, int, int],
) -> dict[str, object]:
    grid = barycentric_grid(denominator)
    ordinary = HypergraphSearch(
        grid,
        denominator,
        minimum_numerator,
        time.perf_counter() + 30.0,
        20_000_000,
        side_counts,
    )
    ordinary_status, *_ = ordinary.run()
    typed = TypedPairSearch(
        grid,
        minimum_numerator,
        side_counts,
        time.perf_counter() + 30.0,
        20_000_000,
    )
    typed_status, *_ = typed.run()
    assert typed_status == ordinary_status
    if typed.solution is not None:
        exact_numerator, _ = exact_grid_score(
            grid, np.asarray(typed.solution, dtype=np.int64), denominator
        )
        assert exact_numerator >= minimum_numerator
    return {
        "denominator": denominator,
        "minimum_numerator": minimum_numerator,
        "side_counts": side_counts,
        "ordinary_status": ordinary_status,
        "typed_pair_status": typed_status,
        "ordinary_nodes": ordinary.counters.nodes,
        "typed_pair_nodes": typed.counters.nodes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    dfs_records = [
        run_dfs(8, 1),
        run_dfs(8, 2),
        run_dfs(12, 4),
        run_dfs(12, 5),
    ]
    expected = ["feasible", "infeasible", "feasible", "infeasible"]
    assert [record["status"] for record in dfs_records] == expected

    # Cross-check q=8, d=2 with the independently implemented HiGHS MILP.
    grid = barycentric_grid(8)
    constraint, bounds, integrality, statistics = build_model(grid, 8, 2, COUNT)
    result = milp(
        np.zeros(grid.shape[0]),
        integrality=integrality,
        bounds=bounds,
        constraints=constraint,
        options={"time_limit": 30.0},
    )
    assert result.status == 2  # HiGHS: model proven infeasible.

    typed_pair_records = []
    for side_counts in ((1, 1, 1), (1, 1, 0), (1, 0, 0)):
        typed_pair_records.append(compare_typed_pair(10, 1, side_counts))
        typed_pair_records.append(compare_typed_pair(8, 3, side_counts))
    assert {record["ordinary_status"] for record in typed_pair_records} == {
        "feasible",
        "infeasible",
    }

    output = {
        "status": "passed",
        "checks": {
            "dfs_feasible_infeasible_transitions": dfs_records,
            "independent_highs_q8_d2": {
                "status": int(result.status),
                "message": result.message,
                "model_statistics": statistics,
            },
            "typed_pair_vs_category_dfs_transitions": typed_pair_records,
        },
    }
    atomic_json(args.output, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
