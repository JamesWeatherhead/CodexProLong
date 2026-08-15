#!/usr/bin/env python3
"""Exact support-clause closure for q=143 base cells and label releases.

For a label triple (i,j,k), choose one label as the supported label.  For each
assignment to the other two labels, one clause requires the supported label to
choose a point whose exact integer determinant is at least 747.  Exactly-one
constraints make these support clauses logically equivalent to all forbidden
tuple clauses, while being dramatically smaller.

All scenario domains are included before support clauses are generated.
Scenario activation literals and triple guards are passed as assumptions, so
one incremental CaDiCaL session retains learned clauses across related cells.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pysat
from pysat.card import CardEnc, EncType
from pysat.solvers import Solver

import q143_cegis as common


ROOT = Path(__file__).resolve().parent


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
    atomic_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(),
    )


def append_event(path: Path, **event: object) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def unique_domain(parts: Iterable[np.ndarray]) -> np.ndarray:
    return np.asarray(
        sorted({tuple(map(int, point)) for part in parts for point in part}),
        dtype=np.int64,
    )


def allowed_indices(domain: np.ndarray, allowed: np.ndarray) -> set[int]:
    allowed_points = {tuple(map(int, point)) for point in allowed}
    return {
        index
        for index, point in enumerate(domain)
        if tuple(map(int, point)) in allowed_points
    }


def domains_sha256(domains: list[np.ndarray]) -> str:
    encoded = json.dumps(
        [domain.tolist() for domain in domains],
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return common.sha256(encoded)


def allowed_indices_sha256(allowed_by_label: list[set[int]]) -> str:
    encoded = json.dumps(
        [sorted(indices) for indices in allowed_by_label],
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return common.sha256(encoded)


class SupportFormula:
    def __init__(
        self,
        domains: list[np.ndarray],
        scenarios: list[dict[str, Any]],
        threshold: int,
    ) -> None:
        self.domains = domains
        self.scenarios = scenarios
        self.threshold = threshold
        self.offsets: list[int] = []
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

        self.scenario_variables: dict[str, int] = {}
        for scenario in scenarios:
            self.top_variable += 1
            self.scenario_variables[scenario["key"]] = self.top_variable
        self._build_scenario_eligibility()

        self.triple_guards: dict[tuple[int, int, int], int] = {}
        for triple in itertools.combinations(range(common.COUNT), 3):
            self.top_variable += 1
            self.triple_guards[triple] = self.top_variable
        self._build_support_groups()

    def close(self) -> None:
        self.solver.delete()

    def variable(self, label: int, index: int) -> int:
        return self.offsets[label] + index

    def add_clause(self, clause: list[int], section: str) -> None:
        self.solver.add_clause(clause)
        self.clause_count += 1
        self.literal_count += len(clause)
        self.clause_hash.update(common.clause_bytes(clause))
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
        for first_label, second_label in itertools.combinations(range(common.COUNT), 2):
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

    def _build_scenario_eligibility(self) -> None:
        for scenario in self.scenarios:
            activation = self.scenario_variables[scenario["key"]]
            allowed_by_label = scenario["allowed_indices"]
            for label, domain in enumerate(self.domains):
                allowed = allowed_by_label[label]
                for index in range(len(domain)):
                    if index not in allowed:
                        self.add_clause(
                            [-activation, -self.variable(label, index)],
                            "scenario_eligibility",
                        )

    def orientation_cost(
        self, triple: tuple[int, int, int], support_label: int
    ) -> tuple[int, int, int]:
        pair = [label for label in triple if label != support_label]
        first_label, second_label = pair
        support_domain = self.domains[support_label]
        literal_cost = 0
        row_count = 0
        for first in self.domains[first_label]:
            for second in self.domains[second_label]:
                valid = common.determinant_batch(first, second, support_domain) >= self.threshold
                valid_count = int(np.count_nonzero(valid))
                if valid_count == len(support_domain):
                    continue
                row_count += 1
                literal_cost += 3 + valid_count
        return literal_cost, row_count, support_label

    def _emit_orientation(
        self, triple: tuple[int, int, int], support_label: int
    ) -> tuple[int, int]:
        pair = [label for label in triple if label != support_label]
        first_label, second_label = pair
        support_domain = self.domains[support_label]
        guard = self.triple_guards[triple]
        before_clauses = self.clause_count
        before_literals = self.literal_count
        for first_index, first in enumerate(self.domains[first_label]):
            for second_index, second in enumerate(self.domains[second_label]):
                valid = np.flatnonzero(
                    common.determinant_batch(first, second, support_domain)
                    >= self.threshold
                )
                if len(valid) == len(support_domain):
                    continue
                clause = [
                    -guard,
                    -self.variable(first_label, first_index),
                    -self.variable(second_label, second_index),
                ]
                clause.extend(
                    self.variable(support_label, int(index)) for index in valid
                )
                self.add_clause(clause, "support")
        return self.clause_count - before_clauses, self.literal_count - before_literals

    def _build_support_groups(self) -> None:
        for triple in itertools.combinations(range(common.COUNT), 3):
            costs = [self.orientation_cost(triple, label) for label in triple]
            literal_cost, predicted_rows, support_label = min(costs)
            rows, literals = self._emit_orientation(triple, support_label)
            if (rows, literals) != (predicted_rows, literal_cost):
                raise RuntimeError("support cost/emission mismatch")
            self.orientation_records.append(
                {
                    "triple": triple,
                    "support_label": support_label,
                    "row_count": rows,
                    "literal_count": literals,
                    "alternative_costs": [
                        {
                            "support_label": label,
                            "literal_count": cost,
                            "row_count": count,
                        }
                        for cost, count, label in sorted(costs)
                    ],
                }
            )

    def assumptions(self, scenario_key: str) -> list[int]:
        assumptions = [
            variable if key == scenario_key else -variable
            for key, variable in self.scenario_variables.items()
        ]
        assumptions.extend(self.triple_guards.values())
        return assumptions

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
            matches = [
                index
                for index in range(len(domain))
                if self.variable(label, index) in positive
            ]
            if len(matches) != 1:
                raise RuntimeError(f"label {label}: expected one choice, got {matches}")
            selected.append(domain[matches[0]])
        return np.asarray(selected, dtype=np.int64)

    def solve_scenario(
        self,
        scenario: dict[str, Any],
        *,
        seconds: float,
        conflict_budget: int,
        conflict_chunk: int,
    ) -> tuple[dict[str, Any], np.ndarray | None]:
        self.set_center_phases(np.asarray(scenario["center"], dtype=np.int64))
        assumptions = self.assumptions(scenario["key"])
        started = time.perf_counter()
        stats_start = self.solver.accum_stats()
        slices = 0
        result = None
        while time.perf_counter() - started < seconds:
            stats_now = self.solver.accum_stats()
            used = int(stats_now.get("conflicts", 0)) - int(
                stats_start.get("conflicts", 0)
            )
            if used >= conflict_budget:
                break
            self.solver.conf_budget(max(1, min(conflict_chunk, conflict_budget - used)))
            result = self.solver.solve_limited(assumptions=assumptions)
            slices += 1
            if result is not None:
                break
        elapsed = time.perf_counter() - started
        stats_end = self.solver.accum_stats()
        conflict_delta = int(stats_end.get("conflicts", 0)) - int(
            stats_start.get("conflicts", 0)
        )
        grid = None
        core_triples: list[tuple[int, int, int]] = []
        if result is True:
            status = "satisfiable_exact_support_formula"
            grid = self.decode(self.solver.get_model())
        elif result is False:
            status = "unsatisfiable"
            core = set(self.solver.get_core() or assumptions)
            core_triples = sorted(
                triple
                for triple, guard in self.triple_guards.items()
                if guard in core
            )
        else:
            status = "timeout"
        return (
            {
                "key": scenario["key"],
                "representative_public_id": scenario["representative"],
                "released_labels": scenario["released_labels"],
                "domain_sizes": [len(indices) for indices in scenario["allowed_indices"]],
                "allowed_indices_sha256": allowed_indices_sha256(
                    scenario["allowed_indices"]
                ),
                "status": status,
                "elapsed_seconds": elapsed,
                "solve_slices": slices,
                "conflict_delta": conflict_delta,
                "solver_statistics_cumulative": stats_end,
                "assumption_count": len(assumptions),
                "assumptions_sha256": common.sha256(common.clause_bytes(assumptions)),
                "unsat_core_triples": core_triples,
                "unsat_core_triple_count": len(core_triples),
            },
            grid,
        )

    def receipt(self) -> dict[str, Any]:
        return {
            "union_domain_sizes": [len(domain) for domain in self.domains],
            "domain_coordinates_sha256": domains_sha256(self.domains),
            "decision_variable_count": self.decision_variable_count,
            "total_variable_count": self.top_variable,
            "scenario_variable_count": len(self.scenario_variables),
            "triple_guard_count": len(self.triple_guards),
            "clause_count": self.clause_count,
            "literal_count": self.literal_count,
            "clause_sha256": self.clause_hash.hexdigest(),
            "section_counts": self.section_counts,
            "nontrivial_triple_count": sum(
                record["row_count"] > 0 for record in self.orientation_records
            ),
            "orientation_records": self.orientation_records,
        }


def base_union_model(
    representatives: tuple[int, ...],
    prior: dict[int, dict[str, Any]],
    seeds: dict[int, dict[str, Any]],
    adaptive: Any,
) -> tuple[list[np.ndarray], list[dict[str, Any]]]:
    per_scenario_domains: dict[int, list[np.ndarray]] = {}
    for representative in representatives:
        center = np.asarray(seeds[representative]["center"], dtype=np.int64)
        radii = tuple(map(int, prior[representative]["radii"]))
        per_scenario_domains[representative] = [
            adaptive.hex_window(center[label], radii[label])
            for label in range(common.COUNT)
        ]
    domains = [
        unique_domain(per_scenario_domains[rep][label] for rep in representatives)
        for label in range(common.COUNT)
    ]
    scenarios = []
    for representative in representatives:
        allowed = [
            allowed_indices(domains[label], per_scenario_domains[representative][label])
            for label in range(common.COUNT)
        ]
        scenarios.append(
            {
                "key": f"base:{representative}",
                "representative": representative,
                "released_labels": [],
                "center": seeds[representative]["center"],
                "allowed_indices": allowed,
            }
        )
    return domains, scenarios


def release_model(
    representative: int,
    prior: dict[int, dict[str, Any]],
    seed: dict[str, Any],
    adaptive: Any,
    lattice: Any,
    release_radius: int,
    release_label_count: int,
) -> tuple[list[np.ndarray], list[dict[str, Any]], list[int]]:
    center = np.asarray(seed["center"], dtype=np.int64)
    base_radii = tuple(map(int, prior[representative]["radii"]))
    ranked = common.variable_pressure(center, base_radii, lattice)
    release_labels = ranked[:release_label_count]
    if any(release_radius < base_radii[label] for label in release_labels):
        raise ValueError(
            "release radius must contain every selected label's base window"
        )
    domains = [
        adaptive.hex_window(
            center[label],
            release_radius if label in release_labels else base_radii[label],
        )
        for label in range(common.COUNT)
    ]
    release_sets: list[tuple[int, ...]] = [()]
    release_sets.extend((label,) for label in release_labels)
    release_sets.extend(itertools.combinations(release_labels, 2))
    scenarios = []
    for released in release_sets:
        radii = list(base_radii)
        for label in released:
            radii[label] = release_radius
        active = [
            adaptive.hex_window(center[label], radii[label])
            for label in range(common.COUNT)
        ]
        allowed = [
            allowed_indices(domains[label], active[label])
            for label in range(common.COUNT)
        ]
        suffix = "base" if not released else "release-" + "-".join(map(str, released))
        scenarios.append(
            {
                "key": f"{representative}:{suffix}",
                "representative": representative,
                "released_labels": list(released),
                "center": seed["center"],
                "allowed_indices": allowed,
            }
        )
    return domains, scenarios, release_labels


def verify_grid(
    grid: np.ndarray,
    lattice: Any,
    threshold: int,
    target: float,
    run_dir: Path,
    key: str,
) -> dict[str, Any]:
    minimum, mathematical_score = lattice.exact_grid_score(
        grid, np.arange(common.COUNT), common.DENOMINATOR
    )
    payload_record = lattice.selected_payload(
        grid, np.arange(common.COUNT), common.DENOMINATOR
    )
    payload = {"points": payload_record["points"]}
    verifier_score = common.frozen_verifier_score(payload)
    safe_key = key.replace(":", "-")
    payload_path = run_dir / f"candidate-{safe_key}.json"
    atomic_json(payload_path, payload)
    result = {
        "scenario": key,
        "barycentric_integer_points": grid.tolist(),
        "minimum_numerator": minimum,
        "threshold_numerator": threshold,
        "mathematical_score": mathematical_score,
        "frozen_verifier_score": verifier_score,
        "target_strictly_above": target,
        "gate_clearing": bool(minimum >= threshold and verifier_score > target),
        "payload": payload_path.name,
        "payload_sha256": common.sha256(payload_path.read_bytes()),
    }
    if minimum < threshold:
        raise RuntimeError("support formula produced a determinant-invalid model")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--stamp")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--representatives", type=common.parse_ints, default=common.OPEN_REPRESENTATIVES)
    parser.add_argument("--skip-base-union", action="store_true")
    parser.add_argument("--skip-releases", action="store_true")
    parser.add_argument("--release-radius", type=int, default=8)
    parser.add_argument("--release-label-count", type=int, default=4)
    parser.add_argument("--scenario-seconds", type=float, default=60.0)
    parser.add_argument("--scenario-conflicts", type=int, default=1_000_000)
    parser.add_argument("--conflict-chunk", type=int, default=10_000)
    args = parser.parse_args()

    for path, expected, label in (
        (common.ADAPTIVE_SOURCE, common.ADAPTIVE_SHA256, "adaptive source"),
        (common.LATTICE_SOURCE, common.LATTICE_SHA256, "lattice source"),
        (common.PRIOR_SUMMARY, common.PRIOR_SUMMARY_SHA256, "prior summary"),
        (common.SNAPSHOT, common.SNAPSHOT_SHA256, "snapshot"),
        (common.VERIFIER, common.VERIFIER_SHA256, "verifier"),
    ):
        common.require_hash(path, expected, label)
    sys.path.insert(0, str(common.BNB))
    adaptive = common.load_module(common.ADAPTIVE_SOURCE, "support_adaptive_q143")
    lattice = common.load_module(common.LATTICE_SOURCE, "support_lattice_q143")
    snapshot, live_score, target, verifier_hash = lattice.load_snapshot(common.SNAPSHOT)
    if verifier_hash != common.VERIFIER_SHA256:
        raise RuntimeError("verifier mismatch")
    threshold = lattice.threshold_numerator(target, common.DENOMINATOR)
    if threshold != 747:
        raise RuntimeError(f"unexpected threshold {threshold}")
    prior = common.prior_open_records()
    seeds = {
        int(seed["representative_id"]): seed
        for seed in adaptive.distinct_public_seeds(snapshot)
    }
    representatives = tuple(args.representatives)
    if not representatives or len(representatives) != len(set(representatives)):
        raise ValueError("representatives must be a nonempty unique list")
    missing = sorted(set(representatives) - set(seeds))
    if missing:
        raise ValueError(f"unknown representative IDs: {missing}")
    if not args.skip_releases and not 1 <= args.release_label_count <= common.COUNT:
        raise ValueError("release-label-count must be between 1 and 11")
    if args.release_radius < 0:
        raise ValueError("release-radius must be nonnegative")

    run_configuration = {
        "representatives": list(representatives),
        "skip_base_union": args.skip_base_union,
        "skip_releases": args.skip_releases,
        "release_radius": args.release_radius,
        "release_label_count": args.release_label_count,
        "threshold_numerator": threshold,
        "support_closure_sha256": common.sha256(Path(__file__).read_bytes()),
        "q143_cegis_sha256": common.sha256(Path(common.__file__).read_bytes()),
        "input_hashes": {
            "adaptive": common.ADAPTIVE_SHA256,
            "lattice": common.LATTICE_SHA256,
            "prior_summary": common.PRIOR_SUMMARY_SHA256,
            "snapshot": common.SNAPSHOT_SHA256,
            "verifier": common.VERIFIER_SHA256,
        },
    }

    if args.resume:
        run_dir = args.resume.resolve()
        checkpoint = json.loads((run_dir / "checkpoint.json").read_text())
        if checkpoint.get("schema") != 2:
            raise RuntimeError("resume requires a schema-2 checkpoint")
        if checkpoint.get("run_configuration") != run_configuration:
            raise RuntimeError("resume configuration or source hash mismatch")
        models_receipt: list[dict[str, Any]] = checkpoint["models"]
        records: list[dict[str, Any]] = checkpoint["records"]
        candidates: list[dict[str, Any]] = checkpoint["candidates"]
        complete = {
            record["key"]
            for record in records
            if record["status"] in {"unsatisfiable", "satisfiable_exact_support_formula"}
        }
    else:
        stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_dir = (args.run_root / stamp).resolve()
        run_dir.mkdir(parents=True, exist_ok=False)
        models_receipt = []
        records = []
        candidates = []
        complete: set[str] = set()
    events = run_dir / "events.jsonl"

    def checkpoint() -> None:
        atomic_json(
            run_dir / "checkpoint.json",
            {
                "schema": 2,
                "run_configuration": run_configuration,
                "snapshot_sha256": common.SNAPSHOT_SHA256,
                "verifier_sha256": common.VERIFIER_SHA256,
                "prior_summary_sha256": common.PRIOR_SUMMARY_SHA256,
                "models": models_receipt,
                "records": records,
                "candidates": candidates,
            },
        )

    if not events.exists():
        append_event(
            events,
            event="start",
            generated_at=datetime.now(UTC).isoformat(),
            representatives=representatives,
            threshold_numerator=threshold,
            target_strictly_above=target,
            paperclip_sources=common.PAPERCLIP_SOURCES,
        )

    gate_clearer = any(bool(candidate.get("gate_clearing")) for candidate in candidates)

    def model_projection(receipt: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in receipt.items()
            if key not in {"build_seconds", "orientation_records"}
        }

    def run_formula(model_name: str, domains: list[np.ndarray], scenarios: list[dict[str, Any]], extra: dict[str, Any]) -> None:
        nonlocal gate_clearer
        build_started = time.perf_counter()
        formula = SupportFormula(domains, scenarios, threshold)
        build_seconds = time.perf_counter() - build_started
        receipt = {"model": model_name, "build_seconds": build_seconds, **formula.receipt(), **extra}
        previous = [model for model in models_receipt if model["model"] == model_name]
        if previous:
            if len(previous) != 1 or model_projection(previous[0]) != model_projection(
                receipt
            ):
                formula.close()
                raise RuntimeError(f"resume formula mismatch for {model_name}")
            append_event(events, event="model_rebuilt_for_resume", **receipt)
        else:
            models_receipt.append(receipt)
            append_event(events, event="model_built", **receipt)
        checkpoint()
        try:
            for scenario in scenarios:
                if scenario["key"] in complete:
                    continue
                # A resume retries an unresolved slice from a fresh solver.
                # Replace, rather than duplicate, its previous timeout record.
                records[:] = [
                    record
                    for record in records
                    if record["key"] != scenario["key"]
                ]
                record, grid = formula.solve_scenario(
                    scenario,
                    seconds=args.scenario_seconds,
                    conflict_budget=args.scenario_conflicts,
                    conflict_chunk=args.conflict_chunk,
                )
                record["model"] = model_name
                if grid is not None:
                    candidate = verify_grid(grid, lattice, threshold, target, run_dir, scenario["key"])
                    record["candidate"] = candidate
                    candidates.append(candidate)
                    gate_clearer = gate_clearer or bool(candidate["gate_clearing"])
                records.append(record)
                if record["status"] in {"unsatisfiable", "satisfiable_exact_support_formula"}:
                    complete.add(record["key"])
                append_event(events, event="scenario_complete", **record)
                checkpoint()
                print(json.dumps(record, sort_keys=True), flush=True)
                if gate_clearer:
                    break
        finally:
            formula.close()

    if not args.skip_base_union and not gate_clearer:
        domains, scenarios = base_union_model(representatives, prior, seeds, adaptive)
        run_formula("four-cell-base-union", domains, scenarios, {})

    if not args.skip_releases and not gate_clearer:
        for representative in representatives:
            domains, scenarios, release_labels = release_model(
                representative,
                prior,
                seeds[representative],
                adaptive,
                lattice,
                args.release_radius,
                args.release_label_count,
            )
            run_formula(
                f"release-{representative}",
                domains,
                scenarios,
                {
                    "representative_public_id": representative,
                    "release_radius": args.release_radius,
                    "ranked_release_labels": release_labels,
                },
            )
            if gate_clearer:
                break

    checkpoint()
    summary = {
        "schema": 2,
        "run_configuration": run_configuration,
        "mode": "exact support-clause incremental CDCL closure",
        "network_used": False,
        "external_writes": [],
        "snapshot_sha256": common.SNAPSHOT_SHA256,
        "verifier_sha256": common.VERIFIER_SHA256,
        "prior_summary_sha256": common.PRIOR_SUMMARY_SHA256,
        "live_score": live_score,
        "target_strictly_above": target,
        "denominator": common.DENOMINATOR,
        "threshold_numerator": threshold,
        "minimum_grid_score": threshold / (common.DENOMINATOR**2),
        "grid_gate_margin": threshold / (common.DENOMINATOR**2) - target,
        "representatives": representatives,
        "models": models_receipt,
        "records": records,
        "status_counts": {
            status: sum(record["status"] == status for record in records)
            for status in sorted({record["status"] for record in records})
        },
        "candidates": candidates,
        "gate_clearing": gate_clearer,
        "paperclip_sources": common.PAPERCLIP_SOURCES,
        "solver": "CaDiCaL 1.5.3",
        "dependencies": {"python_sat": pysat.__version__, "numpy": np.__version__},
        "events": str(events),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, event="complete", summary=summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if gate_clearer else 2


if __name__ == "__main__":
    raise SystemExit(main())
