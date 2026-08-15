#!/usr/bin/env python3
"""Exact C2 support-topology transfer from the recovered SimpleTES asset.

The search first aligns normalized mass/support signatures, then maps the
SimpleTES run geometry onto the 1,999,999-cell incumbent.  Candidate families
include raw resampling, thresholded topology, new-support-only births, and
local-mass-preserving micro-topology transplants.  A bounded multiresolution
coordinate pass only accepts literal gains from the frozen Arena verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter1d


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DEFAULT_SOURCE = REPO / "campaign/c2_asset_recovery/payloads/simpletes.npy"
DEFAULT_SEED = (
    REPO
    / "campaign/analytic/c2_global_topology/runs/"
    "20260815T041000Z-terminal-split/best.npy"
)
DEFAULT_RUN_ROOT = ROOT / "runs"
VERIFIER = (
    REPO
    / "campaign/state/problems/second-autocorrelation-inequality/"
    "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768.py"
)
VERIFIER_SHA256 = (
    "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
)
SOURCE_FILE_SHA256 = (
    "c7365d9ebdcbc7f1014a891ea88cb4ff880152228fedbd5b7df5be7b3cdb9a72"
)
SEED_FILE_SHA256 = (
    "17ae46a8532acd2ed6eb355b968e9e59936adc0335975fd18b67251e0040e640"
)
PUBLIC_SCORE = 0.963588110582029
STRICT_GATE = 0.963598110582029


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, value: object) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    atomic_bytes(path, data)


def atomic_npy(path: Path, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.stem + ".", suffix=".npy", dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        with temporary.open("wb") as handle:
            np.save(handle, values, allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.sequence = 0

    def write(self, event: dict[str, Any]) -> None:
        record = {"sequence": self.sequence, **event}
        self.sequence += 1
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def load_verifier() -> ModuleType:
    actual = sha256(VERIFIER.read_bytes())
    if actual != VERIFIER_SHA256:
        raise RuntimeError(f"verifier hash drift: {actual}")
    spec = importlib.util.spec_from_file_location("frozen_c2_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_array(path: Path, expected_hash: str) -> np.ndarray:
    actual = sha256(path.read_bytes())
    if actual != expected_hash:
        raise RuntimeError(f"input hash drift for {path}: {actual}")
    values = np.load(path, allow_pickle=False).astype(np.float64)
    if values.ndim != 1 or not np.isfinite(values).all() or np.any(values < 0):
        raise RuntimeError(f"invalid input {path}")
    return values


def bin_sum(values: np.ndarray, bins: int) -> np.ndarray:
    boundaries = np.linspace(0, values.size, bins + 1, dtype=np.int64)
    cumulative = np.concatenate(([0.0], np.cumsum(values, dtype=np.float64)))
    return cumulative[boundaries[1:]] - cumulative[boundaries[:-1]]


def signature(values: np.ndarray, bins: int = 2048) -> tuple[np.ndarray, np.ndarray]:
    mass = bin_sum(values, bins)
    mass /= np.sum(mass)
    mask = values > np.max(values) * 1e-8
    support = bin_sum(mask.astype(np.float64), bins)
    widths = np.diff(np.linspace(0, values.size, bins + 1, dtype=np.int64))
    support /= widths
    return gaussian_filter1d(mass, 2.0), gaussian_filter1d(support, 2.0)


def normalized_correlation(left: np.ndarray, right: np.ndarray) -> float:
    left = left - np.mean(left)
    right = right - np.mean(right)
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denom) if denom else -1.0


def aligned_signature(
    source: np.ndarray, scale: float, shift: float, reflect: bool
) -> np.ndarray:
    bins = source.size
    target_x = (np.arange(bins, dtype=np.float64) + 0.5) / bins
    source_x = (target_x - shift) / scale
    if reflect:
        source_x = 1.0 - source_x
    grid = (np.arange(bins, dtype=np.float64) + 0.5) / bins
    return np.interp(source_x, grid, source, left=0.0, right=0.0)


def alignment_grid(source: np.ndarray, seed: np.ndarray) -> list[dict[str, Any]]:
    source_mass, source_support = signature(source)
    seed_mass, seed_support = signature(seed)
    rows: list[dict[str, Any]] = []
    scales = np.linspace(0.94, 1.06, 13)
    shifts = np.linspace(-0.04, 0.04, 17)
    for reflect in (False, True):
        for scale in scales:
            for shift in shifts:
                mass = aligned_signature(source_mass, float(scale), float(shift), reflect)
                support = aligned_signature(
                    source_support, float(scale), float(shift), reflect
                )
                mass_corr = normalized_correlation(mass, seed_mass)
                support_corr = normalized_correlation(support, seed_support)
                rows.append(
                    {
                        "scale": float(scale),
                        "shift": float(shift),
                        "reflect": reflect,
                        "mass_correlation": mass_corr,
                        "support_correlation": support_corr,
                        "objective": 0.7 * mass_corr + 0.3 * support_corr,
                    }
                )
    rows.sort(key=lambda row: float(row["objective"]), reverse=True)
    identity = {
        "scale": 1.0,
        "shift": 0.0,
        "reflect": False,
        "mass_correlation": normalized_correlation(source_mass, seed_mass),
        "support_correlation": normalized_correlation(source_support, seed_support),
    }
    identity["objective"] = (
        0.7 * float(identity["mass_correlation"])
        + 0.3 * float(identity["support_correlation"])
    )
    selected = [rows[0]]
    if any(
        row["scale"] != 1.0 or row["shift"] != 0.0 or row["reflect"]
        for row in selected
    ):
        selected.append(identity)
    for row in rows[1:]:
        if len(selected) >= 3:
            break
        if all(
            abs(float(row["scale"]) - float(old["scale"])) >= 0.02
            or abs(float(row["shift"]) - float(old["shift"])) >= 0.01
            or bool(row["reflect"]) != bool(old["reflect"])
            for old in selected
        ):
            selected.append(row)
    return selected + rows[:12]


def affine_resample(
    source: np.ndarray,
    target_n: int,
    *,
    scale: float,
    shift: float,
    reflect: bool,
    threshold: float | None = None,
) -> np.ndarray:
    work = source
    if threshold is not None:
        work = np.where(source > np.max(source) * threshold, source, 0.0)
    target_x = (np.arange(target_n, dtype=np.float64) + 0.5) / target_n
    source_x = (target_x - shift) / scale
    if reflect:
        source_x = 1.0 - source_x
    indices = np.floor(source_x * source.size).astype(np.int64)
    valid = (indices >= 0) & (indices < source.size)
    output = np.zeros(target_n, dtype=np.float64)
    output[valid] = work[indices[valid]]
    return output


def normalize_mass(values: np.ndarray, mass: float = 1.0) -> np.ndarray:
    total = float(np.sum(values))
    if total <= 0:
        raise ValueError("zero-mass component")
    return values * (mass / total)


def local_mass_match(
    component: np.ndarray, seed: np.ndarray, block_size: int
) -> np.ndarray:
    output = np.zeros_like(component)
    for start in range(0, seed.size, block_size):
        stop = min(seed.size, start + block_size)
        source_block = component[start:stop]
        source_mass = float(np.sum(source_block))
        target_mass = float(np.sum(seed[start:stop]))
        if source_mass > 0 and target_mass > 0:
            output[start:stop] = source_block * (target_mass / source_mass)
        elif target_mass > 0:
            output[start:stop] = seed[start:stop]
    return output


def values_hash(values: np.ndarray) -> str:
    return sha256(np.ascontiguousarray(values).tobytes())


class Search:
    def __init__(
        self,
        verifier: ModuleType,
        source: np.ndarray,
        seed: np.ndarray,
        run_dir: Path,
        log: EventLog,
    ) -> None:
        self.verifier = verifier
        self.source = source
        self.seed = seed
        self.run_dir = run_dir
        self.log = log
        self.evaluations = 0
        self.seed_score = self.evaluate(seed)
        self.best = seed.copy()
        self.best_score = self.seed_score
        self.best_spec: dict[str, Any] = {"family": "seed"}
        self.family_best: dict[str, dict[str, Any]] = {}

    def evaluate(self, values: np.ndarray) -> float:
        self.evaluations += 1
        return float(self.verifier.verify_and_compute_c2(values))

    def record(
        self, family: str, spec: dict[str, Any], values: np.ndarray, score: float
    ) -> None:
        prior = self.family_best.get(family)
        if prior is None or score > float(prior["score"]):
            self.family_best[family] = {"score": score, **spec}
        accepted = score > self.best_score
        if accepted:
            self.best = values.copy()
            self.best_score = score
            self.best_spec = {"family": family, **spec}
            atomic_npy(self.run_dir / "best.npy", self.best)
        self.log.write(
            {
                "event": "candidate",
                "family": family,
                "spec": spec,
                "score": score,
                "gain_from_seed": score - self.seed_score,
                "accepted": accepted,
            }
        )

    def blend_screen(
        self, family: str, component: np.ndarray, metadata: dict[str, Any]
    ) -> tuple[float, float]:
        base = normalize_mass(self.seed)
        component = normalize_mass(component)
        alphas = [
            -1e-1,
            -1e-2,
            -1e-3,
            -1e-4,
            -1e-5,
            -3e-6,
            -1e-6,
            -3e-7,
            -1e-7,
            -3e-8,
            -1e-8,
            -3e-9,
            -1e-9,
            1e-9,
            3e-9,
            1e-8,
            3e-8,
            1e-7,
            3e-7,
            1e-6,
            3e-6,
            1e-5,
            1e-4,
            1e-3,
            1e-2,
            1e-1,
            1.0,
        ]
        best_score = -np.inf
        best_alpha = 0.0
        for alpha in alphas:
            candidate = np.maximum(
                (1.0 - alpha) * base + alpha * component, 0.0
            )
            score = self.evaluate(candidate)
            spec = {**metadata, "alpha": alpha}
            self.record(family, spec, candidate, score)
            if score > best_score:
                best_score = score
                best_alpha = alpha
        return float(best_score), best_alpha

    def coordinate_polish(
        self, component: np.ndarray, alignment: dict[str, Any]
    ) -> None:
        target = normalize_mass(component)
        alphas = [
            -1e-1,
            -1e-2,
            -1e-3,
            -1e-4,
            -1e-5,
            -1e-6,
            -1e-7,
            -1e-8,
            1e-8,
            1e-7,
            1e-6,
            1e-5,
            1e-4,
            1e-3,
            1e-2,
            1e-1,
            1.0,
        ]
        for segments in (8, 32, 128):
            base = normalize_mass(self.best)
            boundaries = np.linspace(0, base.size, segments + 1, dtype=np.int64)
            mismatch: list[tuple[float, int]] = []
            for index in range(segments):
                start, stop = int(boundaries[index]), int(boundaries[index + 1])
                local_target = target[start:stop]
                local_mass = float(np.sum(base[start:stop]))
                if local_mass <= 0 or float(np.sum(local_target)) <= 0:
                    continue
                desired = normalize_mass(local_target, local_mass)
                mismatch.append(
                    (float(np.sum(np.abs(desired - base[start:stop]))), index)
                )
            for _, index in sorted(mismatch, reverse=True)[:6]:
                start, stop = int(boundaries[index]), int(boundaries[index + 1])
                base = normalize_mass(self.best)
                local_mass = float(np.sum(base[start:stop]))
                desired = normalize_mass(target[start:stop], local_mass)
                local_best = self.best_score
                local_best_values: np.ndarray | None = None
                local_best_alpha = 0.0
                for alpha in alphas:
                    candidate = base.copy()
                    candidate[start:stop] = np.maximum(
                        (1.0 - alpha) * base[start:stop] + alpha * desired,
                        0.0,
                    )
                    score = self.evaluate(candidate)
                    spec = {
                        "segments": segments,
                        "segment": index,
                        "alpha": alpha,
                        "alignment": alignment,
                    }
                    self.record("multires_coordinate", spec, candidate, score)
                    if score > local_best:
                        local_best = score
                        local_best_values = candidate
                        local_best_alpha = alpha
                if local_best_values is not None:
                    self.best = local_best_values
                    self.best_score = local_best
                    self.best_spec = {
                        "family": "multires_coordinate",
                        "segments": segments,
                        "segment": index,
                        "alpha": local_best_alpha,
                    }
                    atomic_npy(self.run_dir / "best.npy", self.best)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--stamp")
    args = parser.parse_args()

    source = load_array(args.source.resolve(), SOURCE_FILE_SHA256)
    seed = load_array(args.seed.resolve(), SEED_FILE_SHA256)
    verifier = load_verifier()
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_root.resolve() / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    log = EventLog(run_dir / "events.jsonl")
    atomic_npy(run_dir / "seed.npy", seed)
    atomic_npy(run_dir / "best.npy", seed)

    alignments = alignment_grid(source, seed)
    selected = alignments[:2]
    atomic_json(run_dir / "alignments.json", {"selected": selected, "top": alignments[3:]})
    search = Search(verifier, source, seed, run_dir, log)
    log.write(
        {
            "event": "start",
            "source": str(args.source.resolve()),
            "source_n": int(source.size),
            "source_score": search.evaluate(source),
            "source_values_sha256": values_hash(source),
            "seed": str(args.seed.resolve()),
            "seed_n": int(seed.size),
            "seed_score": search.seed_score,
            "seed_values_sha256": values_hash(seed),
            "selected_alignments": selected,
            "verifier_sha256": VERIFIER_SHA256,
        }
    )

    best_transfer_component: np.ndarray | None = None
    best_transfer_score = -np.inf
    best_alignment: dict[str, Any] | None = None
    for alignment_index, alignment in enumerate(selected):
        kwargs = {
            "scale": float(alignment["scale"]),
            "shift": float(alignment["shift"]),
            "reflect": bool(alignment["reflect"]),
        }
        raw = affine_resample(source, seed.size, **kwargs)
        variants: list[tuple[str, np.ndarray, dict[str, Any]]] = [("raw", raw, {})]
        for threshold in (1e-8, 1e-6):
            topology = affine_resample(
                source, seed.size, threshold=threshold, **kwargs
            )
            variants.append(("threshold", topology, {"threshold": threshold}))
            block_sizes = (2048, 8192, 32768) if threshold == 1e-8 else (8192,)
            for block_size in block_sizes:
                variants.append(
                    (
                        "local_mass",
                        local_mass_match(topology, seed, block_size),
                        {"threshold": threshold, "block_size": block_size},
                    )
                )
        for variant, component, extra in variants:
            if float(np.sum(component)) <= 0:
                continue
            metadata = {
                "alignment_index": alignment_index,
                "alignment": alignment,
                "variant": variant,
                **extra,
            }
            score, _ = search.blend_screen(
                f"blend_{variant}", component, metadata
            )
            if score > best_transfer_score:
                best_transfer_score = score
                best_transfer_component = component.copy()
                best_alignment = alignment

            if not (variant == "threshold" and extra.get("threshold") == 1e-8):
                continue
            for seed_threshold in (0.0, 1e-12, 1e-8):
                cutoff = np.max(seed) * seed_threshold
                birth = np.where(seed <= cutoff, component, 0.0)
                if float(np.sum(birth)) <= 0:
                    continue
                birth_metadata = {
                    **metadata,
                    "seed_threshold": seed_threshold,
                }
                birth_score, _ = search.blend_screen(
                    "support_birth", birth, birth_metadata
                )
                if birth_score > best_transfer_score:
                    best_transfer_score = birth_score
                    best_transfer_component = birth.copy()
                    best_alignment = alignment

    if best_transfer_component is None or best_alignment is None:
        raise RuntimeError("no transfer component survived construction")
    search.coordinate_polish(best_transfer_component, best_alignment)

    summary = {
        "mode": "SimpleTES support-topology alignment, transplant, and exact multiresolution polish",
        "source": str(args.source.resolve()),
        "source_file_sha256": SOURCE_FILE_SHA256,
        "source_values_sha256": values_hash(source),
        "seed": str(args.seed.resolve()),
        "seed_file_sha256": SEED_FILE_SHA256,
        "seed_values_sha256": values_hash(seed),
        "seed_score": search.seed_score,
        "best_score": search.best_score,
        "gain_from_seed": search.best_score - search.seed_score,
        "gain_from_public": search.best_score - PUBLIC_SCORE,
        "strict_gate": STRICT_GATE,
        "gap_to_gate": STRICT_GATE - search.best_score,
        "gate_cleared": search.best_score >= STRICT_GATE,
        "evaluations": search.evaluations,
        "best_spec": search.best_spec,
        "best_transfer_screen_score": best_transfer_score,
        "best_transfer_screen_gain": best_transfer_score - search.seed_score,
        "family_best": search.family_best,
        "selected_alignments": selected,
        "best_payload": str((run_dir / "best.npy").resolve()),
        "best_file_sha256": sha256((run_dir / "best.npy").read_bytes()),
        "best_values_sha256": values_hash(search.best),
        "verifier_sha256": VERIFIER_SHA256,
        "finished_at": datetime.now(UTC).isoformat(),
    }
    atomic_json(run_dir / "summary.json", summary)
    log.write({"event": "complete", "summary": summary})
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
