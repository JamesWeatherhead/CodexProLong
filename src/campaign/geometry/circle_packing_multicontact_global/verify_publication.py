#!/usr/bin/env python3
"""Verify the exact allowlist from a clean copied temporary repository tree."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
MANIFEST = HERE / "PUBLICATION_MANIFEST.json"
FORBIDDEN_CALLS = {"exec", "eval", "compile", "__import__"}
FORBIDDEN_IMPORTS = {"importlib", "runpy"}
FORBIDDEN_HOST_MARKERS = (
    b"/" + b"Users" + b"/",
    b"/" + b"home" + b"/",
    b"C:\\" + b"Users" + b"\\",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"manifest path is not repository-relative: {value}")
    return path


def static_python_audit(path: Path) -> None:
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in FORBIDDEN_IMPORTS:
                    raise RuntimeError(f"dynamic import module in {path}: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".", 1)[0] in FORBIDDEN_IMPORTS:
                raise RuntimeError(f"dynamic import module in {path}: {node.module}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                raise RuntimeError(f"dynamic execution call in {path}: {node.func.id}")


def check_one(root: Path, item: dict[str, Any]) -> None:
    relative = safe_relative(item["path"])
    path = root / relative
    if not path.is_file():
        raise RuntimeError(f"missing allowlist file: {relative}")
    if path.stat().st_size != int(item["bytes"]):
        raise RuntimeError(f"byte-size mismatch: {relative}")
    if sha256_file(path) != item["sha256"]:
        raise RuntimeError(f"SHA-256 mismatch: {relative}")
    raw = path.read_bytes()
    if any(marker in raw for marker in FORBIDDEN_HOST_MARKERS):
        raise RuntimeError(f"host-absolute path marker in public file: {relative}")
    if path.suffix == ".py":
        static_python_audit(path)


def run_checked(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"copied-tree command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def verify() -> dict[str, Any]:
    manifest = json.loads(MANIFEST.read_text())
    if manifest["security"]["downloaded_verifier_dynamic_import_or_exec"] is not False:
        raise RuntimeError("manifest does not prohibit downloaded-verifier execution")
    allowlist = manifest["allowlist"]
    for item in allowlist:
        check_one(REPOSITORY, item)
    for command in manifest["public_commands"]:
        if Path(command.split()[-1]).is_absolute():
            raise RuntimeError(f"absolute public command: {command}")

    with tempfile.TemporaryDirectory(prefix="circle-codim3-public-") as temporary:
        copied_root = Path(temporary)
        for item in allowlist:
            relative = safe_relative(item["path"])
            destination = copied_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPOSITORY / relative, destination)
        manifest_relative = safe_relative(manifest["self"]["path"])
        manifest_destination = copied_root / manifest_relative
        manifest_destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MANIFEST, manifest_destination)
        for item in allowlist:
            check_one(copied_root, item)

        root_relative = safe_relative(manifest["root"])
        public_root = copied_root / root_relative
        tests = run_checked([sys.executable, str(public_root / "test_public_replay.py")], copied_root)
        replay = run_checked([sys.executable, str(public_root / "replay_public.py")], copied_root)
        replay_data = json.loads(replay.stdout)
        if replay_data["gate_clearing"] is not False:
            raise RuntimeError("copied replay unexpectedly clears gate")
        if replay_data["best_changed_score"] != 2.629728811166304:
            raise RuntimeError("copied replay score drift")

    return {
        "schema": "circle-packing-codim3-publication-verification-v1",
        "manifest_sha256": sha256_file(MANIFEST),
        "allowlist_file_count": len(allowlist),
        "allowlist_bytes": sum(int(item["bytes"]) for item in allowlist),
        "excluded_local_file_count": len(manifest["excluded_local_files"]),
        "copied_tree_test_status": "passed",
        "copied_tree_test_output_tail": tests.stderr.strip().splitlines()[-1],
        "copied_tree_replay_score": replay_data["best_changed_score"],
        "dynamic_import_exec_audit": "passed",
        "host_absolute_path_audit": "passed",
    }


def main() -> int:
    print(json.dumps(verify(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
