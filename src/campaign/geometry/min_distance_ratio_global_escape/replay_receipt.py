#!/usr/bin/env python3
"""Read-only, fresh-process replay of the frozen FINAL_V2 frontier.

This script deliberately does not import the search program.  It validates the
frozen bytes, audits the append-only event journal, and asks a new isolated
Python process to evaluate the retained payload with the unchanged verifier.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
RUN = HERE / "runs/FINAL_V2"
VERIFIER = (
    CAMPAIGN
    / "state/problems/min-distance-ratio-2d/"
    "2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad.py"
)
CORPUS = CAMPAIGN / "research_corpus/snapshots/20260815T003306Z/corpus.sqlite3"

LEADER = 12.889229907717521
GATE = 1e-7
STRICT_TARGET = 12.889229807717522

EXPECTED_HASHES = {
    "adjacent_topology_escape.py": "9f2106e9212a945e3cc02330c182bdc1807e2ef66841dedb38af70d931ecc342",
    "assets.json": "38a1af0538bbc5c41b0e0238af0c0265cd7da13cce260217e920728687f34941",
    "runs/FINAL_V2/best.json": "f9e6d812a4545651905bb2589c3b4cc01306727439d8a046fb673b9b8f721b9f",
    "runs/FINAL_V2/corpus_audit.json": "944eccb65d088794ef339dfc56a28a8f77300399dd8ed036d96dd0a3b93fe30b",
    "runs/FINAL_V2/events.jsonl": "5c7876f9db83ec923a51664db36ee5682cdf81bd3dcbdf6b556581465304c46a",
    "runs/FINAL_V2/reconstructed_assets.json": "f801ac52472b5f45be51f4cafea14175cdd6589296e4ddb6e23f2e598d762501",
    "runs/FINAL_V2/summary.json": "9a3ac03edc6335bb8b806670645310fc830774d167874cac799491ab4192180f",
}
VERIFIER_SHA256 = "2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad"
CORPUS_SHA256 = "9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def fresh_process_score(payload_path: Path) -> float:
    program = r'''import json
import sys
from pathlib import Path

verifier_path = Path(sys.argv[1])
payload_path = Path(sys.argv[2])
namespace = {}
source = verifier_path.read_text(encoding="utf-8")
exec(compile(source, str(verifier_path), "exec"), namespace)
payload = json.loads(payload_path.read_text(encoding="utf-8"))
print(json.dumps({"score": namespace["evaluate"](payload)}, allow_nan=False))
'''
    completed = subprocess.run(
        [sys.executable, "-I", "-c", program, str(VERIFIER), str(payload_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(json.loads(completed.stdout)["score"])


def audit() -> dict[str, Any]:
    observed_hashes = {
        relative: sha256_file(HERE / relative) for relative in EXPECTED_HASHES
    }
    require(observed_hashes == EXPECTED_HASHES, "frozen lane artifact hash drift")
    require(sha256_file(VERIFIER) == VERIFIER_SHA256, "frozen verifier hash drift")
    require(sha256_file(CORPUS) == CORPUS_SHA256, "retained corpus hash drift")

    summary = load_json(RUN / "summary.json")
    payload = load_json(RUN / "best.json")
    corpus_audit = load_json(RUN / "corpus_audit.json")
    recovered = load_json(RUN / "reconstructed_assets.json")

    require(len(payload) == 1 and "vectors" in payload, "unexpected payload schema")
    require(len(payload["vectors"]) == 16, "payload does not contain 16 points")
    require(
        all(isinstance(row, list) and len(row) == 2 for row in payload["vectors"]),
        "payload is not 16 two-dimensional vectors",
    )
    score = fresh_process_score(RUN / "best.json")
    require(score == 12.889229907694041, "fresh-process verifier score changed")

    events = [
        json.loads(line)
        for line in (RUN / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    counts = Counter(event.get("event") for event in events)
    require(
        counts == {"assets_reconstructed": 1, "candidate_replayed": 214, "checkpoint": 5},
        "append-only event journal counts changed",
    )
    candidates = [event for event in events if event["event"] == "candidate_replayed"]
    require([event["index"] for event in candidates] == list(range(214)), "candidate index gap")
    require(all(math.isfinite(event["official_score"]) for event in candidates), "nonfinite score")
    require(not any(event["gate_clearing"] for event in candidates), "unexpected gate clearer")
    best_candidate = min(candidates, key=lambda event: event["official_score"])
    novel_candidates = [event for event in candidates if not event["matches_retained_signature"]]
    best_novel = min(novel_candidates, key=lambda event: event["official_score"])

    require(best_candidate["index"] == 130, "best candidate identity changed")
    require(best_candidate["official_score"] == score, "payload/candidate score mismatch")
    require(best_novel["index"] == 55, "best corpus-novel candidate identity changed")
    require(best_novel["official_score"] == 12.894999598753586, "novel frontier changed")

    expected_summary = {
        "run_id": "FINAL_V2",
        "leader": LEADER,
        "gate": GATE,
        "strict_target": STRICT_TARGET,
        "candidate_count": 214,
        "method_counts": {
            "n14_birth2": 12,
            "n15_birth1": 32,
            "n17_delete1": 17,
            "n18_delete2": 153,
        },
        "distinct_ranked_endpoint_signatures": 155,
        "endpoint_signatures_absent_from_retained_corpus_count": 153,
        "endpoint_signature_set_sha256": "5b737befe247e4630fc3ee1888b8184ed6797536a99dacf3ee2f605062765344",
        "novel_endpoint_signature_set_sha256": "9dcf1432f9d7acfa51106ae1f90d7adfa1bdee2746251ce4e9ff370fa09f90f3",
        "best_official_score": score,
        "improvement_over_leader": 2.347988470319251e-11,
        "shortfall_to_strict_target": 9.997651950754971e-8,
        "gate_clearing": False,
        "best_payload_sha256": EXPECTED_HASHES["runs/FINAL_V2/best.json"],
        "events_sha256": EXPECTED_HASHES["runs/FINAL_V2/events.jsonl"],
    }
    for key, expected in expected_summary.items():
        require(summary.get(key) == expected, f"summary field changed: {key}")
    require(
        summary["best_endpoint_absent_from_retained_corpus"]
        == {
            "index": 55,
            "method": "n18_delete2",
            "operation": {"deleted": [2, 8]},
            "official_score": 12.894999598753586,
            "ranked_signature": "cac2cd4ff02ed5fc5e87d2e97997c2902a7790f9a1f120736aa9241676272035",
            "threshold_signature": "649f2a039186a5788f0bc99208f3af429909a8a612717de3a27e775fcf9b215d",
        },
        "best corpus-novel summary record changed",
    )
    require(
        summary["n16_published_diagram_duplicate"]["minimum_graph_isomorphic"] is True,
        "published n=16 graph duplicate result changed",
    )

    require(corpus_audit["solution_count"] == 16, "corpus solution count changed")
    require(corpus_audit["thread_count"] == 29, "corpus thread count changed")
    require(corpus_audit["reply_count"] == 167, "corpus reply count changed")
    require(
        corpus_audit["maximum_stored_vs_replayed_score_delta"] == 0.0,
        "stored corpus scores no longer replay exactly",
    )
    recovered_scores = {
        key: value["score"] for key, value in recovered["reports"].items()
    }
    require(
        recovered_scores
        == {
            "14": 10.994717905673031,
            "15": 12.038438277928686,
            "17": 14.090518704772544,
            "18": 14.725276091685885,
        },
        "adjacent-cardinality reconstruction scores changed",
    )

    return {
        "status": "verified_bounded_negative_frontier",
        "fresh_process_verifier_score": score,
        "leader": LEADER,
        "strict_target": STRICT_TARGET,
        "gate_clearing": score < STRICT_TARGET,
        "shortfall_to_strict_target": score - STRICT_TARGET,
        "candidate_count": len(candidates),
        "event_counts": dict(sorted(counts.items())),
        "distinct_ranked_endpoint_signatures": summary["distinct_ranked_endpoint_signatures"],
        "corpus_novel_ranked_endpoint_signatures": summary[
            "endpoint_signatures_absent_from_retained_corpus_count"
        ],
        "best_corpus_novel_endpoint": summary[
            "best_endpoint_absent_from_retained_corpus"
        ],
        "n16_published_minimum_graph_isomorphic_to_leader": True,
        "hashes": {
            **observed_hashes,
            "frozen_verifier": VERIFIER_SHA256,
            "retained_corpus": CORPUS_SHA256,
        },
    }


def main() -> int:
    print(json.dumps(audit(), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
