#!/usr/bin/env python3
"""Small fail-closed credential scanner for the public campaign mirror."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PATTERNS = {
    "paperclip_api_key": re.compile(rb"gxl_[A-Za-z0-9_-]{24,}"),
    "openai_api_key": re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
    "github_token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{24,}"),
    "aws_access_key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "google_api_key": re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}

SKIP_PARTS = {".git", ".venv", "__pycache__", ".ruff_cache"}
MAX_BYTES = 20 * 1024 * 1024


def scan(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.stat().st_size > MAX_BYTES:
            findings.append(f"oversized-unscanned:{path.relative_to(root)}")
            continue
        data = path.read_bytes()
        for label, pattern in PATTERNS.items():
            if pattern.search(data):
                findings.append(f"{label}:{path.relative_to(root)}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    findings = scan(root)
    if findings:
        print("public mirror scan FAILED")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print(f"public mirror scan OK: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

