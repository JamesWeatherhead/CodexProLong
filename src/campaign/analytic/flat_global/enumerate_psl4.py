#!/usr/bin/env python3
"""Enumerate every length-70 binary sequence with aperiodic PSL <= 4.

The encoding is exact.  For signs a_i in {-1,+1}, introduce Boolean x_i
and mismatch bits y_{i,k} = x_i XOR x_{i+k}.  At lag k,

    C_k = (70-k) - 2 * sum_i y_{i,k}.

Thus |C_k| <= 4 is a pair of cardinality constraints.  Global negation and
alternation let us fix both endpoints to +1 for even length 70.  A generic
equivalence class then appears twice (the two reversals); canonicalization at
the end quotients reversal, negation, and alternation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "vendor" / "python_sat"))

from pysat.card import CardEnc, EncType  # noqa: E402
from pysat.formula import CNF, IDPool  # noqa: E402
from pysat.solvers import Solver  # noqa: E402


N = 70


def xor_equiv(cnf: CNF, x: int, z: int, y: int) -> None:
    """Append clauses for y <-> (x XOR z)."""
    cnf.extend(
        [
            [-x, -z, -y],
            [x, z, -y],
            [x, -z, y],
            [-x, z, y],
        ]
    )


def build_formula() -> tuple[CNF, IDPool, list[int]]:
    pool = IDPool(start_from=N + 1)
    cnf = CNF()
    xs = list(range(1, N + 1))

    # Negation fixes x_0; alternation (for even N) fixes x_{N-1} too.
    cnf.append([xs[0]])
    cnf.append([xs[-1]])

    for lag in range(1, N):
        m = N - lag
        ys: list[int] = []
        for i in range(m):
            y = pool.id(("xor", i, lag))
            ys.append(y)
            xor_equiv(cnf, xs[i], xs[i + lag], y)

        lo = math.ceil((m - 4) / 2)
        hi = math.floor((m + 4) / 2)
        if lo > 0:
            cnf.extend(
                CardEnc.atleast(
                    ys, bound=lo, vpool=pool, encoding=EncType.seqcounter
                ).clauses
            )
        if hi < m:
            cnf.extend(
                CardEnc.atmost(
                    ys, bound=hi, vpool=pool, encoding=EncType.seqcounter
                ).clauses
            )
    return cnf, pool, xs


def autocorr(a: tuple[int, ...]) -> tuple[int, ...]:
    x = np.asarray(a, dtype=np.int16)
    return tuple(int(np.dot(x[:-k], x[k:])) for k in range(1, N))


def transforms(a: tuple[int, ...]) -> list[tuple[int, ...]]:
    alt = tuple(v if i % 2 == 0 else -v for i, v in enumerate(a))
    out = []
    for b in (a, a[::-1], alt, alt[::-1]):
        out.append(b)
        out.append(tuple(-v for v in b))
    return out


def canonical(a: tuple[int, ...]) -> tuple[int, ...]:
    return min(transforms(a))


def bits_hex(a: tuple[int, ...]) -> str:
    bits = "".join("1" if v == 1 else "0" for v in a)
    return f"{int(bits, 2):018X}"


def atomic_json(path: Path, obj: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", default="cadical195")
    ap.add_argument("--out", type=Path, default=HERE / "psl4_length70.json")
    args = ap.parse_args()

    t0 = time.time()
    cnf, pool, xs = build_formula()
    print(
        f"formula vars={pool.top} clauses={len(cnf.clauses)} solver={args.solver}",
        flush=True,
    )

    raw: list[tuple[int, ...]] = []
    with Solver(name=args.solver, bootstrap_with=cnf.clauses) as solver:
        while solver.solve():
            model = set(v for v in solver.get_model() if v > 0)
            a = tuple(1 if x in model else -1 for x in xs)
            corr = autocorr(a)
            assert max(abs(v) for v in corr) <= 4
            raw.append(a)
            # Block the projected coefficient vector, not an auxiliary model.
            solver.add_clause([-x if x in model else x for x in xs])
            if len(raw) % 25 == 0:
                print(f"raw={len(raw)} elapsed={time.time()-t0:.2f}s", flush=True)

    classes: dict[tuple[int, ...], tuple[int, ...]] = {}
    for a in raw:
        classes.setdefault(canonical(a), a)

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
        "endpoint_normalization": [1, 1],
        "solver": args.solver,
        "formula_variables": pool.top,
        "formula_clauses": len(cnf.clauses),
        "raw_endpoint_normalized_solutions": len(raw),
        "equivalence_classes": len(records),
        "elapsed_seconds": time.time() - t0,
        "records": records,
    }
    atomic_json(args.out, result)
    print(
        f"done raw={len(raw)} classes={len(records)} "
        f"elapsed={time.time()-t0:.2f}s out={args.out}",
        flush=True,
    )


if __name__ == "__main__":
    main()
