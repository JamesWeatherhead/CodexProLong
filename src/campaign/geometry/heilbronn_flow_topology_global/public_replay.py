#!/usr/bin/env python3
"""Standard-library-only replay of the copied public receipt packet.

This intentionally does not import the solver, load campaign snapshots, open
the research corpus, read raw runs, or execute a verifier.  It authenticates
the manifest-approved bytes and checks the internally replayable receipt
claims while preserving the explicit boundary around private numerical work.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

if sys.version_info < (3, 11):
    raise RuntimeError("public_replay requires Python >= 3.11")


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "PUBLICATION_MANIFEST.json"
EXPORT = HERE / "PUBLICATION_EXPORT.json"
RECEIPT = HERE / "publication/receipt.json"
PUBLIC_LAYOUT = "src/campaign/geometry/heilbronn_flow_topology_global"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def contains_key(value: Any, forbidden: str) -> bool:
    if isinstance(value, dict):
        return forbidden in value or any(contains_key(item, forbidden) for item in value.values())
    if isinstance(value, list):
        return any(contains_key(item, forbidden) for item in value)
    return False


def verify_manifest(manifest: dict[str, Any]) -> int:
    assert manifest["schema_version"] == 2
    assert manifest["public_layout_root"] == PUBLIC_LAYOUT
    assert manifest["third_party_candidate_bytes_included"] is False
    assert manifest["copied_allowlist_audit"]["downloaded_or_local_verifier_executed"] is False
    included = {entry["path"]: entry for entry in manifest["include"]}
    assert "publication/receipt.json" in included
    assert "public_replay.py" in included
    assert "requirements.txt" in included
    assert not any(path.startswith("runs/") for path in included)
    for relative, entry in included.items():
        path = HERE / relative
        assert path.is_file(), relative
        assert path.stat().st_size == int(entry["bytes"]), relative
        assert sha256_file(path) == entry["sha256"], relative

    excluded_roots = {"runs", "__pycache__"}
    actual = {
        str(path.relative_to(HERE))
        for path in HERE.rglob("*")
        if path.is_file()
        and path.name not in {"PUBLICATION_MANIFEST.json", "PUBLICATION_EXPORT.json"}
        and not any(part in excluded_roots for part in path.relative_to(HERE).parts)
        and path.suffix != ".pyc"
    }
    assert actual == set(included), {"unlisted": sorted(actual - set(included)), "missing": sorted(set(included) - actual)}
    return len(included)


def verify_publication_export(manifest: dict[str, Any]) -> bool:
    """Validate optional metadata emitted by the public snapshot exporter."""

    if not EXPORT.is_file():
        return False
    exported = load_json(EXPORT)
    assert exported["schema_version"] == 1
    assert exported["canonical_manifest"].endswith(
        "geometry/heilbronn_flow_topology_global/PUBLICATION_MANIFEST.json"
    )
    records = {entry["path"]: entry for entry in exported["files"]}
    included = {entry["path"]: entry for entry in manifest["include"]}
    assert set(records) == set(included)
    for relative, entry in included.items():
        record = records[relative]
        assert record["canonical_sha256"] == entry["sha256"]
        assert record["canonical_bytes"] == entry["bytes"]
        assert record["public_sha256"] == sha256_file(HERE / relative)
        assert record["public_bytes"] == (HERE / relative).stat().st_size
        assert record["portable_path_rewrite"] is False
    return True


def verify_receipt(receipt: dict[str, Any]) -> None:
    assert receipt["schema_version"] == 2
    assert receipt["status"] == "frozen_bounded_frontier"
    assert receipt["verifier_sha256"] == "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d"
    assert receipt["snapshot_sha256"] == "e6332c0715a82c9e62d9029385a7db1cab46549bf482ff65dca30e9ee5468d90"
    assert receipt["public_solutions"] == 17
    assert receipt["d3_distinct_public_basins"] == 13
    assert receipt["strict_target"] == receipt["leader"] + receipt["min_improvement"]
    runs = receipt["runs"]
    assert len(runs) == 2
    assert sum(run["records"] for run in runs) == receipt["total_polished_records"] == 398
    assert sum(
        run["template_population_members"] + run["mutation_population_members"] for run in runs
    ) == receipt["total_annealed_population_members"] == 6624
    assert sum(run["gate_clearers"] for run in runs) == receipt["strict_gate_clearers"] == 0
    assert max(run["best_score"] for run in runs) == receipt["best_record"]["verifier_score"]
    assert math.isclose(
        receipt["strict_target"] - receipt["best_record"]["verifier_score"],
        0.002031877867569261,
        rel_tol=0.0,
        abs_tol=1e-18,
    )
    by_name = {run["run"]: run for run in runs}
    global_run = by_name["global-20260815T100000Z-v2"]
    continuation = by_name["continuation-20260815T103000Z-v2"]
    assert (
        global_run["mutation_parents_selected"],
        global_run["mutation_public_parents_selected"],
        global_run["mutation_template_parents_selected"],
    ) == (10, 8, 2)
    assert (
        continuation["mutation_parents_selected"],
        continuation["mutation_public_parents_selected"],
        continuation["mutation_template_parents_selected"],
    ) == (4, 4, 0)
    assert all(run["d3_distinct_public_basins"] == 13 for run in runs)
    assert all(run["all_payload_hashes_match"] for run in runs)
    assert all(run["all_fresh_verifier_replays_match"] for run in runs)
    assert all(run["all_independent_formula_replays_match"] for run in runs)
    assert receipt["all_candidate_payload_hashes_replayed"] is True
    assert receipt["all_candidate_scores_replayed_twice"] is True
    assert receipt["all_candidate_165_triangle_formula_replays_match"] is True
    assert receipt["minimum_true_d3_rms_over_retained_records"] > 1e-4
    assert receipt["minimum_true_d3_rms_over_retained_records"] == 0.04054608891852764
    assert receipt["nearest_public_metric"].startswith("minimum D3-invariant RMS")
    repairs = [run["rms_metadata_repair"] for run in runs]
    assert sum(repair["records_with_nearest_metadata_changed"] for repair in repairs) == 13
    assert all(repair["assignment_cost"] == "squared_euclidean" for repair in repairs)
    assert all(repair["candidate_coordinates_changed"] is False for repair in repairs)
    assert all(repair["payload_hashes_changed"] is False for repair in repairs)
    assert all(repair["verifier_scores_changed"] is False for repair in repairs)

    bug = receipt["boundary_mapping_regression"]
    assert bug["status"] == "private_nonreplayable_audit"
    assert bug["publicly_replayable"] is False
    assert "cannot recompute" in bug["evidence_scope"]
    assert bug["superseded_results_excluded_from_frontier"] is True
    assert all(
        len(entry["sha256"]) == 64 and all(character in "0123456789abcdef" for character in entry["sha256"])
        for entry in bug["private_artifact_hashes"]
    )

    public = receipt["public_receipt_replay"]
    assert public["path"] == f"{PUBLIC_LAYOUT}/public_replay.py"
    assert public["network_required"] is False
    assert public["raw_runs_required"] is False
    assert public["campaign_snapshot_required"] is False
    assert public["corpus_required"] is False
    assert public["numpy_scipy_torch_required"] is False
    assert public["downloaded_or_local_verifier_executed"] is False
    assert not contains_key(receipt, "points")


def scan_public_text(manifest: dict[str, Any]) -> None:
    forbidden = ("g" + "xl_", "bdb" + "7ada8-", "EXA_" + "API_KEY=", "Authorization:" + " Bearer")
    for entry in manifest["include"]:
        path = HERE / entry["path"]
        text = path.read_text(encoding="utf-8", errors="replace")
        assert not any(token in text for token in forbidden), path


def main() -> int:
    manifest = load_json(MANIFEST)
    receipt = load_json(RECEIPT)
    files = verify_manifest(manifest)
    export_verified = verify_publication_export(manifest)
    verify_receipt(receipt)
    scan_public_text(manifest)
    assert not ({"numpy", "scipy", "torch"} & set(sys.modules))
    print(
        json.dumps(
            {
                "status": "ok",
                "public_layout_root": PUBLIC_LAYOUT,
                "manifest_files_verified": files,
                "publication_export_verified": export_verified,
                "receipt_records": receipt["total_polished_records"],
                "network_used": False,
                "campaign_snapshot_opened": False,
                "raw_runs_opened": False,
                "corpus_opened": False,
                "downloaded_or_local_verifier_executed": False,
                "third_party_packages_imported": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
