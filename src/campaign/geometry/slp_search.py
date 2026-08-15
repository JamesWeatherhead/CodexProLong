#!/usr/bin/env python3
"""Checkpointed sequential-linear-programming search for kissing frontiers.

The search stays inside the intended geometry: every row is nonzero and is
explicitly normalized to the unit sphere before it is scored.  It never calls
mutating EinsteinArena endpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csr_matrix, lil_matrix


BASE = "https://einsteinarena.com"
PROBLEMS = {
    "kissing-number-d11-605": 24,
    "kissing-number-d12-842": 25,
}


def fetch_json(path: str, **params: object) -> object:
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


def append_event(path: Path, event: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def normalize(rows: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or np.any(norms <= 1e-14):
        raise ValueError("candidate contains a non-finite or zero vector")
    return rows / norms


def pair_table(rows: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    left: list[np.ndarray] = []
    right: list[np.ndarray] = []
    distances: list[np.ndarray] = []
    count = len(rows)
    for i in range(count - 1):
        js = np.arange(i + 1, count, dtype=np.int32)
        ds = np.linalg.norm(rows[i] - rows[i + 1 :], axis=1)
        left.append(np.full(len(js), i, dtype=np.int32))
        right.append(js)
        distances.append(ds)
    return np.concatenate(left), np.concatenate(right), np.concatenate(distances)


def float_loss(rows: np.ndarray) -> float:
    _, _, distances = pair_table(rows)
    return float(np.maximum(0.0, 2.0 - 2.0 * distances).sum())


def exact_score(problem: dict[str, object], payload: dict[str, object]) -> float:
    namespace: dict[str, object] = {}
    exec(str(problem["verifier"]), namespace)
    evaluate = namespace["evaluate"]
    return float(evaluate(payload))  # type: ignore[operator]


def choose_movable(
    slug: str,
    left: np.ndarray,
    right: np.ndarray,
    distances: np.ndarray,
    active_epsilon: float,
    strategy: str,
) -> np.ndarray:
    if strategy == "all":
        return np.arange(int(max(right)) + 1, dtype=np.int32)
    if strategy == "extra" or (strategy == "auto" and slug == "kissing-number-d11-605"):
        # The public construction is the 604-record plus one attempted point.
        # Preserve the proven 604-point frame and optimize only that extra row.
        return np.array([604], dtype=np.int32)
    penalties = 2.0 - 2.0 * distances
    mask = penalties > active_epsilon
    return np.unique(np.concatenate((left[mask], right[mask]))).astype(np.int32)


def slp_step(
    rows: np.ndarray,
    movable: np.ndarray,
    margin: float,
    trust: float,
    time_limit: float,
) -> tuple[np.ndarray | None, dict[str, object]]:
    left, right, distances = pair_table(rows)
    movable_lookup = {int(point): offset for offset, point in enumerate(movable)}
    incident = np.fromiter(
        (int(i) in movable_lookup or int(j) in movable_lookup for i, j in zip(left, right)),
        dtype=bool,
        count=len(left),
    )
    relevant = incident & (distances < 1.0 + margin)
    pair_ids = np.flatnonzero(relevant)
    q, dimension, pair_count = len(movable), rows.shape[1], len(pair_ids)
    if pair_count == 0:
        return None, {"status": "no_relevant_pairs"}

    variable_count = q * dimension + pair_count
    inequalities = lil_matrix((pair_count, variable_count), dtype=np.float64)
    bounds_rhs = np.empty(pair_count, dtype=np.float64)

    for local_pair, pair_id in enumerate(pair_ids):
        i, j, distance = int(left[pair_id]), int(right[pair_id]), distances[pair_id]
        derivative = -2.0 * (rows[i] - rows[j]) / distance
        # Movement variables are scaled to [-1, 1], avoiding HiGHS treating a
        # tiny physical trust region as numerical zero.
        derivative *= trust
        if i in movable_lookup:
            offset = movable_lookup[i] * dimension
            inequalities[local_pair, offset : offset + dimension] = derivative
        if j in movable_lookup:
            offset = movable_lookup[j] * dimension
            inequalities[local_pair, offset : offset + dimension] = -derivative
        inequalities[local_pair, q * dimension + local_pair] = -1.0
        bounds_rhs[local_pair] = -(2.0 - 2.0 * distance)

    tangencies = lil_matrix((q, variable_count), dtype=np.float64)
    for local_point, point in enumerate(movable):
        offset = local_point * dimension
        tangencies[local_point, offset : offset + dimension] = rows[point]

    objective = np.concatenate((np.zeros(q * dimension), np.ones(pair_count)))
    result = linprog(
        objective,
        A_ub=csr_matrix(inequalities),
        b_ub=bounds_rhs,
        A_eq=csr_matrix(tangencies),
        b_eq=np.zeros(q),
        bounds=[(-1.0, 1.0)] * (q * dimension) + [(0.0, None)] * pair_count,
        method="highs",
        options={
            "time_limit": time_limit,
            "primal_feasibility_tolerance": 1e-10,
            "dual_feasibility_tolerance": 1e-10,
        },
    )
    diagnostics: dict[str, object] = {
        "status": str(result.message),
        "success": bool(result.success),
        "movable_points": q,
        "relevant_pairs": pair_count,
        "trust": trust,
        "margin": margin,
        "solver_objective": float(result.fun) if result.fun is not None else None,
    }
    if not result.success:
        return None, diagnostics

    movement = trust * result.x[: q * dimension].reshape(q, dimension)
    candidate = rows.copy()
    candidate[movable] += movement
    candidate = normalize(candidate)
    diagnostics["max_coordinate_step"] = float(np.max(np.abs(movement)))
    return candidate, diagnostics


def parse_trusts(value: str) -> list[float]:
    trusts = [float(item) for item in value.split(",") if item.strip()]
    if not trusts or any(item <= 0 for item in trusts):
        raise argparse.ArgumentTypeError("trusts must be positive comma-separated floats")
    return trusts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", choices=sorted(PROBLEMS))
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--margin", type=float, default=1e-5)
    parser.add_argument("--active-epsilon", type=float, default=1e-12)
    parser.add_argument(
        "--movable-strategy",
        choices=("auto", "extra", "violations", "all"),
        default="auto",
    )
    parser.add_argument("--trusts", type=parse_trusts, default=parse_trusts("3e-7,1e-6,3e-6,1e-5,3e-5"))
    parser.add_argument("--lp-time-limit", type=float, default=30.0)
    parser.add_argument("--seed-payload", type=Path)
    parser.add_argument("--run-root", type=Path, default=Path(__file__).parent / "runs")
    args = parser.parse_args()

    problem = fetch_json(f"/api/problems/{args.slug}")
    problem_id = PROBLEMS[args.slug]
    leaderboard = fetch_json("/api/leaderboard", problem_id=problem_id, limit=20)
    solutions = fetch_json("/api/solutions/best", problem_id=problem_id, limit=5)
    assert isinstance(problem, dict) and isinstance(leaderboard, list) and isinstance(solutions, list)
    leader = solutions[0]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root / stamp / args.slug
    run_dir.mkdir(parents=True, exist_ok=False)
    events_path = run_dir / "events.jsonl"
    verifier_hash = hashlib.sha256(str(problem["verifier"]).encode()).hexdigest()
    atomic_json(run_dir / "problem.json", problem)
    atomic_json(run_dir / "leaderboard.json", leaderboard)
    atomic_json(run_dir / "best_solutions.json", solutions)

    if args.seed_payload is None:
        seed_data = leader["data"]
        seed_source = f"live solution {leader['id']}"
    else:
        with args.seed_payload.open(encoding="utf-8") as handle:
            seed_data = json.load(handle)
        seed_source = str(args.seed_payload.resolve())
    rows = normalize(np.asarray(seed_data["vectors"], dtype=np.float64))
    payload: dict[str, object] = {"vectors": rows.tolist()}
    best_float = float_loss(rows)
    best_exact = exact_score(problem, payload)
    live_best = float(leader["score"])
    atomic_json(run_dir / "seed.json", payload)
    atomic_json(run_dir / "best.json", payload)
    append_event(
        events_path,
        {
            "event": "start",
            "slug": args.slug,
            "live_best": live_best,
            "seed_float_score": best_float,
            "seed_exact_score": best_exact,
            "seed_source": seed_source,
            "verifier_sha256": verifier_hash,
        },
    )

    accepted = 0
    for round_index in range(args.rounds):
        left, right, distances = pair_table(rows)
        movable = choose_movable(
            args.slug,
            left,
            right,
            distances,
            args.active_epsilon,
            args.movable_strategy,
        )
        round_best: tuple[float, np.ndarray, dict[str, object]] | None = None
        for trust in args.trusts:
            candidate, diagnostics = slp_step(
                rows,
                movable,
                margin=args.margin,
                trust=trust,
                time_limit=args.lp_time_limit,
            )
            candidate_float = float_loss(candidate) if candidate is not None else float("inf")
            diagnostics.update(
                {
                    "event": "trial",
                    "round": round_index,
                    "candidate_float_score": candidate_float,
                    "incumbent_float_score": best_float,
                }
            )
            append_event(events_path, diagnostics)
            if candidate is not None and candidate_float < best_float - 1e-14:
                if round_best is None or candidate_float < round_best[0]:
                    round_best = (candidate_float, candidate, diagnostics)

        if round_best is None:
            append_event(events_path, {"event": "stalled", "round": round_index})
            break

        candidate_float, candidate, diagnostics = round_best
        candidate_payload: dict[str, object] = {"vectors": candidate.tolist()}
        candidate_exact = exact_score(problem, candidate_payload)
        if candidate_exact >= best_exact:
            append_event(
                events_path,
                {
                    "event": "exact_reject",
                    "round": round_index,
                    "candidate_float_score": candidate_float,
                    "candidate_exact_score": candidate_exact,
                    "incumbent_exact_score": best_exact,
                },
            )
            break

        rows, payload = candidate, candidate_payload
        best_float, best_exact = candidate_float, candidate_exact
        accepted += 1
        atomic_json(run_dir / "best.json", payload)
        atomic_json(run_dir / f"checkpoint_{accepted:03d}.json", payload)
        append_event(
            events_path,
            {
                "event": "accept",
                "round": round_index,
                "float_score": best_float,
                "exact_score": best_exact,
                "live_best": live_best,
                "improvement": live_best - best_exact,
                "trust": diagnostics["trust"],
            },
        )

    summary = {
        "slug": args.slug,
        "problem_id": problem_id,
        "verifier_sha256": verifier_hash,
        "live_best_at_start": live_best,
        "seed_source": seed_source,
        "best_float_score": best_float,
        "best_exact_score": best_exact,
        "improvement_over_live_best": live_best - best_exact,
        "gate_clearing": best_exact < live_best,
        "accepted_steps": accepted,
        "payload": str((run_dir / "best.json").resolve()),
        "events": str(events_path.resolve()),
        "reproduce": f"{sys.executable} {Path(__file__).with_name('verify_payload.py')} {args.slug} {(run_dir / 'best.json').resolve()}",
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
