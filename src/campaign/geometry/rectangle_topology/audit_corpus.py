#!/usr/bin/env python3
"""Exhaustive retained-corpus audit for circles-rectangle problem 18."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

from core import (
    CORPUS_SHA256,
    VARIABLES,
    atomic_json,
    circles_to_values,
    constraint_jacobian,
    decode_active,
    normalize_origin,
    sha256_file,
    candidate_metrics,
)


def invariant_topology_hash(active: list[tuple[str, int, int | str]]) -> str:
    graph = nx.Graph()
    for index in range(21):
        graph.add_node(f"c{index}", kind="circle")
    wall_nodes = {wall: f"w{wall}" for wall in ("L", "R", "B", "T")}
    for node in wall_nodes.values():
        graph.add_node(node, kind="wall")
    for first, second in (("L", "B"), ("B", "R"), ("R", "T"), ("T", "L")):
        graph.add_edge(wall_nodes[first], wall_nodes[second], kind="frame")
    for kind, first, second in active:
        if kind == "P":
            graph.add_edge(f"c{first}", f"c{int(second)}", kind="pair")
        elif kind == "W":
            graph.add_edge(f"c{first}", wall_nodes[str(second)], kind="wall_contact")
    return nx.weisfeiler_lehman_graph_hash(graph, node_attr="kind", edge_attr="kind", iterations=8)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stamp", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--campaign-root", type=Path, default=Path(__file__).parents[2])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign = args.campaign_root.resolve()
    latest = json.loads((campaign / "research_corpus" / "latest.json").read_text())
    database = campaign / "research_corpus" / latest["database"]
    if sha256_file(database) != CORPUS_SHA256:
        raise RuntimeError("corpus database hash mismatch")
    connection = sqlite3.connect(database)
    problem = connection.execute(
        "SELECT id,slug,title,description,min_improvement,verifier_sha256 FROM problems WHERE id=18"
    ).fetchone()
    if problem is None:
        raise RuntimeError("missing problem 18")

    constructions: list[dict[str, Any]] = []
    clusters: dict[str, dict[str, Any]] = {}
    for row in connection.execute(
        "SELECT id,agent_name,score,created_at,record_sha256,record_json "
        "FROM solutions WHERE problem_id=18 ORDER BY score DESC,id"
    ):
        solution_id, agent, score, created_at, record_sha, record_json = row
        record = json.loads(record_json)
        circles = np.asarray(record["data"]["circles"], dtype=float)
        normalized, width, height = normalize_origin(circles)
        active = decode_active(normalized, 1e-6)
        pair_count = sum(item[0] == "P" for item in active)
        wall_count = sum(item[0] == "W" for item in active)
        perimeter_active = any(item[0] == "E" for item in active)
        jacobian = constraint_jacobian(
            circles_to_values(normalized), active, 1e-9, 1e-9
        )
        rank = int(np.linalg.matrix_rank(jacobian, tol=1e-9)) if len(active) else 0
        topology_hash = invariant_topology_hash(active)
        construction = {
            "solution_id": solution_id,
            "agent_name": agent,
            "reported_score": score,
            "created_at": created_at,
            "record_sha256": record_sha,
            "metrics_literal": candidate_metrics(normalized, 1e-9, 1e-9),
            "width": width,
            "height": height,
            "pair_contacts_at_1e-6": pair_count,
            "wall_contacts_at_1e-6": wall_count,
            "perimeter_active_at_1e-6": perimeter_active,
            "active_equation_count": len(active),
            "active_jacobian_rank": rank,
            "rigid_square_system": bool(len(active) == VARIABLES and rank == VARIABLES),
            "invariant_topology_hash": topology_hash,
        }
        constructions.append(construction)
        cluster = clusters.setdefault(
            topology_hash,
            {
                "invariant_topology_hash": topology_hash,
                "solution_ids": [],
                "best_reported_score": None,
                "best_solution_id": None,
                "pair_contact_counts": set(),
                "wall_contact_counts": set(),
                "rigid_members": 0,
            },
        )
        cluster["solution_ids"].append(solution_id)
        cluster["pair_contact_counts"].add(pair_count)
        cluster["wall_contact_counts"].add(wall_count)
        cluster["rigid_members"] += int(construction["rigid_square_system"])
        if cluster["best_reported_score"] is None or score > cluster["best_reported_score"]:
            cluster["best_reported_score"] = score
            cluster["best_solution_id"] = solution_id

    thread_rows = connection.execute(
        "SELECT id,agent_name,title,created_at,reply_count,record_sha256,length(body) "
        "FROM threads WHERE problem_id=18 OR source_problem_id=18 OR problem_slug='circles-rectangle' "
        "ORDER BY id"
    ).fetchall()
    thread_ids = [row[0] for row in thread_rows]
    replies = []
    for thread_id in thread_ids:
        replies.extend(
            connection.execute(
                "SELECT id,thread_id,parent_reply_id,agent_name,created_at,record_sha256,length(body) "
                "FROM replies WHERE thread_id=? ORDER BY id",
                (thread_id,),
            ).fetchall()
        )
    connection.close()

    cluster_records = []
    for cluster in clusters.values():
        cluster["pair_contact_counts"] = sorted(cluster["pair_contact_counts"])
        cluster["wall_contact_counts"] = sorted(cluster["wall_contact_counts"])
        cluster_records.append(cluster)
    cluster_records.sort(key=lambda item: float(item["best_reported_score"]), reverse=True)
    audit = {
        "stamp": args.stamp,
        "problem": {
            "id": problem[0],
            "slug": problem[1],
            "title": problem[2],
            "description": problem[3],
            "min_improvement": problem[4],
            "verifier_sha256": problem[5],
        },
        "corpus_database": str(database),
        "corpus_database_sha256": CORPUS_SHA256,
        "coverage": {
            "retained_constructions_read": len(constructions),
            "threads_read_in_full": len(thread_rows),
            "replies_read_in_full": len(replies),
            "thread_ids": thread_ids,
            "reply_ids": [row[0] for row in replies],
        },
        "threads": [
            {
                "id": row[0],
                "agent_name": row[1],
                "title": row[2],
                "created_at": row[3],
                "reply_count": row[4],
                "record_sha256": row[5],
                "body_length": row[6],
            }
            for row in thread_rows
        ],
        "replies": [
            {
                "id": row[0],
                "thread_id": row[1],
                "parent_reply_id": row[2],
                "agent_name": row[3],
                "created_at": row[4],
                "record_sha256": row[5],
                "body_length": row[6],
            }
            for row in replies
        ],
        "constructions": constructions,
        "invariant_topology_clusters": cluster_records,
        "rigid_public_sources": [
            {
                "solution_id": item["solution_id"],
                "reported_score": item["reported_score"],
                "invariant_topology_hash": item["invariant_topology_hash"],
            }
            for item in constructions
            if item["rigid_square_system"]
        ],
    }
    run_dir = Path(__file__).parent / "runs" / args.stamp / "audit"
    atomic_json(run_dir / "corpus_audit.json", audit)
    summary = {
        "stamp": args.stamp,
        "corpus_database_sha256": CORPUS_SHA256,
        "construction_count": len(constructions),
        "thread_count": len(thread_rows),
        "reply_count": len(replies),
        "invariant_topology_cluster_count": len(cluster_records),
        "rigid_construction_count": sum(item["rigid_square_system"] for item in constructions),
        "rigid_invariant_topology_count": len(
            {item["invariant_topology_hash"] for item in constructions if item["rigid_square_system"]}
        ),
        "best_distinct_rigid_source_ids": [
            item["best_solution_id"] for item in cluster_records if item["rigid_members"] > 0
        ],
        "audit_path": str(run_dir / "corpus_audit.json"),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
