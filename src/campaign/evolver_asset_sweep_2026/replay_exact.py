#!/usr/bin/env python3
"""Reproduce the two finite Escher-Loop assets found by the 2026 sweep.

The reviewed programs are fetched from an immutable commit, checked byte-for-byte,
executed without ``__main__`` side effects, converted to Arena payloads in memory,
and evaluated by hash-pinned local verifier modules.  Downloaded source and payload
bytes are never written to disk.
"""

from __future__ import annotations

import hashlib
import json
import math
import urllib.request
from pathlib import Path
from typing import Any, Callable

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "campaign" / "state" / "problems"

ASSETS = {
    "circle-packing": {
        "url": (
            "https://raw.githubusercontent.com/scaling-group/escher-loop/"
            "acc8241e10058bf8ea1b1ea5299efc4eaf054e1f/"
            "examples/circle_packing/best_program.py"
        ),
        "source_sha256": "f644e5417b11f6ba9d1fc95c2d0232d5bc354eee6425633efa69f2330da114ea",
        "verifier_sha256": "2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab",
        "payload_sha256": "5b1ca3d58dab25ef5739999e9421b08ceb9a2cb27f8a6953580cdae5fc08f3b3",
        "score": 2.6352223117773934,
    },
    "heilbronn-triangles": {
        "url": (
            "https://raw.githubusercontent.com/scaling-group/escher-loop/"
            "acc8241e10058bf8ea1b1ea5299efc4eaf054e1f/"
            "examples/heilbronn_triangle/best_program.py"
        ),
        "source_sha256": "b69e2d2ab0e6209ad2d2d0be99d61c89c8ca9c941a07dd3ead81292a792c58ef",
        "verifier_sha256": "6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d",
        "payload_sha256": "1900353a698fe3a01b0bd923b576dff332846fcc9e6a968bb0ec39374fddb20a",
        "score": 0.03372654309850653,
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def fetch_checked(url: str, expected_sha256: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "arena-evolver-asset-replay/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.geturl() != url:
            raise RuntimeError(f"unexpected redirect: {response.geturl()}")
        data = response.read(500_001)
    if len(data) > 500_000:
        raise RuntimeError("source exceeds 500,000-byte replay limit")
    actual = sha256(data)
    if actual != expected_sha256:
        raise RuntimeError(f"source hash mismatch: {actual} != {expected_sha256}")
    return data


def load_checked_verifier(slug: str, expected_sha256: str) -> Callable[[dict[str, Any]], float]:
    path = STATE / slug / f"{expected_sha256}.py"
    source = path.read_bytes()
    actual = sha256(source)
    if actual != expected_sha256:
        raise RuntimeError(f"verifier hash mismatch: {actual} != {expected_sha256}")
    namespace: dict[str, Any] = {"__name__": "arena_verifier"}
    exec(compile(source, str(path), "exec"), namespace)
    evaluate = namespace.get("evaluate")
    if not callable(evaluate):
        raise RuntimeError(f"{path} does not define evaluate")
    return evaluate


def run_reviewed_program(slug: str, source: bytes) -> dict[str, Any]:
    namespace: dict[str, Any] = {"__name__": "reviewed_escher_asset"}
    exec(compile(source, ASSETS[slug]["url"], "exec"), namespace)
    if slug == "circle-packing":
        centers, radii, _ = namespace["construct_packing"]()
        circles = np.column_stack((centers, radii)).astype(np.float64)
        return {"circles": circles.tolist()}
    points = np.asarray(namespace["heilbronn_triangle11"](), dtype=np.float64)
    return {"points": points.tolist()}


def replay(slug: str) -> dict[str, Any]:
    spec = ASSETS[slug]
    source = fetch_checked(spec["url"], spec["source_sha256"])
    payload = run_reviewed_program(slug, source)
    payload_hash = sha256(canonical_json(payload))
    if payload_hash != spec["payload_sha256"]:
        raise RuntimeError(f"payload hash mismatch: {payload_hash} != {spec['payload_sha256']}")
    evaluate = load_checked_verifier(slug, spec["verifier_sha256"])
    score = float(evaluate(payload))
    if not math.isfinite(score) or score != spec["score"]:
        raise RuntimeError(f"score mismatch: {score!r} != {spec['score']!r}")
    return {
        "payload_sha256": payload_hash,
        "score": score,
        "source_sha256": spec["source_sha256"],
        "verifier_sha256": spec["verifier_sha256"],
    }


def main() -> None:
    result = {slug: replay(slug) for slug in ASSETS}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
