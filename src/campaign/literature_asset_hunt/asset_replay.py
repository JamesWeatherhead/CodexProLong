#!/usr/bin/env python3
"""GET-only, non-executing replay of public geometry construction assets.

Downloaded Python/notebook text is *never* imported or executed.  The only
Python module loaded is the locally frozen EinsteinArena verifier whose SHA-256
is pinned in sources.json.
"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
ALLOWED_HOSTS = {
    "raw.githubusercontent.com",
    "www.hars.us",
    "erich-friedman.github.io",
    "www-wales.ch.cam.ac.uk",
}
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("._") or "asset"


def cache_path(url: str) -> Path:
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix or ".bin"
    return ROOT / "cache" / f"{sha256_bytes(url.encode())[:20]}{suffix}"


def validate_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"URL is outside GET-only allowlist: {url}")


def fetch(url: str, refresh: bool) -> tuple[bytes, dict[str, Any]]:
    validate_url(url)
    path = cache_path(url)
    if path.exists() and not refresh:
        raw = path.read_bytes()
        return raw, {
            "cache_path": str(path),
            "final_url": url,
            "from_cache": True,
            "size": len(raw),
            "sha256": sha256_bytes(raw),
        }

    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "EinsteinArena-clean-room-asset-replay/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        final_url = response.geturl()
        validate_url(final_url)
        raw = response.read(MAX_DOWNLOAD_BYTES + 1)
        if len(raw) > MAX_DOWNLOAD_BYTES:
            raise ValueError(f"asset exceeds {MAX_DOWNLOAD_BYTES} bytes")
    atomic_write(path, raw)
    return raw, {
        "cache_path": str(path),
        "final_url": final_url,
        "from_cache": False,
        "size": len(raw),
        "sha256": sha256_bytes(raw),
    }


def json_load(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"))


def parse_simpletes(raw: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    value = json_load(raw)
    return [{"name": "best", "payload": {"circles": value["data"]}}]


def parse_hyra_centered(raw: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    value = json_load(raw)
    circles = [[x + 0.5, y + 0.5, radius] for x, y, radius in value["pieces"]]
    return [{"name": "cirRsqu_n26", "payload": {"circles": circles}}]


def parse_theta_bundle(raw: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    value = json_load(raw)
    candidates = []
    for item in value:
        construction = item["list"]
        # The "Formal" record stores [centers, radii]; the other records
        # directly store [x, y, radius] rows.
        if (
            len(construction) == 2
            and len(construction[0]) == 26
            and len(construction[1]) == 26
            and all(len(point) == 2 for point in construction[0])
        ):
            centers, radii = construction
            construction = [
                [point[0], point[1], radius]
                for point, radius in zip(centers, radii)
            ]
        candidates.append(
            {"name": str(item["name"]), "payload": {"circles": construction}}
        )
    return candidates


def parse_eurek_jsonl(raw: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, line in enumerate(raw.decode("utf-8").splitlines()):
        if not line.strip():
            continue
        value = json.loads(line)
        solution = value["solution"]
        centers = solution["centers"]
        radii = solution["radii"]
        if len(centers) != len(radii):
            raise ValueError("Eurek centers/radii length mismatch")
        circles = [[point[0], point[1], radius] for point, radius in zip(centers, radii)]
        candidates.append({"name": f"line_{index}", "payload": {"circles": circles}})
    return candidates


def notebook_literal_array(raw: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract one np.array(<literal>) assignment from a notebook via AST.

    Deliberately supports literals only.  Calls, names, operators, and all other
    executable expressions inside the array argument are rejected by
    ast.literal_eval.
    """

    notebook = json_load(raw)
    cell_index = int(source["cell_index"])
    variable = str(source["variable"])
    cell = notebook["cells"][cell_index]
    text = "".join(cell["source"])
    tree = ast.parse(text, filename=f"notebook-cell-{cell_index}", mode="exec")
    literal = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == variable for target in node.targets):
            continue
        call = node.value
        if not isinstance(call, ast.Call) or not call.args:
            continue
        function = call.func
        is_array = (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "np"
            and function.attr == "array"
        )
        if not is_array:
            continue
        literal = ast.literal_eval(call.args[0])
    if literal is None:
        raise ValueError(f"literal np.array assignment {variable!r} not found")
    return [{"name": variable, "payload": {str(source["payload_key"]): literal}}]


def parse_plain_xyz(raw: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    lines = [line.strip() for line in raw.decode("utf-8").splitlines() if line.strip()]
    count = int(lines[0])
    vectors = []
    for line in lines[1:]:
        fields = line.split()
        if len(fields) < 3:
            continue
        vectors.append([float(value) for value in fields[-3:]])
    if len(vectors) != count:
        raise ValueError(f"XYZ declared {count} vectors but contained {len(vectors)}")
    return [{"name": f"n{count}", "payload": {"vectors": vectors}}]


def python_array_literal(text: str, variable: str) -> Any:
    tree = ast.parse(text, filename="downloaded-python-not-executed.py", mode="exec")
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == variable for target in targets):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or not value.args:
            continue
        function = value.func
        is_array = (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "np"
            and function.attr == "array"
        )
        if is_array:
            return ast.literal_eval(value.args[0])
    raise ValueError(f"literal np.array assignment {variable!r} not found")


def parse_python_literal_array(raw: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    text = raw.decode("utf-8")
    array = python_array_literal(text, str(source["variable"]))
    if "radius_subtract" in source:
        amount = float(source["radius_subtract"])
        array = [[row[0], row[1], row[2] - amount] for row in array]
    return [
        {
            "name": str(source["variable"]),
            "payload": {str(source["payload_key"]): array},
        }
    ]


def parse_python_centers_radii(raw: bytes, source: dict[str, Any]) -> list[dict[str, Any]]:
    text = raw.decode("utf-8")
    centers = python_array_literal(text, str(source["centers_variable"]))
    radii = python_array_literal(text, str(source["radii_variable"]))
    if len(centers) != len(radii):
        raise ValueError("Python literal centers/radii length mismatch")
    circles = [[point[0], point[1], radius] for point, radius in zip(centers, radii)]
    return [{"name": "centers_radii", "payload": {"circles": circles}}]


PARSERS = {
    "none": lambda raw, source: [],
    "simpletes_ndarray": parse_simpletes,
    "hyra_centered_circles": parse_hyra_centered,
    "theta_circle_bundle": parse_theta_bundle,
    "eurek_jsonl_circle": parse_eurek_jsonl,
    "notebook_literal_array": notebook_literal_array,
    "plain_xyz": parse_plain_xyz,
    "python_literal_array": parse_python_literal_array,
    "python_centers_radii": parse_python_centers_radii,
}


def load_verifier(config: dict[str, Any]):
    path = Path(config["path"])
    actual = sha256_file(path)
    expected = config["sha256"]
    if actual != expected:
        raise ValueError(f"verifier hash mismatch: {path}: {actual} != {expected}")
    spec = importlib.util.spec_from_file_location(f"frozen_{safe_name(config['slug'])}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load verifier spec: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate, actual


def geometry_diagnostics(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    if slug == "circle-packing":
        circles = np.asarray(payload["circles"], dtype=np.float64)
        centers, radii = circles[:, :2], circles[:, 2]
        wall = np.minimum(centers - radii[:, None], 1.0 - centers - radii[:, None])
        pair = min(
            np.linalg.norm(centers[i] - centers[j]) - radii[i] - radii[j]
            for i in range(len(circles))
            for j in range(i + 1, len(circles))
        )
        return {
            "shape": list(circles.shape),
            "radius_sum": float(radii.sum()),
            "minimum_wall_slack": float(wall.min()),
            "minimum_pair_slack": float(pair),
        }
    if slug == "circles-rectangle":
        circles = np.asarray(payload["circles"], dtype=np.float64)
        centers, radii = circles[:, :2], circles[:, 2]
        width = float(np.max(centers[:, 0] + radii) - np.min(centers[:, 0] - radii))
        height = float(np.max(centers[:, 1] + radii) - np.min(centers[:, 1] - radii))
        pair = min(
            np.linalg.norm(centers[i] - centers[j]) - radii[i] - radii[j]
            for i in range(len(circles))
            for j in range(i + 1, len(circles))
        )
        return {
            "shape": list(circles.shape),
            "radius_sum": float(radii.sum()),
            "width_plus_height": width + height,
            "minimum_pair_slack": float(pair),
        }
    if slug in {"heilbronn-triangles", "min-distance-ratio-2d", "thomson-problem"}:
        key = "points" if slug == "heilbronn-triangles" else "vectors"
        array = np.asarray(payload[key], dtype=np.float64)
        return {"shape": list(array.shape), "finite": bool(np.isfinite(array).all())}
    return {}


def finite_score(value: Any) -> float | str:
    number = float(value)
    if math.isnan(number):
        return "NaN"
    if number == float("inf"):
        return "Infinity"
    if number == -float("inf"):
        return "-Infinity"
    return number


def score_candidate(
    verifier: dict[str, Any], evaluate, payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        score_raw = float(evaluate(payload))
        error = None
    except Exception as exc:  # Receipt preserves literal-verifier exceptions.
        score_raw = float("nan")
        error = f"{type(exc).__name__}: {exc}"

    target = float(verifier["target"])
    leader = float(verifier["leader"])
    direction = verifier["direction"]
    if math.isfinite(score_raw):
        gate_margin = score_raw - target if direction == "max" else target - score_raw
        leader_delta = score_raw - leader if direction == "max" else leader - score_raw
        gate_clear = gate_margin > 0.0
    else:
        gate_margin = None
        leader_delta = None
        gate_clear = False
    return {
        "score": finite_score(score_raw),
        "error": error,
        "leader": leader,
        "target": target,
        "direction": direction,
        "gate_margin": gate_margin,
        "leader_delta": leader_delta,
        "strict_gate_clear": gate_clear,
    }


def run(manifest_path: Path, refresh: bool, receipt_path: Path) -> dict[str, Any]:
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    verifiers: dict[str, tuple[dict[str, Any], Any, str]] = {}
    for slug, config0 in manifest["verifiers"].items():
        config = dict(config0)
        config["slug"] = slug
        evaluate, verifier_hash = load_verifier(config)
        verifiers[slug] = (config, evaluate, verifier_hash)

    downloaded: dict[str, tuple[bytes, dict[str, Any]]] = {}
    source_results: list[dict[str, Any]] = []
    gate_clearers: list[dict[str, Any]] = []
    for source in manifest["sources"]:
        url = source["url"]
        entry: dict[str, Any] = {
            "id": source["id"],
            "url": url,
            "parser": source["parser"],
            "slug": source.get("slug"),
            "purpose": source.get("purpose"),
            "candidates": [],
        }
        try:
            if url not in downloaded:
                downloaded[url] = fetch(url, refresh)
            raw, download = downloaded[url]
            entry["download"] = download
            parser = PARSERS[source["parser"]]
            candidates = parser(raw, source)
            if candidates and not source.get("slug"):
                raise ValueError("replayable source is missing slug")
            for candidate in candidates:
                payload = candidate["payload"]
                payload_raw = json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode("utf-8")
                filename = (
                    f"{safe_name(source['id'])}__{safe_name(candidate['name'])}__"
                    f"{sha256_bytes(payload_raw)[:12]}.json"
                )
                payload_path = ROOT / "payloads" / filename
                atomic_write(payload_path, payload_raw + b"\n")
                verifier, evaluate, verifier_hash = verifiers[source["slug"]]
                result = {
                    "name": candidate["name"],
                    "payload_path": str(payload_path),
                    "payload_sha256": sha256_bytes(payload_raw),
                    "verifier_path": verifier["path"],
                    "verifier_sha256": verifier_hash,
                    "diagnostics": geometry_diagnostics(source["slug"], payload),
                }
                result.update(score_candidate(verifier, evaluate, payload))
                entry["candidates"].append(result)
                if result["strict_gate_clear"]:
                    gate_clearers.append({"source_id": source["id"], **result})
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        source_results.append(entry)

    corpus_path = Path(manifest["corpus_snapshot"])
    receipt = {
        "schema_version": 1,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "python": sys.version,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_bytes(manifest_raw),
        "corpus_snapshot": str(corpus_path),
        "corpus_sha256": sha256_file(corpus_path),
        "network_policy": "HTTPS GET only; redirect destination host revalidated; no remote code execution",
        "gate_clearers": gate_clearers,
        "sources": source_results,
    }
    atomic_write(
        receipt_path,
        (json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(),
    )
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "sources.json")
    parser.add_argument("--receipt", type=Path, default=ROOT / "receipt.json")
    parser.add_argument("--refresh", action="store_true", help="repeat each unique HTTPS GET")
    arguments = parser.parse_args()
    receipt = run(arguments.manifest.resolve(), arguments.refresh, arguments.receipt.resolve())
    compact = {
        "receipt": str(arguments.receipt.resolve()),
        "manifest_sha256": receipt["manifest_sha256"],
        "corpus_sha256": receipt["corpus_sha256"],
        "gate_clearers": receipt["gate_clearers"],
        "scores": [
            {
                "source": source["id"],
                "name": candidate["name"],
                "score": candidate["score"],
                "gate_margin": candidate["gate_margin"],
            }
            for source in receipt["sources"]
            for candidate in source["candidates"]
        ],
        "errors": [
            {"source": source["id"], "error": source["error"]}
            for source in receipt["sources"]
            if source.get("error")
        ],
    }
    print(json.dumps(compact, indent=2, sort_keys=True, allow_nan=False))
    return 0 if not compact["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
