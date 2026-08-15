#!/usr/bin/env python3
"""Deterministic global multiscale support-bundle crossover for C2.

This is deliberately not incumbent float polish.  It treats block-local
replacements from several independently discovered public basins as support
atoms.  Several dual certificates for the exact max term rank coordinated
finite masks, after which only the unchanged frozen verifier decides.

Every run is append-only: inputs, selected specifications, event records, and
terminal checkpoints are created once and never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.signal import oaconvolve


ROOT = Path(__file__).resolve().parent
ARENA = ROOT.parents[2]
VERIFIER = (
    ARENA
    / "campaign/state/problems/second-autocorrelation-inequality"
    / "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768.py"
)
VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
PUBLIC_LEADER = 0.963588110582029
MIN_IMPROVEMENT = 1.0e-5
STRICT_GATE = PUBLIC_LEADER + MIN_IMPROVEMENT

DEFAULT_INPUTS = {
    "seed": ARENA
    / "campaign/c2_simpletes_transfer/runs/20260815T045500Z-repeat/best.npy",
    "public_2415": ARENA / "campaign/analytic/c2_secondary/public_2415.npy",
    "public_2414": ARENA / "campaign/analytic/c2_secondary/public_2414.npy",
    "mlai_2413": ARENA
    / "campaign/analytic/c2_secondary/reference_MLAI-Yonsei_2413.npy",
}
SEGMENT_COUNTS = (4, 8, 16, 32, 64)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_values(values: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(values).tobytes()).hexdigest()


def load_verifier():
    if sha256_file(VERIFIER) != VERIFIER_SHA256:
        raise RuntimeError("frozen verifier hash mismatch")
    spec = importlib.util.spec_from_file_location("c2_frozen_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_score(module: Any, values: np.ndarray) -> float:
    return float(module.verify_and_compute_c2(np.asarray(values, dtype=np.float64)))


def write_json_once(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def write_npy_once(path: Path, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        np.save(handle, np.asarray(values, dtype=np.float64), allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())


def append_event(path: Path, value: Any) -> None:
    with path.open("ab") as handle:
        handle.write((json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode())
        handle.flush()
        os.fsync(handle.fileno())


def components(values: np.ndarray) -> tuple[np.ndarray, float, float, float]:
    convolution = oaconvolve(values, values, mode="full")
    numerator = float(
        (
            2.0 * np.dot(convolution, convolution)
            + np.dot(convolution[:-1], convolution[1:])
        )
        / 3.0
    )
    return convolution, numerator, float(values.sum()), float(convolution.max())


def dual_gradient(
    values: np.ndarray,
    convolution: np.ndarray,
    numerator: float,
    mass: float,
    maximum: float,
    kind: str,
) -> np.ndarray:
    h = 4.0 * convolution / (3.0 * numerator)
    h[:-1] += convolution[1:] / (3.0 * numerator)
    h[1:] += convolution[:-1] / (3.0 * numerator)

    if kind == "unique":
        dual = np.zeros_like(convolution)
        dual[int(np.argmax(convolution))] = 1.0
    elif kind.startswith("soft:"):
        beta = float(kind.split(":", 1)[1])
        logits = beta * (convolution / maximum - 1.0)
        logits -= logits.max()
        dual = np.exp(logits)
        dual /= dual.sum()
    elif kind.startswith("top:"):
        count = min(int(kind.split(":", 1)[1]), convolution.size)
        indices = np.argpartition(convolution, -count)[-count:]
        dual = np.zeros_like(convolution)
        dual[indices] = 1.0 / count
    else:
        raise ValueError(f"unknown dual {kind}")

    gradient = (
        2.0 * oaconvolve(h - dual / maximum, values[::-1], mode="valid")
        - 2.0 / mass
    )
    norm = float(np.linalg.norm(gradient))
    if not np.isfinite(norm) or norm == 0.0:
        raise RuntimeError(f"invalid gradient for {kind}")
    return gradient / norm


def edges_for(n: int, segments: int) -> np.ndarray:
    edges = np.linspace(0, n, segments + 1, dtype=np.int64)
    if np.any(np.diff(edges) <= 0):
        raise ValueError("invalid segment partition")
    return edges


def adjusted_source(
    seed: np.ndarray, source: np.ndarray, segments: int, mode: str
) -> np.ndarray:
    if mode == "raw":
        return source
    if mode != "block_mass":
        raise ValueError(mode)
    output = seed.copy()
    edges = edges_for(seed.size, segments)
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        seed_mass = float(seed[lo:hi].sum())
        source_mass = float(source[lo:hi].sum())
        if seed_mass > 0.0 and source_mass > 0.0:
            output[lo:hi] = source[lo:hi] * (seed_mass / source_mass)
    return output


def coordinate_mask(n: int, segments: int, indices: list[int]) -> np.ndarray:
    result = np.zeros(n, dtype=bool)
    edges = edges_for(n, segments)
    for index in indices:
        result[edges[index] : edges[index + 1]] = True
    return result


def make_candidate(
    seed: np.ndarray,
    source: np.ndarray,
    mode: str,
    segments: int,
    indices: list[int],
    alpha: float,
) -> np.ndarray:
    replacement = adjusted_source(seed, source, segments, mode)
    mask = coordinate_mask(seed.size, segments, indices)
    candidate = seed.copy()
    candidate[mask] += alpha * (replacement[mask] - seed[mask])
    np.maximum(candidate, 0.0, out=candidate)
    candidate *= seed.sum() / candidate.sum()
    if not np.isfinite(candidate).all() or np.any(candidate < 0.0):
        raise RuntimeError("candidate is invalid")
    return candidate


@dataclass(frozen=True)
class Spec:
    source: str
    mode: str
    segments: int
    indices: tuple[int, ...]
    proxy_robust: float
    proxy_mean: float
    l1_move_fraction: float
    material_support_xor: int
    schedule: str

    def as_json(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "mode": self.mode,
            "segments": self.segments,
            "indices": list(self.indices),
            "proxy_robust": self.proxy_robust,
            "proxy_mean": self.proxy_mean,
            "l1_move_fraction": self.l1_move_fraction,
            "material_support_xor": self.material_support_xor,
            "schedule": self.schedule,
        }


def enumerate_specs(
    seed: np.ndarray,
    sources: dict[str, np.ndarray],
    gradients: list[np.ndarray],
    random_seed: int,
) -> list[Spec]:
    rng = np.random.default_rng(random_seed)
    material_threshold = float(seed.max() * 1e-10)
    seed_support = seed > material_threshold
    specs: list[Spec] = []
    seen: set[str] = set()

    for source_name, source in sources.items():
        for mode in ("raw", "block_mass"):
            for segments in SEGMENT_COUNTS:
                replacement = adjusted_source(seed, source, segments, mode)
                delta = replacement - seed
                edges = edges_for(seed.size, segments)
                block_predictions = np.vstack(
                    [np.add.reduceat(gradient * delta, edges[:-1]) for gradient in gradients]
                )
                block_move = np.add.reduceat(np.abs(delta), edges[:-1])
                scaled = block_predictions / np.maximum(block_move[None, :], 1e-300)
                robust_per_block = scaled.min(axis=0)
                order = np.argsort(robust_per_block)[::-1]

                schedules: list[tuple[str, np.ndarray]] = []
                for count in sorted(
                    {2, max(2, segments // 8), max(2, segments // 4), segments // 2, segments}
                ):
                    schedules.append((f"certificate_top_{count}", np.sort(order[:count])))
                for density in (0.25, 0.5):
                    count = max(2, int(round(segments * density)))
                    for repeat in range(2):
                        chosen = np.sort(rng.choice(segments, size=count, replace=False))
                        schedules.append((f"global_random_{density:g}_{repeat}", chosen))
                schedules.append(("alternating_even", np.arange(0, segments, 2)))
                schedules.append(("alternating_odd", np.arange(1, segments, 2)))

                for schedule, chosen in schedules:
                    indices = tuple(int(value) for value in chosen)
                    if len(indices) < 2:
                        continue
                    identity = hashlib.sha256(
                        f"{source_name}|{mode}|{segments}|{indices}".encode()
                    ).hexdigest()
                    if identity in seen:
                        continue
                    seen.add(identity)
                    mask = coordinate_mask(seed.size, segments, list(indices))
                    direction = np.zeros_like(seed)
                    direction[mask] = delta[mask]
                    move = float(np.abs(direction).sum())
                    if move <= 0.0:
                        continue
                    predictions = np.array(
                        [float(np.dot(gradient, direction)) / move for gradient in gradients]
                    )
                    candidate_support = replacement > material_threshold
                    support_xor = int(np.count_nonzero((candidate_support ^ seed_support) & mask))
                    specs.append(
                        Spec(
                            source=source_name,
                            mode=mode,
                            segments=segments,
                            indices=indices,
                            proxy_robust=float(predictions.min()),
                            proxy_mean=float(predictions.mean()),
                            l1_move_fraction=move / float(seed.sum()),
                            material_support_xor=support_xor,
                            schedule=schedule,
                        )
                    )
    return specs


def select_specs(specs: list[Spec], maximum: int) -> list[Spec]:
    # One robust certificate choice per source/mode/scale guarantees broad
    # coverage. Remaining slots prefer genuinely different support topologies.
    family_best: dict[tuple[str, str, int], Spec] = {}
    for spec in specs:
        key = (spec.source, spec.mode, spec.segments)
        current = family_best.get(key)
        if current is None or (spec.proxy_robust, spec.proxy_mean) > (
            current.proxy_robust,
            current.proxy_mean,
        ):
            family_best[key] = spec
    selected = sorted(
        family_best.values(),
        key=lambda item: (item.proxy_robust, item.proxy_mean),
        reverse=True,
    )[:maximum]
    selected_ids = {
        (item.source, item.mode, item.segments, item.indices) for item in selected
    }
    if len(selected) < maximum:
        remaining = [
            item
            for item in specs
            if (item.source, item.mode, item.segments, item.indices) not in selected_ids
        ]
        remaining.sort(
            key=lambda item: (
                item.material_support_xor,
                item.l1_move_fraction,
                item.proxy_robust,
            ),
            reverse=True,
        )
        selected.extend(remaining[: maximum - len(selected)])
    selected.sort(key=lambda item: (item.source, item.mode, item.segments, item.indices))
    return selected


def topology_metrics(seed: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    threshold = float(seed.max() * 1e-10)
    before = seed > threshold
    after = candidate > threshold
    return {
        "l1_moved_fraction": float(np.abs(candidate - seed).sum() / seed.sum()),
        "material_births": int(np.count_nonzero(after & ~before)),
        "material_deaths": int(np.count_nonzero(before & ~after)),
        "material_support_xor": int(np.count_nonzero(after ^ before)),
        "nonzero": int(np.count_nonzero(candidate)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--stamp")
    parser.add_argument("--max-specs", type=int, default=60)
    parser.add_argument("--random-seed", type=int, default=2026081502)
    parser.add_argument("--alphas", default="0.01,0.03,0.1,0.3,1.0")
    args = parser.parse_args()

    verifier = load_verifier()
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ-bundle")
    run_dir = args.run_root / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    inputs_dir = run_dir / "inputs"
    events_path = run_dir / "events.jsonl"

    original: dict[str, np.ndarray] = {}
    for name, path in DEFAULT_INPUTS.items():
        values = np.maximum(np.load(path, allow_pickle=False).astype(np.float64), 0.0)
        if values.ndim != 1 or values.size > 2_000_000 or not np.isfinite(values).all():
            raise ValueError(f"invalid input {name}")
        original[name] = values
        write_npy_once(inputs_dir / f"{name}.npy", values)

    seed = original["seed"]
    if any(values.shape != seed.shape for name, values in original.items() if name != "seed"):
        raise RuntimeError("all bundle sources must share the seed resolution")
    seed_mass = float(seed.sum())

    sources: dict[str, np.ndarray] = {}
    for name in ("public_2415", "public_2414", "mlai_2413"):
        sources[name] = original[name] * (seed_mass / float(original[name].sum()))
    sources["public_2415_reflected"] = sources["public_2415"][::-1].copy()
    sources["seed_reflected"] = seed[::-1].copy()

    source_manifest: dict[str, Any] = {
        "verifier_sha256": VERIFIER_SHA256,
        "public_leader": PUBLIC_LEADER,
        "minimum_improvement": MIN_IMPROVEMENT,
        "strict_gate": STRICT_GATE,
        "inputs": {},
        "derived_sources": {},
    }
    for name, values in original.items():
        source_manifest["inputs"][name] = {
            "origin": str(DEFAULT_INPUTS[name]),
            "file_sha256": sha256_file(inputs_dir / f"{name}.npy"),
            "values_sha256": sha256_values(values),
            "n": int(values.size),
            "score": exact_score(verifier, values),
        }
    for name, values in sources.items():
        source_manifest["derived_sources"][name] = {
            "values_sha256": sha256_values(values),
            "score": exact_score(verifier, values),
        }
    write_json_once(run_dir / "source_manifest.json", source_manifest)

    seed_score = exact_score(verifier, seed)
    convolution, numerator, mass, maximum = components(seed)
    dual_kinds = ("unique", "soft:100000", "soft:1000000", "top:512")
    gradients = [
        dual_gradient(seed, convolution, numerator, mass, maximum, kind)
        for kind in dual_kinds
    ]
    all_specs = enumerate_specs(seed, sources, gradients, args.random_seed)
    selected = select_specs(all_specs, args.max_specs)
    write_json_once(
        run_dir / "selected_specs.json",
        {
            "dual_kinds": list(dual_kinds),
            "enumerated": len(all_specs),
            "selected": [spec.as_json() for spec in selected],
        },
    )

    alphas = [float(value) for value in args.alphas.split(",")]
    if not alphas or any(not (0.0 < value <= 1.0) for value in alphas):
        raise ValueError("alphas must be in (0, 1]")

    best_score = seed_score
    best_values = seed.copy()
    best_event: dict[str, Any] = {"kind": "seed", "score": seed_score}
    best_changed_score = -np.inf
    best_changed: np.ndarray | None = None
    best_changed_event: dict[str, Any] | None = None
    evaluations = 0
    accepted = 0

    for spec_index, spec in enumerate(selected):
        source = sources[spec.source]
        for alpha in alphas:
            candidate = make_candidate(
                seed,
                source,
                spec.mode,
                spec.segments,
                list(spec.indices),
                alpha,
            )
            score = exact_score(verifier, candidate)
            evaluations += 1
            metrics = topology_metrics(seed, candidate)
            event = {
                "event": "evaluate",
                "evaluation": evaluations,
                "spec_index": spec_index,
                "source": spec.source,
                "mode": spec.mode,
                "segments": spec.segments,
                "indices": list(spec.indices),
                "schedule": spec.schedule,
                "alpha": alpha,
                "score": score,
                "gain_from_seed": score - seed_score,
                "gap_to_gate": STRICT_GATE - score,
                "candidate_values_sha256": sha256_values(candidate),
                "proxy_robust": spec.proxy_robust,
                "proxy_mean": spec.proxy_mean,
                **metrics,
            }
            if score > best_changed_score:
                best_changed_score = score
                best_changed = candidate.copy()
                best_changed_event = event.copy()
            if score > best_score:
                accepted += 1
                best_score = score
                best_values = candidate.copy()
                best_event = event.copy()
                checkpoint = run_dir / "checkpoints" / f"accepted_{accepted:04d}.npy"
                write_npy_once(checkpoint, best_values)
                event["accepted_checkpoint"] = str(checkpoint.relative_to(run_dir))
            append_event(events_path, event)
            if score >= STRICT_GATE:
                append_event(events_path, {"event": "gate_clearer", "evaluation": evaluations})
                break
        if best_score >= STRICT_GATE:
            break

    if best_changed is None or best_changed_event is None:
        raise RuntimeError("no changed candidate was evaluated")
    write_npy_once(run_dir / "best_changed.npy", best_changed)
    write_npy_once(run_dir / "retained.npy", best_values)
    replay_score = exact_score(verifier, best_values)
    if replay_score != best_score:
        raise RuntimeError(f"terminal exact replay mismatch: {replay_score} != {best_score}")

    summary = {
        "mode": "finite coordinated multiscale support-bundle crossover",
        "seed_score": seed_score,
        "public_leader": PUBLIC_LEADER,
        "strict_gate": STRICT_GATE,
        "best_score": best_score,
        "best_gain_from_seed": best_score - seed_score,
        "best_gap_to_gate": STRICT_GATE - best_score,
        "gate_cleared": bool(best_score >= STRICT_GATE),
        "best_event": best_event,
        "best_changed_score": best_changed_score,
        "best_changed_gain_from_seed": best_changed_score - seed_score,
        "best_changed_gap_to_gate": STRICT_GATE - best_changed_score,
        "best_changed_event": best_changed_event,
        "enumerated_specs": len(all_specs),
        "selected_specs": len(selected),
        "evaluations": evaluations,
        "accepted": accepted,
        "alphas": alphas,
        "random_seed": args.random_seed,
        "retained_values_sha256": sha256_values(best_values),
        "best_changed_values_sha256": sha256_values(best_changed),
        "verifier_sha256": VERIFIER_SHA256,
    }
    write_json_once(run_dir / "summary.json", summary)
    append_event(events_path, {"event": "complete", "summary_sha256": sha256_file(run_dir / "summary.json")})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

