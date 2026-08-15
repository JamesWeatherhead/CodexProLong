#!/usr/bin/env python3
"""Copy only the manifest allowlist and test both supported repository layouts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
LAYOUTS = (
    Path("campaign/analytic/c3_fourier_dual_newton"),
    Path("src/campaign/analytic/c3_fourier_dual_newton"),
)


def run_checked(argv: list[str], cwd: Path, environment: dict[str, str]) -> dict:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    output = completed.stdout.strip()
    return json.loads(output) if output.startswith("{") else {"output": output}


def main() -> int:
    manifest = json.loads((HERE / "PUBLICATION_MANIFEST.json").read_text(encoding="utf-8"))
    relative_files = [Path(row["path"]) for row in manifest["files"]]
    relative_files.append(Path("PUBLICATION_MANIFEST.json"))
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    reports: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="c3-publication-allowlist-") as temporary_name:
        temporary = Path(temporary_name)
        for layout in LAYOUTS:
            packet = temporary / layout
            for relative in relative_files:
                destination = packet / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(HERE / relative, destination)
            replay = run_checked(
                [sys.executable, "-B", str(packet / "replay.py")], temporary, environment
            )
            selftest = run_checked(
                [sys.executable, "-B", str(packet / "publication_selftest.py")],
                temporary,
                environment,
            )
            reports[str(layout)] = {
                "replay_status": replay["status"],
                "selftest_status": selftest["status"],
                "copied_regular_files": len(relative_files),
            }
    print(json.dumps({"status": "ok", "layouts": reports}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
