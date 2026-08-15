#!/usr/bin/env python3
"""Standalone, network-free replay test for the Wichmann publication packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import search


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "20260815T084100Z_exact_sweep"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_manifest() -> int:
    manifest_path = HERE / "PUBLICATION_MANIFEST.json"
    if not manifest_path.exists():
        return 0
    manifest = load_json(manifest_path)
    assert isinstance(manifest, dict)
    count = 0
    for entry in manifest["include"]:
        path = HERE / entry["path"]
        assert path.is_file(), entry["path"]
        assert path.stat().st_size == entry["bytes"], entry["path"]
        assert sha256_file(path) == entry["sha256"], entry["path"]
        count += 1
    return count


def main() -> int:
    config = load_json(RUN / "config.json")
    frozen = load_json(RUN / "summary.json")
    audit = load_json(HERE / "local_verifier_audit.json")
    assert isinstance(config, dict) and isinstance(frozen, dict)
    assert isinstance(audit, dict)

    proof, frontier = search.run_sweep(config["max_marks"])
    regenerated = {
        "schema_version": search.SCHEMA_VERSION,
        "config": config,
        "proof": proof,
        "frontier": frontier,
        "outcome": "gate_clearer" if proof["any_gate_clearer"] else "quantified_no_go",
    }
    assert regenerated == frozen
    assert not proof["any_gate_clearer"]
    assert proof["nondegenerate_parameter_pairs_enumerated"] == 498_002
    assert (
        proof["enumerated_parameter_tuple_sha256"]
        == "0f43b984899e5ac20cbb3ea956f953c618b040cccd396137fed34ec4f57e86bf"
    )

    expected = {
        "degenerate_r0_known_four_mark_control": (0, 1, 4, 6),
        "nondegenerate_global_best": (1, 3, 10, 36),
        "size_360_best": (59, 121, 360, 43_318),
        "near_49k_window_best": (63, 128, 383, 49_023),
        "coverage_at_least_49110_best": (64, 129, 388, 50_310),
    }
    for record in frontier:
        r, s, cardinality, coverage = expected[record["label"]]
        assert (record["r"], record["s"]) == (r, s)
        assert record["cardinality"] == cardinality
        assert record["coverage"] == coverage
        marks = search.wichmann_marks(r, s, record["i"], record["j"])
        replay_coverage, exact, score = search.literal_evaluate(marks)
        assert replay_coverage == coverage == marks[-1]
        assert exact.numerator == record["score_exact_numerator"]
        assert exact.denominator == record["score_exact_denominator"]
        assert score == record["score_float"]
        assert search.sha256_value({"set": marks}) == record["payload_sha256"]
        assert not record["gate_clearing"]

    assert audit["verifier_sha256"] == search.VERIFIER_SHA256
    assert audit["all_literal_matches"] is True
    assert all(row["literal_match"] for row in audit["rows"])
    assert {
        row["label"]: row["payload_sha256"] for row in audit["rows"]
    } == {record["label"]: record["payload_sha256"] for record in frontier}

    manifest_files = verify_manifest()
    print(
        json.dumps(
            {
                "status": "ok",
                "frontier_records": len(frontier),
                "parameter_pairs": proof["nondegenerate_parameter_pairs_enumerated"],
                "manifest_files_verified": manifest_files,
                "network_used": False,
                "downloaded_verifier_executed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
