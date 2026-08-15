#!/usr/bin/env python3
"""Strict-domain search for 26 circles in the unit square.

The official verifier permits 1e-9 overlaps, but this campaign deliberately
requires nonnegative wall and pair slack before a candidate can be accepted.
"""

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
SLUG = "circle-packing"
PROBLEM_ID = 14


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


def metrics(circles: np.ndarray) -> dict[str, float | bool]:
    centers, radii = circles[:, :2], circles[:, 2]
    wall_slack = np.min(
        np.column_stack(
            (
                centers[:, 0] - radii,
                1.0 - centers[:, 0] - radii,
                centers[:, 1] - radii,
                1.0 - centers[:, 1] - radii,
            )
        )
    )
    pair_slack = min(
        np.linalg.norm(centers[i] - centers[j]) - radii[i] - radii[j]
        for i in range(len(circles))
        for j in range(i + 1, len(circles))
    )
    return {
        "score": float(radii.sum()),
        "min_radius": float(radii.min()),
        "min_wall_slack": float(wall_slack),
        "min_pair_slack": float(pair_slack),
        "strict_valid": bool(
            np.isfinite(circles).all()
            and radii.min() > 0.0
            and wall_slack >= 0.0
            and pair_slack >= 0.0
        ),
    }


def radii_lp(centers: np.ndarray, safety: float) -> np.ndarray | None:
    count = len(centers)
    rows = []
    rhs = []
    for i in range(count):
        for j in range(i + 1, count):
            row = np.zeros(count)
            row[i] = row[j] = 1.0
            rows.append(row)
            rhs.append(np.linalg.norm(centers[i] - centers[j]) - safety)
    caps = (
        np.column_stack(
            (
                centers[:, 0],
                1.0 - centers[:, 0],
                centers[:, 1],
                1.0 - centers[:, 1],
            )
        ).min(axis=1)
        - safety
    )
    if np.any(caps <= 1e-14):
        return None
    result = linprog(
        -np.ones(count),
        A_ub=np.asarray(rows),
        b_ub=np.asarray(rhs),
        bounds=[(1e-14, float(cap)) for cap in caps],
        method="highs",
        options={
            "primal_feasibility_tolerance": 1e-10,
            "dual_feasibility_tolerance": 1e-10,
        },
    )
    return result.x if result.success else None


def strict_repair(centers: np.ndarray, safety: float) -> np.ndarray | None:
    radii = radii_lp(centers, safety)
    if radii is None:
        return None
    circles = np.column_stack((centers, radii))
    report = metrics(circles)
    if report["strict_valid"]:
        return circles
    # HiGHS feasibility tolerances can dominate very small safety margins.
    # A global radius decrement gives an explicit, deterministic certificate.
    deficit = max(0.0, -float(report["min_pair_slack"]) / 2.0, -float(report["min_wall_slack"]))
    circles[:, 2] -= deficit + max(safety, 2e-15)
    return circles if metrics(circles)["strict_valid"] else None


def slp_centers(circles: np.ndarray, trust: float, safety: float) -> np.ndarray | None:
    centers = circles[:, :2]
    count = len(circles)
    # Variables are dx_i, dy_i (2n) followed by new radii (n).
    variable_count = 3 * count
    constraints = lil_matrix((4 * count + count * (count - 1) // 2, variable_count))
    rhs = np.empty(constraints.shape[0])
    row_id = 0
    for i, (x, y) in enumerate(centers):
        dx, dy, radius = 2 * i, 2 * i + 1, 2 * count + i
        for delta_index, coefficient, bound in (
            (dx, -1.0, x - safety),
            (dx, 1.0, 1.0 - x - safety),
            (dy, -1.0, y - safety),
            (dy, 1.0, 1.0 - y - safety),
        ):
            constraints[row_id, delta_index] = coefficient
            constraints[row_id, radius] = 1.0
            rhs[row_id] = bound
            row_id += 1
    for i in range(count):
        for j in range(i + 1, count):
            delta = centers[i] - centers[j]
            distance = np.linalg.norm(delta)
            direction = delta / distance
            constraints[row_id, 2 * i : 2 * i + 2] = -direction
            constraints[row_id, 2 * j : 2 * j + 2] = direction
            constraints[row_id, 2 * count + i] = 1.0
            constraints[row_id, 2 * count + j] = 1.0
            rhs[row_id] = distance - safety
            row_id += 1
    objective = np.concatenate((np.zeros(2 * count), -np.ones(count)))
    result = linprog(
        objective,
        A_ub=constraints.tocsr(),
        b_ub=rhs,
        bounds=[(-trust, trust)] * (2 * count) + [(1e-14, None)] * count,
        method="highs",
        options={
            "primal_feasibility_tolerance": 1e-10,
            "dual_feasibility_tolerance": 1e-10,
        },
    )
    if not result.success:
        return None
    moved = centers + result.x[: 2 * count].reshape(count, 2)
    return strict_repair(moved, safety)


def topology(circles: np.ndarray, tolerance: float = 1e-7) -> tuple[tuple[int, int], ...]:
    centers, radii = circles[:, :2], circles[:, 2]
    contacts = []
    for i in range(len(circles)):
        for j in range(i + 1, len(circles)):
            if np.linalg.norm(centers[i] - centers[j]) - radii[i] - radii[j] <= tolerance:
                contacts.append((i, j))
    return tuple(contacts)


def geometry_fingerprint(centers: np.ndarray, decimals: int = 5) -> tuple[float, ...]:
    """Square-symmetry/permutation invariant coarse key for public seeds."""
    pair_distances = sorted(
        np.linalg.norm(centers[i] - centers[j])
        for i in range(len(centers))
        for j in range(i + 1, len(centers))
    )
    wall_distances = sorted(
        np.concatenate(
            (
                centers[:, 0],
                1.0 - centers[:, 0],
                centers[:, 1],
                1.0 - centers[:, 1],
            )
        )
    )
    return tuple(np.round(np.concatenate((pair_distances, wall_distances)), decimals))


def parse_floats(value: str) -> list[float]:
    return [float(item) for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restarts", type=int, default=24)
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--source-count", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260814)
    parser.add_argument("--scales", type=parse_floats, default=parse_floats("1e-4,3e-4,1e-3,3e-3"))
    parser.add_argument("--trusts", type=parse_floats, default=parse_floats("1e-5,3e-5,1e-4,3e-4,1e-3"))
    parser.add_argument("--safety", type=float, default=1e-13)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    args = parser.parse_args()

    problem = get(f"/api/problems/{SLUG}")
    leaderboard = get("/api/leaderboard", problem_id=PROBLEM_ID, limit=20)
    solutions = get("/api/solutions/best", problem_id=PROBLEM_ID, limit=100)
    assert isinstance(problem, dict) and isinstance(leaderboard, list) and isinstance(solutions, list)
    live_best = float(solutions[0]["score"])
    target = live_best + float(problem["minImprovement"])
    sources = []
    seen_fingerprints: set[tuple[float, ...]] = set()
    for solution in solutions:
        circles = np.asarray(solution["data"]["circles"], dtype=np.float64)
        if circles.shape != (26, 3) or not np.isfinite(circles).all():
            continue
        repaired = strict_repair(circles[:, :2], args.safety)
        fingerprint = geometry_fingerprint(circles[:, :2])
        if repaired is None or fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)
        sources.append(
            {
                "solution": solution,
                "original": circles,
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
            # Move a reproducible 2-6 circle block; this is large enough to
            # change local contacts but small enough for strict LP repair.
            block_size = 2 + (restart + source_cycle) % 5
            chosen = rng.choice(len(centers), size=block_size, replace=False)
            centers[chosen] += rng.normal(scale=scale, size=(block_size, 2))
            centers = np.clip(centers, 1e-6, 1.0 - 1e-6)
        current = strict_repair(centers, args.safety)
        if current is None:
            append(
                events,
                {
                    "event": "restart_invalid",
                    "restart": restart,
                    "source_id": source["solution"]["id"],
                    "scale": scale,
                },
            )
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
                "topology_contacts": len(topology(current)),
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
