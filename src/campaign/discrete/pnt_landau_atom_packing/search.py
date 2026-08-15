#!/usr/bin/env python3
"""Constraint-generation screen for nonnegative Landau atom packings."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import linprog


HERE = Path(__file__).resolve().parent
DEFAULT_TABLE = HERE / "bober_sporadic_52.json"


@dataclass(frozen=True)
class Atom:
    line: int
    dilation: int
    period: int
    base_period: int
    pattern: np.ndarray
    score: float


def base_atom(row: dict) -> tuple[int, np.ndarray, float]:
    numerator = row["numerator"]
    denominator = row["denominator"]
    period = math.lcm(*(numerator + denominator))
    coefficients: dict[int, int] = {}
    for value in numerator:
        index = period // value
        coefficients[index] = coefficients.get(index, 0) + 1
    for value in denominator:
        index = period // value
        coefficients[index] = coefficients.get(index, 0) - 1
    pattern = np.fromiter(
        (
            sum(coefficient * (x // index) for index, coefficient in coefficients.items())
            for x in range(period)
        ),
        dtype=np.int8,
        count=period,
    )
    if not np.all((pattern == 0) | (pattern == 1)):
        raise ValueError(f"Bober row {row['line']} is not binary")
    score = (
        sum(value * math.log(value) for value in numerator)
        - sum(value * math.log(value) for value in denominator)
    ) / period
    return period, pattern, score


def build_atoms(table: Path, max_dilation: int) -> list[Atom]:
    rows = json.loads(table.read_text(encoding="utf-8"))["sporadic"]
    atoms: list[Atom] = []
    for row in rows:
        period, pattern, score = base_atom(row)
        for dilation in range(1, max_dilation + 1):
            atoms.append(
                Atom(
                    line=row["line"],
                    dilation=dilation,
                    period=dilation * period,
                    base_period=period,
                    pattern=pattern,
                    score=score / dilation,
                )
            )
    return atoms


def row_at(atoms: list[Atom], x: int) -> np.ndarray:
    return np.fromiter(
        (
            atom.pattern[(x // atom.dilation) % atom.base_period]
            for atom in atoms
        ),
        dtype=np.float64,
        count=len(atoms),
    )


def scan_complete_period(
    atoms: list[Atom], weights: np.ndarray, period: int, chunk_size: int
) -> tuple[float, int, list[int]]:
    nonzero = np.flatnonzero(weights > 1e-12)
    maximum = -math.inf
    argmax = 0
    leaders: list[tuple[float, int]] = []
    for start in range(0, period, chunk_size):
        stop = min(period, start + chunk_size)
        xs = np.arange(start, stop, dtype=np.int64)
        values = np.zeros(stop - start, dtype=np.float64)
        for index in nonzero:
            atom = atoms[int(index)]
            values += weights[index] * atom.pattern[
                (xs // atom.dilation) % atom.base_period
            ]
        local = int(np.argmax(values))
        if float(values[local]) > maximum:
            maximum = float(values[local])
            argmax = start + local
        take = min(32, len(values))
        if take:
            indices = np.argpartition(values, -take)[-take:]
            leaders.extend((float(values[i]), start + int(i)) for i in indices)
    leaders.sort(reverse=True)
    return maximum, argmax, [x for _, x in leaders[:256]]


def solve(args: argparse.Namespace) -> dict:
    atoms = build_atoms(args.table, args.max_dilation)
    joint_period = math.lcm(*(atom.period for atom in atoms))
    if joint_period > args.max_period:
        raise ValueError(
            f"joint period {joint_period:,} exceeds --max-period {args.max_period:,}"
        )

    points = set(range(min(joint_period, args.initial_rows)))
    scores = np.array([atom.score for atom in atoms], dtype=np.float64)
    events = []
    weights = np.zeros(len(atoms), dtype=np.float64)
    for iteration in range(args.max_iterations):
        ordered = sorted(points)
        matrix = np.stack([row_at(atoms, x) for x in ordered])
        result = linprog(
            -scores,
            A_ub=matrix,
            b_ub=np.ones(len(ordered)),
            bounds=(0.0, None),
            method="highs",
        )
        if not result.success:
            raise RuntimeError(result.message)
        weights = result.x
        maximum, argmax, leaders = scan_complete_period(
            atoms, weights, joint_period, args.chunk_size
        )
        event = {
            "iteration": iteration,
            "constraints": len(points),
            "objective": float(scores @ weights),
            "complete_period_max": maximum,
            "argmax": argmax,
            "nonzero": int(np.count_nonzero(weights > 1e-12)),
        }
        events.append(event)
        print(json.dumps(event), flush=True)
        if maximum <= 1.0 + args.tolerance:
            break
        old_size = len(points)
        for x in leaders:
            if float(row_at(atoms, x) @ weights) > 1.0 + args.tolerance / 10:
                points.add(x)
        if len(points) == old_size:
            points.add(argmax)
    else:
        raise RuntimeError("constraint generation did not converge")

    selected = []
    for index in np.flatnonzero(weights > 1e-10):
        atom = atoms[int(index)]
        selected.append(
            {
                "line": atom.line,
                "dilation": atom.dilation,
                "period": atom.period,
                "weight": float(weights[index]),
                "score_contribution": float(weights[index] * atom.score),
            }
        )
    return {
        "status": "floating_screen_only",
        "table": str(args.table),
        "max_dilation": args.max_dilation,
        "atom_count": len(atoms),
        "joint_period": joint_period,
        "objective": float(scores @ weights),
        "complete_period_max": events[-1]["complete_period_max"],
        "selected": selected,
        "events": events,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--max-dilation", type=int, default=6)
    parser.add_argument("--max-period", type=int, default=10_000_000)
    parser.add_argument("--initial-rows", type=int, default=5_000)
    parser.add_argument("--max-iterations", type=int, default=100)
    parser.add_argument("--chunk-size", type=int, default=200_000)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    args = parser.parse_args()
    print(json.dumps(solve(args), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
