#!/usr/bin/env python3
"""Verify the self-contained C2 public allowlist and compact receipts.

Copyright (c) 2026 C2 Native Basin contributors. MIT License.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PACKET = Path(__file__).resolve().parent
MANIFEST = PACKET / "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path.name}")
    return value


def _portable_relative_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def verify_allowlist(manifest: dict[str, Any]) -> dict[str, Any]:
    entries = manifest["allowlist"]
    expected: dict[str, dict[str, Any]] = {}
    for entry in entries:
        relative = entry["path"]
        if not _portable_relative_path(relative):
            raise ValueError(f"nonportable allowlist path: {relative!r}")
        if relative in expected:
            raise ValueError(f"duplicate allowlist path: {relative}")
        expected[relative] = entry

    actual = {
        path.relative_to(PACKET).as_posix()
        for path in PACKET.rglob("*")
        if path.is_file()
    }
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        extra = sorted(actual - set(expected))
        raise ValueError(f"packet file-set mismatch: missing={missing}, extra={extra}")

    total_bytes = 0
    for relative, entry in sorted(expected.items()):
        path = PACKET / relative
        total_bytes += path.stat().st_size
        if relative == "manifest.json":
            if entry.get("sha256") is not None or entry.get("bytes") is not None:
                raise ValueError("self-referential manifest hash policy violated")
            continue
        if path.stat().st_size != entry["bytes"]:
            raise ValueError(f"byte-size mismatch: {relative}")
        if sha256_file(path) != entry["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {relative}")
    return {
        "allowlist_files": len(expected),
        "allowlist_bytes_including_manifest": total_bytes,
    }


def verify_receipts(evidence: dict[str, Any]) -> dict[str, Any]:
    gate = evidence["gate"]
    pilot = evidence["canonical_mac_pilot"]
    bundle = evidence["canonical_bundle_pilot"]
    boundary = evidence["public_packet_replay_boundary"]

    if abs(
        gate["public_leader"]
        + gate["minimum_improvement"]
        - gate["strict_gate"]
    ) > 2.0e-16:
        raise ValueError("strict-gate arithmetic mismatch")
    if pilot["member_steps"] != pilot["population"] * pilot["steps"]:
        raise ValueError("member-step arithmetic mismatch")
    if abs(
        gate["strict_gate"]
        - pilot["best_exact_score"]
        - pilot["gap_to_strict_gate"]
    ) > 2.0e-15:
        raise ValueError("reported strict-gate gap mismatch")
    if pilot["nfft"] < 2 * pilot["native_n"] - 1:
        raise ValueError("FFT length is too short")
    if pilot["nfft"] & (pilot["nfft"] - 1):
        raise ValueError("FFT length is not a power of two")
    if bundle["input_score"] != pilot["best_exact_score"]:
        raise ValueError("bundle input does not match the pilot receipt")
    if bundle["same_point_exact_active_count"] < 2:
        if bundle["support_insertion_performed"]:
            raise ValueError("single-active bundle incorrectly ran insertion")
        if bundle["single_lag_substitution_performed"]:
            raise ValueError("single-active bundle substituted a lag")
    if not all(
        len(value) == 64 and all(character in "0123456789abcdef" for character in value)
        for section in (
            pilot,
            bundle,
            evidence["internal_source_receipts"],
        )
        for key, value in section.items()
        if key.endswith("sha256") or key.endswith(".py")
    ):
        raise ValueError("malformed SHA-256 receipt")
    if not (
        boundary["receipt_hash_and_arithmetic_replay_only"]
        and not boundary["numeric_checkpoint_recomputation_claimed"]
        and not boundary["raw_arrays_included"]
        and not boundary["frozen_verifier_included"]
    ):
        raise ValueError("public replay boundary was weakened")
    return {
        "native_n": pilot["native_n"],
        "member_steps": pilot["member_steps"],
        "best_exact_score_receipt": pilot["best_exact_score"],
        "gap_to_strict_gate": pilot["gap_to_strict_gate"],
        "gate_cleared": pilot["gate_cleared"],
        "bundle_status": bundle["status"],
    }


def verify_provenance(provenance: dict[str, Any]) -> dict[str, Any]:
    boundary = provenance["clean_room_boundary"]
    forbidden = (
        boundary["copied_paper_text"]
        or boundary["copied_repository_code"]
        or boundary["copied_coefficients"]
        or boundary["embedded_third_party_bytes"]
        or boundary["network_required_for_replay"]
    )
    if forbidden:
        raise ValueError("clean-room provenance boundary was weakened")
    paper = provenance["sources"][0]
    repository = provenance["sources"][1]
    if paper["paperclip_id"] != "arx_2508.02803":
        raise ValueError("unexpected Paperclip identifier")
    if not paper["paperclip_line_citation"].endswith("#L19-L38"):
        raise ValueError("Paperclip citation is not line-pinned")
    if repository["license"] != "MIT" or repository["bytes_incorporated"]:
        raise ValueError("repository license/byte boundary mismatch")
    return {
        "paperclip_id": paper["paperclip_id"],
        "repository": repository["repository"],
        "repository_license": repository["license"],
        "third_party_bytes": 0,
    }


def verify_h100_configs() -> dict[str, Any]:
    phase_a = load_json(PACKET / "configs" / "h100_phase_a.json")
    phase_b = load_json(PACKET / "configs" / "h100_phase_b.json")
    histories = len(phase_a["seeds"])
    per_history = phase_a["population"] * phase_a["steps_per_history"]
    if per_history != phase_a["member_steps_per_history"]:
        raise ValueError("H100 per-history member-step mismatch")
    if histories * per_history != phase_a["total_member_steps"]:
        raise ValueError("H100 total member-step mismatch")
    audits = phase_a["steps_per_history"] // phase_a["verify_every_steps"] + 2
    if audits != phase_a["audit_passes_per_history"]:
        raise ValueError("H100 audit-pass mismatch")
    exact_per_history = audits * phase_a["population"]
    if exact_per_history != phase_a["exact_member_evaluations_per_history"]:
        raise ValueError("H100 exact-evaluation mismatch")
    if histories * exact_per_history != phase_a["total_exact_member_evaluations"]:
        raise ValueError("H100 total exact-evaluation mismatch")
    if not phase_b["require_true_multi_active_lag_bundle"]:
        raise ValueError("H100 bundle no longer requires true multi-active lags")
    if phase_b["single_lag_substitution_allowed"]:
        raise ValueError("H100 bundle now allows single-lag substitution")
    return {
        "histories": histories,
        "total_member_steps": phase_a["total_member_steps"],
        "total_exact_member_evaluations": phase_a[
            "total_exact_member_evaluations"
        ],
    }


def verify_packet() -> dict[str, Any]:
    manifest = load_json(MANIFEST)
    if manifest["schema"] != 1:
        raise ValueError("unsupported manifest schema")
    allowlist = verify_allowlist(manifest)
    receipts = verify_receipts(load_json(PACKET / "evidence.json"))
    provenance = verify_provenance(load_json(PACKET / "provenance.json"))
    h100 = verify_h100_configs()
    return {
        "status": "PASS",
        "manifest_sha256": sha256_file(MANIFEST),
        "manifest_self_hash_policy": manifest["packet"]["self_hash_policy"],
        "allowlist": allowlist,
        "excluded_lane_files": manifest["inventory"]["excluded_files"],
        "excluded_lane_bytes": manifest["inventory"]["excluded_bytes"],
        "receipts": receipts,
        "provenance": provenance,
        "h100_plan": h100,
    }


def main() -> int:
    print(json.dumps(verify_packet(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
