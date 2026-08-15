#!/usr/bin/env python3
"""Exact PSL-4 family enumeration using MiniCard's native constraints."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor" / "python_sat"))
from pysat.solvers import Solver  # noqa: E402

N = 70


def autocorr(a: tuple[int, ...]) -> tuple[int, ...]:
    x = np.asarray(a, dtype=np.int16)
    return tuple(int(np.dot(x[:-k], x[k:])) for k in range(1, N))


def transforms(a: tuple[int, ...]) -> list[tuple[int, ...]]:
    alt = tuple(v if i % 2 == 0 else -v for i, v in enumerate(a))
    return [
        b
        for q in (a, a[::-1], alt, alt[::-1])
        for b in (q, tuple(-v for v in q))
    ]


def canonical(a: tuple[int, ...]) -> tuple[int, ...]:
    return min(transforms(a))


def bits_hex(a: tuple[int, ...]) -> str:
    return f"{int(''.join('1' if v == 1 else '0' for v in a), 2):018X}"


def atomic_json(path: Path, obj: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def main() -> None:
    t0 = time.time()
    xs = list(range(1, N + 1))
    # Published highest-merit-factor PSL-4 example at length 70.  Its printed
    # two leading hex padding bits are removed by zfill(N); negate it so both
    # endpoints satisfy our +1 normalization.  Complete phase hints turn the
    # first SAT witness into an immediate encoding check.
    seed_bits = f"{int('01C2FFD4AF33356596', 16):0{N}b}"
    seed = tuple(1 if bit == "0" else -1 for bit in seed_bits)
    assert seed[0] == seed[-1] == 1
    next_var = N + 1
    clauses: list[list[int]] = [[xs[0]], [xs[-1]]]
    atmosts: list[tuple[list[int], int]] = []
    phases = [x if seed[i] == 1 else -x for i, x in enumerate(xs)]

    for lag in range(1, N):
        m = N - lag
        ys = []
        for i in range(m):
            y = next_var
            next_var += 1
            ys.append(y)
            x, z = xs[i], xs[i + lag]
            phases.append(y if seed[i] != seed[i + lag] else -y)
            clauses.extend(
                [[-x, -z, -y], [x, z, -y], [x, -z, y], [-x, z, y]]
            )
        lo = (m - 4 + 1) // 2  # ceil((m-4)/2)
        hi = (m + 4) // 2
        if hi < m:
            atmosts.append((ys, hi))
        if lo > 0:
            atmosts.append(([-y for y in ys], m - lo))

    print(
        f"native formula vars={next_var-1} clauses={len(clauses)} "
        f"atmosts={len(atmosts)}",
        flush=True,
    )
    raw: list[tuple[int, ...]] = []
    with Solver(name="minicard", bootstrap_with=clauses) as solver:
        for lits, bound in atmosts:
            solver.add_atmost(lits, bound)
        solver.set_phases(phases)
        while solver.solve():
            positive = {v for v in solver.get_model() if v > 0}
            a = tuple(1 if x in positive else -1 for x in xs)
            corr = autocorr(a)
            assert max(abs(v) for v in corr) <= 4
            raw.append(a)
            solver.add_clause([-x if x in positive else x for x in xs])
            if len(raw) <= 5 or len(raw) % 25 == 0:
                print(f"raw={len(raw)} elapsed={time.time()-t0:.2f}s", flush=True)

    classes = {canonical(a): a for a in raw}
    records = []
    for key, a in sorted(classes.items()):
        corr = autocorr(a)
        records.append(
            {
                "coefficients": list(a),
                "hex": bits_hex(a),
                "max_abs_autocorrelation": max(abs(v) for v in corr),
                "merit_factor": N * N / (2 * sum(v * v for v in corr)),
                "canonical_sha256": hashlib.sha256(bytes(v > 0 for v in key)).hexdigest(),
            }
        )
    result = {
        "n": N,
        "psl_bound": 4,
        "solver": "minicard-native",
        "variables": next_var - 1,
        "clauses": len(clauses),
        "native_atmost_constraints": len(atmosts),
        "raw_endpoint_normalized_solutions": len(raw),
        "equivalence_classes": len(records),
        "elapsed_seconds": time.time() - t0,
        "records": records,
    }
    out = HERE / "psl4_length70_native.json"
    atomic_json(out, result)
    print(
        f"done raw={len(raw)} classes={len(records)} "
        f"elapsed={time.time()-t0:.2f}s out={out}",
        flush=True,
    )


if __name__ == "__main__":
    main()
