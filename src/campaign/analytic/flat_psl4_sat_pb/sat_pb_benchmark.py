#!/usr/bin/env python3
"""Exact SAT/PB feasibility benchmark for length-70 PSL <= 4 enumeration."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from ortools.sat.python import cp_model
from pysat.card import CardEnc, EncType
from pysat.formula import CNF, CNFPlus, IDPool
from pysat.solvers import Solver


HERE = Path(__file__).resolve().parent
N = 70
BOUND = 4
KNOWN = (
    "0000011100001011111111110101001010111100110011001101010110010110010110",
    "0000011111000000000100110011011100111101001101001100011100101010100101",
    "0010101111111110111000101001110001011001001001111000100110011101000011",
)
ENCODINGS = {
    "cadical_seqcounter": EncType.seqcounter,
    "cadical_cardnetwrk": EncType.cardnetwrk,
    "cadical_totalizer": EncType.totalizer,
    "cadical_mtotalizer": EncType.mtotalizer,
    "cadical_kmtotalizer": EncType.kmtotalizer,
}
BACKENDS = (*ENCODINGS, "minicard_native", "cp_sat")
STAGES = ("forced", "first_hint", "known_chain", "cold", "post_known")


def canonical(bits: str) -> str:
    return orbit(bits)[0]


def orbit(bits: str) -> tuple[str, ...]:
    transforms: set[str] = set()
    for reverse in (False, True):
        source = bits[::-1] if reverse else bits
        for alternate in (False, True):
            alternated = "".join(
                str(int(bit) ^ (index & 1 if alternate else 0))
                for index, bit in enumerate(source)
            )
            for negate in (False, True):
                transforms.add(
                    "".join(str(int(bit) ^ negate) for bit in alternated)
                )
    return tuple(sorted(transforms))


def block_class_pysat(solver: Solver, xs: list[int], bits: str) -> None:
    for transformed in orbit(bits):
        solver.add_clause(
            [
                -variable if transformed[index] == "1" else variable
                for index, variable in enumerate(xs)
            ]
        )


def exact_verify(bits: str) -> dict[str, Any]:
    if len(bits) != N or set(bits) - {"0", "1"}:
        raise RuntimeError("solver returned malformed bits")
    values = [1 if bit == "1" else -1 for bit in bits]
    correlations = [
        sum(values[i] * values[i + lag] for i in range(N - lag))
        for lag in range(1, N)
    ]
    peak = max(abs(value) for value in correlations)
    if peak > BOUND:
        raise RuntimeError(f"solver model violates PSL bound: {peak}")
    return {
        "bits": bits,
        "canonical": canonical(bits),
        "peak_sidelobe": peak,
        "correlations_sha256": hashlib.sha256(
            json.dumps(correlations, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def bounds(size: int) -> tuple[int, int]:
    lower = max(0, (size - BOUND + 1) // 2)
    upper = min(size, (size + BOUND) // 2)
    return lower, upper


def xor_clauses(left: int, right: int, difference: int) -> list[list[int]]:
    return [
        [-left, -right, -difference],
        [left, right, -difference],
        [left, -right, difference],
        [-left, right, difference],
    ]


def add_lex_leader_cnf(formula: CNF | CNFPlus, pool: IDPool, xs: list[int]) -> list[int]:
    """Add x <= reverse(x); x[0]=x[1]=0 already normalizes N/S."""
    prefixes: list[int] = []
    prefix = pool.id(("lex", 0))
    formula.append([prefix])
    prefixes.append(prefix)
    for index in range(N // 2):
        left = xs[index]
        right = xs[N - 1 - index]
        formula.append([-prefix, -left, right])
        if index + 1 == N // 2:
            break
        following = pool.id(("lex", index + 1))
        formula.extend(
            [
                [-following, prefix],
                [-following, -left, right],
                [-following, left, -right],
                [-prefix, -left, -right, following],
                [-prefix, left, right, following],
            ]
        )
        prefixes.append(following)
        prefix = following
    return prefixes


def pysat_formula(backend: str, lex: bool) -> tuple[Any, IDPool, list[int], dict[tuple[int, int], int], list[int]]:
    pool = IDPool()
    xs = [pool.id(("x", index)) for index in range(N)]
    differences: dict[tuple[int, int], int] = {}
    native = backend == "minicard_native"
    formula: CNF | CNFPlus = CNFPlus() if native else CNF()
    encoding = ENCODINGS.get(backend)
    for lag in range(1, N):
        literals: list[int] = []
        for index in range(N - lag):
            difference = pool.id(("y", index, lag))
            differences[index, lag] = difference
            literals.append(difference)
            formula.extend(xor_clauses(xs[index], xs[index + lag], difference))
        lower, upper = bounds(len(literals))
        if native:
            if upper < len(literals):
                formula.append([literals, upper], is_atmost=True)
            if lower > 0:
                formula.append(
                    [[-literal for literal in literals], len(literals) - lower],
                    is_atmost=True,
                )
        else:
            if lower > 0:
                formula.extend(
                    CardEnc.atleast(
                        literals, bound=lower, vpool=pool, encoding=encoding
                    ).clauses
                )
            if upper < len(literals):
                formula.extend(
                    CardEnc.atmost(
                        literals, bound=upper, vpool=pool, encoding=encoding
                    ).clauses
                )
    formula.append([-xs[0]])
    formula.append([-xs[1]])
    prefixes = add_lex_leader_cnf(formula, pool, xs) if lex else []
    return formula, pool, xs, differences, prefixes


def phases_for(
    bits: str,
    xs: list[int],
    differences: dict[tuple[int, int], int],
    prefixes: list[int],
) -> list[int]:
    phases = [variable if bits[index] == "1" else -variable for index, variable in enumerate(xs)]
    phases.extend(
        variable if bits[index] != bits[index + lag] else -variable
        for (index, lag), variable in differences.items()
    )
    prefix_equal = True
    for index, variable in enumerate(prefixes):
        phases.append(variable if prefix_equal else -variable)
        prefix_equal = prefix_equal and bits[index] == bits[N - 1 - index]
    return phases


def bits_from_model(model: list[int], xs: list[int]) -> str:
    positive = {literal for literal in model if literal > 0}
    return "".join("1" if variable in positive else "0" for variable in xs)


def pysat_stats(formula: CNF | CNFPlus, pool: IDPool) -> dict[str, int]:
    return {
        "variables": pool.top,
        "cnf_clauses": len(formula.clauses),
        "native_atmosts": len(formula.atmosts) if isinstance(formula, CNFPlus) else 0,
    }


def run_pysat(backend: str, stage: str, lex: bool) -> dict[str, Any]:
    formula, pool, xs, differences, prefixes = pysat_formula(backend, lex)
    solver_name = "minicard" if backend == "minicard_native" else "cadical195"
    result: dict[str, Any] = {
        "backend": backend,
        "stage": stage,
        "lex_leader": lex,
        "formula": pysat_stats(formula, pool),
    }
    with Solver(name=solver_name, bootstrap_with=formula) as solver:
        if stage == "forced":
            assumptions = [
                variable if KNOWN[0][index] == "1" else -variable
                for index, variable in enumerate(xs)
            ]
            started = time.perf_counter()
            status = solver.solve(assumptions=assumptions)
            result["seconds"] = time.perf_counter() - started
            result["status"] = "sat" if status else "unsat"
            if status:
                witness = bits_from_model(solver.get_model(), xs)
                if witness != KNOWN[0]:
                    raise RuntimeError("forced witness changed")
                result["models"] = [exact_verify(witness)]
        elif stage == "first_hint":
            solver.set_phases(phases_for(KNOWN[0], xs, differences, prefixes))
            started = time.perf_counter()
            status = solver.solve()
            result["seconds"] = time.perf_counter() - started
            result["status"] = "sat" if status else "unsat"
            if status:
                result["models"] = [
                    exact_verify(bits_from_model(solver.get_model(), xs))
                ]
        elif stage == "known_chain":
            models: list[dict[str, Any]] = []
            timings: list[float] = []
            for expected in KNOWN:
                solver.set_phases(phases_for(expected, xs, differences, prefixes))
                started = time.perf_counter()
                status = solver.solve()
                timings.append(time.perf_counter() - started)
                if not status:
                    raise RuntimeError("known chain became unsatisfiable")
                bits = bits_from_model(solver.get_model(), xs)
                verified = exact_verify(bits)
                if bits != expected:
                    raise RuntimeError("phase-guided chain did not reproduce fixture")
                models.append(verified)
                block_class_pysat(solver, xs, bits)
            result.update(status="sat", seconds=sum(timings), timings=timings, models=models)
        else:
            if stage == "post_known":
                for bits in KNOWN:
                    block_class_pysat(solver, xs, bits)
                solver.set_phases(phases_for(KNOWN[0], xs, differences, prefixes))
            started = time.perf_counter()
            status = solver.solve()
            result["seconds"] = time.perf_counter() - started
            result["status"] = "sat" if status else "unsat"
            if status:
                result["models"] = [
                    exact_verify(bits_from_model(solver.get_model(), xs))
                ]
        result["solver_stats"] = solver.accum_stats()
    return result


def add_clause_cp(model: cp_model.CpModel, literals: list[Any]) -> None:
    model.AddBoolOr(literals)


def add_lex_leader_cp(model: cp_model.CpModel, xs: list[Any]) -> list[Any]:
    prefixes: list[Any] = []
    prefix = model.NewBoolVar("lex_0")
    model.Add(prefix == 1)
    prefixes.append(prefix)
    for index in range(N // 2):
        left = xs[index]
        right = xs[N - 1 - index]
        add_clause_cp(model, [prefix.Not(), left.Not(), right])
        if index + 1 == N // 2:
            break
        following = model.NewBoolVar(f"lex_{index + 1}")
        add_clause_cp(model, [following.Not(), prefix])
        add_clause_cp(model, [following.Not(), left.Not(), right])
        add_clause_cp(model, [following.Not(), left, right.Not()])
        add_clause_cp(model, [prefix.Not(), left.Not(), right.Not(), following])
        add_clause_cp(model, [prefix.Not(), left, right, following])
        prefixes.append(following)
        prefix = following
    return prefixes


def cp_formula(lex: bool, blocks: tuple[str, ...] = ()) -> tuple[Any, list[Any], dict[tuple[int, int], Any], list[Any]]:
    model = cp_model.CpModel()
    xs = [model.NewBoolVar(f"x_{index}") for index in range(N)]
    differences: dict[tuple[int, int], Any] = {}
    for lag in range(1, N):
        variables: list[Any] = []
        for index in range(N - lag):
            difference = model.NewBoolVar(f"y_{index}_{lag}")
            differences[index, lag] = difference
            variables.append(difference)
            model.AddBoolXOr([xs[index], xs[index + lag], difference.Not()])
        lower, upper = bounds(len(variables))
        model.Add(sum(variables) >= lower)
        model.Add(sum(variables) <= upper)
    model.Add(xs[0] == 0)
    model.Add(xs[1] == 0)
    prefixes = add_lex_leader_cp(model, xs) if lex else []
    for bits in blocks:
        for transformed in orbit(bits):
            model.Add(
                sum(
                    xs[index] if transformed[index] == "1" else 1 - xs[index]
                    for index in range(N)
                )
                <= N - 1
            )
    return model, xs, differences, prefixes


def cp_add_hint(
    model: cp_model.CpModel,
    bits: str,
    xs: list[Any],
    differences: dict[tuple[int, int], Any],
    prefixes: list[Any],
) -> None:
    for index, variable in enumerate(xs):
        model.AddHint(variable, int(bits[index]))
    for (index, lag), variable in differences.items():
        model.AddHint(variable, int(bits[index] != bits[index + lag]))
    prefix_equal = True
    for index, variable in enumerate(prefixes):
        model.AddHint(variable, int(prefix_equal))
        prefix_equal = prefix_equal and bits[index] == bits[N - 1 - index]


def cp_solve(model: Any, xs: list[Any], seconds: float) -> tuple[Any, dict[str, Any]]:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 1
    started = time.perf_counter()
    status_code = solver.Solve(model)
    elapsed = time.perf_counter() - started
    status_name = solver.StatusName(status_code).lower()
    output: dict[str, Any] = {
        "status": status_name,
        "seconds": elapsed,
        "solver_stats": {
            "conflicts": solver.NumConflicts(),
            "branches": solver.NumBranches(),
            "wall_time": solver.WallTime(),
        },
    }
    if status_code in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        output["models"] = [
            exact_verify("".join(str(solver.Value(variable)) for variable in xs))
        ]
    return solver, output


def run_cp(stage: str, lex: bool, time_limit: float) -> dict[str, Any]:
    blocks: tuple[str, ...] = KNOWN if stage == "post_known" else ()
    model, xs, differences, prefixes = cp_formula(lex, blocks)
    if stage == "forced":
        for index, variable in enumerate(xs):
            model.Add(variable == int(KNOWN[0][index]))
    elif stage in ("first_hint", "post_known"):
        cp_add_hint(model, KNOWN[0], xs, differences, prefixes)
    if stage == "known_chain":
        models: list[dict[str, Any]] = []
        timings: list[float] = []
        for index, expected in enumerate(KNOWN):
            chained, chained_xs, chained_differences, chained_prefixes = cp_formula(
                lex, KNOWN[:index]
            )
            cp_add_hint(
                chained,
                expected,
                chained_xs,
                chained_differences,
                chained_prefixes,
            )
            _, solved = cp_solve(chained, chained_xs, time_limit)
            if solved["status"] not in ("feasible", "optimal"):
                raise RuntimeError("CP-SAT known chain failed")
            if solved["models"][0]["bits"] != expected:
                raise RuntimeError("CP-SAT hint did not reproduce fixture")
            models.extend(solved["models"])
            timings.append(solved["seconds"])
        return {
            "backend": "cp_sat",
            "stage": stage,
            "lex_leader": lex,
            "formula": {
                "variables": len(model.Proto().variables),
                "constraints": len(model.Proto().constraints),
            },
            "status": "sat",
            "seconds": sum(timings),
            "timings": timings,
            "models": models,
        }
    _, solved = cp_solve(model, xs, time_limit)
    return {
        "backend": "cp_sat",
        "stage": stage,
        "lex_leader": lex,
        "formula": {
            "variables": len(model.Proto().variables),
            "constraints": len(model.Proto().constraints),
        },
        **solved,
    }


def worker(backend: str, stage: str, lex: bool, time_limit: float) -> dict[str, Any]:
    if backend == "cp_sat":
        return run_cp(stage, lex, time_limit)
    return run_pysat(backend, stage, lex)


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


def run_subprocess(
    backend: str, stage: str, lex: bool, time_limit: float
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--backend",
        backend,
        "--stage",
        stage,
        "--time-limit",
        str(time_limit),
    ]
    if lex:
        command.append("--lex")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=time_limit + 2.0,
        )
        return json.loads(completed.stdout)
    except subprocess.TimeoutExpired:
        return {
            "backend": backend,
            "stage": stage,
            "lex_leader": lex,
            "status": "timeout",
            "seconds": time.perf_counter() - started,
            "process_timeout": time_limit + 2.0,
        }


def suite(args: argparse.Namespace) -> None:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = args.run_id or timestamp
    run_dir = HERE / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, Any]] = []
    for lex in (False, True):
        for backend in BACKENDS:
            for stage in STAGES:
                limit = args.hard_time_limit if stage in ("cold", "post_known") else 20.0
                result = run_subprocess(backend, stage, lex, limit)
                results.append(result)
                print(
                    backend,
                    f"lex={int(lex)}",
                    stage,
                    result["status"],
                    f"seconds={result.get('seconds', 0):.6f}",
                    flush=True,
                )
    record = {
        "schema": "flat-psl4-sat-pb-feasibility-v1",
        "created_utc": timestamp,
        "run_id": run_id,
        "python": sys.version,
        "known_canonical_fixtures": KNOWN,
        "hard_time_limit": args.hard_time_limit,
        "results": results,
        "scope": (
            "Feasibility benchmark. Hinted fixtures validate encoding and "
            "blocked solution-to-solution mechanics; they do not demonstrate "
            "cold discovery or complete enumeration."
        ),
    }
    path = run_dir / "benchmark.json"
    atomic_json(path, record)
    print(f"receipt={path}")
    print(f"sha256={hashlib.sha256(path.read_bytes()).hexdigest()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--backend", choices=BACKENDS)
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--lex", action="store_true")
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--hard-time-limit", type=float, default=5.0)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.worker:
        if not args.backend or not args.stage:
            parser.error("--worker requires --backend and --stage")
        print(json.dumps(worker(args.backend, args.stage, args.lex, args.time_limit)))
    else:
        suite(args)


if __name__ == "__main__":
    main()
