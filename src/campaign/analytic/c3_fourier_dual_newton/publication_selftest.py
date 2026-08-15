#!/usr/bin/env python3
"""Standard-library integrity and privacy test for the publishable packet."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "PUBLICATION_MANIFEST.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def ignored(relative: Path) -> bool:
    return (
        "__pycache__" in relative.parts
        or relative.suffix in {".pyc", ".pyo"}
        or relative.name == ".DS_Store"
        or relative.name.startswith("._")
        or any(part.startswith(".publication-selftest-") for part in relative.parts)
    )


def load_manifest() -> dict[str, Any]:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "manifest is not an object")
    return value


def main() -> int:
    manifest = load_manifest()
    require(manifest.get("schema") == "einstein-arena-publication-manifest-v1",
            "manifest schema drift")
    require(manifest.get("include_policy") == "deny-by-default exact regular-file allowlist",
            "manifest policy drift")
    require(manifest.get("external_writes") == [], "manifest records external writes")
    require(manifest["policy"]["candidate_payloads_included"] is False,
            "candidate payload policy drift")
    require(manifest["policy"]["verifier_source_included"] is False,
            "verifier source policy drift")
    require(manifest["policy"]["corpus_database_included"] is False,
            "corpus database policy drift")

    file_rows = manifest.get("files")
    require(isinstance(file_rows, list) and file_rows, "manifest file list missing")
    paths = [row.get("path") for row in file_rows]
    require(all(isinstance(path, str) for path in paths), "non-string manifest path")
    require(paths == sorted(paths) and len(paths) == len(set(paths)),
            "manifest paths are not unique and sorted")
    allowed = {Path(path) for path in paths}
    for row in file_rows:
        relative = Path(row["path"])
        require(not relative.is_absolute() and ".." not in relative.parts,
                f"unsafe manifest path: {relative}")
        path = HERE / relative
        require(path.is_file() and not path.is_symlink(), f"missing regular file: {relative}")
        require(path.stat().st_size == row["bytes"], f"size drift: {relative}")
        require(sha256_file(path) == row["sha256"], f"hash drift: {relative}")

    actual = {
        path.relative_to(HERE)
        for path in HERE.rglob("*")
        if path.is_file() and not ignored(path.relative_to(HERE))
    }
    expected = allowed | {Path("PUBLICATION_MANIFEST.json")}
    require(actual == expected,
            f"deny-by-default tree drift: missing={sorted(expected-actual)!r}, "
            f"extra={sorted(actual-expected)!r}")

    # Construct forbidden literals so this source does not self-trigger.
    host_markers = [
        "/" + "Users" + "/",
        "file" + "://",
        "C:" + "\\\\Users\\",
    ]
    credential_markers = [
        "sk" + "-proj-",
        "Bearer" + " ",
        "api" + "_key=",
        "password" + "=",
    ]
    scanned = 0
    for relative in sorted(expected):
        data = (HERE / relative).read_bytes()
        require(b"\x00" not in data, f"binary/NUL payload is not publication-safe: {relative}")
        text = data.decode("utf-8")
        for marker in host_markers + credential_markers:
            require(marker not in text, f"forbidden private marker in {relative}: {marker!r}")
        scanned += 1

    replay_source = (HERE / "replay.py").read_text(encoding="utf-8")
    for network_module in ("urllib", "requests", "socket", "http.client"):
        require(network_module not in replay_source, f"public replay imports network module: {network_module}")
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", str(HERE / "replay.py")],
        cwd=HERE,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    replay_report = json.loads(completed.stdout)
    require(replay_report.get("status") == "ok", "portable replay did not report ok")
    require(replay_report.get("private_input_replayed") is False,
            "portable replay unexpectedly read a private input")
    report = {
        "status": "ok",
        "manifest_files": len(file_rows),
        "scanned_text_files_including_manifest": scanned,
        "portable_replay": "ok",
        "external_writes": manifest["external_writes"],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
