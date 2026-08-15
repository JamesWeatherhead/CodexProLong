#!/usr/bin/env python3
"""Fine multiresolution continuation of the SimpleTES support-birth transfer."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = REPO / "campaign/c2_asset_recovery/payloads/simpletes.npy"
ORIGINAL_SEED = (
    REPO
    / "campaign/analytic/c2_global_topology/runs/"
    "20260815T041000Z-terminal-split/best.npy"
)
DEFAULT_INPUT = ROOT / "runs/20260815T044000Z-signed-transfer/best.npy"
VERIFIER = (
    REPO
    / "campaign/state/problems/second-autocorrelation-inequality/"
    "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768.py"
)
VERIFIER_SHA256 = (
    "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
)
SOURCE_SHA256 = "c7365d9ebdcbc7f1014a891ea88cb4ff880152228fedbd5b7df5be7b3cdb9a72"
ORIGINAL_SEED_SHA256 = (
    "17ae46a8532acd2ed6eb355b968e9e59936adc0335975fd18b67251e0040e640"
)
DEFAULT_INPUT_SHA256 = (
    "21f99110aed0e86ff690812d57b80ac4ef7f9e6d14e3ed6ff33633d2eabbbf7a"
)
STRICT_GATE = 0.963598110582029


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path, expected: str) -> np.ndarray:
    actual = sha256(path.read_bytes())
    if actual != expected:
        raise RuntimeError(f"input hash drift for {path}: {actual}")
    return np.load(path, allow_pickle=False).astype(np.float64)


def load_verifier():
    if sha256(VERIFIER.read_bytes()) != VERIFIER_SHA256:
        raise RuntimeError("verifier hash drift")
    spec = importlib.util.spec_from_file_location("frozen_c2_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    atomic_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(),
    )


def atomic_npy(path: Path, values: np.ndarray) -> None:
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


def normalize(values: np.ndarray, mass: float = 1.0) -> np.ndarray:
    total = float(np.sum(values))
    if total <= 0:
        raise ValueError("zero mass")
    return values * (mass / total)


def aligned_topology(source: np.ndarray, target_n: int) -> np.ndarray:
    work = np.where(source > np.max(source) * 1e-8, source, 0.0)
    target_x = (np.arange(target_n, dtype=np.float64) + 0.5) / target_n
    source_x = (target_x - 0.03) / 0.97
    indices = np.floor(source_x * source.size).astype(np.int64)
    valid = (indices >= 0) & (indices < source.size)
    output = np.zeros(target_n, dtype=np.float64)
    output[valid] = work[indices[valid]]
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--input-sha256", default=DEFAULT_INPUT_SHA256)
    parser.add_argument("--run-root", type=Path, default=ROOT / "runs")
    parser.add_argument("--stamp")
    parser.add_argument("--top-blocks", type=int, default=16)
    args = parser.parse_args()

    source = load(SOURCE, SOURCE_SHA256)
    original = load(ORIGINAL_SEED, ORIGINAL_SEED_SHA256)
    current = load(args.input.resolve(), args.input_sha256)
    verifier = load_verifier()
    stamp = args.stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-fine"
    run_dir = args.run_root.resolve() / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    atomic_npy(run_dir / "seed.npy", current)
    atomic_npy(run_dir / "best.npy", current)

    topology = aligned_topology(source, current.size)
    birth = np.where(original == 0.0, topology, 0.0)
    if float(np.sum(birth)) <= 0:
        raise RuntimeError("aligned birth topology is empty")
    target = normalize(birth)
    current = normalize(current)
    seed_score = float(verifier.verify_and_compute_c2(current))
    best_score = seed_score
    evaluations = 1
    accepted: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    alphas = [-3e-8, -1e-8, -3e-9, -1e-9, 1e-9, 3e-9, 1e-8, 3e-8, 1e-7]

    for segments in (256, 512, 1024):
        boundaries = np.linspace(0, current.size, segments + 1, dtype=np.int64)
        ranked: list[tuple[float, int]] = []
        for index in range(segments):
            start, stop = int(boundaries[index]), int(boundaries[index + 1])
            block_mass = float(np.sum(current[start:stop]))
            birth_mass = float(np.sum(target[start:stop]))
            if block_mass > 0 and birth_mass > 0:
                ranked.append((block_mass * birth_mass, index))
        for _, index in sorted(ranked, reverse=True)[: args.top_blocks]:
            start, stop = int(boundaries[index]), int(boundaries[index + 1])
            base = normalize(current)
            local_mass = float(np.sum(base[start:stop]))
            desired = normalize(target[start:stop], local_mass)
            local_best_score = best_score
            local_best: np.ndarray | None = None
            local_alpha = 0.0
            for alpha in alphas:
                candidate = base.copy()
                candidate[start:stop] = np.maximum(
                    (1.0 - alpha) * base[start:stop] + alpha * desired, 0.0
                )
                score = float(verifier.verify_and_compute_c2(candidate))
                evaluations += 1
                event = {
                    "segments": segments,
                    "segment": index,
                    "alpha": alpha,
                    "score": score,
                    "gain_from_seed": score - seed_score,
                    "accepted": False,
                }
                if score > local_best_score + 5e-15:
                    local_best_score = score
                    local_best = candidate
                    local_alpha = alpha
                events.append(event)
            if local_best is not None:
                current = local_best
                best_score = local_best_score
                accepted_event = {
                    "segments": segments,
                    "segment": index,
                    "alpha": local_alpha,
                    "score": best_score,
                    "gain_from_seed": best_score - seed_score,
                }
                accepted.append(accepted_event)
                events[-len(alphas) + alphas.index(local_alpha)]["accepted"] = True
                atomic_npy(run_dir / "best.npy", current)

    atomic_json(run_dir / "events.json", events)
    summary = {
        "mode": "fine SimpleTES-only support-birth multiresolution continuation",
        "input": str(args.input.resolve()),
        "input_file_sha256": args.input_sha256,
        "source_file_sha256": SOURCE_SHA256,
        "original_seed_file_sha256": ORIGINAL_SEED_SHA256,
        "alignment": {"scale": 0.97, "shift": 0.03, "reflect": False},
        "threshold": 1e-8,
        "resolutions": [256, 512, 1024],
        "top_blocks": args.top_blocks,
        "evaluations": evaluations,
        "accepted": accepted,
        "seed_score": seed_score,
        "best_score": best_score,
        "gain": best_score - seed_score,
        "strict_gate": STRICT_GATE,
        "gap_to_gate": STRICT_GATE - best_score,
        "gate_cleared": best_score >= STRICT_GATE,
        "best_payload": str((run_dir / "best.npy").resolve()),
        "best_file_sha256": sha256((run_dir / "best.npy").read_bytes()),
        "best_values_sha256": sha256(np.ascontiguousarray(current).tobytes()),
        "verifier_sha256": VERIFIER_SHA256,
        "finished_at": datetime.now(UTC).isoformat(),
    }
    atomic_json(run_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
