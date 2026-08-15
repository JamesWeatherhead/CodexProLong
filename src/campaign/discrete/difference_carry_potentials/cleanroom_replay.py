#!/usr/bin/env python3
"""Local-import-free reconstruction and replay of the frozen CP-SAT formula.

This is intentionally separate from solver.py and audit.py.  It uses only the
frozen factual input, the OR-Tools public API, and the Python standard library.
It independently derives the boundary graph, enumerates the finite shape
tables, reconstructs deterministic model bytes, compares them with model.pb,
and solves with one worker.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import ortools
from ortools.sat.python import cp_model


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "20260815T121057Z"
EXPECTED_INPUT_SHA256 = (
    "64ff8b828048a103057a5359290ebe14338f56f1a30f4d41e82648f13e42a727"
)
EXPECTED_MODEL_SHA256 = (
    "0fcb2054f099e398959e5318033f8969582becb5d6bbce072c40a6d455b0e4b4"
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def required_carries(gap: int, modulus: int, target: int) -> tuple[int, ...]:
    positive = range(0, (target - gap) // modulus + 1)
    opposite = range(1, (target - (modulus - gap)) // modulus + 2)
    return tuple(sorted((*positive, *(-value for value in opposite))))


def derive_from_scratch() -> tuple[
    cp_model.CpModel, bytes, dict[str, Any]
]:
    input_path = HERE / "frozen_inputs.json"
    if digest(input_path) != EXPECTED_INPUT_SHA256:
        raise AssertionError("clean-room frozen-input hash mismatch")
    data = json.loads(input_path.read_text(encoding="utf-8"))
    residues = data["core"]["residues"]
    modulus = data["core"]["modulus"]
    target = data["leader"]["first_missing"]

    if len(residues) != 90 or residues != sorted(set(residues)) or residues[0] != 0:
        raise AssertionError("clean-room residue shape mismatch")
    if hashlib.sha256(canonical(residues)).hexdigest() != data["core"]["residues_sha256"]:
        raise AssertionError("clean-room residue digest mismatch")
    cyclic = collections.Counter(
        (left - right) % modulus
        for left in residues
        for right in residues
        if left != right
    )
    if set(cyclic) != set(range(1, modulus)) or set(cyclic.values()) != {1}:
        raise AssertionError("clean-room core is not a perfect cyclic difference set")

    low: list[tuple[int, int]] = []
    middle: list[tuple[int, int]] = []
    high: list[tuple[int, int]] = []
    adjacency = {residue: set() for residue in residues}
    for upper_index, upper in enumerate(residues):
        for lower in residues[:upper_index]:
            carries = required_carries(upper - lower, modulus, target)
            pair = (upper, lower)
            if carries == tuple(range(-6, 7)):
                low.append(pair)
                adjacency[upper].add(lower)
                adjacency[lower].add(upper)
            elif carries == tuple(range(-6, 6)):
                middle.append(pair)
            elif carries == tuple(range(-7, 6)):
                high.append(pair)
            else:
                raise AssertionError(f"unexpected clean-room carries: {pair} {carries}")
    if (len(low), len(middle), high) != (1043, 2961, [(6967, 0)]):
        raise AssertionError("clean-room edge partition mismatch")
    if min(map(len, adjacency.values())) != 14:
        raise AssertionError("clean-room boundary degree mismatch")

    distance = {0: 0}
    queue: collections.deque[int] = collections.deque([0])
    while queue:
        current = queue.popleft()
        for neighbor in sorted(adjacency[current]):
            if neighbor not in distance:
                distance[neighbor] = distance[current] + 1
                queue.append(neighbor)
    if len(distance) != 90 or max(distance.values()) != 7:
        raise AssertionError("clean-room boundary graph mismatch")

    # Independent form of the cardinality argument.  Every column pair needs
    # at least 12 products; a minimum of 1 or 2 costs >360 total points.  A
    # minimum of 3 leaves exactly one possible size-5 neighbor, but its 14
    # boundary neighbors each need product >=13 and hence size >=5.
    if 1 + 89 * 12 <= 360 or 2 + 89 * 6 <= 360:
        raise AssertionError("clean-room cardinality inequalities changed")
    if min(map(len, adjacency.values())) <= 1:
        raise AssertionError("clean-room size-3 contradiction unavailable")

    shapes: list[tuple[int, int, int, int]] = []
    for first in range(1, 13):
        for second in range(first + 1, 13):
            for third in range(second + 1, 13):
                shapes.append((0, first, second, third))
    if len(shapes) != 220:
        raise AssertionError("clean-room shape enumeration mismatch")

    def table(required: range) -> list[tuple[int, int, int]]:
        rows: list[tuple[int, int, int]] = []
        required_values = tuple(required)
        for left_index, left_shape in enumerate(shapes):
            for right_index, right_shape in enumerate(shapes):
                raw = {
                    left_value - right_value
                    for left_value in left_shape
                    for right_value in right_shape
                }
                for translation_delta in range(-19, 19):
                    if all(
                        value - translation_delta in raw
                        for value in required_values
                    ):
                        rows.append(
                            (left_index, right_index, translation_delta)
                        )
        return rows

    low_table = table(range(-6, 7))
    high_table = table(range(-7, 6))
    if len(low_table) != 238 or len(high_table) != 238:
        raise AssertionError("clean-room compatibility count mismatch")

    model = cp_model.CpModel()
    shape_variables: dict[int, cp_model.IntVar] = {}
    translation_variables: dict[int, cp_model.IntVar] = {}
    for residue in residues:
        shape_variables[residue] = model.new_int_var(0, 219, f"shape_{residue}")
        radius = 6 * distance[residue]
        translation_variables[residue] = model.new_int_var(
            -radius, radius, f"translation_{residue}"
        )
    model.add(translation_variables[0] == 0)
    for index, (upper, lower) in enumerate(low):
        delta = model.new_int_var(-6, 6, f"low_delta_{index}")
        model.add(
            delta == translation_variables[upper] - translation_variables[lower]
        )
        model.add_allowed_assignments(
            [shape_variables[upper], shape_variables[lower], delta], low_table
        )
    for index, (upper, lower) in enumerate(high):
        delta = model.new_int_var(-7, 5, f"high_delta_{index}")
        model.add(
            delta == translation_variables[upper] - translation_variables[lower]
        )
        model.add_allowed_assignments(
            [shape_variables[upper], shape_variables[lower], delta], high_table
        )

    model_bytes = model.proto.SerializeToString(deterministic=True)
    facts = {
        "low_edges": len(low),
        "middle_edges_omitted": len(middle),
        "high_edges": len(high),
        "minimum_boundary_degree": min(map(len, adjacency.values())),
        "maximum_boundary_distance": max(distance.values()),
        "shapes": len(shapes),
        "low_tuples": len(low_table),
        "high_tuples": len(high_table),
        "variables": len(model.proto.variables),
        "constraints": len(model.proto.constraints),
        "bytes": len(model_bytes),
    }
    return model, model_bytes, facts


def replay(seconds: float) -> dict[str, Any]:
    model, model_bytes, facts = derive_from_scratch()
    observed_hash = hashlib.sha256(model_bytes).hexdigest()
    if observed_hash != EXPECTED_MODEL_SHA256:
        raise AssertionError(f"clean-room model hash mismatch: {observed_hash}")
    if model_bytes != (RUN / "model.pb").read_bytes():
        raise AssertionError("clean-room model bytes differ from frozen formula")
    if facts != {
        "low_edges": 1043,
        "middle_edges_omitted": 2961,
        "high_edges": 1,
        "minimum_boundary_degree": 14,
        "maximum_boundary_distance": 7,
        "shapes": 220,
        "low_tuples": 238,
        "high_tuples": 238,
        "variables": 1224,
        "constraints": 2089,
        "bytes": 1928061,
    }:
        raise AssertionError(f"clean-room reconstructed facts mismatch: {facts}")

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 20260815
    solver.parameters.cp_model_presolve = True
    status_code = solver.solve(model)
    status = solver.status_name(status_code)
    if status != "INFEASIBLE":
        raise AssertionError(f"clean-room solve returned {status}")
    return {
        "schema": 1,
        "ok": True,
        "implementation": "local-import-free independent reconstruction",
        "input_sha256": EXPECTED_INPUT_SHA256,
        "model_sha256": EXPECTED_MODEL_SHA256,
        "model_bytes_equal": True,
        "ortools_version": ortools.__version__,
        "workers": 1,
        "seed": 20260815,
        "status": status,
        "wall_time_seconds": solver.wall_time,
        "facts": facts,
    }


def write_json(path: Path, value: Any) -> None:
    resolved = path.resolve()
    if HERE not in resolved.parents:
        raise ValueError("clean-room receipt must stay inside the isolated subtree")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical(value) + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{resolved.name}.", dir=resolved.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, resolved)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    receipt = replay(arguments.seconds)
    if arguments.output:
        write_json(arguments.output, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
