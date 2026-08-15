#!/usr/bin/env python3
"""Copy exactly the public allowlist and test canonical plus src layouts."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LAYOUTS = (
    "campaign/discrete/difference_carry_potentials",
    "src/campaign/discrete/difference_carry_potentials",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest_path = ROOT / "PUBLICATION_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    results = []
    (ROOT / "runs").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".copied_allowlist_", dir=ROOT / "runs") as temporary:
        temporary_root = Path(temporary)
        for index, layout in enumerate(LAYOUTS):
            destination = temporary_root / f"layout_{index}" / layout
            destination.mkdir(parents=True)
            shutil.copy2(manifest_path, destination / manifest_path.name)
            relative_paths = [record["path"] for record in manifest["files"]]
            for relative in relative_paths:
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            expected_files = {manifest_path.name, *relative_paths}
            observed_files = {
                str(path.relative_to(destination))
                for path in destination.rglob("*")
                if path.is_file()
            }
            if observed_files != expected_files:
                raise AssertionError("copied tree differs from exact publication allowlist")
            environment = dict(os.environ)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            packet_test = subprocess.run(
                [sys.executable, str(destination / "test_packet.py")],
                cwd=destination,
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            cleanroom_test = subprocess.run(
                [
                    sys.executable,
                    str(destination / "cleanroom_replay.py"),
                    "--seconds",
                    "30",
                ],
                cwd=destination,
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            )
            observed_after = {
                str(path.relative_to(destination))
                for path in destination.rglob("*")
                if path.is_file()
            }
            if observed_after != expected_files:
                raise AssertionError("copied replay created an undeclared file")
            cleanroom_receipt = json.loads(cleanroom_test.stdout)
            results.append(
                {
                    "layout": layout,
                    "packet_test": packet_test.stdout.strip(),
                    "cleanroom_status": cleanroom_receipt["status"],
                    "model_sha256": cleanroom_receipt["model_sha256"],
                    "passed": True,
                }
            )
    receipt = {"schema": 1, "copied_exact_allowlist": True, "results": results}
    if args.output:
        resolved = args.output.resolve()
        if ROOT not in resolved.parents:
            raise ValueError("output must stay in the isolated subtree")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
