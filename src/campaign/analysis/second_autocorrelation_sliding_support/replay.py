#!/usr/bin/env python3
"""Independent deterministic replay for the frozen sliding-support campaign.

This file deliberately does not import ``search.py``.  It reconstructs every
candidate directly from the immutable seed, the JSON atom descriptions, and
the logged optimizer parameters, then evaluates a clean-room mirror of the
unchanged hash-pinned Arena formula.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy.signal import oaconvolve


HERE = Path(__file__).resolve().parent
ARENA = HERE.parents[2]
DEFAULT_RUN = HERE / "runs/20260815T064800Z-sliding-support"
VERIFIER = (
    ARENA
    / "campaign/state/problems/second-autocorrelation-inequality"
    / "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768.py"
)
VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
SEED_VALUES_SHA256 = "8ad79d6fa04b566b852138709d959df928a7ec7cd36143d03a80901c1b485e34"
SEED_SCORE = 0.9635881192968997
SCORE_TOLERANCE = 5.0e-15


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_values(values: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(values, dtype=np.float64).tobytes())


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_events(path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise RuntimeError(f"invalid JSONL at line {line_number}") from error
    return result


def write_json_idempotent(path: Path, value: Any) -> None:
    payload = (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"refusing to overwrite divergent receipt: {path}")
        return
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()


def check_verifier_hash() -> None:
    if sha256_file(VERIFIER) != VERIFIER_SHA256:
        raise RuntimeError("frozen verifier hash mismatch")


def exact_score(values: np.ndarray) -> float:
    """Clean-room mirror; the downloaded verifier is never executed on host."""

    function = np.asarray(values, dtype=np.float64)
    if function.ndim != 1 or np.any(function < -1.0e-6):
        raise ValueError("invalid C2 function")
    function = np.maximum(function, 0.0)
    if float(np.sum(function)) == 0.0:
        raise ValueError("function must have positive integral")
    convolution = oaconvolve(function, function, mode="full")
    intervals = np.diff(np.linspace(-0.5, 0.5, len(convolution) + 2))
    padded = np.concatenate(([0.0], convolution, [0.0]))
    left = padded[:-1]
    right = padded[1:]
    l2_squared = float(
        np.sum((intervals / 3.0) * (left**2 + left * right + right**2))
    )
    l1_norm = float(np.sum(np.abs(convolution)) / (len(convolution) + 1))
    infinity_norm = float(np.max(np.abs(convolution)))
    return float(l2_squared / (l1_norm * infinity_norm))


def normalize_mass(values: np.ndarray, mass: float) -> np.ndarray:
    result = np.maximum(np.asarray(values, dtype=np.float64), 0.0)
    total = float(result.sum())
    if not np.isfinite(total) or total <= 0.0:
        raise RuntimeError("invalid reconstructed candidate mass")
    return np.ascontiguousarray(result * (mass / total))


def reconstruct(seed: np.ndarray, event: dict[str, Any]) -> np.ndarray:
    atoms = event["spec"]["atoms"]
    parameters = np.asarray(
        event["optimization"]["parameters"], dtype=np.float64
    )
    if parameters.shape != (2 * len(atoms),):
        raise RuntimeError("logged parameter vector has the wrong shape")

    templates = [
        seed[
            int(atom["template_start"]) : int(atom["template_start"])
            + int(atom["length"])
        ].copy()
        for atom in atoms
    ]
    candidate = seed.copy()
    for atom in atoms:
        if atom["kind"] == "existing":
            start = int(atom["target_start"])
            candidate[start : start + int(atom["length"])] = 0.0

    for index, (atom, template) in enumerate(zip(atoms, templates, strict=True)):
        amplitude = float(parameters[2 * index])
        shift = float(parameters[2 * index + 1])
        integer_shift = math.floor(shift)
        fraction = float(shift - integer_shift)
        start = int(atom["target_start"]) + integer_shift
        stop = start + int(atom["length"])
        if start < 0 or stop + 1 > candidate.size:
            raise RuntimeError("reconstructed atom left the native domain")
        candidate[start:stop] += amplitude * (1.0 - fraction) * template
        candidate[start + 1 : stop + 1] += amplitude * fraction * template

    return normalize_mass(candidate, float(seed.sum()))


def topology(seed: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    scaled = normalize_mass(candidate, float(seed.sum()))
    threshold = float(seed.max() * 1.0e-10)
    before = seed > threshold
    after = scaled > threshold
    return {
        "material_threshold": threshold,
        "material_births": int(np.count_nonzero(after & ~before)),
        "material_deaths": int(np.count_nonzero(before & ~after)),
        "material_support_xor": int(np.count_nonzero(after ^ before)),
        "l1_moved_fraction": float(np.abs(scaled - seed).sum() / seed.sum()),
        "nonzero": int(np.count_nonzero(scaled)),
    }


def is_genuine(metrics: dict[str, Any]) -> bool:
    return bool(
        metrics["material_births"] >= 1
        and metrics["material_support_xor"] >= 2
        and metrics["l1_moved_fraction"] >= 1.0e-6
    )


def compare_topology(actual: dict[str, Any], logged: dict[str, Any]) -> None:
    for key in (
        "material_births",
        "material_deaths",
        "material_support_xor",
        "nonzero",
    ):
        if actual[key] != logged[key]:
            raise RuntimeError(f"topology mismatch for {key}")
    for key in ("material_threshold", "l1_moved_fraction"):
        if abs(float(actual[key]) - float(logged[key])) > 1.0e-18:
            raise RuntimeError(f"topology mismatch for {key}")


def assert_close(actual: float, expected: float, label: str) -> None:
    if abs(actual - expected) > SCORE_TOLERANCE:
        raise RuntimeError(
            f"{label} mismatch: actual={actual:.17g}, expected={expected:.17g}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    args = parser.parse_args()
    run = args.run.resolve()

    manifest = load_json(run / "input_manifest.json")
    summary = load_json(run / "summary.json")
    specs = load_json(run / "specs.json")
    events = load_events(run / "events.jsonl")
    if len(events) != 66 or events[0]["event"] != "start" or events[-1]["event"] != "complete":
        raise RuntimeError("event stream is incomplete")
    evaluations = [event for event in events if event["event"] == "evaluate"]
    if [event["evaluation"] for event in evaluations] != list(range(1, 65)):
        raise RuntimeError("evaluation sequence is not contiguous")
    if len(specs) != 8 or summary["evaluation_count"] != len(evaluations):
        raise RuntimeError("spec/evaluation count mismatch")

    check_verifier_hash()
    seed = np.load(run / "seed.npy", allow_pickle=False).astype(np.float64)
    seed = normalize_mass(seed, float(seed.sum()))
    if sha256_values(seed) != SEED_VALUES_SHA256:
        raise RuntimeError("seed value hash mismatch")
    if manifest["input_values_sha256"] != SEED_VALUES_SHA256:
        raise RuntimeError("manifest seed value hash mismatch")
    if sha256_file(run / "seed.npy") != manifest["input_file_sha256"]:
        raise RuntimeError("run seed file hash mismatch")
    seed_score = exact_score(seed)
    if seed_score != SEED_SCORE or manifest["seed_score"] != SEED_SCORE:
        raise RuntimeError("seed score mismatch")

    strict_gate = float(manifest["strict_gate"])
    best_score = seed_score
    best_candidate = seed
    best_evaluation: int | None = None
    best_topology_score = -math.inf
    best_topology_candidate: np.ndarray | None = None
    best_topology_evaluation: int | None = None
    gate_clearers: list[int] = []
    max_score_delta = 0.0
    replay_rows: list[dict[str, Any]] = []

    for event in evaluations:
        candidate = reconstruct(seed, event)
        candidate_hash = sha256_values(candidate)
        if candidate_hash != event["candidate_values_sha256"]:
            raise RuntimeError(
                f"candidate byte hash mismatch at evaluation {event['evaluation']}"
            )
        score = exact_score(candidate)
        delta = abs(score - float(event["score"]))
        max_score_delta = max(max_score_delta, delta)
        assert_close(score, float(event["score"]), f"score at evaluation {event['evaluation']}")

        metrics = topology(seed, candidate)
        compare_topology(metrics, event["topology"])
        genuine = is_genuine(metrics)
        clears_gate = bool(genuine and score >= strict_gate)
        if genuine != bool(event["genuine_topology"]):
            raise RuntimeError("genuine-topology classification mismatch")
        if clears_gate != bool(event["clears_gate"]):
            raise RuntimeError("gate classification mismatch")
        if clears_gate:
            gate_clearers.append(int(event["evaluation"]))

        if score > best_score:
            best_score = score
            best_candidate = candidate
            best_evaluation = int(event["evaluation"])
        if genuine and score > best_topology_score:
            best_topology_score = score
            best_topology_candidate = candidate
            best_topology_evaluation = int(event["evaluation"])

        replay_rows.append(
            {
                "evaluation": int(event["evaluation"]),
                "values_sha256": candidate_hash,
                "score": score,
                "genuine_topology": genuine,
                "clears_gate": clears_gate,
            }
        )

    assert_close(best_score, float(summary["best_score"]), "best score")
    if best_evaluation != int(summary["best_event"]["evaluation"]):
        raise RuntimeError("best-event mismatch")
    if sha256_values(best_candidate) != summary["best_values_sha256"]:
        raise RuntimeError("best-candidate hash mismatch")
    if best_topology_candidate is None or best_topology_evaluation is None:
        raise RuntimeError("no genuine topology-changing candidate was replayed")
    assert_close(
        best_topology_score,
        float(summary["best_topology_score"]),
        "best topology score",
    )
    if best_topology_evaluation != int(summary["best_topology_event"]["evaluation"]):
        raise RuntimeError("best-topology-event mismatch")
    if sha256_values(best_topology_candidate) != summary["best_topology_values_sha256"]:
        raise RuntimeError("best-topology candidate hash mismatch")
    if gate_clearers or summary["gate_clearer_count"] != 0 or summary["gate_cleared"]:
        raise RuntimeError("unexpected gate clearer")

    retained = np.load(run / "retained.npy", allow_pickle=False).astype(np.float64)
    best_topology = np.load(run / "best_topology.npy", allow_pickle=False).astype(np.float64)
    if not np.array_equal(retained, best_candidate):
        raise RuntimeError("retained.npy does not equal the replayed best candidate")
    if not np.array_equal(best_topology, best_topology_candidate):
        raise RuntimeError("best_topology.npy does not equal the replayed topology best")
    assert_close(exact_score(retained), best_score, "retained exact score")
    assert_close(
        exact_score(best_topology),
        best_topology_score,
        "best-topology exact score",
    )

    artifact_names = [
        "best_topology.npy",
        "events.jsonl",
        "gradient_check.json",
        "input_manifest.json",
        "retained.npy",
        "seed.npy",
        "specs.json",
        "summary.json",
    ]
    receipt = {
        "status": "PASS",
        "replay_kind": "independent reconstruction; no import from search.py",
        "replay_command": (
            "./.venv/bin/python "
            "campaign/analysis/second_autocorrelation_sliding_support/replay.py "
            "--run campaign/analysis/second_autocorrelation_sliding_support/"
            "runs/20260815T064800Z-sliding-support"
        ),
        "evaluation_count": len(evaluations),
        "reconstructed_candidate_hash_mismatches": 0,
        "maximum_absolute_score_delta": max_score_delta,
        "evaluation_replay_sha256": sha256_bytes(canonical_json(replay_rows)),
        "seed": {
            "score": seed_score,
            "values_sha256": sha256_values(seed),
        },
        "best_overall": {
            "evaluation": best_evaluation,
            "score": best_score,
            "gain_from_seed": best_score - seed_score,
            "gap_to_gate": strict_gate - best_score,
            "genuine_topology": False,
            "values_sha256": sha256_values(best_candidate),
        },
        "best_genuine_topology": {
            "evaluation": best_topology_evaluation,
            "score": best_topology_score,
            "gain_from_seed": best_topology_score - seed_score,
            "gap_to_gate": strict_gate - best_topology_score,
            "topology": topology(seed, best_topology_candidate),
            "values_sha256": sha256_values(best_topology_candidate),
        },
        "gate": {
            "strict_threshold": strict_gate,
            "clearer_count": 0,
            "cleared": False,
        },
        "frozen_verifier_sha256": sha256_file(VERIFIER),
        "artifact_file_sha256": {
            name: sha256_file(run / name) for name in artifact_names
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
    }
    write_json_idempotent(run / "independent_replay.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
