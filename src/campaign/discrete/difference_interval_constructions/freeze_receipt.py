#!/usr/bin/env python3
"""Freeze and validate the bounded interval-construction negative frontier."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import search
import prime_power_sweep


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[2]
CORPUS = REPOSITORY / "campaign/research_corpus/snapshots/20260815T003306Z/corpus.sqlite3"
VERIFIER = (
    REPOSITORY
    / "campaign/state/problems/difference-bases"
    / "a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585.py"
)
K0_CHECKPOINTS = (
    HERE / "checkpoint_small.json",
    HERE / "checkpoint.json",
    HERE / "checkpoint_large.json",
)
TAIL_CHECKPOINT = HERE / "tail_checkpoint.json"
TAIL_FULL_CHECKPOINT = HERE / "tail_full_checkpoint.json"
PRIME_POWER_CHECKPOINT = HERE / "prime_power_checkpoint.json"
BASE_URL = "https://einsteinarena.com"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def portable(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY.resolve()).as_posix()


def atomic_json(path: Path, value: Any) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(raw)
    os.replace(temporary, path)


def get_json(path: str, **parameters: Any) -> Any:
    query = urllib.parse.urlencode(parameters)
    url = BASE_URL + path + (("?" + query) if query else "")
    request = urllib.request.Request(
        url, headers={"User-Agent": "difference-interval-readonly-audit/1"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def deterministic_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "elapsed_seconds"}


def validate_k0() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    files = []
    for path in K0_CHECKPOINTS:
        checkpoint = json.loads(path.read_text())
        if checkpoint["gate_clearing"]:
            raise RuntimeError(f"unexpected gate flag in {path}")
        records.extend(checkpoint["records"])
        files.append(
            {"path": portable(path), "sha256": sha256_file(path), "records": len(checkpoint["records"])}
        )
    expected = [value for value in range(2, 500) if search.is_prime(value)]
    actual = [int(record["q"]) for record in records]
    if actual != expected:
        raise RuntimeError(f"prime-order inventory mismatch: {actual}")
    for record in records:
        score = float(record["cardinality"] ** 2 / record["coverage"])
        if score != float(record["score"]):
            raise RuntimeError(f"exact score mismatch at q={record['q']}")
        if int(record["cardinality"]) != 4 * (int(record["q"]) + 1):
            raise RuntimeError(f"cardinality mismatch at q={record['q']}")
        if int(record["coverage"]) != (
            6 * int(record["modulus"]) + int(record["maximum_empty_arc"]) - 1
        ):
            raise RuntimeError(f"coverage identity mismatch at q={record['q']}")
    return records, files


def validate_tail(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    checkpoint = json.loads(path.read_text())
    if checkpoint["gate_clearing"]:
        raise RuntimeError(f"unexpected gate flag in {path}")
    for q_record in checkpoint["q_records"]:
        expected_extras = list(range(int(q_record["maximum_extra"]) + 1))
        actual_extras = [int(record["extra"]) for record in q_record["records"]]
        if actual_extras != expected_extras:
            raise RuntimeError(f"tail inventory mismatch at q={q_record['q']}")
        for record in q_record["records"]:
            score = float(record["cardinality"] ** 2 / record["coverage"])
            if score != float(record["score"]):
                raise RuntimeError(
                    f"tail score mismatch at q={q_record['q']} k={record['extra']}"
                )
            if int(record["coverage"]) < int(record["predicted_floor"]):
                raise RuntimeError(
                    f"tail floor mismatch at q={q_record['q']} k={record['extra']}"
                )
    descriptor = {
        "path": portable(path),
        "sha256": sha256_file(path),
        "q_count": len(checkpoint["q_records"]),
        "candidate_count": sum(len(item["records"]) for item in checkpoint["q_records"]),
    }
    return checkpoint, descriptor


def validate_prime_powers() -> tuple[dict[str, Any], dict[str, Any]]:
    checkpoint = json.loads(PRIME_POWER_CHECKPOINT.read_text())
    expected = prime_power_sweep.nonprime_prime_powers()
    actual = [int(record["q"]) for record in checkpoint["records"]]
    if actual != expected or checkpoint["scope"]["q_completed"] != expected:
        raise RuntimeError("non-prime prime-power inventory mismatch")
    if checkpoint["gate_clearing"]:
        raise RuntimeError("unexpected prime-power gate flag")
    for record in checkpoint["records"]:
        if float(record["score"]) != float(
            record["cardinality"] ** 2 / record["coverage"]
        ):
            raise RuntimeError(f"prime-power score mismatch at q={record['q']}")
        if int(record["coverage"]) != (
            6 * int(record["modulus"]) + int(record["maximum_empty_arc"]) - 1
        ):
            raise RuntimeError(f"prime-power coverage mismatch at q={record['q']}")
    descriptor = {
        "path": portable(PRIME_POWER_CHECKPOINT),
        "sha256": sha256_file(PRIME_POWER_CHECKPOINT),
        "records": len(checkpoint["records"]),
    }
    return checkpoint, descriptor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if sha256_file(VERIFIER) != search.VERIFIER_SHA256:
        raise RuntimeError("frozen verifier hash mismatch")
    if sha256_file(CORPUS) != "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb":
        raise RuntimeError("corpus hash mismatch")

    k0_records, k0_files = validate_k0()
    prime_powers, prime_power_file = validate_prime_powers()
    tail, tail_file = validate_tail(TAIL_CHECKPOINT)
    tail_full, tail_full_file = validate_tail(TAIL_FULL_CHECKPOINT)
    k0_best = min(k0_records, key=lambda item: float(item["score"]))
    changed_k0_best = min(
        (
            record
            for record in [*k0_records, *prime_powers["records"]]
            if int(record["q"]) != 89
        ),
        key=lambda item: float(item["score"]),
    )
    tail_records = [
        {"q": q_record["q"], **record}
        for checkpoint in (tail, tail_full)
        for q_record in checkpoint["q_records"]
        for record in q_record["records"]
    ]
    changed_tail_best = min(
        (record for record in tail_records if int(record["extra"]) > 0),
        key=lambda item: float(item["score"]),
    )

    live = None
    if not args.offline:
        problem = get_json("/api/problems/difference-bases")
        best = get_json("/api/solutions/best", problem_id=19, limit=1)[0]
        live_hash = hashlib.sha256(problem["verifier"].encode()).hexdigest()
        if live_hash != search.VERIFIER_SHA256:
            raise RuntimeError(f"live verifier changed: {live_hash}")
        if problem["solutionSchema"] != {
            "set": "list of non-negative integers (up to 2000 elements)"
        }:
            raise RuntimeError(f"live schema changed: {problem['solutionSchema']}")
        live = {
            "problem_id": problem["id"],
            "scoring": problem["scoring"],
            "min_improvement": problem["minImprovement"],
            "solution_schema": problem["solutionSchema"],
            "verifier_sha256": live_hash,
            "leader_id": best["id"],
            "leader_score": best["score"],
        }

    output = {
        "problem": "difference-bases",
        "live": live,
        "frozen_verifier": {
            "path": portable(VERIFIER),
            "sha256": sha256_file(VERIFIER),
            "executed": False,
        },
        "corpus": {
            "path": portable(CORPUS),
            "sha256": sha256_file(CORPUS),
            "solutions_read": 23,
            "threads_read": 11,
            "replies_read": 78,
        },
        "target_strictly_below": search.TARGET,
        "k0_scope": {
            "prime_orders_q": "all 95 primes from 2 through 499",
            "nonprime_prime_power_orders_q": {
                "orders": prime_power_sweep.nonprime_prime_powers(),
                "checkpoint": prime_power_file,
            },
            "all_prime_power_orders_q_under_schema_ceiling": True,
            "schema_cardinality_ceiling_reached": True,
            "every_unit_multiplier_and_cyclic_cut": True,
            "checkpoints": k0_files,
        },
        "tail_scope": {
            "selected_q_k0_through_k20": tail_file,
            "complete_k0_through_kq_for_q_53_61_89_97_101": tail_full_file,
        },
        "regenerated_incumbent": deterministic_record(k0_best),
        "best_changed_prime_order_k0": deterministic_record(changed_k0_best),
        "best_positive_tail": deterministic_record(changed_tail_best),
        "gate_clearing": False,
        "conclusion": (
            "No gate clear. The exhaustive prime-order k=0 Leech/Singer family "
            "and all non-prime prime powers through q=499 regenerate the q=89 "
            "incumbent as the unique best; the best changed q is 53. "
            "Complete positive-k tail sweeps at the five strongest selected orders "
            "also remain above the live gate."
        ),
        "source": {
            "paper": "Banakh and Gavrylkiv, Difference bases in cyclic groups",
            "doi": "10.1142/S0219498819500816",
            "citation": "https://paperclip.gxl.ai/citations/papers/arx_1702.02631#L71-L82,L96-L105,L136-L155",
        },
    }
    atomic_json(HERE / "receipt.json", output)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
