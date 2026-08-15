#!/usr/bin/env python3
"""Hash, topology, formula, and optional full deterministic replay.

Only the local, authored ``search`` module is imported. The frozen verifier is
hashed and its formula is independently transcribed here; it is never imported
or dynamically executed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import networkx as nx
import numpy as np
import scipy

import search


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def independent_formula(points: np.ndarray) -> float:
    vectors = np.array(points, dtype=np.float64)
    if vectors.shape != (282, 3):
        raise ValueError(f"shape mismatch: {vectors.shape}")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms < 1e-12] = 1e-12
    vectors = vectors / norms
    diffs = vectors[:, None, :] - vectors[None, :, :]
    dist_sq = np.sum(diffs**2, axis=2)
    iu = np.triu_indices(282, k=1)
    dists = np.sqrt(dist_sq[iu])
    dists[dists < 1e-12] = 1e-12
    return float(np.sum(1.0 / dists))


def load_incumbent() -> tuple[np.ndarray, bytes]:
    raw = search.SNAPSHOT.read_bytes()
    snapshot = json.loads(raw)
    solution = next(
        item
        for item in snapshot["solutions"]
        if int(item["id"]) == search.LEADER_SOLUTION_ID
    )
    return search.normalize(np.asarray(solution["data"]["vectors"], dtype=float)), raw


def replay_abstract_classes(
    base_faces: frozenset[search.Face], payload: dict[str, object]
) -> tuple[list[search.Mutation], int]:
    mutations: list[search.Mutation] = []
    for expected_id, record in enumerate(payload["mutations"]):
        if int(record["mutation_id"]) != expected_id:
            raise ValueError("non-contiguous mutation IDs")
        faces = base_faces
        moves: list[search.Move] = []
        for move_record in record["moves"]:
            move = search.Move(
                tuple(int(value) for value in move_record["edge"]),
                tuple(int(value) for value in move_record["opposite"]),
            )
            faces = search.apply_flip(faces, move.edge, move.opposite)
            moves.append(move)
        mutation = search.Mutation(
            str(record["operator"]),
            tuple(moves),
            faces,
            record.get("parent_faces_sha256"),
        )
        if mutation.face_hash != record["faces_sha256"]:
            raise ValueError(f"mutation {expected_id} face hash mismatch")
        if mutation.wl_hash != record["wl_hash"]:
            raise ValueError(f"mutation {expected_id} WL hash mismatch")
        if mutation.histogram != record["degree_histogram"]:
            raise ValueError(f"mutation {expected_id} degree histogram mismatch")
        mutations.append(mutation)

    exact_representatives: list[search.Mutation] = []
    for mutation in mutations:
        search.exact_class_add(exact_representatives, mutation)
    return mutations, len(exact_representatives)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument(
        "--full",
        action="store_true",
        help="regenerate and relax every trial, rather than only replaying artifacts",
    )
    args = parser.parse_args()
    run = args.run.resolve()

    summary_path = run / "summary.json"
    receipt_path = run / "receipt.json"
    topology_path = run / "topology_classes.json"
    events_path = run / "events.jsonl"
    candidate_path = run / "best_candidate.json"
    summary = json.loads(summary_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    topology_payload = json.loads(topology_path.read_text())
    event_raw = events_path.read_bytes()
    event_lines = event_raw.splitlines(keepends=True)
    events = [json.loads(line) for line in event_lines]

    if events[-1]["event"] != "complete":
        raise ValueError("missing terminal completion event")
    if sha256(summary_path) != receipt["summary_sha256"]:
        raise ValueError("summary hash mismatch")
    if sha256(topology_path) != receipt["topology_classes_sha256"]:
        raise ValueError("topology class hash mismatch")
    if sha256(candidate_path) != receipt["candidate_sha256"]:
        raise ValueError("candidate hash mismatch")
    prefix_hash = hashlib.sha256(b"".join(event_lines[:-1])).hexdigest()
    if prefix_hash != receipt["events_sha256_before_completion"]:
        raise ValueError("event prefix hash mismatch")
    if hashlib.sha256(receipt_path.read_bytes()).hexdigest() != events[-1]["receipt_sha256"]:
        raise ValueError("terminal receipt hash mismatch")
    if search.sha256_path(search.VERIFIER) != search.VERIFIER_SHA256:
        raise ValueError("frozen verifier hash mismatch")

    incumbent, snapshot_raw = load_incumbent()
    if hashlib.sha256(snapshot_raw).hexdigest() != summary["snapshot_sha256"]:
        raise ValueError("snapshot hash mismatch")
    incumbent_faces = search.faces_from_points(incumbent)
    mutations, exact_class_count = replay_abstract_classes(
        incumbent_faces, topology_payload
    )
    declared_exact = int(summary["enumeration"]["selected_unique_graph_class_count"])
    if exact_class_count != declared_exact:
        raise ValueError(
            f"exact class count mismatch: replay {exact_class_count}, declared {declared_exact}"
        )

    candidate = np.asarray(json.loads(candidate_path.read_text())["vectors"], dtype=float)
    candidate_score = independent_formula(candidate)
    if candidate_score != float(receipt["frozen_formula_score"]):
        raise ValueError("candidate frozen-formula score mismatch")
    if candidate_score != float(summary["best"]["score"]):
        raise ValueError("summary best score mismatch")
    candidate_topology = search.topology(search.normalize(candidate))
    if candidate_topology != summary["best"]["topology"]:
        raise ValueError("candidate topology mismatch")

    trial_events = [event for event in events if event["event"] == "trial"]
    full_replayed = 0
    max_score_delta = 0.0
    if args.full:
        start = events[0]
        bounds = start["bounds"]
        for event in trial_events:
            mutation = mutations[int(event["mutation_id"])]
            initial, used = search.realize_mutation(
                incumbent,
                incumbent_faces,
                mutation,
                float(event["requested_fraction"]),
            )
            if used != [float(value) for value in event["used_fractions"]]:
                raise ValueError(f"trial {event['trial']} realized fractions mismatch")
            if search.topology(initial) != event["initial_topology"]:
                raise ValueError(f"trial {event['trial']} initial topology mismatch")
            relaxed, _ = search.relax(
                initial, int(bounds["rounds"]), int(bounds["maxiter"])
            )
            replay_score = independent_formula(relaxed)
            delta = abs(replay_score - float(event["frozen_formula_score"]))
            max_score_delta = max(max_score_delta, delta)
            if delta > 5e-10:
                raise ValueError(f"trial {event['trial']} score delta {delta}")
            if search.topology(relaxed) != event["final_topology"]:
                raise ValueError(f"trial {event['trial']} final topology mismatch")
            full_replayed += 1

    result = {
        "status": "pass",
        "run": run.name,
        "full_trial_replay_requested": bool(args.full),
        "full_trials_replayed": full_replayed,
        "recorded_trial_count": len(trial_events),
        "max_replayed_score_delta": max_score_delta,
        "abstract_mutation_path_count": len(mutations),
        "exact_graph_class_count": exact_class_count,
        "candidate_sha256": sha256(candidate_path),
        "candidate_frozen_formula_score": candidate_score,
        "candidate_topology": candidate_topology,
        "target_strictly_below": float(receipt["target_strictly_below"]),
        "gate_clearing": candidate_score < float(receipt["target_strictly_below"]),
        "hashes": {
            "verifier_sha256": search.VERIFIER_SHA256,
            "snapshot_sha256": hashlib.sha256(snapshot_raw).hexdigest(),
            "summary_sha256": sha256(summary_path),
            "receipt_sha256": sha256(receipt_path),
            "topology_classes_sha256": sha256(topology_path),
            "events_sha256": sha256(events_path),
        },
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "networkx": nx.__version__,
        },
        "verifier_execution": "none; hash checked and formula independently transcribed",
    }
    output = run / "independent_replay.json"
    if output.exists():
        raise FileExistsError(output)
    search.write_once(output, result)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
