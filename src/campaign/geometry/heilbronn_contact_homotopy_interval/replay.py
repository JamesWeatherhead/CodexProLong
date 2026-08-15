#!/usr/bin/env python3
"""Independent clean-room replay for a Heilbronn contact-homotopy run."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

COUNT = 11
TRIPLES = tuple(itertools.combinations(range(COUNT), 3))
STRICT_GATE = 0.036529890880030155


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def normalized_score_barycentric(values: list[float]) -> tuple[float, float, float]:
    if len(values) != 23 or not all(math.isfinite(value) for value in values):
        raise ValueError("expected 23 finite active-system values")
    points = [values[2 * index : 2 * index + 2] for index in range(COUNT)]
    domain = []
    for b, c in points:
        domain.extend((b, c, 1.0 - b - c))
    score = math.inf
    distance = math.inf
    for i, j, k in TRIPLES:
        bi, ci = points[i]
        bj, cj = points[j]
        bk, ck = points[k]
        score = min(score, abs((bj - bi) * (ck - ci) - (cj - ci) * (bk - bi)))
    for i in range(COUNT):
        for j in range(i + 1, COUNT):
            distance = min(
                distance,
                math.hypot(points[i][0] - points[j][0], points[i][1] - points[j][1]),
            )
    return score, min(domain), distance


def normalized_score_cartesian(points: list[list[float]]) -> tuple[float, float, float]:
    if len(points) != COUNT or any(len(point) != 2 for point in points):
        raise ValueError("expected exactly 11 coordinate pairs")
    if not all(math.isfinite(value) for point in points for value in point):
        raise ValueError("non-finite coordinate")
    root3 = math.sqrt(3.0)
    slacks = []
    for x, y in points:
        slacks.extend((y, root3 * x - y, root3 - root3 * x - y))
    minimum_area = math.inf
    minimum_distance = math.inf
    for i, j, k in TRIPLES:
        xi, yi = points[i]
        xj, yj = points[j]
        xk, yk = points[k]
        twice_area = abs((xj - xi) * (yk - yi) - (yj - yi) * (xk - xi))
        minimum_area = min(minimum_area, 0.5 * twice_area)
    for i in range(COUNT):
        for j in range(i + 1, COUNT):
            minimum_distance = min(
                minimum_distance,
                math.hypot(points[i][0] - points[j][0], points[i][1] - points[j][1]),
            )
    return minimum_area / (root3 / 4.0), min(slacks), minimum_distance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    run = args.run.resolve()
    summary = json.loads((run / "summary.json").read_text())
    config = json.loads((run / "config.json").read_text())
    payload = json.loads((run / "best.json").read_text())
    if sha256_file(run / "config.json") != summary["config_sha256"]:
        raise RuntimeError("config hash mismatch")
    if sha256_file(run / "results.jsonl") != summary["results_sha256"]:
        raise RuntimeError("results hash mismatch")
    if config["task_count"] != summary["tasks_planned"]:
        raise RuntimeError("task count mismatch")
    records = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines()]
    if len(records) != summary["tasks_recorded"]:
        raise RuntimeError("record count mismatch")
    if [record["task_id"] for record in records] != list(range(len(records))):
        raise RuntimeError("task order is not complete and monotone")
    replayed_endpoints = 0
    maximum_endpoint_score_delta = 0.0
    maximum_endpoint_domain_delta = 0.0
    for record in records:
        if record["status"] != "complete":
            continue
        endpoint = record["endpoint"]
        if canonical_sha256(endpoint) != record["endpoint_sha256"]:
            raise RuntimeError(f"endpoint hash mismatch at task {record['task_id']}")
        endpoint_score, endpoint_domain, endpoint_distance = normalized_score_barycentric(endpoint)
        score_delta = abs(endpoint_score - float(record["score"]))
        domain_delta = abs(endpoint_domain - float(record["minimum_domain_slack"]))
        distance_delta = abs(endpoint_distance - float(record["minimum_pair_distance"]))
        if score_delta > 5e-15 or domain_delta > 5e-15 or distance_delta > 5e-15:
            raise RuntimeError(f"endpoint metric mismatch at task {record['task_id']}")
        maximum_endpoint_score_delta = max(maximum_endpoint_score_delta, score_delta)
        maximum_endpoint_domain_delta = max(maximum_endpoint_domain_delta, domain_delta)
        replayed_endpoints += 1
    replayed_polishes = 0
    maximum_polish_score_delta = 0.0
    polish_path = run / "polish.jsonl"
    if polish_path.exists():
        if sha256_file(polish_path) != summary["polish_sha256"]:
            raise RuntimeError("polish hash mismatch")
        for line in polish_path.read_text().splitlines():
            record = json.loads(line)
            if canonical_sha256(record["values"]) != record["values_sha256"]:
                raise RuntimeError("polish value hash mismatch")
            polish_score, polish_domain, polish_distance = normalized_score_barycentric(record["values"])
            score_delta = abs(polish_score - float(record["score"]))
            if (
                score_delta > 5e-15
                or abs(polish_domain - float(record["minimum_domain_slack"])) > 5e-15
                or abs(polish_distance - float(record["minimum_pair_distance"])) > 5e-15
            ):
                raise RuntimeError("polish metric mismatch")
            maximum_polish_score_delta = max(maximum_polish_score_delta, score_delta)
            replayed_polishes += 1
    score, minimum_domain_slack, minimum_distance = normalized_score_cartesian(payload["points"])
    if abs(score - summary["best_score_clean_formula"]) > 5e-15:
        raise RuntimeError("clean-room score mismatch")
    if minimum_domain_slack < -2e-10 or minimum_distance <= 1e-9:
        raise RuntimeError("best payload is outside intended domain")
    gate_clearing = score > STRICT_GATE
    if gate_clearing != summary["gate_clearing"]:
        raise RuntimeError("gate decision mismatch")
    if canonical_sha256(payload) != summary["best_payload_sha256"]:
        raise RuntimeError("best payload hash mismatch")
    if summary.get("events_sha256") and sha256_file(run / "events.jsonl") != summary["events_sha256"]:
        raise RuntimeError("events hash mismatch")
    result = {
        "status": "PASS",
        "run": str(run),
        "tasks": len(records),
        "complete_paths": sum(record["status"] == "complete" for record in records),
        "replayed_endpoints": replayed_endpoints,
        "replayed_polishes": replayed_polishes,
        "maximum_endpoint_score_delta": maximum_endpoint_score_delta,
        "maximum_endpoint_domain_delta": maximum_endpoint_domain_delta,
        "maximum_polish_score_delta": maximum_polish_score_delta,
        "score": score,
        "strict_gate": STRICT_GATE,
        "gate_margin": score - STRICT_GATE,
        "gate_clearing": gate_clearing,
        "minimum_domain_slack": minimum_domain_slack,
        "minimum_pair_distance": minimum_distance,
        "best_payload_sha256": summary["best_payload_sha256"],
        "results_sha256": summary["results_sha256"],
    }
    output = run / "independent_replay.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
