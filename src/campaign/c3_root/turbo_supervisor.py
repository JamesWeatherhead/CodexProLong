#!/usr/bin/env python3
"""Persistently run exact-accepted C3 continuation cycles."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
CAMPAIGN = ROOT.parent
POLISHER = CAMPAIGN / "c1_root" / "smooth_polish.py"
TARGET = 1.4515618638902069
LEADER = 1.4515718638902069
VERIFIER_SHA256 = "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9"


def exact_score(path: Path) -> float:
    values = np.load(path, allow_pickle=False).astype(np.float64)
    convolution = np.convolve(values, values, mode="full")
    return float(2.0 * len(values) * np.max(convolution) / np.sum(values) ** 2)


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_event(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--cycles", type=int, default=20)
    parser.add_argument("--betas", default="3e6,1e7,3e7,1e8,3e8,1e9,3e9")
    parser.add_argument("--maxiter", type=int, default=3500)
    parser.add_argument("--maxcor", type=int, default=200)
    parser.add_argument("--state-dir", type=Path, default=ROOT / "turbo")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--path-check-only",
        action="store_true",
        help="assert and print child path resolution without creating files",
    )
    args = parser.parse_args()
    if args.cycles < 1:
        raise RuntimeError("cycles must be positive")

    # The child runs with ``cwd=CAMPAIGN``.  Resolve the supervisor-owned
    # directory first so a caller-provided relative path cannot silently gain
    # a second ``campaign/`` prefix and evade the exact acceptance scan.
    args.state_dir = args.state_dir.resolve()
    if args.path_check_only:
        run_root = args.state_dir / "runs"
        child_view = (CAMPAIGN / run_root).resolve()
        assert run_root.is_absolute()
        assert child_view == run_root
        print(
            json.dumps(
                {
                    "child_cwd": str(CAMPAIGN),
                    "child_run_root": str(child_view),
                    "path_check_passed": True,
                    "state_dir": str(args.state_dir),
                },
                sort_keys=True,
            )
        )
        return 0
    state_path = args.state_dir / "state.json"
    events_path = args.state_dir / "events.jsonl"
    run_root = args.state_dir / "runs"
    run_root.mkdir(parents=True, exist_ok=True)
    if args.resume:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        current = Path(state["best_path"])
        starting_cycle = int(state["cycles_completed"])
    else:
        if args.input is None:
            raise RuntimeError("--input is required unless --resume is used")
        current = args.input.resolve()
        starting_cycle = 0
        if state_path.exists():
            raise RuntimeError(f"state exists at {state_path}; use --resume")

    best_score = exact_score(current)
    state = {
        "schema_version": 1,
        "best_path": str(current),
        "best_score": best_score,
        "best_sha256": hashlib.sha256(current.read_bytes()).hexdigest(),
        "leader_score": LEADER,
        "target_score": TARGET,
        "verifier_sha256": VERIFIER_SHA256,
        "gate_gap": best_score - TARGET,
        "cycles_completed": starting_cycle,
        "updated_at": datetime.now(UTC).isoformat(),
        "status": "running" if best_score > TARGET else "finished",
    }
    atomic_json(state_path, state)

    for cycle in range(starting_cycle + 1, starting_cycle + args.cycles + 1):
        if best_score <= TARGET:
            break
        before = {path.resolve() for path in run_root.iterdir() if path.is_dir()}
        log_path = args.state_dir / f"cycle-{cycle:03d}.log"
        command = [
            sys.executable,
            "-u",
            str(POLISHER),
            "--input",
            str(current),
            "--run-root",
            str(run_root),
            "--gate",
            "1e-5",
            "--signed",
            "--betas",
            args.betas,
            "--maxiter",
            str(args.maxiter),
            "--maxcor",
            str(args.maxcor),
        ]
        started = datetime.now(UTC)
        append_event(
            events_path,
            {
                "event": "cycle_started",
                "cycle": cycle,
                "input": str(current),
                "input_score": best_score,
                "started_at": started.isoformat(),
                "command": command,
            },
        )
        with log_path.open("wb") as log:
            result = subprocess.run(
                command,
                cwd=CAMPAIGN,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
            log.flush()
            os.fsync(log.fileno())
        if result.returncode != 0:
            state["status"] = "child_failed"
            state["updated_at"] = datetime.now(UTC).isoformat()
            state["last_returncode"] = result.returncode
            atomic_json(state_path, state)
            raise RuntimeError(f"cycle {cycle} failed; inspect {log_path}")

        created = sorted(
            (
                path.resolve()
                for path in run_root.iterdir()
                if path.is_dir() and path.resolve() not in before
            ),
            key=lambda path: path.stat().st_mtime_ns,
        )
        if len(created) != 1:
            raise RuntimeError(f"cycle {cycle} created {len(created)} run directories")
        candidate = created[0] / "best.npy"
        candidate_score = exact_score(candidate)
        improved = candidate_score < best_score
        if improved:
            current = candidate
            best_score = candidate_score
        finished = datetime.now(UTC)
        state = {
            "schema_version": 1,
            "best_path": str(current),
            "best_score": best_score,
            "best_sha256": hashlib.sha256(current.read_bytes()).hexdigest(),
            "leader_score": LEADER,
            "target_score": TARGET,
            "verifier_sha256": VERIFIER_SHA256,
            "gate_gap": best_score - TARGET,
            "cycles_completed": cycle,
            "updated_at": finished.isoformat(),
            "status": "finished" if best_score <= TARGET else "running",
        }
        atomic_json(state_path, state)
        append_event(
            events_path,
            {
                "event": "cycle_completed",
                "cycle": cycle,
                "candidate": str(candidate),
                "candidate_score": candidate_score,
                "improved": improved,
                "best_path": str(current),
                "best_score": best_score,
                "gate_gap": best_score - TARGET,
                "finished_at": finished.isoformat(),
                "duration_seconds": (finished - started).total_seconds(),
            },
        )

    state["status"] = "finished" if best_score <= TARGET else "cycle_budget_exhausted"
    state["updated_at"] = datetime.now(UTC).isoformat()
    atomic_json(state_path, state)
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if best_score <= TARGET else 2


if __name__ == "__main__":
    raise SystemExit(main())
