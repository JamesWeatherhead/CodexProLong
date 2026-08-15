#!/usr/bin/env python3
"""Recover public C3 assets and replay the unchanged frozen Arena verifier.

Every network operation is an HTTP GET against a commit-pinned GitHub URL.
Third-party source blobs and arrays stay under git-ignored local directories.
Remote Python is never executed: literal arrays are extracted with ``ast``.
"""

from __future__ import annotations

import ast
import gzip
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
    / "campaign/state/problems/third-autocorrelation-inequality/"
    "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9.py"
)
VERIFIER_SHA256 = (
    "b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9"
)
CORPUS = REPO / "campaign/research_corpus/snapshots/20260815T003306Z/corpus.sqlite3"
CORPUS_SHA256 = (
    "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"
)
LOCAL_FRONTIER = (
    REPO
    / "campaign/c3_root/turbo-topology-continuation-v2/runs/"
    "20260815T031008Z/best.npy"
)
LOCAL_FRONTIER_SHA256 = (
    "c3af7761fd3cf1a9a812b1ed04219eb17ceb5821946990efbd6f09d4d31679bd"
)
PUBLIC_LEADER_SCORE = 1.4515718638902069
MIN_IMPROVEMENT = 1e-5
STRICT_GATE = PUBLIC_LEADER_SCORE - MIN_IMPROVEMENT

SIMPLETES_COMMIT = "a19a54b109db6185ab1f13dd59dd150074b24136"
TOGETHER_COMMIT = "c388c6f7408c886311940896713339a1a70c2394"
ALPHAEVOLVE_COMMIT = "4226acbf237ff9ad10ba7673a2af127a2d8a5971"
THETA_COMMIT = "7c12898f5d7627af403e3aca643af76199fb5c20"
JMSUNG_COMMIT = "1762674da8374d631b718dc7feeecdbd8753a2ea"
GIGAEVO_COMMIT = "0f2b866543089a6054f57f1a71eb615a55d89348"
OPENEVOLVE_COMMIT = "411fb59c886c18704caaffb611e17cf9e7d824d2"
SHINKA_COMMIT = "d4e9b9d43e8a2df186d32f2e52d2db7183115b3e"
HYRA_COMMIT = "26ebfbe7d491e6521d8bb5fc21fe88bb31460825"


CONSTRUCTION_SOURCES: dict[str, dict[str, Any]] = {
    "simpletes": {
        "url": (
            "https://raw.githubusercontent.com/wq-will/SimpleTES/"
            f"{SIMPLETES_COMMIT}/best_results/mathematics_discovery/"
            "third_autocorrelation_inequality/"
            "third_autocorrelation_inequality_best_construction.json"
        ),
        "sha256": "26aa4363b9a1afd5c8f0ba6b94c4987a052f6f876b419de167cb37092d43092d",
        "cache_name": "simpletes-construction.json",
        "parser": "simpletes_json",
        "repository": "wq-will/SimpleTES",
        "commit": SIMPLETES_COMMIT,
        "license": "GNU AGPL-3.0-or-later",
    },
    "together_2026": {
        "url": (
            "https://raw.githubusercontent.com/togethercomputer/"
            f"erdos-minimum-overlap/{TOGETHER_COMMIT}/third-autocorrelation/"
            "solutions/ours_2026.py"
        ),
        "sha256": "ef0e4f1a8544537adca7931ae1ce9b73a5e140e065b0718b1d5064e48cc2c77f",
        "cache_name": "together-ours-2026.py",
        "parser": "python_f_values",
        "repository": "togethercomputer/erdos-minimum-overlap",
        "commit": TOGETHER_COMMIT,
        "license": "NOASSERTION (GitHub reports no repository license)",
    },
    "together_alphaevolve_2025": {
        "url": (
            "https://raw.githubusercontent.com/togethercomputer/"
            f"erdos-minimum-overlap/{TOGETHER_COMMIT}/third-autocorrelation/"
            "solutions/alphaevolve_2025.py"
        ),
        "sha256": "7ad28403a9fd140754203ad5b67bed6b4925084f8923ef110bedbeb713b3cb09",
        "cache_name": "together-alphaevolve-2025.py",
        "parser": "python_f_values",
        "repository": "togethercomputer/erdos-minimum-overlap",
        "commit": TOGETHER_COMMIT,
        "license": "NOASSERTION (GitHub reports no repository license)",
    },
    "alphaevolve_official": {
        "url": (
            "https://raw.githubusercontent.com/google-deepmind/"
            f"alphaevolve_results/{ALPHAEVOLVE_COMMIT}/mathematical_results.ipynb"
        ),
        "sha256": "2cce2543e48c89aa3e91614272a698a0147dd2548ea11cf92f1292b7435d38ff",
        "cache_name": "alphaevolve-mathematical-results.ipynb",
        "parser": "notebook_height_sequence_3",
        "repository": "google-deepmind/alphaevolve_results",
        "commit": ALPHAEVOLVE_COMMIT,
        "license": "Apache-2.0",
    },
    "thetaevolve": {
        "url": (
            "https://raw.githubusercontent.com/ypwang61/ThetaEvolve/"
            f"{THETA_COMMIT}/Results/ThirdAutoCorrIneq/data.json"
        ),
        "sha256": "60a0ed6553dbf97f10bd2024edd1a3229facf719f74fca80fc488c82a1352a15",
        "cache_name": "thetaevolve-data.json",
        "parser": "theta_json",
        "repository": "ypwang61/ThetaEvolve",
        "commit": THETA_COMMIT,
        "license": "Apache-2.0",
    },
    "jmsung_best": {
        "url": (
            "https://raw.githubusercontent.com/jmsung/einstein/"
            f"{JMSUNG_COMMIT}/scripts/third_autocorrelation/seeds/best.json.gz"
        ),
        "sha256": "6e3c1a332ea4da79ae684850aa8e01f8b6624c13eff171c6ac4b8354b12e86d6",
        "cache_name": "jmsung-best.json.gz",
        "parser": "gzip_values_json",
        "repository": "jmsung/einstein",
        "commit": JMSUNG_COMMIT,
        "license": "MIT",
    },
}


PROGRAM_SOURCES: dict[str, dict[str, str]] = {
    "simpletes_program": {
        "url": (
            "https://raw.githubusercontent.com/wq-will/SimpleTES/"
            f"{SIMPLETES_COMMIT}/best_results/mathematics_discovery/"
            "third_autocorrelation_inequality/"
            "third_autocorrelation_inequality_best.py"
        ),
        "sha256": "c5fde1649ded92ac9b3c6d1ff1095aa312be42706babdecf6bc03fcff69cc70e",
        "cache_name": "simpletes-program.py",
        "repository": "wq-will/SimpleTES",
        "commit": SIMPLETES_COMMIT,
        "license": "GNU AGPL-3.0-or-later",
        "classification": "published search program with frozen construction above",
    },
    "theta_init": {
        "url": (
            "https://raw.githubusercontent.com/ypwang61/ThetaEvolve/"
            f"{THETA_COMMIT}/Results/ThirdAutoCorrIneq/programs/Init.py"
        ),
        "sha256": "9ba0e740d5b68326110af878a04a6aa404ff4fdf2d38d3b4300d793473f23c7a",
        "cache_name": "theta-Init.py",
        "repository": "ypwang61/ThetaEvolve",
        "commit": THETA_COMMIT,
        "license": "Apache-2.0",
        "classification": "program paired with frozen data.json construction",
    },
    "theta_8b_rl": {
        "url": (
            "https://raw.githubusercontent.com/ypwang61/ThetaEvolve/"
            f"{THETA_COMMIT}/Results/ThirdAutoCorrIneq/programs/8B-w_RL@65.py"
        ),
        "sha256": "0113766d5196a6bacb99df79c8d657349d54ff999ba6da5deb9fbc944e6d95ab",
        "cache_name": "theta-8B-w-RL-65.py",
        "repository": "ypwang61/ThetaEvolve",
        "commit": THETA_COMMIT,
        "license": "Apache-2.0",
        "classification": "program paired with frozen data.json construction",
    },
    "theta_8b_no_rl": {
        "url": (
            "https://raw.githubusercontent.com/ypwang61/ThetaEvolve/"
            f"{THETA_COMMIT}/Results/ThirdAutoCorrIneq/programs/8B-wo_RL@100.py"
        ),
        "sha256": "52eb61b4b9432b7090b3bc8f1289d39c8ca0e915222ba152eb2615529733f644",
        "cache_name": "theta-8B-wo-RL-100.py",
        "repository": "ypwang61/ThetaEvolve",
        "commit": THETA_COMMIT,
        "license": "Apache-2.0",
        "classification": "program paired with frozen data.json construction",
    },
    "theta_1_5b_rl": {
        "url": (
            "https://raw.githubusercontent.com/ypwang61/ThetaEvolve/"
            f"{THETA_COMMIT}/Results/ThirdAutoCorrIneq/programs/1.5B-w_RL@200.py"
        ),
        "sha256": "e293c8edcb294a4b6190209d633cc8d77936ce908ecc8f0ad27b992543c12cb5",
        "cache_name": "theta-1.5B-w-RL-200.py",
        "repository": "ypwang61/ThetaEvolve",
        "commit": THETA_COMMIT,
        "license": "Apache-2.0",
        "classification": "program paired with frozen data.json construction",
    },
    "theta_1_5b_no_rl": {
        "url": (
            "https://raw.githubusercontent.com/ypwang61/ThetaEvolve/"
            f"{THETA_COMMIT}/Results/ThirdAutoCorrIneq/programs/1.5B-wo_RL@600.py"
        ),
        "sha256": "1d7ce3f208e161b65ebba78274d0c0203f81fd52adbf2d580351315858c1c379",
        "cache_name": "theta-1.5B-wo-RL-600.py",
        "repository": "ypwang61/ThetaEvolve",
        "commit": THETA_COMMIT,
        "license": "Apache-2.0",
        "classification": "program paired with frozen data.json construction",
    },
    "gigaevo_initial": {
        "url": (
            "https://raw.githubusercontent.com/FusionBrainLab/gigaevo-core/"
            f"{GIGAEVO_COMMIT}/problems/alphaevolve/third_autocorr_ineq/"
            "initial_programs/optimize.py"
        ),
        "sha256": "2ed9e4849932c5701e04da1891708859e360dd0e68de7ae24c1d14a7bb86a659",
        "cache_name": "gigaevo-optimize.py",
        "repository": "FusionBrainLab/gigaevo-core",
        "commit": GIGAEVO_COMMIT,
        "license": "MIT",
        "classification": "deterministic starter only; repository publishes no frozen C3 output",
    },
    "gigaevo_helper": {
        "url": (
            "https://raw.githubusercontent.com/FusionBrainLab/gigaevo-core/"
            f"{GIGAEVO_COMMIT}/problems/alphaevolve/third_autocorr_ineq/helper.py"
        ),
        "sha256": "bf42fb1c27553c8750d186ea129ae42bd6a6592f7c5f24fd20d31a0594ce06de",
        "cache_name": "gigaevo-helper.py",
        "repository": "FusionBrainLab/gigaevo-core",
        "commit": GIGAEVO_COMMIT,
        "license": "MIT",
        "classification": "C3 evaluator helper; no frozen output",
    },
    "gigaevo_metrics": {
        "url": (
            "https://raw.githubusercontent.com/FusionBrainLab/gigaevo-core/"
            f"{GIGAEVO_COMMIT}/problems/alphaevolve/third_autocorr_ineq/metrics.yaml"
        ),
        "sha256": "fc7d3c3499d412f75b8921994dc3041da4759702c787eba86619d72ae2c67e3e",
        "cache_name": "gigaevo-metrics.yaml",
        "repository": "FusionBrainLab/gigaevo-core",
        "commit": GIGAEVO_COMMIT,
        "license": "MIT",
        "classification": "C3 metric declaration; no frozen output",
    },
    "openevolve_initial": {
        "url": (
            "https://raw.githubusercontent.com/algorithmicsuperintelligence/"
            f"openevolve/{OPENEVOLVE_COMMIT}/examples/alphaevolve_math_problems/"
            "third_autocorr_ineq/initial_program.py"
        ),
        "sha256": "33b723258a2354b489e89e94e8fb3dae89442f362fcfaaf7f6d5cbf2d125adbb",
        "cache_name": "openevolve-initial.py",
        "repository": "algorithmicsuperintelligence/openevolve",
        "commit": OPENEVOLVE_COMMIT,
        "license": "Apache-2.0",
        "classification": "n=400 C3 JAX starter only; no frozen evolved output",
    },
    "shinkaevolve_initial": {
        "url": (
            "https://raw.githubusercontent.com/jaumededios/ShinkaYale/"
            f"{SHINKA_COMMIT}/Examples_Shinkaevolve/"
            "4_2_third_autocorrelation_solution/initial.py"
        ),
        "sha256": "d0b0088a7179fe57f1ac8de064b38869de4a471e34172873650a11b9f54d1bd2",
        "cache_name": "shinkaevolve-initial.py",
        "repository": "jaumededios/ShinkaYale",
        "commit": SHINKA_COMMIT,
        "license": "NOASSERTION (GitHub reports no repository license)",
        "classification": "random-search starter only; no frozen evolved output",
    },
}


LICENSE_SOURCES: dict[str, dict[str, str]] = {
    "simpletes": {
        "url": f"https://raw.githubusercontent.com/wq-will/SimpleTES/{SIMPLETES_COMMIT}/LICENSE",
        "sha256": "3bdf828d3e3e55318bb9d12e10dbda27b4f7725d9da7ced98b526359ff80fb7d",
        "cache_name": "LICENSE-SimpleTES",
    },
    "alphaevolve": {
        "url": f"https://raw.githubusercontent.com/google-deepmind/alphaevolve_results/{ALPHAEVOLVE_COMMIT}/LICENSE",
        "sha256": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
        "cache_name": "LICENSE-alphaevolve-results",
    },
    "thetaevolve": {
        "url": f"https://raw.githubusercontent.com/ypwang61/ThetaEvolve/{THETA_COMMIT}/LICENSE",
        "sha256": "bf917707c1e0ffdfe653d63aebc188a48f738f3faad9acc188c346d3618694af",
        "cache_name": "LICENSE-ThetaEvolve",
    },
    "jmsung": {
        "url": f"https://raw.githubusercontent.com/jmsung/einstein/{JMSUNG_COMMIT}/LICENSE",
        "sha256": "e1be5288a75dc4c7e6c84548d1b72b661080421517a6247da6b6dd6753d6478b",
        "cache_name": "LICENSE-jmsung-einstein",
    },
    "gigaevo": {
        "url": f"https://raw.githubusercontent.com/FusionBrainLab/gigaevo-core/{GIGAEVO_COMMIT}/LICENSE",
        "sha256": "bf3ea8739346080477f584894a92ec0cdffe7c2d31f6c520f7e75c7bceee7948",
        "cache_name": "LICENSE-gigaevo-core",
    },
    "openevolve": {
        "url": (
            "https://raw.githubusercontent.com/algorithmicsuperintelligence/"
            f"openevolve/{OPENEVOLVE_COMMIT}/LICENSE"
        ),
        "sha256": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
        "cache_name": "LICENSE-openevolve",
    },
}

HYRA_TREE_URL = (
    "https://api.github.com/repos/Tencent-Hunyuan/Hyra-results/git/trees/"
    f"{HYRA_COMMIT}?recursive=1"
)
HYRA_TREE_CANONICAL_SHA256 = (
    "71fc56f0c3200daf3aeebb72ad1100d82adcad5d123451b5c5fcf3c27866680d"
)
HYRA_LICENSE_URL = (
    "https://raw.githubusercontent.com/Tencent-Hunyuan/Hyra-results/"
    f"{HYRA_COMMIT}/LICENSE"
)
HYRA_LICENSE_SHA256 = (
    "ece6c7026732f576af3a909a117b321c9e8cfd96fc4d56e5229ff1a288dae087"
)

PAPERCLIP_SOURCES = [
    {
        "claim": "AlphaEvolve reports a 400-cell C3 construction with C3 <= 1.4557.",
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2506.13131#L190-L193",
    },
    {
        "claim": "The later mathematics report gives the C3 setup and the same 1.4557 result.",
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L118-L121",
    },
    {
        "claim": "ImprovEvolve's reported autocorrelation result is for C2, not C3.",
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2602.10233#L1",
    },
    {
        "claim": "GigaEvo reports four validation problems and publishes its framework; it does not report a C3 result.",
        "url": "https://paperclip.gxl.ai/citations/papers/arx_2511.17592#L30-L32,L65-L66",
    },
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "c3-asset-audit/1"})
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
    spec = importlib.util.spec_from_file_location("frozen_c3_verifier", VERIFIER)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assignment_literal(source: str, name: str) -> np.ndarray:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        value = node.value
        if isinstance(value, ast.Call):
            if not value.args:
                continue
            value = value.args[0]
        return np.asarray(ast.literal_eval(value), dtype=np.float64)
    raise ValueError(f"literal assignment {name!r} not found")


def parse_source(source: dict[str, Any], raw: bytes) -> list[tuple[str, np.ndarray]]:
    parser = str(source["parser"])
    if parser == "simpletes_json":
        parsed = json.loads(raw)
        return [("simpletes", np.asarray(parsed["data"], dtype=np.float64))]
    if parser == "python_f_values":
        label = str(source["cache_name"]).removesuffix(".py")
        return [(label, assignment_literal(raw.decode(), "f_values"))]
    if parser == "notebook_height_sequence_3":
        notebook = json.loads(raw)
        for cell in notebook["cells"]:
            text = "".join(cell.get("source", []))
            if "height_sequence_3" in text:
                return [("alphaevolve-official", assignment_literal(text, "height_sequence_3"))]
        raise ValueError("official C3 notebook cell not found")
    if parser == "theta_json":
        return [
            ("theta-" + str(row["name"]).replace("/", "-"), np.asarray(row["list"], dtype=np.float64))
            for row in json.loads(raw)
        ]
    if parser == "gzip_values_json":
        parsed = json.loads(gzip.decompress(raw))
        return [("jmsung-best", np.asarray(parsed["values"], dtype=np.float64))]
    raise ValueError(f"unknown parser: {parser}")


def corpus_rows() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    if sha256(CORPUS.read_bytes()) != CORPUS_SHA256:
        raise RuntimeError("frozen Arena corpus hash drift")
    rows: list[dict[str, Any]] = []
    by_hash: dict[str, list[dict[str, Any]]] = {}
    connection = sqlite3.connect(f"file:{CORPUS}?mode=ro", uri=True)
    try:
        query = connection.execute(
            "SELECT id, agent_name, score, record_json FROM solutions "
            "WHERE problem_id = 4 ORDER BY id"
        )
        for solution_id, agent_name, score, record_json in query:
            values = np.asarray(json.loads(record_json)["data"]["values"], dtype=np.float64)
            value_hash = sha256(np.ascontiguousarray(values).tobytes())
            row = {
                "id": int(solution_id),
                "agent_name": str(agent_name),
                "score": float(score),
                "n": int(values.size),
                "values_sha256": value_hash,
                "values": values,
            }
            rows.append(row)
            by_hash.setdefault(value_hash, []).append(row)
    finally:
        connection.close()
    return rows, by_hash


def equivalent_matches(values: np.ndarray, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = float(np.sum(values))
    if total == 0.0:
        return []
    matches: list[dict[str, Any]] = []
    for row in rows:
        prior = row["values"]
        if prior.size != values.size or float(np.sum(prior)) == 0.0:
            continue
        prior_normalized = prior / np.sum(prior)
        for variant, candidate in (("same", values), ("reverse", values[::-1])):
            error = float(np.max(np.abs(candidate / np.sum(candidate) - prior_normalized)))
            if error < 1e-12:
                matches.append(
                    {
                        "id": row["id"],
                        "agent_name": row["agent_name"],
                        "score": row["score"],
                        "variant": variant,
                        "max_normalized_error": error,
                    }
                )
    return matches


def audit_values(
    label: str,
    values: np.ndarray,
    verifier: ModuleType,
    rows: list[dict[str, Any]],
    by_hash: dict[str, list[dict[str, Any]]],
    score_cache: dict[str, float],
) -> dict[str, Any]:
    if values.ndim != 1 or values.size == 0 or values.size > 2_000_000:
        raise RuntimeError(f"{label}: invalid shape {values.shape}")
    if not np.isfinite(values).all() or float(np.sum(values)) == 0.0:
        raise RuntimeError(f"{label}: invalid values")
    values = np.ascontiguousarray(values, dtype=np.float64)
    value_hash = sha256(values.tobytes())
    score = score_cache.get(value_hash)
    if score is None:
        score = float(verifier.evaluate({"values": values.tolist()}))
        score_cache[value_hash] = score
    payload = PAYLOADS / f"{label}.npy"
    payload_hash = atomic_npy(payload, values)
    exact = [
        {key: row[key] for key in ("id", "agent_name", "score")}
        for row in by_hash.get(value_hash, [])
    ]
    return {
        "label": label,
        "n": int(values.size),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
        "sum": float(np.sum(values)),
        "positive": int(np.count_nonzero(values > 0.0)),
        "negative": int(np.count_nonzero(values < 0.0)),
        "zero": int(np.count_nonzero(values == 0.0)),
        "score": score,
        "gap_to_public_leader": score - PUBLIC_LEADER_SCORE,
        "gap_to_strict_gate": score - STRICT_GATE,
        "gate_cleared": score <= STRICT_GATE,
        "values_sha256": value_hash,
        "payload_path": str(payload.relative_to(REPO)),
        "payload_file_sha256": payload_hash,
        "exact_corpus_matches": exact,
        "scale_or_reverse_equivalent_matches": equivalent_matches(values, rows),
    }


def download_pinned(
    name: str, source: dict[str, str], directory: Path = CACHE
) -> dict[str, Any]:
    raw = fetch(source["url"])
    actual = sha256(raw)
    if actual != source["sha256"]:
        raise RuntimeError(f"{name} hash drift: {actual}")
    cache_path = directory / source["cache_name"]
    atomic_bytes(cache_path, raw)
    return {
        **source,
        "bytes": len(raw),
        "cache_path": str(cache_path.relative_to(REPO)),
    }


def hyra_inventory() -> dict[str, Any]:
    raw = fetch(HYRA_TREE_URL)
    parsed = json.loads(raw)
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode()
    actual = sha256(canonical)
    if actual != HYRA_TREE_CANONICAL_SHA256:
        raise RuntimeError(f"Hyra tree drift: {actual}")
    atomic_bytes(CACHE / "hyra-tree.json", raw)
    license_raw = fetch(HYRA_LICENSE_URL)
    if sha256(license_raw) != HYRA_LICENSE_SHA256:
        raise RuntimeError("Hyra license hash drift")
    atomic_bytes(CACHE / "LICENSE-Hyra-results", license_raw)
    paths = [row["path"] for row in parsed["tree"]]
    autocorrelation_paths = [path for path in paths if "autocorrelation" in path.lower()]
    c3_paths = [
        path
        for path in paths
        if any(term in path.lower() for term in ("third_autocorr", "autocorrelation_third"))
    ]
    return {
        "repository": "Tencent-Hunyuan/Hyra-results",
        "commit": HYRA_COMMIT,
        "license": "Apache-2.0",
        "tree_url": HYRA_TREE_URL,
        "tree_canonical_sha256": actual,
        "tree_entries": len(paths),
        "tree_truncated": bool(parsed.get("truncated")),
        "autocorrelation_paths": autocorrelation_paths,
        "c3_paths": c3_paths,
        "conclusion": "no downloadable C3 construction at the pinned commit",
    }


def main() -> int:
    verifier = load_verifier()
    rows, by_hash = corpus_rows()
    score_cache: dict[str, float] = {}
    constructions: list[dict[str, Any]] = []
    source_receipts: dict[str, Any] = {}
    for source_name, source in CONSTRUCTION_SOURCES.items():
        raw = fetch(str(source["url"]))
        actual = sha256(raw)
        if actual != source["sha256"]:
            raise RuntimeError(f"{source_name} source hash drift: {actual}")
        cache_path = CACHE / str(source["cache_name"])
        atomic_bytes(cache_path, raw)
        labels: list[str] = []
        for label, values in parse_source(source, raw):
            result = audit_values(label, values, verifier, rows, by_hash, score_cache)
            result["source_name"] = source_name
            constructions.append(result)
            labels.append(label)
        source_receipts[source_name] = {
            **source,
            "bytes": len(raw),
            "cache_path": str(cache_path.relative_to(REPO)),
            "construction_labels": labels,
        }

    programs = {
        name: download_pinned(name, source)
        for name, source in PROGRAM_SOURCES.items()
    }
    licenses = {
        name: download_pinned(name, source)
        for name, source in LICENSE_SOURCES.items()
    }
    hyra = hyra_inventory()

    frontier_hash = sha256(LOCAL_FRONTIER.read_bytes())
    if frontier_hash != LOCAL_FRONTIER_SHA256:
        raise RuntimeError(f"local frontier drift: {frontier_hash}")
    frontier = np.load(LOCAL_FRONTIER, allow_pickle=False).astype(np.float64)
    frontier_score = float(verifier.evaluate({"values": frontier.tolist()}))

    distinct = [row for row in constructions if not row["exact_corpus_matches"]]
    best_distinct = min(distinct, key=lambda row: float(row["score"]))
    best_overall = min(constructions, key=lambda row: float(row["score"]))
    receipt = {
        "schema": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "commit_pinned_GET_static_parse_and_unchanged_verifier_replay",
        "network_policy": "GET-only",
        "external_writes": [],
        "verifier": {
            "path": str(VERIFIER.relative_to(REPO)),
            "sha256": VERIFIER_SHA256,
        },
        "frozen_arena_corpus": {
            "path": str(CORPUS.relative_to(REPO)),
            "sha256": CORPUS_SHA256,
            "c3_rows_checked": len(rows),
        },
        "frontier": {
            "public_leader_score": PUBLIC_LEADER_SCORE,
            "minimum_improvement": MIN_IMPROVEMENT,
            "strict_gate": STRICT_GATE,
            "local_path": str(LOCAL_FRONTIER.relative_to(REPO)),
            "local_file_sha256": frontier_hash,
            "local_values_sha256": sha256(np.ascontiguousarray(frontier).tobytes()),
            "local_score": frontier_score,
        },
        "construction_sources": source_receipts,
        "constructions": constructions,
        "program_artifacts": programs,
        "license_artifacts": licenses,
        "hyra_inventory": hyra,
        "paperclip_sources": PAPERCLIP_SOURCES,
        "coverage_notes": {
            "improvevolve": "primary paper reports C2 only and exposes no C3 construction",
            "gigaevo": "primary paper does not evaluate C3; repository has a C3 starter but no frozen output",
            "openevolve": "repository has an n=400 C3 starter but no frozen evolved output",
            "shinkaevolve": "example repository has a starter/evaluator but no frozen evolved output",
            "mlevolve": "repository README reports C3 scores but its complete tree exposes no downloadable C3 construction or program",
            "forks": "all 16 public SimpleTES forks and the ahead official AlphaEvolve fork checked during discovery retained byte-identical C3 assets",
            "together_and_alphaevolve": "published 400-cell arrays are exact frozen-Arena duplicates",
        },
        "best_recovered_overall": {
            key: best_overall[key]
            for key in ("label", "score", "n", "values_sha256", "exact_corpus_matches")
        },
        "best_new_distinct": {
            key: best_distinct[key]
            for key in ("label", "score", "n", "values_sha256", "exact_corpus_matches")
        },
        "best_new_gap_to_local_frontier": float(best_distinct["score"]) - frontier_score,
        "competitive_new_seed": bool(float(best_distinct["score"]) <= frontier_score),
        "topology_transfer": {
            "run": False,
            "reason": "no distinct recovered construction is competitive with the frozen local frontier",
        },
        "conclusion": (
            "SimpleTES is the best newly distinct public C3 array recovered, but it is "
            "far above the local frontier. The strongest high-resolution asset is an exact "
            "duplicate of two frozen Arena submissions. No topology-transfer run is justified."
        ),
    }
    atomic_json(RECEIPT, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
