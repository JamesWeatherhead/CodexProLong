#!/usr/bin/env python3
"""Pain-ranked action-space topology search for circles in a rectangle."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize

from audit_corpus import invariant_topology_hash
from core import (
    CORPUS_SHA256,
    GATE,
    LEADER_SCORE,
    PAIR_TOLERANCE,
    PERIMETER_TOLERANCE,
    TARGET,
    VERIFIER_SHA256,
    atomic_json,
    append_event,
    candidate_metrics,
    canonical_signature,
    load_corpus_solution,
    normalize_origin,
    optimize_strict,
    pain_ranking,
    refine_rigid,
    sha256_file,
    values_to_circles,
)


PAPER_ALPHAEVOLVE = "https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L513-L516"
PAPER_PAS_PCI = (
    "https://paperclip.gxl.ai/citations/papers/"
    "arx_1701.00541#L76-L80,L84,L87-L93,L123-L126"
)


@dataclass(frozen=True)
class ActionSpace:
    center: tuple[float, float]
    clearance: float


def clearance(
    point: np.ndarray,
    circles: np.ndarray,
    width: float,
    height: float,
    excluded: set[int],
) -> float:
    x, y = map(float, point)
    if not (0 <= x <= width and 0 <= y <= height):
        return -1.0
    value = min(x, width - x, y, height - y)
    for index, circle in enumerate(circles):
        if index in excluded:
            continue
        value = min(value, float(np.linalg.norm(point - circle[:2]) - circle[2]))
    return value


def action_spaces(
    circles: np.ndarray,
    width: float,
    height: float,
    excluded: set[int],
    grid_size: int,
    requested: int,
    reject_centers: list[np.ndarray],
) -> list[ActionSpace]:
    xs = np.linspace(0.015 * width, 0.985 * width, grid_size)
    ys = np.linspace(0.015 * height, 0.985 * height, grid_size)
    ranked = []
    for x in xs:
        for y in ys:
            point = np.asarray([x, y])
            ranked.append((clearance(point, circles, width, height, excluded), point))
    ranked.sort(key=lambda item: item[0], reverse=True)
    starts: list[np.ndarray] = []
    separation = 0.045 * min(width, height)
    for value, point in ranked:
        if value <= 1e-4:
            break
        if all(np.linalg.norm(point - prior) >= separation for prior in starts):
            starts.append(point)
        if len(starts) >= max(16, 5 * requested):
            break
    polished: list[ActionSpace] = []
    for start in starts:
        result = minimize(
            lambda point: -clearance(point, circles, width, height, excluded),
            start,
            method="Nelder-Mead",
            bounds=((1e-9, width - 1e-9), (1e-9, height - 1e-9)),
            options={"maxiter": 500, "xatol": 1e-12, "fatol": 1e-12},
        )
        point = np.clip(result.x, [1e-9, 1e-9], [width - 1e-9, height - 1e-9])
        value = clearance(point, circles, width, height, excluded)
        if value <= 1e-6:
            continue
        if any(np.linalg.norm(point - old) < 0.035 * min(width, height) for old in reject_centers):
            continue
        if any(np.linalg.norm(point - np.asarray(item.center)) < 1e-5 for item in polished):
            continue
        polished.append(ActionSpace(tuple(map(float, point)), float(value)))
    polished.sort(key=lambda item: item.clearance, reverse=True)
    return polished[:requested]


def parse_ids(value: str) -> list[int]:
    return [int(part) for part in value.split(",") if part.strip()]


def parse_floats(value: str) -> list[float]:
    return [float(part) for part in value.split(",") if part.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="append", type=Path, default=[])
    parser.add_argument("--corpus-solution-ids", type=parse_ids, default=[])
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--grid-size", type=int, default=35)
    parser.add_argument("--spaces-per-circle", type=int, default=3)
    parser.add_argument("--pain-per-group", type=int, default=1)
    parser.add_argument("--split-pairs", type=int, default=6)
    parser.add_argument("--split-spaces", type=int, default=2)
    parser.add_argument("--split-angles", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=18)
    parser.add_argument(
        "--trusts",
        type=parse_floats,
        default=parse_floats("1e-5,3e-5,1e-4,3e-4,1e-3,3e-3,1e-2,3e-2,8e-2"),
    )
    parser.add_argument("--aspect-trust-ratio", type=float, default=0.5)
    parser.add_argument("--safety", type=float, default=2e-12)
    parser.add_argument("--max-seeds", type=int, default=120)
    parser.add_argument("--stamp", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--campaign-root", type=Path, default=Path(__file__).parents[2])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign = args.campaign_root.resolve()
    latest = json.loads((campaign / "research_corpus" / "latest.json").read_text())
    database = campaign / "research_corpus" / latest["database"]
    if sha256_file(database) != CORPUS_SHA256:
        raise RuntimeError("corpus database hash mismatch")
    audit = json.loads(args.audit.resolve().read_text())
    if audit["corpus_database_sha256"] != CORPUS_SHA256:
        raise RuntimeError("audit corpus hash mismatch")
    public_hashes = {
        item["invariant_topology_hash"] for item in audit["constructions"]
    }
    run_dir = Path(__file__).parent / "runs" / args.stamp / "void_relocate"
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    config = {
        "stamp": args.stamp,
        "verifier_sha256": VERIFIER_SHA256,
        "corpus_database_sha256": CORPUS_SHA256,
        "corpus_audit": str(args.audit.resolve()),
        "leader_score": LEADER_SCORE,
        "gate": GATE,
        "target_strictly_above": TARGET,
        "pair_tolerance": PAIR_TOLERANCE,
        "perimeter_tolerance": PERIMETER_TOLERANCE,
        "grid_size": args.grid_size,
        "spaces_per_circle": args.spaces_per_circle,
        "pain_per_group": args.pain_per_group,
        "split_pairs": args.split_pairs,
        "split_spaces": args.split_spaces,
        "split_angles": args.split_angles,
        "rounds": args.rounds,
        "trusts": args.trusts,
        "aspect_trust_ratio": args.aspect_trust_ratio,
        "safety": args.safety,
        "max_seeds": args.max_seeds,
        "method": "pain-ranked single and split-neighbor action-space relocation with free aspect ratio",
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
    source_records = []
    for source_name, raw in sources:
        pain, active, root_values = pain_ranking(raw)
        circles = values_to_circles(root_values)
        width = float(root_values[63])
        height = float(root_values[64])
        order = np.argsort(circles[:, 2])
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
                    "radius_range": [float(np.min(circles[group, 2])), float(np.max(circles[group, 2]))],
                }
            )
        source_record = {
            "source": source_name,
            "score": float(np.sum(circles[:, 2])),
            "width": width,
            "height": height,
            "labeled_signature": canonical_signature(active),
            "invariant_topology_hash": invariant_topology_hash(active),
            "pain": pain.tolist(),
            "groups": group_records,
        }
        source_records.append(source_record)
        append_event(events, {"event": "source_prepared", **source_record})

        for circle_index in painful:
            spaces = action_spaces(
                circles,
                width,
                height,
                {circle_index},
                args.grid_size,
                args.spaces_per_circle,
                [circles[circle_index, :2]],
            )
            for space_index, space in enumerate(spaces):
                centers = circles[:, :2].copy()
                centers[circle_index] = np.asarray(space.center)
                generated.append(
                    {
                        "source": source_name,
                        "kind": "single_action_space",
                        "moved": [circle_index],
                        "space_index": space_index,
                        "space": {"center": space.center, "clearance": space.clearance},
                        "width": width,
                        "centers": centers,
                    }
                )

        ranked_painful = sorted(set(painful), key=lambda index: (-pain[index], index))
        for first, second in list(combinations(ranked_painful, 2))[: args.split_pairs]:
            spaces = action_spaces(
                circles,
                width,
                height,
                {first, second},
                args.grid_size,
                args.split_spaces,
                [circles[first, :2], circles[second, :2]],
            )
            separation = float(circles[first, 2] + circles[second, 2] + 2e-4)
            for space_index, space in enumerate(spaces):
                midpoint = np.asarray(space.center)
                for angle_index in range(args.split_angles):
                    angle = math.pi * angle_index / args.split_angles
                    direction = np.asarray([math.cos(angle), math.sin(angle)])
                    centers = circles[:, :2].copy()
                    centers[first] = np.clip(
                        midpoint - 0.5 * separation * direction,
                        [1e-6, 1e-6],
                        [width - 1e-6, height - 1e-6],
                    )
                    centers[second] = np.clip(
                        midpoint + 0.5 * separation * direction,
                        [1e-6, 1e-6],
                        [width - 1e-6, height - 1e-6],
                    )
                    generated.append(
                        {
                            "source": source_name,
                            "kind": "split_neighbor_action_space",
                            "moved": [first, second],
                            "space_index": space_index,
                            "angle_index": angle_index,
                            "space": {"center": space.center, "clearance": space.clearance},
                            "width": width,
                            "centers": centers,
                        }
                    )

    generated = generated[: args.max_seeds]
    atomic_json(run_dir / "sources.json", source_records)
    best_score = -math.inf
    best_payload: Path | None = None
    best_strict = -math.inf
    optimized_count = refined_count = 0
    topology_scores: dict[str, float] = {}
    invariant_scores: dict[str, float] = {}
    novel_invariant_hashes: set[str] = set()
    for seed_index, seed in enumerate(generated):
        optimized, optimization = optimize_strict(
            seed["centers"],
            float(seed["width"]),
            args.safety,
            args.trusts,
            args.aspect_trust_ratio,
            args.rounds,
        )
        event: dict[str, Any] = {
            "event": "seed_finished",
            "seed_index": seed_index,
            **{key: value for key, value in seed.items() if key != "centers"},
            "optimization": optimization,
        }
        if optimized is not None:
            optimized_count += 1
            circles, width = optimized
            best_strict = max(best_strict, float(candidate_metrics(circles, 0.0, 0.0)["score"]))
            refinement = refine_rigid(circles, width)
            event["refinement"] = {
                key: value for key, value in refinement.items() if key not in {"active", "buffered_values"}
            }
            if refinement["status"] == "refined":
                refined_count += 1
                labeled = str(refinement["signature"])
                invariant = invariant_topology_hash(refinement["active"])
                score = float(refinement["buffered_report"]["score"])
                event["refinement"]["invariant_topology_hash"] = invariant
                event["refinement"]["matches_public_topology"] = invariant in public_hashes
                if invariant not in public_hashes:
                    novel_invariant_hashes.add(invariant)
                invariant_scores[invariant] = max(invariant_scores.get(invariant, -math.inf), score)
                if labeled not in topology_scores or score > topology_scores[labeled]:
                    topology_scores[labeled] = score
                    topology_dir = run_dir / "topologies" / labeled[:16]
                    payload = topology_dir / "candidate.json"
                    atomic_json(payload, {"circles": values_to_circles(refinement["buffered_values"]).tolist()})
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
                    best_payload = run_dir / "topologies" / labeled[:16] / "candidate.json"
        append_event(events, event)
        if (seed_index + 1) % 10 == 0:
            atomic_json(
                run_dir / "checkpoint.json",
                {
                    "seeds_completed": seed_index + 1,
                    "seeds_total": len(generated),
                    "optimized_count": optimized_count,
                    "refined_count": refined_count,
                    "distinct_labeled_topologies": len(topology_scores),
                    "distinct_invariant_topologies": len(invariant_scores),
                    "novel_invariant_topologies": len(novel_invariant_hashes),
                    "best_strict": best_strict if math.isfinite(best_strict) else None,
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
        "distinct_labeled_topologies": len(topology_scores),
        "distinct_invariant_topologies": len(invariant_scores),
        "novel_invariant_topologies_vs_public_corpus": len(novel_invariant_hashes),
        "best_strict": best_strict if math.isfinite(best_strict) else None,
        "best_buffered_score": best_score if math.isfinite(best_score) else None,
        "best_payload": str(best_payload) if best_payload else None,
        "best_margin_to_target": best_score - TARGET if math.isfinite(best_score) else None,
        "gate_clearing_screen": bool(best_score > TARGET),
        "limitation": (
            "Bounded deterministic first-generation action-space adaptation from two "
            "public rigid graph classes; not an exhaustive contact-graph search."
        ),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, {"event": "run_finished", **summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
