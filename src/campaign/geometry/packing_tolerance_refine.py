"""High-precision literal-tolerance roots for the two circle-packing tasks.

This program intentionally differs from the strict-domain packing campaign:
it sets every active pair to the verifier's permitted 1e-9 overlap and, for
the rectangle problem, sets the perimeter to its permitted 1e-9 overrun.  All
outputs are labeled tolerance-dependent.  Downloaded verifier code is never
executed on the host; final scores must be replayed with ``./arena verify``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import mpmath as mp
import numpy as np

CONFIG = {
    "circle-packing": {"count": 26, "problem_id": 14, "mode": "square"},
    "circles-rectangle": {"count": 21, "problem_id": 18, "mode": "rectangle"},
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def normalize_rectangle(circles: np.ndarray) -> np.ndarray:
    result = circles.copy()
    result[:, 0] -= np.min(result[:, 0] - result[:, 2])
    result[:, 1] -= np.min(result[:, 1] - result[:, 2])
    return result


def decode_active(
    circles: np.ndarray, mode: str, tolerance: float
) -> tuple[list[tuple[int, int]], list[tuple[int, str]]]:
    if mode == "rectangle":
        circles = normalize_rectangle(circles)
    centers, radii = circles[:, :2], circles[:, 2]
    count = len(circles)
    pairs = [
        (i, j)
        for i in range(count)
        for j in range(i + 1, count)
        if np.linalg.norm(centers[i] - centers[j]) - radii[i] - radii[j] <= tolerance
    ]
    if mode == "square":
        bounds = (0.0, 1.0, 0.0, 1.0)
    else:
        bounds = (
            0.0,
            float(np.max(centers[:, 0] + radii)),
            0.0,
            float(np.max(centers[:, 1] + radii)),
        )
    left, right, bottom, top = bounds
    walls: list[tuple[int, str]] = []
    for i, (x_value, y_value) in enumerate(centers):
        for name, slack in (
            ("L", x_value - radii[i] - left),
            ("R", right - x_value - radii[i]),
            ("B", y_value - radii[i] - bottom),
            ("T", top - y_value - radii[i]),
        ):
            if slack <= tolerance:
                walls.append((i, name))
    return pairs, walls


def initial_values(circles: np.ndarray, mode: str) -> mp.matrix:
    if mode == "rectangle":
        circles = normalize_rectangle(circles)
    count = len(circles)
    extra = 2 if mode == "rectangle" else 0
    values = mp.matrix(3 * count + extra, 1)
    for i in range(count):
        values[2 * i] = mp.mpf(float(circles[i, 0]))
        values[2 * i + 1] = mp.mpf(float(circles[i, 1]))
        values[2 * count + i] = mp.mpf(float(circles[i, 2]))
    if mode == "rectangle":
        values[3 * count] = mp.mpf(float(np.max(circles[:, 0] + circles[:, 2])))
        values[3 * count + 1] = mp.mpf(float(np.max(circles[:, 1] + circles[:, 2])))
    return values


def equations_and_jacobian(
    values: mp.matrix,
    count: int,
    mode: str,
    pairs: list[tuple[int, int]],
    walls: list[tuple[int, str]],
    pair_overlap: mp.mpf,
    perimeter_overrun: mp.mpf,
    wall_slack: mp.mpf,
) -> tuple[mp.matrix, mp.matrix]:
    radius_start = 2 * count
    width_id, height_id = 3 * count, 3 * count + 1
    equation_count = len(pairs) + len(walls) + (mode == "rectangle")
    equations = mp.matrix(equation_count, 1)
    jacobian = mp.matrix(equation_count, len(values))
    row = 0
    for i, j in pairs:
        dx = values[2 * i] - values[2 * j]
        dy = values[2 * i + 1] - values[2 * j + 1]
        distance = mp.sqrt(dx * dx + dy * dy)
        equations[row] = (
            distance
            - values[radius_start + i]
            - values[radius_start + j]
            + pair_overlap
        )
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
            equations[row] = values[x_id] - values[radius_id] - wall_slack
            jacobian[row, x_id], jacobian[row, radius_id] = 1, -1
        elif wall == "R":
            if mode == "square":
                equations[row] = 1 - values[x_id] - values[radius_id] - wall_slack
            else:
                equations[row] = (
                    values[width_id] - values[x_id] - values[radius_id] - wall_slack
                )
                jacobian[row, width_id] = 1
            jacobian[row, x_id], jacobian[row, radius_id] = -1, -1
        elif wall == "B":
            equations[row] = values[y_id] - values[radius_id] - wall_slack
            jacobian[row, y_id], jacobian[row, radius_id] = 1, -1
        else:
            if mode == "square":
                equations[row] = 1 - values[y_id] - values[radius_id] - wall_slack
            else:
                equations[row] = (
                    values[height_id] - values[y_id] - values[radius_id] - wall_slack
                )
                jacobian[row, height_id] = 1
            jacobian[row, y_id], jacobian[row, radius_id] = -1, -1
        row += 1
    if mode == "rectangle":
        equations[row] = 2 + perimeter_overrun - values[width_id] - values[height_id]
        jacobian[row, width_id] = jacobian[row, height_id] = -1
    return equations, jacobian


def solve_root(
    start: mp.matrix,
    count: int,
    mode: str,
    pairs: list[tuple[int, int]],
    walls: list[tuple[int, str]],
    pair_overlap: mp.mpf,
    perimeter_overrun: mp.mpf,
    wall_slack: mp.mpf,
    iterations: int,
    tolerance: mp.mpf,
) -> tuple[mp.matrix, mp.mpf, mp.matrix]:
    values = mp.matrix(start)
    jacobian = mp.matrix(1, 1)
    for _ in range(iterations):
        equations, jacobian = equations_and_jacobian(
            values,
            count,
            mode,
            pairs,
            walls,
            pair_overlap,
            perimeter_overrun,
            wall_slack,
        )
        residual = max(abs(item) for item in equations)
        if residual < tolerance:
            return values, residual, jacobian
        values += mp.lu_solve(jacobian, -equations)
    equations, jacobian = equations_and_jacobian(
        values,
        count,
        mode,
        pairs,
        walls,
        pair_overlap,
        perimeter_overrun,
        wall_slack,
    )
    return values, max(abs(item) for item in equations), jacobian


def values_to_circles(values: mp.matrix, count: int, mode: str) -> np.ndarray:
    circles = np.empty((count, 3), dtype=np.float64)
    for i in range(count):
        circles[i] = (
            float(values[2 * i]),
            float(values[2 * i + 1]),
            float(values[2 * count + i]),
        )
    return normalize_rectangle(circles) if mode == "rectangle" else circles


def literal_metrics(circles: np.ndarray, mode: str) -> dict[str, Any]:
    centers, radii = circles[:, :2], circles[:, 2]
    pair_slacks = np.array(
        [
            np.sqrt(np.sum((centers[i] - centers[j]) ** 2)) - radii[i] - radii[j]
            for i in range(len(circles))
            for j in range(i + 1, len(circles))
        ]
    )
    finite = bool(np.isfinite(circles).all())
    if mode == "square":
        wall_slacks = np.column_stack(
            (
                centers[:, 0] - radii,
                1 - centers[:, 0] - radii,
                centers[:, 1] - radii,
                1 - centers[:, 1] - radii,
            )
        )
        contained = bool(
            ((radii[:, None] <= centers) & (centers <= 1 - radii[:, None])).all()
        )
        accepted = bool(
            finite and (radii >= 0).all() and contained and np.all(pair_slacks >= -1e-9)
        )
        return {
            "score": float(np.sum(radii)) if accepted else -math.inf,
            "raw_radius_sum": float(np.sum(radii)),
            "accepted_preview": accepted,
            "minimum_pair_slack": float(np.min(pair_slacks)),
            "minimum_wall_slack": float(np.min(wall_slacks)),
            "perimeter_slack": None,
        }
    min_x = np.min(circles[:, 0] - radii)
    max_x = np.max(circles[:, 0] + radii)
    min_y = np.min(circles[:, 1] - radii)
    max_y = np.max(circles[:, 1] + radii)
    perimeter_slack = float(2 - (max_x - min_x) - (max_y - min_y))
    spacing = np.maximum(
        np.abs(np.spacing(centers[:, 0])), np.abs(np.spacing(centers[:, 1]))
    )
    accepted = bool(
        finite
        and (radii > 0).all()
        and np.abs(centers).max() <= 1e6
        and np.all(radii >= 1e6 * spacing)
        and perimeter_slack >= -1e-9
        and np.all(pair_slacks >= -1e-9)
    )
    return {
        "score": float(np.sum(radii)) if accepted else -math.inf,
        "raw_radius_sum": float(np.sum(radii)),
        "accepted_preview": accepted,
        "minimum_pair_slack": float(np.min(pair_slacks)),
        "minimum_wall_slack": None,
        "perimeter_slack": perimeter_slack,
    }


def repair_float(circles: np.ndarray, mode: str) -> tuple[np.ndarray, int]:
    repaired = circles.copy()
    for steps in range(1001):
        if literal_metrics(repaired, mode)["accepted_preview"]:
            return repaired, steps
        repaired[:, 2] = np.nextafter(repaired[:, 2], 0.0)
        if mode == "rectangle":
            repaired = normalize_rectangle(repaired)
    raise RuntimeError("1,000 representable radius decrements did not pass preview")


def mp_objective(values: mp.matrix, count: int) -> mp.mpf:
    return sum(values[2 * count + i] for i in range(count))


def load_corpus_context(campaign_root: Path, slug: str) -> tuple[Path, dict[str, Any]]:
    latest = json.loads(
        (campaign_root / "research_corpus" / "latest.json").read_text(encoding="utf-8")
    )
    database = campaign_root / "research_corpus" / latest["database"]
    if sha256_file(database) != latest["database_sha256"]:
        raise RuntimeError("corpus database hash mismatch")
    connection = sqlite3.connect(database)
    problem = connection.execute(
        "SELECT verifier_sha256, min_improvement FROM problems WHERE slug=?", (slug,)
    ).fetchone()
    leader = connection.execute(
        """
        SELECT s.id,s.agent_name,s.score FROM solutions s
        JOIN problems p ON p.id=s.problem_id WHERE p.slug=? ORDER BY s.score DESC LIMIT 1
        """,
        (slug,),
    ).fetchone()
    counts = connection.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM solutions s JOIN problems p ON p.id=s.problem_id
            WHERE p.slug=?),
          (SELECT COUNT(*) FROM threads WHERE problem_slug=?),
          (SELECT COUNT(*) FROM replies r JOIN threads t ON t.id=r.thread_id
            WHERE t.problem_slug=?)
        """,
        (slug, slug, slug),
    ).fetchone()
    connection.close()
    if problem is None or leader is None:
        raise RuntimeError(f"missing corpus context for {slug}")
    return database, {
        "corpus_database_sha256": latest["database_sha256"],
        "verifier_sha256": problem[0],
        "min_improvement": float(problem[1]),
        "leader_id": int(leader[0]),
        "leader_agent": leader[1],
        "leader_score": float(leader[2]),
        "solution_count": int(counts[0]),
        "thread_count": int(counts[1]),
        "reply_count": int(counts[2]),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", choices=sorted(CONFIG))
    parser.add_argument("seed_payload", type=Path)
    parser.add_argument("--active-tolerance", type=float, default=1e-7)
    parser.add_argument("--digits", type=int, default=100)
    parser.add_argument("--iterations", type=int, default=12)
    parser.add_argument("--float-buffer", default="2e-15")
    parser.add_argument("--stamp", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--campaign-root", type=Path, default=Path(__file__).parents[1])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    campaign_root = args.campaign_root.resolve()
    config = CONFIG[args.slug]
    count, mode = int(config["count"]), str(config["mode"])
    seed_path = args.seed_payload.resolve()
    seed_record = json.loads(seed_path.read_text(encoding="utf-8"))
    seed = np.asarray(seed_record["circles"], dtype=float)
    if seed.shape != (count, 3) or not np.isfinite(seed).all():
        raise RuntimeError("invalid seed shape or finiteness")
    pairs, walls = decode_active(seed, mode, args.active_tolerance)
    expected = 3 * count + (2 if mode == "rectangle" else 0)
    actual = len(pairs) + len(walls) + (mode == "rectangle")
    if actual != expected:
        raise RuntimeError(
            f"active system not square: {len(pairs)} pairs + {len(walls)} walls "
            f"+ {int(mode == 'rectangle')} perimeter != {expected}"
        )

    database, context = load_corpus_context(campaign_root, args.slug)
    run_dir = campaign_root / "geometry" / "runs" / args.stamp / args.slug
    run_dir.mkdir(parents=True, exist_ok=False)
    atomic_json(run_dir / "seed.json", {"circles": seed.tolist()})
    atomic_json(
        run_dir / "active_set.json",
        {"pairs": pairs, "walls": walls, "perimeter": mode == "rectangle"},
    )

    mp.mp.dps = args.digits
    zero = mp.mpf("0")
    full = mp.mpf("1e-9")
    buffer = mp.mpf(args.float_buffer)
    buffered = full - buffer
    tolerance = mp.mpf(10) ** (-(args.digits - 15))
    start = initial_values(seed, mode)
    roots: dict[str, tuple[mp.matrix, mp.mpf, mp.matrix]] = {}
    roots["strict"] = solve_root(
        start, count, mode, pairs, walls, zero, zero, zero, args.iterations, tolerance
    )
    roots["full"] = solve_root(
        roots["strict"][0],
        count,
        mode,
        pairs,
        walls,
        full,
        full if mode == "rectangle" else zero,
        zero,
        args.iterations,
        tolerance,
    )
    roots["buffered"] = solve_root(
        roots["strict"][0],
        count,
        mode,
        pairs,
        walls,
        buffered,
        buffered if mode == "rectangle" else zero,
        buffer if mode == "square" else zero,
        args.iterations,
        tolerance,
    )

    candidate = values_to_circles(roots["buffered"][0], count, mode)
    candidate, repair_steps = repair_float(candidate, mode)
    preview = literal_metrics(candidate, mode)
    atomic_json(run_dir / "candidate.json", {"circles": candidate.tolist()})

    full_jacobian = np.asarray(roots["full"][2].tolist(), dtype=float)
    objective_gradient = np.zeros(expected)
    objective_gradient[2 * count : 3 * count] = 1.0
    multipliers = np.linalg.solve(full_jacobian.T, -objective_gradient)
    singular_values = np.linalg.svd(full_jacobian, compute_uv=False)
    strict_objective = mp_objective(roots["strict"][0], count)
    full_objective = mp_objective(roots["full"][0], count)
    buffered_objective = mp_objective(roots["buffered"][0], count)
    target = context["leader_score"] + context["min_improvement"]

    summary = {
        "slug": args.slug,
        "mode": mode,
        "tolerance_dependent": True,
        "disclosure": (
            "This construction intentionally uses the verifier's explicit 1e-9 "
            "pair tolerance"
            + (" and 1e-9 perimeter tolerance." if mode == "rectangle" else ".")
        ),
        "seed_payload": str(seed_path),
        "seed_sha256": sha256_file(seed_path),
        "corpus_database": str(database),
        "public_context": context,
        "pair_contacts": len(pairs),
        "wall_contacts": len(walls),
        "perimeter_active": mode == "rectangle",
        "high_precision_digits": args.digits,
        "full_pair_overlap": mp.nstr(full, 20),
        "full_perimeter_overrun": mp.nstr(full if mode == "rectangle" else zero, 20),
        "candidate_float_buffer": mp.nstr(buffer, 20),
        "strict_root_objective": mp.nstr(strict_objective, 60),
        "full_tolerance_root_objective": mp.nstr(full_objective, 60),
        "buffered_root_objective": mp.nstr(buffered_objective, 60),
        "full_root_gain_over_strict": mp.nstr(full_objective - strict_objective, 40),
        "root_residuals": {
            name: mp.nstr(result[1], 30) for name, result in roots.items()
        },
        "active_jacobian_rank": int(np.linalg.matrix_rank(full_jacobian, tol=1e-11)),
        "active_jacobian_smallest_singular_value": float(singular_values[-1]),
        "kkt_multiplier_minimum": float(np.min(multipliers)),
        "kkt_multiplier_maximum": float(np.max(multipliers)),
        "kkt_all_nonnegative": bool(np.min(multipliers) >= -1e-9),
        "live_leader": context["leader_score"],
        "target_strictly_above": target,
        "same_topology_full_root_margin_to_target": float(full_objective) - target,
        "same_topology_full_root_clears_gate": bool(float(full_objective) > target),
        "float_repair_nextafter_steps": repair_steps,
        "candidate_preview": preview,
        "candidate_preview_margin_to_target": preview["raw_radius_sum"] - target,
        "candidate_preview_clears_gate": bool(
            preview["accepted_preview"] and preview["raw_radius_sum"] > target
        ),
        "payload": str((run_dir / "candidate.json").resolve()),
        "verifier_sha256": context["verifier_sha256"],
        "limitations": (
            "The positive KKT multipliers certify first-order optimality only "
            "for the recorded active topology. A different contact topology "
            "could in principle do better."
        ),
        "docker_verifier_score": None,
        "docker_receipt": None,
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
