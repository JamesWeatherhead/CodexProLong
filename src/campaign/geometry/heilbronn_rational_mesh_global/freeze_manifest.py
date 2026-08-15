#!/usr/bin/env python3
"""Compile final raw search summaries into a compact deterministic manifest."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SEARCH = ROOT / "rational_mesh_search.py"
SEARCH_SHA256 = "67ac382fa33eafbfec8233f59b0269533e2cecafbcb8c05c754843024fc77271"
SUMMARIES = {
    "PUBLIC_V2": "237a4e4d83225678fc4cddfadd25e58a27eb17bd3d101b8962f315ec70d390ce",
    "TOPOLOGY_V2": "e9687326a5447a8e715a5ecb5538f93f0cedcbabaf2047661af9e74074c45523",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_search() -> Any:
    if sha256(SEARCH) != SEARCH_SHA256:
        raise RuntimeError("search source hash drift")
    spec = importlib.util.spec_from_file_location("rational_mesh_search_freeze", SEARCH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import rational-mesh search")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_search()
    records = []
    batches = []
    formula_keys = (
        "decision_variable_count",
        "total_variable_count",
        "clause_count",
        "literal_count",
        "clause_sha256",
        "section_counts",
        "nontrivial_triple_count",
    )
    for name, expected_hash in SUMMARIES.items():
        path = ROOT / "runs" / name / "summary.json"
        if sha256(path) != expected_hash:
            raise RuntimeError(f"{name}: summary hash drift")
        summary = json.loads(path.read_text())
        if summary["configuration"]["search_source_sha256"] != SEARCH_SHA256:
            raise RuntimeError(f"{name}: source pin drift")
        if summary["gate_clearing"] or summary["candidates"]:
            raise RuntimeError(f"{name}: unexpected candidate")
        keys = []
        for record in summary["records"]:
            projection = {
                "key": record["key"],
                "family": record["family"],
                "denominator": record["denominator"],
                "threshold_numerator": record["threshold_numerator"],
                "center_boundary_counts": record["center_boundary_counts"],
                "center_minimum_numerator": record["center_minimum_numerator"],
                "domain_sizes": record["domain_sizes"],
                "domain_coordinates_sha256": record["domain_coordinates_sha256"],
                "metadata": record["metadata"],
                "status": record["status"],
                "impossible_triples": record["impossible_triples"],
            }
            if record["status"] == "unsatisfiable":
                projection.update({key: record[key] for key in formula_keys})
            elif record["status"] != "triple_upper_bound_unsatisfiable":
                raise RuntimeError(f"{record['key']}: nonfinal status")
            records.append(projection)
            keys.append(record["key"])
        batches.append(
            {
                "name": name,
                "phases": summary["configuration"]["phases"],
                "summary_sha256": expected_hash,
                "case_keys": keys,
            }
        )
    manifest = {
        "schema": 1,
        "mode": "compact deterministic exact finite-domain manifest",
        "network_used": False,
        "external_writes": [],
        "search_source_sha256": SEARCH_SHA256,
        "screen_sha256": module.SCREEN_SHA256,
        "snapshot_sha256": module.SNAPSHOT_SHA256,
        "verifier_sha256": module.VERIFIER_SHA256,
        "target_strictly_above_decimal": module.TARGET_TEXT,
        "denominators": [156, 152, 174, 210],
        "batches": batches,
        "enumerated_case_count": len(records),
        "distinct_domain_count": len(
            {(record["denominator"], record["domain_coordinates_sha256"]) for record in records}
        ),
        "records": records,
        "claim_scope": (
            "Exact no-go only for the recorded finite labeled rational-mesh domains; "
            "not a global lattice or continuous impossibility proof."
        ),
    }
    module.atomic_json(ROOT / "case_manifest.json", manifest)
    print(json.dumps({"output": str(ROOT / "case_manifest.json"), "records": len(records)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
