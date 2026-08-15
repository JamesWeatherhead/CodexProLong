#!/usr/bin/env python3
"""Deterministic, low-impact complex monodromy feasibility probe.

This is intentionally capped.  Stabilization is not a completeness proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

from core import (
    DERIVED_INPUTS_PATH,
    INCUMBENT_SYSTEM,
    STRICT_GATE,
    TARGET_MANIFEST_PATH,
    canonical_exchange,
    cluster_index,
    gamma_track_to_target,
    load_seed,
    metrics,
    newton,
    read_unresolved,
    target_system,
    track_rhs_segment,
)


def encode_complex(values: np.ndarray) -> list[list[float]]:
    return [[float(value.real), float(value.imag)] for value in values]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def random_rhs(rng: np.random.Generator, scale: float) -> np.ndarray:
    return scale * (rng.standard_normal(17) + 1j * rng.standard_normal(17))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("bounded_result.json"))
    parser.add_argument("--seed", type=int, default=20260815115727)
    parser.add_argument("--rhs-scale", type=float, default=0.025)
    parser.add_argument("--loops", type=int, default=24)
    parser.add_argument("--fruitless", type=int, default=10)
    parser.add_argument("--max-roots", type=int, default=12)
    parser.add_argument("--target-count", type=int, default=2)
    parser.add_argument("--seconds", type=float, default=35.0)
    args = parser.parse_args()

    started = time.perf_counter()
    rng = np.random.default_rng(args.seed)
    seed = load_seed().astype(complex)
    seed, seed_ok, seed_iterations, seed_residual = newton(
        INCUMBENT_SYSTEM, seed, tolerance=3e-14, max_iterations=20
    )
    if not seed_ok:
        raise RuntimeError(f"seed Newton refinement failed: residual={seed_residual}")

    base_rhs = random_rhs(rng, args.rhs_scale * 0.2)
    base_root, base_track = track_rhs_segment(
        INCUMBENT_SYSTEM,
        seed,
        np.zeros(17, dtype=complex),
        base_rhs,
        initial_step=0.025,
    )
    if not base_track["success"]:
        raise RuntimeError(f"failed to reach generic base: {base_track}")

    roots: list[np.ndarray] = [base_root]
    loop_records: list[dict[str, object]] = []
    fruitless = 0
    attempts = 0
    while (
        attempts < args.loops
        and fruitless < args.fruitless
        and len(roots) < args.max_roots
        and time.perf_counter() - started < args.seconds
    ):
        source_index = attempts % len(roots)
        current = roots[source_index]
        vertices = [
            base_rhs,
            random_rhs(rng, args.rhs_scale),
            random_rhs(rng, args.rhs_scale),
            base_rhs,
        ]
        legs = []
        success = True
        for rhs_start, rhs_target in zip(vertices, vertices[1:]):
            current, record = track_rhs_segment(
                INCUMBENT_SYSTEM,
                current,
                rhs_start,
                rhs_target,
                initial_step=0.025,
            )
            legs.append(record)
            if not record["success"]:
                success = False
                break
        endpoint_residual = float(
            np.max(np.abs(INCUMBENT_SYSTEM.evaluate(current) - base_rhs))
        )
        match = cluster_index(roots, current, 2e-7) if success else None
        discovered = bool(success and match is None and endpoint_residual <= 1e-9)
        if discovered:
            roots.append(current)
            match = len(roots) - 1
            fruitless = 0
        else:
            fruitless += 1
        loop_records.append(
            {
                "loop": attempts,
                "source_root": source_index,
                "success": success,
                "discovered": discovered,
                "endpoint_root": match,
                "endpoint_residual": endpoint_residual,
                "legs": legs,
            }
        )
        attempts += 1

    incumbent_specializations: list[dict[str, object]] = []
    for index, root in enumerate(roots):
        if time.perf_counter() - started >= args.seconds:
            break
        endpoint, record = track_rhs_segment(
            INCUMBENT_SYSTEM,
            root,
            base_rhs,
            np.zeros(17, dtype=complex),
            initial_step=0.025,
        )
        endpoint_residual = float(np.max(np.abs(INCUMBENT_SYSTEM.evaluate(endpoint))))
        incumbent_specializations.append(
            {
                "generic_root": index,
                "track": record,
                "endpoint_residual": endpoint_residual,
                "metrics": metrics(endpoint),
                "endpoint": encode_complex(endpoint),
            }
        )

    # Select distinct reflection orbits in increasing natural multihomogeneous
    # bound order from the frozen manifest produced by audit.py.
    manifest_path = TARGET_MANIFEST_PATH
    manifest = json.loads(manifest_path.read_text())
    selected_targets = []
    seen_orbits = set()
    for target in manifest["targets"]:
        canonical = tuple(tuple(v) for v in target["canonical_exchange"])
        if canonical in seen_orbits:
            continue
        seen_orbits.add(canonical)
        selected_targets.append(target)
        if len(selected_targets) >= args.target_count:
            break

    target_records: list[dict[str, object]] = []
    legal_gate_clearers: list[dict[str, object]] = []
    for target_index, target in enumerate(selected_targets):
        if time.perf_counter() - started >= args.seconds:
            break
        outgoing = tuple(target["outgoing"])
        incoming = tuple(target["incoming"])
        system = target_system(outgoing, incoming)
        paths = []
        for root_index, root in enumerate(roots):
            if time.perf_counter() - started >= args.seconds:
                break
            phase = float(rng.uniform(0, 2 * math.pi))
            gamma = complex(math.cos(phase), math.sin(phase))
            endpoint, record = gamma_track_to_target(root, base_rhs, system, gamma)
            endpoint_residual = float(np.max(np.abs(system.evaluate(endpoint))))
            root_metrics = metrics(endpoint)
            path = {
                "generic_root": root_index,
                "gamma": [gamma.real, gamma.imag],
                "track": record,
                "endpoint_residual": endpoint_residual,
                "metrics": root_metrics,
                "endpoint": encode_complex(endpoint),
            }
            paths.append(path)
            if (
                record["success"]
                and endpoint_residual <= 1e-9
                and root_metrics.get("gate_clearing")
            ):
                legal_gate_clearers.append(
                    {
                        "target_index": target_index,
                        "path_index": len(paths) - 1,
                        "score": root_metrics["score"],
                    }
                )
        target_records.append(
            {
                "outgoing": list(outgoing),
                "incoming": list(incoming),
                "canonical_exchange": target["canonical_exchange"],
                "multihomogeneous_bezout_bound": target[
                    "multihomogeneous_bezout_bound"
                ],
                "paths": paths,
            }
        )

    result = {
        "schema": "heilbronn-bounded-gamma-monodromy-probe-v1",
        "status": "candidate" if legal_gate_clearers else "bounded_no_candidate",
        "scope_caveat": (
            "Random monodromy stabilization is heuristic. This capped probe neither "
            "enumerates all generic roots nor certifies completeness of any target fiber."
        ),
        "config": {
            "seed": args.seed,
            "rhs_scale": args.rhs_scale,
            "loop_cap": args.loops,
            "fruitless_cap": args.fruitless,
            "root_cap": args.max_roots,
            "target_cap": args.target_count,
            "wall_seconds_cap": args.seconds,
        },
        "seed": {
            "newton_success": seed_ok,
            "newton_iterations": seed_iterations,
            "residual": seed_residual,
        },
        "generic_base": {
            "rhs": encode_complex(base_rhs),
            "initial_track": base_track,
            "roots_discovered": len(roots),
            "loop_attempts": attempts,
            "fruitless_at_stop": fruitless,
        },
        "loops": loop_records,
        "generic_roots": [encode_complex(root) for root in roots],
        "incumbent_specializations": incumbent_specializations,
        "target_probes": target_records,
        "legal_gate_clearers": legal_gate_clearers,
        "strict_gate": STRICT_GATE,
        "elapsed_seconds": time.perf_counter() - started,
        "inputs": {
            "derived_inputs_sha256": sha256_file(DERIVED_INPUTS_PATH),
            "target_manifest_sha256": sha256_file(manifest_path),
            "private_source_bytes_included": False,
        },
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "elapsed_seconds": result["elapsed_seconds"],
                "generic_roots": len(roots),
                "loop_attempts": attempts,
                "target_systems": len(target_records),
                "target_paths": sum(len(t["paths"]) for t in target_records),
                "legal_gate_clearers": len(legal_gate_clearers),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
