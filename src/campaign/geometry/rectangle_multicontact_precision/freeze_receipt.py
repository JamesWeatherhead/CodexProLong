#!/usr/bin/env python3
"""Freeze aggregate evidence for the rectangle multi-contact campaign."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import verifier_formula


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
RUN_NAMES = (
    "20260815T_RECT_CODIM2_CANONICAL",
    "20260815T_RECT_CODIM3_CANONICAL",
    "20260815T_RECT_CODIM2_DISTINCT1010",
    "20260815T_RECT_CODIM3_DISTINCT1010",
)
VERIFIER_SHA256 = "c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9"
TARGET = 2.365832385307997


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def resolve_recorded_path(value: str) -> Path:
    """Resolve a historical path without rewriting the immutable run log."""
    path = Path(value)
    if path.exists():
        return path
    if not path.is_absolute():
        return REPOSITORY / path
    if "campaign" in path.parts:
        index = path.parts.index("campaign")
        return REPOSITORY.joinpath(*path.parts[index:])
    raise RuntimeError(f"recorded path is outside the repository: {value}")


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPOSITORY.resolve()).as_posix()
    except ValueError as error:
        raise RuntimeError(f"path is outside the repository: {path}") from error


def portableize(value: Any) -> Any:
    """Convert repository-local absolute strings to stable relative paths."""
    if isinstance(value, dict):
        return {key: portableize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portableize(item) for item in value]
    if isinstance(value, tuple):
        return [portableize(item) for item in value]
    if isinstance(value, str) and Path(value).is_absolute():
        return portable_path(resolve_recorded_path(value))
    return value


def main() -> int:
    verifier_formula.assert_verifier_hash()
    runs = []
    union_wl: set[str] = set()
    total_graphs = 0
    total_accepted = 0
    total_vertices = 0
    best_changed: dict[str, Any] | None = None

    for name in RUN_NAMES:
        directory = HERE / "runs" / name
        summary_path = directory / "summary.json"
        events_path = directory / "events.jsonl"
        summary = json.loads(summary_path.read_text())
        if summary["verifier_sha256"] != VERIFIER_SHA256:
            raise RuntimeError(f"verifier mismatch in {name}")
        accepted_signatures: set[str] = set()
        for line in events_path.read_text().splitlines():
            event = json.loads(line)
            if event.get("event") == "graph_accepted":
                accepted_signatures.add(str(event["signature"]))
                union_wl.add(str(event["wl_signature"]))
        if len(accepted_signatures) != int(summary["accepted_labeled_graphs"]):
            raise RuntimeError(f"accepted-event mismatch in {name}")
        changed = summary["best_changed"]
        if changed is None:
            raise RuntimeError(f"run has no changed graph: {name}")
        payload_path = resolve_recorded_path(changed["payload"])
        if sha256_file(payload_path) != changed["payload_sha256"]:
            raise RuntimeError(f"changed payload hash mismatch in {name}")
        run_record = {
            "run": name,
            "dimension": int(summary.get("dimension", 2)),
            "seed": summary["seed"],
            "seed_sha256": summary["seed_sha256"],
            "release_sets_processed": int(
                summary.get("release_pairs_processed", summary.get("release_triples_processed"))
            ),
            "linear_vertices": int(summary["linear_vertices"]),
            "graphs_tested": int(summary["graphs_tested"]),
            "accepted_labeled_graphs": int(summary["accepted_labeled_graphs"]),
            "unlabeled_wl_graph_classes": int(summary["unlabeled_wl_graph_classes"]),
            "best_score": float(summary["best_score"]),
            "best_margin_to_target": float(summary["best_margin_to_target"]),
            "best_changed": changed,
            "summary_sha256": sha256_file(summary_path),
            "events_sha256": sha256_file(events_path),
            "config_sha256": sha256_file(directory / "config.json"),
        }
        runs.append(run_record)
        total_graphs += run_record["graphs_tested"]
        total_accepted += run_record["accepted_labeled_graphs"]
        total_vertices += run_record["linear_vertices"]
        if best_changed is None or float(changed["score"]) > float(best_changed["score"]):
            best_changed = {"run": name, **changed}

    canonical_base = json.loads((HERE / "runs" / RUN_NAMES[0] / "summary.json").read_text())["best"]
    if sha256_file(resolve_recorded_path(canonical_base["payload"])) != canonical_base["payload_sha256"]:
        raise RuntimeError("canonical base payload hash mismatch")
    assert best_changed is not None
    output = {
        "problem": "circles-rectangle",
        "live": {
            "problem_id": 18,
            "leader": 2.365832385207997,
            "min_improvement": 1e-10,
            "target_strictly_above": TARGET,
            "solution_schema": {"circles": "array of 21 [x, y, r] triples"},
            "verifier_sha256": VERIFIER_SHA256,
            "pair_tolerance": 1e-9,
            "perimeter_tolerance": 1e-9,
        },
        "evaluation_mirror": {
            "path": str(Path(verifier_formula.__file__)),
            "sha256": sha256_file(Path(verifier_formula.__file__)),
            "frozen_verifier_executed": False,
        },
        "gate_clearing": False,
        "canonical_tolerance_ceiling": canonical_base,
        "canonical_gap_to_gate": TARGET - float(canonical_base["score"]),
        "best_changed_global": best_changed,
        "best_changed_gap_to_gate": TARGET - float(best_changed["score"]),
        "total_linear_vertices": total_vertices,
        "total_graphs_tested": total_graphs,
        "total_accepted_labeled_graphs": total_accepted,
        "union_unlabeled_wl_graph_classes": len(union_wl),
        "runs": runs,
        "conclusion": (
            "No gate clear. Exhaustive codimension-two and linearized codimension-three "
            "contact replacement from both retained rigid public graph classes found no "
            "changed topology within 0.0037 of the live target."
        ),
    }
    output = portableize(output)
    atomic_json(HERE / "receipt.json", output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
