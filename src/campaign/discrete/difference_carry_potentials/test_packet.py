#!/usr/bin/env python3
"""Standalone stdlib-only test for a copied publication allowlist."""

from __future__ import annotations

import collections
import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "PUBLICATION_MANIFEST.json"
MODEL_SHA256 = "0fcb2054f099e398959e5318033f8969582becb5d6bbce072c40a6d455b0e4b4"
VERIFIER_SHA256 = "a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585"
INPUT_SHA256 = "64ff8b828048a103057a5359290ebe14338f56f1a30f4d41e82648f13e42a727"


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(contains_key(item, key) for item in value)
    return False


def required_quotients(gap: int, modulus: int, target: int) -> tuple[int, ...]:
    values: set[int] = set()
    quotient = 0
    while gap + quotient * modulus <= target:
        values.add(quotient)
        quotient += 1
    complement = modulus - gap
    quotient = 0
    while complement + quotient * modulus <= target:
        values.add(-(quotient + 1))
        quotient += 1
    return tuple(sorted(values))


def verify_event_chain(path: Path) -> tuple[int, str]:
    previous = "0" * 64
    count = 0
    for count, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        event = json.loads(line)
        if event["sequence"] != count or event["previous_hash"] != previous:
            raise AssertionError(f"event chain mismatch at line {count}")
        observed = event.pop("hash")
        expected = hashlib.sha256(canonical_bytes(event)).hexdigest()
        if observed != expected:
            raise AssertionError(f"event hash mismatch at line {count}")
        previous = observed
    return count, previous


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["schema"] != "difference-carry-potentials-publication-v2":
        raise AssertionError("unexpected publication manifest schema")
    entries = manifest["files"]
    if not isinstance(entries, list) or len(entries) != 21:
        raise AssertionError("unexpected publication allowlist shape")
    relatives = [record["path"] for record in entries]
    if relatives != sorted(relatives) or len(relatives) != len(set(relatives)):
        raise AssertionError("publication paths are not sorted and unique")
    for record in entries:
        relative = record["path"]
        portable = PurePosixPath(relative)
        if portable.is_absolute() or ".." in portable.parts:
            raise AssertionError(f"unsafe publication path: {relative}")
        path = ROOT / relative
        if not path.is_file():
            raise AssertionError(f"allowlisted file missing: {relative}")
        if path.stat().st_size != record["bytes"] or sha_file(path) != record["sha256"]:
            raise AssertionError(f"allowlisted size/hash mismatch: {relative}")

    frozen = json.loads((ROOT / "frozen_inputs.json").read_text(encoding="utf-8"))
    summary = json.loads(
        (ROOT / "runs/20260815T121057Z/summary.json").read_text(encoding="utf-8")
    )
    checkpoint = json.loads(
        (ROOT / "runs/20260815T121057Z/checkpoint.json").read_text(encoding="utf-8")
    )
    audit = json.loads(
        (ROOT / "runs/20260815T121057Z/audit.json").read_text(encoding="utf-8")
    )
    cleanroom = json.loads(
        (ROOT / "runs/20260815T121057Z/cleanroom_replay.json").read_text(
            encoding="utf-8"
        )
    )
    run_manifest = json.loads(
        (ROOT / "runs/20260815T121057Z/manifest.json").read_text(encoding="utf-8")
    )

    if sha_file(ROOT / "frozen_inputs.json") != INPUT_SHA256:
        raise AssertionError("frozen input hash mismatch")
    residues = frozen["core"]["residues"]
    modulus = frozen["core"]["modulus"]
    if hashlib.sha256(canonical_bytes(residues)).hexdigest() != frozen["core"]["residues_sha256"]:
        raise AssertionError("residue-core hash mismatch")
    if len(residues) != 90 or len(set(residues)) != 90 or residues != sorted(residues):
        raise AssertionError("residue-core shape mismatch")
    counts = collections.Counter(
        (a - b) % modulus for a in residues for b in residues if a != b
    )
    if set(counts) != set(range(1, modulus)) or set(counts.values()) != {1}:
        raise AssertionError("residue core is not a perfect cyclic difference set")

    low: list[tuple[int, int]] = []
    middle: list[tuple[int, int]] = []
    high: list[tuple[int, int]] = []
    adjacency = {residue: set() for residue in residues}
    for index, upper in enumerate(residues):
        for lower in residues[:index]:
            required = required_quotients(upper - lower, modulus, 49_110)
            if required == tuple(range(-6, 7)):
                low.append((upper, lower))
                adjacency[upper].add(lower)
                adjacency[lower].add(upper)
            elif required == tuple(range(-6, 6)):
                middle.append((upper, lower))
            elif required == tuple(range(-7, 6)):
                high.append((upper, lower))
            else:
                raise AssertionError("unexpected forced quotient interval")
    if (len(low), len(middle), high) != (1043, 2961, [(6967, 0)]):
        raise AssertionError("edge partition mismatch")
    if min(map(len, adjacency.values())) != 14:
        raise AssertionError("boundary minimum degree mismatch")
    distance = {0: 0}
    queue: collections.deque[int] = collections.deque([0])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency[current]:
            if neighbor not in distance:
                distance[neighbor] = distance[current] + 1
                queue.append(neighbor)
    if len(distance) != 90 or max(distance.values()) != 7:
        raise AssertionError("boundary connectivity/distance mismatch")

    facts = summary["facts"]
    if summary["outcome"] != "bounded_no_go" or summary["candidate_written"]:
        raise AssertionError("frozen outcome mismatch")
    if summary["solver"]["status"] != "INFEASIBLE":
        raise AssertionError("original solve status mismatch")
    if facts["model_sha256"] != MODEL_SHA256 or checkpoint["model_sha256"] != MODEL_SHA256:
        raise AssertionError("model hash pin mismatch")
    if sha_file(ROOT / "runs/20260815T121057Z/model.pb") != MODEL_SHA256:
        raise AssertionError("model bytes mismatch")
    if facts["normalized_shape_count"] != 220:
        raise AssertionError("shape count mismatch")
    if (facts["low_boundary_allowed_tuples"], facts["high_boundary_allowed_tuples"]) != (238, 238):
        raise AssertionError("compatibility-table count mismatch")
    if facts["middle_edges_omitted_from_relaxation"] != 2961:
        raise AssertionError("relaxation scope mismatch")
    if facts["cardinality_reduction"]["conclusion"] != "all_90_columns_have_size_4":
        raise AssertionError("cardinality reduction mismatch")
    if not audit["ok"] or audit["fresh_status"] != "INFEASIBLE":
        raise AssertionError("fresh replay receipt mismatch")
    if audit["verifier_sha256"] != VERIFIER_SHA256 or audit["model_sha256"] != MODEL_SHA256:
        raise AssertionError("audit hash pin mismatch")
    if not cleanroom["ok"] or cleanroom["status"] != "INFEASIBLE":
        raise AssertionError("clean-room replay receipt mismatch")
    if not cleanroom["model_bytes_equal"]:
        raise AssertionError("clean-room formula bytes were not identical")
    if cleanroom["model_sha256"] != MODEL_SHA256:
        raise AssertionError("clean-room model hash mismatch")

    expected_run_dir = (
        "campaign/discrete/difference_carry_potentials/runs/20260815T121057Z"
    )
    config = json.loads(
        (ROOT / "runs/20260815T121057Z/config.json").read_text(encoding="utf-8")
    )
    if config["input"] != "campaign/discrete/difference_carry_potentials/frozen_inputs.json":
        raise AssertionError("config input is not repository-relative")
    if config.get("path_encoding") != "repository-relative":
        raise AssertionError("config path encoding missing")
    if audit["run_dir"] != expected_run_dir or audit.get("path_encoding") != "repository-relative":
        raise AssertionError("audit run path is not repository-relative")
    first_event = json.loads(
        (ROOT / "runs/20260815T121057Z/events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    if first_event["payload"] != config:
        raise AssertionError("portable config and event payload differ")

    for relative, expected in run_manifest["files"].items():
        if sha_file(ROOT / "runs/20260815T121057Z" / relative) != expected:
            raise AssertionError(f"original run manifest mismatch: {relative}")
    event_count, last_hash = verify_event_chain(
        ROOT / "runs/20260815T121057Z/events.jsonl"
    )
    if event_count != 2 or checkpoint["last_event_hash"] != last_hash:
        raise AssertionError("checkpoint/event-chain mismatch")

    gate = frozen["leader"]["gate_score"]
    first_gate = next(
        coverage
        for coverage in range(49_109, 49_200)
        if float(Fraction(360**2, coverage)) < gate
    )
    if first_gate != 49_110:
        raise AssertionError("single-missing-integer gate mismatch")

    public_json = [
        manifest, frozen, summary, checkpoint, audit, cleanroom, run_manifest
    ]
    if any(contains_key(value, "set") for value in public_json):
        raise AssertionError("public JSON unexpectedly contains a candidate set")
    if any("candidate" in path.name.lower() for path in ROOT.rglob("*") if path.is_file()):
        raise AssertionError("candidate-like file exists in copied packet")

    text = "\n".join(
        (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
        for relative in relatives
    )
    secret_patterns = (
        r"gxl_[A-Za-z0-9_-]{20,}",
        r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}",
        r"github_pat_[A-Za-z0-9_]{20,}",
    )
    if any(re.search(pattern, text) for pattern in secret_patterns):
        raise AssertionError("credential-like string found in publication allowlist")
    machine_path_pattern = r"(?<!:)/(?:Users|home)/[^\s\"']+"
    if re.search(machine_path_pattern, text):
        raise AssertionError("machine-absolute path found in publication allowlist")
    if not (ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License"):
        raise AssertionError("license boundary missing")

    alias = ROOT / "MANIFEST.json"
    if alias.exists() and alias.read_bytes() != MANIFEST.read_bytes():
        raise AssertionError("local MANIFEST alias differs from publication manifest")

    print(
        "difference_carry_potentials copied packet: PASS "
        f"files={len(entries)} model={MODEL_SHA256[:12]}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
