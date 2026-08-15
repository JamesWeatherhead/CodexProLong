#!/usr/bin/env python3
"""Exact graph-isomorphism audit for final Thomson triangulations."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import scipy
from scipy.spatial import ConvexHull


HERE = Path(__file__).resolve().parent
SNAPSHOT = (
    HERE.parents[2]
    / "campaign/geometry/snapshots/thomson-problem_20260814T234236Z.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def graph(points: object) -> nx.Graph:
    rows = np.asarray(points, dtype=np.float64)
    rows /= np.linalg.norm(rows, axis=1, keepdims=True)
    hull = ConvexHull(rows)
    result = nx.Graph()
    result.add_nodes_from(range(rows.shape[0]))
    for a, b, c in hull.simplices:
        result.add_edges_from(
            ((int(a), int(b)), (int(a), int(c)), (int(b), int(c)))
        )
    return result


def write_once(path: Path, value: object) -> str:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    snapshot = json.loads(SNAPSHOT.read_text())
    leader = next(item for item in snapshot["solutions"] if int(item["id"]) == 561)
    leader_graph = graph(leader["data"]["vectors"])
    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    trials = [event for event in events if event["event"] == "trial"]
    checks = []
    for event in trials:
        candidate_path = Path(event["candidate"])
        if sha256(candidate_path) != event["candidate_sha256"]:
            raise ValueError(f"candidate hash mismatch for trial {event['trial']}")
        candidate = json.loads(candidate_path.read_text())
        candidate_graph = graph(candidate["vectors"])
        checks.append(
            {
                "trial": int(event["trial"]),
                "candidate_sha256": event["candidate_sha256"],
                "isomorphic_to_incumbent": nx.is_isomorphic(
                    leader_graph, candidate_graph
                ),
            }
        )
    result = {
        "status": "pass" if all(row["isomorphic_to_incumbent"] for row in checks) else "fail",
        "run": str(run),
        "snapshot_sha256": sha256(SNAPSHOT),
        "incumbent_solution_id": 561,
        "incumbent_graph": {
            "vertices": leader_graph.number_of_nodes(),
            "edges": leader_graph.number_of_edges(),
        },
        "trial_count": len(checks),
        "exactly_isomorphic_to_incumbent_count": sum(
            bool(row["isomorphic_to_incumbent"]) for row in checks
        ),
        "checks": checks,
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "networkx": nx.__version__,
        },
    }
    output = run / "exact_isomorphism_audit.json"
    output_sha = write_once(output, result)
    print(json.dumps({**result, "receipt_sha256": output_sha}, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
