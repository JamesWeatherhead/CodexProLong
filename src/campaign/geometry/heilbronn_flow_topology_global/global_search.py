#!/usr/bin/env python3
"""Bounded global topology search for the n=11 Heilbronn triangle problem.

This is a clean-room implementation of a FlowBoost-style search stack:

* explicit boundary/vertex topology islands;
* smooth absolute determinants and annealed soft-min optimization;
* stochastic perturbations in unconstrained barycentric coordinates;
* depth-4/6/8/11 death-and-rebirth moves; and
* a final full 165-constraint SLSQP max-min polish.

The script is deliberately offline.  It reads a frozen public snapshot and the
frozen verifier from the campaign tree, writes append-only run evidence, and
never calls an Arena or GitHub endpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

if sys.version_info < (3, 11):
    raise RuntimeError("heilbronn_flow_topology_global requires Python >= 3.11")

import numpy as np
import torch
from scipy.optimize import linear_sum_assignment, minimize
from scipy.spatial import ConvexHull, QhullError


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
SNAPSHOT = CAMPAIGN / "geometry/snapshots/heilbronn-triangles_20260814T231406Z.json"
VERIFIER = (
    CAMPAIGN
    / "state/problems/heilbronn-triangles"
    / "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d.py"
)
EXPECTED_VERIFIER_SHA256 = "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d"
COUNT = 11
SQRT3 = math.sqrt(3.0)
BOUNDING_AREA = SQRT3 / 4.0
TRIPLES = np.asarray(list(itertools.combinations(range(COUNT), 3)), dtype=np.int64)
VERTICES = np.asarray(((0.0, 0.0), (1.0, 0.0), (0.5, SQRT3 / 2.0)), dtype=np.float64)
# Edge modes are indexed by the *opposite vertex* A/B/C.  The verifier's
# domain-slack order is bottom/left/right, so the corresponding permutation is
# C/B/A.
EDGE_TO_SLACK = (2, 1, 0)
SLACK_TO_EDGE = (2, 1, 0)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_jsonl(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load_evaluate() -> object:
    source = VERIFIER.read_text(encoding="utf-8")
    actual = hashlib.sha256(source.encode()).hexdigest()
    if actual != EXPECTED_VERIFIER_SHA256:
        raise RuntimeError(f"verifier hash changed: {actual}")
    namespace: dict[str, object] = {}
    exec(compile(source, str(VERIFIER), "exec"), namespace)  # noqa: S102 - frozen local verifier
    return namespace["evaluate"]


def verifier_score(evaluate: object, points: np.ndarray) -> float:
    return float(evaluate({"points": np.asarray(points, dtype=np.float64).tolist()}))  # type: ignore[operator]


def barycentric(points: np.ndarray) -> np.ndarray:
    points = np.asarray(points, dtype=np.float64)
    c = 2.0 * points[:, 1] / SQRT3
    b = points[:, 0] - 0.5 * c
    a = 1.0 - b - c
    return np.column_stack((a, b, c))


def cartesian(weights: np.ndarray) -> np.ndarray:
    weights = np.asarray(weights, dtype=np.float64)
    return weights @ VERTICES


def signed_double_areas(points: np.ndarray) -> np.ndarray:
    p = np.asarray(points, dtype=np.float64)
    first = p[TRIPLES[:, 1]] - p[TRIPLES[:, 0]]
    second = p[TRIPLES[:, 2]] - p[TRIPLES[:, 0]]
    return first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]


def hard_score(points: np.ndarray) -> float:
    return float(np.min(np.abs(signed_double_areas(points))) / (2.0 * BOUNDING_AREA))


def domain_slacks(points: np.ndarray) -> np.ndarray:
    p = np.asarray(points, dtype=np.float64)
    return np.column_stack(
        (
            p[:, 1],
            SQRT3 * p[:, 0] - p[:, 1],
            SQRT3 - SQRT3 * p[:, 0] - p[:, 1],
        )
    )


def d3_rms_distance(first: np.ndarray, second: np.ndarray) -> float:
    """Permutation- and D3-invariant RMS matching distance."""

    first_bary = barycentric(first)
    second = np.asarray(second, dtype=np.float64)
    best = math.inf
    for permutation in itertools.permutations(range(3)):
        transformed = cartesian(first_bary[:, permutation])
        distances = np.linalg.norm(transformed[:, None, :] - second[None, :, :], axis=2)
        # RMS minimizes the sum of squared distances, not the sum of distances.
        rows, columns = linear_sum_assignment(distances * distances)
        rms = float(np.sqrt(np.mean(distances[rows, columns] ** 2)))
        best = min(best, rms)
    return best


def topology_signature(points: np.ndarray, active_tolerance: float = 1e-7) -> dict[str, object]:
    points = np.asarray(points, dtype=np.float64)
    slacks = domain_slacks(points)
    contact_matrix = np.abs(slacks) <= 1e-7
    side_counts = sorted((int(value) for value in contact_matrix.sum(axis=0)), reverse=True)
    vertex_contacts = int(np.sum(contact_matrix.sum(axis=1) >= 2))
    areas = np.abs(signed_double_areas(points)) / (2.0 * BOUNDING_AREA)
    minimum = float(np.min(areas))
    active_ids = np.flatnonzero(areas <= minimum + active_tolerance)
    degrees = np.zeros(COUNT, dtype=np.int64)
    for triple in TRIPLES[active_ids]:
        degrees[triple] += 1
    try:
        hull_vertices = int(len(ConvexHull(points).vertices))
    except QhullError:
        hull_vertices = 0
    return {
        "side_contact_counts_sorted": side_counts,
        "vertex_contacts": vertex_contacts,
        "hull_vertices": hull_vertices,
        "active_triples_1e-7": int(len(active_ids)),
        "active_degree_sequence": sorted((int(value) for value in degrees), reverse=True),
    }


def canonical_template_key(vertex_bits: tuple[int, int, int], edge_counts: tuple[int, int, int]) -> tuple[int, ...]:
    keys = []
    for permutation in itertools.permutations(range(3)):
        keys.append(tuple(vertex_bits[index] for index in permutation) + tuple(edge_counts[index] for index in permutation))
    return min(keys)


@dataclass(frozen=True)
class Template:
    template_id: str
    modes: tuple[int, ...]
    vertex_bits: tuple[int, int, int]
    edge_counts: tuple[int, int, int]

    @property
    def fixed_points(self) -> int:
        return sum(1 for mode in self.modes if mode != 0)


def enumerate_templates() -> list[Template]:
    """Enumerate every positive-score outer-boundary contact pattern modulo D3.

    Modes are: 0 interior; 1/2/3 on the edge opposite A/B/C; and
    4/5/6 fixed at A/B/C.  Three collinear points on an outer edge force score
    zero, so patterns violating that elementary condition are omitted exactly.
    """

    representatives: dict[tuple[int, ...], tuple[tuple[int, int, int], tuple[int, int, int]]] = {}
    for vertex_bits in itertools.product((0, 1), repeat=3):
        for edge_counts in itertools.product(range(3), repeat=3):
            valid = True
            for edge in range(3):
                endpoints = [index for index in range(3) if index != edge]
                if edge_counts[edge] + vertex_bits[endpoints[0]] + vertex_bits[endpoints[1]] > 2:
                    valid = False
            occupied = sum(vertex_bits) + sum(edge_counts)
            if not valid or occupied > COUNT:
                continue
            key = canonical_template_key(vertex_bits, edge_counts)
            current = representatives.get(key)
            candidate = (tuple(vertex_bits), tuple(edge_counts))
            if current is None or candidate < current:
                representatives[key] = candidate
    templates = []
    for index, (_key, (vertex_bits, edge_counts)) in enumerate(sorted(representatives.items()), start=1):
        modes: list[int] = []
        for vertex, present in enumerate(vertex_bits):
            modes.extend([4 + vertex] * present)
        for edge, count in enumerate(edge_counts):
            modes.extend([1 + edge] * count)
        modes.extend([0] * (COUNT - len(modes)))
        templates.append(
            Template(
                template_id=f"T{index:03d}-v{''.join(map(str, vertex_bits))}-e{''.join(map(str, edge_counts))}",
                modes=tuple(modes),
                vertex_bits=vertex_bits,
                edge_counts=edge_counts,
            )
        )
    return templates


def raw_to_points(raw: torch.Tensor, modes: torch.Tensor) -> torch.Tensor:
    """Map unconstrained genes to exact triangle topology coordinates."""

    batch = raw.shape[0]
    vertices = torch.as_tensor(
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        dtype=raw.dtype,
        device=raw.device,
    )
    point_weights: list[torch.Tensor] = []
    for point in range(COUNT):
        mode = int(modes[point])
        if mode == 0:
            point_weights.append(torch.softmax(raw[:, point, :], dim=-1))
        elif 1 <= mode <= 3:
            edge = mode - 1
            t = torch.sigmoid(raw[:, point, 0])
            remaining = [index for index in range(3) if index != edge]
            coordinates = []
            for index in range(3):
                if index == edge:
                    coordinates.append(torch.zeros(batch, dtype=raw.dtype, device=raw.device))
                elif index == remaining[0]:
                    coordinates.append(t)
                else:
                    coordinates.append(1.0 - t)
            point_weights.append(torch.stack(coordinates, dim=1))
        else:
            point_weights.append(vertices[mode - 4].expand(batch, 3))
    weights = torch.stack(point_weights, dim=1)
    xy_vertices = torch.as_tensor(VERTICES, dtype=raw.dtype, device=raw.device)
    return torch.einsum("bnc,cd->bnd", weights, xy_vertices)


def torch_scores(points: torch.Tensor, smooth_epsilon: float, temperature: float) -> tuple[torch.Tensor, torch.Tensor]:
    triples = torch.as_tensor(TRIPLES, dtype=torch.long, device=points.device)
    first = points[:, triples[:, 1], :] - points[:, triples[:, 0], :]
    second = points[:, triples[:, 2], :] - points[:, triples[:, 0], :]
    determinants = first[:, :, 0] * second[:, :, 1] - first[:, :, 1] * second[:, :, 0]
    smooth = torch.sqrt(determinants * determinants + smooth_epsilon * smooth_epsilon) / (2.0 * BOUNDING_AREA)
    soft_min = -temperature * torch.logsumexp(-smooth / temperature, dim=1)
    hard = torch.min(torch.abs(determinants) / (2.0 * BOUNDING_AREA), dim=1).values
    return soft_min, hard


def random_raw(population: int, rng: np.random.Generator) -> np.ndarray:
    raw = np.empty((population, COUNT, 3), dtype=np.float64)
    split = population // 2
    for start, stop, alpha in ((0, split, 1.0), (split, population, 0.35)):
        if start == stop:
            continue
        weights = rng.dirichlet(np.full(3, alpha), size=(stop - start) * COUNT).reshape(stop - start, COUNT, 3)
        raw[start:stop] = np.log(np.maximum(weights, 1e-14))
    return raw


def points_to_raw(points: np.ndarray, modes: tuple[int, ...]) -> np.ndarray:
    weights = np.clip(barycentric(points), 1e-12, 1.0)
    raw = np.log(weights)
    for point, mode in enumerate(modes):
        if 1 <= mode <= 3:
            edge = mode - 1
            remaining = [index for index in range(3) if index != edge]
            t = float(weights[point, remaining[0]] / np.sum(weights[point, remaining]))
            raw[point, 0] = math.log(np.clip(t, 1e-12, 1 - 1e-12) / np.clip(1 - t, 1e-12, 1.0))
    return raw


def infer_public_template(points: np.ndarray, solution_id: int) -> Template:
    """Infer only exact outer-boundary modes; no active-triple topology is copied."""

    slacks = np.abs(domain_slacks(points))
    modes: list[int] = []
    vertex_bits = [0, 0, 0]
    edge_counts = [0, 0, 0]
    for point, row in zip(points, slacks):
        vertex_distances = np.linalg.norm(VERTICES - point[None, :], axis=1)
        vertex = int(np.argmin(vertex_distances))
        if vertex_distances[vertex] <= 1e-7:
            modes.append(4 + vertex)
            vertex_bits[vertex] = 1
        else:
            side = int(np.argmin(row))
            if row[side] <= 1e-7:
                edge = SLACK_TO_EDGE[side]
                modes.append(1 + edge)
                edge_counts[edge] += 1
            else:
                modes.append(0)
    return Template(
        template_id=f"public-{solution_id}",
        modes=tuple(modes),
        vertex_bits=tuple(vertex_bits),
        edge_counts=tuple(edge_counts),
    )


def anneal_population(
    initial_raw: np.ndarray,
    modes: tuple[int, ...],
    steps: int,
    seed: int,
    event_path: Path,
    event_prefix: str,
    mutable_mask: np.ndarray | None = None,
    freeze_fraction: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    torch.manual_seed(seed)
    raw = torch.tensor(initial_raw, dtype=torch.float64, requires_grad=True)
    frozen_raw = raw.detach().clone()
    if mutable_mask is not None:
        mask_tensor = torch.as_tensor(mutable_mask, dtype=torch.bool).unsqueeze(-1).expand_as(raw)
    else:
        mask_tensor = None
    mode_tensor = torch.as_tensor(modes, dtype=torch.long)
    optimizer = torch.optim.Adam([raw], lr=0.055)
    temperatures = np.geomspace(8e-3, 8e-5, steps)
    started = time.perf_counter()
    for step, temperature in enumerate(temperatures, start=1):
        optimizer.zero_grad(set_to_none=True)
        points = raw_to_points(raw, mode_tensor)
        soft, hard = torch_scores(points, smooth_epsilon=1e-10, temperature=float(temperature))
        loss = -torch.mean(soft)
        loss.backward()
        frozen_stage = mask_tensor is not None and step <= int(freeze_fraction * steps)
        if frozen_stage:
            raw.grad.masked_fill_(~mask_tensor, 0.0)
        torch.nn.utils.clip_grad_norm_([raw], max_norm=10.0)
        optimizer.step()
        with torch.no_grad():
            if frozen_stage:
                raw[~mask_tensor] = frozen_raw[~mask_tensor]
            raw.clamp_(-14.0, 14.0)
            if step % 100 == 0 and step < steps:
                noise = 0.018 * (1.0 - step / steps)
                raw.add_(noise * torch.randn_like(raw))
        if step in {1, steps} or step % max(1, steps // 5) == 0:
            append_jsonl(
                event_path,
                {
                    "event": "anneal_progress",
                    "prefix": event_prefix,
                    "step": step,
                    "temperature": float(temperature),
                    "population_best_hard": float(torch.max(hard).detach()),
                    "population_median_hard": float(torch.median(hard).detach()),
                    "elapsed_seconds": time.perf_counter() - started,
                    "kept_points_frozen": bool(frozen_stage),
                },
            )
    with torch.no_grad():
        final_points = raw_to_points(raw, mode_tensor)
        _, hard = torch_scores(final_points, smooth_epsilon=1e-10, temperature=float(temperatures[-1]))
    return final_points.cpu().numpy(), hard.cpu().numpy()


def smooth_polish(
    points: np.ndarray,
    modes: tuple[int, ...],
    maxiter: int,
) -> tuple[np.ndarray, dict[str, object]]:
    """L-BFGS-B polish of the final smooth-min objective in topology coordinates."""

    initial = points_to_raw(points, modes).ravel()
    mode_tensor = torch.as_tensor(modes, dtype=torch.long)

    def objective(values: np.ndarray) -> tuple[float, np.ndarray]:
        genes = torch.tensor(values.reshape(1, COUNT, 3), dtype=torch.float64, requires_grad=True)
        candidate = raw_to_points(genes, mode_tensor)
        soft, _hard = torch_scores(candidate, smooth_epsilon=1e-12, temperature=2e-5)
        loss = -soft[0]
        loss.backward()
        return float(loss.detach()), genes.grad.detach().numpy().ravel()

    result = minimize(
        objective,
        initial,
        jac=True,
        method="L-BFGS-B",
        bounds=[(-18.0, 18.0)] * len(initial),
        options={"maxiter": maxiter, "ftol": 1e-15, "gtol": 1e-10, "maxls": 50},
    )
    with torch.no_grad():
        genes = torch.tensor(result.x.reshape(1, COUNT, 3), dtype=torch.float64)
        candidate = raw_to_points(genes, mode_tensor).numpy()[0]
    return candidate, {
        "success": bool(result.success),
        "status": int(result.status),
        "message": str(result.message),
        "iterations": int(result.nit),
        "initial_score": hard_score(points),
        "final_hard_score": hard_score(candidate),
        "minimum_domain_slack": float(np.min(domain_slacks(candidate))),
    }


def area_constraint(values: np.ndarray) -> np.ndarray:
    points = values[: 2 * COUNT].reshape(COUNT, 2)
    return np.abs(signed_double_areas(points)) / (2.0 * BOUNDING_AREA) - values[-1]


def area_jacobian(values: np.ndarray) -> np.ndarray:
    points = values[: 2 * COUNT].reshape(COUNT, 2)
    determinants = signed_double_areas(points)
    signs = np.where(determinants >= 0.0, 1.0, -1.0)
    jacobian = np.zeros((len(TRIPLES), 2 * COUNT + 1), dtype=np.float64)
    scale = 1.0 / (2.0 * BOUNDING_AREA)
    for row, ((i, j, k), sign) in enumerate(zip(TRIPLES, signs)):
        xi, yi = points[i]
        xj, yj = points[j]
        xk, yk = points[k]
        jacobian[row, 2 * i : 2 * i + 2] = sign * scale * np.asarray((yj - yk, xk - xj))
        jacobian[row, 2 * j : 2 * j + 2] = sign * scale * np.asarray((yk - yi, xi - xk))
        jacobian[row, 2 * k : 2 * k + 2] = sign * scale * np.asarray((yi - yj, xj - xi))
        jacobian[row, -1] = -1.0
    return jacobian


def domain_constraint(values: np.ndarray) -> np.ndarray:
    return domain_slacks(values[: 2 * COUNT].reshape(COUNT, 2)).ravel()


def domain_jacobian(_values: np.ndarray) -> np.ndarray:
    jacobian = np.zeros((3 * COUNT, 2 * COUNT + 1), dtype=np.float64)
    for point in range(COUNT):
        x, y = 2 * point, 2 * point + 1
        jacobian[3 * point, y] = 1.0
        jacobian[3 * point + 1, x], jacobian[3 * point + 1, y] = SQRT3, -1.0
        jacobian[3 * point + 2, x], jacobian[3 * point + 2, y] = -SQRT3, -1.0
    return jacobian


def topology_equalities(values: np.ndarray, modes: tuple[int, ...]) -> np.ndarray:
    points = values[: 2 * COUNT].reshape(COUNT, 2)
    slacks = domain_slacks(points)
    equations: list[float] = []
    for point, mode in enumerate(modes):
        if 1 <= mode <= 3:
            equations.append(float(slacks[point, EDGE_TO_SLACK[mode - 1]]))
        elif 4 <= mode <= 6:
            vertex = VERTICES[mode - 4]
            equations.extend((float(points[point, 0] - vertex[0]), float(points[point, 1] - vertex[1])))
    return np.asarray(equations)


def topology_jacobian(_values: np.ndarray, modes: tuple[int, ...]) -> np.ndarray:
    rows: list[np.ndarray] = []
    domain = domain_jacobian(_values)
    for point, mode in enumerate(modes):
        if 1 <= mode <= 3:
            rows.append(domain[3 * point + EDGE_TO_SLACK[mode - 1]])
        elif 4 <= mode <= 6:
            xrow = np.zeros(2 * COUNT + 1)
            yrow = np.zeros(2 * COUNT + 1)
            xrow[2 * point] = 1.0
            yrow[2 * point + 1] = 1.0
            rows.extend((xrow, yrow))
    return np.asarray(rows)


def polish(points: np.ndarray, modes: tuple[int, ...] | None, maxiter: int) -> tuple[np.ndarray, dict[str, object]]:
    initial_score = hard_score(points)
    initial = np.concatenate((points.ravel(), [max(0.0, initial_score - 1e-10)]))
    objective_gradient = np.zeros(2 * COUNT + 1)
    objective_gradient[-1] = -1.0
    constraints: list[dict[str, object]] = [
        {"type": "ineq", "fun": area_constraint, "jac": area_jacobian},
        {"type": "ineq", "fun": domain_constraint, "jac": domain_jacobian},
    ]
    if modes is not None and any(mode != 0 for mode in modes):
        constraints.append(
            {
                "type": "eq",
                "fun": lambda values: topology_equalities(values, modes),
                "jac": lambda values: topology_jacobian(values, modes),
            }
        )
    bounds = [(0.0, 1.0), (0.0, SQRT3 / 2.0)] * COUNT + [(0.0, 0.1)]
    result = minimize(
        lambda values: -values[-1],
        initial,
        jac=lambda _values: objective_gradient,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": maxiter, "ftol": 1e-13, "disp": False},
    )
    candidate = np.asarray(result.x[: 2 * COUNT], dtype=np.float64).reshape(COUNT, 2)
    final_score = hard_score(candidate)
    final_domain = float(np.min(domain_slacks(candidate)))
    accepted = bool(
        np.isfinite(candidate).all()
        and final_domain >= -1e-9
        and final_score + 1e-14 >= initial_score
    )
    if not accepted:
        candidate = np.asarray(points, dtype=np.float64).copy()
        final_score = initial_score
        final_domain = float(np.min(domain_slacks(candidate)))
    return candidate, {
        "success": bool(result.success),
        "status": int(result.status),
        "message": str(result.message),
        "iterations": int(result.nit),
        "objective_variable": float(result.x[-1]),
        "initial_score": initial_score,
        "accepted": accepted,
        "final_hard_score": final_score,
        "minimum_domain_slack": final_domain,
        "minimum_area_slack": float(np.min(area_constraint(result.x))),
    }


def public_solutions() -> tuple[dict[str, object], list[dict[str, object]]]:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    return snapshot, list(snapshot["solutions"])


def evaluate_candidate(
    points: np.ndarray,
    source: dict[str, object],
    evaluate: object,
    public: list[dict[str, object]],
    leader: float,
    target: float,
) -> dict[str, object]:
    first = verifier_score(evaluate, points)
    second_evaluate = load_evaluate()
    second = verifier_score(second_evaluate, points)
    distances = [d3_rms_distance(points, np.asarray(item["data"]["points"], dtype=np.float64)) for item in public]
    nearest = int(np.argmin(distances))
    point_bytes = json.dumps({"points": points.tolist()}, sort_keys=True, separators=(",", ":")).encode()
    return {
        **source,
        "payload_sha256": hashlib.sha256(point_bytes).hexdigest(),
        "verifier_score": first,
        "independent_replay_score": second,
        "replay_exact_agreement": first == second,
        "improvement_over_leader": first - leader,
        "strict_gate_clearer": bool(first > target and second > target),
        "minimum_domain_slack": float(np.min(domain_slacks(points))),
        "nearest_public_solution_id": int(public[nearest]["id"]),
        "nearest_public_d3_rms": distances[nearest],
        "topology": topology_signature(points),
        "points": points.tolist(),
    }


def parse_depths(value: str) -> tuple[int, ...]:
    depths = tuple(int(item) for item in value.split(",") if item.strip())
    if not depths or min(depths) < 4 or max(depths) > COUNT:
        raise argparse.ArgumentTypeError(f"mutation depths must lie in [4,{COUNT}]")
    return depths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--population", type=int, default=24)
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--maxiter", type=int, default=900)
    parser.add_argument("--lbfgs-maxiter", type=int, default=650)
    parser.add_argument("--mutation-depths", type=parse_depths, default=parse_depths("4,6,8,11"))
    parser.add_argument("--mutation-parents", type=int, default=8)
    parser.add_argument("--mutation-population", type=int, default=4)
    parser.add_argument("--mutation-top-k", type=int, default=1)
    parser.add_argument("--mutation-steps", type=int, default=400)
    parser.add_argument("--mutation-freeze-fraction", type=float, default=0.55)
    parser.add_argument("--skip-template-phase", action="store_true")
    parser.add_argument("--seed", type=int, default=20260815)
    parser.add_argument("--run-root", type=Path, default=HERE / "runs")
    parser.add_argument("--stamp")
    args = parser.parse_args()
    if args.population < args.top_k or args.top_k < 1:
        raise ValueError("population must be at least top-k >= 1")

    rng = np.random.default_rng(args.seed)
    random.seed(args.seed)
    torch.set_num_threads(max(1, min(8, os.cpu_count() or 1)))
    snapshot, public = public_solutions()
    evaluate = load_evaluate()
    leader = float(snapshot["solutions"][0]["score"])
    improvement = float(snapshot["problem"]["minImprovement"])
    target = leader + improvement
    templates = enumerate_templates()
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    results_path = run_dir / "results.jsonl"
    started = time.perf_counter()
    atomic_json(
        run_dir / "inputs.json",
        {
            "snapshot": str(SNAPSHOT.relative_to(CAMPAIGN)),
            "snapshot_sha256": sha256_path(SNAPSHOT),
            "verifier": str(VERIFIER.relative_to(CAMPAIGN)),
            "verifier_sha256": sha256_path(VERIFIER),
            "leader": leader,
            "min_improvement": improvement,
            "strict_target": target,
            "public_solutions": len(public),
            "templates": len(templates),
            "parameters": vars(args) | {"run_root": str(args.run_root)},
        },
    )
    append_jsonl(events, {"event": "run_started", "stamp": stamp, "templates": len(templates)})

    records: list[dict[str, object]] = []
    archive: list[tuple[float, np.ndarray, Template]] = []
    gate_record: dict[str, object] | None = None

    def retain(points: np.ndarray, source: dict[str, object]) -> dict[str, object]:
        nonlocal gate_record
        record = evaluate_candidate(points, source, evaluate, public, leader, target)
        append_jsonl(results_path, record)
        records.append(record)
        if record["strict_gate_clearer"]:
            gate_record = record
            atomic_json(run_dir / "GATE_CANDIDATE.json", record)
        return record

    completed_templates = 0
    template_schedule = [] if args.skip_template_phase else templates
    for template_index, template in enumerate(template_schedule):
        initial = random_raw(args.population, rng)
        population, scores = anneal_population(
            initial,
            template.modes,
            args.steps,
            args.seed + template_index,
            events,
            template.template_id,
        )
        best_ids = np.argsort(scores)[::-1][: args.top_k]
        for rank, candidate_id in enumerate(best_ids, start=1):
            raw_points = population[candidate_id]
            fixed, fixed_info = smooth_polish(raw_points, template.modes, args.lbfgs_maxiter)
            fixed_record = retain(
                fixed,
                {
                    "phase": "template",
                    "template_id": template.template_id,
                    "rank_within_template": rank,
                    "polish": "smooth_fixed_topology",
                    "annealed_score": float(scores[candidate_id]),
                    "polish_info": fixed_info,
                },
            )
            archive.append((float(fixed_record["verifier_score"]), fixed, template))
            if gate_record is not None:
                break
            released, released_info = polish(fixed, None, args.maxiter)
            released_record = retain(
                released,
                {
                    "phase": "template",
                    "template_id": template.template_id,
                    "rank_within_template": rank,
                    "polish": "released_topology",
                    "annealed_score": float(scores[candidate_id]),
                    "polish_info": released_info,
                },
            )
            archive.append((float(released_record["verifier_score"]), released, template))
            if gate_record is not None:
                break
        atomic_json(
            run_dir / "checkpoint.json",
            {
                "completed_templates": template_index + 1,
                "total_templates": len(template_schedule),
                "records": len(records),
                "best_score": max(float(record["verifier_score"]) for record in records),
                "gate_clearer": gate_record is not None,
            },
        )
        if gate_record is not None:
            break
        completed_templates = template_index + 1

    # The public discussion exhausts depth-1/2/3 point replacement.  This
    # separate family begins at depth four and includes full-set rebirth.
    public_parents: list[tuple[float, np.ndarray, Template]] = []
    for item in public:
        points = np.asarray(item["data"]["points"], dtype=np.float64)
        if any(d3_rms_distance(points, previous[1]) <= 1e-8 for previous in public_parents):
            continue
        public_parents.append(
            (
                verifier_score(evaluate, points),
                points,
                infer_public_template(points, int(item["id"])),
            )
        )
    archive.extend(public_parents)
    mutation_members = 0
    selected_parent_templates: list[str] = []
    if gate_record is None and archive:
        archive.sort(key=lambda item: item[0], reverse=True)
        parents = archive[: args.mutation_parents]
        selected_parent_templates = [parent[2].template_id for parent in parents]
        for depth_index, depth in enumerate(args.mutation_depths):
            for parent_index, (parent_score, parent, template) in enumerate(parents):
                initial = np.repeat(points_to_raw(parent, template.modes)[None, :, :], args.mutation_population, axis=0)
                fresh = random_raw(args.mutation_population, rng)
                mutable = np.zeros((args.mutation_population, COUNT), dtype=bool)
                for member in range(args.mutation_population):
                    chosen = rng.choice(COUNT, size=depth, replace=False)
                    initial[member, chosen] = fresh[member, chosen]
                    mutable[member, chosen] = True
                mutation_members += args.mutation_population
                population, scores = anneal_population(
                    initial,
                    template.modes,
                    args.mutation_steps,
                    args.seed + 100000 + 1000 * depth_index + parent_index,
                    events,
                    f"mutation-d{depth}-{template.template_id}-p{parent_index}",
                    mutable_mask=mutable,
                    freeze_fraction=args.mutation_freeze_fraction,
                )
                candidate_ids = np.argsort(scores)[::-1][: args.mutation_top_k]
                for mutation_rank, candidate_id in enumerate(candidate_ids, start=1):
                    fixed, fixed_info = smooth_polish(
                        population[candidate_id], template.modes, args.lbfgs_maxiter
                    )
                    fixed_record = retain(
                        fixed,
                        {
                            "phase": "death_rebirth",
                            "depth": depth,
                            "parent_rank": parent_index + 1,
                            "parent_score": parent_score,
                            "mutation_rank": mutation_rank,
                            "template_id": template.template_id,
                            "polish": "smooth_fixed_topology",
                            "annealed_score": float(scores[candidate_id]),
                            "polish_info": fixed_info,
                        },
                    )
                    if gate_record is not None:
                        break
                    released, released_info = polish(fixed, None, args.maxiter)
                    retain(
                        released,
                        {
                            "phase": "death_rebirth",
                            "depth": depth,
                            "parent_rank": parent_index + 1,
                            "parent_score": parent_score,
                            "mutation_rank": mutation_rank,
                            "template_id": template.template_id,
                            "polish": "released_topology",
                            "annealed_score": float(scores[candidate_id]),
                            "polish_info": released_info,
                        },
                    )
                    if gate_record is not None:
                        break
                if gate_record is not None:
                    break
            if gate_record is not None:
                break

    scores = np.asarray([float(record["verifier_score"]) for record in records])
    distances = np.asarray([float(record["nearest_public_d3_rms"]) for record in records])
    best_id = int(np.argmax(scores))
    distinct_ids = np.flatnonzero(distances > 1e-4)
    best_distinct_id = int(distinct_ids[np.argmax(scores[distinct_ids])]) if len(distinct_ids) else None
    summary = {
        "status": "gate_clearer" if gate_record is not None else "bounded_frontier",
        "verifier_sha256": EXPECTED_VERIFIER_SHA256,
        "leader": leader,
        "strict_target": target,
        "templates_enumerated": completed_templates,
        "topology_templates_available": len(templates),
        "d3_distinct_public_basins": len(public_parents),
        "mutation_parents_selected": len(selected_parent_templates),
        "mutation_public_parents_selected": sum(
            template_id.startswith("public-") for template_id in selected_parent_templates
        ),
        "mutation_template_parents_selected": sum(
            not template_id.startswith("public-") for template_id in selected_parent_templates
        ),
        "template_population_members": completed_templates * args.population,
        "mutation_population_members": mutation_members,
        "polished_records": len(records),
        "death_rebirth_depths": list(args.mutation_depths),
        "best_record": {key: value for key, value in records[best_id].items() if key != "points"},
        "best_distinct_record": (
            {key: value for key, value in records[best_distinct_id].items() if key != "points"}
            if best_distinct_id is not None
            else None
        ),
        "records_above_0_035": int(np.sum(scores >= 0.035)),
        "records_above_0_036": int(np.sum(scores >= 0.036)),
        "records_distinct_from_public_1e_4": int(np.sum(distances > 1e-4)),
        "gate_clearers": int(np.sum(scores > target)),
        "elapsed_seconds": time.perf_counter() - started,
        "events_sha256": sha256_path(events),
        "results_sha256": sha256_path(results_path),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_jsonl(events, {"event": "run_completed", "status": summary["status"], "elapsed_seconds": summary["elapsed_seconds"]})
    return 0 if gate_record is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
