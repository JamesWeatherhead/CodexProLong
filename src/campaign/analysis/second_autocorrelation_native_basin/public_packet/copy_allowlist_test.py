#!/usr/bin/env python3
"""Test exact allowlist copies in canonical and mirrored repository layouts.

Copyright (c) 2026 C2 Native Basin contributors. MIT License.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


PACKET = Path(__file__).resolve().parent
LANE = PACKET.parent
RELATIVE_LANE = Path("campaign/analysis/second_autocorrelation_native_basin")


def load_manifest() -> dict[str, Any]:
    return json.loads((PACKET / "manifest.json").read_text(encoding="utf-8"))


def safe_child_environment() -> dict[str, str]:
    result = {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    for name in (
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "LD_LIBRARY_PATH",
        "DYLD_LIBRARY_PATH",
    ):
        if name in os.environ:
            result[name] = os.environ[name]
    return result


def copy_allowlist(destination: Path, manifest: dict[str, Any]) -> None:
    for entry in manifest["allowlist"]:
        relative = Path(entry["path"])
        source = PACKET / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def run_check(packet: Path, program: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(packet / program)],
        cwd=packet.parents[4],
        env=safe_child_environment(),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{program} failed with exit {completed.returncode}:\n"
            + completed.stdout
            + completed.stderr
        )
    value = json.loads(completed.stdout)
    if value.get("status") != "PASS":
        raise RuntimeError(f"{program} did not report PASS")
    return value


def main() -> int:
    manifest = load_manifest()
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix=".public_copy_test-", dir=LANE) as raw:
        temporary = Path(raw)
        layouts = {
            "canonical": temporary / "canonical" / RELATIVE_LANE / "public_packet",
            "mirrored": temporary
            / "mirrored"
            / "src"
            / RELATIVE_LANE
            / "public_packet",
        }
        for name, packet in layouts.items():
            copy_allowlist(packet, manifest)
            checks = {}
            for program in ("replay_public.py", "test_packet.py", "scan_packet.py"):
                checks[program] = run_check(packet, program)["status"]
            results.append({"layout": name, "checks": checks, "status": "PASS"})
    print(
        json.dumps(
            {
                "status": "PASS",
                "layouts": results,
                "temporary_copy_removed": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
