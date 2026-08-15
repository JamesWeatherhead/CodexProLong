#!/usr/bin/env python3
"""Validate the frozen H100 plan without starting optimization.

Copyright (c) 2026 C2 Native Basin contributors. MIT License.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from typing import Any


PACKET = Path(__file__).resolve().parent
EXPECTED = {"numpy": "2.5.2", "scipy": "1.18.0", "torch": "2.13.0"}


def load_config(name: str) -> dict[str, Any]:
    return json.loads((PACKET / "configs" / name).read_text(encoding="utf-8"))


def validate_configs() -> dict[str, Any]:
    phase_a = load_config("h100_phase_a.json")
    phase_b = load_config("h100_phase_b.json")
    histories = len(phase_a["seeds"])
    calculated_member_steps = (
        histories * phase_a["population"] * phase_a["steps_per_history"]
    )
    if calculated_member_steps != phase_a["total_member_steps"]:
        raise RuntimeError("Phase-A member-step arithmetic mismatch")
    calculated_audits = phase_a["steps_per_history"] // phase_a[
        "verify_every_steps"
    ] + 2
    if calculated_audits != phase_a["audit_passes_per_history"]:
        raise RuntimeError("Phase-A audit-pass arithmetic mismatch")
    if (
        histories * calculated_audits * phase_a["population"]
        != phase_a["total_exact_member_evaluations"]
    ):
        raise RuntimeError("Phase-A exact-evaluation arithmetic mismatch")
    if not phase_b["require_true_multi_active_lag_bundle"]:
        raise RuntimeError("Phase-B true multi-active requirement is disabled")
    if phase_b["single_lag_substitution_allowed"]:
        raise RuntimeError("Phase-B single-lag substitution is enabled")
    return {
        "native_n": phase_a["native_n"],
        "nfft": phase_a["nfft"],
        "histories": histories,
        "total_member_steps": calculated_member_steps,
        "total_exact_member_evaluations": phase_a[
            "total_exact_member_evaluations"
        ],
    }


def package_versions() -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in EXPECTED:
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def validate_hardware() -> dict[str, Any]:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available")
    if torch.cuda.device_count() != 1:
        raise RuntimeError("exactly one visible CUDA device is required")
    properties = torch.cuda.get_device_properties(0)
    name = str(properties.name)
    total_memory = int(properties.total_memory)
    if "H100" not in name.upper():
        raise RuntimeError(f"visible device is not an H100: {name}")
    if total_memory < 79_000_000_000:
        raise RuntimeError(f"H100 reports less than 79 GB: {total_memory}")
    return {
        "device_count": 1,
        "device_name": name,
        "total_memory_bytes": total_memory,
        "cuda_version": torch.version.cuda,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="validate plan arithmetic without importing PyTorch or checking CUDA",
    )
    args = parser.parse_args()
    versions = package_versions()
    result: dict[str, Any] = {
        "status": "PASS",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": versions,
        "expected_packages": EXPECTED,
        "configs": validate_configs(),
        "optimization_started": False,
    }
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("the frozen H100 plan requires CPython 3.12")
    if not args.config_only:
        for name, expected in EXPECTED.items():
            if versions[name] != expected:
                raise RuntimeError(
                    f"{name} version mismatch: expected {expected}, got {versions[name]}"
                )
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            raise RuntimeError("the frozen H100 plan requires Linux x86_64")
        result["hardware"] = validate_hardware()
    else:
        result["hardware"] = "not_checked_config_only"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
