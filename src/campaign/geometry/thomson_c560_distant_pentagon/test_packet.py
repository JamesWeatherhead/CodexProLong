#!/usr/bin/env python3
"""Standalone integrity tests for the coordinate-free public packet."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads(
        (HERE / "PUBLICATION_MANIFEST.json").read_text(encoding="utf-8")
    )
    paths = [entry["path"] for entry in manifest["include"]]
    if len(paths) != len(set(paths)) or set(paths) != {
        ".gitignore",
        "HANDOFF.md",
        "LICENSE",
        "PROVENANCE.md",
        "README.md",
        "freeze_publication.py",
        "replay_exact.py",
        "requirements.txt",
        "search.py",
        "test_packet.py",
        "receipt.json",
    }:
        raise ValueError("publication allowlist mismatch")
    for entry in manifest["include"]:
        path = HERE / entry["path"]
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing/nonregular allowlisted file: {path}")
        if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise ValueError(f"allowlisted hash/size mismatch: {path}")

    receipt = json.loads((HERE / "receipt.json").read_text(encoding="utf-8"))
    result = receipt["result"]
    problem = receipt["problem"]
    assert receipt["status"] == "frozen_quantified_no_go"
    assert receipt["scope"]["trial_count"] == 28
    assert receipt["scope"]["source_graph_count"] == 7
    assert result["source_retaining_count"] == 20
    assert result["defect_free_final_count"] == 24
    assert result["distinct_final_exact_isomorphism_class_count"] == 7
    assert result["best_all"]["score"] == 37148.1301703428
    assert not result["best_all"]["defect_free"]
    assert result["best_defect_free"]["score"] == 37148.14103932371
    assert result["best_defect_free"]["final_pentagon_separation"] == 5
    assert result["best_source_retaining"]["score"] == 37148.250685079416
    assert result["best_source_retaining"]["final_pentagon_separation"] == 4
    assert not result["gate_clearer"]
    assert result["best_all"]["score"] > problem["target_at_or_below"]
    assert not result["clamps_active"]
    boundary = receipt["publication_boundary"]
    assert not boundary["candidate_coordinates_included"]
    assert not boundary["private_graph_bytes_included"]
    assert not boundary["third_party_source_or_binary_bytes_included"]

    for name in (
        "freeze_publication.py",
        "replay_exact.py",
        "search.py",
        "test_packet.py",
    ):
        source = (HERE / name).read_text(encoding="utf-8")
        ast.parse(source, filename=name)
    for name in ("search.py", "replay_exact.py"):
        source = (HERE / name).read_text(encoding="utf-8")
        for forbidden in (
            "import requests",
            "import socket",
            "import subprocess",
            "urllib.request",
            "campaign/arena submit",
            "github.com/JamesWeatherhead",
        ):
            if forbidden in source:
                raise ValueError(f"forbidden runtime surface in {name}: {forbidden}")

    print("PASS: 11 allowlisted files; coordinate-free no-go receipt verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
