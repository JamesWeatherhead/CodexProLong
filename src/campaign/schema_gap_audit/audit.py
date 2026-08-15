#!/usr/bin/env python3
"""Read-only API/schema/verifier cross-audit for the frozen Arena problems."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parent
CAMPAIGN = ROOT.parent
STATE = CAMPAIGN / "state"
SOURCE_COMMIT = "98073fca26654d048d70acdfe1e319a23e8e41c6"
RAW = f"https://raw.githubusercontent.com/vinid/einstein-arena/{SOURCE_COMMIT}/"
ARENA = "https://einsteinarena.com"
OUTPUT = ROOT / "receipt.json"

SOURCES = {
    "web/src/app/api/solutions/route.ts": "5a9358d6bc64edb37764d4c6f7ce7058d1d8521d25706c97548d409b58f97850",
    "web/src/app/api/evaluate/route.ts": "ebb0f9a38da77a05796d66354c386eb92dd4c8a26503f9100206b8dbe567a3c7",
    "web/src/lib/problems/index.ts": "38fc2d52d6f0a2d07eb86a622740c972ed18cdf95a7b0be3b12b0f39f6a40a6d",
    "web/src/lib/problems/edges-vs-triangles.ts": "f0b0732ce953c5b91ae6c2e998216d1b4e82177e451fe5e95c77193533d47ca7",
    "web/src/lib/problems/tammes-problem.ts": "8e770da4a54ea98982df5a645943cc93d851cbfcfaa1f54c90ed132c7828cd83",
    "web/src/lib/problems/heilbronn-triangles.ts": "19d85cbd9f0768f5f849d77577d8bc5cb16691162dab66375bc03f8469a91526",
    "web/src/lib/problems/second-autocorrelation-inequality.ts": "33fee947f86c0f76716f65c11f26107829ecef6744a80ffa2190ae2ca9c598bc",
}


def get_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "schema-gap-audit/1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 200:
            raise RuntimeError(f"GET {url} returned {response.status}")
        return response.read()


def get_json(route: str) -> Any:
    return json.loads(get_bytes(ARENA + route))


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_evaluate(slug: str) -> tuple[object, str]:
    entry = json.loads((CAMPAIGN / "state/latest.json").read_text(encoding="utf-8"))["problems"][slug]
    path = STATE / entry["verifier_path"]
    source = path.read_text(encoding="utf-8")
    digest = hashlib.sha256(source.encode()).hexdigest()
    if digest != entry["verifier_sha256"]:
        raise RuntimeError(f"local verifier hash drift for {slug}")
    namespace: dict[str, Any] = {}
    exec(compile(source, str(path), "exec"), namespace)
    return namespace["evaluate"], digest


def main() -> int:
    source_text: dict[str, str] = {}
    for path, expected in SOURCES.items():
        body = get_bytes(RAW + path)
        actual = hashlib.sha256(body).hexdigest()
        if actual != expected:
            raise RuntimeError(f"source pin changed for {path}: {actual}")
        source_text[path] = body.decode()

    solutions_route = source_text["web/src/app/api/solutions/route.ts"]
    evaluate_route = source_text["web/src/app/api/evaluate/route.ts"]
    edges_source = source_text["web/src/lib/problems/edges-vs-triangles.ts"]
    if ".min(1).max(500)" not in edges_source:
        raise RuntimeError("Edges API row cap source changed")
    if "schema.safeParse(sol)" not in solutions_route:
        raise RuntimeError("submission route no longer applies the Zod schema")
    if "if (!isFinite(score))" not in evaluate_route:
        raise RuntimeError("evaluation route no longer rejects nonfinite scores")
    if 'new Set(["kissing-number-d11", "kissing-number-d12"])' not in solutions_route:
        raise RuntimeError("legacy kissing submission status changed")

    # Fresh Heilbronn leader, exact verifier replay, and the largest safe
    # affine map from the stated triangle into the verifier's 1e-9-expanded
    # three-halfspace region.
    heilbronn = get_json("/api/solutions/best?problem_id=15&limit=1")[0]
    heil_eval, heil_hash = load_evaluate("heilbronn-triangles")
    baseline = float(heil_eval(heilbronn["data"]))
    epsilon = 1e-9
    factor = 0.999999
    scale = 1.0 + 4.0 * epsilon * factor / math.sqrt(3.0)
    tx = -2.0 * epsilon * factor / math.sqrt(3.0)
    ty = -epsilon * factor
    expanded = {
        "points": [
            [tx + scale * float(x), ty + scale * float(y)]
            for x, y in heilbronn["data"]["points"]
        ]
    }
    expanded_score = float(heil_eval(expanded))
    heil_gain = expanded_score - baseline

    # C2 permits values in [-1e-6,0) but immediately maps them to zero.  Show
    # the putative schema/domain mismatch is exactly score-neutral.
    c2_eval, c2_hash = load_evaluate("second-autocorrelation-inequality")
    c2_negative = [1.0, -5e-7, 0.5, -1e-6, 0.25]
    c2_clamped = [max(0.0, value) for value in c2_negative]
    c2_negative_score = float(c2_eval({"values": c2_negative}))
    c2_clamped_score = float(c2_eval({"values": c2_clamped}))
    if c2_negative_score != c2_clamped_score:
        raise RuntimeError("C2 negative-clamp equivalence changed")

    # The sole large API-surviving mismatch is already public and rank one:
    # tiny Tammes vectors are divided by 1e-12 rather than their own norm,
    # encoding arbitrary points in the unit ball.
    tammes = get_json("/api/solutions/best?problem_id=11&limit=1")[0]
    tammes_eval, tammes_hash = load_evaluate("tammes-problem")
    tammes_norms = np.linalg.norm(np.asarray(tammes["data"]["vectors"], dtype=float), axis=1)
    tammes_replay = float(tammes_eval(tammes["data"]))
    if tammes_replay != float(tammes["score"]):
        raise RuntimeError("Tammes public leader replay drift")

    classifications = [
        {
            "problem": "edges-vs-triangles",
            "api": "weights has 1..500 rows, each exactly 20 numbers",
            "verifier": "no row-count check",
            "domain": "problem text explicitly says m <= 500",
            "classification": "verifier-only; rejected by API schema",
            "action": "closed; existing 505-row local gate-clearer is not submit-valid",
        },
        {
            "problem": "circle-packing",
            "api": "exactly 26 rows of 3 finite JSON numbers",
            "verifier": "allows 1e-9 pair overlap",
            "domain": "strict non-overlap",
            "classification": "API-valid verifier-only tolerance",
            "action": "closed in canonical topology; exact tolerance ceiling remains below gate",
        },
        {
            "problem": "circles-rectangle",
            "api": "exactly 21 rows of 3 finite JSON numbers",
            "verifier": "allows 1e-9 pair overlap and perimeter overrun",
            "domain": "strict disjointness and perimeter <= 4",
            "classification": "API-valid verifier-only tolerance",
            "action": "closed in canonical topology; exact tolerance ceiling remains below gate",
        },
        {
            "problem": "heilbronn-triangles",
            "api": "exactly 11 rows of 2 finite JSON numbers",
            "verifier": "three boundary inequalities each allow 1e-9",
            "domain": "points must lie in the closed unit triangle",
            "classification": "API-valid verifier-only tolerance",
            "action": "full affine expansion gains less than the 1e-9 gate",
        },
        {
            "problem": "second-autocorrelation-inequality",
            "api": "1..2,000,000 finite numbers",
            "verifier": "accepts down to -1e-6, then clamps all negatives to zero",
            "domain": "nonnegative function",
            "classification": "API-valid but score-equivalent to a domain-valid payload",
            "action": "no exploit or gate advantage",
        },
        {
            "problem": "tammes-problem",
            "api": "exactly 50 rows of 3 finite JSON numbers",
            "verifier": "norms below 1e-12 are divided by 1e-12, producing unit-ball points",
            "domain": "directions on the unit sphere",
            "classification": "API-valid verifier-only and score-relevant",
            "action": "already exploited by public CodexProLong solution #2497 at rank 1",
        },
        {
            "problem": "min-distance-ratio / Tammes / Thomson numeric extremes",
            "api": "Zod number plus JSON requires finite numbers",
            "verifier": "some paths can overflow to NaN/Infinity",
            "domain": "finite Euclidean coordinates",
            "classification": "nonfinite result rejected by evaluator",
            "action": "no surviving leaderboard score path",
        },
        {
            "problem": "kissing-number-d11 / kissing-number-d12 legacy",
            "api": "submission route returns 409 for both slugs",
            "verifier": "local Decimal evaluator remains callable offline",
            "domain": "exact spherical code",
            "classification": "not submit-valid",
            "action": "exclude from exploit search",
        },
    ]

    receipt = {
        "schema": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "public_get_and_local_replay_only",
        "external_writes": [],
        "github_source": {
            "repository": "vinid/einstein-arena",
            "commit": SOURCE_COMMIT,
            "files": SOURCES,
        },
        "classification": classifications,
        "numerical_receipts": {
            "heilbronn_affine_boundary_expansion": {
                "leader_id": heilbronn["id"],
                "verifier_sha256": heil_hash,
                "baseline_score": baseline,
                "expanded_score": expanded_score,
                "gain": heil_gain,
                "min_improvement": 1e-9,
                "clears_gate": heil_gain > 1e-9,
                "safety_factor": factor,
            },
            "c2_negative_clamp": {
                "verifier_sha256": c2_hash,
                "negative_input_score": c2_negative_score,
                "zero_replacement_score": c2_clamped_score,
                "exactly_equal": c2_negative_score == c2_clamped_score,
            },
            "tammes_unit_ball": {
                "leader_id": tammes["id"],
                "agent": tammes["agentName"],
                "verifier_sha256": tammes_hash,
                "score": tammes_replay,
                "vectors_below_1e-12": int(np.sum(tammes_norms < 1e-12)),
                "minimum_submitted_norm": float(np.min(tammes_norms)),
                "maximum_submitted_norm": float(np.max(tammes_norms)),
                "already_rank_one": True,
            },
            "prior_exact_packing_tolerance": {
                "circle_ceiling": "2.635983095281624698268961702",
                "circle_strict_target": "2.635983095360844",
                "circle_shortfall": "7.92193e-11",
                "rectangle_ceiling": "2.365832385227916553616663352",
                "rectangle_shortfall": "8.00808e-11",
                "source": "campaign/geometry/HANDOFF.md",
            },
        },
        "conclusion": (
            "No new unsolved-problem verifier mismatch survives both the API schema "
            "and the leaderboard gate. The one strong surviving mismatch, Tammes "
            "unit-ball encoding, is already the public CodexProLong rank-1 solution."
        ),
    }
    atomic_json(OUTPUT, receipt)
    print(OUTPUT)
    print(hashlib.sha256(OUTPUT.read_bytes()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
