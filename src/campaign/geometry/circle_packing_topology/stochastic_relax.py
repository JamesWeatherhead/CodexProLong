#!/usr/bin/env python3
"""Clean-room stochastic contact-graph escapes for 26-circle sum packing.

The seed family combines global all-center jitter with coordinated shear,
vortex, wave, and quadrant-flow perturbations.  A smooth elastic relaxation is
followed by an exact fixed-centers HiGHS radius LP, strict-domain sequential LP,
and rigid-root refinement.  This is a small CPU search inspired by the public
FlowBoost methodology, not a copy or execution of its unlicensed source tree.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import minimize


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from circle_packing_search import strict_repair  # noqa: E402
from continue_contacts import (  # noqa: E402
    CORPUS_SHA256,
    GATE,
    LEADER_SCORE,
    PAIR_TOLERANCE,
    TARGET,
    VERIFIER_SHA256,
    canonical_signature,
    load_corpus_solution,
    sha256_file,
    values_to_circles,
)
from void_relocate import optimize_seed, pain_ranking, refine_rigid  # noqa: E402


COUNT = 26
FLOWBOOST_PAPER = "https://paperclip.gxl.ai/citations/papers/arx_2601.18005#L1"
FLOWBOOST_REPOSITORY = "https://github.com/berczig/FlowBoost"
FLOWBOOST_COMMIT = "95d6feef0f6c9aaa2c28727910b2eecebeeb9026"


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


def elastic_loss_gradient(
    variables: np.ndarray, penalty: float, reward: float
) -> tuple[float, np.ndarray]:
    centers = variables[: 2 * COUNT].reshape(COUNT, 2)
    radii = variables[2 * COUNT :]
    gradient = np.zeros_like(variables)
    center_gradient = gradient[: 2 * COUNT].reshape(COUNT, 2)
    radius_gradient = gradient[2 * COUNT :]
    loss = -reward * float(np.sum(radii))
    radius_gradient[:] = -reward

    for index in range(COUNT):
        x, y = centers[index]
        radius = radii[index]
        violations = (
            (radius - x, np.asarray([-1.0, 0.0])),
            (radius + x - 1.0, np.asarray([1.0, 0.0])),
            (radius - y, np.asarray([0.0, -1.0])),
            (radius + y - 1.0, np.asarray([0.0, 1.0])),
        )
        for violation, direction in violations:
            if violation > 0:
                loss += penalty * violation * violation
                scale = 2 * penalty * violation
                center_gradient[index] += scale * direction
                radius_gradient[index] += scale

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
    penalties: list[float],
    maxiter: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    variables = np.concatenate((centers.reshape(-1), radii))
    stages: list[dict[str, Any]] = []
    bounds = [(1e-7, 1 - 1e-7)] * (2 * COUNT) + [(1e-7, 0.3)] * COUNT
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
            }
        )
    return variables[: 2 * COUNT].reshape(COUNT, 2), {"stages": stages}


def generate_perturbations(
    centers: np.ndarray,
    rng: np.random.Generator,
    scales: list[float],
    repeats: int,
) -> list[dict[str, Any]]:
    centered = centers - 0.5
    result: list[dict[str, Any]] = []
    for scale in scales:
        for repeat in range(repeats):
            iid = centers + rng.normal(0.0, scale, size=centers.shape)
            result.append({"kind": "global_iid", "scale": scale, "repeat": repeat, "centers": iid})

            shear_sign = -1.0 if repeat % 2 else 1.0
            shear = centers.copy()
            shear[:, 0] += scale * centered[:, 1]
            shear[:, 1] += shear_sign * scale * centered[:, 0]
            shear += rng.normal(0.0, 0.08 * scale, size=centers.shape)
            result.append({"kind": "coordinated_shear", "scale": scale, "repeat": repeat, "centers": shear})

            radius = np.linalg.norm(centered, axis=1) + 1e-12
            tangent = np.column_stack((-centered[:, 1], centered[:, 0])) / radius[:, None]
            vortex = centers + scale * tangent * (0.35 + radius[:, None])
            vortex += rng.normal(0.0, 0.05 * scale, size=centers.shape)
            result.append({"kind": "coordinated_vortex", "scale": scale, "repeat": repeat, "centers": vortex})

            phase = repeat * math.pi / max(1, repeats)
            wave = centers.copy()
            wave[:, 0] += scale * np.sin(2 * math.pi * centers[:, 1] + phase)
            wave[:, 1] += scale * np.sin(2 * math.pi * centers[:, 0] - phase)
            result.append({"kind": "coordinated_wave", "scale": scale, "repeat": repeat, "centers": wave})

            quadrant = centers.copy()
            labels = (centers[:, 0] >= 0.5).astype(int) + 2 * (centers[:, 1] >= 0.5).astype(int)
            shifts = rng.normal(0.0, scale, size=(4, 2))
            shifts -= np.mean(shifts, axis=0)
            quadrant += shifts[labels]
            result.append({"kind": "quadrant_flow", "scale": scale, "repeat": repeat, "centers": quadrant})
    for item in result:
        item["centers"] = np.clip(item["centers"], 1e-6, 1 - 1e-6)
    return result


def parse_floats(value: str) -> list[float]:
    return [float(part) for part in value.split(",") if part.strip()]


def parse_ids(value: str) -> list[int]:
    return [int(part) for part in value.split(",") if part.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="append", type=Path, default=[])
    parser.add_argument("--corpus-solution-ids", type=parse_ids, default=[])
    parser.add_argument("--scales", type=parse_floats, default=parse_floats("0.004,0.01,0.025,0.05"))
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--penalties", type=parse_floats, default=parse_floats("1e3,3e4,1e6"))
    parser.add_argument("--elastic-maxiter", type=int, default=220)
    parser.add_argument("--slp-rounds", type=int, default=22)
    parser.add_argument(
        "--trusts",
        type=parse_floats,
        default=parse_floats("1e-5,3e-5,1e-4,3e-4,1e-3,3e-3,1e-2,3e-2,8e-2"),
    )
    parser.add_argument("--safety", type=float, default=2e-12)
    parser.add_argument("--rng-seed", type=int, default=20260815)
    parser.add_argument("--max-seeds", type=int, default=80)
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
        "scales": args.scales,
        "repeats": args.repeats,
        "penalties": args.penalties,
        "elastic_maxiter": args.elastic_maxiter,
        "slp_rounds": args.slp_rounds,
        "trusts": args.trusts,
        "safety": args.safety,
        "rng_seed": args.rng_seed,
        "max_seeds": args.max_seeds,
        "method": "clean-room global stochastic elastic relaxation plus fixed-center radius LP",
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
        source_records.append(
            {
                "source": source_name,
                "score": float(np.sum(circles[:, 2])),
                "active_signature": canonical_signature(active),
            }
        )
        for perturbation in generate_perturbations(circles[:, :2], rng, args.scales, args.repeats):
            perturbation.update(source=source_name, radii=circles[:, 2].copy())
            generated.append(perturbation)
    generated = generated[: args.max_seeds]
    atomic_json(run_dir / "sources.json", source_records)

    best_score = -math.inf
    best_payload: Path | None = None
    best_strict_local = -math.inf
    optimized_count = refined_count = 0
    topologies: dict[str, float] = {}
    for seed_index, seed in enumerate(generated):
        relaxed_centers, elastic = elastic_relax(
            seed["centers"], seed["radii"], args.penalties, args.elastic_maxiter
        )
        optimized, optimization = optimize_seed(
            relaxed_centers, args.safety, args.trusts, args.slp_rounds
        )
        event: dict[str, Any] = {
            "event": "seed_finished",
            "seed_index": seed_index,
            "source": seed["source"],
            "kind": seed["kind"],
            "scale": seed["scale"],
            "repeat": seed["repeat"],
            "elastic": elastic,
            "optimization": optimization,
        }
        if optimized is not None:
            optimized_count += 1
            local_score = float(optimization["final_strict"]["score"])
            best_strict_local = max(best_strict_local, local_score)
            refinement = refine_rigid(optimized)
            event["refinement"] = {
                key: value for key, value in refinement.items() if key not in {"active", "buffered_values"}
            }
            if refinement["status"] == "refined":
                refined_count += 1
                signature = str(refinement["signature"])
                score = float(refinement["buffered_report"]["score"])
                if signature not in topologies or score > topologies[signature]:
                    topologies[signature] = score
                    topology_dir = run_dir / "topologies" / signature[:16]
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
                    best_payload = run_dir / "topologies" / signature[:16] / "candidate.json"
        append_event(events, event)
        if (seed_index + 1) % 5 == 0:
            atomic_json(
                run_dir / "checkpoint.json",
                {
                    "seeds_completed": seed_index + 1,
                    "seeds_total": len(generated),
                    "optimized_count": optimized_count,
                    "refined_count": refined_count,
                    "distinct_refined_topologies": len(topologies),
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
        "distinct_refined_topologies": len(topologies),
        "best_strict_local": best_strict_local if math.isfinite(best_strict_local) else None,
        "best_buffered_score": best_score if math.isfinite(best_score) else None,
        "best_payload": str(best_payload) if best_payload else None,
        "best_margin_to_target": best_score - TARGET if math.isfinite(best_score) else None,
        "gate_clearing_screen": bool(best_score > TARGET),
        "limitation": (
            "Bounded CPU-only search over five clean-room global perturbation fields, "
            "the configured scales/repeats, and supplied rigid sources. It does not "
            "train or reproduce FlowBoost and is not a global topology proof."
        ),
    }
    atomic_json(run_dir / "summary.json", summary)
    append_event(events, {"event": "run_finished", **summary})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
