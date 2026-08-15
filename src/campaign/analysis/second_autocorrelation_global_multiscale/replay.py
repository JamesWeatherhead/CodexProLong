#!/usr/bin/env python3
"""Independent deterministic replay of a C2 multiscale bundle run."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
ARENA = ROOT.parents[2]
VERIFIER = (
    ARENA
    / "campaign/state/problems/second-autocorrelation-inequality"
    / "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768.py"
)
VERIFIER_SHA256 = "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"


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
    spec = importlib.util.spec_from_file_location("c2_independent_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_score(module: Any, values: np.ndarray) -> float:
    return float(module.verify_and_compute_c2(np.asarray(values, dtype=np.float64)))


def edges_for(n: int, segments: int) -> np.ndarray:
    return np.linspace(0, n, segments + 1, dtype=np.int64)


def block_mass_replacement(
    seed: np.ndarray, source: np.ndarray, segments: int
) -> np.ndarray:
    output = seed.copy()
    edges = edges_for(seed.size, segments)
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        seed_mass = float(seed[lo:hi].sum())
        source_mass = float(source[lo:hi].sum())
        if seed_mass > 0.0 and source_mass > 0.0:
            output[lo:hi] = source[lo:hi] * (seed_mass / source_mass)
    return output


def reconstruct(
    seed: np.ndarray,
    source: np.ndarray,
    mode: str,
    segments: int,
    indices: list[int],
    alpha: float,
) -> np.ndarray:
    replacement = source if mode == "raw" else block_mass_replacement(seed, source, segments)
    edges = edges_for(seed.size, segments)
    result = seed.copy()
    for index in indices:
        lo, hi = int(edges[index]), int(edges[index + 1])
        result[lo:hi] += alpha * (replacement[lo:hi] - seed[lo:hi])
    np.maximum(result, 0.0, out=result)
    result *= seed.sum() / result.sum()
    return result


def topology(seed: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
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


def write_or_verify_json(path: Path, value: Any) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    if path.exists():
        if path.read_bytes() != payload:
            raise RuntimeError(f"existing replay receipt differs: {path}")
        return
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    verifier = load_verifier()
    manifest = json.loads((run / "source_manifest.json").read_text())
    summary = json.loads((run / "summary.json").read_text())

    inputs: dict[str, np.ndarray] = {}
    input_audit: dict[str, Any] = {}
    for name, expected in manifest["inputs"].items():
        path = run / "inputs" / f"{name}.npy"
        if sha256_file(path) != expected["file_sha256"]:
            raise RuntimeError(f"input file hash mismatch: {name}")
        values = np.load(path, allow_pickle=False).astype(np.float64)
        if sha256_values(values) != expected["values_sha256"]:
            raise RuntimeError(f"input value hash mismatch: {name}")
        score = exact_score(verifier, values)
        if score != expected["score"]:
            raise RuntimeError(f"input score mismatch: {name}")
        inputs[name] = values
        input_audit[name] = {"score": score, "values_sha256": sha256_values(values)}

    seed = inputs["seed"]
    seed_mass = float(seed.sum())
    sources = {
        name: inputs[name] * (seed_mass / float(inputs[name].sum()))
        for name in ("public_2415", "public_2414", "mlai_2413")
    }
    sources["public_2415_reflected"] = sources["public_2415"][::-1].copy()
    sources["seed_reflected"] = seed[::-1].copy()
    for name, expected in manifest["derived_sources"].items():
        values = sources[name]
        if sha256_values(values) != expected["values_sha256"]:
            raise RuntimeError(f"derived source hash mismatch: {name}")
        if exact_score(verifier, values) != expected["score"]:
            raise RuntimeError(f"derived source score mismatch: {name}")

    events = [json.loads(line) for line in (run / "events.jsonl").read_text().splitlines()]
    evaluations = [event for event in events if event.get("event") == "evaluate"]
    if len(evaluations) != summary["evaluations"]:
        raise RuntimeError("evaluation count mismatch")

    best_score = -np.inf
    best_event: dict[str, Any] | None = None
    best_noncontrol = -np.inf
    best_noncontrol_event: dict[str, Any] | None = None
    best_support = -np.inf
    best_support_event: dict[str, Any] | None = None
    best_finite_topology = -np.inf
    best_finite_topology_event: dict[str, Any] | None = None
    candidate_bytes = 0

    for expected_index, event in enumerate(evaluations, start=1):
        if event["evaluation"] != expected_index:
            raise RuntimeError("nonconsecutive event index")
        candidate = reconstruct(
            seed,
            sources[event["source"]],
            event["mode"],
            int(event["segments"]),
            [int(value) for value in event["indices"]],
            float(event["alpha"]),
        )
        candidate_bytes += candidate.nbytes
        if sha256_values(candidate) != event["candidate_values_sha256"]:
            raise RuntimeError(f"candidate hash mismatch at {expected_index}")
        metrics = topology(seed, candidate)
        for key, observed in metrics.items():
            expected = event[key]
            if isinstance(observed, float):
                if observed != expected:
                    raise RuntimeError(f"metric mismatch {key} at {expected_index}")
            elif observed != expected:
                raise RuntimeError(f"metric mismatch {key} at {expected_index}")
        score = exact_score(verifier, candidate)
        if score != event["score"]:
            raise RuntimeError(f"score mismatch at {expected_index}: {score} != {event['score']}")
        if score > best_score:
            best_score, best_event = score, event

        full_mask = len(event["indices"]) == int(event["segments"])
        reflection_control = event["source"] == "seed_reflected" and event["alpha"] == 1.0 and full_mask
        known_parent_control = event["source"].startswith("public_2415") and event["alpha"] == 1.0 and full_mask
        if not reflection_control and not known_parent_control and score > best_noncontrol:
            best_noncontrol, best_noncontrol_event = score, event
        if (
            not reflection_control
            and not known_parent_control
            and event["material_support_xor"] > 0
            and score > best_support
        ):
            best_support, best_support_event = score, event
        if (
            not reflection_control
            and not known_parent_control
            and event["material_support_xor"] >= 1000
            and event["l1_moved_fraction"] >= 0.001
            and score > best_finite_topology
        ):
            best_finite_topology, best_finite_topology_event = score, event

    retained = np.load(run / "retained.npy", allow_pickle=False).astype(np.float64)
    best_changed = np.load(run / "best_changed.npy", allow_pickle=False).astype(np.float64)
    retained_score = exact_score(verifier, retained)
    if retained_score != summary["best_score"]:
        raise RuntimeError("retained score mismatch")
    if sha256_values(retained) != summary["retained_values_sha256"]:
        raise RuntimeError("retained hash mismatch")
    if sha256_values(best_changed) != summary["best_changed_values_sha256"]:
        raise RuntimeError("best-changed hash mismatch")
    if best_score != summary["best_changed_score"]:
        raise RuntimeError("event maximum mismatch")

    replay = {
        "status": "pass",
        "run": str(run),
        "verifier_sha256": VERIFIER_SHA256,
        "input_audit": input_audit,
        "evaluations_replayed": len(evaluations),
        "candidate_bytes_reconstructed": candidate_bytes,
        "retained_score": retained_score,
        "retained_values_sha256": sha256_values(retained),
        "event_maximum_score": best_score,
        "event_maximum": best_event,
        "best_noncontrol_score": best_noncontrol,
        "best_noncontrol": best_noncontrol_event,
        "best_material_support_mosaic_score": best_support,
        "best_material_support_mosaic": best_support_event,
        "finite_topology_definition": {
            "minimum_material_support_xor": 1000,
            "minimum_l1_moved_fraction": 0.001,
            "excludes_exact_reflection_and_whole_known_parent_controls": True,
        },
        "best_finite_topology_mosaic_score": best_finite_topology,
        "best_finite_topology_mosaic": best_finite_topology_event,
        "gate_cleared": bool(retained_score >= summary["strict_gate"]),
        "gap_to_gate": float(summary["strict_gate"] - retained_score),
    }
    write_or_verify_json(run / "independent_replay.json", replay)
    print(json.dumps(replay, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
