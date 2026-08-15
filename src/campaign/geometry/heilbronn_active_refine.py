#!/usr/bin/env python3
"""High-precision active-set refinement for Heilbronn triangles n=11."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import mpmath as mp
import numpy as np

BASE = "https://einsteinarena.com"
SLUG = "heilbronn-triangles"
PROBLEM_ID = 15
COUNT = 11
BOUNDING_AREA = np.sqrt(3.0) / 4.0


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


def signed_double_area(points: np.ndarray, triple: tuple[int, int, int]) -> float:
    i, j, k = triple
    first = points[j] - points[i]
    second = points[k] - points[i]
    return float(first[0] * second[1] - first[1] * second[0])


def triangle_gradient(points: np.ndarray, triple: tuple[int, int, int], sign: float) -> np.ndarray:
    i, j, k = triple
    xi, yi = points[i]
    xj, yj = points[j]
    xk, yk = points[k]
    gradient = np.zeros(2 * COUNT)
    gradient[2 * i : 2 * i + 2] = (yj - yk, xk - xj)
    gradient[2 * j : 2 * j + 2] = (yk - yi, xi - xk)
    gradient[2 * k : 2 * k + 2] = (yi - yj, xj - xi)
    return 0.5 * sign * gradient


def active_triples(
    points: np.ndarray, tolerance: float
) -> tuple[list[tuple[int, int, int]], dict[tuple[int, int, int], int], float]:
    records = []
    for triple in itertools.combinations(range(COUNT), 3):
        double = signed_double_area(points, triple)
        records.append((abs(double) / 2.0, triple, 1 if double >= 0.0 else -1))
    minimum = min(record[0] for record in records)
    active = [record[1] for record in records if record[0] - minimum <= tolerance]
    signs = {record[1]: record[2] for record in records}
    return active, signs, minimum


def boundary_contacts(points: np.ndarray, tolerance: float) -> list[tuple[int, str]]:
    sq3 = np.sqrt(3.0)
    contacts: list[tuple[int, str]] = []
    for point, (x, y) in enumerate(points):
        slacks = {"bottom": y, "left": sq3 * x - y, "right": sq3 - sq3 * x - y}
        contacts.extend((point, side) for side, slack in slacks.items() if abs(slack) <= tolerance)
    return contacts


def equations_and_jacobian(
    values: mp.matrix,
    triples: list[tuple[int, int, int]],
    signs: dict[tuple[int, int, int], int],
    contacts: list[tuple[int, str]],
) -> tuple[mp.matrix, mp.matrix]:
    score_id = 2 * COUNT
    size = len(triples) + len(contacts)
    equations = mp.matrix(size, 1)
    jacobian = mp.matrix(size, 2 * COUNT + 1)
    row = 0
    for triple in triples:
        i, j, k = triple
        xi, yi = values[2 * i], values[2 * i + 1]
        xj, yj = values[2 * j], values[2 * j + 1]
        xk, yk = values[2 * k], values[2 * k + 1]
        sign = mp.mpf(signs[triple])
        double = (xj - xi) * (yk - yi) - (yj - yi) * (xk - xi)
        equations[row] = sign * double / 2 - values[score_id]
        jacobian[row, 2 * i], jacobian[row, 2 * i + 1] = sign * (yj - yk) / 2, sign * (xk - xj) / 2
        jacobian[row, 2 * j], jacobian[row, 2 * j + 1] = sign * (yk - yi) / 2, sign * (xi - xk) / 2
        jacobian[row, 2 * k], jacobian[row, 2 * k + 1] = sign * (yi - yj) / 2, sign * (xj - xi) / 2
        jacobian[row, score_id] = -1
        row += 1
    sq3 = mp.sqrt(3)
    for point, side in contacts:
        x_id, y_id = 2 * point, 2 * point + 1
        if side == "bottom":
            equations[row] = values[y_id]
            jacobian[row, y_id] = 1
        elif side == "left":
            equations[row] = sq3 * values[x_id] - values[y_id]
            jacobian[row, x_id], jacobian[row, y_id] = sq3, -1
        else:
            equations[row] = sq3 - sq3 * values[x_id] - values[y_id]
            jacobian[row, x_id], jacobian[row, y_id] = -sq3, -1
        row += 1
    return equations, jacobian


def active_diagnostics(
    points: np.ndarray,
    triples: list[tuple[int, int, int]],
    signs: dict[tuple[int, int, int], int],
    contacts: list[tuple[int, str]],
) -> dict[str, object]:
    matrix = np.zeros((len(triples) + len(contacts), 2 * COUNT + 1))
    for row, triple in enumerate(triples):
        matrix[row, : 2 * COUNT] = triangle_gradient(points, triple, signs[triple])
        matrix[row, -1] = -1.0
    sq3 = np.sqrt(3.0)
    boundary_gradients = []
    for offset, (point, side) in enumerate(contacts, start=len(triples)):
        gradient = np.zeros(2 * COUNT)
        if side == "bottom":
            gradient[2 * point + 1] = 1.0
        elif side == "left":
            gradient[2 * point : 2 * point + 2] = (sq3, -1.0)
        else:
            gradient[2 * point : 2 * point + 2] = (-sq3, -1.0)
        matrix[offset, : 2 * COUNT] = gradient
        boundary_gradients.append(gradient)
    singular = np.linalg.svd(matrix, compute_uv=False)

    # KKT: sum(lambda_i grad A_i) + sum(mu_j grad b_j) = 0,
    # sum(lambda_i) = 1, with all multipliers nonnegative at this maximum.
    kkt = np.zeros((2 * COUNT + 1, len(triples) + len(contacts)))
    for column, triple in enumerate(triples):
        kkt[: 2 * COUNT, column] = triangle_gradient(points, triple, signs[triple])
        kkt[-1, column] = 1.0
    for boundary_id, gradient in enumerate(boundary_gradients):
        kkt[: 2 * COUNT, len(triples) + boundary_id] = gradient
    rhs = np.zeros(2 * COUNT + 1)
    rhs[-1] = 1.0
    multipliers = np.linalg.solve(kkt, rhs)
    residual = np.linalg.norm(kkt @ multipliers - rhs, ord=np.inf)
    return {
        "active_jacobian_rank": int(np.linalg.matrix_rank(matrix, tol=1e-11)),
        "active_jacobian_singular_values": singular.tolist(),
        "kkt_residual_inf": float(residual),
        "triple_multipliers": [
            {"triple": triple, "multiplier": float(multiplier)}
            for triple, multiplier in zip(triples, multipliers[: len(triples)])
        ],
        "boundary_multipliers": [
            {"contact": contact, "multiplier": float(multiplier)}
            for contact, multiplier in zip(contacts, multipliers[len(triples) :])
        ],
        "all_multipliers_positive": bool(np.min(multipliers) > 0.0),
    }


def all_metrics(points: np.ndarray) -> dict[str, object]:
    records = []
    for triple in itertools.combinations(range(COUNT), 3):
        records.append((abs(signed_double_area(points, triple)) / 2.0, triple))
    records.sort()
    sq3 = np.sqrt(3.0)
    slacks = []
    for x, y in points:
        slacks.extend((y, sq3 * x - y, sq3 - sq3 * x - y))
    return {
        "minimum_raw_area": float(records[0][0]),
        "second_inactive_raw_area": float(records[17][0]),
        "minimum_domain_slack": float(min(slacks)),
        "finite": bool(np.isfinite(points).all()),
        "distinct": bool(np.min(np.linalg.norm(points[:, None] - points[None, :], axis=2) + np.eye(COUNT)) > 1e-12),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-payload", type=Path)
    parser.add_argument("--active-tolerance", type=float, default=1e-12)
    parser.add_argument("--boundary-tolerance", type=float, default=1e-12)
    parser.add_argument("--digits", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=12)
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
    seed = np.asarray(seed_data["points"], dtype=np.float64)
    triples, signs, seed_raw_score = active_triples(seed, args.active_tolerance)
    contacts = boundary_contacts(seed, args.boundary_tolerance)
    if len(triples) + len(contacts) != 2 * COUNT + 1:
        raise RuntimeError(f"active system is not square: {len(triples)} triples + {len(contacts)} contacts")

    live_best = float(solutions[0]["score"])
    target = live_best + float(problem["minImprovement"])
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
    diagnostics = active_diagnostics(seed, triples, signs, contacts)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_json(run_dir / "problem.json", problem)
    atomic_json(run_dir / "leaderboard.json", leaderboard)
    atomic_json(run_dir / "best_solutions.json", solutions)
    atomic_json(run_dir / "seed.json", {"points": seed.tolist()})
    atomic_json(
        run_dir / "active_set.json",
        {
            "triples": triples,
            "signs": {str(triple): signs[triple] for triple in triples},
            "boundary_contacts": contacts,
            **diagnostics,
        },
    )

    mp.mp.dps = args.digits
    values = mp.matrix(2 * COUNT + 1, 1)
    for point in range(COUNT):
        values[2 * point] = mp.mpf(seed[point, 0])
        values[2 * point + 1] = mp.mpf(seed[point, 1])
    values[2 * COUNT] = mp.mpf(seed_raw_score)
    for iteration in range(args.iterations):
        equations, jacobian = equations_and_jacobian(values, triples, signs, contacts)
        residual = max(abs(value) for value in equations)
        append(events, {"event": "newton", "iteration": iteration, "max_residual": mp.nstr(residual, 30)})
        if residual < mp.mpf(10) ** (-(args.digits - 15)):
            break
        values += mp.lu_solve(jacobian, -equations)
    equations, _ = equations_and_jacobian(values, triples, signs, contacts)
    residual = max(abs(value) for value in equations)
    exact_raw = values[2 * COUNT]
    exact_normalized = exact_raw / (mp.sqrt(3) / 4)
    refined = np.asarray(
        [[float(values[2 * point]), float(values[2 * point + 1])] for point in range(COUNT)]
    )
    payload = {"points": refined.tolist()}
    atomic_json(run_dir / "best.json", payload)

    namespace: dict[str, object] = {}
    exec(problem["verifier"], namespace)  # noqa: S102 -- live public verifier replay
    official_score = float(namespace["evaluate"](payload))  # type: ignore[operator]
    metrics = all_metrics(refined)
    summary = {
        "slug": SLUG,
        "seed_source": seed_source,
        "verifier_sha256": verifier_hash,
        "live_best": live_best,
        "target": target,
        "seed_score": seed_raw_score / BOUNDING_AREA,
        "active_triples": len(triples),
        "boundary_contacts": len(contacts),
        "active_jacobian_rank": diagnostics["active_jacobian_rank"],
        "smallest_singular_value": diagnostics["active_jacobian_singular_values"][-1],
        "all_kkt_multipliers_positive": diagnostics["all_multipliers_positive"],
        "smallest_triple_multiplier": min(
            item["multiplier"] for item in diagnostics["triple_multipliers"]
        ),
        "high_precision_digits": args.digits,
        "high_precision_residual": mp.nstr(residual, 30),
        "high_precision_raw_area": mp.nstr(exact_raw, 70),
        "high_precision_normalized_score": mp.nstr(exact_normalized, 70),
        "official_verifier_score": official_score,
        "improvement_over_live": official_score - live_best,
        "gate_clearing": official_score > target,
        "intended_domain": bool(metrics["finite"] and metrics["distinct"] and metrics["minimum_domain_slack"] >= -1e-15),
        **metrics,
        "payload": str((run_dir / "best.json").resolve()),
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
