#!/usr/bin/env python3
"""Graph-aware clean-room recombination of retained geometry constructions.

The script never averages coordinate vectors.  It transfers whole graph
neighborhoods, splices low-contact cuts, and releases/promotes several contacts
at once.  Candidate centers are repaired with the applicable exact radii LP,
polished with the existing clean-room active-set SLP, and finally evaluated by
the SHA-pinned local Arena verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import networkx as nx
import numpy as np
from scipy.optimize import minimize


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
GEOMETRY = CAMPAIGN / "geometry"
ASSETS = CAMPAIGN / "literature_asset_hunt"
CORPUS = CAMPAIGN / "research_corpus" / "snapshots" / "20260815T003306Z" / "corpus.sqlite3"
CORPUS_SHA256 = "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"

sys.path.insert(0, str(GEOMETRY))
sys.path.insert(0, str(GEOMETRY / "circle_packing_topology"))
import circle_packing_search as circle_lp  # noqa: E402
import void_relocate as circle_active  # noqa: E402

sys.path.insert(0, str(GEOMETRY / "rectangle_topology"))
import core as rectangle_active  # noqa: E402


LANES = {
    "circle-packing": {
        "count": 26,
        "direction": "max",
        "leader": 2.635983095260844,
        "target": 2.635983095360844,
        "pair_budget": 58,
        "wall_budget": 20,
        "verifier": CAMPAIGN
        / "state/problems/circle-packing/2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab.py",
        "verifier_sha256": "2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab",
    },
    "circles-rectangle": {
        "count": 21,
        "direction": "max",
        "leader": 2.365832385207997,
        "target": 2.365832385307997,
        "pair_budget": 47,
        "wall_budget": 17,
        "verifier": CAMPAIGN
        / "state/problems/circles-rectangle/c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9.py",
        "verifier_sha256": "c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9",
    },
    "min-distance-ratio-2d": {
        "count": 16,
        "direction": "min",
        "leader": 12.8892299077175,
        "target": 12.8892298077175,
        "minimum_budget": 22,
        "maximum_budget": 8,
        "verifier": CAMPAIGN
        / "state/problems/min-distance-ratio-2d/2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad.py",
        "verifier_sha256": "2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad",
    },
}


@dataclass
class Source:
    name: str
    values: np.ndarray
    score_hint: float
    width: float | None = None


@dataclass
class Seed:
    signature: str
    exact_signature: str
    method: str
    host: str
    donor: str
    values: np.ndarray
    score: float
    width: float | None
    metadata: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_verifier(lane: str):
    config = LANES[lane]
    path = Path(config["verifier"])
    actual = sha256_file(path)
    if actual != config["verifier_sha256"]:
        raise RuntimeError(f"verifier hash mismatch: {actual}")
    name = "frozen_" + lane.replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load verifier {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.evaluate


def raw_hash(array: np.ndarray, width: float | None = None) -> str:
    rounded = np.round(np.asarray(array, dtype=float), 13).tolist()
    raw = json.dumps([rounded, None if width is None else round(width, 13)], separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def normalize_rectangle(circles: np.ndarray) -> tuple[np.ndarray, float]:
    normalized, width, height = rectangle_active.normalize_origin(circles)
    scale = 2.0 / (width + height)
    normalized = normalized.copy()
    normalized[:, :2] *= scale
    normalized[:, 2] *= scale
    return rectangle_active.normalize_origin(normalized)[0], width * scale


def normalize_min_points(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=float)
    centered = points - np.mean(points, axis=0)
    covariance = centered.T @ centered
    _, vectors = np.linalg.eigh(covariance)
    centered = centered @ vectors[:, ::-1]
    diameter = max(
        np.linalg.norm(centered[i] - centered[j])
        for i in range(len(centered))
        for j in range(i + 1, len(centered))
    )
    if diameter <= 1e-15:
        raise ValueError("degenerate point source")
    return centered / diameter


def load_sources(lane: str) -> list[Source]:
    key = "circles" if lane != "min-distance-ratio-2d" else "vectors"
    connection = sqlite3.connect(CORPUS)
    rows = connection.execute(
        """
        SELECT s.id, s.agent_name, s.score, s.record_json
        FROM solutions s JOIN problems p ON p.id=s.problem_id
        WHERE p.slug=?
        """,
        (lane,),
    ).fetchall()
    connection.close()
    sources: list[Source] = []
    for solution_id, agent, score, record_text in rows:
        data = json.loads(record_text)["data"]
        array = np.asarray(data[key], dtype=float)
        if lane == "circles-rectangle":
            array, width = normalize_rectangle(array)
        elif lane == "min-distance-ratio-2d":
            array, width = normalize_min_points(array), None
        else:
            width = None
        sources.append(Source(f"corpus:{solution_id}:{agent}", array, float(score), width))

    receipt = json.loads((ASSETS / "receipt.json").read_text())
    for source_record in receipt["sources"]:
        if source_record.get("slug") != lane:
            continue
        for candidate in source_record["candidates"]:
            payload = json.loads(Path(candidate["payload_path"]).read_text())
            array = np.asarray(payload[key], dtype=float)
            if lane == "circles-rectangle":
                array, width = normalize_rectangle(array)
            elif lane == "min-distance-ratio-2d":
                array, width = normalize_min_points(array), None
            else:
                width = None
            score = candidate["score"]
            score_hint = float(score) if isinstance(score, (int, float)) else 1e100
            sources.append(Source(f"asset:{source_record['id']}:{candidate['name']}", array, score_hint, width))

    patterns: list[Path] = []
    if lane == "circle-packing":
        patterns.extend(
            sorted((GEOMETRY / "circle_packing_topology/runs/20260815T021013Z/topologies").glob("*/candidate.json"))
        )
        patterns.extend(
            sorted((GEOMETRY / "circle_packing_topology/runs/20260815T020538Z/topologies").glob("*/candidate.json"))[:80]
        )
    elif lane == "circles-rectangle":
        patterns.extend(
            sorted((GEOMETRY / "rectangle_topology/runs/20260815T022200Z/stochastic_relax/topologies").glob("*/candidate.json"))
        )
        patterns.extend(
            sorted((GEOMETRY / "rectangle_topology/runs/20260815T022100Z/void_relocate/topologies").glob("*/candidate.json"))
        )
    else:
        patterns.extend(sorted((GEOMETRY / "runs").glob("*/min-distance-ratio-2d/best.json")))
    for path in patterns:
        payload = json.loads(path.read_text())
        array = np.asarray(payload[key], dtype=float)
        if lane == "circles-rectangle":
            array, width = normalize_rectangle(array)
            score = float(np.sum(array[:, 2]))
        elif lane == "min-distance-ratio-2d":
            array, width = normalize_min_points(array), None
            score = min_distance_score(array)
        else:
            width = None
            score = float(np.sum(array[:, 2]))
        sources.append(Source(f"local:{path.relative_to(CAMPAIGN)}", array, score, width))

    expected = int(LANES[lane]["count"])
    deduplicated: dict[str, Source] = {}
    for source in sources:
        if source.values.shape[0] != expected or not np.isfinite(source.values).all():
            continue
        signature = raw_hash(source.values, source.width)
        previous = deduplicated.get(signature)
        if previous is None:
            deduplicated[signature] = source
        elif lane == "min-distance-ratio-2d" and source.score_hint < previous.score_hint:
            deduplicated[signature] = source
        elif lane != "min-distance-ratio-2d" and source.score_hint > previous.score_hint:
            deduplicated[signature] = source
    reverse = lane != "min-distance-ratio-2d"
    return sorted(deduplicated.values(), key=lambda item: item.score_hint, reverse=reverse)


def d4(points: np.ndarray, code: int) -> np.ndarray:
    result = np.asarray(points, dtype=float).copy()
    if code >= 4:
        result[:, 0] = 1.0 - result[:, 0]
    for _ in range(code % 4):
        result = np.column_stack((1.0 - result[:, 1], result[:, 0]))
    return result


def source_unit_coordinates(source: Source, lane: str) -> np.ndarray:
    if lane == "circle-packing":
        return np.clip(source.values[:, :2], 0.0, 1.0)
    if lane == "circles-rectangle":
        width = float(source.width)
        return np.clip(
            np.column_stack((source.values[:, 0] / width, source.values[:, 1] / (2.0 - width))),
            0.0,
            1.0,
        )
    points = normalize_min_points(source.values)
    span = float(np.max(np.ptp(points, axis=0)))
    return np.clip(points / max(span, 1e-12) + 0.5, 0.0, 1.0)


def ranked_pair_edges(points: np.ndarray, budget: int, radii: np.ndarray | None = None) -> list[tuple[int, int]]:
    ranked = []
    for first in range(len(points)):
        for second in range(first + 1, len(points)):
            distance = float(np.linalg.norm(points[first] - points[second]))
            if radii is None:
                value = distance
            else:
                value = distance - float(radii[first] + radii[second])
            ranked.append((value, first, second))
    ranked.sort()
    return [(first, second) for _, first, second in ranked[:budget]]


def bfs_module(
    count: int,
    edges: Iterable[tuple[int, int]],
    coordinates: np.ndarray,
    start: int,
    requested: int,
) -> list[int]:
    adjacency = {index: set() for index in range(count)}
    for first, second in edges:
        adjacency[first].add(second)
        adjacency[second].add(first)
    selected = [start]
    seen = {start}
    cursor = 0
    while cursor < len(selected) and len(selected) < requested:
        current = selected[cursor]
        cursor += 1
        for neighbor in sorted(adjacency[current]):
            if neighbor not in seen:
                seen.add(neighbor)
                selected.append(neighbor)
                if len(selected) == requested:
                    break
    if len(selected) < requested:
        remaining = sorted(
            (index for index in range(count) if index not in seen),
            key=lambda index: float(np.linalg.norm(coordinates[index] - coordinates[start])),
        )
        selected.extend(remaining[: requested - len(selected)])
    return selected


def packing_graph_signature(
    circles: np.ndarray,
    width: float,
    pair_budget: int,
    wall_budget: int,
    exact_tolerance: float | None = None,
) -> str:
    count = len(circles)
    centers, radii = circles[:, :2], circles[:, 2]
    height = 2.0 - width
    graph = nx.Graph()
    for index in range(count):
        graph.add_node(index, label="circle")
    walls = [count + offset for offset in range(4)]
    for wall in walls:
        graph.add_node(wall, label="wall")
    for offset in range(4):
        graph.add_edge(walls[offset], walls[(offset + 1) % 4], kind="frame")

    pair_rows = []
    for first in range(count):
        for second in range(first + 1, count):
            slack = float(np.linalg.norm(centers[first] - centers[second]) - radii[first] - radii[second])
            pair_rows.append((slack, first, second))
    pair_rows.sort()
    if exact_tolerance is None:
        selected_pairs = pair_rows[:pair_budget]
    else:
        selected_pairs = [row for row in pair_rows if row[0] <= exact_tolerance]
    for _, first, second in selected_pairs:
        graph.add_edge(first, second, kind="contact")

    wall_rows = []
    for index, (x, y, radius) in enumerate(circles):
        wall_rows.extend(
            [
                (float(x - radius), index, walls[0]),
                (float(width - x - radius), index, walls[1]),
                (float(y - radius), index, walls[2]),
                (float(height - y - radius), index, walls[3]),
            ]
        )
    wall_rows.sort()
    if exact_tolerance is None:
        selected_walls = wall_rows[:wall_budget]
    else:
        selected_walls = [row for row in wall_rows if row[0] <= exact_tolerance]
    for _, index, wall in selected_walls:
        graph.add_edge(index, wall, kind="contact")
    digest = nx.weisfeiler_lehman_graph_hash(graph, node_attr="label", edge_attr="kind", iterations=8)
    degrees = sorted(dict(graph.degree()).values())
    return hashlib.sha256(json.dumps([digest, degrees, graph.number_of_edges()]).encode()).hexdigest()


def min_graph_signature(points: np.ndarray, exact_tolerance: float | None = None) -> str:
    count = len(points)
    rows = sorted(
        (float(np.linalg.norm(points[first] - points[second])), first, second)
        for first in range(count)
        for second in range(first + 1, count)
    )
    minimum, maximum = rows[0][0], rows[-1][0]
    if exact_tolerance is None:
        minimum_rows = rows[: int(LANES["min-distance-ratio-2d"]["minimum_budget"])]
        maximum_rows = rows[-int(LANES["min-distance-ratio-2d"]["maximum_budget"]) :]
    else:
        minimum_rows = [row for row in rows if row[0] <= minimum * (1 + exact_tolerance)]
        maximum_rows = [row for row in rows if row[0] >= maximum * (1 - exact_tolerance)]
    graph = nx.Graph()
    for index in range(count):
        graph.add_node(index, label="point")
    for _, first, second in minimum_rows:
        graph.add_edge(first, second, kind="minimum")
    for _, first, second in maximum_rows:
        graph.add_edge(first, second, kind="maximum")
    digest = nx.weisfeiler_lehman_graph_hash(graph, node_attr="label", edge_attr="kind", iterations=8)
    edge_degrees = sorted((graph.degree(index),) for index in graph.nodes)
    return hashlib.sha256(json.dumps([digest, edge_degrees, len(minimum_rows), len(maximum_rows)]).encode()).hexdigest()


def farthest_subset(points: np.ndarray, count: int) -> np.ndarray:
    if len(points) <= count:
        return points.copy()
    center = np.mean(points, axis=0)
    selected = [int(np.argmax(np.linalg.norm(points - center, axis=1)))]
    distances = np.linalg.norm(points - points[selected[0]], axis=1)
    while len(selected) < count:
        index = int(np.argmax(distances))
        selected.append(index)
        distances = np.minimum(distances, np.linalg.norm(points - points[index], axis=1))
        distances[selected] = -1
    return points[selected]


def source_edges(source: Source, lane: str) -> list[tuple[int, int]]:
    count = int(LANES[lane]["count"])
    if lane == "circle-packing":
        return ranked_pair_edges(source.values[:, :2], int(LANES[lane]["pair_budget"]), source.values[:, 2])
    if lane == "circles-rectangle":
        return ranked_pair_edges(source.values[:, :2], int(LANES[lane]["pair_budget"]), source.values[:, 2])
    return ranked_pair_edges(source.values, int(LANES[lane]["minimum_budget"]))


def recombine_units(
    host: Source,
    donor: Source,
    lane: str,
    rng: np.random.Generator,
) -> tuple[np.ndarray, str, dict[str, Any]]:
    count = int(LANES[lane]["count"])
    host_units = source_unit_coordinates(host, lane)
    donor_units = d4(source_unit_coordinates(donor, lane), int(rng.integers(0, 8)))
    method_roll = float(rng.random())
    metadata: dict[str, Any] = {}
    if method_roll < 0.68:
        requested = int(rng.integers(2, min(9, count // 2) + 1))
        donor_start = int(rng.integers(0, count))
        host_start = int(rng.integers(0, count))
        donor_module = bfs_module(count, source_edges(donor, lane), donor_units, donor_start, requested)
        host_module = bfs_module(count, source_edges(host, lane), host_units, host_start, requested)
        donor_block = donor_units[donor_module]
        host_block = host_units[host_module]
        donor_center = np.mean(donor_block, axis=0)
        host_center = np.mean(host_block, axis=0)
        donor_radius = math.sqrt(float(np.mean(np.sum((donor_block - donor_center) ** 2, axis=1))))
        host_radius = math.sqrt(float(np.mean(np.sum((host_block - host_center) ** 2, axis=1))))
        scale = (host_radius / max(donor_radius, 1e-8)) * float(rng.uniform(0.82, 1.18))
        transplanted = host_center + scale * (donor_block - donor_center)
        output = host_units.copy()
        donor_order = np.argsort(np.arctan2(*(donor_block - donor_center)[:, ::-1].T))
        host_order = np.argsort(np.arctan2(*(host_block - host_center)[:, ::-1].T))
        for donor_position, host_position in zip(donor_order, host_order):
            output[host_module[int(host_position)]] = transplanted[int(donor_position)]
        method = "graph_module_transplant"
        metadata.update(module_size=requested, donor_module=donor_module, host_module=host_module)
    else:
        angle = float(rng.choice(np.arange(8) * math.pi / 8))
        direction = np.asarray([math.cos(angle), math.sin(angle)])
        threshold = float(rng.uniform(0.35, 0.65))
        host_projection = host_units @ direction
        donor_projection = donor_units @ direction
        candidates = np.vstack(
            (
                host_units[host_projection <= np.quantile(host_projection, threshold)],
                donor_units[donor_projection > np.quantile(donor_projection, threshold)],
            )
        )
        output = farthest_subset(candidates, count)
        if len(output) < count:
            output = farthest_subset(np.vstack((output, host_units, donor_units)), count)
        method = "low_contact_cut_splice"
        metadata.update(angle=angle, cut_quantile=threshold)

    output = np.clip(output, 2e-5, 1 - 2e-5)
    # A simultaneous release/promotion move: several short edges are opened
    # while the nearest non-selected cross edges are closed.  This deliberately
    # crosses a multi-contact branch rather than performing a one-edge flip.
    all_edges = ranked_pair_edges(output, count * (count - 1) // 2)
    release_count = int(rng.integers(2, 6))
    chosen = all_edges[: max(release_count, min(2 * count, len(all_edges)))]
    chosen = [chosen[int(index)] for index in rng.choice(len(chosen), size=release_count, replace=False)]
    step = float(10 ** rng.uniform(-3.0, -1.55))
    for first, second in chosen:
        delta = output[first] - output[second]
        norm = max(float(np.linalg.norm(delta)), 1e-12)
        direction = delta / norm
        output[first] += 0.5 * step * direction
        output[second] -= 0.5 * step * direction
    selected_set = {tuple(sorted(edge)) for edge in chosen}
    promote_pool = [edge for edge in all_edges[release_count:] if tuple(sorted(edge)) not in selected_set]
    promote_count = min(release_count - 1, len(promote_pool))
    for first, second in promote_pool[:promote_count]:
        delta = output[first] - output[second]
        norm = max(float(np.linalg.norm(delta)), 1e-12)
        direction = delta / norm
        output[first] -= 0.18 * step * direction
        output[second] += 0.18 * step * direction
    output = np.clip(output, 2e-5, 1 - 2e-5)
    metadata.update(released_edges=chosen, promoted_edges=promote_pool[:promote_count], release_step=step)
    return output, method + "+multi_contact_release", metadata


def choose_rectangle_width(host: Source, donor: Source, rng: np.random.Generator) -> float:
    host_width, donor_width = float(host.width), float(donor.width)
    choice = int(rng.integers(0, 4))
    if choice == 0:
        return host_width
    if choice == 1:
        return donor_width
    if choice == 2:
        host_aspect = host_width / (2 - host_width)
        donor_aspect = donor_width / (2 - donor_width)
        aspect = math.sqrt(host_aspect * donor_aspect)
        return 2 * aspect / (1 + aspect)
    return float(np.clip(0.5 * (host_width + donor_width) + rng.normal(0, 0.008), 0.8, 1.2))


def units_to_centers(units: np.ndarray, lane: str, width: float | None) -> np.ndarray:
    if lane == "circle-packing":
        return units.copy()
    if lane == "circles-rectangle":
        assert width is not None
        return np.column_stack((units[:, 0] * width, units[:, 1] * (2 - width)))
    centered = units - np.mean(units, axis=0)
    return centered / max(float(np.max(np.ptp(centered, axis=0))), 1e-12)


def min_distance_score(points: np.ndarray) -> float:
    distances = [
        float(np.linalg.norm(points[first] - points[second]))
        for first in range(len(points))
        for second in range(first + 1, len(points))
    ]
    return (max(distances) / min(distances)) ** 2 if min(distances) > 1e-12 else 1e100


def repair_seed(
    lane: str,
    units: np.ndarray,
    width: float | None,
) -> tuple[np.ndarray, float, float | None] | None:
    centers = units_to_centers(units, lane, width)
    if lane == "circle-packing":
        circles = circle_lp.strict_repair(centers, 2e-12)
        if circles is None:
            return None
        return circles, float(np.sum(circles[:, 2])), None
    if lane == "circles-rectangle":
        assert width is not None
        repaired = rectangle_active.strict_repair(centers, width, 2e-12)
        if repaired is None:
            return None
        circles, repaired_width = repaired
        return circles, float(np.sum(circles[:, 2])), repaired_width
    points = normalize_min_points(centers)
    return points, min_distance_score(points), None


class AnchoredMinProblem:
    def __init__(self, count: int, anchor: tuple[int, int]):
        self.count = count
        self.anchor = anchor
        self.free = [index for index in range(count) if index not in anchor]
        self.offset = {index: 2 * position for position, index in enumerate(self.free)}
        self.score_id = 2 * len(self.free)
        self.pairs = [(i, j) for i in range(count) for j in range(i + 1, count) if (i, j) != anchor]

    def unpack(self, variables: np.ndarray) -> tuple[np.ndarray, float]:
        points = np.empty((self.count, 2))
        first, second = self.anchor
        points[first] = [0.0, 0.0]
        points[second] = [1.0, 0.0]
        points[self.free] = variables[: self.score_id].reshape(-1, 2)
        return points, float(variables[-1])

    def pack(self, points: np.ndarray) -> np.ndarray:
        score = min_distance_score(points)
        return np.concatenate((points[self.free].reshape(-1), [score]))

    def constraints(self, variables: np.ndarray) -> np.ndarray:
        points, score = self.unpack(variables)
        squared = np.asarray([np.sum((points[i] - points[j]) ** 2) for i, j in self.pairs])
        return np.concatenate((squared - 1, score - squared))

    def jacobian(self, variables: np.ndarray) -> np.ndarray:
        points, _ = self.unpack(variables)
        pair_count = len(self.pairs)
        jacobian = np.zeros((2 * pair_count, self.score_id + 1))
        for row, (first, second) in enumerate(self.pairs):
            gradient = 2 * (points[first] - points[second])
            if first in self.offset:
                offset = self.offset[first]
                jacobian[row, offset : offset + 2] = gradient
                jacobian[pair_count + row, offset : offset + 2] = -gradient
            if second in self.offset:
                offset = self.offset[second]
                jacobian[row, offset : offset + 2] = -gradient
                jacobian[pair_count + row, offset : offset + 2] = gradient
            jacobian[pair_count + row, -1] = 1
        return jacobian

    def selected(self, variables: np.ndarray, edges: tuple[tuple[int, int], ...], bound: float) -> np.ndarray:
        points, _ = self.unpack(variables)
        return np.asarray([np.sum((points[i] - points[j]) ** 2) - bound for i, j in edges])


def anchor_min_points(points: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
    rows = sorted(
        (float(np.linalg.norm(points[first] - points[second])), first, second)
        for first in range(len(points))
        for second in range(first + 1, len(points))
    )
    distance, first, second = rows[0]
    centered = points - points[first]
    delta = centered[second]
    cosine, sine = delta[0] / distance, delta[1] / distance
    rotation = np.asarray([[cosine, sine], [-sine, cosine]])
    return centered @ rotation.T / distance, (first, second)


def polish_min(points: np.ndarray, maxiter: int) -> tuple[np.ndarray, dict[str, Any]]:
    anchored, anchor = anchor_min_points(points)
    model = AnchoredMinProblem(len(points), anchor)
    initial = model.pack(anchored)
    shortest = ranked_pair_edges(anchored, 10)
    released = tuple(edge for edge in shortest if edge != anchor)[: int(min(4, len(shortest) - 1))]
    constraints: list[dict[str, Any]] = [
        {"type": "ineq", "fun": model.constraints, "jac": model.jacobian}
    ]
    if released:
        constraints.append(
            {
                "type": "ineq",
                "fun": lambda values: model.selected(values, released, (1.0025) ** 2),
            }
        )
    objective_jacobian = np.zeros_like(initial)
    objective_jacobian[-1] = 1
    bounds = [(-7.0, 7.0)] * model.score_id + [(1.0, 30.0)]
    forced = minimize(
        lambda values: values[-1],
        initial,
        jac=lambda _values: objective_jacobian,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": max(80, maxiter // 3), "ftol": 1e-11, "disp": False},
    )
    start = forced.x if np.isfinite(forced.x).all() else initial
    free = minimize(
        lambda values: values[-1],
        start,
        jac=lambda _values: objective_jacobian,
        method="SLSQP",
        bounds=bounds,
        constraints=[{"type": "ineq", "fun": model.constraints, "jac": model.jacobian}],
        options={"maxiter": maxiter, "ftol": 1e-12, "disp": False},
    )
    result_points, _ = model.unpack(free.x)
    return result_points, {
        "anchor": anchor,
        "released": released,
        "forced_success": bool(forced.success),
        "free_success": bool(free.success),
        "forced_iterations": int(forced.nit),
        "free_iterations": int(free.nit),
    }


def literal_score(lane: str, evaluate, values: np.ndarray) -> float:
    key = "vectors" if lane == "min-distance-ratio-2d" else "circles"
    try:
        return float(evaluate({key: values.tolist()}))
    except Exception:
        return 1e100 if lane == "min-distance-ratio-2d" else -1e100


def gate_clear(lane: str, score: float) -> bool:
    target = float(LANES[lane]["target"])
    return score < target if lane == "min-distance-ratio-2d" else score > target


def select_for_polish(seeds: list[Seed], count: int, rng: np.random.Generator, lane: str) -> list[Seed]:
    reverse = lane != "min-distance-ratio-2d"
    ordered = sorted(seeds, key=lambda seed: seed.score, reverse=reverse)
    elite_count = min(len(ordered), max(1, int(0.72 * count)))
    selected = ordered[:elite_count]
    remaining = ordered[elite_count:]
    if remaining and len(selected) < count:
        indices = rng.choice(len(remaining), size=min(count - len(selected), len(remaining)), replace=False)
        selected.extend(remaining[int(index)] for index in indices)
    return selected


def run_lane(args: argparse.Namespace) -> dict[str, Any]:
    lane = args.lane
    config = LANES[lane]
    if sha256_file(CORPUS) != CORPUS_SHA256:
        raise RuntimeError("corpus hash mismatch")
    evaluate = load_verifier(lane)
    rng = np.random.default_rng(args.rng_seed)
    sources = load_sources(lane)
    if len(sources) < 2:
        raise RuntimeError("need at least two sources")
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = HERE / "runs" / stamp / lane
    run_dir.mkdir(parents=True, exist_ok=False)
    catalog_path = run_dir / "seed_catalog.jsonl"
    events_path = run_dir / "events.jsonl"
    started = time.monotonic()
    deadline = started + args.time_limit_seconds
    source_manifest = [
        {
            "name": source.name,
            "score_hint": source.score_hint,
            "width": source.width,
            "payload_hash": raw_hash(source.values, source.width),
        }
        for source in sources
    ]
    atomic_json(run_dir / "sources.json", source_manifest)
    atomic_json(
        run_dir / "config.json",
        {
            "lane": lane,
            "rng_seed": args.rng_seed,
            "target_signatures": args.target_signatures,
            "attempt_limit": args.attempt_limit,
            "polish_count": args.polish_count,
            "slp_rounds": args.slp_rounds,
            "time_limit_seconds": args.time_limit_seconds,
            "leader": config["leader"],
            "target": config["target"],
            "verifier_sha256": config["verifier_sha256"],
            "corpus_sha256": CORPUS_SHA256,
            "asset_receipt_sha256": sha256_file(ASSETS / "receipt.json"),
            "methods": ["graph_module_transplant", "low_contact_cut_splice", "multi_contact_release"],
        },
    )

    signatures: set[str] = set()
    exact_signatures: set[str] = set()
    seeds: list[Seed] = []
    attempts = repair_failures = duplicate_signatures = 0
    while (
        len(signatures) < args.target_signatures
        and attempts < args.attempt_limit
        and time.monotonic() < deadline
    ):
        attempts += 1
        # Bias toward the better half but keep every retained topology eligible.
        pool = min(len(sources), max(12, len(sources) // 2))
        host = sources[int(rng.integers(0, pool))] if rng.random() < 0.72 else sources[int(rng.integers(len(sources)))]
        donor = sources[int(rng.integers(len(sources)))]
        if donor.name == host.name:
            donor = sources[(sources.index(host) + 1 + int(rng.integers(len(sources) - 1))) % len(sources)]
        units, method, metadata = recombine_units(host, donor, lane, rng)
        width = choose_rectangle_width(host, donor, rng) if lane == "circles-rectangle" else None
        repaired = repair_seed(lane, units, width)
        if repaired is None:
            repair_failures += 1
            continue
        values, score, repaired_width = repaired
        if lane == "circle-packing":
            signature = packing_graph_signature(
                values, 1.0, int(config["pair_budget"]), int(config["wall_budget"])
            )
            exact_signature = packing_graph_signature(
                values, 1.0, int(config["pair_budget"]), int(config["wall_budget"]), 2e-7
            )
        elif lane == "circles-rectangle":
            signature = packing_graph_signature(
                values,
                float(repaired_width),
                int(config["pair_budget"]),
                int(config["wall_budget"]),
            )
            exact_signature = packing_graph_signature(
                values,
                float(repaired_width),
                int(config["pair_budget"]),
                int(config["wall_budget"]),
                2e-7,
            )
        else:
            signature = min_graph_signature(values)
            exact_signature = min_graph_signature(values, 1e-3)
        if signature in signatures:
            duplicate_signatures += 1
            continue
        signatures.add(signature)
        exact_signatures.add(exact_signature)
        seed = Seed(signature, exact_signature, method, host.name, donor.name, values, score, repaired_width, metadata)
        seeds.append(seed)
        append_jsonl(
            catalog_path,
            {
                "index": len(seeds) - 1,
                "signature": signature,
                "exact_signature": exact_signature,
                "method": method,
                "host": host.name,
                "donor": donor.name,
                "score": score,
                "width": repaired_width,
                "metadata": metadata,
                "values": values.tolist(),
            },
        )
        if len(seeds) % 50 == 0:
            atomic_json(
                run_dir / "checkpoint.json",
                {
                    "phase": "generation",
                    "attempts": attempts,
                    "ranked_contact_signatures": len(signatures),
                    "threshold_contact_signatures": len(exact_signatures),
                    "elapsed_seconds": time.monotonic() - started,
                },
            )

    selected = select_for_polish(seeds, args.polish_count, rng, lane)
    best_score = float(config["leader"])
    best_payload: Path | None = None
    best_source = "retained_leader"
    polished_signatures: set[str] = set()
    refined_signatures: set[str] = set()
    polished = refined = 0
    for polish_index, seed in enumerate(selected):
        if time.monotonic() >= deadline:
            break
        record: dict[str, Any] = {
            "event": "polish_finished",
            "polish_index": polish_index,
            "seed_signature": seed.signature,
            "method": seed.method,
            "host": seed.host,
            "donor": seed.donor,
        }
        if lane == "circle-packing":
            optimized, diagnostics = circle_active.optimize_seed(
                seed.values[:, :2],
                2e-12,
                [1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2],
                args.slp_rounds,
            )
            record["optimization"] = diagnostics
            if optimized is None:
                append_jsonl(events_path, record)
                continue
            polished += 1
            candidate = optimized
            refinement = circle_active.refine_rigid(candidate)
            record["refinement_status"] = refinement["status"]
            if refinement["status"] == "refined":
                refined += 1
                refined_signatures.add(str(refinement["signature"]))
                candidate = circle_active.values_to_circles(refinement["buffered_values"])
            score = literal_score(lane, evaluate, candidate)
            signature = packing_graph_signature(candidate, 1.0, 58, 20, 2e-7)
        elif lane == "circles-rectangle":
            optimized, diagnostics = rectangle_active.optimize_strict(
                seed.values[:, :2],
                float(seed.width),
                2e-12,
                [1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2],
                1.0,
                args.slp_rounds,
            )
            record["optimization"] = diagnostics
            if optimized is None:
                append_jsonl(events_path, record)
                continue
            polished += 1
            candidate, width = optimized
            refinement = rectangle_active.refine_rigid(candidate, width)
            record["refinement_status"] = refinement["status"]
            if refinement["status"] == "refined":
                refined += 1
                refined_signatures.add(str(refinement["signature"]))
                candidate = rectangle_active.values_to_circles(refinement["buffered_values"])
                width = float(refinement["buffered_values"][rectangle_active.WIDTH_ID])
            score = literal_score(lane, evaluate, candidate)
            signature = packing_graph_signature(candidate, width, 47, 17, 2e-7)
        else:
            candidate, diagnostics = polish_min(seed.values, args.min_maxiter)
            record["optimization"] = diagnostics
            polished += 1
            score = literal_score(lane, evaluate, candidate)
            signature = min_graph_signature(candidate, 1e-6)
        polished_signatures.add(signature)
        record.update(score=score, polished_signature=signature, clears_gate=gate_clear(lane, score))
        append_jsonl(events_path, record)

        better = score < best_score if lane == "min-distance-ratio-2d" else score > best_score
        if better:
            best_score = score
            best_source = f"polish:{polish_index}:{seed.signature}"
            best_payload = run_dir / "best.json"
            key = "vectors" if lane == "min-distance-ratio-2d" else "circles"
            atomic_json(best_payload, {key: candidate.tolist()})
            atomic_json(
                run_dir / "best_receipt.json",
                {
                    "score": score,
                    "leader": config["leader"],
                    "target": config["target"],
                    "clears_gate": gate_clear(lane, score),
                    "source": best_source,
                    "payload": str(best_payload),
                    "payload_sha256": sha256_file(best_payload),
                    "verifier_sha256": config["verifier_sha256"],
                },
            )
            if gate_clear(lane, score):
                atomic_json(run_dir / "GATE_CLEARER.json", json.loads((run_dir / "best_receipt.json").read_text()))
                break

    elapsed = time.monotonic() - started
    summary = {
        "lane": lane,
        "source_count": len(sources),
        "attempts": attempts,
        "repair_failures": repair_failures,
        "duplicate_ranked_signatures": duplicate_signatures,
        "ranked_contact_signatures": len(signatures),
        "threshold_contact_signatures": len(exact_signatures),
        "target_signatures": args.target_signatures,
        "target_reached": len(signatures) >= args.target_signatures,
        "selected_for_polish": len(selected),
        "polished": polished,
        "polished_contact_signatures": len(polished_signatures),
        "rigid_refined": refined,
        "rigid_signatures": len(refined_signatures),
        "leader": config["leader"],
        "target": config["target"],
        "best_score": best_score,
        "best_source": best_source,
        "best_payload": None if best_payload is None else str(best_payload),
        "clears_gate": gate_clear(lane, best_score),
        "elapsed_seconds": elapsed,
        "stopped_on_time_limit": time.monotonic() >= deadline,
        "verifier_sha256": config["verifier_sha256"],
        "corpus_sha256": CORPUS_SHA256,
    }
    atomic_json(run_dir / "summary.json", summary)
    atomic_json(run_dir / "checkpoint.json", {"phase": "complete", **summary})
    print(json.dumps({"run_dir": str(run_dir), **summary}, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("lane", choices=sorted(LANES))
    parser.add_argument("--target-signatures", type=int, default=520)
    parser.add_argument("--attempt-limit", type=int, default=30000)
    parser.add_argument("--polish-count", type=int, default=60)
    parser.add_argument("--slp-rounds", type=int, default=10)
    parser.add_argument("--min-maxiter", type=int, default=500)
    parser.add_argument("--time-limit-seconds", type=float, default=850.0)
    parser.add_argument("--rng-seed", type=int, default=2026081504)
    parser.add_argument("--stamp")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_lane(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
