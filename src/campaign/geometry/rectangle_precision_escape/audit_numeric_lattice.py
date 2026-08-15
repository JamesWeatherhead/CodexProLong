#!/usr/bin/env python3
"""Bounded exact-verifier audit of large-coordinate rounding for rectangle n=21.

This does not optimize or submit anything.  It tests whether a gate-clearing
uniform dilation of the frozen 47-pair/17-wall root can be hidden by float64
rounding after otherwise irrelevant translations.  Candidate arrays stay in
memory and every apparent hit is replayed by the frozen verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / (
    "campaign/geometry/rectangle_topology/runs/20260815T022200Z/"
    "stochastic_relax/topologies/cdea3037dafa48f9/candidate.json"
)
SUMMARY = SEED.with_name("summary.json")
VERIFIER_SHA = "c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9"
VERIFIER = ROOT / "campaign/state/problems/circles-rectangle" / f"{VERIFIER_SHA}.py"
LEADER = 2.365832385207997
TARGET = LEADER + 1e-10


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verifier():
    if file_sha(VERIFIER) != VERIFIER_SHA:
        raise RuntimeError("frozen verifier hash mismatch")
    namespace: dict[str, Any] = {"__name__": "arena_verifier"}
    exec(compile(VERIFIER.read_bytes(), str(VERIFIER), "exec"), namespace)
    return namespace["evaluate"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=5_000_000)
    parser.add_argument("--batch", type=int, default=25_000)
    args = parser.parse_args()

    circles = np.asarray(json.loads(SEED.read_text())["circles"], dtype=np.float64)
    centers, radii = circles[:, :2], circles[:, 2]
    active = json.loads(SUMMARY.read_text())["active"]
    active_pairs = [(a, b) for kind, a, b in active if kind == "P"]
    left = np.asarray([a for a, _ in active_pairs], dtype=int)
    right = np.asarray([b for _, b in active_pairs], dtype=int)
    evaluate = load_verifier()
    baseline = float(evaluate({"circles": circles.tolist()}))

    # A small positive safety margin above the strict gate.
    relative_gate = TARGET / baseline - 1.0
    radius_scale = relative_gate + 2e-12
    scaled_radii = radii * (1.0 + radius_scale)
    center = np.asarray([centers[0, 0], centers[0, 0]])
    rng = np.random.default_rng(0xBEEF)

    best_min_slack = -float("inf")
    best_pair_slack = -float("inf")
    best_perimeter_slack = -float("inf")
    exact_hits: list[dict[str, Any]] = []
    tested = 0

    while tested < args.samples:
        count = min(args.batch, args.samples - tested)
        exponents = rng.integers(10, 20, size=(count, 2))
        signs = np.where(rng.random((count, 2)) < 0.5, -1.0, 1.0)
        translations = signs * 1.25 * np.exp2(exponents)
        ulps = np.abs(np.spacing(translations))
        phase = rng.uniform(-1.0, 1.0, size=(count, 2)) * ulps
        center_scale = rng.uniform(-2e-9, 3e-9, size=count)
        trial_centers = (
            (centers[None, :, :] - center) * (1.0 + center_scale[:, None, None])
            + center
            + phase[:, None, :]
            + translations[:, None, :]
        )

        width = np.max(trial_centers[:, :, 0] + scaled_radii, axis=1) - np.min(
            trial_centers[:, :, 0] - scaled_radii, axis=1
        )
        height = np.max(trial_centers[:, :, 1] + scaled_radii, axis=1) - np.min(
            trial_centers[:, :, 1] - scaled_radii, axis=1
        )
        perimeter_slack = 2.0 + 1e-9 - width - height
        dx = trial_centers[:, left, 0] - trial_centers[:, right, 0]
        dy = trial_centers[:, left, 1] - trial_centers[:, right, 1]
        pair_slack = np.min(
            np.sqrt(dx * dx + dy * dy)
            - scaled_radii[left]
            - scaled_radii[right]
            + 1e-9,
            axis=1,
        )
        joint = np.minimum(perimeter_slack, pair_slack)
        index = int(np.argmax(joint))
        if float(joint[index]) > best_min_slack:
            best_min_slack = float(joint[index])
            best_pair_slack = float(pair_slack[index])
            best_perimeter_slack = float(perimeter_slack[index])

        for index in np.flatnonzero((perimeter_slack >= 0) & (pair_slack >= 0)):
            payload = {
                "circles": np.column_stack((trial_centers[index], scaled_radii)).tolist()
            }
            score = float(evaluate(payload))
            if np.isfinite(score):
                raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                exact_hits.append({"score": score, "payload_sha256": hashlib.sha256(raw).hexdigest()})
        tested += count

    result = {
        "baseline_score": baseline,
        "best_joint_slack": best_min_slack,
        "best_pair_slack_at_joint_best": best_pair_slack,
        "best_perimeter_slack_at_joint_best": best_perimeter_slack,
        "exact_hits": exact_hits,
        "radius_scale": radius_scale,
        "samples": tested,
        "seed_sha256": file_sha(SEED),
        "target": TARGET,
        "verifier_sha256": VERIFIER_SHA,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
