#!/usr/bin/env python3
"""Multiresolution search over patched relative-difference-set block lifts.

For odd prime ``p``, each quadratic graph

    Q_c,d = {(x, q*x^2 + c*x + d): x in F_p}

is a relative difference set in F_p^2: its directed differences cover every
element outside one order-p subgroup exactly once.  Distinct slopes also make
cross-block directed differences cover the whole product group.  We embed four
such graphs in integer cells at the sparse-ruler heights ``{0,1,4,6}`` (or its
reflection), and optimize the carry orientation induced by a common GL(2,p)
map.  This changes every block support, rather than moving one or two points or
translating an incumbent Singer block.

Modular coverage does *not* imply consecutive integer coverage.  The search
therefore scores literal integer differences at every trial, uses a nested
sequence of prefix masks as its smooth objective, and replays each retained
frontier through the pinned Arena verifier.  Checkpoints are atomic and fully
deterministic for a fixed seed and budget.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from exact import ROOT, atomic_json, difference_bits, first_missing, load_live, replay


CHECKPOINT = ROOT / "checkpoints" / "relative_graph.json"
BEST = ROOT / "candidates" / "relative_graph_best.json"
HEIGHTS = ((0, 1, 4, 6), (0, 2, 5, 6))


def is_prime(value: int) -> bool:
    if value < 2:
        return False
    if value % 2 == 0:
        return value == 2
    divisor = 3
    while divisor * divisor <= value:
        if value % divisor == 0:
            return False
        divisor += 2
    return True


@dataclass(frozen=True)
class Parameters:
    p: int
    heights: tuple[int, int, int, int]
    quadratic: int
    matrix: tuple[int, int, int, int]
    slopes: tuple[int, int, int, int]
    intercepts: tuple[int, int, int, int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "p": self.p,
            "heights": list(self.heights),
            "quadratic": self.quadratic,
            "matrix": list(self.matrix),
            "slopes": list(self.slopes),
            "intercepts": list(self.intercepts),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Parameters":
        return cls(
            int(value["p"]),
            tuple(map(int, value["heights"])),
            int(value["quadratic"]),
            tuple(map(int, value["matrix"])),
            tuple(map(int, value["slopes"])),
            tuple(map(int, value["intercepts"])),
        )


def validate(parameters: Parameters) -> None:
    p = parameters.p
    if not is_prime(p) or p == 2:
        raise ValueError("p must be an odd prime")
    if parameters.heights not in HEIGHTS:
        raise ValueError("unknown four-mark sparse-ruler height set")
    a, b, c, d = parameters.matrix
    if (a * d - b * c) % p == 0:
        raise ValueError("matrix is singular")
    if parameters.quadratic % p == 0:
        raise ValueError("quadratic coefficient must be nonzero")
    if len(set(value % p for value in parameters.slopes)) != 4:
        raise ValueError("the four slopes must be distinct")


def construct(parameters: Parameters) -> list[int]:
    validate(parameters)
    p = parameters.p
    cell = p * p
    a, b, c, d = parameters.matrix
    values: list[int] = []
    for height, slope, intercept in zip(
        parameters.heights, parameters.slopes, parameters.intercepts
    ):
        for x in range(p):
            y = (parameters.quadratic * x * x + slope * x + intercept) % p
            low = (a * x + b * y) % p
            high = (c * x + d * y) % p
            values.append(height * cell + low + p * high)
    if len(set(values)) != 4 * p:
        raise RuntimeError("relative-graph blocks unexpectedly collided")
    return sorted(values)


def random_parameters(p: int, heights: tuple[int, int, int, int], rng: random.Random) -> Parameters:
    while True:
        matrix = tuple(rng.randrange(p) for _ in range(4))
        if (matrix[0] * matrix[3] - matrix[1] * matrix[2]) % p:
            break
    return Parameters(
        p,
        heights,
        rng.randrange(1, p),
        matrix,
        tuple(rng.sample(range(p), 4)),
        tuple(rng.randrange(p) for _ in range(4)),
    )


def replace_coordinate(parameters: Parameters, index: int, value: int) -> Parameters | None:
    flat = [
        parameters.quadratic,
        *parameters.matrix,
        *parameters.slopes,
        *parameters.intercepts,
    ]
    flat[index] = value
    candidate = Parameters(
        parameters.p,
        parameters.heights,
        flat[0],
        tuple(flat[1:5]),
        tuple(flat[5:9]),
        tuple(flat[9:13]),
    )
    try:
        validate(candidate)
    except ValueError:
        return None
    return candidate


def mask(horizon: int) -> int:
    return (1 << (horizon + 1)) - 2


def signature(bits: int, horizon: int) -> tuple[int, int, int]:
    """Smooth curriculum objective, followed by the literal prefix."""
    missing = (mask(horizon) & ~bits).bit_count()
    return (-missing, first_missing(bits), bits.bit_count())


def curriculum(prefix: int, target: int, cell: int) -> int:
    horizon = 512
    while horizon <= prefix and horizon < target:
        horizon *= 2
    useful = sorted(set([horizon, cell, 2 * cell, 4 * cell, target]))
    return min(value for value in useful if value > prefix) if prefix < target else target


def exact_record(parameters: Parameters, live: dict[str, Any]) -> tuple[dict[str, Any], int]:
    values = construct(parameters)
    bits = difference_bits(values)
    result = replay(values, live)
    result["parameters"] = parameters.as_dict()
    result["difference_count"] = bits.bit_count()
    result["required_coverage"] = math.ceil(
        len(values) ** 2 / live["gate_score"]
    )
    result.pop("payload")
    return result, bits


def checkpoint_state(
    live: dict[str, Any], seed: int, budgets: dict[str, int], records: list[dict[str, Any]]
) -> dict[str, Any]:
    best = max(records, key=lambda record: (record["coverage"], record["difference_count"]))
    return {
        "schema": 1,
        "family": "quadratic relative-difference-set graphs in four integer cells",
        "seed": seed,
        "budgets": budgets,
        "verifier_sha256": live["verifier_sha256"],
        "leader_id": live["leader_id"],
        "leader_payload_sha256": live["leader_payload_sha256"],
        "leader_score": live["leader_score"],
        "leader_coverage": live["leader_coverage"],
        "gate_score": live["gate_score"],
        "records": records,
        "best": best,
        "gate_cleared": bool(best["gate_cleared"]),
        "complete": False,
    }


def write_best(record: dict[str, Any], parameters: Parameters, live: dict[str, Any]) -> None:
    result = replay(construct(parameters), live)
    payload = {
        "schema": 1,
        "verifier_sha256": live["verifier_sha256"],
        "construction": "quadratic_relative_graph_blocks",
        "parameters": parameters.as_dict(),
        "receipt": {key: value for key, value in result.items() if key != "payload"},
        "payload": result["payload"],
    }
    if payload["receipt"]["payload_sha256"] != record["payload_sha256"]:
        raise RuntimeError("candidate receipt changed during serialization")
    atomic_json(BEST, payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primes", default="83,89,97")
    parser.add_argument("--random-starts", type=int, default=300)
    parser.add_argument("--elite", type=int, default=2)
    parser.add_argument("--sweeps", type=int, default=1)
    parser.add_argument("--seed", type=int, default=2026081501)
    args = parser.parse_args()
    primes = [int(value) for value in args.primes.split(",") if value.strip()]
    if any(not is_prime(value) or value == 2 for value in primes):
        raise SystemExit("--primes must contain odd primes")
    if min(args.random_starts, args.elite, args.sweeps) < 1:
        raise SystemExit("all budgets must be positive")

    live = load_live()
    rng = random.Random(args.seed)
    budgets = {
        "random_starts_per_prime_height": args.random_starts,
        "elite_per_prime_height": args.elite,
        "coordinate_sweeps": args.sweeps,
    }
    records: list[dict[str, Any]] = []
    best_parameters: Parameters | None = None
    best_record: dict[str, Any] | None = None
    started = time.monotonic()

    for p in primes:
        cell = p * p
        target = math.ceil((4 * p) ** 2 / live["gate_score"])
        for heights in HEIGHTS:
            pool: list[tuple[tuple[int, int, int], Parameters, int]] = []
            initial_horizon = min(512, target)
            for trial in range(args.random_starts):
                parameters = random_parameters(p, heights, rng)
                bits = difference_bits(construct(parameters))
                pool.append((signature(bits, initial_horizon), parameters, bits))
                if (trial + 1) % 50 == 0:
                    pool.sort(key=lambda item: item[0], reverse=True)
                    pool = pool[: max(args.elite, 4)]
            pool.sort(key=lambda item: item[0], reverse=True)

            for _, initial, initial_bits in pool[: args.elite]:
                parameters = initial
                bits = initial_bits
                for _sweep in range(args.sweeps):
                    prefix = first_missing(bits)
                    horizon = curriculum(prefix, target, cell)
                    changed = False
                    for coordinate in range(13):
                        current = signature(bits, horizon)
                        selected = parameters
                        selected_bits = bits
                        start_value = [
                            parameters.quadratic,
                            *parameters.matrix,
                            *parameters.slopes,
                            *parameters.intercepts,
                        ][coordinate]
                        values: Iterable[int] = range(1, p) if coordinate == 0 else range(p)
                        for value in values:
                            if value == start_value:
                                continue
                            candidate = replace_coordinate(parameters, coordinate, value)
                            if candidate is None:
                                continue
                            candidate_bits = difference_bits(construct(candidate))
                            candidate_signature = signature(candidate_bits, horizon)
                            if candidate_signature > current:
                                current = candidate_signature
                                selected = candidate
                                selected_bits = candidate_bits
                        if selected != parameters:
                            parameters = selected
                            bits = selected_bits
                            changed = True
                    if not changed:
                        break

                record, bits = exact_record(parameters, live)
                record.update(
                    {
                        "prime": p,
                        "height_assignment": list(heights),
                        "elapsed_seconds": round(time.monotonic() - started, 6),
                    }
                )
                records.append(record)
                if best_record is None or (
                    record["coverage"], record["difference_count"]
                ) > (best_record["coverage"], best_record["difference_count"]):
                    best_record = record
                    best_parameters = parameters
                    write_best(record, parameters, live)
                state = checkpoint_state(live, args.seed, budgets, records)
                atomic_json(CHECKPOINT, state)
                print(json.dumps(record, sort_keys=True), flush=True)
                if record["gate_cleared"]:
                    state["complete"] = True
                    state["conclusion"] = "exact verifier-valid gate-clearer found"
                    atomic_json(CHECKPOINT, state)
                    return 0

    if best_record is None or best_parameters is None:
        raise RuntimeError("search produced no records")
    state = checkpoint_state(live, args.seed, budgets, records)
    state["complete"] = True
    state["conclusion"] = (
        "Bounded relative-difference-set search did not clear the exact live gate. "
        "The best raw embedding is retained as a quantified topology frontier."
    )
    atomic_json(CHECKPOINT, state)
    print(json.dumps(state["best"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
