#!/usr/bin/env python3
"""Offline exact audit of EinsteinArena kissing-number-d11 solution 1492.

The default mode is fully offline: it extracts the public solution from the
frozen exhaustive corpus, writes a standalone payload, replays the frozen
verifier, checks the kissing inequalities over Q, and inventories every public
solution/thread/reply in that corpus.  ``--refresh-live`` additionally performs
GET-only requests to freeze current leaderboard and ranking-policy evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORPUS = ROOT / "campaign/research_corpus/snapshots/20260815T003306Z/corpus.sqlite3"
VERIFIER = (
    ROOT
    / "campaign/state/problems/kissing-number-d11/"
    "3f62786f20e351f8cfef68538867f29a573d9fe20fc8a5e1428a55035a4bc5a3.py"
)
PROBLEM_ID = 6
SOLUTION_ID = 1492
EXPECTED_AGENT = "KawaiiCorgi"
EXPECTED_RECORD_SHA256 = "a1921fc7e26323d603cb267a4837689b3361d0f4481a3073ec3042ae44503bc0"
EXPECTED_CORPUS_SHA256 = "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"
EXPECTED_VERIFIER_SHA256 = "3f62786f20e351f8cfef68538867f29a573d9fe20fc8a5e1428a55035a4bc5a3"
ARENA_BASE = "https://einsteinarena.com"
ARENA_SOURCE_COMMIT = "98073fca26654d048d70acdfe1e319a23e8e41c6"
ARENA_ROUTE_URL = (
    "https://raw.githubusercontent.com/vinid/einstein-arena/"
    f"{ARENA_SOURCE_COMMIT}/web/src/app/api/leaderboard/route.ts"
)
USER_AGENT = "Codex-read-only-kissing-d11-audit/1.0"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8") + b"\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def fraction_text(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def lexical_record(raw: str) -> dict[str, Any]:
    return json.loads(raw, parse_float=Decimal, parse_int=int)


def fraction_vectors(record: dict[str, Any]) -> list[list[Fraction]]:
    return [[Fraction(value) for value in row] for row in record["data"]["vectors"]]


def import_verifier(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("kissing_d11_frozen_verifier", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import verifier {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_geometry(vectors: list[list[Fraction]]) -> dict[str, Any]:
    if len(vectors) != 594 or {len(row) for row in vectors} != {11}:
        raise AssertionError("payload is not 594 x 11")
    tuples = [tuple(row) for row in vectors]
    if len(set(tuples)) != len(tuples):
        raise AssertionError("duplicate vectors")

    norms = [sum(value * value for value in row) for row in vectors]
    if min(norms) <= 0:
        raise AssertionError("zero vector")

    max_norm = max(norms)
    min_distance: Fraction | None = None
    min_distance_pairs: list[tuple[int, int]] = []
    positive_pairs = 0
    normalized_contacts: list[tuple[int, int]] = []
    normalized_violations: list[tuple[int, int]] = []
    max_cosine_squared = Fraction(-1)
    max_cosine_pair: tuple[int, int] | None = None

    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            dot = sum(a * b for a, b in zip(vectors[i], vectors[j]))
            distance = norms[i] + norms[j] - 2 * dot
            if min_distance is None or distance < min_distance:
                min_distance = distance
                min_distance_pairs = [(i, j)]
            elif distance == min_distance:
                min_distance_pairs.append((i, j))

            # For positive dot products, cos(theta) <= 1/2 is exactly
            # equivalent to 4 dot^2 <= ||v_i||^2 ||v_j||^2.  Nonpositive
            # dot products satisfy the kissing inequality automatically.
            if dot > 0:
                positive_pairs += 1
                lhs = 4 * dot * dot
                rhs = norms[i] * norms[j]
                if lhs > rhs:
                    normalized_violations.append((i, j))
                elif lhs == rhs:
                    normalized_contacts.append((i, j))
                cosine_squared = dot * dot / rhs
                if cosine_squared > max_cosine_squared:
                    max_cosine_squared = cosine_squared
                    max_cosine_pair = (i, j)

    assert min_distance is not None
    if normalized_violations:
        raise AssertionError(f"normalized kissing violations: {normalized_violations[:5]}")
    if min_distance < max_norm:
        raise AssertionError("raw AlphaEvolve-lemma inequality fails")
    if max_cosine_squared != Fraction(1, 4):
        raise AssertionError(f"unexpected max positive cosine squared: {max_cosine_squared}")

    vector_set = set(tuples)
    antipodal_pairs = sum(
        tuple(-value for value in row) in vector_set for row in tuples
    ) // 2
    integer_rows = [all(value.denominator == 1 for value in row) for row in vectors]
    axis_rows = sum(
        is_integer
        and norms[index] == 4
        and sum(value != 0 for value in row) == 1
        for index, (row, is_integer) in enumerate(zip(vectors, integer_rows))
    )
    type_b_rows = sum(
        is_integer
        and norms[index] == 4
        and sum(value != 0 for value in row) == 4
        and all(value in (-1, 0, 1) for value in row)
        for index, (row, is_integer) in enumerate(zip(vectors, integer_rows))
    )

    return {
        "antipodal_pairs": antipodal_pairs,
        "axis_rows_pm2": axis_rows,
        "distinct_vectors": len(vector_set),
        "exact_norm_squared_4_rows": sum(norm == 4 for norm in norms),
        "integer_rows": sum(integer_rows),
        "max_norm_squared": fraction_text(max_norm),
        "max_positive_cosine": "1/2",
        "max_positive_cosine_pair_zero_based": list(max_cosine_pair or ()),
        "max_positive_cosine_squared": fraction_text(max_cosine_squared),
        "min_norm_squared": fraction_text(min(norms)),
        "min_raw_pair_distance_squared": fraction_text(min_distance),
        "min_raw_pair_distance_pair_count": len(min_distance_pairs),
        "min_raw_pair_distance_pairs_first_20_zero_based": [
            list(pair) for pair in min_distance_pairs[:20]
        ],
        "minimum_normalized_center_distance_squared": "4",
        "noninteger_rows": len(vectors) - sum(integer_rows),
        "normalized_contact_pair_count": len(normalized_contacts),
        "normalized_violation_pair_count": len(normalized_violations),
        "positive_inner_product_pair_count": positive_pairs,
        "raw_lemma_margin_squared": fraction_text(min_distance - max_norm),
        "shape": [len(vectors), len(vectors[0])],
        "type_b_rows_four_pm1": type_b_rows,
    }


def corpus_inventory(database: sqlite3.Connection) -> dict[str, Any]:
    solution_rows = database.execute(
        """SELECT id, agent_name, score, created_at, record_sha256, record_json
           FROM solutions WHERE problem_id = ? ORDER BY id""",
        (PROBLEM_ID,),
    ).fetchall()
    solutions: list[dict[str, Any]] = []
    zero_solution_ids: list[int] = []
    for solution_id, agent, score, created_at, record_sha256, raw in solution_rows:
        parsed = json.loads(raw)
        if sha256_bytes(canonical_json(parsed)) != record_sha256:
            raise AssertionError(f"bad solution record hash: {solution_id}")
        rows = parsed.get("data", {}).get("vectors")
        if not isinstance(rows, list):
            raise AssertionError(f"missing vectors in solution {solution_id}")
        widths = sorted({len(row) for row in rows if isinstance(row, list)})
        shape = [len(rows), widths[0] if len(widths) == 1 else widths]
        if shape != [594, 11]:
            raise AssertionError(f"bad shape in solution {solution_id}: {shape}")
        if score == 0:
            zero_solution_ids.append(int(solution_id))
        solutions.append(
            {
                "agent_name": agent,
                "created_at": created_at,
                "id": int(solution_id),
                "record_sha256": record_sha256,
                "score": score,
                "shape": shape,
            }
        )

    thread_rows = database.execute(
        """SELECT id, agent_name, title, body, created_at, reply_count,
                  record_sha256, record_json
           FROM threads WHERE problem_id = ? ORDER BY id""",
        (PROBLEM_ID,),
    ).fetchall()
    threads: list[dict[str, Any]] = []
    replies: list[dict[str, Any]] = []
    for thread_id, agent, title, body, created_at, reply_count, record_sha256, raw in thread_rows:
        if sha256_bytes(canonical_json(json.loads(raw))) != record_sha256:
            raise AssertionError(f"bad thread record hash: {thread_id}")
        reply_rows = database.execute(
            """SELECT id, parent_reply_id, agent_name, body, created_at,
                      record_sha256, record_json
               FROM replies WHERE thread_id = ? ORDER BY id""",
            (thread_id,),
        ).fetchall()
        if len(reply_rows) != int(reply_count):
            raise AssertionError(
                f"thread {thread_id} declared {reply_count} replies but corpus has {len(reply_rows)}"
            )
        threads.append(
            {
                "agent_name": agent,
                "body_bytes_utf8": len(body.encode("utf-8")),
                "body_sha256": sha256_bytes(body.encode("utf-8")),
                "created_at": created_at,
                "id": int(thread_id),
                "record_sha256": record_sha256,
                "reply_count": int(reply_count),
                "title": title,
            }
        )
        for reply_id, parent_reply_id, reply_agent, reply_body, reply_created_at, reply_sha, reply_raw in reply_rows:
            if sha256_bytes(canonical_json(json.loads(reply_raw))) != reply_sha:
                raise AssertionError(f"bad reply record hash: {reply_id}")
            replies.append(
                {
                    "agent_name": reply_agent,
                    "body_bytes_utf8": len(reply_body.encode("utf-8")),
                    "body_sha256": sha256_bytes(reply_body.encode("utf-8")),
                    "created_at": reply_created_at,
                    "id": int(reply_id),
                    "parent_reply_id": parent_reply_id,
                    "record_sha256": reply_sha,
                    "thread_id": int(thread_id),
                }
            )

    leaderboard = [
        {
            "agent_name": row[1],
            "best_score": row[2],
            "rank": int(row[0]),
            "submissions": int(row[3]),
        }
        for row in database.execute(
            """SELECT rank, agent_name, best_score, submissions
               FROM leaderboard WHERE problem_id = ? ORDER BY rank""",
            (PROBLEM_ID,),
        )
    ]
    if zero_solution_ids != [SOLUTION_ID]:
        raise AssertionError(f"unexpected score-zero solution set: {zero_solution_ids}")
    if len(solutions) != 99 or len(threads) != 25 or len(replies) != 86:
        raise AssertionError(
            f"unexpected corpus counts: {len(solutions)}, {len(threads)}, {len(replies)}"
        )
    return {
        "corpus_sha256": sha256_file(CORPUS),
        "leaderboard_snapshot": leaderboard,
        "problem_id": PROBLEM_ID,
        "replies": replies,
        "reply_count": len(replies),
        "solutions": solutions,
        "solution_count": len(solutions),
        "threads": threads,
        "thread_count": len(threads),
        "zero_score_solution_ids": zero_solution_ids,
    }


def http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.status != 200:
            raise RuntimeError(f"GET {url}: HTTP {response.status}")
        return response.read()


def live_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    def get_json(path: str) -> tuple[Any, str, str]:
        raw = http_get(ARENA_BASE + path)
        value = json.loads(raw)
        return value, sha256_bytes(raw), sha256_bytes(canonical_json(value))

    problem, problem_raw_sha, problem_canonical_sha = get_json(
        "/api/problems/kissing-number-d11"
    )
    d11_board, d11_board_raw_sha, d11_board_canonical_sha = get_json(
        "/api/leaderboard?problem_id=6&limit=100"
    )
    d11_best, d11_best_raw_sha, d11_best_canonical_sha = get_json(
        "/api/solutions/best?problem_id=6&limit=1"
    )
    min_ratio_board, min_ratio_raw_sha, min_ratio_canonical_sha = get_json(
        "/api/leaderboard?problem_id=5&limit=10"
    )
    thomson_board, thomson_raw_sha, thomson_canonical_sha = get_json(
        "/api/leaderboard?problem_id=10&limit=10"
    )
    route_source = http_get(ARENA_ROUTE_URL)
    route_text = route_source.decode("utf-8")

    if problem["id"] != PROBLEM_ID:
        raise AssertionError("live problem id changed")
    if sha256_bytes(problem["verifier"].encode("utf-8")) != EXPECTED_VERIFIER_SHA256:
        raise AssertionError("live verifier changed")
    if not d11_best or d11_best[0]["id"] != SOLUTION_ID:
        raise AssertionError("live public best is no longer solution 1492")
    if sha256_bytes(canonical_json(d11_best[0])) != EXPECTED_RECORD_SHA256:
        raise AssertionError("live solution record differs from frozen corpus record")
    if canonical_json(d11_best[0]["data"]) != canonical_json(payload):
        raise AssertionError("live solution payload differs from extracted payload")
    if d11_board[0]["rank"] != 1 or d11_board[0]["bestScore"] != 0:
        raise AssertionError("unexpected d11 leaderboard head")
    if [row["rank"] for row in min_ratio_board[:2]] != [1, 2]:
        raise AssertionError("unexpected min-distance ranks")
    if min_ratio_board[0]["bestScore"] != min_ratio_board[1]["bestScore"]:
        raise AssertionError("min-distance live leaders are no longer exactly tied")
    if [row["rank"] for row in thomson_board[:3]] != [1, 2, 3]:
        raise AssertionError("unexpected Thomson ranks")
    if len({row["bestScore"] for row in thomson_board[:3]}) != 1:
        raise AssertionError("Thomson live leaders are no longer exactly tied")
    if "rank: i + 1" not in route_text:
        raise AssertionError("leaderboard source no longer assigns ordinal index ranks")
    if "score ASC, evaluated_at ASC" not in route_text:
        raise AssertionError("leaderboard tie-break source changed")

    return {
        "arena_base": ARENA_BASE,
        "conclusion": {
            "equal_scores_receive_joint_rank_1": False,
            "reason": (
                "The GET route unconditionally maps sorted result index i to rank i+1; "
                "live exact best-score ties receive ranks 1,2 (and 1,2,3)."
            ),
            "score_zero_tie_currently_observed": False,
        },
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "kissing_d11": {
            "best_solution_canonical_sha256": d11_best_canonical_sha,
            "best_solution_raw_response_sha256": d11_best_raw_sha,
            "leaderboard": d11_board,
            "leaderboard_canonical_sha256": d11_board_canonical_sha,
            "leaderboard_raw_response_sha256": d11_board_raw_sha,
            "problem_canonical_sha256": problem_canonical_sha,
            "problem_raw_response_sha256": problem_raw_sha,
            "solution_1492_record_sha256": EXPECTED_RECORD_SHA256,
        },
        "ranking_source": {
            "commit": ARENA_SOURCE_COMMIT,
            "license": "MIT",
            "route_sha256": sha256_bytes(route_source),
            "url": ARENA_ROUTE_URL,
            "verified_tokens": ["rank: i + 1", "score ASC, evaluated_at ASC"],
        },
        "tied_best_examples": [
            {
                "leaderboard_canonical_sha256": min_ratio_canonical_sha,
                "leaderboard_raw_response_sha256": min_ratio_raw_sha,
                "problem_id": 5,
                "rows": min_ratio_board[:2],
                "slug": "min-distance-ratio-2d",
            },
            {
                "leaderboard_canonical_sha256": thomson_canonical_sha,
                "leaderboard_raw_response_sha256": thomson_raw_sha,
                "problem_id": 10,
                "rows": thomson_board[:3],
                "slug": "thomson-problem",
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-live",
        action="store_true",
        help="GET current Arena/API and pinned GitHub source evidence (never writes remotely)",
    )
    args = parser.parse_args()

    if sha256_file(CORPUS) != EXPECTED_CORPUS_SHA256:
        raise AssertionError("frozen corpus hash changed")
    if sha256_file(VERIFIER) != EXPECTED_VERIFIER_SHA256:
        raise AssertionError("frozen verifier hash changed")

    database = sqlite3.connect(CORPUS)
    try:
        row = database.execute(
            """SELECT agent_name, score, created_at, record_sha256, record_json
               FROM solutions WHERE id = ? AND problem_id = ?""",
            (SOLUTION_ID, PROBLEM_ID),
        ).fetchone()
        if row is None:
            raise AssertionError("solution 1492 missing from frozen corpus")
        agent, recorded_score, created_at, record_sha256, raw_record = row
        if agent != EXPECTED_AGENT or recorded_score != 0:
            raise AssertionError("unexpected source solution metadata")
        if record_sha256 != EXPECTED_RECORD_SHA256:
            raise AssertionError("unexpected source record hash")

        numeric_record = json.loads(raw_record)
        lexical = lexical_record(raw_record)
        if sha256_bytes(canonical_json(numeric_record)) != record_sha256:
            raise AssertionError("source record canonical hash does not replay")
        payload = numeric_record["data"]
        vectors = fraction_vectors(lexical)
        exact = exact_geometry(vectors)
        inventory = corpus_inventory(database)
    finally:
        database.close()

    # Prove that the standalone numeric JSON round-trip retains every exact
    # decimal coordinate from the archived lexical representation.
    standalone_roundtrip = json.loads(
        json.dumps(payload, ensure_ascii=False, allow_nan=False),
        parse_float=Decimal,
        parse_int=int,
    )
    if fraction_vectors({"data": standalone_roundtrip}) != vectors:
        raise AssertionError("standalone payload changed an exact coordinate")

    payload_path = HERE / "payload.json"
    manifest_path = HERE / "corpus_manifest.json"
    live_path = HERE / "live_api_evidence.json"
    receipt_path = HERE / "receipt.json"
    atomic_json(payload_path, payload)
    atomic_json(manifest_path, inventory)

    verifier = import_verifier(VERIFIER)
    loaded_payload = json.loads(payload_path.read_text(encoding="utf-8"))
    verifier_exact_check = bool(verifier._exact_check(loaded_payload["vectors"]))
    verifier_score = verifier.evaluate(loaded_payload)
    if not verifier_exact_check or verifier_score != 0.0:
        raise AssertionError(
            f"frozen verifier did not accept payload exactly: {verifier_exact_check}, {verifier_score}"
        )

    live: dict[str, Any] | None = None
    if args.refresh_live:
        live = live_evidence(payload)
        atomic_json(live_path, live)
    elif live_path.exists():
        live = json.loads(live_path.read_text(encoding="utf-8"))

    lexical_values = [value for row in lexical["data"]["vectors"] for value in row]
    receipt: dict[str, Any] = {
        "conclusion": {
            "domain_valid_exact_score_zero_construction_recovered": True,
            "recoverable_from": "public EinsteinArena best-solutions API / exhaustive corpus",
            "verifier_exploit": False,
        },
        "coordinate_tokens": {
            "decimal_tokens": sum(isinstance(value, Decimal) for value in lexical_values),
            "integer_tokens": sum(isinstance(value, int) for value in lexical_values),
            "total": len(lexical_values),
        },
        "corpus": {
            "manifest_path": str(manifest_path.relative_to(ROOT)),
            "manifest_sha256": sha256_file(manifest_path),
            "path": str(CORPUS.relative_to(ROOT)),
            "reply_count": inventory["reply_count"],
            "sha256": sha256_file(CORPUS),
            "solution_count": inventory["solution_count"],
            "thread_count": inventory["thread_count"],
            "zero_score_solution_ids": inventory["zero_score_solution_ids"],
        },
        "exact_geometry": exact,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "live_api_evidence": None,
        "payload": {
            "path": str(payload_path.relative_to(ROOT)),
            "sha256": sha256_file(payload_path),
        },
        "source_solution": {
            "agent_name": agent,
            "created_at": created_at,
            "id": SOLUTION_ID,
            "record_sha256": record_sha256,
            "recorded_score": recorded_score,
        },
        "verifier": {
            "exact_check": verifier_exact_check,
            "path": str(VERIFIER.relative_to(ROOT)),
            "score": verifier_score,
            "sha256": sha256_file(VERIFIER),
        },
    }
    if live is not None:
        receipt["live_api_evidence"] = {
            "conclusion": live["conclusion"],
            "fetched_at": live["fetched_at"],
            "path": str(live_path.relative_to(ROOT)),
            "sha256": sha256_file(live_path),
        }
    atomic_json(receipt_path, receipt)

    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"audit failed: {exc}", file=sys.stderr)
        raise
