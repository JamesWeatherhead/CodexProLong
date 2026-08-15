#!/usr/bin/env python3
"""Rebuild or check the target inventory from the compact public fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from core import (
    ACTIVE,
    DERIVED_INPUTS_PATH,
    HERE,
    INCUMBENT_SYSTEM,
    POINT_GROUP_DIMS,
    REFLECTION_LABELS,
    TARGET_MANIFEST_PATH,
    canonical_exchange,
    load_derived_inputs,
    load_seed,
    read_unresolved,
    reflect_triple,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def multihomogeneous_bezout(triples: tuple[tuple[int, int, int], ...]) -> int:
    """Coefficient of product point_group^dimension * z in the degree product."""
    caps = POINT_GROUP_DIMS
    state: dict[tuple[int, ...], int] = {(0,) * len(caps): 1}
    for triple in triples:
        updated: dict[tuple[int, ...], int] = {}
        for exponent, coefficient in state.items():
            for group in (*triple, 11):
                new_exponent = list(exponent)
                new_exponent[group] += 1
                if new_exponent[group] > caps[group]:
                    continue
                key = tuple(new_exponent)
                updated[key] = updated.get(key, 0) + coefficient
        state = updated
    return state.get(caps, 0)


def percentile(sorted_values: list[int], q: float) -> int:
    return sorted_values[round((len(sorted_values) - 1) * q)]


def build_manifest() -> dict[str, object]:
    fixture = load_derived_inputs()
    unresolved = read_unresolved()
    unresolved_pairs = {
        (tuple(row["outgoing"]), tuple(row["incoming"])) for row in unresolved
    }
    targets: list[dict[str, object]] = []
    orbit_members: dict[
        tuple[tuple[int, int, int], tuple[int, int, int]],
        list[tuple[tuple[int, int, int], tuple[int, int, int]]],
    ] = {}
    for row in unresolved:
        outgoing = tuple(row["outgoing"])
        incoming = tuple(row["incoming"])
        pair = (outgoing, incoming)
        canonical = canonical_exchange(outgoing, incoming)
        orbit_members.setdefault(canonical, []).append(pair)
        triples = tuple(t for t in ACTIVE if t != outgoing) + (incoming,)
        reflected = (reflect_triple(outgoing), reflect_triple(incoming))
        reflection_status = row["reflection_status"]
        if (reflected in unresolved_pairs) != (reflection_status == "unresolved"):
            raise AssertionError("derived reflection status is inconsistent")
        targets.append(
            {
                "inventory_index": row["inventory_index"],
                "pseudo_status": row["status"],
                "outgoing": list(outgoing),
                "incoming": list(incoming),
                "canonical_exchange": [list(canonical[0]), list(canonical[1])],
                "reflection_exchange": [list(reflected[0]), list(reflected[1])],
                "reflection_status": reflection_status,
                "multihomogeneous_bezout_bound": multihomogeneous_bezout(triples),
            }
        )

    bounds = sorted(int(target["multihomogeneous_bezout_bound"]) for target in targets)
    canonical_bounds = []
    for members in orbit_members.values():
        representative = members[0]
        triples = tuple(t for t in ACTIVE if t != representative[0]) + (
            representative[1],
        )
        canonical_bounds.append(multihomogeneous_bezout(triples))
    canonical_bounds.sort()

    seed = load_seed().astype(complex)
    residual = float(np.max(np.abs(INCUMBENT_SYSTEM.evaluate(seed))))
    jacobian = INCUMBENT_SYSTEM.jacobian(seed)
    singular_values = np.linalg.svd(jacobian, compute_uv=False)
    return {
        "schema": "heilbronn-gamma-monodromy-target-manifest-v2",
        "scope": {
            "unresolved_target_systems": len(targets),
            "reflection_orbits_touching_unresolved": len(orbit_members),
            "reflection_fixed_unresolved": sum(
                1
                for canonical, members in orbit_members.items()
                if len(members) == 1
                and (reflect_triple(canonical[0]), reflect_triple(canonical[1]))
                == canonical
            ),
            "active_equations": 17,
            "boundary_equalities_eliminated": 6,
            "free_barycentric_coordinates": 16,
            "variables_including_z": 17,
            "total_degree_bound_per_system": 2**17,
            "incumbent_natural_multihomogeneous_bezout_bound": (
                multihomogeneous_bezout(ACTIVE)
            ),
            "target_natural_multihomogeneous_bezout_bounds": {
                "minimum": bounds[0],
                "p25": percentile(bounds, 0.25),
                "median": percentile(bounds, 0.5),
                "p75": percentile(bounds, 0.75),
                "maximum": bounds[-1],
                "sum_without_symmetry_reduction": sum(bounds),
                "unique_values": len(set(bounds)),
            },
            "orbit_representative_bound_sum": sum(canonical_bounds),
            "orbit_representative_bound_median": percentile(canonical_bounds, 0.5),
            "warning": (
                "Multihomogeneous Bezout values are rigorous path upper bounds, not "
                "mixed volumes or root counts. A complete run must compute an affine "
                "mixed-volume/root count or pass a validated sparse trace test."
            ),
        },
        "incumbent_numeric_check": {
            "maximum_equation_residual": residual,
            "jacobian_rank": int(np.linalg.matrix_rank(jacobian)),
            "smallest_singular_value": float(singular_values[-1]),
        },
        "status_counts": {
            "private_census": fixture["private_run_aggregates"],
            "unresolved": dict(sorted(Counter(row["status"] for row in unresolved).items())),
            "reflection_counterpart": dict(
                sorted(Counter(row["reflection_status"] for row in unresolved).items())
            ),
        },
        "reflection": {
            "label_permutation": list(REFLECTION_LABELS),
            "spatial_map_on_barycentric_abc": "(a,b,c)->(c,b,a)",
            "involution": all(
                REFLECTION_LABELS[REFLECTION_LABELS[i]] == i for i in range(11)
            ),
            "active_set_invariant": sorted(map(reflect_triple, ACTIVE)) == sorted(ACTIVE),
        },
        "inputs": {
            "derived_inputs": {
                "path": DERIVED_INPUTS_PATH.name,
                "sha256": sha256_file(DERIVED_INPUTS_PATH),
            },
            "private_source_provenance": fixture["private_source_provenance"],
            "corpus_audit_claims": fixture["corpus_audit_claims"],
            "private_source_bytes_included": False,
        },
        "targets": sorted(
            targets,
            key=lambda target: (
                target["multihomogeneous_bezout_bound"],
                target["outgoing"],
                target["incoming"],
            ),
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check and args.output:
        parser.error("--check and --output are mutually exclusive")

    result = build_manifest()
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.check:
        if TARGET_MANIFEST_PATH.read_text() != encoded:
            raise SystemExit("target_manifest.json does not match derived_inputs.json")
        status = "PASS"
    else:
        output = args.output or TARGET_MANIFEST_PATH
        if not output.is_absolute() and output.parent == Path("."):
            output = HERE / output
        output.write_text(encoded)
        status = "WROTE"
    print(json.dumps({"status": status, **result["scope"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
