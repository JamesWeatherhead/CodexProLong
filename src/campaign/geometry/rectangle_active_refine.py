#!/usr/bin/env python3
"""High-precision refinement of a rigid circles-rectangle active set."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import mpmath as mp
import numpy as np

from rectangle_packing_search import SLUG, atomic_json, get, metrics, normalize_origin


COUNT = 21


def append(path: Path, event: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def decode_active(circles: np.ndarray, tolerance: float) -> tuple[list[tuple[int, int]], list[tuple[int, str]]]:
    circles = normalize_origin(circles)
    centers, radii = circles[:, :2], circles[:, 2]
    width = np.max(centers[:, 0] + radii)
    height = np.max(centers[:, 1] + radii)
    pairs = [
        (i, j)
        for i in range(COUNT)
        for j in range(i + 1, COUNT)
        if np.linalg.norm(centers[i] - centers[j]) - radii[i] - radii[j] <= tolerance
    ]
    walls: list[tuple[int, str]] = []
    for i, (x, y) in enumerate(centers):
        for name, slack in (
            ("L", x - radii[i]),
            ("R", width - x - radii[i]),
            ("B", y - radii[i]),
            ("T", height - y - radii[i]),
        ):
            if slack <= tolerance:
                walls.append((i, name))
    return pairs, walls


def equations_and_jacobian(
    values: mp.matrix,
    pairs: list[tuple[int, int]],
    walls: list[tuple[int, str]],
) -> tuple[mp.matrix, mp.matrix]:
    radius_start, width_id, height_id = 2 * COUNT, 3 * COUNT, 3 * COUNT + 1
    equation_count = len(pairs) + len(walls) + 1
    equations = mp.matrix(equation_count, 1)
    jacobian = mp.matrix(equation_count, 3 * COUNT + 2)
    row = 0
    for i, j in pairs:
        dx = values[2 * i] - values[2 * j]
        dy = values[2 * i + 1] - values[2 * j + 1]
        distance = mp.sqrt(dx * dx + dy * dy)
        equations[row] = distance - values[radius_start + i] - values[radius_start + j]
        jacobian[row, 2 * i] = dx / distance
        jacobian[row, 2 * i + 1] = dy / distance
        jacobian[row, 2 * j] = -dx / distance
        jacobian[row, 2 * j + 1] = -dy / distance
        jacobian[row, radius_start + i] = -1
        jacobian[row, radius_start + j] = -1
        row += 1
    for i, wall in walls:
        x_id, y_id, radius_id = 2 * i, 2 * i + 1, radius_start + i
        if wall == "L":
            equations[row] = values[x_id] - values[radius_id]
            jacobian[row, x_id], jacobian[row, radius_id] = 1, -1
        elif wall == "R":
            equations[row] = values[width_id] - values[x_id] - values[radius_id]
            jacobian[row, width_id], jacobian[row, x_id], jacobian[row, radius_id] = 1, -1, -1
        elif wall == "B":
            equations[row] = values[y_id] - values[radius_id]
            jacobian[row, y_id], jacobian[row, radius_id] = 1, -1
        else:
            equations[row] = values[height_id] - values[y_id] - values[radius_id]
            jacobian[row, height_id], jacobian[row, y_id], jacobian[row, radius_id] = 1, -1, -1
        row += 1
    equations[row] = values[width_id] + values[height_id] - 2
    jacobian[row, width_id] = jacobian[row, height_id] = 1
    return equations, jacobian


def float_payload(values: mp.matrix) -> np.ndarray:
    circles = np.empty((COUNT, 3), dtype=np.float64)
    for i in range(COUNT):
        circles[i] = float(values[2 * i]), float(values[2 * i + 1]), float(values[2 * COUNT + i])
    circles = normalize_origin(circles)
    report = metrics(circles)
    if not report["strict_valid"]:
        decrement = max(
            0.0,
            -float(report["min_pair_slack"]) / 2.0,
            -float(report["perimeter_slack"]) / 4.0,
        )
        circles[:, 2] -= decrement
    for _ in range(100):
        if metrics(circles)["strict_valid"]:
            # Leave several representable-radius steps of genuine-domain
            # clearance, rather than accepting a float equality whose exact
            # real interpretation could lie on the wrong side.
            for _ in range(8):
                circles[:, 2] = np.nextafter(circles[:, 2], 0.0)
            return normalize_origin(circles)
        circles[:, 2] = np.nextafter(circles[:, 2], 0.0)
    raise RuntimeError("could not make rounded active-set root strictly feasible")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("seed_payload", type=Path)
    parser.add_argument("--active-tolerance", type=float, default=1e-7)
    parser.add_argument("--digits", type=int, default=80)
    parser.add_argument("--iterations", type=int, default=8)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    args = parser.parse_args()

    with args.seed_payload.open(encoding="utf-8") as handle:
        seed = normalize_origin(np.asarray(json.load(handle)["circles"], dtype=np.float64))
    pairs, walls = decode_active(seed, args.active_tolerance)
    if len(pairs) + len(walls) + 1 != 3 * COUNT + 2:
        raise RuntimeError(f"active set is not square: {len(pairs)} pairs + {len(walls)} walls + perimeter")

    problem = get(f"/api/problems/{SLUG}")
    solutions = get("/api/solutions/best", problem_id=18, limit=20)
    assert isinstance(problem, dict) and isinstance(solutions, list)
    live_best = float(solutions[0]["score"])
    target = live_best + float(problem["minImprovement"])
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_json(run_dir / "problem.json", problem)
    atomic_json(run_dir / "best_solutions.json", solutions)
    atomic_json(run_dir / "seed.json", {"circles": seed.tolist()})
    atomic_json(run_dir / "active_set.json", {"pairs": pairs, "walls": walls, "perimeter": True})

    mp.mp.dps = args.digits
    values = mp.matrix(3 * COUNT + 2, 1)
    for i in range(COUNT):
        values[2 * i], values[2 * i + 1] = mp.mpf(seed[i, 0]), mp.mpf(seed[i, 1])
        values[2 * COUNT + i] = mp.mpf(seed[i, 2])
    values[3 * COUNT] = mp.mpf(np.max(seed[:, 0] + seed[:, 2]))
    values[3 * COUNT + 1] = mp.mpf(np.max(seed[:, 1] + seed[:, 2]))

    initial_jacobian = equations_and_jacobian(values, pairs, walls)[1]
    numpy_jacobian = np.asarray(initial_jacobian.tolist(), dtype=np.float64)
    rank = int(np.linalg.matrix_rank(numpy_jacobian, tol=1e-10))
    smallest_singular = float(np.linalg.svd(numpy_jacobian, compute_uv=False)[-1])
    for iteration in range(args.iterations):
        equations, jacobian = equations_and_jacobian(values, pairs, walls)
        residual = max(abs(value) for value in equations)
        append(events, {"event": "newton", "iteration": iteration, "max_residual": mp.nstr(residual, 20)})
        if residual < mp.mpf(10) ** (-(args.digits - 15)):
            break
        values += mp.lu_solve(jacobian, -equations)

    equations, _ = equations_and_jacobian(values, pairs, walls)
    final_residual = max(abs(value) for value in equations)
    exact_objective = sum(values[2 * COUNT + i] for i in range(COUNT))
    circles = float_payload(values)
    report = metrics(circles)
    atomic_json(run_dir / "best.json", {"circles": circles.tolist()})

    namespace: dict[str, object] = {}
    exec(problem["verifier"], namespace)
    official_score = float(namespace["evaluate"]({"circles": circles.tolist()}))  # type: ignore[operator]
    summary = {
        "slug": SLUG,
        "seed_payload": str(args.seed_payload.resolve()),
        "verifier_sha256": verifier_hash,
        "live_best": live_best,
        "target": target,
        "pair_contacts": len(pairs),
        "wall_contacts": len(walls),
        "active_jacobian_rank": rank,
        "active_jacobian_smallest_singular_value": smallest_singular,
        "high_precision_digits": args.digits,
        "high_precision_max_residual": mp.nstr(final_residual, 30),
        "high_precision_objective": mp.nstr(exact_objective, 50),
        "official_verifier_score": official_score,
        "strict_metrics": report,
        "gate_clearing": bool(report["strict_valid"] and official_score > target),
        "shortfall_to_target": target - official_score,
        "payload": str((run_dir / "best.json").resolve()),
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
