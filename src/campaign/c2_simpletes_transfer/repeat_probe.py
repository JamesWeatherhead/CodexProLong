#!/usr/bin/env python3
"""Exact integer-repeat/pad transfer probe for the SimpleTES C2 asset."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = REPO / "campaign/c2_asset_recovery/payloads/simpletes.npy"
SEED = (
    REPO
    / "campaign/analytic/c2_global_topology/runs/"
    "20260815T041000Z-terminal-split/best.npy"
)
VERIFIER = (
    REPO
    / "campaign/state/problems/second-autocorrelation-inequality/"
    "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768.py"
)
SOURCE_SHA256 = "c7365d9ebdcbc7f1014a891ea88cb4ff880152228fedbd5b7df5be7b3cdb9a72"
SEED_SHA256 = "17ae46a8532acd2ed6eb355b968e9e59936adc0335975fd18b67251e0040e640"
VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, value: object) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
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


def load(path: Path, expected: str) -> np.ndarray:
    actual = sha256(path.read_bytes())
    if actual != expected:
        raise RuntimeError(f"hash drift for {path}: {actual}")
    return np.load(path, allow_pickle=False).astype(np.float64)


def main() -> int:
    source = load(SOURCE, SOURCE_SHA256)
    seed = load(SEED, SEED_SHA256)
    if sha256(VERIFIER.read_bytes()) != VERIFIER_SHA256:
        raise RuntimeError("verifier hash drift")
    spec = importlib.util.spec_from_file_location("frozen_c2_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import verifier")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)

    repeated = np.repeat(source, 7)
    padding = seed.size - repeated.size
    if padding < 0:
        raise RuntimeError("repeat does not fit verifier cap")
    base = seed / np.sum(seed)
    seed_score = float(verifier.verify_and_compute_c2(base))
    rows = []
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        left = round(padding * fraction)
        component = np.pad(repeated, (left, padding - left))
        component_score = float(verifier.verify_and_compute_c2(component))
        component /= np.sum(component)
        probes = []
        for alpha in (-1e-8, -1e-9, 1e-9, 1e-8):
            candidate = np.maximum((1.0 - alpha) * base + alpha * component, 0.0)
            score = float(verifier.verify_and_compute_c2(candidate))
            probes.append(
                {"alpha": alpha, "score": score, "gain_from_seed": score - seed_score}
            )
        rows.append(
            {
                "left_padding_fraction": fraction,
                "left_padding": left,
                "right_padding": padding - left,
                "component_score": component_score,
                "probes": probes,
            }
        )
    receipt = {
        "mode": "exact 7x repeat plus zero-pad resampling and signed crossover",
        "source_file_sha256": SOURCE_SHA256,
        "seed_file_sha256": SEED_SHA256,
        "verifier_sha256": VERIFIER_SHA256,
        "source_n": int(source.size),
        "repeat": 7,
        "repeated_n": int(repeated.size),
        "target_n": int(seed.size),
        "padding": padding,
        "seed_score": seed_score,
        "rows": rows,
        "best_crossover": max(
            (probe for row in rows for probe in row["probes"]), key=lambda row: row["score"]
        ),
        "external_writes": [],
    }
    atomic_json(ROOT / "repeat_probe.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
