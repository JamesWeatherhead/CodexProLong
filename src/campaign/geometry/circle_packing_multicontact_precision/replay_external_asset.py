#!/usr/bin/env python3
"""Hash-pin and replay the recovered ClaudeEvolve strict coordinate table."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

import verifier_formula


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
PAYLOAD = HERE / "recovered_claudeevolve_strict.json"
VERIFIER = verifier_formula.VERIFIER
EXPECTED_VERIFIER_SHA256 = verifier_formula.VERIFIER_SHA256
TARGET = 2.635983095360844


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def load_evaluate():
    verifier_formula.assert_verifier_hash()
    return verifier_formula.evaluate


def portable_path(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY.resolve()).as_posix()


def main() -> int:
    payload = json.loads(PAYLOAD.read_text())
    schema_valid = set(payload) == {"circles"}
    circles = np.asarray(payload["circles"], dtype=np.float64)
    schema_valid = bool(
        schema_valid and circles.shape == (26, 3) and np.isfinite(circles).all()
    )
    if not schema_valid:
        raise RuntimeError("asset does not satisfy the live API schema")

    score = float(load_evaluate()(payload))
    centers = circles[:, :2]
    radii = circles[:, 2]
    pair_overruns = []
    pair_gaps = []
    for i in range(26):
        for j in range(i + 1, 26):
            distance = float(np.linalg.norm(centers[i] - centers[j]))
            pair_gaps.append(distance - float(radii[i] + radii[j]))
            pair_overruns.append(float(radii[i] + radii[j]) - distance)
    wall_slacks = np.concatenate((centers - radii[:, None], 1.0 - radii[:, None] - centers))

    result = {
        "asset": "ClaudeEvolve paper strict coordinate table",
        "asset_source": "https://github.com/BudEcosystem/ClaudeEvolve/blob/main/docs/circle_packing_paper.md",
        "classification": "physical-strict",
        "payload": portable_path(PAYLOAD),
        "payload_sha256": sha256_file(PAYLOAD),
        "verifier": portable_path(VERIFIER),
        "verifier_sha256": sha256_file(VERIFIER),
        "evaluation_mirror": {
            "path": portable_path(Path(verifier_formula.__file__)),
            "sha256": sha256_file(Path(verifier_formula.__file__)),
            "frozen_verifier_executed": False,
        },
        "solution_schema": {"circles": "array of [x, y, r] triples"},
        "schema_valid": schema_valid,
        "literal_verifier_accepted": math.isfinite(score),
        "literal_verifier_score": score if math.isfinite(score) else None,
        "minimum_pair_gap": min(pair_gaps),
        "maximum_pair_overrun": max(0.0, max(pair_overruns)),
        "minimum_wall_slack": float(np.min(wall_slacks)),
        "maximum_wall_overrun": max(0.0, -float(np.min(wall_slacks))),
        "target_strictly_above": TARGET,
        "gap_to_gate": TARGET - score,
        "gate_clearing": math.isfinite(score) and score > TARGET,
        "source_claims": {
            "paper_full_precision": 2.6359829286,
            "readme_headline_without_recovered_coordinates": 2.6359835671240317,
        },
    }
    atomic_json(HERE / "external_asset_replay.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
