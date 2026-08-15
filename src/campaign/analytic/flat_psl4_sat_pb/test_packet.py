#!/usr/bin/env python3
"""Standalone regression for the frozen PSL-4 SAT/PB feasibility packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cube_benchmark as cube
import sat_pb_benchmark as sat


HERE = Path(__file__).resolve().parent
SUITE = HERE / "runs" / "20260815T085500Z" / "benchmark.json"
CUBES = HERE / "runs" / "20260815T084700Z" / "cube_benchmark.json"
SUITE_SHA256 = "db6bbfd8cd81422aed55775a9f5b309b0d31db8fd22e585332611e19ae0d0a09"
CUBES_SHA256 = "141d6284bddfb579b64a2688b43ade448482142d223b20de7ce0c14bfadcec48"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_receipts() -> None:
    if sha256(SUITE) != SUITE_SHA256 or sha256(CUBES) != CUBES_SHA256:
        raise RuntimeError("frozen benchmark receipt hash changed")
    suite = json.loads(SUITE.read_text())
    for row in suite["results"]:
        stage = row["stage"]
        if stage in ("forced", "first_hint"):
            if row["status"] not in ("sat", "optimal"):
                raise RuntimeError(f"validated stage failed: {row}")
            sat.exact_verify(row["models"][0]["bits"])
        elif stage == "known_chain":
            if row["status"] != "sat" or len(row["models"]) != 3:
                raise RuntimeError(f"known chain failed: {row}")
            canonical = {model["canonical"] for model in row["models"]}
            if canonical != set(sat.KNOWN):
                raise RuntimeError("known chain canonical classes changed")
            for model in row["models"]:
                sat.exact_verify(model["bits"])
        elif row["status"] not in ("timeout", "unknown"):
            raise RuntimeError("cold/post-known stage unexpectedly resolved")

    cubes = json.loads(CUBES.read_text())
    cpp_rows = cubes["cpp_exact_outside_in"]["rows"]
    expected = [row["solutions"] > 0 for row in cpp_rows]
    if sum(expected) != 3:
        raise RuntimeError("fixture cube count changed")
    for backend in cubes["sat_backends"]:
        if backend["resolved"] != 256 or backend["unknown"] != 0:
            raise RuntimeError("cube benchmark is no longer fully resolved")
        for row in backend["rows"]:
            if (row["status"] == "sat") != expected[row["index"]]:
                raise RuntimeError("SAT/C++ cube status mismatch")
            if row["status"] == "sat":
                sat.exact_verify(row["model"]["bits"])


def live_regression() -> None:
    native = sat.run_pysat("minicard_native", "known_chain", True)
    if [model["canonical"] for model in native["models"]] != list(sat.KNOWN):
        raise RuntimeError("live native MiniCard chain changed")
    cp = sat.run_cp("known_chain", True, 5.0)
    if [model["canonical"] for model in cp["models"]] != list(sat.KNOWN):
        raise RuntimeError("live CP-SAT chain changed")

    cubes = cube.generate_cubes(16, 28, 0x12124930)
    cpp = cube.run_cpp(cubes)
    native_cubes = cube.run_sat_backend("minicard_native", cubes, 5000)
    expected = [row["solutions"] > 0 for row in cpp["rows"]]
    if native_cubes["resolved"] != len(cubes):
        raise RuntimeError("live cube regression left unknown rows")
    for row in native_cubes["rows"]:
        if (row["status"] == "sat") != expected[row["index"]]:
            raise RuntimeError("live cube regression disagrees")


def main() -> None:
    audit_receipts()
    live_regression()
    print("packet test OK: exact fixtures, class blocks, cold frontier, cubes")


if __name__ == "__main__":
    main()
