#!/usr/bin/env python3
"""Recover public C2 construction assets and replay the frozen Arena verifier.

All network operations are GETs against commit-pinned raw GitHub URLs or the
public Einstein Arena best-solutions endpoint.  Downloaded blobs and extracted
NumPy arrays are written atomically below this directory.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sqlite3
import tempfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CACHE = ROOT / "cache"
PAYLOADS = ROOT / "payloads"
RECEIPT = ROOT / "receipt.json"

VERIFIER = (
    REPO
    / "campaign/state/problems/second-autocorrelation-inequality/"
    "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768.py"
)
VERIFIER_SHA256 = (
    "dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768"
)
LEADER_URL = "https://einsteinarena.com/api/solutions/best?problem_id=3&limit=1"
MIN_IMPROVEMENT = 1e-5

SIMPLETES_COMMIT = "a19a54b109db6185ab1f13dd59dd150074b24136"
HYRA_COMMIT = "26ebfbe7d491e6521d8bb5fc21fe88bb31460825"

ASSETS: dict[str, dict[str, Any]] = {
    "simpletes": {
        "url": (
            "https://raw.githubusercontent.com/wq-will/SimpleTES/"
            f"{SIMPLETES_COMMIT}/best_results/mathematics_discovery/"
            "second_autocorrelation_inequality/"
            "second_autocorrelation_inequality_best_construction.json"
        ),
        "sha256": "cd9d2fb1ba5280f46dbe8a836d1dc65c2b0c9e6a2c0cd9f857c47cee7d555ccd",
        "cache_name": "simpletes-construction.json",
        "array_key": "construction",
        "reported_score_key": "score",
        "repository": "wq-will/SimpleTES",
        "commit": SIMPLETES_COMMIT,
        "license": "GNU AGPL-3.0-or-later (repository LICENSE)",
        "license_url": (
            "https://raw.githubusercontent.com/wq-will/SimpleTES/"
            f"{SIMPLETES_COMMIT}/LICENSE"
        ),
        "license_sha256": (
            "3bdf828d3e3e55318bb9d12e10dbda27b4f7725d9da7ced98b526359ff80fb7d"
        ),
        "program_url": (
            "https://raw.githubusercontent.com/wq-will/SimpleTES/"
            f"{SIMPLETES_COMMIT}/best_results/mathematics_discovery/"
            "second_autocorrelation_inequality/"
            "second_autocorrelation_inequality_best.py"
        ),
        "program_sha256": (
            "2e9acbdf8c3cea1bb475bed6b0d11840bd78400f42af13201922b8cccb2bc521"
        ),
    },
    "hyra": {
        "url": (
            "https://raw.githubusercontent.com/Tencent-Hunyuan/Hyra-results/"
            f"{HYRA_COMMIT}/AI4Science/autocorrelation_second/solution.json"
        ),
        "sha256": "7e5fc9864969d100982fdd56b085c996e62b42e2cf2f632d9f22bb1cd8ce893a",
        "cache_name": "hyra-solution.json",
        "array_key": "values",
        "reported_score_key": None,
        "repository": "Tencent-Hunyuan/Hyra-results",
        "commit": HYRA_COMMIT,
        "license": "Apache-2.0 (repository LICENSE)",
        "license_url": (
            "https://raw.githubusercontent.com/Tencent-Hunyuan/Hyra-results/"
            f"{HYRA_COMMIT}/LICENSE"
        ),
        "license_sha256": (
            "ece6c7026732f576af3a909a117b321c9e8cfd96fc4d56e5229ff1a288dae087"
        ),
    },
}

PAPERCLIP_SOURCES = [
    {
        "claim": "Jaech--Joseph publish the spike-plus-comb profile and link higher-resolution coefficients.",
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2508.02803#L27-L34",
    },
    {
        "claim": "ImprovEvolve reports AlphaEvolve's irregular 50,000-step seed and a 0.96258 multiresolution continuation.",
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2602.10233#L87-L98",
    },
    {
        "claim": "ImprovEvolve publishes the evolved C2 code and the human-edited 1.6-million-step schedule.",
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2602.10233#L240-L245",
    },
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "c2-asset-audit/1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path: Path, value: object) -> None:
    encoded = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    atomic_bytes(path, encoded)


def atomic_npy(path: Path, values: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=path.stem + ".", suffix=".npy", dir=path.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with temporary.open("wb") as handle:
            np.save(handle, values, allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
        data = temporary.read_bytes()
        os.replace(temporary, path)
        return sha256(data)
    finally:
        temporary.unlink(missing_ok=True)


def load_verifier() -> ModuleType:
    actual = sha256(VERIFIER.read_bytes())
    if actual != VERIFIER_SHA256:
        raise RuntimeError(f"verifier hash drift: {actual}")
    spec = importlib.util.spec_from_file_location("frozen_c2_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_widths(mask: np.ndarray) -> list[int]:
    padded = np.pad(mask.astype(np.int8), (1, 1))
    edges = np.flatnonzero(np.diff(padded))
    return (edges[1::2] - edges[::2]).astype(int).tolist()


def stats(values: np.ndarray) -> dict[str, Any]:
    maximum = float(np.max(values))
    exact_mask = values > 0.0
    material_mask = values > maximum * 1e-8
    exact_runs = run_widths(exact_mask)
    material_runs = run_widths(material_mask)
    return {
        "n": int(values.size),
        "minimum": float(np.min(values)),
        "maximum": maximum,
        "sum": float(np.sum(values)),
        "nonzero": int(np.count_nonzero(exact_mask)),
        "material_threshold": maximum * 1e-8,
        "material_nonzero": int(np.count_nonzero(material_mask)),
        "exact_support_runs": len(exact_runs),
        "material_support_runs": len(material_runs),
        "material_run_width_median": (
            float(np.median(material_runs)) if material_runs else 0.0
        ),
        "material_run_width_maximum": max(material_runs, default=0),
        "values_sha256": sha256(np.ascontiguousarray(values).tobytes()),
    }


def current_leader() -> dict[str, Any]:
    rows = json.loads(fetch(LEADER_URL))
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("public leader endpoint did not return one row")
    row = rows[0]
    return {
        "id": int(row["id"]),
        "agent_name": row.get("agentName"),
        "score": float(row["score"]),
        "minimum_improvement": MIN_IMPROVEMENT,
        "strict_gate": float(row["score"]) + MIN_IMPROVEMENT,
        "endpoint": LEADER_URL,
    }


def compare_local_hyra(values: np.ndarray) -> dict[str, Any]:
    path = REPO / "campaign/analytic/c2_secondary/reference_Hyra_2361.npy"
    if not path.exists():
        return {"path": str(path), "present": False}
    prior = np.load(path, allow_pickle=False).astype(np.float64)
    return {
        "path": str(path),
        "present": True,
        "shape_equal": prior.shape == values.shape,
        "array_equal": bool(np.array_equal(prior, values)),
        "prior_values_sha256": sha256(np.ascontiguousarray(prior).tobytes()),
    }


def arena_corpus_matches(values_sha256: str) -> dict[str, Any]:
    """Prove whether the recovered vector already occurs in the frozen corpus."""
    latest_path = REPO / "campaign/research_corpus/latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    database_path = latest_path.parent / latest["database"]
    database_bytes_sha256 = sha256(database_path.read_bytes())
    if database_bytes_sha256 != latest["database_sha256"]:
        raise RuntimeError("research corpus database hash drift")
    matches: list[dict[str, Any]] = []
    rows_checked = 0
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT id, agent_name, score, record_json FROM solutions "
            "WHERE problem_id = 3 ORDER BY id"
        )
        for solution_id, agent_name, score, record_json in rows:
            record = json.loads(record_json)
            prior = np.asarray(record["data"]["values"], dtype=np.float64)
            prior_hash = sha256(np.ascontiguousarray(prior).tobytes())
            rows_checked += 1
            if prior_hash == values_sha256:
                matches.append(
                    {
                        "id": int(solution_id),
                        "agent_name": str(agent_name),
                        "score": float(score),
                    }
                )
    finally:
        connection.close()
    return {
        "snapshot": latest["snapshot"],
        "database_path": str(database_path.relative_to(REPO)),
        "database_sha256": database_bytes_sha256,
        "c2_rows_checked": rows_checked,
        "exact_matches": matches,
    }


def main() -> int:
    verifier = load_verifier()
    leader = current_leader()
    results: dict[str, Any] = {}
    for name, source in ASSETS.items():
        raw = fetch(str(source["url"]))
        actual = sha256(raw)
        if actual != source["sha256"]:
            raise RuntimeError(f"{name} source hash drift: {actual}")
        cache_path = CACHE / str(source["cache_name"])
        atomic_bytes(cache_path, raw)

        parsed = json.loads(raw)
        values = np.asarray(parsed[source["array_key"]], dtype=np.float64)
        if values.ndim != 1 or not (1 <= values.size <= 2_000_000):
            raise RuntimeError(f"{name}: invalid shape {values.shape}")
        if not np.isfinite(values).all() or np.any(values < -1e-6):
            raise RuntimeError(f"{name}: invalid values")

        score = float(verifier.evaluate({"values": values.tolist()}))
        payload_path = PAYLOADS / f"{name}.npy"
        payload_sha = atomic_npy(payload_path, values)
        result = {
            **stats(values),
            "score": score,
            "gap_to_live_leader": float(leader["score"]) - score,
            "gap_to_strict_gate": float(leader["strict_gate"]) - score,
            "gate_cleared": score >= float(leader["strict_gate"]),
            "reported_score": (
                float(parsed[source["reported_score_key"]])
                if source["reported_score_key"] is not None
                else None
            ),
            "raw_cache_path": str(cache_path.relative_to(REPO)),
            "payload_path": str(payload_path.relative_to(REPO)),
            "payload_file_sha256": payload_sha,
            "source": source,
        }
        result["frozen_arena_corpus"] = arena_corpus_matches(
            str(result["values_sha256"])
        )
        if name == "hyra":
            result["prior_local_reference"] = compare_local_hyra(values)
        results[name] = result

    receipt = {
        "schema": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "commit_pinned_GET_and_unchanged_local_verifier_replay",
        "external_writes": [],
        "leader": leader,
        "verifier": {
            "path": str(VERIFIER.relative_to(REPO)),
            "sha256": VERIFIER_SHA256,
        },
        "paperclip_sources": PAPERCLIP_SOURCES,
        "results": results,
        "conclusion": (
            "SimpleTES is a newly recovered independent 262,144-value public asset; "
            "Hyra's upstream asset is byte-for-value identical to the already frozen "
            "Arena reference. Neither clears the live submission gate."
        ),
    }
    atomic_json(RECEIPT, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
