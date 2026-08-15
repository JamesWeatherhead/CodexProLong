#!/usr/bin/env python3
"""Network-free replay of the frozen C3 Fourier/Newton publication packet.

The default path uses only packet-contained text and the Python standard
library.  ``--with-private-input`` additionally authenticates and FFT-replays
the excluded baseline array and verifier file when the private campaign tree
is available.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/20260815T124000Z"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path.name}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def require_close(actual: float, expected: float, message: str) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=5e-15):
        raise RuntimeError(f"{message}: expected {expected!r}, got {actual!r}")


def verify_receipt_files(receipt: dict[str, Any]) -> None:
    publication_files = receipt.get("publication_files")
    require(isinstance(publication_files, dict), "receipt publication file map missing")
    for relative, expected in publication_files.items():
        require(isinstance(relative, str) and isinstance(expected, str), "bad file map")
        rel = Path(relative)
        require(not rel.is_absolute() and ".." not in rel.parts, "unsafe receipt path")
        path = HERE / rel
        require(path.is_file(), f"publication file missing: {relative}")
        require(sha256_file(path) == expected, f"publication hash drift: {relative}")


def load_events(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        require(bool(line), f"blank event line {line_number}")
        value = json.loads(line)
        require(isinstance(value, dict), f"event line {line_number} is not an object")
        rows.append(value)
    return rows


def verify_frozen_run() -> dict[str, Any]:
    receipt = load_json(HERE / "receipt.json")
    config = load_json(RUN / "config.json")
    summary = load_json(RUN / "summary.json")
    corpus = load_json(HERE / "corpus_audit.json")
    events = load_events(RUN / "events.jsonl")

    require(receipt.get("status") == "bounded_no_gate", "unexpected receipt status")
    require(summary.get("status") == "bounded_no_gate", "unexpected summary status")
    require(not bool(receipt["bounded_search"]["gate_cleared"]), "receipt clears gate")
    require(not bool(summary["gate_cleared"]), "summary clears gate")
    require(receipt.get("external_mutations") == [], "packet records external mutations")
    verify_receipt_files(receipt)

    require(sha256_file(RUN / "config.json") == summary["config_sha256"], "config hash drift")
    require(sha256_file(RUN / "events.jsonl") == summary["events_sha256"], "event hash drift")
    require(
        sha256_file(HERE / "fourier_dual_newton.py") == summary["source_sha256"],
        "search source hash drift",
    )

    require(len(events) == 12, "unexpected event count")
    require(events[0].get("event") == "config", "first event is not config")
    require({key: value for key, value in events[0].items() if key != "event"} == config,
            "event/config mismatch")
    cap_rows = [row for row in events if row.get("event") == "cap_square_projection"]
    branch_rows = [row for row in events if row.get("event") == "fourier_branch_screen"]
    newton_rows = [row for row in events if row.get("event") == "semismooth_newton"]
    require(len(cap_rows) == 6 and len(branch_rows) == 1 and len(newton_rows) == 4,
            "unexpected probe partition")
    require(
        [row["relative_cap_drop"] for row in cap_rows]
        == [3e-6, 1e-5, 3e-5, 1e-4, 3e-4, 1e-3],
        "cap schedule drift",
    )
    require(all(row["best_alpha"] == 0.0 and row["fft_gain"] == 0.0 for row in cap_rows),
            "coefficient-cap no-improvement claim drift")

    branch = branch_rows[0]
    require(branch["tested_candidates"] == 3980, "branch count drift")
    require(branch["frequency_pool"] == 1024, "branch frequency pool drift")
    require(branch["fft_gain"] == 0.0 and branch["alpha"] == 0.0,
            "branch no-improvement claim drift")
    require(
        [row["beta"] for row in newton_rows] == [3e9, 1e10, 3e10, 1e11],
        "Newton beta schedule drift",
    )
    require(all(row["hessian_vector_products"] == 45 for row in newton_rows),
            "Newton product budget drift")
    require(all(row["cg_info"] == 45 for row in newton_rows),
            "Newton bounded/nonconverged status drift")

    target = float(config["live_leader"]) - float(config["minimum_improvement"])
    require_close(config["strict_target"], target, "strict target drift")
    require_close(summary["strict_target"], target, "summary target drift")
    remaining = float(config["official_baseline_score"]) - target
    require_close(summary["remaining_gate_gap"], remaining, "remaining gate gap drift")

    screen_scores = [float(row["best_fft_score"]) for row in cap_rows]
    screen_scores.append(float(branch["best_fft_score"]))
    screen_scores.extend(float(row["best_fft_score"]) for row in newton_rows)
    best_score = min(screen_scores)
    best_gain = float(summary["baseline_fft_score"]) - best_score
    maximum_newton_gain = max(float(row["fft_gain"]) for row in newton_rows)
    require_close(summary["best_fft_screen_score"], best_score, "best FFT score drift")
    require_close(summary["best_fft_screen_gain"], best_gain, "best FFT gain drift")
    require_close(summary["maximum_newton_fft_gain"], maximum_newton_gain,
                  "maximum Newton gain drift")
    require(summary["cap_projection_trials"] == len(cap_rows), "cap count drift")
    require(summary["fourier_branch_candidates"] == branch["tested_candidates"],
            "branch summary count drift")
    require(summary["newton_systems"] == len(newton_rows), "Newton count drift")
    require(best_score > target, "event log unexpectedly clears the strict gate")

    require(receipt["verifier_sha256"] == config["verifier_sha256"], "verifier pin drift")
    require(receipt["baseline"]["artifact_sha256"] == config["input_artifact_sha256"],
            "baseline artifact pin drift")
    require(receipt["baseline"]["values_float64_sha256"] == config["input_values_float64_sha256"],
            "baseline value pin drift")
    require_close(receipt["baseline"]["official_score"], config["official_baseline_score"],
                  "official baseline drift")
    require(receipt["corpus"] == corpus["corpus"], "corpus receipt drift")
    require(corpus["corpus"]["all_c3_constructions_read"] == 40, "construction count drift")
    require(corpus["corpus"]["all_c3_threads_read"] == 20, "thread count drift")
    require(corpus["corpus"]["all_c3_replies_read"] == 97, "reply count drift")
    require(all("values" not in item and "agent_name" not in item and "created_at" not in item
                for item in corpus["constructions"]), "corpus publication minimization drift")
    require_close(receipt["bounded_search"]["best_fft_screen_gain"],
                  summary["best_fft_screen_gain"], "receipt best gain drift")
    require_close(receipt["bounded_search"]["maximum_newton_fft_gain"],
                  summary["maximum_newton_fft_gain"], "receipt Newton gain drift")

    return {
        "status": "ok",
        "publication_files": len(receipt["publication_files"]),
        "event_rows": len(events),
        "cap_projection_trials": len(cap_rows),
        "fourier_branch_candidates": branch["tested_candidates"],
        "newton_systems": len(newton_rows),
        "best_fft_screen_gain": summary["best_fft_screen_gain"],
        "maximum_newton_fft_gain": summary["maximum_newton_fft_gain"],
        "remaining_gate_gap": summary["remaining_gate_gap"],
        "gate_cleared": False,
        "private_input_replayed": False,
    }


def replay_private_input(campaign_root: Path, report: dict[str, Any]) -> None:
    # Imported lazily so the default publication replay remains stdlib-only.
    import numpy as np
    from scipy.fft import irfft, next_fast_len, rfft

    receipt = load_json(HERE / "receipt.json")
    baseline = campaign_root / receipt["baseline"]["path"]
    verifier = (
        campaign_root
        / "state/problems/third-autocorrelation-inequality"
        / f"{receipt['verifier_sha256']}.py"
    )
    require(baseline.is_file(), f"private baseline missing: {baseline}")
    require(verifier.is_file(), f"hash-pinned verifier missing: {verifier}")
    require(sha256_file(baseline) == receipt["baseline"]["artifact_sha256"],
            "private baseline artifact hash drift")
    require(sha256_file(verifier) == receipt["verifier_sha256"], "private verifier hash drift")
    values = np.load(baseline, allow_pickle=False).astype(np.float64)
    require(hashlib.sha256(values.tobytes()).hexdigest()
            == receipt["baseline"]["values_float64_sha256"], "private value hash drift")
    require(values.ndim == 1 and len(values) == receipt["baseline"]["n"],
            "private baseline shape drift")
    require(bool(np.isfinite(values).all()), "private baseline is non-finite")
    values /= float(np.sum(values))
    length = next_fast_len(2 * len(values) - 1)
    spectrum = rfft(values, length)
    convolution = irfft(spectrum * spectrum, length)[: 2 * len(values) - 1]
    fft_score = float(2.0 * len(values) * np.max(convolution))
    require_close(fft_score, receipt["baseline"]["official_score"],
                  "private baseline FFT score drift")
    report["private_input_replayed"] = True
    report["private_baseline_fft_score"] = fft_score
    report["private_verifier_sha256"] = receipt["verifier_sha256"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-private-input",
        action="store_true",
        help="also authenticate and FFT-replay excluded campaign inputs",
    )
    parser.add_argument(
        "--campaign-root",
        type=Path,
        help="campaign directory containing analytic/, state/, and research_corpus/",
    )
    args = parser.parse_args()
    report = verify_frozen_run()
    if args.with_private_input:
        campaign_root = (args.campaign_root or HERE.parents[1]).resolve()
        replay_private_input(campaign_root, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
