#!/usr/bin/env python3
"""Strict-domain active-set search for 21 circles in a perimeter-4 rectangle."""

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
from scipy.optimize import linprog
from scipy.sparse import lil_matrix


BASE = "https://einsteinarena.com"
SLUG = "circles-rectangle"
PROBLEM_ID = 18
COUNT = 21


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


def normalize_origin(circles: np.ndarray) -> np.ndarray:
    normalized = circles.copy()
    normalized[:, 0] -= np.min(circles[:, 0] - circles[:, 2])
    normalized[:, 1] -= np.min(circles[:, 1] - circles[:, 2])
    return normalized


def metrics(circles: np.ndarray) -> dict[str, float | bool]:
    centers, radii = circles[:, :2], circles[:, 2]
    width = np.max(centers[:, 0] + radii) - np.min(centers[:, 0] - radii)
    height = np.max(centers[:, 1] + radii) - np.min(centers[:, 1] - radii)
    pair_slack = min(
        np.linalg.norm(centers[i] - centers[j]) - radii[i] - radii[j]
        for i in range(len(circles))
        for j in range(i + 1, len(circles))
    )
    perimeter_slack = 2.0 - width - height
    return {
        "score": float(radii.sum()),
        "min_radius": float(radii.min()),
        "width": float(width),
        "height": float(height),
        "perimeter_slack": float(perimeter_slack),
        "min_pair_slack": float(pair_slack),
        "strict_valid": bool(
            np.isfinite(circles).all()
            and radii.min() > 0.0
            and perimeter_slack >= 0.0
            and pair_slack >= 0.0
        ),
    }


def radii_lp(centers: np.ndarray, safety: float) -> np.ndarray | None:
    # Variables: radii, enclosing width, enclosing height. Translation is fixed
    # by placing the lower and left sides at zero.
    variable_count = COUNT + 2
    width_id, height_id = COUNT, COUNT + 1
    rows: list[np.ndarray] = []
    rhs: list[float] = []
    for i, (x, y) in enumerate(centers):
        for dimension, extent_id in ((x, width_id), (y, height_id)):
            lower = np.zeros(variable_count)
            lower[i] = 1.0
            rows.append(lower)
            rhs.append(float(dimension - safety))
            upper = np.zeros(variable_count)
            upper[i] = 1.0
            upper[extent_id] = -1.0
            rows.append(upper)
            rhs.append(float(-dimension - safety))
    for i in range(COUNT):
        for j in range(i + 1, COUNT):
            row = np.zeros(variable_count)
            row[i] = row[j] = 1.0
            rows.append(row)
            rhs.append(float(np.linalg.norm(centers[i] - centers[j]) - safety))
    perimeter = np.zeros(variable_count)
    perimeter[width_id] = perimeter[height_id] = 1.0
    rows.append(perimeter)
    rhs.append(2.0 - safety)
    objective = np.concatenate((-np.ones(COUNT), np.zeros(2)))
    result = linprog(
        objective,
        A_ub=np.asarray(rows),
        b_ub=np.asarray(rhs),
        bounds=[(1e-14, None)] * COUNT + [(1e-14, 2.0)] * 2,
        method="highs",
        options={
            "primal_feasibility_tolerance": 1e-10,
            "dual_feasibility_tolerance": 1e-10,
        },
    )
    return result.x[:COUNT] if result.success else None


def strict_repair(centers: np.ndarray, safety: float) -> np.ndarray | None:
    radii = radii_lp(centers, safety)
    if radii is None:
        return None
    circles = np.column_stack((centers, radii))
    report = metrics(circles)
    if report["strict_valid"]:
        return normalize_origin(circles)
    decrement = max(
        0.0,
        -float(report["min_pair_slack"]) / 2.0,
        -float(report["perimeter_slack"]) / 4.0,
    )
    circles[:, 2] -= decrement + max(safety, 2e-15)
    if np.min(circles[:, 2]) <= 0.0 or not metrics(circles)["strict_valid"]:
        return None
    return normalize_origin(circles)


def slp_centers(circles: np.ndarray, trust: float, safety: float) -> np.ndarray | None:
    circles = normalize_origin(circles)
    centers = circles[:, :2]
    # Variables: dx,dy for each center; new radii; width; height.
    variable_count = 3 * COUNT + 2
    radius_start, width_id, height_id = 2 * COUNT, 3 * COUNT, 3 * COUNT + 1
    row_count = 4 * COUNT + COUNT * (COUNT - 1) // 2 + 1
    constraints = lil_matrix((row_count, variable_count))
    rhs = np.empty(row_count)
    row_id = 0
    for i, (x, y) in enumerate(centers):
        dx, dy, radius = 2 * i, 2 * i + 1, radius_start + i
        for delta_id, delta_coefficient, extent_id, bound in (
            (dx, -1.0, None, x - safety),
            (dx, 1.0, width_id, -x - safety),
            (dy, -1.0, None, y - safety),
            (dy, 1.0, height_id, -y - safety),
        ):
            constraints[row_id, delta_id] = delta_coefficient
            constraints[row_id, radius] = 1.0
            if extent_id is not None:
                constraints[row_id, extent_id] = -1.0
            rhs[row_id] = bound
            row_id += 1
    for i in range(COUNT):
        for j in range(i + 1, COUNT):
            delta = centers[i] - centers[j]
            distance = np.linalg.norm(delta)
            direction = delta / distance
            constraints[row_id, 2 * i : 2 * i + 2] = -direction
            constraints[row_id, 2 * j : 2 * j + 2] = direction
            constraints[row_id, radius_start + i] = 1.0
            constraints[row_id, radius_start + j] = 1.0
            rhs[row_id] = distance - safety
            row_id += 1
    constraints[row_id, width_id] = constraints[row_id, height_id] = 1.0
    rhs[row_id] = 2.0 - safety

    objective = np.concatenate((np.zeros(2 * COUNT), -np.ones(COUNT), np.zeros(2)))
    result = linprog(
        objective,
        A_ub=constraints.tocsr(),
        b_ub=rhs,
        bounds=[(-trust, trust)] * (2 * COUNT)
        + [(1e-14, None)] * COUNT
        + [(1e-14, 2.0)] * 2,
        method="highs",
        options={
            "primal_feasibility_tolerance": 1e-10,
            "dual_feasibility_tolerance": 1e-10,
        },
    )
    if not result.success:
        return None
    moved = centers + result.x[: 2 * COUNT].reshape(COUNT, 2)
    return strict_repair(moved, safety)


def geometry_fingerprint(centers: np.ndarray, decimals: int = 5) -> tuple[float, ...]:
    distances = sorted(
        np.linalg.norm(centers[i] - centers[j])
        for i in range(COUNT)
        for j in range(i + 1, COUNT)
    )
    return tuple(np.round(distances, decimals))


def topology(circles: np.ndarray, tolerance: float = 1e-7) -> tuple[tuple[int, int], ...]:
    centers, radii = circles[:, :2], circles[:, 2]
    return tuple(
        (i, j)
        for i in range(COUNT)
        for j in range(i + 1, COUNT)
        if np.linalg.norm(centers[i] - centers[j]) - radii[i] - radii[j] <= tolerance
    )


def boundary_contacts(circles: np.ndarray, tolerance: float = 1e-7) -> int:
    x, y, radii = circles[:, 0], circles[:, 1], circles[:, 2]
    left, right = np.min(x - radii), np.max(x + radii)
    bottom, top = np.min(y - radii), np.max(y + radii)
    slacks = np.column_stack((x - radii - left, right - x - radii, y - radii - bottom, top - y - radii))
    return int(np.sum(slacks <= tolerance))


def parse_floats(value: str) -> list[float]:
    return [float(item) for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-count", type=int, default=8)
    parser.add_argument("--restarts", type=int, default=24)
    parser.add_argument("--rounds", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--scales", type=parse_floats, default=parse_floats("1e-4,3e-4,1e-3,3e-3"))
    parser.add_argument("--trusts", type=parse_floats, default=parse_floats("1e-5,3e-5,1e-4,3e-4,1e-3"))
    parser.add_argument("--safety", type=float, default=1e-13)
    parser.add_argument("--seed-payload", type=Path)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    args = parser.parse_args()

    problem = get(f"/api/problems/{SLUG}")
    leaderboard = get("/api/leaderboard", problem_id=PROBLEM_ID, limit=20)
    solutions = get("/api/solutions/best", problem_id=PROBLEM_ID, limit=100)
    assert isinstance(problem, dict) and isinstance(leaderboard, list) and isinstance(solutions, list)
    live_best = float(solutions[0]["score"])
    target = live_best + float(problem["minImprovement"])

    source_candidates = list(solutions)
    if args.seed_payload is not None:
        with args.seed_payload.open(encoding="utf-8") as handle:
            local_data = json.load(handle)
        local_circles = np.asarray(local_data["circles"], dtype=np.float64)
        source_candidates.insert(
            0,
            {
                "id": "local",
                "agentName": "local-checkpoint",
                "score": float(local_circles[:, 2].sum()),
                "data": {"circles": local_circles.tolist()},
            },
        )

    sources = []
    fingerprints: set[tuple[float, ...]] = set()
    for solution in source_candidates:
        original = normalize_origin(np.asarray(solution["data"]["circles"], dtype=np.float64))
        if original.shape != (COUNT, 3) or not np.isfinite(original).all():
            continue
        fingerprint = geometry_fingerprint(original[:, :2])
        repaired = strict_repair(original[:, :2], args.safety)
        if repaired is None or fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        sources.append(
            {
                "solution": solution,
                "original": original,
                "repaired": repaired,
                "repaired_metrics": metrics(repaired),
            }
        )
        if len(sources) >= args.source_count:
            break
    if not sources:
        raise RuntimeError("no repairable public seed centers")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / SLUG
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    atomic_json(run_dir / "problem.json", problem)
    atomic_json(run_dir / "leaderboard.json", leaderboard)
    atomic_json(run_dir / "best_solutions.json", solutions)
    verifier_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()

    best_source = max(sources, key=lambda item: float(item["repaired_metrics"]["score"]))
    best = np.asarray(best_source["repaired"]).copy()
    best_report = metrics(best)
    atomic_json(
        run_dir / "sources.json",
        [
            {
                "solution_id": source["solution"]["id"],
                "agent_name": source["solution"].get("agentName"),
                "public_score": source["solution"]["score"],
                "repaired_metrics": source["repaired_metrics"],
                "circles": source["original"].tolist(),
            }
            for source in sources
        ],
    )
    atomic_json(run_dir / "best.json", {"circles": best.tolist()})
    append(
        events,
        {
            "event": "start",
            "live_best": live_best,
            "target": target,
            "source_count": len(sources),
            "best_source_id": best_source["solution"]["id"],
            "best_source_public_score": best_source["solution"]["score"],
            "repaired_seed": best_report,
            "verifier_sha256": verifier_hash,
        },
    )

    rng = np.random.default_rng(args.seed)
    seen_topologies = {topology(best)}
    accepted = 0
    for restart in range(args.restarts):
        source_index = restart % len(sources)
        source = sources[source_index]
        source_cycle = restart // len(sources)
        scale = args.scales[source_cycle % len(args.scales)]
        centers = np.asarray(source["original"])[:, :2].copy()
        if source_cycle:
            block_size = 2 + (restart + source_cycle) % 5
            chosen = rng.choice(COUNT, size=block_size, replace=False)
            centers[chosen] += rng.normal(scale=scale, size=(block_size, 2))
        current = strict_repair(centers, args.safety)
        if current is None:
            append(events, {"event": "restart_invalid", "restart": restart, "source_id": source["solution"]["id"]})
            continue
        for round_index in range(args.rounds):
            round_best = current
            round_score = float(metrics(current)["score"])
            chosen_trust = None
            for trust in args.trusts:
                candidate = slp_centers(current, trust, args.safety)
                report = metrics(candidate) if candidate is not None else {"strict_valid": False, "score": -np.inf}
                append(
                    events,
                    {
                        "event": "trial",
                        "restart": restart,
                        "source_id": source["solution"]["id"],
                        "round": round_index,
                        "scale": scale,
                        "trust": trust,
                        **report,
                    },
                )
                if report["strict_valid"] and float(report["score"]) > round_score + 1e-14:
                    round_best, round_score, chosen_trust = candidate, float(report["score"]), trust
            if chosen_trust is None:
                break
            current = round_best
            seen_topologies.add(topology(current))

        report = metrics(current)
        append(
            events,
            {
                "event": "restart_end",
                "restart": restart,
                "source_id": source["solution"]["id"],
                "scale": scale,
                "pair_contacts": len(topology(current)),
                "boundary_contacts": boundary_contacts(current),
                "distinct_topologies": len(seen_topologies),
                **report,
            },
        )
        if report["strict_valid"] and float(report["score"]) > float(best_report["score"]) + 1e-14:
            best, best_report = current.copy(), report
            accepted += 1
            atomic_json(run_dir / "best.json", {"circles": best.tolist()})
            atomic_json(run_dir / f"checkpoint_{accepted:03d}.json", {"circles": best.tolist()})

    namespace: dict[str, object] = {}
    exec(problem["verifier"], namespace)
    official_score = float(namespace["evaluate"]({"circles": best.tolist()}))  # type: ignore[operator]
    summary = {
        "slug": SLUG,
        "verifier_sha256": verifier_hash,
        "live_best": live_best,
        "target": target,
        "official_verifier_score": official_score,
        "strict_metrics": best_report,
        "gate_clearing": bool(best_report["strict_valid"] and official_score > target),
        "shortfall_to_target": target - official_score,
        "accepted_global_checkpoints": accepted,
        "source_count": len(sources),
        "distinct_contact_topologies": len(seen_topologies),
        "payload": str((run_dir / "best.json").resolve()),
        "events": str(events.resolve()),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
