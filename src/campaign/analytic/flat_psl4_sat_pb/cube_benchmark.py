#!/usr/bin/env python3
"""Deterministic outside-in cube benchmark: SAT/PB versus exact C++ DFS."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import random
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from pysat.solvers import Solver

import sat_pb_benchmark as sat


HERE = Path(__file__).resolve().parent


def newly_fixed(values: list[int | None], depth: int) -> int:
    lag = sat.N - depth
    return sum(int(values[index]) * int(values[index + lag]) for index in range(depth))


def random_path(generator: random.Random, depth: int) -> str:
    values: list[int | None] = [None] * sat.N

    def descend(current: int) -> bool:
        if current == depth:
            return True
        branches = [(0, 0), (0, 1), (1, 0), (1, 1)]
        generator.shuffle(branches)
        if current in (0, 1):
            branches = [branch for branch in branches if branch[0] == 0]
        for left_bit, right_bit in branches:
            right = sat.N - 1 - current
            values[current] = 1 if left_bit else -1
            values[right] = 1 if right_bit else -1
            if abs(newly_fixed(values, current + 1)) <= sat.BOUND and descend(current + 1):
                return True
        values[current] = None
        values[sat.N - 1 - current] = None
        return False

    if not descend(0):
        raise RuntimeError("failed to generate valid outside-in path")
    return "".join("?" if value is None else ("1" if value > 0 else "0") for value in values)


def fixture_cube(bits: str, depth: int) -> str:
    return bits[:depth] + "?" * (sat.N - 2 * depth) + bits[sat.N - depth :]


def generate_cubes(count: int, depth: int, seed: int) -> list[str]:
    if not (2 <= depth < sat.N // 2):
        raise ValueError("depth must be in [2, 34]")
    cubes: list[str] = []
    seen: set[str] = set()
    for bits in sat.KNOWN:
        cube = fixture_cube(bits, depth)
        if cube not in seen:
            cubes.append(cube)
            seen.add(cube)
    generator = random.Random(seed)
    while len(cubes) < count:
        cube = random_path(generator, depth)
        if cube not in seen:
            cubes.append(cube)
            seen.add(cube)
    return cubes


def parse_cpp(stdout: str) -> tuple[list[dict[str, int]], dict[str, Any]]:
    rows: list[dict[str, int]] = []
    done: dict[str, Any] | None = None
    for line in stdout.splitlines():
        if line.startswith("CUBE "):
            _, index, nodes, leaves, solutions = line.split()
            rows.append(
                {
                    "index": int(index),
                    "nodes": int(nodes),
                    "leaves": int(leaves),
                    "solutions": int(solutions),
                }
            )
        elif line.startswith("DONE "):
            done = {}
            for key, value in re.findall(r"([a-z_]+)=([^ ]+)", line):
                done[key] = float(value) if key == "seconds" else int(value)
    if done is None:
        raise RuntimeError("C++ baseline omitted DONE row")
    return rows, done


def run_cpp(cubes: list[str]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="psl4-cube-cpp-") as name:
        binary = Path(name) / "cube_baseline"
        compile_command = [
            "clang++",
            "-std=c++20",
            "-O3",
            "-DNDEBUG",
            "-march=native",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            str(HERE / "cube_baseline.cpp"),
            "-o",
            str(binary),
        ]
        subprocess.run(compile_command, check=True)
        completed = subprocess.run(
            [str(binary)],
            input="\n".join(cubes) + "\n",
            capture_output=True,
            text=True,
            check=True,
        )
    rows, done = parse_cpp(completed.stdout)
    return {
        "compile_command": [*compile_command[:-3], "<source>", "-o", "<binary>"],
        "rows": rows,
        "done": done,
    }


def completion_for(cube: str, seed: int) -> str:
    generator = random.Random(seed)
    return "".join(str(generator.randrange(2)) if bit == "?" else bit for bit in cube)


def stats_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    return {key: after.get(key, 0) - before.get(key, 0) for key in set(before) | set(after)}


def run_sat_backend(
    backend: str, cubes: list[str], conflict_budget: int
) -> dict[str, Any]:
    formula, pool, xs, differences, prefixes = sat.pysat_formula(backend, False)
    solver_name = "minicard" if backend == "minicard_native" else "cadical195"
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    with Solver(name=solver_name, bootstrap_with=formula) as solver:
        for index, cube in enumerate(cubes):
            completion = completion_for(cube, 0xC0BE0000 + index)
            solver.set_phases(sat.phases_for(completion, xs, differences, prefixes))
            assumptions = [
                xs[position] if bit == "1" else -xs[position]
                for position, bit in enumerate(cube)
                if bit != "?"
            ]
            before = solver.accum_stats()
            solver.conf_budget(conflict_budget)
            cube_started = time.perf_counter()
            status = solver.solve_limited(
                assumptions=assumptions, expect_interrupt=True
            )
            seconds = time.perf_counter() - cube_started
            after = solver.accum_stats()
            row: dict[str, Any] = {
                "index": index,
                "status": "sat" if status is True else ("unsat" if status is False else "unknown"),
                "seconds": seconds,
                "stats_delta": stats_delta(before, after),
            }
            if status is True:
                bits = sat.bits_from_model(solver.get_model(), xs)
                for position, bit in enumerate(cube):
                    if bit != "?" and bits[position] != bit:
                        raise RuntimeError("SAT model violates cube assumption")
                row["model"] = sat.exact_verify(bits)
                solver.add_clause(
                    [-variable if bits[position] == "1" else variable for position, variable in enumerate(xs)]
                )
            rows.append(row)
        total_seconds = time.perf_counter() - started
        cumulative = solver.accum_stats()
    return {
        "backend": backend,
        "formula": sat.pysat_stats(formula, pool),
        "conflict_budget_per_cube": conflict_budget,
        "seconds": total_seconds,
        "cumulative_stats": cumulative,
        "resolved": sum(row["status"] != "unknown" for row in rows),
        "sat": sum(row["status"] == "sat" for row in rows),
        "unsat": sum(row["status"] == "unsat" for row in rows),
        "unknown": sum(row["status"] == "unknown" for row in rows),
        "rows": rows,
    }


def atomic_json(path: Path, value: Any) -> None:
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cube-count", type=int, default=256)
    parser.add_argument("--depth", type=int, default=28)
    parser.add_argument("--seed", type=int, default=0x12124930)
    parser.add_argument("--conflict-budget", type=int, default=5000)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = args.run_id or timestamp
    run_dir = HERE / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    cubes = generate_cubes(args.cube_count, args.depth, args.seed)
    cpp = run_cpp(cubes)
    backends = [
        run_sat_backend("minicard_native", cubes, args.conflict_budget),
        run_sat_backend("cadical_seqcounter", cubes, args.conflict_budget),
    ]
    cpp_status = [row["solutions"] > 0 for row in cpp["rows"]]
    for backend in backends:
        for row in backend["rows"]:
            if row["status"] == "unknown":
                continue
            if (row["status"] == "sat") != cpp_status[row["index"]]:
                raise RuntimeError(
                    f"{backend['backend']} disagrees with C++ on cube {row['index']}"
                )

    record = {
        "schema": "flat-psl4-cube-feasibility-v1",
        "created_utc": timestamp,
        "run_id": run_id,
        "cube_count": len(cubes),
        "depth": args.depth,
        "free_bits": sat.N - 2 * args.depth,
        "seed": args.seed,
        "cubes_sha256": hashlib.sha256(
            ("\n".join(cubes) + "\n").encode()
        ).hexdigest(),
        "fixture_cube_indices": list(range(min(len(sat.KNOWN), len(cubes)))),
        "cpp_exact_outside_in": cpp,
        "sat_backends": backends,
        "scope": (
            "C++ is the exact newly-fixed-sidelobe outside-in baseline, not "
            "the stronger active-lag accelerator. SAT unknown rows are not "
            "proofs and are excluded from agreement counts."
        ),
    }
    path = run_dir / "cube_benchmark.json"
    atomic_json(path, record)
    print(
        "cpp",
        cpp["done"],
        *[
            {
                "backend": backend["backend"],
                "seconds": backend["seconds"],
                "resolved": backend["resolved"],
                "sat": backend["sat"],
                "unsat": backend["unsat"],
                "unknown": backend["unknown"],
            }
            for backend in backends
        ],
    )
    print(f"receipt={path}")
    print(f"sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
