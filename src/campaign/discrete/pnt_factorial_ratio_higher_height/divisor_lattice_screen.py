#!/usr/bin/env python3
"""Continuous-relaxation and exact-candidate screen on smooth divisor lattices.

For each declared modulus M and height D, the floating LP maximizes the
normalized factorial-ratio score over *all real* divisor-supported lists with
balance, height D, and 0 <= Landau step <= D.  It is therefore a stronger
numerical screen than an integer-only search, but is not presented as an exact
LP proof.  The integer candidate obtained by rounding is independently
period-replayed and is the only mathematical certificate retained.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import linprog

from higher_height_core import (
    canonical_signed_list,
    decimal_score,
    exact_period_replay,
    signed_list_from_counts,
)


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "divisor_lattice_receipt.json"
DEFAULT_PERIODS = [
    30, 60, 120, 180, 210, 360, 420, 840, 1260, 1680, 2520, 5040,
    7560, 9240, 13860, 18480, 27720, 30030, 60060, 120120, 180180,
    360360, 510510, 1021020, 1531530, 9699690,
]


def atomic_json(path: Path, value: Any) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def divisors(number: int) -> np.ndarray:
    values: list[int] = []
    for divisor in range(1, math.isqrt(number) + 1):
        if number % divisor:
            continue
        values.append(divisor)
        if divisor * divisor != number:
            values.append(number // divisor)
    return np.asarray(sorted(values), dtype=np.int64)


def landau_curve(modulus: int, keys: np.ndarray, values: np.ndarray) -> np.ndarray:
    increments = np.zeros(modulus + 1, dtype=np.float64)
    for key, value in zip(keys, values):
        increments[modulus // int(key) :: modulus // int(key)] += float(value)
    return np.cumsum(increments)[:modulus]


def solve(modulus: int, target_height: int, max_iterations: int) -> dict[str, Any]:
    keys = divisors(modulus)
    objective = -(keys * np.log(keys)) / (modulus * target_height)
    rows = set(range(min(modulus, 12_000)))
    rows.update(
        map(int, np.linspace(0, modulus - 1, min(modulus, 5_000), dtype=np.int64))
    )
    history: list[dict[str, Any]] = []
    solution: np.ndarray | None = None
    for iteration in range(max_iterations):
        row_array = np.asarray(sorted(rows), dtype=np.int64)
        matrix = ((row_array[:, None] * keys[None, :]) // modulus).astype(float)
        result = linprog(
            objective,
            A_ub=np.vstack((matrix, -matrix)),
            b_ub=np.concatenate(
                (np.full(len(row_array), target_height, dtype=float),
                 np.zeros(len(row_array), dtype=float))
            ),
            A_eq=np.vstack((keys, np.ones(len(keys)))),
            b_eq=np.asarray((0.0, -float(target_height))),
            bounds=(-10.0 * target_height, 10.0 * target_height),
            method="highs",
            options={
                "primal_feasibility_tolerance": 1e-9,
                "dual_feasibility_tolerance": 1e-9,
            },
        )
        if not result.success:
            raise RuntimeError(f"LP failed for M={modulus}, D={target_height}: {result.message}")
        solution = np.asarray(result.x, dtype=float)
        curve = landau_curve(modulus, keys, solution)
        low = float(curve.min())
        high = float(curve.max())
        history.append(
            {
                "iteration": iteration,
                "master_rows": len(rows),
                "continuous_score": -float(result.fun),
                "full_period_minimum": low,
                "full_period_maximum": high,
            }
        )
        if low >= -2e-8 and high <= target_height + 2e-8:
            break
        count = min(512, modulus)
        rows.update(map(int, np.argpartition(curve, count - 1)[:count]))
        rows.update(map(int, np.argpartition(curve, -count)[-count:]))
    if solution is None:
        raise AssertionError("LP did not run")

    rounded = np.rint(solution).astype(np.int64)
    if float(np.max(np.abs(solution - rounded))) > 2e-6:
        raise RuntimeError("continuous optimum did not round to an integer candidate")
    raw_counts = {
        int(key): int(value)
        for key, value in zip(keys, rounded)
        if int(value)
    }
    counts = canonical_signed_list(signed_list_from_counts(raw_counts))
    if -sum(counts.values()) != target_height:
        raise AssertionError("rounded candidate has the wrong height")
    replay = exact_period_replay(counts)
    if not replay["is_integral_factorial_ratio"]:
        raise AssertionError("rounded candidate failed its exact period")
    return {
        "period_lattice": modulus,
        "divisor_variables": len(keys),
        "height": target_height,
        "history": history,
        "continuous_relaxation_status": "numerical HiGHS optimum; not an exact dual certificate",
        "rounded_exact_candidate": {
            "signed_list": signed_list_from_counts(counts),
            "score_decimal": str(decimal_score(counts)),
            "exact_period_replay": replay,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--periods", nargs="*", type=int, default=DEFAULT_PERIODS)
    parser.add_argument("--max-iterations", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = [
        solve(modulus, target_height, args.max_iterations)
        for modulus in args.periods
        for target_height in (2, 3)
    ]
    scores = [
        result["rounded_exact_candidate"]["score_decimal"] for result in results
    ]
    receipt = {
        "scope": "declared smooth divisor lattices; complete period separation",
        "periods": args.periods,
        "heights": [2, 3],
        "runs": len(results),
        "largest_period": max(args.periods),
        "largest_divisor_variable_count": max(
            result["divisor_variables"] for result in results
        ),
        "all_continuous_scores_within_2e-12_of_chebyshev": all(
            abs(result["history"][-1]["continuous_score"] - 0.9212920229340908)
            <= 2e-12
            for result in results
        ),
        "all_rounded_candidates_exactly_replayed": all(
            result["rounded_exact_candidate"]["exact_period_replay"]
            ["is_integral_factorial_ratio"]
            for result in results
        ),
        "best_rounded_score_decimal": max(scores),
        "results": results,
        "claim_boundary": (
            "The exact candidate replays are mathematical certificates.  The "
            "continuous relaxation optima are numerical negative evidence only."
        ),
    }
    atomic_json(OUTPUT, receipt)
    print(json.dumps({key: value for key, value in receipt.items() if key != "results"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
