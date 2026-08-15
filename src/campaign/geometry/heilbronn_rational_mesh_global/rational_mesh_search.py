#!/usr/bin/env python3
"""Exact support-clause searches on selected q=144..220 rational meshes.

The campaign has two non-overlapping families:

* radius-2 windows around every D3-distinct public rounding at the four most
  favorable exact denominators;
* topology-changing q=156 neighborhoods: forced boundary births from the
  high-scoring three-boundary basin, forced one/two boundary deaths from the
  six-boundary leader, and disconnected cross-basin domain unions.

Every determinant is integer exact.  A case is either closed by an exact
per-triple domain upper bound, solved by an exact support-clause SAT formula,
or explicitly reported as conflict/time capped.  A SAT model is independently
checked against the frozen verifier before it is called gate-clearing.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import os
import tempfile
import time
from datetime import UTC, datetime
from decimal import Decimal, ROUND_CEILING, getcontext
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pysat
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver
from scipy.optimize import linear_sum_assignment


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
SNAPSHOT = (
    REPOSITORY
    / "campaign/geometry/snapshots/heilbronn-triangles_20260814T231406Z.json"
)
VERIFIER = (
    REPOSITORY
    / "campaign/state/problems/heilbronn-triangles/"
    "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d.py"
)
SCREEN = ROOT / "denominator_screen.json"
SNAPSHOT_SHA256 = "e6332c0715a82c9e62d9029385a7db1cab46549bf482ff65dca30e9ee5468d90"
VERIFIER_SHA256 = "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d"
SCREEN_SHA256 = "5d24c5e559e50374b27ae22383fd8c9dbf0ffca14bb4f0342285320375d4d066"
TARGET_TEXT = "0.036529890880030155"
COUNT = 11
TOPOLOGY_Q = 156

PAPERCLIP_SOURCES = [
    {
        "claim": (
            "A unit-triangle optimum with n>=5 can be represented with at least "
            "four boundary points and one edge carrying two, unless all vertices "
            "are occupied; affine S3 symmetry strengthens the mixed-integer model."
        ),
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2607.15021#L1",
    },
    {
        "claim": (
            "Recursive branch-and-bound on increasingly fine grids and adaptive "
            "discretization are established exact-computation strategies."
        ),
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L18-L22",
    },
    {
        "claim": (
            "Binary discretization makes bilinear terms more tractable through "
            "exact binary-continuous linearization and small residual ranges."
        ),
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L63-L79",
    },
    {
        "claim": (
            "Boundary-structure symmetry breaking plus numerical-to-symbolic "
            "refinement recovers exact best-known configurations on small instances."
        ),
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2603.11107#L1",
    },
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def atomic_json(path: Path, value: object) -> None:
    encoded = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_event(path: Path, event: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def clause_bytes(clause: Iterable[int]) -> bytes:
    return (" ".join(map(str, clause)) + " 0\n").encode()


def parse_ints(text: str) -> tuple[int, ...]:
    return tuple(int(value) for value in text.split(",") if value.strip())


def cartesian_to_barycentric(points: list[list[float]]) -> np.ndarray:
    cartesian = np.asarray(points, dtype=np.float64)
    third = 2.0 * cartesian[:, 1] / math.sqrt(3.0)
    second = cartesian[:, 0] - 0.5 * third
    first = 1.0 - second - third
    barycentric = np.column_stack((first, second, third))
    barycentric[np.abs(barycentric) < 1e-12] = 0.0
    if barycentric.shape != (COUNT, 3) or np.any(barycentric < -1e-9):
        raise ValueError("public seed is outside the equilateral triangle")
    return np.maximum(barycentric, 0.0)


def nearest_grid(barycentric: np.ndarray, denominator: int) -> np.ndarray:
    rows = []
    for row in barycentric:
        scaled = row * denominator
        base = np.floor(scaled + 1e-12).astype(np.int64)
        needed = denominator - int(base.sum())
        if not 0 <= needed <= 2:
            raise RuntimeError("invalid largest-remainder state")
        order = np.argsort(-(scaled - base), kind="stable")
        base[order[:needed]] += 1
        if np.any(base < 0) or int(base.sum()) != denominator:
            raise RuntimeError("invalid rounded point")
        rows.append(base)
    return np.asarray(rows, dtype=np.int64)


def topology_preserving_grid(
    barycentric: np.ndarray, denominator: int, zero_tolerance: float = 1e-10
) -> np.ndarray:
    """Round while preserving each source coordinate's zero/nonzero status.

    Public numerical constructions contain meaningful positive coordinates far
    below one mesh unit.  Ordinary largest-remainder rounding collapses those
    topologies.  There are only three barycentric coordinates, so enumerate the
    constrained integer simplex row exactly and minimize squared rounding error
    with a deterministic lexicographic tie break.
    """

    rows = []
    for row in barycentric:
        scaled = np.asarray(row, dtype=np.float64) * denominator
        zero = np.asarray(row, dtype=np.float64) <= zero_tolerance
        best: tuple[float, tuple[int, int, int]] | None = None
        for first in range(denominator + 1):
            for second in range(denominator - first + 1):
                point = (first, second, denominator - first - second)
                if any((value == 0) != bool(zero[index]) for index, value in enumerate(point)):
                    continue
                error = sum((point[index] - float(scaled[index])) ** 2 for index in range(3))
                candidate = (error, point)
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            raise RuntimeError("no topology-preserving rational rounding exists")
        rows.append(best[1])
    return np.asarray(rows, dtype=np.int64)


def canonical_key(grid: np.ndarray) -> tuple[tuple[int, int, int], ...]:
    return min(
        tuple(sorted(tuple(map(int, row)) for row in grid[:, permutation]))
        for permutation in itertools.permutations(range(3))
    )


def hex_window(center: np.ndarray, radius: int) -> np.ndarray:
    points = set()
    for first in range(-radius, radius + 1):
        for second in range(-radius, radius + 1):
            third = -first - second
            if max(abs(first), abs(second), abs(third)) > radius:
                continue
            point = center + np.asarray((first, second, third), dtype=np.int64)
            if np.all(point >= 0):
                points.add(tuple(map(int, point)))
    return np.asarray(sorted(points), dtype=np.int64)


def determinant_batch(
    first: np.ndarray, second: np.ndarray, third: np.ndarray
) -> np.ndarray:
    delta_second = np.asarray(second, dtype=np.int64)[..., 1:] - np.asarray(
        first, dtype=np.int64
    )[..., 1:]
    delta_third = np.asarray(third, dtype=np.int64)[..., 1:] - np.asarray(
        first, dtype=np.int64
    )[..., 1:]
    return np.abs(
        delta_second[..., 0] * delta_third[..., 1]
        - delta_second[..., 1] * delta_third[..., 0]
    )


def exact_grid_score(grid: np.ndarray) -> int:
    return min(
        int(determinant_batch(grid[first], grid[second], grid[third]))
        for first, second, third in itertools.combinations(range(COUNT), 3)
    )


def threshold_numerator(denominator: int) -> int:
    getcontext().prec = 80
    return int(
        (Decimal(TARGET_TEXT) * Decimal(denominator * denominator)).to_integral_value(
            rounding=ROUND_CEILING
        )
    )


def domains_hash(domains: list[np.ndarray]) -> str:
    return sha256_bytes(
        json.dumps(
            [domain.tolist() for domain in domains],
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    )


def boundary_counts(grid: np.ndarray) -> list[int]:
    return [int(np.count_nonzero(grid[:, side] == 0)) for side in range(3)]


def apply_forcing(
    domain: np.ndarray, constraints: tuple[tuple[int, str], ...]
) -> np.ndarray:
    mask = np.ones(len(domain), dtype=bool)
    for coordinate, relation in constraints:
        if relation == "zero":
            mask &= domain[:, coordinate] == 0
        elif relation == "positive":
            mask &= domain[:, coordinate] > 0
        else:
            raise ValueError(f"unknown forcing relation {relation}")
    filtered = domain[mask]
    if len(filtered) == 0:
        raise RuntimeError(f"forcing emptied a domain: {constraints}")
    return filtered


def local_domains(
    center: np.ndarray,
    radius: int,
    forcing: dict[int, tuple[tuple[int, str], ...]] | None = None,
) -> list[np.ndarray]:
    forcing = forcing or {}
    return [
        apply_forcing(hex_window(center[label], radius), forcing.get(label, ()))
        for label in range(COUNT)
    ]


def topology_forcing(center: np.ndarray) -> dict[int, tuple[tuple[int, str], ...]]:
    """Force the exact boundary-incidence topology of an integer center."""

    return {
        label: tuple(
            (coordinate, "zero" if center[label, coordinate] == 0 else "positive")
            for coordinate in range(3)
        )
        for label in range(COUNT)
    }


def distinct_public_centers(
    snapshot: dict[str, Any], denominator: int
) -> list[dict[str, Any]]:
    by_key: dict[tuple[tuple[int, int, int], ...], dict[str, Any]] = {}
    for solution in snapshot["solutions"]:
        center = nearest_grid(
            cartesian_to_barycentric(solution["data"]["points"]), denominator
        )
        key = canonical_key(center)
        if key not in by_key:
            by_key[key] = {
                "representative_id": int(solution["id"]),
                "public_ids": [],
                "public_score": float(solution["score"]),
                "center": center,
                "boundary_counts": boundary_counts(center),
            }
        by_key[key]["public_ids"].append(int(solution["id"]))
    return sorted(
        by_key.values(),
        key=lambda item: (-item["public_score"], item["representative_id"]),
    )


def solution_center(
    snapshot: dict[str, Any], public_id: int, denominator: int
) -> np.ndarray:
    matches = [solution for solution in snapshot["solutions"] if int(solution["id"]) == public_id]
    if len(matches) != 1:
        raise RuntimeError(f"expected unique public ID {public_id}")
    return nearest_grid(
        cartesian_to_barycentric(matches[0]["data"]["points"]), denominator
    )


def solution_center_preserving_topology(
    snapshot: dict[str, Any], public_id: int, denominator: int
) -> np.ndarray:
    matches = [solution for solution in snapshot["solutions"] if int(solution["id"]) == public_id]
    if len(matches) != 1:
        raise RuntimeError(f"expected unique public ID {public_id}")
    return topology_preserving_grid(
        cartesian_to_barycentric(matches[0]["data"]["points"]), denominator
    )


def project_to_side(
    center: np.ndarray, label: int, side: int, mode: str
) -> np.ndarray:
    projected = center.copy()
    amount = int(projected[label, side])
    projected[label, side] = 0
    others = [coordinate for coordinate in range(3) if coordinate != side]
    if mode == "first":
        projected[label, others[0]] += amount
    elif mode == "second":
        projected[label, others[1]] += amount
    elif mode == "proportional":
        total = int(center[label, others].sum())
        first_add = int(round(amount * int(center[label, others[0]]) / total))
        projected[label, others[0]] += first_add
        projected[label, others[1]] += amount - first_add
    else:
        raise ValueError(mode)
    return projected


def boundary_birth_cases(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    denominator = TOPOLOGY_Q
    source_id = 1015
    original = solution_center_preserving_topology(snapshot, source_id, denominator)
    if boundary_counts(original) != [1, 1, 1]:
        raise RuntimeError("three-boundary source topology drift")
    candidates: list[dict[str, Any]] = []
    nearest_by_side: dict[int, list[int]] = {}
    for side in range(3):
        labels = [label for label in range(COUNT) if original[label, side] > 0]
        nearest_by_side[side] = sorted(labels, key=lambda label: (original[label, side], label))
        label = nearest_by_side[side][0]
        for mode in ("proportional", "first", "second"):
            center = project_to_side(original, label, side, mode)
            forcing = topology_forcing(center)
            candidates.append(
                {
                    "key": f"q156-birth-side{side}-label{label}-{mode}",
                    "family": "forced_boundary_birth",
                    "denominator": denominator,
                    "center": center,
                    "domains": local_domains(center, 2, forcing),
                    "metadata": {
                        "source_public_id": source_id,
                        "born": [[label, side]],
                        "redistribution": mode,
                        "center_boundary_counts": boundary_counts(center),
                    },
                }
            )
    for first_side, second_side in itertools.combinations(range(3), 2):
        pair = min(
            (
                (first_label, second_label)
                for first_label in nearest_by_side[first_side][:3]
                for second_label in nearest_by_side[second_side][:3]
                if first_label != second_label
            ),
            key=lambda labels: (
                int(original[labels[0], first_side])
                + int(original[labels[1], second_side]),
                labels,
            ),
        )
        center = project_to_side(original, pair[0], first_side, "proportional")
        center = project_to_side(center, pair[1], second_side, "proportional")
        forcing = topology_forcing(center)
        candidates.append(
            {
                "key": f"q156-double-birth-sides{first_side}{second_side}-labels{pair[0]}-{pair[1]}",
                "family": "forced_double_boundary_birth",
                "denominator": denominator,
                "center": center,
                "domains": local_domains(center, 2, forcing),
                "metadata": {
                    "source_public_id": source_id,
                    "born": [[pair[0], first_side], [pair[1], second_side]],
                    "redistribution": "proportional",
                    "center_boundary_counts": boundary_counts(center),
                },
            }
        )
    return candidates


def move_inward(center: np.ndarray, label: int, side: int, step: int) -> np.ndarray:
    moved = center.copy()
    if moved[label, side] != 0:
        raise ValueError("inward move requires a boundary point")
    donors = [coordinate for coordinate in range(3) if coordinate != side]
    donor = max(donors, key=lambda coordinate: (moved[label, coordinate], -coordinate))
    if moved[label, donor] < step:
        raise RuntimeError("insufficient barycentric mass for inward move")
    moved[label, side] += step
    moved[label, donor] -= step
    return moved


def boundary_death_cases(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    denominator = TOPOLOGY_Q
    source_id = 630
    original = solution_center(snapshot, source_id, denominator)
    boundary = [
        (label, int(np.flatnonzero(original[label] == 0)[0]))
        for label in range(COUNT)
        if np.count_nonzero(original[label] == 0) == 1
    ]
    if len(boundary) != 6:
        raise RuntimeError("leader no longer has six simple boundary points")
    cases = []
    release_sets = [(item,) for item in boundary]
    release_sets.extend(itertools.combinations(boundary, 2))
    for released in release_sets:
        center = original.copy()
        released_labels = {label for label, _ in released}
        for label, side in boundary:
            if label in released_labels:
                center = move_inward(center, label, side, 3)
        forcing = topology_forcing(center)
        suffix = "-".join(f"{label}s{side}" for label, side in released)
        cases.append(
            {
                "key": f"q156-boundary-death-{suffix}",
                "family": (
                    "forced_single_boundary_death"
                    if len(released) == 1
                    else "forced_double_boundary_death"
                ),
                "denominator": denominator,
                "center": center,
                "domains": local_domains(center, 2, forcing),
                "metadata": {
                    "source_public_id": source_id,
                    "deaths": [list(item) for item in released],
                    "surviving_boundary_points_forced": True,
                    "center_boundary_counts": boundary_counts(center),
                },
            }
        )
    return cases


def align_secondary(primary: np.ndarray, secondary: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
    best = None
    for permutation in itertools.permutations(range(3)):
        transformed = secondary[:, permutation]
        costs = np.max(np.abs(primary[:, None, :] - transformed[None, :, :]), axis=2)
        rows, columns = linear_sum_assignment(costs)
        ordered = np.empty_like(primary)
        ordered[rows] = transformed[columns]
        score = (int(costs[rows, columns].sum()), int(costs[rows, columns].max()), permutation)
        if best is None or score < best[0]:
            best = (score, ordered, columns.tolist())
    assert best is not None
    return best[1], {
        "matching_l1_inf_sum": best[0][0],
        "matching_inf_max": best[0][1],
        "coordinate_permutation": list(best[0][2]),
        "secondary_assignment": best[2],
    }


def union_domain(parts: Iterable[np.ndarray]) -> np.ndarray:
    return np.asarray(
        sorted({tuple(map(int, point)) for part in parts for point in part}),
        dtype=np.int64,
    )


def crossover_cases(
    snapshot: dict[str, Any], denominators: tuple[int, ...]
) -> list[dict[str, Any]]:
    pairs = ((630, 1015), (630, 1006), (630, 649), (1015, 1006))
    cases = []
    for denominator in (value for value in (156, 174) if value in denominators):
        for first_id, second_id in pairs:
            first = solution_center_preserving_topology(snapshot, first_id, denominator)
            second = solution_center_preserving_topology(snapshot, second_id, denominator)
            aligned, alignment = align_secondary(first, second)
            domains = [
                union_domain((hex_window(first[label], 1), hex_window(aligned[label], 1)))
                for label in range(COUNT)
            ]
            cases.append(
                {
                    "key": f"q{denominator}-crossover-{first_id}-{second_id}",
                    "family": "cross_basin_disconnected_union",
                    "denominator": denominator,
                    "center": first,
                    "domains": domains,
                    "metadata": {
                        "source_public_ids": [first_id, second_id],
                        "radius_per_component": 1,
                        "first_boundary_counts": boundary_counts(first),
                        "second_boundary_counts": boundary_counts(aligned),
                        **alignment,
                    },
                }
            )
    return cases


def all_cases(
    snapshot: dict[str, Any], denominators: tuple[int, ...], phases: set[str]
) -> list[dict[str, Any]]:
    cases = []
    if "public" in phases:
        for denominator in denominators:
            for seed in distinct_public_centers(snapshot, denominator):
                center = seed["center"]
                cases.append(
                    {
                        "key": f"q{denominator}-public-{seed['representative_id']}-r2",
                        "family": "public_basin_radius2",
                        "denominator": denominator,
                        "center": center,
                        "domains": local_domains(center, 2),
                        "metadata": {
                            key: value
                            for key, value in seed.items()
                            if key != "center"
                        },
                    }
                )
    if "topology" in phases:
        if TOPOLOGY_Q not in denominators:
            raise ValueError("topology phase requires q=156")
        cases.extend(boundary_birth_cases(snapshot))
        cases.extend(boundary_death_cases(snapshot))
        cases.extend(crossover_cases(snapshot, denominators))
    keys = [case["key"] for case in cases]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate case key")
    return cases


def triple_upper_bound(
    first_domain: np.ndarray, second_domain: np.ndarray, third_domain: np.ndarray
) -> int:
    maximum = 0
    for first in first_domain:
        for second in second_domain:
            maximum = max(
                maximum,
                int(np.max(determinant_batch(first, second, third_domain))),
            )
    return maximum


def impossible_triples(domains: list[np.ndarray], threshold: int) -> list[dict[str, Any]]:
    impossible = []
    for triple in itertools.combinations(range(COUNT), 3):
        maximum = triple_upper_bound(*(domains[label] for label in triple))
        if maximum < threshold:
            impossible.append({"triple": list(triple), "maximum_numerator": maximum})
    return impossible


class SupportFormula:
    def __init__(self, domains: list[np.ndarray], threshold: int) -> None:
        self.domains = domains
        self.threshold = threshold
        self.offsets = []
        next_variable = 1
        for domain in domains:
            self.offsets.append(next_variable)
            next_variable += len(domain)
        self.decision_variable_count = next_variable - 1
        self.top_variable = self.decision_variable_count
        self.solver = Solver(name="cadical153")
        self.clause_count = 0
        self.literal_count = 0
        self.clause_hash = hashlib.sha256()
        self.section_counts: dict[str, dict[str, int]] = {}
        self.orientation_records: list[dict[str, Any]] = []
        self._build_exactly_one()
        self._build_collisions()
        self._build_support()

    def close(self) -> None:
        self.solver.delete()

    def variable(self, label: int, index: int) -> int:
        return self.offsets[label] + index

    def add_clause(self, clause: list[int], section: str) -> None:
        self.solver.add_clause(clause)
        self.clause_count += 1
        self.literal_count += len(clause)
        self.clause_hash.update(clause_bytes(clause))
        counts = self.section_counts.setdefault(section, {"clauses": 0, "literals": 0})
        counts["clauses"] += 1
        counts["literals"] += len(clause)

    def _build_exactly_one(self) -> None:
        for label, domain in enumerate(self.domains):
            variables = [self.variable(label, index) for index in range(len(domain))]
            encoding = CardEnc.equals(
                lits=variables,
                bound=1,
                top_id=self.top_variable,
                encoding=EncType.seqcounter,
            )
            self.top_variable = max(self.top_variable, encoding.nv)
            for clause in encoding.clauses:
                self.add_clause(clause, "exactly_one")

    def _build_collisions(self) -> None:
        for first_label, second_label in itertools.combinations(range(COUNT), 2):
            lookup = {
                tuple(map(int, point)): index
                for index, point in enumerate(self.domains[second_label])
            }
            for first_index, point in enumerate(self.domains[first_label]):
                second_index = lookup.get(tuple(map(int, point)))
                if second_index is not None:
                    self.add_clause(
                        [
                            -self.variable(first_label, first_index),
                            -self.variable(second_label, second_index),
                        ],
                        "collisions",
                    )

    def orientation_cost(
        self, triple: tuple[int, int, int], support_label: int
    ) -> tuple[int, int, int]:
        first_label, second_label = [label for label in triple if label != support_label]
        support_domain = self.domains[support_label]
        literals = 0
        rows = 0
        for first in self.domains[first_label]:
            for second in self.domains[second_label]:
                count = int(
                    np.count_nonzero(
                        determinant_batch(first, second, support_domain) >= self.threshold
                    )
                )
                if count == len(support_domain):
                    continue
                rows += 1
                literals += 2 + count
        return literals, rows, support_label

    def emit_orientation(
        self, triple: tuple[int, int, int], support_label: int
    ) -> tuple[int, int]:
        first_label, second_label = [label for label in triple if label != support_label]
        support_domain = self.domains[support_label]
        before_clauses = self.clause_count
        before_literals = self.literal_count
        for first_index, first in enumerate(self.domains[first_label]):
            for second_index, second in enumerate(self.domains[second_label]):
                valid = np.flatnonzero(
                    determinant_batch(first, second, support_domain) >= self.threshold
                )
                if len(valid) == len(support_domain):
                    continue
                clause = [
                    -self.variable(first_label, first_index),
                    -self.variable(second_label, second_index),
                ]
                clause.extend(
                    self.variable(support_label, int(index)) for index in valid
                )
                self.add_clause(clause, "support")
        return self.clause_count - before_clauses, self.literal_count - before_literals

    def _build_support(self) -> None:
        for triple in itertools.combinations(range(COUNT), 3):
            alternatives = [self.orientation_cost(triple, label) for label in triple]
            expected_literals, expected_rows, support_label = min(alternatives)
            rows, literals = self.emit_orientation(triple, support_label)
            if (rows, literals) != (expected_rows, expected_literals):
                raise RuntimeError("support cost/emission mismatch")
            self.orientation_records.append(
                {
                    "triple": list(triple),
                    "support_label": support_label,
                    "row_count": rows,
                    "literal_count": literals,
                }
            )

    def set_center_phases(self, center: np.ndarray) -> None:
        phases = []
        for label, domain in enumerate(self.domains):
            index = int(np.argmin(np.max(np.abs(domain - center[label]), axis=1)))
            phases.append(self.variable(label, index))
        self.solver.set_phases(phases)

    def decode(self, model: list[int]) -> np.ndarray:
        positive = {literal for literal in model if literal > 0}
        selected = []
        for label, domain in enumerate(self.domains):
            indices = [
                index
                for index in range(len(domain))
                if self.variable(label, index) in positive
            ]
            if len(indices) != 1:
                raise RuntimeError(f"label {label}: expected one value, got {indices}")
            selected.append(domain[indices[0]])
        return np.asarray(selected, dtype=np.int64)

    def solve(
        self, center: np.ndarray, seconds: float, conflicts: int, chunk: int
    ) -> tuple[dict[str, Any], np.ndarray | None]:
        self.set_center_phases(center)
        started = time.perf_counter()
        statistics_start = self.solver.accum_stats()
        result = None
        slices = 0
        while time.perf_counter() - started < seconds:
            statistics = self.solver.accum_stats()
            used = int(statistics.get("conflicts", 0)) - int(
                statistics_start.get("conflicts", 0)
            )
            if used >= conflicts:
                break
            self.solver.conf_budget(max(1, min(chunk, conflicts - used)))
            result = self.solver.solve_limited()
            slices += 1
            if result is not None:
                break
        elapsed = time.perf_counter() - started
        statistics_end = self.solver.accum_stats()
        conflict_delta = int(statistics_end.get("conflicts", 0)) - int(
            statistics_start.get("conflicts", 0)
        )
        if result is True:
            status = "satisfiable"
            grid = self.decode(self.solver.get_model())
        elif result is False:
            status = "unsatisfiable"
            grid = None
        else:
            status = "timeout"
            grid = None
        return (
            {
                "status": status,
                "elapsed_seconds": elapsed,
                "solve_slices": slices,
                "conflict_delta": conflict_delta,
                "solver_statistics": statistics_end,
            },
            grid,
        )

    def receipt(self) -> dict[str, Any]:
        return {
            "domain_sizes": [len(domain) for domain in self.domains],
            "domain_coordinates_sha256": domains_hash(self.domains),
            "decision_variable_count": self.decision_variable_count,
            "total_variable_count": self.top_variable,
            "clause_count": self.clause_count,
            "literal_count": self.literal_count,
            "clause_sha256": self.clause_hash.hexdigest(),
            "section_counts": self.section_counts,
            "nontrivial_triple_count": sum(
                record["row_count"] > 0 for record in self.orientation_records
            ),
        }


def load_verifier() -> Any:
    if sha256(VERIFIER) != VERIFIER_SHA256:
        raise RuntimeError("frozen verifier hash drift")
    spec = importlib.util.spec_from_file_location("rational_mesh_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_grid(
    grid: np.ndarray,
    denominator: int,
    threshold: int,
    verifier: Any,
    run_dir: Path,
    key: str,
) -> dict[str, Any]:
    minimum = exact_grid_score(grid)
    barycentric = grid.astype(np.float64) / denominator
    points = np.column_stack(
        (
            barycentric[:, 1] + 0.5 * barycentric[:, 2],
            (np.sqrt(3.0) / 2.0) * barycentric[:, 2],
        )
    )
    payload = {"points": points.tolist()}
    verifier_score = float(verifier.evaluate(payload))
    path = run_dir / f"candidate-{key}.json"
    atomic_json(path, payload)
    target = float(TARGET_TEXT)
    record = {
        "barycentric_integer_points": grid.tolist(),
        "denominator": denominator,
        "minimum_numerator": minimum,
        "threshold_numerator": threshold,
        "exact_grid_score": minimum / (denominator * denominator),
        "frozen_verifier_score": verifier_score,
        "target_strictly_above": target,
        "payload": path.name,
        "payload_sha256": sha256(path),
        "gate_clearing": bool(minimum >= threshold and verifier_score > target),
    }
    if minimum < threshold:
        raise RuntimeError("support formula returned a determinant-invalid model")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--denominators", type=parse_ints, default=parse_ints("156,152,174,210"))
    parser.add_argument("--phases", default="public,topology")
    parser.add_argument("--case-prefix")
    parser.add_argument("--case-limit", type=int)
    parser.add_argument("--scenario-seconds", type=float, default=60.0)
    parser.add_argument("--scenario-conflicts", type=int, default=500_000)
    parser.add_argument("--conflict-chunk", type=int, default=10_000)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--stamp")
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    phases = {phase.strip() for phase in args.phases.split(",") if phase.strip()}
    if not phases or not phases <= {"public", "topology"}:
        raise ValueError("phases must be public and/or topology")
    if len(args.denominators) != len(set(args.denominators)):
        raise ValueError("denominators must be unique")
    if any(not 144 <= denominator <= 220 for denominator in args.denominators):
        raise ValueError("denominators must lie in q=144..220")
    for path, expected, label in (
        (SNAPSHOT, SNAPSHOT_SHA256, "snapshot"),
        (VERIFIER, VERIFIER_SHA256, "verifier"),
        (SCREEN, SCREEN_SHA256, "denominator screen"),
    ):
        if sha256(path) != expected:
            raise RuntimeError(f"{label} hash drift")
    snapshot = json.loads(SNAPSHOT.read_text())
    screen = json.loads(SCREEN.read_text())
    if tuple(screen["selected_denominators"]) != (156, 152, 174, 210):
        raise RuntimeError("selected denominator screen drift")
    verifier = load_verifier()
    cases = all_cases(snapshot, args.denominators, phases)
    if args.case_prefix:
        cases = [case for case in cases if case["key"].startswith(args.case_prefix)]
    if args.case_limit is not None:
        cases = cases[: args.case_limit]
    if not cases:
        raise ValueError("no cases selected")

    configuration = {
        "denominators": list(args.denominators),
        "phases": sorted(phases),
        "case_prefix": args.case_prefix,
        "case_limit": args.case_limit,
        "case_keys_sha256": sha256_bytes(
            json.dumps([case["key"] for case in cases], separators=(",", ":")).encode()
        ),
        "search_source_sha256": sha256(Path(__file__)),
        "snapshot_sha256": SNAPSHOT_SHA256,
        "verifier_sha256": VERIFIER_SHA256,
        "screen_sha256": SCREEN_SHA256,
    }
    if args.resume:
        run_dir = args.resume.resolve()
        checkpoint = json.loads((run_dir / "checkpoint.json").read_text())
        if checkpoint.get("schema") != 1 or checkpoint.get("configuration") != configuration:
            raise RuntimeError("resume configuration/source mismatch")
        records: list[dict[str, Any]] = checkpoint["records"]
        candidates: list[dict[str, Any]] = checkpoint["candidates"]
    else:
        stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = (args.run_root / stamp).resolve()
        run_dir.mkdir(parents=True, exist_ok=False)
        records = []
        candidates = []
    events = run_dir / "events.jsonl"

    def checkpoint() -> None:
        atomic_json(
            run_dir / "checkpoint.json",
            {
                "schema": 1,
                "configuration": configuration,
                "records": records,
                "candidates": candidates,
            },
        )

    if not events.exists():
        append_event(
            events,
            {
                "event": "start",
                "generated_at": datetime.now(UTC).isoformat(),
                "configuration": configuration,
                "paperclip_sources": PAPERCLIP_SOURCES,
            },
        )
    complete = {
        record["key"]
        for record in records
        if record["status"] in {"triple_upper_bound_unsatisfiable", "unsatisfiable", "satisfiable"}
    }
    gate_clearing = any(candidate["gate_clearing"] for candidate in candidates)
    for case in cases:
        if gate_clearing or case["key"] in complete:
            continue
        records[:] = [record for record in records if record["key"] != case["key"]]
        domains = case["domains"]
        denominator = int(case["denominator"])
        threshold = threshold_numerator(denominator)
        precheck_started = time.perf_counter()
        impossible = impossible_triples(domains, threshold)
        precheck_seconds = time.perf_counter() - precheck_started
        base = {
            "key": case["key"],
            "family": case["family"],
            "denominator": denominator,
            "threshold_numerator": threshold,
            "threshold_score": threshold / (denominator * denominator),
            "gate_margin": threshold / (denominator * denominator) - float(TARGET_TEXT),
            "center_boundary_counts": boundary_counts(case["center"]),
            "center_minimum_numerator": exact_grid_score(case["center"]),
            "domain_sizes": [len(domain) for domain in domains],
            "domain_coordinates_sha256": domains_hash(domains),
            "metadata": case["metadata"],
            "precheck_seconds": precheck_seconds,
            "impossible_triples": impossible,
        }
        if impossible:
            record = {
                **base,
                "status": "triple_upper_bound_unsatisfiable",
                "impossible_triple_count": len(impossible),
            }
            records.append(record)
            append_event(events, {"event": "case_complete", **record})
            checkpoint()
            print(json.dumps(record, sort_keys=True), flush=True)
            continue

        build_started = time.perf_counter()
        formula = SupportFormula(domains, threshold)
        build_seconds = time.perf_counter() - build_started
        try:
            solve_record, grid = formula.solve(
                case["center"],
                args.scenario_seconds,
                args.scenario_conflicts,
                args.conflict_chunk,
            )
            record = {
                **base,
                **formula.receipt(),
                "build_seconds": build_seconds,
                **solve_record,
            }
            if grid is not None:
                candidate = verify_grid(
                    grid, denominator, threshold, verifier, run_dir, case["key"]
                )
                record["candidate"] = candidate
                candidates.append({"key": case["key"], **candidate})
                gate_clearing = gate_clearing or candidate["gate_clearing"]
            records.append(record)
            append_event(events, {"event": "case_complete", **record})
            checkpoint()
            print(json.dumps(record, sort_keys=True), flush=True)
        finally:
            formula.close()

    checkpoint()
    summary = {
        "schema": 1,
        "mode": "exact rational-mesh support-clause search",
        "configuration": configuration,
        "network_used_by_search": False,
        "external_writes": [],
        "target_strictly_above": float(TARGET_TEXT),
        "case_count": len(cases),
        "records": records,
        "status_counts": {
            status: sum(record["status"] == status for record in records)
            for status in sorted({record["status"] for record in records})
        },
        "candidates": candidates,
        "gate_clearing": gate_clearing,
        "solver": "CaDiCaL 1.5.3",
        "dependencies": {
            "python_sat": pysat.__version__,
            "numpy": np.__version__,
        },
        "paperclip_sources": PAPERCLIP_SOURCES,
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, {"event": "complete", "summary": summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if gate_clearing else 2


if __name__ == "__main__":
    raise SystemExit(main())
