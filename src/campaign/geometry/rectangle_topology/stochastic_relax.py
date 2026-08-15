#!/usr/bin/env python3
"""Clean-room global-field topology search for circles in a rectangle."""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
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
    optimize_strict,
    pain_ranking,
    refine_rigid,
    sha256_file,
    values_to_circles,
)


COUNT = 21
FLOWBOOST_PAPER = "https://paperclip.gxl.ai/citations/papers/arx_2601.18005#L1"
FLOWBOOST_REPOSITORY = "https://github.com/berczig/FlowBoost"
FLOWBOOST_COMMIT = "95d6feef0f6c9aaa2c28727910b2eecebeeb9026"


def elastic_loss_gradient(
    variables: np.ndarray, penalty: float, reward: float
) -> tuple[float, np.ndarray]:
    centers = variables[: 2 * COUNT].reshape(COUNT, 2)
    radii = variables[2 * COUNT : 3 * COUNT]
    width = float(variables[-1])
    height = 2 - width
    gradient = np.zeros_like(variables)
    center_gradient = gradient[: 2 * COUNT].reshape(COUNT, 2)
    radius_gradient = gradient[2 * COUNT : 3 * COUNT]
    loss = -reward * float(np.sum(radii))
    radius_gradient[:] = -reward
    for index in range(COUNT):
        x, y = centers[index]
        radius = radii[index]
        # violation, center derivative, width derivative
        violations = (
            (radius - x, np.asarray([-1.0, 0.0]), 0.0),
            (radius + x - width, np.asarray([1.0, 0.0]), -1.0),
            (radius - y, np.asarray([0.0, -1.0]), 0.0),
            (radius + y - height, np.asarray([0.0, 1.0]), 1.0),
        )
        for violation, direction, width_derivative in violations:
            if violation <= 0:
                continue
            loss += penalty * violation * violation
            scale = 2 * penalty * violation
            center_gradient[index] += scale * direction
            radius_gradient[index] += scale
            gradient[-1] += scale * width_derivative
    for first in range(COUNT):
        for second in range(first + 1, COUNT):
            delta = centers[first] - centers[second]
            distance = max(float(np.linalg.norm(delta)), 1e-14)
            overlap = radii[first] + radii[second] - distance
            if overlap <= 0:
                continue
            loss += penalty * overlap * overlap
            scale = 2 * penalty * overlap
            direction = delta / distance
            center_gradient[first] -= scale * direction
            center_gradient[second] += scale * direction
            radius_gradient[first] += scale
            radius_gradient[second] += scale
    return loss, gradient


def elastic_relax(
    centers: np.ndarray,
    radii: np.ndarray,
    width: float,
    penalties: list[float],
    maxiter: int,
) -> tuple[np.ndarray, float, dict[str, Any]]:
    variables = np.concatenate((centers.reshape(-1), radii, [width]))
    stages = []
    bounds = [(1e-7, 1.9999999)] * (2 * COUNT) + [(1e-7, 0.3)] * COUNT + [(0.35, 1.65)]
    for penalty in penalties:
        result = minimize(
            lambda value: elastic_loss_gradient(value, penalty, 1.0)[0],
            variables,
            jac=lambda value: elastic_loss_gradient(value, penalty, 1.0)[1],
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": maxiter, "ftol": 1e-13, "gtol": 1e-9, "maxcor": 30},
        )
        variables = np.asarray(result.x)
        stages.append(
            {
                "penalty": penalty,
                "success": bool(result.success),
                "iterations": int(result.nit),
                "evaluations": int(result.nfev),
                "loss": float(result.fun),
                "width": float(variables[-1]),
            }
        )
    return variables[: 2 * COUNT].reshape(COUNT, 2), float(variables[-1]), {"stages": stages}


def generate_fields(
    centers: np.ndarray,
    width: float,
    rng: np.random.Generator,
    scales: list[float],
    repeats: int,
    aspect_scale: float,
) -> list[dict[str, Any]]:
    height = 2 - width
    result: list[dict[str, Any]] = []
    for scale in scales:
        for repeat in range(repeats):
            new_width = float(np.clip(width + rng.normal(0, aspect_scale * scale), 0.45, 1.55))
            new_height = 2 - new_width
            normalized = np.column_stack((centers[:, 0] / width, centers[:, 1] / height))
            base = np.column_stack((normalized[:, 0] * new_width, normalized[:, 1] * new_height))
            magnitude = scale * min(new_width, new_height)
            centered = np.column_stack((normalized[:, 0] - 0.5, normalized[:, 1] - 0.5))

            iid = base + rng.normal(0.0, magnitude, size=base.shape)
            result.append({"kind": "global_iid", "scale": scale, "repeat": repeat, "width": new_width, "centers": iid})

            sign = -1 if repeat % 2 else 1
            shear = base.copy()
            shear[:, 0] += magnitude * centered[:, 1]
            shear[:, 1] += sign * magnitude * centered[:, 0]
            shear += rng.normal(0.0, 0.08 * magnitude, size=base.shape)
            result.append({"kind": "coordinated_shear", "scale": scale, "repeat": repeat, "width": new_width, "centers": shear})

            norm = np.linalg.norm(centered, axis=1) + 1e-12
            tangent = np.column_stack((-centered[:, 1], centered[:, 0])) / norm[:, None]
            vortex = base + magnitude * tangent * (0.35 + norm[:, None])
            vortex += rng.normal(0.0, 0.05 * magnitude, size=base.shape)
            result.append({"kind": "coordinated_vortex", "scale": scale, "repeat": repeat, "width": new_width, "centers": vortex})

            phase = repeat * math.pi / max(1, repeats)
            wave = base.copy()
            wave[:, 0] += magnitude * np.sin(2 * math.pi * normalized[:, 1] + phase)
            wave[:, 1] += magnitude * np.sin(2 * math.pi * normalized[:, 0] - phase)
            result.append({"kind": "coordinated_wave", "scale": scale, "repeat": repeat, "width": new_width, "centers": wave})

            labels = (normalized[:, 0] >= 0.5).astype(int) + 2 * (normalized[:, 1] >= 0.5).astype(int)
            shifts = rng.normal(0.0, magnitude, size=(4, 2))
            shifts -= np.mean(shifts, axis=0)
            quadrant = base + shifts[labels]
            result.append({"kind": "quadrant_flow", "scale": scale, "repeat": repeat, "width": new_width, "centers": quadrant})
    for item in result:
        item["centers"] = np.clip(
            item["centers"],
            [1e-6, 1e-6],
            [float(item["width"]) - 1e-6, 2 - float(item["width"]) - 1e-6],
        )
    return result


def parse_ids(value: str) -> list[int]:
    return [int(part) for part in value.split(",") if part.strip()]


def parse_floats(value: str) -> list[float]:
    return [float(part) for part in value.split(",") if part.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="append", type=Path, default=[])
    parser.add_argument("--corpus-solution-ids", type=parse_ids, default=[])
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--scales", type=parse_floats, default=parse_floats("0.004,0.01,0.025,0.05"))
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--aspect-kick-scale", type=float, default=1.0)
    parser.add_argument("--penalties", type=parse_floats, default=parse_floats("1e3,3e4,1e6"))
    parser.add_argument("--elastic-maxiter", type=int, default=220)
    parser.add_argument("--slp-rounds", type=int, default=22)
    parser.add_argument(
        "--trusts",
        type=parse_floats,
        default=parse_floats("1e-5,3e-5,1e-4,3e-4,1e-3,3e-3,1e-2,3e-2,8e-2"),
    )
    parser.add_argument("--aspect-trust-ratio", type=float, default=0.5)
    parser.add_argument("--safety", type=float, default=2e-12)
    parser.add_argument("--rng-seed", type=int, default=20260815)
    parser.add_argument("--max-seeds", type=int, default=80)
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
    public_hashes = {item["invariant_topology_hash"] for item in audit["constructions"]}
    run_dir = Path(__file__).parent / "runs" / args.stamp / "stochastic_relax"
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
        "scales": args.scales,
        "repeats": args.repeats,
        "aspect_kick_scale": args.aspect_kick_scale,
        "penalties": args.penalties,
        "elastic_maxiter": args.elastic_maxiter,
        "slp_rounds": args.slp_rounds,
        "trusts": args.trusts,
        "aspect_trust_ratio": args.aspect_trust_ratio,
        "safety": args.safety,
        "rng_seed": args.rng_seed,
        "max_seeds": args.max_seeds,
        "method": "clean-room global stochastic fields with free aspect ratio and exact radius LP",
        "literature": FLOWBOOST_PAPER,
        "upstream_repository": FLOWBOOST_REPOSITORY,
        "upstream_commit_read_only": FLOWBOOST_COMMIT,
        "upstream_license_note": "no root license found; no code copied or executed",
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

    rng = np.random.default_rng(args.rng_seed)
    generated: list[dict[str, Any]] = []
    source_records = []
    for source_name, source in sources:
        _, active, root_values = pain_ranking(source)
        circles = values_to_circles(root_values)
        width = float(root_values[63])
        source_records.append(
            {
                "source": source_name,
                "score": float(np.sum(circles[:, 2])),
                "width": width,
                "height": float(root_values[64]),
                "labeled_signature": canonical_signature(active),
                "invariant_topology_hash": invariant_topology_hash(active),
            }
        )
        for field in generate_fields(
            circles[:, :2], width, rng, args.scales, args.repeats, args.aspect_kick_scale
        ):
            field.update(source=source_name, radii=circles[:, 2].copy())
            generated.append(field)
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
        relaxed_centers, relaxed_width, elastic = elastic_relax(
            seed["centers"], seed["radii"], float(seed["width"]), args.penalties, args.elastic_maxiter
        )
        optimized, optimization = optimize_strict(
            relaxed_centers,
            relaxed_width,
            args.safety,
            args.trusts,
            args.aspect_trust_ratio,
            args.slp_rounds,
        )
        event: dict[str, Any] = {
            "event": "seed_finished",
            "seed_index": seed_index,
            "source": seed["source"],
            "kind": seed["kind"],
            "scale": seed["scale"],
            "repeat": seed["repeat"],
            "initial_width": seed["width"],
            "relaxed_width": relaxed_width,
            "elastic": elastic,
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
        if (seed_index + 1) % 5 == 0:
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
            "Bounded CPU-only search over five clean-room global center fields, "
            "four scales, two repeats, and two public rigid graph classes."
        ),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, {"event": "run_finished", **summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
