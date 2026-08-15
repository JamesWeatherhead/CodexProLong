#!/usr/bin/env python3
"""Independent hash, topology, and frozen-verifier replay for one search run."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
from scipy.spatial import ConvexHull


HERE = Path(__file__).resolve().parent
ARENA = HERE.parents[2]
VERIFIER_SHA256 = "4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af"
VERIFIER = ARENA / f"campaign/state/problems/thomson-problem/{VERIFIER_SHA256}.py"

Face = tuple[int, int, int]
Edge = tuple[int, int]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    if not np.isfinite(points).all() or np.any(norms < 1e-12):
        raise ValueError("invalid point array")
    return points / norms


def parse_xyz(path: Path) -> np.ndarray:
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [
        [float(value) for value in line.split()[1:4]]
        for line in lines[2:]
        if len(line.split()) >= 4
    ]
    points = normalize(np.asarray(rows))
    if int(lines[0]) != 72 or points.shape != (72, 3):
        raise ValueError("invalid frozen N=72 source")
    return points


def faces_from_points(points: np.ndarray) -> frozenset[Face]:
    return frozenset(
        tuple(sorted(int(value) for value in face))
        for face in ConvexHull(points).simplices
    )


def graph_data(
    faces: frozenset[Face], count: int
) -> tuple[set[Edge], np.ndarray, nx.Graph]:
    edges: set[Edge] = set()
    for a, b, c in faces:
        edges.update(
            {
                tuple(sorted((a, b))),
                tuple(sorted((a, c))),
                tuple(sorted((b, c))),
            }
        )
    degrees = np.zeros(count, dtype=np.int16)
    for a, b in edges:
        degrees[a] += 1
        degrees[b] += 1
    graph = nx.Graph()
    graph.add_nodes_from(range(count))
    graph.add_edges_from(edges)
    return edges, degrees, graph


def faces_hash(faces: frozenset[Face]) -> str:
    payload = json.dumps(sorted(faces), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def apply_flip(faces: frozenset[Face], edge: Edge, opposite: Edge) -> frozenset[Face]:
    a, b = edge
    c, d = opposite
    removed = {
        tuple(sorted((a, b, c))),
        tuple(sorted((a, b, d))),
    }
    if not removed <= faces:
        raise ValueError(f"invalid replay flip {edge} / {opposite}")
    return frozenset(
        (set(faces) - removed)
        | {
            tuple(sorted((c, d, a))),
            tuple(sorted((c, d, b))),
        }
    )


def force_flip(points: np.ndarray, edge: Edge, opposite: Edge, fraction: float) -> np.ndarray:
    a, b = edge
    c, d = opposite
    result = points.copy()

    def unit(row: np.ndarray) -> np.ndarray:
        return row / np.linalg.norm(row)

    result[c] = unit((1.0 - fraction) * points[c] + fraction * points[d])
    result[d] = unit((1.0 - fraction) * points[d] + fraction * points[c])
    result[a] = unit((1.0 + fraction) * points[a] - fraction * points[b])
    result[b] = unit((1.0 + fraction) * points[b] - fraction * points[a])
    return normalize(result)


def split(points: np.ndarray, faces: frozenset[Face]) -> np.ndarray:
    edges, _, _ = graph_data(faces, 72)
    midpoints = []
    for a, b in sorted(edges):
        midpoint = points[a] + points[b]
        midpoints.append(midpoint / np.linalg.norm(midpoint))
    result = normalize(np.vstack((points, np.asarray(midpoints))))
    if result.shape != (282, 3):
        raise ValueError("split shape mismatch")
    return result


def topology(points: np.ndarray) -> dict[str, object]:
    faces = faces_from_points(points)
    edges, degrees, graph = graph_data(faces, points.shape[0])
    return {
        "face_count": len(faces),
        "edge_count": len(edges),
        "degree_histogram": {
            str(key): int(value) for key, value in sorted(Counter(degrees).items())
        },
        "wl_hash": nx.weisfeiler_lehman_graph_hash(graph, iterations=20),
        "faces_sha256": faces_hash(faces),
    }


def energy(points: np.ndarray) -> float:
    differences = points[:, None, :] - points[None, :, :]
    distances = np.linalg.norm(differences, axis=2)
    np.fill_diagonal(distances, np.inf)
    return float(np.triu(1.0 / distances, 1).sum())


def load_evaluate():
    if sha256(VERIFIER) != VERIFIER_SHA256:
        raise ValueError("frozen verifier hash mismatch")
    spec = importlib.util.spec_from_file_location("independent_frozen_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate


def write_once(path: Path, value: object) -> str:
    payload = (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode()
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
    summary_path = run / "summary.json"
    receipt_path = run / "receipt.json"
    events_path = run / "events.jsonl"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    events = [json.loads(line) for line in events_path.read_text().splitlines()]

    if events[-1]["event"] != "complete":
        raise ValueError("run has no terminal completion event")
    if sha256(summary_path) != receipt["summary_sha256"]:
        raise ValueError("summary hash mismatch")
    if sha256(receipt_path) != events[-1]["receipt_sha256"]:
        raise ValueError("receipt hash mismatch")

    source_path = run / "sources/72.xyz"
    if sha256(source_path) != summary["n72_source_sha256"]:
        raise ValueError("N=72 source hash mismatch")
    source = parse_xyz(source_path)
    source_faces = faces_from_points(source)

    topology_events = [event for event in events if event["event"] == "topology_class"]
    topology_hashes: list[str] = []
    topology_wl_hashes: list[str] = []
    class_payloads: dict[int, dict[str, object]] = {}
    for event in topology_events:
        artifact = Path(event["artifact"])
        if sha256(artifact) != event["artifact_sha256"]:
            raise ValueError(f"class artifact hash mismatch: {artifact}")
        payload = json.loads(artifact.read_text())
        class_id = int(payload["class_id"])
        class_payloads[class_id] = payload
        faces = frozenset(tuple(int(value) for value in face) for face in payload["faces"])
        replayed = source_faces
        for move in payload["path"]:
            replayed = apply_flip(
                replayed,
                tuple(int(value) for value in move["edge"]),
                tuple(int(value) for value in move["opposite"]),
            )
        if replayed != faces:
            raise ValueError(f"class {class_id} path does not replay")
        edges, degrees, graph = graph_data(faces, 72)
        if len(faces) != 140 or len(edges) != 210:
            raise ValueError(f"class {class_id} Euler counts fail")
        if Counter(degrees) != Counter({5: 12, 6: 60}):
            raise ValueError(f"class {class_id} defect multiset fails")
        if faces_hash(faces) != payload["faces_sha256"]:
            raise ValueError(f"class {class_id} face hash fails")
        wl_hash = nx.weisfeiler_lehman_graph_hash(graph, iterations=20)
        if wl_hash != payload["wl_hash"]:
            raise ValueError(f"class {class_id} WL hash fails")
        topology_hashes.append(payload["faces_sha256"])
        topology_wl_hashes.append(wl_hash)

    if len(set(topology_hashes)) != len(topology_events):
        raise ValueError("duplicate labelled class")
    # Different WL hashes are a certificate of non-isomorphism.
    if len(set(topology_wl_hashes)) != len(topology_events):
        raise ValueError("class set is not pairwise WL-distinct")

    evaluate = load_evaluate()
    trial_events = [event for event in events if event["event"] == "trial"]
    replayed_scores: list[float] = []
    replayed_initial_wl: list[str] = []
    replayed_final_wl: list[str] = []
    total_candidate_bytes = 0
    for event in trial_events:
        class_payload = class_payloads[int(event["class_id"])]
        faces = frozenset(
            tuple(int(value) for value in face) for face in class_payload["faces"]
        )
        small = source.copy()
        fraction = float(event["force_fraction"])
        for move in class_payload["path"]:
            small = force_flip(
                small,
                tuple(int(value) for value in move["edge"]),
                tuple(int(value) for value in move["opposite"]),
                fraction,
            )
        initial = split(small, faces)
        initial_topology = topology(initial)
        if initial_topology["wl_hash"] != event["initial_topology"]["wl_hash"]:
            raise ValueError(f"trial {event['trial']} initial topology mismatch")
        if abs(energy(initial) - float(event["raw_energy"])) > 2e-9:
            raise ValueError(f"trial {event['trial']} raw energy mismatch")
        replayed_initial_wl.append(str(initial_topology["wl_hash"]))

        candidate_path = Path(event["candidate"])
        if sha256(candidate_path) != event["candidate_sha256"]:
            raise ValueError(f"trial {event['trial']} candidate hash mismatch")
        total_candidate_bytes += candidate_path.stat().st_size
        candidate = json.loads(candidate_path.read_text())
        points = np.asarray(candidate["vectors"], dtype=np.float64)
        if points.shape != (282, 3) or not np.isfinite(points).all():
            raise ValueError(f"trial {event['trial']} domain mismatch")
        score = float(evaluate(candidate))
        if score != float(event["official_verifier_score"]):
            raise ValueError(f"trial {event['trial']} verifier mismatch")
        final_topology = topology(normalize(points))
        if final_topology["wl_hash"] != event["final_topology"]["wl_hash"]:
            raise ValueError(f"trial {event['trial']} final topology mismatch")
        replayed_final_wl.append(str(final_topology["wl_hash"]))
        replayed_scores.append(score)

    best_path = Path(summary["best_any"]["path"])
    if sha256(best_path) != summary["best_any"]["sha256"]:
        raise ValueError("best candidate hash mismatch")
    best_candidate = json.loads(best_path.read_text())
    best_score = float(evaluate(best_candidate))
    if best_score != min(replayed_scores) or best_score != summary["best_any"]["score"]:
        raise ValueError("best score mismatch")
    best_points = np.asarray(best_candidate["vectors"], dtype=np.float64)
    norms = np.linalg.norm(best_points, axis=1)

    result = {
        "status": "pass",
        "run": str(run),
        "verifier_sha256": VERIFIER_SHA256,
        "summary_sha256": sha256(summary_path),
        "receipt_sha256": sha256(receipt_path),
        "events_sha256": sha256(events_path),
        "n72_source_sha256": sha256(source_path),
        "topology_class_count": len(topology_events),
        "pairwise_wl_distinct_class_count": len(set(topology_wl_hashes)),
        "trial_count": len(trial_events),
        "unique_replayed_initial_topology_count": len(set(replayed_initial_wl)),
        "unique_replayed_final_topology_count": len(set(replayed_final_wl)),
        "total_candidate_bytes_hashed": total_candidate_bytes,
        "official_verifier_score": best_score,
        "target_strictly_below": summary["target_strictly_below"],
        "gate_gap": best_score - float(summary["target_strictly_below"]),
        "gate_clearing": best_score < float(summary["target_strictly_below"]),
        "best_candidate_sha256": sha256(best_path),
        "domain": {
            "shape": list(best_points.shape),
            "finite": bool(np.isfinite(best_points).all()),
            "norm_min": float(norms.min()),
            "norm_max": float(norms.max()),
        },
    }
    output = run / "independent_replay.json"
    output_sha = write_once(output, result)
    print(json.dumps({**result, "independent_replay_sha256": output_sha}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
