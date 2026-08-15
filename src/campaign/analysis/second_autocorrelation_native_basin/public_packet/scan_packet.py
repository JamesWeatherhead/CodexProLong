#!/usr/bin/env python3
"""Scan the exact C2 public packet for publication boundary violations.

Copyright (c) 2026 C2 Native Basin contributors. MIT License.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any


PACKET = Path(__file__).resolve().parent
ALLOWED_LICENSE_CLASSES = {
    "MIT-Original",
    "MIT-License-Text",
    "Factual-Metadata",
    "Dependency-Declaration",
}
FORBIDDEN_SUFFIXES = {
    ".npy",
    ".npz",
    ".pyc",
    ".pyo",
    ".so",
    ".dylib",
    ".dll",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".pt",
    ".pth",
    ".bin",
}
PRIVATE_PATTERNS = [
    re.compile(re.escape("/" + "Users/")),
    re.compile(re.escape("/" + "home/")),
    re.compile(r"[A-Za-z]:\\(?:Users|Documents and Settings)\\"),
]
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*[\"'][^\"']{12,}[\"']",
        re.IGNORECASE,
    ),
    re.compile(
        re.escape("-----BEGIN " + "PRIVATE KEY-----"), re.IGNORECASE
    ),
    re.compile(
        re.escape("-----BEGIN RSA " + "PRIVATE KEY-----"), re.IGNORECASE
    ),
    re.compile(
        re.escape("-----BEGIN OPENSSH " + "PRIVATE KEY-----"), re.IGNORECASE
    ),
]


def load_manifest() -> dict[str, Any]:
    return json.loads((PACKET / "manifest.json").read_text(encoding="utf-8"))


def scan_ast(relative: str, source: str) -> list[str]:
    findings: list[str] = []
    tree = ast.parse(source, filename=relative)
    strict_cleanroom = relative in {"c2_cleanroom.py", "replay_public.py"}
    denied_modules = {
        "requests",
        "httpx",
        "urllib",
        "socket",
        "ftplib",
        "importlib",
    }
    for node in ast.walk(tree):
        if strict_cleanroom and isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in denied_modules:
                    findings.append(f"{relative}: denied import {alias.name}")
        if strict_cleanroom and isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module in denied_modules:
                findings.append(f"{relative}: denied import {node.module}")
        if strict_cleanroom and isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {
                "exec",
                "eval",
                "compile",
                "__import__",
            }:
                findings.append(f"{relative}: denied dynamic call {node.func.id}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in {
                "exec_module",
                "load_module",
                "urlopen",
            }:
                findings.append(
                    f"{relative}: denied dynamic/network call {node.func.attr}"
                )
    return findings


def scan_packet() -> dict[str, Any]:
    manifest = load_manifest()
    entries = {entry["path"]: entry for entry in manifest["allowlist"]}
    actual = {
        path.relative_to(PACKET).as_posix()
        for path in PACKET.rglob("*")
        if path.is_file()
    }
    findings: list[str] = []
    if actual != set(entries):
        findings.append(
            "file-set mismatch: "
            f"missing={sorted(set(entries) - actual)}, "
            f"extra={sorted(actual - set(entries))}"
        )

    maximum_size = int(manifest["policy"]["maximum_public_file_bytes"])
    scanned_bytes = 0
    for relative in sorted(actual):
        path = PACKET / relative
        size = path.stat().st_size
        scanned_bytes += size
        if size > maximum_size:
            findings.append(f"{relative}: exceeds {maximum_size} bytes")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(f"{relative}: forbidden binary/archive suffix")
        if path.is_symlink():
            findings.append(f"{relative}: symlink is not allowed")
        payload = path.read_bytes()
        if b"\x00" in payload:
            findings.append(f"{relative}: contains NUL bytes")
            continue
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(f"{relative}: is not UTF-8 text")
            continue
        for pattern in PRIVATE_PATTERNS:
            if pattern.search(text):
                findings.append(f"{relative}: private absolute path pattern")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(f"{relative}: possible provider credential")
        if relative.endswith(".py"):
            findings.extend(scan_ast(relative, text))

        entry = entries.get(relative)
        if entry is None:
            continue
        if entry["license_class"] not in ALLOWED_LICENSE_CLASSES:
            findings.append(f"{relative}: unclear license class")

    notice = (PACKET / "NOTICE.md").read_text(encoding="utf-8")
    provenance = json.loads(
        (PACKET / "provenance.json").read_text(encoding="utf-8")
    )
    if "no repository code or coefficient" not in notice.lower():
        findings.append("NOTICE.md: missing explicit third-party-byte boundary")
    if any(source["bytes_incorporated"] for source in provenance["sources"]):
        findings.append("provenance.json: third-party bytes marked incorporated")
    if findings:
        raise RuntimeError("publication scan failed:\n" + "\n".join(findings))
    return {
        "status": "PASS",
        "files_scanned": len(actual),
        "bytes_scanned": scanned_bytes,
        "secret_findings": 0,
        "private_path_findings": 0,
        "forbidden_binary_findings": 0,
        "dynamic_verifier_or_network_findings": 0,
        "unclear_license_findings": 0,
        "third_party_bytes": 0,
    }


def main() -> int:
    print(json.dumps(scan_packet(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
