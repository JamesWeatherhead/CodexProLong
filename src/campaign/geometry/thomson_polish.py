#!/usr/bin/env python3
"""Checkpointed tangent-coordinate L-BFGS polish for Thomson n=282."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.optimize import minimize


BASE = "https://einsteinarena.com"
SLUG = "thomson-problem"
PROBLEM_ID = 10
COUNT = 282


def get(path: str, **params: object) -> object:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as response:
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


def normalize(points: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(points, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or np.any(norms <= 1e-14):
        raise ValueError("non-finite or zero Thomson point")
    return points / norms


def tangent_basis(points: np.ndarray) -> np.ndarray:
    basis = np.empty((COUNT, 2, 3))
    axes = np.eye(3)
    for i, point in enumerate(points):
        reference = axes[np.argmin(np.abs(point))]
        first = np.cross(point, reference)
        first /= np.linalg.norm(first)
        second = np.cross(point, first)
        basis[i, 0], basis[i, 1] = first, second
    return basis


def map_parameters(parameters: np.ndarray, base: np.ndarray, basis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    tangent = parameters.reshape(COUNT, 2)
    raw = base + np.einsum("nik,ni->nk", basis, tangent)
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    return raw / norms, norms


def energy_gradient(points: np.ndarray) -> tuple[float, np.ndarray]:
    differences = points[:, None, :] - points[None, :, :]
    distances = np.linalg.norm(differences, axis=2)
    np.fill_diagonal(distances, np.inf)
    inverse = 1.0 / distances
    energy = float(np.triu(inverse, 1).sum())
    gradient = -(differences * inverse[:, :, None] ** 3).sum(axis=1)
    return energy, gradient


def objective(parameters: np.ndarray, base: np.ndarray, basis: np.ndarray) -> tuple[float, np.ndarray]:
    points, norms = map_parameters(parameters, base, basis)
    energy, gradient = energy_gradient(points)
    tangent_gradient = gradient - np.sum(gradient * points, axis=1, keepdims=True) * points
    raw_gradient = tangent_gradient / norms
    parameter_gradient = np.einsum("nik,nk->ni", basis, raw_gradient)
    return energy, parameter_gradient.ravel()


def projected_gradient_norm(points: np.ndarray) -> tuple[float, float]:
    _, gradient = energy_gradient(points)
    tangent = gradient - np.sum(gradient * points, axis=1, keepdims=True) * points
    norms = np.linalg.norm(tangent, axis=1)
    return float(np.max(norms)), float(np.linalg.norm(tangent))


def parse_floats(value: str) -> list[float]:
    return [float(item) for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--kick-scales", type=parse_floats, default=parse_floats("0,1e-8,3e-8,1e-7,3e-7,1e-6"))
    parser.add_argument("--maxiter", type=int, default=300)
    parser.add_argument("--maxfun", type=int, default=1000)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    args = parser.parse_args()

    problem = get(f"/api/problems/{SLUG}")
    leaderboard = get("/api/leaderboard", problem_id=PROBLEM_ID, limit=20)
    solutions = get("/api/solutions/best", problem_id=PROBLEM_ID, limit=20)
    assert isinstance(problem, dict) and isinstance(leaderboard, list) and isinstance(solutions, list)
    live_best = float(solutions[0]["score"])
    target = live_best - float(problem["minImprovement"])
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
    seed_points = normalize(np.asarray(solutions[0]["data"]["vectors"], dtype=np.float64))

    namespace: dict[str, object] = {}
    exec(problem["verifier"], namespace)
    evaluate = namespace["evaluate"]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_json(run_dir / "problem.json", problem)
    atomic_json(run_dir / "leaderboard.json", leaderboard)
    atomic_json(run_dir / "best_solutions.json", solutions)
    atomic_json(run_dir / "seed.json", {"vectors": seed_points.tolist()})

    best = seed_points.copy()
    best_score = float(evaluate({"vectors": best.tolist()}))  # type: ignore[operator]
    initial_max_gradient, initial_total_gradient = projected_gradient_norm(best)
    append(
        events,
        {
            "event": "start",
            "live_best": live_best,
            "target": target,
            "normalized_seed_score": best_score,
            "projected_gradient_max": initial_max_gradient,
            "projected_gradient_total": initial_total_gradient,
            "verifier_sha256": verifier_hash,
        },
    )

    rng = np.random.default_rng(args.seed)
    accepted = 0
    for restart, scale in enumerate(args.kick_scales):
        base = seed_points.copy()
        basis = tangent_basis(base)
        if scale:
            kick = rng.normal(scale=scale, size=(COUNT, 2))
            base = normalize(base + np.einsum("nik,ni->nk", basis, kick))
            basis = tangent_basis(base)
        result = minimize(
            objective,
            np.zeros(2 * COUNT),
            args=(base, basis),
            method="L-BFGS-B",
            jac=True,
            options={
                "maxiter": args.maxiter,
                "maxfun": args.maxfun,
                "maxls": 50,
                "ftol": 1e-15,
                "gtol": 1e-12,
                "maxcor": 30,
            },
        )
        candidate = normalize(map_parameters(result.x, base, basis)[0])
        score = float(evaluate({"vectors": candidate.tolist()}))  # type: ignore[operator]
        maximum_gradient, total_gradient = projected_gradient_norm(candidate)
        append(
            events,
            {
                "event": "restart_end",
                "restart": restart,
                "kick_scale": scale,
                "score": score,
                "improvement_over_live": live_best - score,
                "iterations": int(result.nit),
                "evaluations": int(result.nfev),
                "success": bool(result.success),
                "status": int(result.status),
                "message": str(result.message),
                "projected_gradient_max": maximum_gradient,
                "projected_gradient_total": total_gradient,
            },
        )
        if score < best_score:
            best, best_score = candidate.copy(), score
            accepted += 1
            atomic_json(run_dir / "best.json", {"vectors": best.tolist()})
            atomic_json(run_dir / f"checkpoint_{accepted:03d}.json", {"vectors": best.tolist()})

    if accepted == 0:
        atomic_json(run_dir / "best.json", {"vectors": best.tolist()})
    norms = np.linalg.norm(best, axis=1)
    final_max_gradient, final_total_gradient = projected_gradient_norm(best)
    summary = {
        "slug": SLUG,
        "verifier_sha256": verifier_hash,
        "live_best": live_best,
        "target": target,
        "official_verifier_score": best_score,
        "improvement_over_live": live_best - best_score,
        "gate_clearing": best_score < target,
        "accepted_checkpoints": accepted,
        "norm_min": float(norms.min()),
        "norm_max": float(norms.max()),
        "finite_nonzero": bool(np.isfinite(best).all() and np.all(norms > 0.0)),
        "initial_projected_gradient_max": initial_max_gradient,
        "initial_projected_gradient_total": initial_total_gradient,
        "final_projected_gradient_max": final_max_gradient,
        "final_projected_gradient_total": final_total_gradient,
        "payload": str((run_dir / "best.json").resolve()),
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
