#!/usr/bin/env python3
"""Verify or explicitly regenerate the frozen publication manifest.

The default action is read-only.  A write requires ``--write``; refreshing the
publication timestamp additionally requires ``--refresh-timestamp``.  This
keeps ordinary inspection, including ``--help``, from mutating evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import datetime as dt
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "PUBLICATION_MANIFEST.json"
RECEIPT = Path("runs/20260815T093000Z/receipt.json")
RETAINED_DIR = Path(
    "runs/20260815T104000Z/psl4-metal-run-20260815T104000Z-validation"
)
RETAINED_AUDIT = Path("runs/20260815T104000Z/audit.json")
RETAINED_DISPATCHER_RECEIPT = Path(
    "runs/20260815T104000Z/dispatcher_receipt.json"
)
FILES = {
    "LICENSE": "license",
    "README.md": "overview and reproducibility",
    "HANDOFF.md": "frozen result and migration boundary",
    "PROVENANCE.md": "primary-source and local-input provenance",
    "psl4_metal_bfs.mm": "clean-room exact Objective-C++/Metal engine",
    "benchmark.py": "standalone differential benchmark",
    "concurrency_benchmark.py": "exact two-stream throughput and ETA benchmark",
    "dispatcher_benchmark.py": "durable two-stream dispatcher and ETA benchmark",
    "gpu_dispatch.py": "isolated append-only per-task dispatcher",
    "audit_run.py": "read-only exactly-once run audit",
    "verify_discovery.py": "standalone exact replay of both production discoveries",
    "test_packet.py": "copied-allowlist regression",
    "freeze.py": "deterministic manifest generator",
    "fixtures/shard0_reference.tsv": "factual canonical counter fixture",
    "fixtures/shard1_reference.tsv": "second factual canonical counter fixture",
    "fixtures/completed_shard_sample.tsv": "factual shard-size/CPU-time sample",
    "discoveries/psl4_class_04.json": "fourth retained symmetry-distinct exact PSL-4 class",
    "discoveries/psl4_class_05.json": "fifth retained symmetry-distinct exact PSL-4 class",
    str(RECEIPT): "full-shard exact benchmark receipt",
    "runs/20260815T093000Z/concurrency_receipt.json": "two-stream exact throughput receipt",
    "runs/20260815T093000Z/dispatcher_receipt.json": "earlier disposable-root dispatcher rate sample",
    str(RETAINED_AUDIT): "retained two-shard validation audit",
    str(RETAINED_DISPATCHER_RECEIPT): "retained two-shard dispatcher receipt",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(generated_at: str) -> dict:
    receipt_path = ROOT / RECEIPT
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    dispatcher_receipt = json.loads(
        (ROOT / RETAINED_DISPATCHER_RECEIPT).read_text(encoding="utf-8")
    )
    files = dict(FILES)
    retained_files = sorted(
        path for path in (ROOT / RETAINED_DIR).rglob("*") if path.is_file()
    )
    for path in retained_files:
        relative = str(path.relative_to(ROOT))
        if relative in files:
            raise RuntimeError(f"duplicate retained allowlist path: {relative}")
        if path.name == "psl4_metal_bfs":
            role = "retained validation Mach-O binary"
        elif path.name == "psl4_metal_bfs.mm":
            role = "retained validation archived source"
        elif path.name == "config.json":
            role = "retained validation frozen config"
        elif path.name == "initialization.json":
            role = "retained validation self-test receipt"
        elif path.name == "journal.tsv":
            role = "retained validation reconstructed shard journal"
        elif path.name == "receipt.json" and path.parent.name == "shards":
            role = "retained validation shard receipt"
        elif path.name == "receipt.json":
            role = "retained validation shard receipt"
        elif path.suffix == ".json" and path.parent.name == "tasks":
            role = "retained validation task receipt"
        elif path.name.endswith(".lock"):
            role = "retained validation lock inode"
        else:
            role = "retained validation run artifact"
        files[relative] = role
    entries = []
    for relative, role in files.items():
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        entries.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "license": "MIT",
                "role": role,
            }
        )
    return {
        "schema": "psl4-metal-publication-manifest-v1",
        "generated_at": generated_at,
        "source_receipt_generated_at": receipt["generated_at"],
        "packet_license": "MIT",
        "license_holder": "James Weatherhead",
        "platform_scope": "macOS with Apple Metal",
        "receipt_sha256": sha256(receipt_path),
        "retained_validation_artifact_set_sha256": dispatcher_receipt[
            "validation_provenance"
        ]["artifact_set_sha256"],
        "retained_validation_audit_sha256": sha256(ROOT / RETAINED_AUDIT),
        "retained_validation_dispatcher_receipt_sha256": sha256(
            ROOT / RETAINED_DISPATCHER_RECEIPT
        ),
        "files": entries,
        "excluded": [
            "PUBLICATION_MANIFEST.json (self-hash intentionally omitted)",
            "__pycache__/ and *.pyc",
            "unretained Mach-O binaries and Metal compiler artifacts",
            "temporary benchmark/concurrency outputs",
            "canonical CPU run directories, journals, logs, and binaries",
            "production_runs/ active proof state and control handoffs",
            "credentials, API keys, environment dumps, and host-private paths",
        ],
    }


def encode_manifest(manifest: dict) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()


def write_manifest(encoded: bytes) -> None:
    temporary = MANIFEST.with_name(f".{MANIFEST.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, MANIFEST)
        directory = os.open(ROOT, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="atomically write the recomputed manifest (otherwise check only)",
    )
    parser.add_argument(
        "--refresh-timestamp",
        action="store_true",
        help="with --write, set generated_at to the current UTC time",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.refresh_timestamp and not args.write:
        raise SystemExit("--refresh-timestamp requires --write")
    if args.refresh_timestamp or not MANIFEST.is_file():
        generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
    else:
        existing = json.loads(MANIFEST.read_text(encoding="utf-8"))
        generated_at = existing["generated_at"]
    encoded = encode_manifest(build_manifest(generated_at))
    if args.write:
        write_manifest(encoded)
    else:
        if not MANIFEST.is_file():
            raise FileNotFoundError(MANIFEST)
        if MANIFEST.read_bytes() != encoded:
            raise RuntimeError(
                "publication manifest is stale; review changes, then run "
                "freeze.py --write --refresh-timestamp"
            )
    print(sha256(MANIFEST))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
