#!/usr/bin/env python3
"""Validate primary/replay q=143 runs and write a compact durable receipt.

The bulky solver checkpoints stay under the ignored ``runs/`` tree.  This
script checks their scope, exact-formula fingerprints, scenario inventory, and
independent replay agreement before atomically replacing ``receipt.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
RECEIPT = ROOT / "receipt.json"

INPUTS = {
    "adaptive_q143_sat.py": (
        REPOSITORY / "campaign/geometry/heilbronn_bnb/adaptive_q143_sat.py",
        "855e4c6775bf84515272edb5271642be2bfbcbe0a1a9bd718201ca683ba3383c",
    ),
    "lattice_bnb.py": (
        REPOSITORY / "campaign/geometry/heilbronn_bnb/lattice_bnb.py",
        "4aa1f1a2d6786d9c47dec8de2b3a0c889e34901ef39583e592b91aa181ab3477",
    ),
    "prior_summary.json": (
        REPOSITORY
        / "campaign/geometry/heilbronn_bnb/runs/20260815T031000Z/"
        "heilbronn-triangles/summary.json",
        "7cc482375bcd6f55401ef9b13372dafe6d64df1ced9c399f9451a7042d8f7655",
    ),
    "public_snapshot.json": (
        REPOSITORY
        / "campaign/geometry/snapshots/heilbronn-triangles_20260814T231406Z.json",
        "e6332c0715a82c9e62d9029385a7db1cab46549bf482ff65dca30e9ee5468d90",
    ),
    "frozen_verifier.py": (
        REPOSITORY
        / "campaign/state/problems/heilbronn-triangles/"
        "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d.py",
        "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d",
    ),
}

RUNS = {
    "primary_base": ROOT / "runs/BASE_CLOSURE_V3",
    "primary_releases": ROOT / "runs/RELEASE_CLOSURE_V3",
    "replay_base": ROOT / "runs/REPLAY_BASE_V3",
    "replay_releases": ROOT / "runs/REPLAY_RELEASES_V3",
}

PAPERCLIP_SOURCES = [
    {
        "paper": "Bloem et al., arXiv:1604.06204",
        "claim": "add-only incremental CDCL retains learned clauses; assumptions activate formula parts",
        "url": "https://paperclip.gxl.ai/citations/papers/arx_1604.06204#L82-L88",
    },
    {
        "paper": "Bloem et al., arXiv:1604.06204",
        "claim": "finite CEGIS alternates candidates and counterexamples through monotone refinement",
        "url": "https://paperclip.gxl.ai/citations/papers/arx_1604.06204#L165-L173",
    },
    {
        "paper": "Monji, Modir, and Kocuk, arXiv:2512.14505",
        "claim": "Heilbronn maximin geometry uses the absolute signed determinant",
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L8-L13,L18-L22,L93-L97",
    },
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(REPOSITORY))


def load_summary(run: Path) -> dict[str, Any]:
    return json.loads((run / "summary.json").read_text())


def assert_common(summary: dict[str, Any], record_count: int) -> None:
    assert summary["schema"] == 2
    assert summary["mode"] == "exact support-clause incremental CDCL closure"
    assert summary["network_used"] is False
    assert summary["external_writes"] == []
    assert summary["denominator"] == 143
    assert summary["threshold_numerator"] == 747
    assert summary["representatives"] == [630, 1005, 1004, 649]
    assert summary["status_counts"] == {"unsatisfiable": record_count}
    assert len(summary["records"]) == record_count
    assert all(record["status"] == "unsatisfiable" for record in summary["records"])
    assert summary["candidates"] == []
    assert summary["gate_clearing"] is False
    for key, (_, expected) in INPUTS.items():
        field = {
            "public_snapshot.json": "snapshot_sha256",
            "frozen_verifier.py": "verifier_sha256",
            "prior_summary.json": "prior_summary_sha256",
        }.get(key)
        if field:
            assert summary[field] == expected


def expected_release_inventory(summary: dict[str, Any]) -> dict[int, set[tuple[int, ...]]]:
    expected: dict[int, set[tuple[int, ...]]] = {}
    assert len(summary["models"]) == 4
    for model in summary["models"]:
        representative = int(model["representative_public_id"])
        labels = tuple(map(int, model["ranked_release_labels"]))
        assert len(labels) == 4 and len(set(labels)) == 4
        scenarios: set[tuple[int, ...]] = {()}
        scenarios.update((label,) for label in labels)
        scenarios.update(
            (labels[first], labels[second])
            for first in range(3)
            for second in range(first + 1, 4)
        )
        expected[representative] = scenarios
    return expected


def assert_base(summary: dict[str, Any]) -> None:
    assert_common(summary, 4)
    assert summary["run_configuration"]["skip_base_union"] is False
    assert summary["run_configuration"]["skip_releases"] is True
    assert len(summary["models"]) == 1
    assert summary["models"][0]["model"] == "four-cell-base-union"
    assert {
        (int(record["representative_public_id"]), tuple(record["released_labels"]))
        for record in summary["records"]
    } == {(630, ()), (1005, ()), (1004, ()), (649, ())}


def assert_releases(summary: dict[str, Any]) -> None:
    assert_common(summary, 44)
    configuration = summary["run_configuration"]
    assert configuration["skip_base_union"] is True
    assert configuration["skip_releases"] is False
    assert configuration["release_radius"] == 8
    assert configuration["release_label_count"] == 4
    assert {
        int(model["representative_public_id"]) for model in summary["models"]
    } == {630, 1005, 1004, 649}
    expected = expected_release_inventory(summary)
    actual: dict[int, set[tuple[int, ...]]] = {representative: set() for representative in expected}
    for record in summary["records"]:
        representative = int(record["representative_public_id"])
        actual[representative].add(tuple(map(int, record["released_labels"])))
    assert actual == expected


def compact_model(model: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "model",
        "representative_public_id",
        "release_radius",
        "ranked_release_labels",
        "union_domain_sizes",
        "domain_coordinates_sha256",
        "decision_variable_count",
        "total_variable_count",
        "scenario_variable_count",
        "triple_guard_count",
        "clause_count",
        "literal_count",
        "clause_sha256",
        "section_counts",
        "nontrivial_triple_count",
    )
    return {key: model[key] for key in keys if key in model}


def compact_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": record["key"],
        "representative_public_id": record["representative_public_id"],
        "released_labels": record["released_labels"],
        "domain_sizes": record["domain_sizes"],
        "allowed_indices_sha256": record["allowed_indices_sha256"],
        "status": record["status"],
        "conflict_delta": record["conflict_delta"],
        "solve_slices": record["solve_slices"],
        "assumption_count": record["assumption_count"],
        "assumptions_sha256": record["assumptions_sha256"],
        "unsat_core_triple_count": record["unsat_core_triple_count"],
    }


def deterministic_projection(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_configuration": summary["run_configuration"],
        "models": [compact_model(model) for model in summary["models"]],
        "records": [
            {
                "key": record["key"],
                "representative_public_id": record["representative_public_id"],
                "released_labels": record["released_labels"],
                "domain_sizes": record["domain_sizes"],
                "allowed_indices_sha256": record["allowed_indices_sha256"],
                "status": record["status"],
                "assumption_count": record["assumption_count"],
                "assumptions_sha256": record["assumptions_sha256"],
            }
            for record in summary["records"]
        ],
    }


def run_hashes(run: Path) -> dict[str, str]:
    return {
        name: sha256(run / name)
        for name in ("summary.json", "checkpoint.json", "events.jsonl")
    }


def atomic_json(path: Path, value: object) -> None:
    encoded = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
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


def main() -> int:
    for label, (path, expected) in INPUTS.items():
        actual = sha256(path)
        if actual != expected:
            raise RuntimeError(f"{label} hash drift: expected {expected}, got {actual}")

    summaries = {label: load_summary(run) for label, run in RUNS.items()}
    expected_source_configuration = {
        "support_closure_sha256": sha256(ROOT / "support_closure.py"),
        "q143_cegis_sha256": sha256(ROOT / "q143_cegis.py"),
    }
    for label, summary in summaries.items():
        for field, expected in expected_source_configuration.items():
            if summary["run_configuration"].get(field) != expected:
                raise RuntimeError(f"{label} was generated by a different {field}")
    assert_base(summaries["primary_base"])
    assert_base(summaries["replay_base"])
    assert_releases(summaries["primary_releases"])
    assert_releases(summaries["replay_releases"])
    if deterministic_projection(summaries["primary_base"]) != deterministic_projection(
        summaries["replay_base"]
    ):
        raise RuntimeError("base replay changed deterministic formula or scenario projection")
    if deterministic_projection(summaries["primary_releases"]) != deterministic_projection(
        summaries["replay_releases"]
    ):
        raise RuntimeError("release replay changed deterministic formula or scenario projection")

    primary_base = summaries["primary_base"]
    primary_releases = summaries["primary_releases"]
    source_paths = [
        ROOT / "q143_cegis.py",
        ROOT / "support_closure.py",
        ROOT / "verify_candidate.py",
        ROOT / "freeze_receipt.py",
    ]
    receipt = {
        "schema": 1,
        "problem": "heilbronn-triangles",
        "result": "bounded_no_go",
        "claim": (
            "All four formerly unresolved q=143 heterogeneous radius-3/5 cells, "
            "plus every radius-8 single- and two-label release among four "
            "pressure-ranked labels per cell, are UNSAT in the exact finite "
            "support-clause formulation."
        ),
        "scope_caveat": (
            "This is not a global q=143 lattice proof and not a continuous Heilbronn "
            "upper bound. CaDiCaL results are independently replayed formula receipts, "
            "not checked DRAT/LRAT proof objects."
        ),
        "mathematics": {
            "denominator": 143,
            "determinant_threshold_numerator": 747,
            "threshold_exact": "747/20449",
            "threshold_decimal": primary_base["minimum_grid_score"],
            "live_score": primary_base["live_score"],
            "strict_target": primary_base["target_strictly_above"],
            "threshold_minus_target": primary_base["grid_gate_margin"],
        },
        "inventory": {
            "base_scenarios": 4,
            "single_label_release_scenarios": 16,
            "two_label_release_scenarios": 24,
            "release_scenarios_including_repeated_bases": 44,
            "candidate_count": 0,
            "gate_clearing": False,
        },
        "base_formula": compact_model(primary_base["models"][0]),
        "base_records": [compact_record(record) for record in primary_base["records"]],
        "release_formulas": [compact_model(model) for model in primary_releases["models"]],
        "release_records": [compact_record(record) for record in primary_releases["records"]],
        "independent_replay": {
            "fresh_solver_processes": True,
            "base_deterministic_projection_equal": True,
            "release_deterministic_projection_equal": True,
            "run_artifact_hashes": {
                label: {
                    "path": relative(run),
                    **run_hashes(run),
                }
                for label, run in RUNS.items()
            },
        },
        "frozen_inputs": {
            label: {"path": relative(path), "sha256": expected}
            for label, (path, expected) in INPUTS.items()
        },
        "source_hashes": {relative(path): sha256(path) for path in source_paths},
        "paperclip_sources": PAPERCLIP_SOURCES,
        "external_activity": {"network_used_by_solver": False, "writes": []},
    }
    atomic_json(RECEIPT, receipt)
    print(json.dumps({"receipt": relative(RECEIPT), "sha256": sha256(RECEIPT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
