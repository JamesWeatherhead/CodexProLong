#!/usr/bin/env python3
"""Exact carry-potential relaxation for the fixed Singer residue core.

The Arena candidate itself is never loaded here.  The only construction input
is the attributed 90-residue core in ``frozen_inputs.json``.  The program
proves a finite reduction for arbitrary (unbounded) integer lifts of those
residues, builds a necessary binary-table CP-SAT relaxation, and journals the
result.  INFEASIBLE closes the declared family; SAT would only mean that this
necessary relaxation survived and would not be an Arena candidate.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import itertools
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import ortools
from ortools.sat.python import cp_model


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[2]
DEFAULT_INPUT = ROOT / "frozen_inputs.json"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    tmp = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, canonical_bytes(value) + b"\n")


def repository_relative(path: Path) -> str:
    """Return a stable repository-relative path or reject the path."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError as error:
        raise ValueError(f"path is outside the repository: {resolved}") from error


def load_inputs(path: Path = DEFAULT_INPUT) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    residues = data["core"]["residues"]
    digest = sha256_bytes(canonical_bytes(residues))
    expected = data["core"]["residues_sha256"]
    if digest != expected:
        raise ValueError(f"residue hash mismatch: {digest} != {expected}")
    return data


def validate_perfect_difference_set(residues: list[int], modulus: int) -> None:
    if len(residues) != 90 or len(set(residues)) != 90:
        raise ValueError("expected 90 distinct residues")
    if residues != sorted(residues) or residues[0] != 0:
        raise ValueError("residues must be sorted and normalized at zero")
    if not all(0 <= residue < modulus for residue in residues):
        raise ValueError("residue outside modulus")
    counts = collections.Counter(
        (a - b) % modulus for a in residues for b in residues if a != b
    )
    if len(counts) != modulus - 1:
        raise ValueError("not every nonzero cyclic difference occurs")
    bad = [difference for difference in range(1, modulus) if counts[difference] != 1]
    if bad:
        raise ValueError(f"not a perfect cyclic difference set: {bad[:10]}")


def required_quotients(gap: int, modulus: int, target: int) -> tuple[int, ...]:
    """Height differences forced by literal targets in both residue classes.

    For an actual positive residue gap ``g``, targets congruent to ``g`` use
    ``g + q*m`` and targets congruent to ``-g`` use ``-g + (q+1)*m``.
    The latter therefore require the negative height difference ``-(q+1)``.
    """

    if not 0 < gap < modulus:
        raise ValueError("gap must be a nonzero residue representative")
    required: set[int] = set()
    quotient = 0
    while gap + quotient * modulus <= target:
        required.add(quotient)
        quotient += 1
    quotient = 0
    complement = modulus - gap
    while complement + quotient * modulus <= target:
        required.add(-(quotient + 1))
        quotient += 1
    return tuple(sorted(required))


@dataclass(frozen=True)
class Edge:
    upper: int
    lower: int
    gap: int
    required: tuple[int, ...]


def derive_edges(
    residues: list[int], modulus: int, target: int
) -> tuple[list[Edge], list[Edge], list[Edge]]:
    boundary_low: list[Edge] = []
    middle: list[Edge] = []
    boundary_high: list[Edge] = []
    for index, upper in enumerate(residues):
        for lower in residues[:index]:
            gap = upper - lower
            required = required_quotients(gap, modulus, target)
            edge = Edge(upper, lower, gap, required)
            if required == tuple(range(-6, 7)):
                boundary_low.append(edge)
            elif required == tuple(range(-6, 6)):
                middle.append(edge)
            elif required == tuple(range(-7, 6)):
                boundary_high.append(edge)
            else:
                raise ValueError(f"unexpected quotient interval for gap {gap}: {required}")
    return boundary_low, middle, boundary_high


def graph_facts(residues: list[int], boundary_low: list[Edge]) -> dict[str, Any]:
    adjacency = {residue: set() for residue in residues}
    for edge in boundary_low:
        adjacency[edge.upper].add(edge.lower)
        adjacency[edge.lower].add(edge.upper)
    distances = {0: 0}
    queue: collections.deque[int] = collections.deque([0])
    while queue:
        current = queue.popleft()
        for neighbor in sorted(adjacency[current]):
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
    if set(distances) != set(residues):
        raise ValueError("13-quotient boundary graph is disconnected")
    degrees = {residue: len(adjacency[residue]) for residue in residues}
    return {
        "adjacency": adjacency,
        "distances": distances,
        "connected": True,
        "minimum_degree": min(degrees.values()),
        "maximum_degree": max(degrees.values()),
        "distance_from_zero_maximum": max(distances.values()),
        "degree_histogram": dict(sorted(collections.Counter(degrees.values()).items())),
    }


def cardinality_reduction(
    residue_count: int, total_size: int, minimum_boundary_degree: int
) -> dict[str, Any]:
    """Return the exact count argument forcing four points per residue.

    Every residue pair needs at least 12 distinct height differences.  Thus a
    smallest column of size 1 or 2 makes the total exceed 360.  If it has size
    3, all other columns have size at least 4; at total 360 there can be only
    one size-5 column.  A boundary neighbor needs 13 differences, hence size
    at least 5 against the size-3 column.  Minimum boundary degree 14 is a
    contradiction.  Therefore every column has size at least 4, and the total
    forces all 90 sizes to equal 4.
    """

    if residue_count != 90 or total_size != 360:
        raise ValueError("this reduction is specialized to 90 columns and size 360")
    lower_if_min_1 = 1 + (residue_count - 1) * 12
    lower_if_min_2 = 2 + (residue_count - 1) * 6
    if lower_if_min_1 <= total_size or lower_if_min_2 <= total_size:
        raise AssertionError("minimum-column count reduction failed")
    if minimum_boundary_degree < 2:
        raise AssertionError("size-3 contradiction needs at least two boundary neighbors")
    return {
        "pairwise_minimum_required_distinct_differences": 12,
        "boundary_required_distinct_differences": 13,
        "total_lower_bound_if_minimum_column_size_1": lower_if_min_1,
        "total_lower_bound_if_minimum_column_size_2": lower_if_min_2,
        "size_3_only_possible_raw_pattern": {"size_3_columns": 1, "size_5_columns": 1, "size_4_columns": 88},
        "size_3_boundary_neighbors_required_at_least_5": minimum_boundary_degree,
        "size_3_available_columns_of_size_at_least_5": 1,
        "conclusion": "all_90_columns_have_size_4",
    }


def normalized_four_shapes() -> list[tuple[int, int, int, int]]:
    """All normalized four-point shapes that can touch a 13-value edge.

    On such an edge at least 13 of the 16 ordered cross pairs land in an
    interval of diameter 12.  For any two points on one side, their eight
    incident pairs contain at least five in-interval pairs (globally only
    three can be outside), so some opposite point is shared.  Their separation
    is at most 12.  Hence each side has span at most 12.
    """

    return [(0, *tail) for tail in itertools.combinations(range(1, 13), 3)]


def compatible_tuples(
    shapes: list[tuple[int, int, int, int]], required: Iterable[int]
) -> list[tuple[int, int, int]]:
    required_set = set(required)
    if not required_set:
        raise ValueError("empty requirement")
    # A required value lies in [-7, 6], while normalized shape differences
    # lie in [-12, 12].  [-19, 18] therefore exhausts every possible offset.
    output: list[tuple[int, int, int]] = []
    for left_index, left in enumerate(shapes):
        for right_index, right in enumerate(shapes):
            raw = {a - b for a in left for b in right}
            for offset in range(-19, 19):
                if required_set.issubset({offset + value for value in raw}):
                    output.append((left_index, right_index, offset))
    return output


@dataclass
class Reduction:
    model: cp_model.CpModel
    inputs: dict[str, Any]
    facts: dict[str, Any]
    model_bytes: bytes


def build_reduction(input_path: Path = DEFAULT_INPUT) -> Reduction:
    inputs = load_inputs(input_path)
    residues = inputs["core"]["residues"]
    modulus = inputs["core"]["modulus"]
    target = inputs["leader"]["first_missing"]
    validate_perfect_difference_set(residues, modulus)
    low, middle, high = derive_edges(residues, modulus, target)
    graph = graph_facts(residues, low)
    count_proof = cardinality_reduction(
        len(residues), inputs["leader"]["size"], graph["minimum_degree"]
    )
    shapes = normalized_four_shapes()
    low_table = compatible_tuples(shapes, range(-6, 7))
    high_table = compatible_tuples(shapes, range(-7, 6))

    if len(shapes) != 220:
        raise AssertionError("shape enumeration changed")
    if len(low_table) != 238 or len(high_table) != 238:
        raise AssertionError("boundary table enumeration changed")
    low_offsets = sorted({row[2] for row in low_table})
    high_offsets = sorted({row[2] for row in high_table})
    if low_offsets != list(range(-6, 7)):
        raise AssertionError("unexpected low-boundary offsets")
    if high_offsets != list(range(-7, 6)):
        raise AssertionError("unexpected high-boundary offsets")

    model = cp_model.CpModel()
    shape_vars: dict[int, cp_model.IntVar] = {}
    translation_vars: dict[int, cp_model.IntVar] = {}
    for residue in residues:
        distance = graph["distances"][residue]
        shape_vars[residue] = model.new_int_var(0, len(shapes) - 1, f"shape_{residue}")
        translation_vars[residue] = model.new_int_var(
            -6 * distance, 6 * distance, f"translation_{residue}"
        )
    model.add(translation_vars[0] == 0)

    for index, edge in enumerate(low):
        delta = model.new_int_var(-6, 6, f"low_delta_{index}")
        model.add(delta == translation_vars[edge.upper] - translation_vars[edge.lower])
        model.add_allowed_assignments(
            [shape_vars[edge.upper], shape_vars[edge.lower], delta], low_table
        )
    for index, edge in enumerate(high):
        delta = model.new_int_var(-7, 5, f"high_delta_{index}")
        model.add(delta == translation_vars[edge.upper] - translation_vars[edge.lower])
        model.add_allowed_assignments(
            [shape_vars[edge.upper], shape_vars[edge.lower], delta], high_table
        )

    model_bytes = model.proto.SerializeToString(deterministic=True)
    proto = model.proto
    facts = {
        "modulus": modulus,
        "target_coverage": target,
        "residue_count": len(residues),
        "perfect_ordered_nonzero_differences": modulus - 1,
        "unordered_residue_pairs": len(low) + len(middle) + len(high),
        "boundary_low_edges": len(low),
        "middle_edges_omitted_from_relaxation": len(middle),
        "boundary_high_edges": len(high),
        "boundary_high_edge_records": [
            {"upper": edge.upper, "lower": edge.lower, "gap": edge.gap}
            for edge in high
        ],
        "boundary_graph": {
            key: value for key, value in graph.items() if key not in {"adjacency", "distances"}
        },
        "cardinality_reduction": count_proof,
        "normalized_shape_count": len(shapes),
        "low_boundary_allowed_tuples": len(low_table),
        "high_boundary_allowed_tuples": len(high_table),
        "low_boundary_allowed_offsets": low_offsets,
        "high_boundary_allowed_offsets": high_offsets,
        "model_variables": len(proto.variables),
        "model_constraints": len(proto.constraints),
        "model_bytes": len(model_bytes),
        "model_sha256": sha256_bytes(model_bytes),
        "relaxation_scope": "all 1043 [-6,6] boundary edges plus the unique [-7,5] edge; 2961 middle edges and all residue-zero requirements omitted",
    }
    return Reduction(model=model, inputs=inputs, facts=facts, model_bytes=model_bytes)


def solve_reduction(reduction: Reduction, seconds: float, seed: int) -> dict[str, Any]:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.cp_model_presolve = True
    status_code = solver.solve(reduction.model)
    status = solver.status_name(status_code)
    return {
        "status": status,
        "status_code": int(status_code),
        "infeasible": status == "INFEASIBLE",
        "wall_time_seconds": solver.wall_time,
        "user_time_seconds": solver.user_time,
        "conflicts": solver.num_conflicts,
        "branches": solver.num_branches,
        "response_stats": solver.response_stats(),
    }


def event_records(config: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    previous = "0" * 64
    for sequence, (kind, payload) in enumerate(
        [("config", config), ("solve", result)], start=1
    ):
        record = {
            "sequence": sequence,
            "type": kind,
            "payload": payload,
            "previous_hash": previous,
        }
        record["hash"] = sha256_bytes(canonical_bytes(record))
        previous = record["hash"]
        records.append(record)
    return records


def default_run_dir() -> Path:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return ROOT / "runs" / timestamp


def run(args: argparse.Namespace) -> Path:
    run_dir = args.run_dir or default_run_dir()
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite run directory: {run_dir}")
    run_dir.mkdir(parents=True)

    reduction = build_reduction(args.input)
    input_relative = repository_relative(args.input)
    solver_relative = repository_relative(Path(__file__))
    command = (
        f".venv/bin/python {solver_relative} --input {input_relative} "
        f"--seconds {args.seconds} --seed {args.seed}"
    )
    config = {
        "schema": 1,
        "method": "fixed-core-unbounded-height-boundary-table-csp",
        "input": input_relative,
        "path_encoding": "repository-relative",
        "input_sha256": sha256_file(args.input),
        "seconds": args.seconds,
        "workers": 1,
        "seed": args.seed,
        "ortools_version": ortools.__version__,
        "python": sys.version,
        "verifier_sha256": reduction.inputs["problem"]["verifier_sha256"],
        "reproduction_command": command,
    }
    write_json(run_dir / "config.json", config)
    atomic_write(run_dir / "model.pb", reduction.model_bytes)
    result = solve_reduction(reduction, args.seconds, args.seed)
    events = event_records(config, result)
    atomic_write(
        run_dir / "events.jsonl",
        b"".join(canonical_bytes(event) + b"\n" for event in events),
    )

    checkpoint = {
        "schema": 1,
        "complete": result["status"] in {"INFEASIBLE", "OPTIMAL", "FEASIBLE"},
        "status": result["status"],
        "model_sha256": reduction.facts["model_sha256"],
        "last_event_hash": events[-1]["hash"],
    }
    write_json(run_dir / "checkpoint.json", checkpoint)
    summary = {
        "schema": 1,
        "outcome": "bounded_no_go" if result["infeasible"] else "relaxation_not_closed",
        "candidate_written": False,
        "arena_actions": 0,
        "external_mutations": 0,
        "claim": (
            "No 360-point integer set whose residue support modulo 8011 is the "
            "attributed 90-residue leader core can cover every difference through "
            "49110; arbitrary unbounded per-residue height supports are included."
            if result["infeasible"]
            else "No no-go claim: the necessary relaxation was not proved infeasible."
        ),
        "facts": reduction.facts,
        "solver": result,
        "limitations": [
            "different residue cores",
            "residues outside the fixed 90-column core",
            "cardinalities other than 360",
            "moduli other than 8011",
            "global optimality",
        ],
    }
    write_json(run_dir / "summary.json", summary)
    hashed_files = ["checkpoint.json", "config.json", "events.jsonl", "model.pb", "summary.json"]
    manifest = {
        "schema": 1,
        "files": {name: sha256_file(run_dir / name) for name in hashed_files},
    }
    write_json(run_dir / "manifest.json", manifest)
    return run_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--seed", type=int, default=20260815)
    return parser.parse_args()


if __name__ == "__main__":
    output = run(parse_args())
    print(output)
