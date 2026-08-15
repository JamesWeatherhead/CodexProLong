#!/usr/bin/env python3
"""Standalone copied-allowlist and adversarial regression for the frozen packet."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "PUBLICATION_MANIFEST.json"
RETAINED_ROOT = (
    ROOT
    / "runs"
    / "20260815T104000Z"
    / "psl4-metal-run-20260815T104000Z-validation"
)
RETAINED_AUDIT = ROOT / "runs" / "20260815T104000Z" / "audit.json"
RETAINED_DISPATCHER_RECEIPT = (
    ROOT / "runs" / "20260815T104000Z" / "dispatcher_receipt.json"
)
FORBIDDEN = (
    b"/" + b"Users" + b"/",
    b"gxl" + b"_",
    b"sk-" + b"proj-",
    b"BEGIN " + b"PRIVATE KEY",
)
PUBLICATION_EXPORT = ROOT / "PUBLICATION_EXPORT.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run(
    command: list[str],
    *,
    timeout: int = 300,
    cwd: Path = ROOT,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
        env=env,
    )


def canonical_json(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def rewrite_json(path: Path, payload: dict) -> None:
    os.chmod(path, 0o644)
    path.write_bytes(canonical_json(payload))
    os.chmod(path, 0o444)


def validate_manifest() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "psl4-metal-publication-manifest-v1"
        or manifest.get("license_holder") != "James Weatherhead"
        or manifest.get("packet_license") != "MIT"
    ):
        raise AssertionError("publication manifest envelope mismatch")
    generated_at = parse_aware_timestamp(
        manifest.get("generated_at"), "publication manifest"
    )
    source_generated_at = parse_aware_timestamp(
        manifest.get("source_receipt_generated_at"), "source benchmark receipt"
    )
    if generated_at < source_generated_at:
        raise AssertionError("manifest timestamp predates its source receipt")
    allowed = {"PUBLICATION_MANIFEST.json"}
    for entry in manifest["files"]:
        path = ROOT / entry["path"]
        if not path.is_file():
            raise AssertionError(f"missing allowlisted file: {entry['path']}")
        if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            raise AssertionError(f"manifest mismatch: {entry['path']}")
        if entry.get("license") != "MIT":
            raise AssertionError(f"unexpected file license: {entry['path']}")
        allowed.add(entry["path"])
        data = path.read_bytes()
        for marker in FORBIDDEN:
            if marker in data:
                raise AssertionError(f"private marker {marker!r} in {entry['path']}")
    if PUBLICATION_EXPORT.is_file():
        validate_publication_export(manifest)
        allowed.add(PUBLICATION_EXPORT.name)
    observed = {
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and "production_runs" not in path.parts
        and path.suffix != ".pyc"
    }
    if observed != allowed:
        raise AssertionError(
            f"allowlist drift: extra={sorted(observed-allowed)}, "
            f"missing={sorted(allowed-observed)}"
        )
    receipt = ROOT / "runs" / "20260815T093000Z" / "receipt.json"
    if sha256(receipt) != manifest.get("receipt_sha256"):
        raise AssertionError("top-level receipt hash mismatch")
    dispatcher = json.loads(
        RETAINED_DISPATCHER_RECEIPT.read_text(encoding="utf-8")
    )
    if (
        manifest.get("retained_validation_audit_sha256") != sha256(RETAINED_AUDIT)
        or manifest.get("retained_validation_dispatcher_receipt_sha256")
        != sha256(RETAINED_DISPATCHER_RECEIPT)
        or manifest.get("retained_validation_artifact_set_sha256")
        != dispatcher.get("validation_provenance", {}).get("artifact_set_sha256")
    ):
        raise AssertionError("manifest retained-validation pin mismatch")
    return manifest


def validate_publication_export(manifest: dict) -> None:
    publication = json.loads(PUBLICATION_EXPORT.read_text(encoding="utf-8"))
    if (
        publication.get("schema_version") != 1
        or publication.get("canonical_manifest")
        != "analytic/flat_psl4_hardware/PUBLICATION_MANIFEST.json"
        or publication.get("canonical_manifest_sha256") != sha256(MANIFEST)
    ):
        raise AssertionError("publication export envelope mismatch")
    records = publication.get("files")
    if not isinstance(records, list) or len(records) != len(manifest["files"]):
        raise AssertionError("publication export cardinality mismatch")
    by_path = {record.get("path"): record for record in records}
    if len(by_path) != len(records):
        raise AssertionError("duplicate publication export path")
    for entry in manifest["files"]:
        record = by_path.get(entry["path"])
        path = ROOT / entry["path"]
        if not isinstance(record, dict) or (
            record.get("canonical_sha256") != entry["sha256"]
            or record.get("canonical_bytes") != entry["bytes"]
            or record.get("public_sha256") != sha256(path)
            or record.get("public_bytes") != path.stat().st_size
            or type(record.get("portable_path_rewrite")) is not bool
        ):
            raise AssertionError(f"publication export mismatch: {entry['path']}")


def validate_freeze_is_read_only() -> None:
    before = MANIFEST.read_bytes()
    help_result = run(
        [sys.executable, str(ROOT / "freeze.py"), "--help"],
        timeout=30,
    )
    if "--write" not in help_result.stdout or MANIFEST.read_bytes() != before:
        raise AssertionError("freeze --help mutated the publication manifest")
    run([sys.executable, str(ROOT / "freeze.py")], timeout=30)
    if MANIFEST.read_bytes() != before:
        raise AssertionError("read-only freeze check mutated the publication manifest")


def validate_quick_engine() -> dict:
    completed = run([sys.executable, str(ROOT / "benchmark.py")], timeout=120)
    receipt = json.loads(completed.stdout)
    if receipt.get("status") != "pass" or receipt.get("mode") != "quick":
        raise AssertionError("quick differential benchmark failed")
    task = receipt["hard_task"]["tasks"][0]
    if (
        task["task_index"] != 351916
        or task["nodes"] != 82824482
        or task["exact_checks"] != 182221485
        or task["valid_leaves"] != 1
        or len(task["answers"]) != 1
    ):
        raise AssertionError("hard-task exact fixture mismatch")
    return receipt


def validate_discovery() -> dict:
    completed = run(
        [sys.executable, str(ROOT / "verify_discovery.py")],
        timeout=30,
    )
    receipt = json.loads(completed.stdout)
    if (
        receipt.get("status") != "pass"
        or receipt.get("discovered_class_count") != 2
        or receipt.get("all_exact_peak_sidelobes") != 4
        or receipt.get("all_cpu_metal_counters_match") is not True
        or receipt.get("pairwise_symmetry_distinct") is not True
        or receipt.get("symmetry_distinct_public_fixture_count") != 3
        or receipt.get("retained_corpus_solution_count") != 24
        or receipt.get("retained_corpus_symmetry_match_count") != 0
        or receipt.get("any_clears_first_place_gate") is not False
        or [item.get("name") for item in receipt.get("class_summaries", [])]
        != ["psl4_class_04", "psl4_class_05"]
    ):
        raise AssertionError("production discovery replay failed")
    for item in receipt["class_summaries"]:
        if (
            item.get("exact_peak_sidelobe") != 4
            or item.get("cpu_metal_counters_match") is not True
            or item.get("clears_first_place_gate") is not False
        ):
            raise AssertionError(f"discovery summary mismatch: {item.get('name')}")
    return receipt


def parse_aware_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise AssertionError(f"missing timestamp: {label}")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AssertionError(f"naive timestamp: {label}")
    if parsed > datetime.now(timezone.utc):
        raise AssertionError(f"future timestamp: {label}")
    return parsed


def validate_retained_dispatcher_receipt() -> dict:
    sys.path.insert(0, str(ROOT))
    import gpu_dispatch

    receipt = json.loads(RETAINED_DISPATCHER_RECEIPT.read_text(encoding="utf-8"))
    required_keys = {
        "schema", "generated_at", "status", "scope", "source_sha256",
        "binary_sha256", "config_schema", "initialization_engine_sha256",
        "initialization_self_test", "virtual_shards", "shards", "task_receipts",
        "complete_shards", "comparison", "task_external_wall_sums",
        "validation_provenance", "two_stream", "memory_evidence", "task_size_sample",
    }
    if set(receipt) != required_keys:
        raise AssertionError("retained dispatcher receipt field set mismatch")
    parse_aware_timestamp(receipt.get("generated_at"), "dispatcher receipt")
    if (
        receipt.get("schema") != "psl4-metal-durable-dispatcher-benchmark-v1"
        or receipt.get("status") != "pass"
        or receipt.get("scope") != "exactly two reference shards; never a production run"
        or receipt.get("virtual_shards") != 8192
        or receipt.get("shards") != [0, 1]
        or receipt.get("task_receipts") != 182
        or receipt.get("complete_shards") != 2
        or receipt.get("initialization_self_test") != gpu_dispatch.SELF_TEST_MARKER
    ):
        raise AssertionError("retained dispatcher receipt envelope mismatch")

    relative = str(RETAINED_ROOT.relative_to(ROOT))
    provenance = receipt.get("validation_provenance")
    if not isinstance(provenance, dict) or provenance != {
        "retained": True,
        "run_name": RETAINED_ROOT.name,
        "retained_relative_path": relative,
        "config_sha256": sha256(RETAINED_ROOT / "config.json"),
        "initialization_sha256": sha256(RETAINED_ROOT / "initialization.json"),
        "artifact_set_sha256": provenance.get("artifact_set_sha256"),
        "audit_evidence_sha256": sha256(RETAINED_AUDIT),
    }:
        raise AssertionError("retained validation provenance mismatch")

    config = json.loads((RETAINED_ROOT / "config.json").read_text(encoding="utf-8"))
    initialization = json.loads(
        (RETAINED_ROOT / "initialization.json").read_text(encoding="utf-8")
    )
    parse_aware_timestamp(config.get("created_at"), "retained config")
    parse_aware_timestamp(initialization.get("created_at"), "retained initialization")
    if (
        receipt["source_sha256"] != sha256(ROOT / "psl4_metal_bfs.mm")
        or receipt["source_sha256"] != sha256(
            RETAINED_ROOT / "artifacts" / "psl4_metal_bfs.mm"
        )
        or receipt["binary_sha256"] != config.get("binary_sha256")
        or receipt["binary_sha256"] != sha256(
            RETAINED_ROOT / "artifacts" / "psl4_metal_bfs"
        )
        or receipt["config_schema"] != config.get("schema")
        or receipt["initialization_engine_sha256"]
        != initialization.get("engine_sha256")
    ):
        raise AssertionError("retained source/binary/config/init pin mismatch")

    completed = run(
        [
            sys.executable,
            str(ROOT / "audit_run.py"),
            "--run-dir",
            str(RETAINED_ROOT),
            "--allow-incomplete",
        ],
        timeout=120,
    )
    reconstructed_audit = json.loads(completed.stdout)
    audit_evidence = json.loads(RETAINED_AUDIT.read_text(encoding="utf-8"))
    parse_aware_timestamp(audit_evidence.get("generated_at"), "retained audit")
    if (
        set(audit_evidence) != {
            "schema", "generated_at", "status", "run_name",
            "retained_relative_path", "audit",
        }
        or audit_evidence.get("schema") != "psl4-metal-retained-validation-audit-v1"
        or audit_evidence.get("status") != "pass"
        or audit_evidence.get("run_name") != RETAINED_ROOT.name
        or audit_evidence.get("retained_relative_path") != relative
        or audit_evidence.get("audit") != reconstructed_audit
        or provenance["artifact_set_sha256"]
        != reconstructed_audit.get("artifact_set_sha256")
        or reconstructed_audit.get("status") != "incomplete"
        or reconstructed_audit.get("task_receipt_count") != 182
        or reconstructed_audit.get("unique_task_count") != 182
        or reconstructed_audit.get("complete_shards") != 2
        or reconstructed_audit.get("missing_task_count") != 730_628
        or reconstructed_audit.get("exactly_once") is not False
    ):
        raise AssertionError("retained audit semantics mismatch")

    task_files = list((RETAINED_ROOT / "shards").glob("*/tasks/*.json"))
    shard_receipts = list((RETAINED_ROOT / "shards").glob("*/receipt.json"))
    if len(task_files) != 182 or len(shard_receipts) != 2:
        raise AssertionError("retained evidence tree cardinality mismatch")
    expected_fixture_hashes = {
        "0": sha256(ROOT / "fixtures" / "shard0_reference.tsv"),
        "1": sha256(ROOT / "fixtures" / "shard1_reference.tsv"),
    }
    for shard, expected_tasks in (("0", 84), ("1", 98)):
        comparison = receipt.get("comparison", {}).get(shard, {})
        shard_receipt = json.loads(
            (
                RETAINED_ROOT
                / "shards"
                / f"{int(shard):06d}"
                / "receipt.json"
            ).read_text(encoding="utf-8")
        )
        observed_wall_sum = sum(
            json.loads(path.read_text(encoding="utf-8"))["external_wall_seconds"]
            for path in (
                RETAINED_ROOT / "shards" / f"{int(shard):06d}" / "tasks"
            ).glob("*.json")
        )
        if (
            comparison.get("task_count") != expected_tasks
            or comparison.get("counter_or_answer_mismatches") != 0
            or comparison.get("reference_sha256") != expected_fixture_hashes[shard]
            or comparison.get("totals") != shard_receipt.get("totals")
            or not math.isclose(
                receipt.get("task_external_wall_sums", {}).get(shard, -1),
                observed_wall_sum,
                rel_tol=1e-12,
            )
        ):
            raise AssertionError(f"retained fixture comparison mismatch: {shard}")

    two_stream = receipt.get("two_stream")
    if not isinstance(two_stream, dict) or set(two_stream) != {
        "external_wall_seconds", "combined_nodes", "nodes_per_second",
        "whole_run_eta_hours", "sample_min_eta_hours", "sample_max_eta_hours",
        "speedup_vs_active_8_worker_cpu_eta",
    }:
        raise AssertionError("retained throughput field set mismatch")
    wall = two_stream["external_wall_seconds"]
    nodes = two_stream["combined_nodes"]
    rate = two_stream["nodes_per_second"]
    if (
        nodes != 6_127_055_662
        or not isinstance(wall, (int, float))
        or wall <= 0
        or not math.isclose(rate, nodes / wall, rel_tol=1e-12)
        or not (
            0 < two_stream["sample_min_eta_hours"]
            <= two_stream["whole_run_eta_hours"]
            <= two_stream["sample_max_eta_hours"]
        )
        or two_stream["speedup_vs_active_8_worker_cpu_eta"] <= 0
    ):
        raise AssertionError("retained throughput arithmetic mismatch")
    return receipt


def _launch_pair(commands: list[list[str]], *, timeout: int = 180) -> list[dict]:
    processes = [
        subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for command in commands
    ]
    outputs: list[dict] = []
    try:
        for process in processes:
            stdout, stderr = process.communicate(timeout=timeout)
            if process.returncode != 0:
                raise AssertionError(
                    f"concurrent command failed ({process.returncode}): {stderr}"
                )
            outputs.append(json.loads(stdout))
    except BaseException:
        for process in processes:
            if process.poll() is None:
                process.kill()
        raise
    return outputs


def validate_guards(base: Path) -> None:
    descendant = ROOT / "psl4-metal-run-20260815T120200Z-forbidden"
    rejected = run(
        [
            sys.executable,
            str(ROOT / "gpu_dispatch.py"),
            "--run-dir",
            str(descendant),
            "--virtual-shards",
            "8192",
            "--shard",
            "0",
            "--dry-run",
        ],
        check=False,
    )
    if rejected.returncode == 0:
        raise AssertionError("packet-descendant path guard regressed")
    real_parent = base / "real-parent"
    real_parent.mkdir()
    symlink_parent = base / "linked-parent"
    symlink_parent.symlink_to(real_parent, target_is_directory=True)
    rejected = run(
        [
            sys.executable,
            str(ROOT / "gpu_dispatch.py"),
            "--run-dir",
            str(symlink_parent / "psl4-metal-run-20260815T120201Z-symlink"),
            "--virtual-shards",
            "8192",
            "--shard",
            "0",
            "--dry-run",
        ],
        check=False,
    )
    if rejected.returncode == 0:
        raise AssertionError("symlink-ancestor path guard regressed")
    unsafe_parent = base / "world-writable-parent"
    unsafe_parent.mkdir()
    os.chmod(unsafe_parent, 0o777)
    rejected = run(
        [
            sys.executable,
            str(ROOT / "gpu_dispatch.py"),
            "--run-dir",
            str(unsafe_parent / "psl4-metal-run-20260815T120208Z-unsafe"),
            "--virtual-shards",
            "8192",
            "--shard",
            "0",
            "--dry-run",
        ],
        check=False,
    )
    if rejected.returncode == 0:
        raise AssertionError("writable-ancestor path guard regressed")
    rejected = run(
        [
            sys.executable,
            str(ROOT / "gpu_dispatch.py"),
            "--run-dir",
            "/psl4-metal-run-20260815T120209Z-broad",
            "--virtual-shards",
            "8192",
            "--shard",
            "0",
            "--dry-run",
        ],
        check=False,
    )
    if rejected.returncode == 0:
        raise AssertionError("broad-root path guard regressed")


def validate_init_race_and_dispatch() -> tuple[Path, dict]:
    sys.path.insert(0, str(ROOT))
    import gpu_dispatch

    virtual_shards = 100_000_000
    task_indices = (17159, 22135)
    shards = [gpu_dispatch.splitmix64(index) % virtual_shards for index in task_indices]
    for task_index, shard in zip(task_indices, shards):
        if gpu_dispatch.expected_indices(virtual_shards, shard) != [task_index]:
            raise AssertionError("single-task dispatcher fixture drifted")
    holder = Path(
        tempfile.mkdtemp(prefix="psl4-metal-packet-test-", dir="/private/tmp")
    )
    run_dir = holder / "psl4-metal-run-20260815T120202Z-regression"
    # Simulate an interrupted pre-config initialization, then race two idempotent
    # explicit initializers against the same fresh root.
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True)
    archived = artifacts / "psl4_metal_bfs.mm"
    archived.write_bytes((ROOT / "psl4_metal_bfs.mm").read_bytes())
    os.chmod(archived, 0o444)
    # Crash remnants from both atomic JSON creation and compilation must be
    # recognized narrowly and cleaned under the setup lock before resuming.
    (run_dir / ".config.json.999999.tmp").write_bytes(b"partial")
    (artifacts / ".psl4_metal_bfs.999999.tmp").write_bytes(b"partial")
    (run_dir / ".setup.lock").touch(mode=0o600)
    init_command = [
        sys.executable,
        str(ROOT / "gpu_dispatch.py"),
        "--run-dir",
        str(run_dir),
        "--virtual-shards",
        str(virtual_shards),
        "--init-only",
    ]
    initializations = _launch_pair([init_command, init_command])
    if initializations[0] != initializations[1]:
        raise AssertionError("concurrent initialization was not idempotent")
    commands = [
        [
            sys.executable,
            str(ROOT / "gpu_dispatch.py"),
            "--run-dir",
            str(run_dir),
            "--virtual-shards",
            str(virtual_shards),
            "--shard",
            str(shard),
        ]
        for shard in shards
    ]
    first = _launch_pair(commands)
    resumed = _launch_pair(commands)
    if first != resumed or any(item.get("complete_task_count") != 1 for item in first):
        raise AssertionError("two-stream write-once dispatcher resume mismatch")
    audit = json.loads(
        run(
            [
                sys.executable,
                str(ROOT / "audit_run.py"),
                "--run-dir",
                str(run_dir),
                "--allow-incomplete",
            ],
            timeout=120,
        ).stdout
    )
    if (
        audit.get("task_receipt_count") != 2
        or audit.get("complete_shards") != 2
        or audit.get("duplicate_task_count") != 0
        or audit.get("misplaced_task_count") != 0
        or audit.get("initialization_self_test") != "verified"
    ):
        raise AssertionError("isolated-run audit mismatch")
    return run_dir, audit


def expect_audit_rejection(run_dir: Path, label: str) -> None:
    completed = run(
        [
            sys.executable,
            str(ROOT / "audit_run.py"),
            "--run-dir",
            str(run_dir),
            "--allow-incomplete",
        ],
        timeout=120,
        check=False,
    )
    if completed.returncode == 0:
        raise AssertionError(f"adversarial mutation accepted: {label}")


def validate_adversarial_audit(source_run: Path) -> int:
    parent = source_run.parent
    shard_dirs = sorted((source_run / "shards").iterdir())
    if len(shard_dirs) != 2:
        raise AssertionError("mutation fixture shard count drifted")
    rejected = 0

    # Reproduce the external audit attack: replace the journal and update its
    # direct hash while falsifying every summary field. Reconstruction must fail.
    mutated = parent / "psl4-metal-run-20260815T120203Z-journal"
    shutil.copytree(source_run, mutated)
    shard = mutated / "shards" / shard_dirs[0].name
    journal = shard / "journal.tsv"
    os.chmod(journal, 0o644)
    journal.write_text("NOT A JOURNAL\n", encoding="utf-8")
    os.chmod(journal, 0o444)
    receipt_path = shard / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["journal_sha256"] = sha256(journal)
    receipt["totals"] = {key: 0 for key in receipt["totals"]}
    receipt["task_indices_sha256"] = "f" * 64
    receipt["answer_count"] = 999
    receipt["answers_sha256"] = "e" * 64
    rewrite_json(receipt_path, receipt)
    expect_audit_rejection(mutated, "journal/totals/index/answer summaries")
    rejected += 1

    mutated = parent / "psl4-metal-run-20260815T120204Z-filename"
    shutil.copytree(source_run, mutated)
    task = next((mutated / "shards" / shard_dirs[0].name / "tasks").iterdir())
    task.rename(task.with_name("999999.json"))
    expect_audit_rejection(mutated, "task filename/index")
    rejected += 1

    mutated = parent / "psl4-metal-run-20260815T120205Z-selftest"
    shutil.copytree(source_run, mutated)
    init_path = mutated / "initialization.json"
    init = json.loads(init_path.read_text(encoding="utf-8"))
    init["self_test_marker"] = "unverified"
    rewrite_json(init_path, init)
    expect_audit_rejection(mutated, "self-test evidence")
    rejected += 1

    mutated = parent / "psl4-metal-run-20260815T120206Z-config"
    shutil.copytree(source_run, mutated)
    config_path = mutated / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["strong_exact_stride"] = 2
    rewrite_json(config_path, config)
    expect_audit_rejection(mutated, "frozen config pin")
    rejected += 1

    mutated = parent / "psl4-metal-run-20260815T120207Z-taskhash"
    shutil.copytree(source_run, mutated)
    shard = mutated / "shards" / shard_dirs[0].name
    receipt_path = shard / "receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["task_receipts_sha256"] = "a" * 64
    rewrite_json(receipt_path, receipt)
    expect_audit_rejection(mutated, "ordered task-receipt hash")
    rejected += 1

    mutated = parent / "psl4-metal-run-20260815T120210Z-writable"
    shutil.copytree(source_run, mutated)
    task = next((mutated / "shards" / shard_dirs[0].name / "tasks").iterdir())
    os.chmod(task, 0o644)
    expect_audit_rejection(mutated, "writable durable receipt")
    rejected += 1
    return rejected


def validate_copied_allowlist(manifest: dict) -> None:
    if os.environ.get("PSL4_PACKET_COPIED_TEST") == "1":
        return
    with tempfile.TemporaryDirectory(prefix="psl4-metal-allowlist-copy-") as directory:
        copy_root = Path(directory) / "packet"
        copy_root.mkdir()
        shutil.copy2(MANIFEST, copy_root / MANIFEST.name)
        for entry in manifest["files"]:
            source = ROOT / entry["path"]
            target = copy_root / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        environment = dict(os.environ)
        environment["PSL4_PACKET_COPIED_TEST"] = "1"
        completed = run(
            [sys.executable, str(copy_root / "test_packet.py")],
            timeout=300,
            cwd=copy_root,
            env=environment,
        )
        if json.loads(completed.stdout).get("status") != "pass":
            raise AssertionError("copied allowlist regression failed")


def main() -> int:
    manifest = validate_manifest()
    validate_freeze_is_read_only()
    quick = validate_quick_engine()
    discovery = validate_discovery()
    retained = validate_retained_dispatcher_receipt()
    with tempfile.TemporaryDirectory(prefix="psl4-metal-guard-test-") as directory:
        validate_guards(Path(directory))
    run_dir, dispatch = validate_init_race_and_dispatch()
    try:
        adversarial = validate_adversarial_audit(run_dir)
    finally:
        shutil.rmtree(run_dir.parent)
    validate_copied_allowlist(manifest)
    result = {
        "status": "pass",
        "manifest_files": len(manifest["files"]),
        "source_sha256": quick["source_sha256"],
        "random_parent_depth_cases": quick["self_test"]["random_parent_depth_cases"],
        "discovered_class_count": discovery["discovered_class_count"],
        "discovered_classes_exact_peak_sidelobe": discovery[
            "all_exact_peak_sidelobes"
        ],
        "discovered_classes_clear_gate": discovery["any_clears_first_place_gate"],
        "discovered_classes_pairwise_distinct": discovery[
            "pairwise_symmetry_distinct"
        ],
        "dispatcher_task_receipts": dispatch["task_receipt_count"],
        "retained_dispatcher_task_receipts": retained["task_receipts"],
        "retained_artifact_set_sha256": retained["validation_provenance"][
            "artifact_set_sha256"
        ],
        "dispatcher_resume": "exact",
        "concurrent_initialization": "atomic-idempotent",
        "adversarial_mutations_rejected": adversarial,
        "copied_allowlist": "pass",
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
