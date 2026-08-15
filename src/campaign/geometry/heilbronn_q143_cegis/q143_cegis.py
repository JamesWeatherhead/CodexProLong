#!/usr/bin/env python3
"""Incremental lazy-CDCL/CEGIS for the four open q=143 Heilbronn cells.

The SAT instance contains only one-hot label domains and collision constraints
at first.  Every SAT model is separated with exact integer determinants.  A
violating labeled triple generates exact ternary no-goods, including safe
"star" generalizations that hold two selected points fixed and enumerate the
third point's complete superset domain.  Clauses are only added, so CaDiCaL
retains learned clauses.  Related base/single-release/pair-release scenarios
share one solver and use assumptions to restrict each label's active window.

No downloaded or frozen program is modified.  This file imports only the
hash-pinned local q=143 geometry helpers.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import itertools
import json
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

import numpy as np
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver


ROOT = Path(__file__).resolve().parent
GEOMETRY = ROOT.parent
BNB = GEOMETRY / "heilbronn_bnb"
ADAPTIVE_SOURCE = BNB / "adaptive_q143_sat.py"
LATTICE_SOURCE = BNB / "lattice_bnb.py"
PRIOR_SUMMARY = (
    BNB
    / "runs/20260815T031000Z/heilbronn-triangles/summary.json"
)
SNAPSHOT = GEOMETRY / "snapshots/heilbronn-triangles_20260814T231406Z.json"
VERIFIER = (
    GEOMETRY.parent
    / "state/problems/heilbronn-triangles/"
    "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d.py"
)

ADAPTIVE_SHA256 = "855e4c6775bf84515272edb5271642be2bfbcbe0a1a9bd718201ca683ba3383c"
LATTICE_SHA256 = "4aa1f1a2d6786d9c47dec8de2b3a0c889e34901ef39583e592b91aa181ab3477"
PRIOR_SUMMARY_SHA256 = "7cc482375bcd6f55401ef9b13372dafe6d64df1ced9c399f9451a7042d8f7655"
SNAPSHOT_SHA256 = "e6332c0715a82c9e62d9029385a7db1cab46549bf482ff65dca30e9ee5468d90"
VERIFIER_SHA256 = "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d"

DENOMINATOR = 143
COUNT = 11
OPEN_REPRESENTATIVES = (630, 1005, 1004, 649)

PAPERCLIP_SOURCES = [
    {
        "claim": (
            "Monotone clause addition lets incremental CDCL retain learned clauses; "
            "assumption/activation literals can enable or disable related formula parts."
        ),
        "url": "https://paperclip.gxl.ai/citations/papers/arx_1604.06204#L82-L88",
    },
    {
        "claim": (
            "Finite CEGIS alternates candidate generation and exact counterexample "
            "refinement; add-only constraints are well suited to incremental solving."
        ),
        "url": "https://paperclip.gxl.ai/citations/papers/arx_1604.06204#L165-L173",
    },
    {
        "claim": (
            "The Heilbronn objective is the absolute signed determinant, and symmetry "
            "breaking materially strengthens exact computational formulations."
        ),
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L8-L13,L18-L22,L93-L97",
    },
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_hash(path: Path, expected: str, label: str) -> None:
    actual = sha256(path.read_bytes())
    if actual != expected:
        raise RuntimeError(f"{label} hash drift: expected {expected}, got {actual}")


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, value: object) -> None:
    encoded = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    atomic_bytes(path, encoded)


def append_event(path: Path, **event: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def parse_ints(text: str) -> tuple[int, ...]:
    return tuple(int(value) for value in text.split(",") if value.strip())


def clause_bytes(clause: Iterable[int]) -> bytes:
    return (" ".join(map(str, clause)) + " 0\n").encode()


def hex_distance(first: np.ndarray, second: np.ndarray) -> int:
    return int(np.max(np.abs(first - second)))


def determinant_batch(
    first: np.ndarray, second: np.ndarray, third: np.ndarray
) -> np.ndarray:
    """Broadcastable exact absolute determinant on integer barycentric points."""
    first_array = np.asarray(first, dtype=np.int64)
    second_array = np.asarray(second, dtype=np.int64)
    third_array = np.asarray(third, dtype=np.int64)
    delta_second = second_array[..., 1:] - first_array[..., 1:]
    delta_third = third_array[..., 1:] - first_array[..., 1:]
    return np.abs(
        delta_second[..., 0] * delta_third[..., 1]
        - delta_second[..., 1] * delta_third[..., 0]
    )


def prior_open_records() -> dict[int, dict[str, Any]]:
    summary = json.loads(PRIOR_SUMMARY.read_text())
    records = {
        int(record["representative_public_id"]): record
        for record in summary["records"]
        if record["status"] == "unresolved_conflict_budget"
    }
    if tuple(records) != OPEN_REPRESENTATIVES:
        raise RuntimeError(f"unexpected prior open inventory: {tuple(records)}")
    return records


def variable_pressure(center: np.ndarray, base_radii: tuple[int, ...], lattice: ModuleType) -> list[int]:
    scored = []
    for label in range(COUNT):
        incident = []
        for triple in itertools.combinations(range(COUNT), 3):
            if label not in triple:
                continue
            numerator = int(
                lattice.determinant_numerator(
                    center[triple[0]], center[triple[1]], center[triple[2]]
                )
            )
            incident.append(numerator)
        incident.sort()
        # Small radii identify labels implicated by the prior exact UNSAT core.
        # The low-determinant sum ranks the remaining topology pressure.
        score = (
            0 if base_radii[label] < max(base_radii) else 1,
            sum(incident[:8]),
            incident[0],
            label,
        )
        scored.append((score, label))
    return [label for _, label in sorted(scored)]


class LazyModel:
    def __init__(
        self,
        center: np.ndarray,
        base_radii: tuple[int, ...],
        release_radius: int,
        adaptive: ModuleType,
        lattice: ModuleType,
        restored_nogoods: Iterable[tuple[int, int, int]] = (),
    ) -> None:
        self.center = np.asarray(center, dtype=np.int64)
        self.base_radii = base_radii
        self.release_radius = release_radius
        self.adaptive = adaptive
        self.lattice = lattice
        self.domains = [
            adaptive.hex_window(self.center[label], release_radius)
            for label in range(COUNT)
        ]
        self.offsets: list[int] = []
        next_variable = 1
        for domain in self.domains:
            self.offsets.append(next_variable)
            next_variable += len(domain)
        self.decision_variable_count = next_variable - 1
        self.top_variable = self.decision_variable_count
        self.solver = Solver(name="cadical153")
        self.base_clause_count = 0
        self.base_clause_hash = hashlib.sha256()
        self.nogoods: set[tuple[int, int, int]] = set()
        self.nogood_hash = hashlib.sha256()
        self._build_base()
        for nogood in sorted(restored_nogoods):
            self.add_nogood(nogood)

    def close(self) -> None:
        self.solver.delete()

    def variable(self, label: int, index: int) -> int:
        return self.offsets[label] + index

    def label_index(self, variable: int) -> tuple[int, int]:
        for label in range(COUNT):
            start = self.offsets[label]
            stop = start + len(self.domains[label])
            if start <= variable < stop:
                return label, variable - start
        raise ValueError(f"not a decision variable: {variable}")

    def _add_base_clause(self, clause: list[int]) -> None:
        self.solver.add_clause(clause)
        self.base_clause_count += 1
        self.base_clause_hash.update(clause_bytes(clause))

    def _build_base(self) -> None:
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
                self._add_base_clause(clause)

        # Coincident labeled points are not a valid 11-point configuration.
        for first_label, second_label in itertools.combinations(range(COUNT), 2):
            lookup = {
                tuple(point): index
                for index, point in enumerate(self.domains[second_label])
            }
            for first_index, point in enumerate(self.domains[first_label]):
                second_index = lookup.get(tuple(point))
                if second_index is not None:
                    self._add_base_clause(
                        [
                            -self.variable(first_label, first_index),
                            -self.variable(second_label, second_index),
                        ]
                    )

        # Prefer the published rounded center while leaving the full scenario free.
        phases = []
        for label, domain in enumerate(self.domains):
            index = int(np.argmin(np.max(np.abs(domain - self.center[label]), axis=1)))
            phases.append(self.variable(label, index))
        self.solver.set_phases(phases)

    def scenario_assumptions(self, radii: tuple[int, ...]) -> list[int]:
        assumptions = []
        for label, domain in enumerate(self.domains):
            for index, point in enumerate(domain):
                if hex_distance(point, self.center[label]) > radii[label]:
                    assumptions.append(-self.variable(label, index))
        return assumptions

    def decode(self, model: list[int]) -> tuple[np.ndarray, tuple[int, ...]]:
        positive = {literal for literal in model if literal > 0}
        indices = []
        for label, domain in enumerate(self.domains):
            selected = [
                index
                for index in range(len(domain))
                if self.variable(label, index) in positive
            ]
            if len(selected) != 1:
                raise RuntimeError(f"label {label} has {len(selected)} selected points")
            indices.append(selected[0])
        grid = np.asarray(
            [self.domains[label][indices[label]] for label in range(COUNT)],
            dtype=np.int64,
        )
        return grid, tuple(indices)

    def violations(self, grid: np.ndarray, threshold: int) -> list[tuple[int, int, int]]:
        bad = []
        for triple in itertools.combinations(range(COUNT), 3):
            value = int(
                self.lattice.determinant_numerator(
                    grid[triple[0]], grid[triple[1]], grid[triple[2]]
                )
            )
            if value < threshold:
                bad.append(triple)
        return bad

    def add_nogood(self, variables: Iterable[int]) -> bool:
        key = tuple(sorted(map(int, variables)))
        if len(key) != 3 or len(set(key)) != 3:
            raise ValueError(f"invalid ternary no-good: {key}")
        if key in self.nogoods:
            return False
        self.nogoods.add(key)
        clause = [-variable for variable in key]
        self.solver.add_clause(clause)
        self.nogood_hash.update(clause_bytes(clause))
        return True

    def add_star_cuts(
        self,
        indices: tuple[int, ...],
        violations: list[tuple[int, int, int]],
        threshold: int,
    ) -> int:
        before = len(self.nogoods)
        for first_label, second_label, third_label in violations:
            first_index = indices[first_label]
            second_index = indices[second_label]
            third_index = indices[third_label]
            first = self.domains[first_label][first_index]
            second = self.domains[second_label][second_index]
            third = self.domains[third_label][third_index]

            values = determinant_batch(first, second, self.domains[third_label])
            for candidate in np.flatnonzero(values < threshold):
                self.add_nogood(
                    (
                        self.variable(first_label, first_index),
                        self.variable(second_label, second_index),
                        self.variable(third_label, int(candidate)),
                    )
                )

            values = determinant_batch(first, self.domains[second_label], third)
            for candidate in np.flatnonzero(values < threshold):
                self.add_nogood(
                    (
                        self.variable(first_label, first_index),
                        self.variable(second_label, int(candidate)),
                        self.variable(third_label, third_index),
                    )
                )

            values = determinant_batch(self.domains[first_label], second, third)
            for candidate in np.flatnonzero(values < threshold):
                self.add_nogood(
                    (
                        self.variable(first_label, int(candidate)),
                        self.variable(second_label, second_index),
                        self.variable(third_label, third_index),
                    )
                )
        return len(self.nogoods) - before


def scenario_inventory(
    base_radii: tuple[int, ...],
    ranked_labels: list[int],
    release_radius: int,
    release_depth: int,
    release_label_count: int,
) -> list[dict[str, Any]]:
    labels = ranked_labels[:release_label_count]
    releases: list[tuple[int, ...]] = [()]
    if release_depth >= 1:
        releases.extend((label,) for label in labels)
    if release_depth >= 2:
        releases.extend(itertools.combinations(labels, 2))
    scenarios = []
    for released in releases:
        radii = list(base_radii)
        for label in released:
            radii[label] = release_radius
        name = "base" if not released else "release-" + "-".join(map(str, released))
        scenarios.append(
            {"name": name, "released_labels": list(released), "radii": radii}
        )
    return scenarios


def nogood_digest(nogoods: Iterable[tuple[int, int, int]]) -> str:
    digest = hashlib.sha256()
    for nogood in sorted(nogoods):
        digest.update(clause_bytes([-value for value in nogood]))
    return digest.hexdigest()


def save_nogoods(path: Path, nogoods: set[tuple[int, int, int]]) -> str:
    raw = json.dumps(sorted(nogoods), separators=(",", ":")).encode()
    encoded = gzip.compress(raw, compresslevel=9, mtime=0)
    atomic_bytes(path, encoded)
    return sha256(encoded)


def load_nogoods(path: Path) -> set[tuple[int, int, int]]:
    if not path.exists():
        return set()
    return {tuple(map(int, row)) for row in json.loads(gzip.decompress(path.read_bytes()))}


def frozen_verifier_score(payload: dict[str, Any]) -> float:
    require_hash(VERIFIER, VERIFIER_SHA256, "frozen verifier")
    verifier = load_module(VERIFIER, "frozen_heilbronn_verifier")
    return float(verifier.evaluate(payload))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--stamp")
    parser.add_argument("--resume", type=Path)
    parser.add_argument(
        "--representatives",
        type=parse_ints,
        default=OPEN_REPRESENTATIVES,
        help="comma-separated prior unresolved representative submission ids",
    )
    parser.add_argument("--release-radius", type=int, default=8)
    parser.add_argument("--release-depth", type=int, choices=(0, 1, 2), default=2)
    parser.add_argument("--release-label-count", type=int, default=4)
    parser.add_argument("--scenario-seconds", type=float, default=30.0)
    parser.add_argument("--scenario-conflicts", type=int, default=300_000)
    parser.add_argument("--conflict-chunk", type=int, default=50_000)
    parser.add_argument("--max-cegis-iterations", type=int, default=10_000)
    parser.add_argument("--checkpoint-iterations", type=int, default=25)
    args = parser.parse_args()

    for path, expected, label in (
        (ADAPTIVE_SOURCE, ADAPTIVE_SHA256, "adaptive q143 source"),
        (LATTICE_SOURCE, LATTICE_SHA256, "lattice source"),
        (PRIOR_SUMMARY, PRIOR_SUMMARY_SHA256, "prior q143 summary"),
        (SNAPSHOT, SNAPSHOT_SHA256, "frozen geometry snapshot"),
        (VERIFIER, VERIFIER_SHA256, "frozen verifier"),
    ):
        require_hash(path, expected, label)

    sys.path.insert(0, str(BNB))
    adaptive = load_module(ADAPTIVE_SOURCE, "frozen_adaptive_q143")
    lattice = load_module(LATTICE_SOURCE, "frozen_lattice_bnb")
    snapshot, live_score, target, snapshot_verifier_hash = lattice.load_snapshot(SNAPSHOT)
    if snapshot_verifier_hash != VERIFIER_SHA256:
        raise RuntimeError("snapshot and frozen verifier disagree")
    threshold = lattice.threshold_numerator(target, DENOMINATOR)
    if threshold != 747:
        raise RuntimeError(f"unexpected q143 threshold: {threshold}")

    prior = prior_open_records()
    public_seeds = {
        int(seed["representative_id"]): seed
        for seed in adaptive.distinct_public_seeds(snapshot)
    }
    representatives = tuple(args.representatives)
    if not representatives or any(rep not in prior for rep in representatives):
        raise ValueError("representatives must be drawn from the four prior open cells")

    if args.resume:
        run_dir = args.resume.resolve()
        checkpoint = json.loads((run_dir / "checkpoint.json").read_text())
        records: list[dict[str, Any]] = checkpoint["records"]
        # Timeout records are resumable attempts, not completed scenarios.
        completed = {
            f"{record['representative_public_id']}:{record['scenario']}"
            for record in records
            if record["status"] in {"unsatisfiable", "satisfiable_exact"}
        }
        candidate_record = checkpoint.get("candidate")
    else:
        stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = (args.run_root / stamp).resolve()
        run_dir.mkdir(parents=True, exist_ok=False)
        records = []
        completed: set[str] = set()
        candidate_record = None

    events = run_dir / "events.jsonl"
    if not events.exists():
        append_event(
            events,
            event="start",
            generated_at=datetime.now(UTC).isoformat(),
            representatives=representatives,
            snapshot_sha256=SNAPSHOT_SHA256,
            verifier_sha256=VERIFIER_SHA256,
            prior_summary_sha256=PRIOR_SUMMARY_SHA256,
            target_strictly_above=target,
            denominator=DENOMINATOR,
            threshold_numerator=threshold,
            minimum_grid_score=threshold / (DENOMINATOR * DENOMINATOR),
            paperclip_sources=PAPERCLIP_SOURCES,
        )
    else:
        append_event(events, event="resume", existing_records=len(records))

    def save_checkpoint(current_rep: int | None = None) -> None:
        atomic_json(
            run_dir / "checkpoint.json",
            {
                "schema": 1,
                "snapshot_sha256": SNAPSHOT_SHA256,
                "verifier_sha256": VERIFIER_SHA256,
                "prior_summary_sha256": PRIOR_SUMMARY_SHA256,
                "denominator": DENOMINATOR,
                "threshold_numerator": threshold,
                "representatives": representatives,
                "current_representative": current_rep,
                "completed_scenarios": sorted(completed),
                "records": records,
                "candidate": candidate_record,
            },
        )

    gate_clearer = False
    for representative in representatives:
        seed = public_seeds[representative]
        center = np.asarray(seed["center"], dtype=np.int64)
        base_radii = tuple(map(int, prior[representative]["radii"]))
        ranked = variable_pressure(center, base_radii, lattice)
        scenarios = scenario_inventory(
            base_radii,
            ranked,
            args.release_radius,
            args.release_depth,
            args.release_label_count,
        )
        nogood_path = run_dir / f"nogoods-{representative}.json.gz"
        restored = load_nogoods(nogood_path)
        model = LazyModel(
            center,
            base_radii,
            args.release_radius,
            adaptive,
            lattice,
            restored,
        )
        append_event(
            events,
            event="seed_start",
            representative=representative,
            base_radii=base_radii,
            ranked_release_labels=ranked,
            superset_domain_sizes=[len(domain) for domain in model.domains],
            restored_nogoods=len(restored),
        )
        try:
            # Seed the monotone database with exact star cuts around the public center.
            center_indices = tuple(
                int(np.argmin(np.max(np.abs(domain - center[label]), axis=1)))
                for label, domain in enumerate(model.domains)
            )
            center_violations = model.violations(center, threshold)
            model.add_star_cuts(center_indices, center_violations, threshold)

            for scenario in scenarios:
                key = f"{representative}:{scenario['name']}"
                if key in completed:
                    continue
                assumptions = model.scenario_assumptions(tuple(scenario["radii"]))
                assumptions_hash = sha256(clause_bytes(assumptions))
                started = time.perf_counter()
                stats_start = model.solver.accum_stats()
                iterations = 0
                sat_models = 0
                new_nogoods = 0
                status = "timeout"
                last_violation_count = None
                unsat_core_size = None
                grid_candidate = None

                while iterations < args.max_cegis_iterations:
                    elapsed = time.perf_counter() - started
                    stats_now = model.solver.accum_stats()
                    used_conflicts = int(stats_now.get("conflicts", 0)) - int(
                        stats_start.get("conflicts", 0)
                    )
                    if elapsed >= args.scenario_seconds:
                        status = "timeout_seconds"
                        break
                    if used_conflicts >= args.scenario_conflicts:
                        status = "timeout_conflicts"
                        break
                    budget = min(
                        args.conflict_chunk,
                        args.scenario_conflicts - used_conflicts,
                    )
                    model.solver.conf_budget(max(1, budget))
                    result = model.solver.solve_limited(assumptions=assumptions)
                    iterations += 1
                    if result is None:
                        continue
                    if result is False:
                        status = "unsatisfiable"
                        unsat_core_size = len(model.solver.get_core() or assumptions)
                        break

                    sat_models += 1
                    grid, indices = model.decode(model.solver.get_model())
                    violations = model.violations(grid, threshold)
                    last_violation_count = len(violations)
                    if not violations:
                        exact_numerator, exact_score = lattice.exact_grid_score(
                            grid, np.arange(COUNT), DENOMINATOR
                        )
                        if exact_numerator < threshold:
                            raise RuntimeError("separator accepted an invalid model")
                        grid_candidate = grid
                        status = "satisfiable_exact"
                        break
                    added = model.add_star_cuts(indices, violations, threshold)
                    if added <= 0:
                        raise RuntimeError("violating model added no new exact cut")
                    new_nogoods += added
                    if iterations % args.checkpoint_iterations == 0:
                        file_hash = save_nogoods(nogood_path, model.nogoods)
                        append_event(
                            events,
                            event="cegis_checkpoint",
                            representative=representative,
                            scenario=scenario["name"],
                            iterations=iterations,
                            sat_models=sat_models,
                            nogood_count=len(model.nogoods),
                            nogood_file_sha256=file_hash,
                            last_violation_count=last_violation_count,
                        )

                elapsed = time.perf_counter() - started
                stats_end = model.solver.accum_stats()
                conflict_delta = int(stats_end.get("conflicts", 0)) - int(
                    stats_start.get("conflicts", 0)
                )
                file_hash = save_nogoods(nogood_path, model.nogoods)
                record: dict[str, Any] = {
                    "representative_public_id": representative,
                    "equivalent_public_ids": prior[representative]["equivalent_public_ids"],
                    "scenario": scenario["name"],
                    "released_labels": scenario["released_labels"],
                    "radii": scenario["radii"],
                    "status": status,
                    "iterations": iterations,
                    "sat_models_separated": sat_models,
                    "new_nogoods": new_nogoods,
                    "total_nogoods": len(model.nogoods),
                    "nogood_semantic_sha256": nogood_digest(model.nogoods),
                    "nogood_file": str(nogood_path.relative_to(run_dir)),
                    "nogood_file_sha256": file_hash,
                    "base_clause_count": model.base_clause_count,
                    "base_clause_sha256": model.base_clause_hash.hexdigest(),
                    "decision_variable_count": model.decision_variable_count,
                    "total_variable_count": model.top_variable,
                    "assumption_count": len(assumptions),
                    "assumptions_sha256": assumptions_hash,
                    "elapsed_seconds": elapsed,
                    "conflict_delta": conflict_delta,
                    "solver_statistics_cumulative": stats_end,
                    "last_violation_count": last_violation_count,
                    "unsat_core_size": unsat_core_size,
                }

                if grid_candidate is not None:
                    integer_minimum, mathematical_score = lattice.exact_grid_score(
                        grid_candidate, np.arange(COUNT), DENOMINATOR
                    )
                    payload = lattice.selected_payload(
                        grid_candidate, np.arange(COUNT), DENOMINATOR
                    )
                    arena_payload = {"points": payload["points"]}
                    verifier_score = frozen_verifier_score(arena_payload)
                    payload_path = run_dir / "candidate.json"
                    atomic_json(payload_path, arena_payload)
                    payload_sha = sha256(payload_path.read_bytes())
                    candidate_record = {
                        "representative_public_id": representative,
                        "scenario": scenario["name"],
                        "released_labels": scenario["released_labels"],
                        "barycentric_integer_points": grid_candidate.tolist(),
                        "minimum_numerator": integer_minimum,
                        "mathematical_score": mathematical_score,
                        "frozen_verifier_score": verifier_score,
                        "target_strictly_above": target,
                        "gate_clearing": bool(verifier_score > target),
                        "payload": str(payload_path.relative_to(run_dir)),
                        "payload_sha256": payload_sha,
                    }
                    record["candidate"] = candidate_record
                    gate_clearer = bool(candidate_record["gate_clearing"])

                records.append(record)
                if status in {"unsatisfiable", "satisfiable_exact"}:
                    completed.add(key)
                save_checkpoint(representative)
                append_event(events, event="scenario_complete", **record)
                print(json.dumps(record, sort_keys=True), flush=True)
                if gate_clearer:
                    break
            if gate_clearer:
                break
        finally:
            model.close()

    save_checkpoint(None)
    status_counts = {
        status: sum(record["status"] == status for record in records)
        for status in sorted({record["status"] for record in records})
    }
    summary = {
        "schema": 1,
        "mode": "incremental lazy-CDCL exact q143 CEGIS",
        "network_used": False,
        "external_writes": [],
        "snapshot": str(SNAPSHOT.resolve()),
        "snapshot_sha256": SNAPSHOT_SHA256,
        "verifier": str(VERIFIER.resolve()),
        "verifier_sha256": VERIFIER_SHA256,
        "prior_summary": str(PRIOR_SUMMARY.resolve()),
        "prior_summary_sha256": PRIOR_SUMMARY_SHA256,
        "live_score": live_score,
        "target_strictly_above": target,
        "denominator": DENOMINATOR,
        "threshold_numerator": threshold,
        "minimum_grid_score": threshold / (DENOMINATOR * DENOMINATOR),
        "grid_gate_margin": threshold / (DENOMINATOR * DENOMINATOR) - target,
        "representatives": representatives,
        "status_counts": status_counts,
        "scenario_count": len(records),
        "records": records,
        "candidate": candidate_record,
        "gate_clearing": gate_clearer,
        "paperclip_sources": PAPERCLIP_SOURCES,
        "solver": "CaDiCaL 1.5.3 via python-sat 1.9.dev14",
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, event="complete", summary=summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if gate_clearer else 2


if __name__ == "__main__":
    raise SystemExit(main())
