#!/usr/bin/env python3
"""Reproduce and independently screen the published 841-point d12 code.

This tool never imports or executes a downloaded verifier.  The only
authoritative score is obtained separately with ``campaign/arena verify``.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
SOURCE_COMMIT = "eba37f0368f62828780d1f9d90315b367d2a612f"
SOURCE_URL = (
    "https://raw.githubusercontent.com/k-nic/841_in_12D/"
    f"{SOURCE_COMMIT}/gram841_coordinates.txt"
)
SOURCE_SHA256 = "995264fe8be616cc546f04ef542dbf4ef6effe9ba5dfa4ceec1aa7e069f476a9"
VERIFIER_SHA256 = "eb043620439a6631451657013a12c66e55db43589431bcdad08e3b2189246ca8"
CORPUS_SHA256 = "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"
PAPERCLIP_CITATION = (
    "https://paperclip.gxl.ai/citations/papers/arx_2606.18984#L1"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def append_event(path: Path, event: dict[str, Any], previous: str | None) -> str:
    body = {**event, "previous_event_sha256": previous}
    event_hash = sha256(canonical_json(body))
    row = {**body, "event_sha256": event_hash}
    with path.open("ab") as handle:
        handle.write(canonical_json(row) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event_hash


def obtain_source(path: Path, allow_download: bool) -> bytes:
    if path.exists():
        data = path.read_bytes()
    elif allow_download:
        request = urllib.request.Request(
            SOURCE_URL, headers={"User-Agent": "EinsteinArena-reproducer/1"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
        if sha256(data) != SOURCE_SHA256:
            raise ValueError("downloaded source coordinates failed SHA-256 pin")
        atomic_write(path, data)
    else:
        raise FileNotFoundError(
            f"missing pinned source {path}; rerun without --offline once"
        )
    actual = sha256(data)
    if actual != SOURCE_SHA256:
        raise ValueError(f"source SHA-256 mismatch: {actual}")
    return data


def parse_coordinates(data: bytes) -> list[list[float]]:
    rows: list[list[float]] = []
    for line_number, raw in enumerate(data.decode("ascii").splitlines(), 1):
        if not raw.strip():
            continue
        row = [float(token) for token in raw.split()]
        if len(row) != 12:
            raise ValueError(f"line {line_number}: expected 12 coordinates")
        rows.append(row)
    if len(rows) != 841:
        raise ValueError(f"expected 841 vectors, got {len(rows)}")
    return rows


def decimal_certificate(vectors: list[list[float]]) -> dict[str, Any]:
    """Mirror the verifier's exact sufficient condition independently."""

    getcontext().prec = 40
    dec = [[Decimal(str(value)) for value in row] for row in vectors]
    norms = [sum((x * x for x in row), Decimal(0)) for row in dec]
    max_norm = max(norms)
    max_norm_index = norms.index(max_norm)

    min_distance: Decimal | None = None
    min_pair: tuple[int, int] | None = None
    max_dot: Decimal | None = None
    max_dot_pair: tuple[int, int] | None = None
    for i, j in itertools.combinations(range(len(dec)), 2):
        left, right = dec[i], dec[j]
        distance = sum(
            ((a - b) * (a - b) for a, b in zip(left, right)), Decimal(0)
        )
        dot = sum((a * b for a, b in zip(left, right)), Decimal(0))
        if min_distance is None or distance < min_distance:
            min_distance, min_pair = distance, (i, j)
        if max_dot is None or dot > max_dot:
            max_dot, max_dot_pair = dot, (i, j)

    assert min_distance is not None and min_pair is not None
    assert max_dot is not None and max_dot_pair is not None
    margin = min_distance - max_norm
    return {
        "condition": "min_pair_squared_distance >= max_squared_norm",
        "passes": margin >= 0,
        "max_squared_norm": str(max_norm),
        "max_squared_norm_index_zero_based": max_norm_index,
        "min_pair_squared_distance": str(min_distance),
        "min_pair_zero_based": list(min_pair),
        "exact_margin": str(margin),
        "max_raw_dot": str(max_dot),
        "max_raw_dot_pair_zero_based": list(max_dot_pair),
        "pair_count": len(vectors) * (len(vectors) - 1) // 2,
        "decimal_precision": getcontext().prec,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=HERE / "source" / "gram841_coordinates.txt",
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--run-id")
    args = parser.parse_args()

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = HERE / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    events = run_dir / "events.jsonl"
    previous: str | None = None
    previous = append_event(
        events,
        {
            "event": "run_started",
            "run_id": run_id,
            "source_commit": SOURCE_COMMIT,
            "source_sha256": SOURCE_SHA256,
            "verifier_sha256": VERIFIER_SHA256,
            "corpus_sha256": CORPUS_SHA256,
        },
        previous,
    )

    source = obtain_source(args.source.resolve(), allow_download=not args.offline)
    vectors = parse_coordinates(source)
    candidate_bytes = canonical_json({"vectors": vectors})
    candidate_hash = sha256(candidate_bytes)
    candidate_path = run_dir / "candidate_841.json"
    atomic_write(candidate_path, candidate_bytes)
    atomic_write(HERE / "candidate_841.json", candidate_bytes)
    previous = append_event(
        events,
        {
            "event": "candidate_materialized",
            "candidate_sha256": candidate_hash,
            "candidate_relative_path": str(candidate_path.relative_to(CAMPAIGN)),
            "shape": [841, 12],
        },
        previous,
    )

    exact = decimal_certificate(vectors)
    if not exact["passes"]:
        raise RuntimeError("published coordinate payload failed independent exact screen")
    certificate = {
        "schema_version": 1,
        "run_id": run_id,
        "candidate_sha256": candidate_hash,
        "candidate_relative_path": str(candidate_path.relative_to(CAMPAIGN)),
        "stable_candidate_relative_path": str(
            (HERE / "candidate_841.json").relative_to(CAMPAIGN)
        ),
        "source": {
            "repository": "https://github.com/k-nic/841_in_12D",
            "commit": SOURCE_COMMIT,
            "path": "gram841_coordinates.txt",
            "sha256": SOURCE_SHA256,
            "license_file_present": False,
        },
        "paperclip_line_pinned_citation": PAPERCLIP_CITATION,
        "verifier_sha256": VERIFIER_SHA256,
        "corpus_database_sha256": CORPUS_SHA256,
        "independent_decimal_screen": exact,
        "authoritative_verification": {
            "status": "pending_offline_controller_replay",
            "command": (
                "cd /Users/jacweath/EinsteinArena/campaign && "
                f"./arena verify kissing-number-d12 {candidate_path.relative_to(CAMPAIGN)}"
            ),
        },
    }
    certificate_bytes = json.dumps(certificate, indent=2, sort_keys=True).encode("utf-8")
    atomic_write(run_dir / "certificate.json", certificate_bytes)
    previous = append_event(
        events,
        {
            "event": "independent_exact_screen_passed",
            "candidate_sha256": candidate_hash,
            "exact_margin": exact["exact_margin"],
            "certificate_sha256": sha256(certificate_bytes),
        },
        previous,
    )
    summary = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "candidate": str(candidate_path),
        "candidate_sha256": candidate_hash,
        "source_sha256": SOURCE_SHA256,
        "verifier_sha256": VERIFIER_SHA256,
        "exact_margin": exact["exact_margin"],
        "last_event_sha256": previous,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
