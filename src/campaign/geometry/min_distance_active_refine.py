#!/usr/bin/env python3
"""High-precision active-set refinement for min-distance-ratio-2d."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import mpmath as mp
import numpy as np


BASE = "https://einsteinarena.com"
SLUG = "min-distance-ratio-2d"
PROBLEM_ID = 5
COUNT = 16


def get(path: str, **params: object) -> object:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.load(response)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append(path: Path, event: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def canonicalize(points: np.ndarray, anchor: tuple[int, int]) -> np.ndarray:
    points = points - points.mean(axis=0)
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    minimum = np.min(distances[np.triu_indices(COUNT, 1)])
    points /= minimum
    a, b = anchor
    delta = points[b] - points[a]
    cosine, sine = delta[0] / np.linalg.norm(delta), delta[1] / np.linalg.norm(delta)
    rotation = np.array([[cosine, sine], [-sine, cosine]])
    return points @ rotation.T


def active_sets(points: np.ndarray, tolerance: float) -> tuple[list[tuple[int, int]], list[tuple[int, int]], float]:
    distances = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    values = distances[np.triu_indices(COUNT, 1)]
    minimum, maximum = float(values.min()), float(values.max())
    minimum_edges = []
    maximum_edges = []
    for i in range(COUNT):
        for j in range(i + 1, COUNT):
            if abs(distances[i, j] - minimum) <= tolerance:
                minimum_edges.append((i, j))
            if abs(distances[i, j] - maximum) <= tolerance:
                maximum_edges.append((i, j))
    return minimum_edges, maximum_edges, maximum * maximum / (minimum * minimum)


def equations_and_jacobian(
    values: mp.matrix,
    minimum_edges: list[tuple[int, int]],
    maximum_edges: list[tuple[int, int]],
    anchor: tuple[int, int],
) -> tuple[mp.matrix, mp.matrix]:
    score_id = 2 * COUNT
    equation_count = len(minimum_edges) + len(maximum_edges) + 3
    equations = mp.matrix(equation_count, 1)
    jacobian = mp.matrix(equation_count, 2 * COUNT + 1)
    row = 0
    for i, j in minimum_edges:
        dx, dy = values[2 * i] - values[2 * j], values[2 * i + 1] - values[2 * j + 1]
        equations[row] = dx * dx + dy * dy - 1
        jacobian[row, 2 * i], jacobian[row, 2 * i + 1] = 2 * dx, 2 * dy
        jacobian[row, 2 * j], jacobian[row, 2 * j + 1] = -2 * dx, -2 * dy
        row += 1
    for i, j in maximum_edges:
        dx, dy = values[2 * i] - values[2 * j], values[2 * i + 1] - values[2 * j + 1]
        equations[row] = dx * dx + dy * dy - values[score_id]
        jacobian[row, 2 * i], jacobian[row, 2 * i + 1] = 2 * dx, 2 * dy
        jacobian[row, 2 * j], jacobian[row, 2 * j + 1] = -2 * dx, -2 * dy
        jacobian[row, score_id] = -1
        row += 1
    for i in range(COUNT):
        equations[row] += values[2 * i]
        jacobian[row, 2 * i] = 1
        equations[row + 1] += values[2 * i + 1]
        jacobian[row + 1, 2 * i + 1] = 1
    row += 2
    a, b = anchor
    equations[row] = values[2 * b + 1] - values[2 * a + 1]
    jacobian[row, 2 * b + 1], jacobian[row, 2 * a + 1] = 1, -1
    return equations, jacobian


def rigidity_and_multipliers(
    points: np.ndarray,
    minimum_edges: list[tuple[int, int]],
    maximum_edges: list[tuple[int, int]],
) -> dict[str, object]:
    edges = minimum_edges + maximum_edges
    rigidity = np.zeros((len(edges), 2 * COUNT))
    for row, (i, j) in enumerate(edges):
        gradient = 2.0 * (points[i] - points[j])
        rigidity[row, 2 * i : 2 * i + 2] = gradient
        rigidity[row, 2 * j : 2 * j + 2] = -gradient
    singular = np.linalg.svd(rigidity, compute_uv=False)
    _, _, right = np.linalg.svd(rigidity.T, full_matrices=True)
    stress = right[-1]
    if np.median(stress[: len(minimum_edges)]) < 0.0:
        stress = -stress
    minimum_weights = stress[: len(minimum_edges)]
    maximum_weights = -stress[len(minimum_edges) :]
    scale = maximum_weights.sum()
    minimum_weights /= scale
    maximum_weights /= scale
    return {
        "rank": int(np.linalg.matrix_rank(rigidity, tol=1e-10)),
        "singular_values": singular.tolist(),
        "minimum_edge_multipliers": [
            {"edge": edge, "multiplier": float(weight)}
            for edge, weight in zip(minimum_edges, minimum_weights)
        ],
        "maximum_edge_multipliers": [
            {"edge": edge, "multiplier": float(weight)}
            for edge, weight in zip(maximum_edges, maximum_weights)
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-payload", type=Path)
    parser.add_argument("--active-tolerance", type=float, default=1e-6)
    parser.add_argument("--digits", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    args = parser.parse_args()

    problem = get(f"/api/problems/{SLUG}")
    solutions = get("/api/solutions/best", problem_id=PROBLEM_ID, limit=100)
    leaderboard = get("/api/leaderboard", problem_id=PROBLEM_ID, limit=100)
    assert isinstance(problem, dict) and isinstance(solutions, list) and isinstance(leaderboard, list)
    if args.seed_payload is None:
        seed_data = solutions[0]["data"]
        seed_source = f"live solution {solutions[0]['id']}"
    else:
        with args.seed_payload.open(encoding="utf-8") as handle:
            seed_data = json.load(handle)
        seed_source = str(args.seed_payload.resolve())
    raw = np.asarray(seed_data["vectors"], dtype=np.float64)
    provisional, _, _ = active_sets(raw, args.active_tolerance)
    anchor = provisional[0]
    seed = canonicalize(raw, anchor)
    minimum_edges, maximum_edges, seed_score = active_sets(seed, args.active_tolerance)
    if len(minimum_edges) + len(maximum_edges) + 3 != 2 * COUNT + 1:
        raise RuntimeError("active system is not square after three similarity gauges")

    live_best = float(solutions[0]["score"])
    target = live_best - float(problem["minImprovement"])
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
    diagnostics = rigidity_and_multipliers(seed, minimum_edges, maximum_edges)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_json(run_dir / "problem.json", problem)
    atomic_json(run_dir / "leaderboard.json", leaderboard)
    atomic_json(run_dir / "best_solutions.json", solutions)
    atomic_json(run_dir / "seed.json", {"vectors": seed.tolist()})
    atomic_json(
        run_dir / "active_set.json",
        {
            "minimum_edges": minimum_edges,
            "maximum_edges": maximum_edges,
            "anchor": anchor,
            **diagnostics,
        },
    )

    mp.mp.dps = args.digits
    values = mp.matrix(2 * COUNT + 1, 1)
    for i in range(COUNT):
        values[2 * i], values[2 * i + 1] = mp.mpf(seed[i, 0]), mp.mpf(seed[i, 1])
    values[2 * COUNT] = mp.mpf(seed_score)
    for iteration in range(args.iterations):
        equations, jacobian = equations_and_jacobian(values, minimum_edges, maximum_edges, anchor)
        residual = max(abs(value) for value in equations)
        append(events, {"event": "newton", "iteration": iteration, "max_residual": mp.nstr(residual, 30)})
        if residual < mp.mpf(10) ** (-(args.digits - 15)):
            break
        values += mp.lu_solve(jacobian, -equations)
    equations, _ = equations_and_jacobian(values, minimum_edges, maximum_edges, anchor)
    residual = max(abs(value) for value in equations)
    exact_score = values[2 * COUNT]
    refined = np.asarray([[float(values[2 * i]), float(values[2 * i + 1])] for i in range(COUNT)])
    payload = {"vectors": refined.tolist()}
    atomic_json(run_dir / "best.json", payload)

    namespace: dict[str, object] = {}
    exec(problem["verifier"], namespace)
    official_score = float(namespace["evaluate"](payload))  # type: ignore[operator]
    distances = np.linalg.norm(refined[:, None, :] - refined[None, :, :], axis=2)
    pairwise = distances[np.triu_indices(COUNT, 1)]
    summary = {
        "slug": SLUG,
        "seed_source": seed_source,
        "verifier_sha256": verifier_hash,
        "live_best": live_best,
        "target": target,
        "seed_score": seed_score,
        "minimum_edges": len(minimum_edges),
        "maximum_edges": len(maximum_edges),
        "rigidity_rank": diagnostics["rank"],
        "smallest_nonzero_singular_value": diagnostics["singular_values"][-2],
        "high_precision_digits": args.digits,
        "high_precision_residual": mp.nstr(residual, 30),
        "high_precision_score": mp.nstr(exact_score, 60),
        "official_verifier_score": official_score,
        "improvement_over_live": live_best - official_score,
        "gate_clearing": official_score < target,
        "min_distance": float(pairwise.min()),
        "max_distance": float(pairwise.max()),
        "finite_distinct": bool(np.isfinite(refined).all() and pairwise.min() > 1e-12),
        "payload": str((run_dir / "best.json").resolve()),
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
