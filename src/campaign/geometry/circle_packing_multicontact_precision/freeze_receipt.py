#!/usr/bin/env python3
"""Freeze and independently characterize the completed codimension-two runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
REPOSITORY = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(CAMPAIGN / "geometry/circle_packing_topology"))
import codim2_pivots as pivot  # noqa: E402
import continue_contacts as cc  # noqa: E402


RUN_NAMES = (
    "20260815T_CODIM2_FULL_R2",
    "20260815T_CODIM2_NEUTRAL_FULL",
    "20260815T_CODIM2_DISTINCT1462_FULL",
)
BASE_URL = "https://einsteinarena.com"
WALL_IDS = {"L": 26, "R": 27, "B": 28, "T": 29}


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


def get_json(path: str, **parameters: Any) -> Any:
    query = urllib.parse.urlencode(parameters)
    url = BASE_URL + path + (("?" + query) if query else "")
    request = urllib.request.Request(url, headers={"User-Agent": "circle-packing-readonly-audit/1"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def graph_hash(active: list[tuple[str, int, int | str]]) -> str:
    graph = nx.Graph()
    for index in range(26):
        graph.add_node(index, label="circle")
    for index in range(26, 30):
        graph.add_node(index, label="wall")
    for first, second in ((26, 28), (28, 27), (27, 29), (29, 26)):
        graph.add_edge(first, second, kind="frame")
    for kind, first, second in active:
        if kind == "P":
            graph.add_edge(first, int(second), kind="contact")
        else:
            graph.add_edge(first, WALL_IDS[str(second)], kind="contact")
    digest = nx.weisfeiler_lehman_graph_hash(
        graph, node_attr="label", edge_attr="kind", iterations=8
    )
    degrees = sorted(dict(graph.degree()).values())
    return hashlib.sha256(
        json.dumps([digest, degrees, graph.number_of_edges()], separators=(",", ":")).encode()
    ).hexdigest()


def constraints_from_record(
    base: list[tuple[str, int, int | str]], record: dict[str, Any]
) -> list[tuple[str, int, int | str]]:
    released = {tuple(item) for item in record["released"]}
    return [item for item in base if item not in released] + [
        tuple(item) for item in record["added"]
    ]


def recover_payload(
    run: Path,
    config: dict[str, Any],
    record: dict[str, Any],
    evaluate,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    seed = json.loads(resolve_recorded_path(config["seed"]).read_text())
    circles = np.asarray(seed["circles"], dtype=np.float64)
    base_active = [tuple(item) for item in config["base_active"]]
    base = cc.solve_targets(cc.circles_to_values(circles), base_active)
    if not base.success:
        raise RuntimeError(f"cannot recover base for {run.name}: {base.residual}")
    released_indices = tuple(int(item) for item in record["released_indices"])
    start, _, _ = pivot.make_start(
        base.values,
        base_active,
        released_indices,
        np.asarray(record["opening"], dtype=float),
    )
    active = constraints_from_record(base_active, record)
    root = cc.solve_targets(start, active, pair_tolerance=cc.PAIR_TOLERANCE, max_evaluations=900)
    if not root.success:
        raise RuntimeError(f"cannot recover changed root for {run.name}: {root.residual}")
    payload, exact = pivot.exact_payload(root.values, evaluate)
    if payload is None:
        raise RuntimeError(f"recovered changed root is not accepted for {run.name}: {exact}")
    if abs(float(exact["literal_verifier_score"]) - float(record["score"])) > 2e-12:
        raise RuntimeError(f"changed score mismatch for {run.name}")
    path = run / "best_changed.json"
    atomic_json(path, payload)

    strict_root = cc.solve_targets(root.values, active, pair_tolerance=0.0, max_evaluations=1000)
    strict: dict[str, Any] = {"success": strict_root.success, "residual": strict_root.residual}
    if strict_root.success:
        strict_payload, strict_exact = pivot.exact_payload(strict_root.values, evaluate)
        strict.update(
            equation_score=cc.metrics(strict_root.values, 0.0)["score"],
            live_verifier_score=(
                strict_exact.get("literal_verifier_score") if strict_payload is not None else None
            ),
            exact=strict_exact,
        )
    return path, exact, strict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    evaluate = pivot.load_verifier()
    if args.offline:
        live = None
    else:
        problem = get_json("/api/problems/circle-packing")
        leaderboard = get_json("/api/solutions/best", problem_id=14, limit=1)
        verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
        live = {
            "problem_id": problem["id"],
            "scoring": problem["scoring"],
            "min_improvement": problem["minImprovement"],
            "solution_schema": problem["solutionSchema"],
            "verifier_sha256": verifier_hash,
            "leader_id": leaderboard[0]["id"],
            "leader_score": leaderboard[0]["score"],
        }
        if verifier_hash != pivot.VERIFIER_SHA256:
            raise RuntimeError(f"live verifier changed: {verifier_hash}")
        if problem["solutionSchema"] != pivot.LIVE_SCHEMA:
            raise RuntimeError(f"live solution schema changed: {problem['solutionSchema']}")

    run_records: list[dict[str, Any]] = []
    union_hashes: set[str] = set()
    best_changed_global: dict[str, Any] | None = None
    total_labeled = 0
    for name in RUN_NAMES:
        run = HERE / "runs" / name
        summary = json.loads((run / "summary.json").read_text())
        config = json.loads((run / "config.json").read_text())
        accepted: list[dict[str, Any]] = []
        hashes: set[str] = set()
        with (run / "events.jsonl").open() as handle:
            for line in handle:
                record = json.loads(line)
                if record.get("event") != "graph_accepted":
                    continue
                accepted.append(record)
                active = constraints_from_record(
                    [tuple(item) for item in config["base_active"]], record
                )
                digest = graph_hash(active)
                hashes.add(digest)
                union_hashes.add(digest)
        if not accepted:
            raise RuntimeError(f"run has no accepted changed graph: {name}")
        total_labeled += len(accepted)
        best_changed = max(accepted, key=lambda item: float(item["score"]))
        payload_path, exact, strict = recover_payload(
            run, config, best_changed, evaluate
        )
        changed_record = {
            "score": exact["literal_verifier_score"],
            "gap_to_gate": pivot.TARGET - float(exact["literal_verifier_score"]),
            "payload": str(payload_path),
            "payload_sha256": sha256_file(payload_path),
            "released": best_changed["released"],
            "added": best_changed["added"],
            "signature": best_changed["signature"],
            "classification": (
                "verifier-only" if exact["pair_tolerance_only"] else "physical-strict"
            ),
            "exact": exact,
            "strict": strict,
        }
        if best_changed_global is None or float(changed_record["score"]) > float(
            best_changed_global["score"]
        ):
            best_changed_global = {"run": name, **changed_record}
        scores = np.asarray([float(item["score"]) for item in accepted])
        run_records.append(
            {
                "run": name,
                "seed": config["seed"],
                "seed_sha256": config["seed_sha256"],
                "release_pairs": summary["release_pairs_processed"],
                "linear_vertices": summary["linear_vertices"],
                "graphs_tested": summary["graphs_tested"],
                "accepted_labeled_graphs": len(accepted),
                "unlabeled_wl_graph_classes": len(hashes),
                "score_quantiles": {
                    str(q): float(np.quantile(scores, q))
                    for q in (0.0, 0.5, 0.9, 0.99, 1.0)
                },
                "best_changed": changed_record,
                "summary_sha256": sha256_file(run / "summary.json"),
                "events_sha256": sha256_file(run / "events.jsonl"),
                "config_sha256": sha256_file(run / "config.json"),
            }
        )

    incumbent_path = HERE / "runs/20260815T_CODIM2_FULL_R2/best.json"
    incumbent_payload = json.loads(incumbent_path.read_text())
    if not pivot.schema_valid(incumbent_payload):
        raise RuntimeError("incumbent replay payload does not match schema")
    incumbent_score = float(evaluate(incumbent_payload))
    canonical_config = json.loads(
        (HERE / "runs/20260815T_CODIM2_FULL_R2/config.json").read_text()
    )
    canonical_active = [tuple(item) for item in canonical_config["base_active"]]
    canonical_values = cc.circles_to_values(
        np.asarray(incumbent_payload["circles"], dtype=np.float64)
    )
    canonical_strict_root = cc.solve_targets(
        canonical_values,
        canonical_active,
        pair_tolerance=0.0,
        max_evaluations=1000,
    )
    if not canonical_strict_root.success:
        raise RuntimeError("canonical strict physical root recovery failed")
    canonical_strict_payload, canonical_strict_exact = pivot.exact_payload(
        canonical_strict_root.values, evaluate
    )
    if canonical_strict_payload is None:
        raise RuntimeError("canonical strict physical root failed verifier replay")
    receipt = {
        "problem": "circle-packing",
        "live": live,
        "verifier": str(pivot.VERIFIER),
        "verifier_sha256": pivot.VERIFIER_SHA256,
        "evaluation_mirror": {
            "path": str(HERE / "verifier_formula.py"),
            "sha256": sha256_file(HERE / "verifier_formula.py"),
            "frozen_verifier_executed": False,
        },
        "solution_schema": pivot.LIVE_SCHEMA,
        "leader": pivot.LEADER,
        "min_improvement": pivot.MIN_IMPROVEMENT,
        "target_strictly_above": pivot.TARGET,
        "pair_tolerance": cc.PAIR_TOLERANCE,
        "wall_tolerance": 0.0,
        "incumbent_tolerance_ceiling": {
            "score": incumbent_score,
            "gap_to_gate": pivot.TARGET - incumbent_score,
            "payload": str(incumbent_path),
            "payload_sha256": sha256_file(incumbent_path),
            "classification": "verifier-only",
            "maximum_pair_overrun": max(
                float(incumbent_payload["circles"][first][2])
                + float(incumbent_payload["circles"][second][2])
                - float(
                    np.linalg.norm(
                        np.asarray(incumbent_payload["circles"][first][:2])
                        - np.asarray(incumbent_payload["circles"][second][:2])
                    )
                )
                for first in range(26)
                for second in range(first + 1, 26)
            ),
            "strict_physical_root": {
                "equation_score": cc.metrics(canonical_strict_root.values, 0.0)["score"],
                "live_verifier_score": canonical_strict_exact["literal_verifier_score"],
                "classification": "physical-strict",
                "exact": canonical_strict_exact,
            },
        },
        "runs": run_records,
        "total_accepted_labeled_graphs": total_labeled,
        "union_unlabeled_wl_graph_classes": len(union_hashes),
        "best_changed_global": best_changed_global,
        "gate_clearing": bool(
            incumbent_score > pivot.TARGET
            or (best_changed_global is not None and best_changed_global["score"] > pivot.TARGET)
        ),
        "conclusion": (
            "No gate clear. The incumbent's 1e-9 pair-overlap tolerance root remains "
            "best; wall containment is exact and no wall overrun is accepted."
        ),
    }
    receipt = portableize(receipt)
    atomic_json(HERE / "receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
