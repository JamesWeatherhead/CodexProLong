#!/usr/bin/env python3
"""Rebuild the PSL-4 accelerator without modifying the frozen base engine."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = REPO / "campaign" / "flat_psl4_global_exact" / "psl4_popcount.cpp"
PATCH = HERE / "accelerator.patch"

BASE_SHA256 = "a9c7dfd13aeb06302d192215a49888552925f76b3a96e33b2450d16661363b42"
PATCH_SHA256 = "2ad9e2387e92c5b8ef8217e5d616a4ff41bc6da960ce821c22d4c4563992b51b"
OUTPUT_SHA256 = "431ae5ed5c8800a0639cbd3cc7d298afc50d58b9b23e18a10634efd290f4c3ee"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_hash(path: Path, expected: str, label: str) -> None:
    observed = sha256(path)
    if observed != expected:
        raise RuntimeError(
            f"{label} SHA-256 changed: expected {expected}, observed {observed}"
        )


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", dir=destination.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "build" / "psl4_accelerated.cpp",
    )
    args = parser.parse_args()

    require_hash(BASE, BASE_SHA256, "frozen base source")
    require_hash(PATCH, PATCH_SHA256, "accelerator patch")
    with tempfile.TemporaryDirectory(prefix="psl4-accelerator-") as name:
        generated = Path(name) / "psl4_accelerated.cpp"
        shutil.copyfile(BASE, generated)
        completed = subprocess.run(
            ["patch", "--silent", str(generated), str(PATCH)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "patch failed:\n" + completed.stdout + completed.stderr
            )
        require_hash(generated, OUTPUT_SHA256, "generated accelerator source")
        atomic_copy(generated, args.output.resolve())

    print(f"output={args.output.resolve()}")
    print(f"sha256={OUTPUT_SHA256}")


if __name__ == "__main__":
    main()
