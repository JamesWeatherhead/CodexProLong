#!/usr/bin/env python3
"""Fresh-process exact replay of the frozen rational-mesh no-go packet.

This script reconstructs every finite domain from the pinned public snapshot,
recomputes every integer upper-bound obstruction, rebuilds every support CNF,
checks its deterministic coordinate/clause hashes, and asks a fresh CaDiCaL
instance for an uncapped UNSAT result.  It does not access the network.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SEARCH = ROOT / "rational_mesh_search.py"
MANIFEST = ROOT / "case_manifest.json"
MANIFEST_SHA256 = "4aef22d0653edbb2833bdcc2cd6bf1a4ea070cef32ad0666f44aed53756203c9"
SEARCH_SHA256 = "67ac382fa33eafbfec8233f59b0269533e2cecafbcb8c05c754843024fc77271"
DENOMINATORS = (156, 152, 174, 210)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_search() -> Any:
    if file_sha256(SEARCH) != SEARCH_SHA256:
        raise RuntimeError("search source hash drift")
    spec = importlib.util.spec_from_file_location("rational_mesh_search_replay", SEARCH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import rational-mesh search")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def topology_assertions(case: dict[str, Any], module: Any) -> None:
    family = case["family"]
    total = sum(module.boundary_counts(case["center"]))
    expected = {
        "forced_boundary_birth": 4,
        "forced_double_boundary_birth": 5,
        "forced_single_boundary_death": 5,
        "forced_double_boundary_death": 4,
    }.get(family)
    if expected is not None and total != expected:
        raise RuntimeError(f"{case['key']}: expected {expected} boundary incidences, got {total}")
    if family == "cross_basin_disconnected_union":
        metadata = case["metadata"]
        if metadata["matching_inf_max"] <= 0:
            raise RuntimeError(f"{case['key']}: crossover components collapsed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    module = load_search()
    if file_sha256(MANIFEST) != MANIFEST_SHA256:
        raise RuntimeError("case manifest hash drift")
    manifest = json.loads(MANIFEST.read_text())
    if manifest["search_source_sha256"] != SEARCH_SHA256:
        raise RuntimeError("manifest source pin drift")
    if tuple(manifest["denominators"]) != DENOMINATORS:
        raise RuntimeError("manifest denominator drift")
    snapshot = json.loads(module.SNAPSHOT.read_text())
    projection_keys = (
        "domain_sizes",
        "domain_coordinates_sha256",
        "decision_variable_count",
        "total_variable_count",
        "clause_count",
        "literal_count",
        "clause_sha256",
        "section_counts",
        "nontrivial_triple_count",
    )
    replay_records = []
    all_domain_keys: set[tuple[int, str]] = set()
    total_conflicts = 0
    total_clauses = 0

    manifest_records = {record["key"]: record for record in manifest["records"]}
    if len(manifest_records) != manifest["enumerated_case_count"]:
        raise RuntimeError("manifest record-count or key uniqueness drift")
    for batch in manifest["batches"]:
        batch_name = batch["name"]
        cases = module.all_cases(snapshot, DENOMINATORS, set(batch["phases"]))
        records = {key: manifest_records[key] for key in batch["case_keys"]}
        if [case["key"] for case in cases] != batch["case_keys"]:
            raise RuntimeError(f"{batch_name}: case-set/order drift")

        statuses: dict[str, int] = {}
        for case in cases:
            topology_assertions(case, module)
            record = records[case["key"]]
            denominator = int(case["denominator"])
            threshold = module.threshold_numerator(denominator)
            domain_hash = module.domains_hash(case["domains"])
            all_domain_keys.add((denominator, domain_hash))
            if record["denominator"] != denominator:
                raise RuntimeError(f"{case['key']}: denominator drift")
            if record["threshold_numerator"] != threshold:
                raise RuntimeError(f"{case['key']}: threshold drift")
            if record["domain_coordinates_sha256"] != domain_hash:
                raise RuntimeError(f"{case['key']}: domain hash drift")
            if record["domain_sizes"] != [len(domain) for domain in case["domains"]]:
                raise RuntimeError(f"{case['key']}: domain size drift")
            if record["center_minimum_numerator"] != module.exact_grid_score(case["center"]):
                raise RuntimeError(f"{case['key']}: center score drift")
            if record["center_boundary_counts"] != module.boundary_counts(case["center"]):
                raise RuntimeError(f"{case['key']}: center topology drift")
            if record["metadata"] != case["metadata"]:
                raise RuntimeError(f"{case['key']}: metadata drift")

            impossible = module.impossible_triples(case["domains"], threshold)
            if impossible:
                if record["status"] != "triple_upper_bound_unsatisfiable":
                    raise RuntimeError(f"{case['key']}: obstruction status drift")
                if record["impossible_triples"] != impossible:
                    raise RuntimeError(f"{case['key']}: obstruction list drift")
                status = record["status"]
                conflicts = 0
                clauses = 0
            else:
                if record["status"] != "unsatisfiable":
                    raise RuntimeError(f"{case['key']}: expected recorded UNSAT")
                formula = module.SupportFormula(case["domains"], threshold)
                try:
                    fresh = formula.receipt()
                    for key in projection_keys:
                        if fresh[key] != record[key]:
                            raise RuntimeError(f"{case['key']}: {key} replay drift")
                    if formula.solver.solve() is not False:
                        raise RuntimeError(f"{case['key']}: fresh solver did not prove UNSAT")
                    statistics = formula.solver.accum_stats()
                    conflicts = int(statistics.get("conflicts", 0))
                    clauses = int(fresh["clause_count"])
                    total_conflicts += conflicts
                    total_clauses += clauses
                finally:
                    formula.close()
                status = "unsatisfiable"
            statuses[status] = statuses.get(status, 0) + 1
            replay_records.append(
                {
                    "key": case["key"],
                    "family": case["family"],
                    "denominator": denominator,
                    "domain_coordinates_sha256": domain_hash,
                    "status": status,
                    "fresh_conflicts": conflicts,
                    "clause_count": clauses,
                }
            )
        expected_statuses = {
            status: sum(record["status"] == status for record in records.values())
            for status in sorted({record["status"] for record in records.values()})
        }
        if statuses != expected_statuses:
            raise RuntimeError(f"{batch_name}: status-count drift")

    if len(replay_records) != manifest["enumerated_case_count"]:
        raise RuntimeError("replay case-count drift")
    if len(all_domain_keys) != manifest["distinct_domain_count"]:
        raise RuntimeError("replay distinct-domain-count drift")

    verifier = module.load_verifier()
    verifier_conversion_checks = []
    for denominator in DENOMINATORS:
        grid = module.solution_center(snapshot, 630, denominator)
        barycentric = grid.astype(module.np.float64) / denominator
        points = module.np.column_stack(
            (
                barycentric[:, 1] + 0.5 * barycentric[:, 2],
                (module.np.sqrt(3.0) / 2.0) * barycentric[:, 2],
            )
        )
        payload = {"points": points.tolist()}
        verifier_score = float(verifier.evaluate(payload))
        minimum_numerator = module.exact_grid_score(grid)
        exact_score = minimum_numerator / (denominator * denominator)
        if abs(verifier_score - exact_score) > 1e-14:
            raise RuntimeError(f"q={denominator}: verifier/grid normalization mismatch")
        verifier_conversion_checks.append(
            {
                "denominator": denominator,
                "minimum_numerator": minimum_numerator,
                "exact_grid_score": exact_score,
                "frozen_verifier_score": verifier_score,
                "absolute_difference": abs(verifier_score - exact_score),
                "gate_clearing": verifier_score > float(module.TARGET_TEXT),
            }
        )

    receipt = {
        "schema": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "fresh-process exact reconstruction and uncapped SAT replay",
        "network_used": False,
        "external_writes": [],
        "replay_source_sha256": file_sha256(Path(__file__)),
        "search_source_sha256": SEARCH_SHA256,
        "case_manifest_sha256": MANIFEST_SHA256,
        "screen_sha256": module.SCREEN_SHA256,
        "snapshot_sha256": module.SNAPSHOT_SHA256,
        "verifier_sha256": module.VERIFIER_SHA256,
        "summary_sha256": {
            batch["name"]: batch["summary_sha256"] for batch in manifest["batches"]
        },
        "enumerated_case_count": len(replay_records),
        "distinct_domain_count": len(all_domain_keys),
        "status_counts": {
            status: sum(record["status"] == status for record in replay_records)
            for status in sorted({record["status"] for record in replay_records})
        },
        "fresh_unsat_conflicts": total_conflicts,
        "fresh_formula_clauses": total_clauses,
        "verifier_conversion_checks": verifier_conversion_checks,
        "gate_clearing_candidate": None,
        "claim_scope": (
            "Exact no-go only for the 72 distinct finite labeled rational-mesh domains "
            "represented by 75 enumerated cases; not a global q=144..220 lattice or "
            "continuous Heilbronn impossibility proof."
        ),
        "records": replay_records,
    }
    if args.output:
        module.atomic_json(args.output.resolve(), receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
