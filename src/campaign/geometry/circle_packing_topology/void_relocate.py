#!/usr/bin/env python3
"""Deterministic PAS-PCI-style topology escapes for 26 circles in a square.

This is a local search tool only.  It removes pain-ranked circles, computes
empty action spaces against the remaining packing, and generates both single
relocations and two-circle split-neighbor relocations.  Each seed is repaired
and locally optimized by strict-domain sequential LP before any rigid active
system is solved at the literal verifier tolerance.  Downloaded verifier code
is never imported or executed; the best payload must be replayed with
``./arena verify``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from circle_packing_search import metrics as strict_metrics  # noqa: E402
from circle_packing_search import slp_centers, strict_repair  # noqa: E402
from continue_contacts import (  # noqa: E402
    ALL_CONSTRAINTS,
    COUNT,
    CORPUS_SHA256,
    GATE,
    LEADER_SCORE,
    PAIR_TOLERANCE,
    TARGET,
    VARIABLES,
    VERIFIER_SHA256,
    Constraint,
    canonical_signature,
    circles_to_values,
    constraint_jacobian,
    constraint_values,
    decode_active,
    load_corpus_solution,
    metrics,
    sha256_file,
    solve_targets,
    values_to_circles,
    verifier_buffer,
)


PAPER_ALPHAEVOLVE = (
    "https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L513-L516"
)
PAPER_PAS_PCI = (
    "https://paperclip.gxl.ai/citations/papers/"
    "arx_1701.00541#L76-L80,L84,L87-L93,L123-L126"
)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def append_event(path: Path, value: Any) -> None:
    line = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def action_clearance(point: np.ndarray, circles: np.ndarray, excluded: set[int]) -> float:
    x, y = float(point[0]), float(point[1])
    if not (0 <= x <= 1 and 0 <= y <= 1):
        return -1.0
    clearance = min(x, 1 - x, y, 1 - y)
    for index, circle in enumerate(circles):
        if index in excluded:
            continue
        clearance = min(clearance, float(np.linalg.norm(point - circle[:2]) - circle[2]))
    return clearance


@dataclass(frozen=True)
class ActionSpace:
    center: tuple[float, float]
    clearance: float


def action_spaces(
    circles: np.ndarray,
    excluded: set[int],
    grid_size: int,
    requested: int,
    reject_centers: list[np.ndarray],
) -> list[ActionSpace]:
    """Approximate the largest empty action spaces, then locally polish them."""
    axis = np.linspace(0.015, 0.985, grid_size)
    ranked: list[tuple[float, np.ndarray]] = []
    for x in axis:
        for y in axis:
            point = np.asarray([x, y])
            ranked.append((action_clearance(point, circles, excluded), point))
    ranked.sort(key=lambda item: item[0], reverse=True)

    starts: list[np.ndarray] = []
    for clearance, point in ranked:
        if clearance <= 1e-4:
            break
        if all(np.linalg.norm(point - prior) >= 0.045 for prior in starts):
            starts.append(point)
        if len(starts) >= max(16, 5 * requested):
            break

    polished: list[ActionSpace] = []
    for start in starts:
        result = minimize(
            lambda point: -action_clearance(point, circles, excluded),
            start,
            method="Nelder-Mead",
            bounds=((1e-9, 1 - 1e-9), (1e-9, 1 - 1e-9)),
            options={"maxiter": 500, "xatol": 1e-12, "fatol": 1e-12},
        )
        point = np.clip(np.asarray(result.x), 1e-9, 1 - 1e-9)
        clearance = action_clearance(point, circles, excluded)
        if clearance <= 1e-6:
            continue
        # The removed circle's old site is a trivial action space and does not
        # change topology, so explicitly suppress its neighborhood.
        if any(np.linalg.norm(point - old) < 0.035 for old in reject_centers):
            continue
        if any(np.linalg.norm(point - np.asarray(item.center)) < 1e-5 for item in polished):
            continue
        polished.append(ActionSpace(tuple(map(float, point)), float(clearance)))
    polished.sort(key=lambda item: item.clearance, reverse=True)
    return polished[:requested]


def pain_ranking(circles: np.ndarray) -> tuple[np.ndarray, list[Constraint], np.ndarray]:
    active = decode_active(circles, 1e-6)
    if len(active) != VARIABLES:
        raise ValueError(f"pain seed needs 78 active constraints, found {len(active)}")
    root = solve_targets(circles_to_values(circles), active)
    if not root.success:
        raise ValueError("failed to solve source active system")
    jacobian = constraint_jacobian(root.values, active, PAIR_TOLERANCE)
    objective = np.zeros(VARIABLES)
    objective[2 * COUNT :] = 1
    multipliers = np.linalg.solve(jacobian.T, -objective)
    # The first-order stationarity equation for each radius makes the *sum* of
    # incident KKT loads identically one at a rigid optimum, so that sum cannot
    # rank circles.  A squared-load concentration score distinguishes circles
    # carrying one or two strong contacts from those whose load is broadly
    # distributed; active degree is a deterministic tie-breaker below.
    pain = np.zeros(COUNT)
    degree = np.zeros(COUNT)
    for multiplier, constraint in zip(multipliers, active):
        load = float(multiplier) ** 2
        pain[constraint[1]] += load
        degree[constraint[1]] += 1
        if constraint[0] == "P":
            pain[int(constraint[2])] += load
            degree[int(constraint[2])] += 1
    pain += degree * 1e-9
    return pain, active, root.values


def select_square_active(values: np.ndarray, tolerance: float = 3e-6) -> list[Constraint] | None:
    """Select 78 independent nearly-tight constraints for rigid refinement."""
    slacks = constraint_values(values, ALL_CONSTRAINTS, 0.0)
    ordered = np.argsort(slacks)
    selected: list[Constraint] = []
    rows: list[np.ndarray] = []
    rank = 0
    for index_value in ordered:
        index = int(index_value)
        if slacks[index] > tolerance:
            break
        constraint = ALL_CONSTRAINTS[index]
        row = constraint_jacobian(values, [constraint], 0.0)[0]
        candidate_rows = rows + [row]
        new_rank = int(np.linalg.matrix_rank(np.asarray(candidate_rows), tol=1e-10))
        if new_rank > rank:
            selected.append(constraint)
            rows.append(row)
            rank = new_rank
        if len(selected) == VARIABLES:
            return selected
    return None


def optimize_seed(
    centers: np.ndarray,
    safety: float,
    trusts: list[float],
    rounds: int,
) -> tuple[np.ndarray | None, dict[str, Any]]:
    current = strict_repair(centers, safety)
    if current is None:
        return None, {"status": "initial_repair_failed"}
    initial = strict_metrics(current)
    accepted_steps = 0
    for _ in range(rounds):
        incumbent = current
        incumbent_score = float(strict_metrics(current)["score"])
        chosen: float | None = None
        for trust in trusts:
            candidate = slp_centers(current, trust, safety)
            if candidate is None:
                continue
            report = strict_metrics(candidate)
            if report["strict_valid"] and float(report["score"]) > incumbent_score + 2e-13:
                incumbent = candidate
                incumbent_score = float(report["score"])
                chosen = trust
        if chosen is None:
            break
        current = incumbent
        accepted_steps += 1
    return current, {
        "status": "optimized",
        "initial_strict": initial,
        "final_strict": strict_metrics(current),
        "accepted_slp_steps": accepted_steps,
    }


def refine_rigid(circles: np.ndarray) -> dict[str, Any]:
    values = circles_to_values(circles)
    active = select_square_active(values)
    if active is None:
        return {"status": "no_78_constraint_rigid_system"}
    strict = solve_targets(values, active, pair_tolerance=0.0, max_evaluations=700)
    if not strict.success:
        return {"status": "strict_root_failed", "residual": strict.residual}
    strict_report = metrics(strict.values, 0.0)
    if not strict_report["accepted_screen"]:
        return {"status": "strict_root_globally_invalid", "strict_report": strict_report}
    full = solve_targets(strict.values, active, pair_tolerance=PAIR_TOLERANCE, max_evaluations=700)
    if not full.success:
        return {"status": "full_root_failed", "residual": full.residual}
    full_report = metrics(full.values, PAIR_TOLERANCE)
    if not full_report["accepted_screen"]:
        return {"status": "full_root_globally_invalid", "full_report": full_report}
    buffered, buffer_steps, buffered_report = verifier_buffer(full.values)
    return {
        "status": "refined",
        "active": active,
        "signature": canonical_signature(active),
        "strict_report": strict_report,
        "full_report": full_report,
        "buffer_steps": buffer_steps,
        "buffered_report": buffered_report,
        "buffered_values": buffered,
    }


def parse_float_list(value: str) -> list[float]:
    return [float(part) for part in value.split(",") if part.strip()]


def parse_ids(value: str) -> list[int]:
    return [int(part) for part in value.split(",") if part.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="append", type=Path, default=[])
    parser.add_argument("--corpus-solution-ids", type=parse_ids, default=[])
    parser.add_argument("--grid-size", type=int, default=35)
    parser.add_argument("--spaces-per-circle", type=int, default=3)
    parser.add_argument("--pain-per-group", type=int, default=1)
    parser.add_argument("--split-pairs", type=int, default=6)
    parser.add_argument("--split-spaces", type=int, default=2)
    parser.add_argument("--split-angles", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=18)
    parser.add_argument(
        "--trusts",
        type=parse_float_list,
        default=parse_float_list("1e-5,3e-5,1e-4,3e-4,1e-3,3e-3,1e-2,3e-2,8e-2"),
    )
    parser.add_argument("--safety", type=float, default=2e-12)
    parser.add_argument("--max-seeds", type=int, default=120)
    parser.add_argument("--stamp", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--campaign-root", type=Path, default=HERE.parents[1])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign = args.campaign_root.resolve()
    latest = json.loads((campaign / "research_corpus" / "latest.json").read_text())
    database = campaign / "research_corpus" / latest["database"]
    if sha256_file(database) != CORPUS_SHA256:
        raise RuntimeError("corpus database hash mismatch")
    run_dir = HERE / "runs" / args.stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    config = {
        "stamp": args.stamp,
        "verifier_sha256": VERIFIER_SHA256,
        "corpus_database_sha256": CORPUS_SHA256,
        "leader_score": LEADER_SCORE,
        "gate": GATE,
        "target_strictly_above": TARGET,
        "pair_tolerance": PAIR_TOLERANCE,
        "grid_size": args.grid_size,
        "spaces_per_circle": args.spaces_per_circle,
        "pain_per_group": args.pain_per_group,
        "split_pairs": args.split_pairs,
        "split_spaces": args.split_spaces,
        "split_angles": args.split_angles,
        "rounds": args.rounds,
        "trusts": args.trusts,
        "safety": args.safety,
        "max_seeds": args.max_seeds,
        "method": "pain-ranked single relocation and split-neighbor action-space relocation",
        "literature": [PAPER_ALPHAEVOLVE, PAPER_PAS_PCI],
    }
    atomic_json(run_dir / "config.json", config)
    append_event(events, {"event": "run_started", **config})

    sources: list[tuple[str, np.ndarray]] = []
    for path in args.seed:
        record = json.loads(path.resolve().read_text())
        sources.append((f"file:{path.resolve()}", np.asarray(record["circles"], dtype=float)))
    for solution_id in args.corpus_solution_ids:
        sources.append((f"corpus_solution:{solution_id}", load_corpus_solution(database, solution_id)))
    if not sources:
        raise ValueError("provide --seed and/or --corpus-solution-ids")

    generated: list[dict[str, Any]] = []
    source_records: list[dict[str, Any]] = []
    for source_name, raw in sources:
        pain, active, root_values = pain_ranking(raw)
        source_circles = values_to_circles(root_values)
        order = np.argsort(source_circles[:, 2])
        groups = [np.asarray(group, dtype=int) for group in np.array_split(order, 4)]
        painful: list[int] = []
        group_records = []
        for group_index, group in enumerate(groups):
            ranked = sorted(map(int, group), key=lambda index: (-pain[index], index))
            chosen = ranked[: args.pain_per_group]
            painful.extend(chosen)
            group_records.append(
                {
                    "group": group_index,
                    "members": list(map(int, group)),
                    "chosen": chosen,
                    "radius_range": [
                        float(np.min(source_circles[group, 2])),
                        float(np.max(source_circles[group, 2])),
                    ],
                }
            )
        source_record = {
            "source": source_name,
            "full_score": float(np.sum(source_circles[:, 2])),
            "active_signature": canonical_signature(active),
            "pain": pain.tolist(),
            "groups": group_records,
        }
        source_records.append(source_record)
        append_event(events, {"event": "source_prepared", **source_record})

        for circle_index in painful:
            spaces = action_spaces(
                source_circles,
                {circle_index},
                args.grid_size,
                args.spaces_per_circle,
                [source_circles[circle_index, :2]],
            )
            for space_index, space in enumerate(spaces):
                centers = source_circles[:, :2].copy()
                centers[circle_index] = np.asarray(space.center)
                generated.append(
                    {
                        "source": source_name,
                        "kind": "single_action_space",
                        "moved": [circle_index],
                        "space_index": space_index,
                        "space": {"center": space.center, "clearance": space.clearance},
                        "centers": centers,
                    }
                )

        ranked_painful = sorted(set(painful), key=lambda index: (-pain[index], index))
        pairs = list(combinations(ranked_painful, 2))[: args.split_pairs]
        for first, second in pairs:
            excluded = {first, second}
            spaces = action_spaces(
                source_circles,
                excluded,
                args.grid_size,
                args.split_spaces,
                [source_circles[first, :2], source_circles[second, :2]],
            )
            separation = float(source_circles[first, 2] + source_circles[second, 2] + 2e-4)
            for space_index, space in enumerate(spaces):
                midpoint = np.asarray(space.center)
                for angle_index in range(args.split_angles):
                    angle = math.pi * angle_index / args.split_angles
                    direction = np.asarray([math.cos(angle), math.sin(angle)])
                    centers = source_circles[:, :2].copy()
                    centers[first] = np.clip(midpoint - 0.5 * separation * direction, 1e-6, 1 - 1e-6)
                    centers[second] = np.clip(midpoint + 0.5 * separation * direction, 1e-6, 1 - 1e-6)
                    generated.append(
                        {
                            "source": source_name,
                            "kind": "split_neighbor_action_space",
                            "moved": [first, second],
                            "space_index": space_index,
                            "angle_index": angle_index,
                            "space": {"center": space.center, "clearance": space.clearance},
                            "centers": centers,
                        }
                    )

    generated = generated[: args.max_seeds]
    atomic_json(run_dir / "sources.json", source_records)
    best_score = -math.inf
    best_payload: Path | None = None
    refined_topologies: dict[str, float] = {}
    optimized_count = refined_count = 0
    best_strict_local = -math.inf
    for seed_index, seed in enumerate(generated):
        optimized, optimization = optimize_seed(
            seed["centers"], args.safety, args.trusts, args.rounds
        )
        event: dict[str, Any] = {
            "event": "seed_finished",
            "seed_index": seed_index,
            **{key: value for key, value in seed.items() if key != "centers"},
            "optimization": optimization,
        }
        if optimized is not None:
            optimized_count += 1
            local_score = float(strict_metrics(optimized)["score"])
            best_strict_local = max(best_strict_local, local_score)
            refinement = refine_rigid(optimized)
            event["refinement"] = {
                key: value
                for key, value in refinement.items()
                if key not in {"active", "buffered_values"}
            }
            if refinement["status"] == "refined":
                refined_count += 1
                signature = str(refinement["signature"])
                score = float(refinement["buffered_report"]["score"])
                if signature not in refined_topologies or score > refined_topologies[signature]:
                    refined_topologies[signature] = score
                    topology_dir = run_dir / "topologies" / signature[:16]
                    payload = topology_dir / "candidate.json"
                    atomic_json(
                        payload,
                        {"circles": values_to_circles(refinement["buffered_values"]).tolist()},
                    )
                    atomic_json(
                        topology_dir / "summary.json",
                        {
                            **event,
                            "active": refinement["active"],
                            "candidate": str(payload),
                            "candidate_sha256": sha256_file(payload),
                        },
                    )
                if score > best_score:
                    best_score = score
                    best_payload = run_dir / "topologies" / signature[:16] / "candidate.json"
        append_event(events, event)
        if (seed_index + 1) % 10 == 0:
            atomic_json(
                run_dir / "checkpoint.json",
                {
                    "seeds_completed": seed_index + 1,
                    "seeds_total": len(generated),
                    "optimized_count": optimized_count,
                    "refined_count": refined_count,
                    "distinct_refined_topologies": len(refined_topologies),
                    "best_strict_local": best_strict_local if math.isfinite(best_strict_local) else None,
                    "best_buffered_score": best_score if math.isfinite(best_score) else None,
                    "best_payload": str(best_payload) if best_payload else None,
                },
            )

    summary = {
        **config,
        "sources": source_records,
        "generated_seed_count": len(generated),
        "optimized_count": optimized_count,
        "refined_count": refined_count,
        "distinct_refined_topologies": len(refined_topologies),
        "best_strict_local": best_strict_local if math.isfinite(best_strict_local) else None,
        "best_buffered_score": best_score if math.isfinite(best_score) else None,
        "best_payload": str(best_payload) if best_payload else None,
        "best_margin_to_target": best_score - TARGET if math.isfinite(best_score) else None,
        "gate_clearing_screen": bool(best_score > TARGET),
        "limitation": (
            "Bounded deterministic first-generation PAS-PCI adaptation: pain-ranked "
            "single relocations and split-neighbor relocations from supplied rigid "
            "sources. It is not an exhaustive contact-graph search or the paper's "
            "full multi-cycle stochastic algorithm."
        ),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, {"event": "run_finished", **summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
