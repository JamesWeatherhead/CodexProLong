#!/usr/bin/env python3
"""Export a deterministic, public-safe snapshot of the local campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
AGENT = "CodexProLong"
SOLUTION_IDS = {
    "tammes-problem": [2496, 2497],
    "kissing-number-d12-842": [2499],
    "kissing-number-d11-605": [2500],
    "first-autocorrelation-inequality": [2504],
    "uncertainty-principle": [2505],
}
DISCLOSURES = {"tammes-problem": "verifier/domain mismatch: one point is not on S^2"}
WIN_ARTIFACTS = {
    "kissing-number-d12-842": "geometry/runs/20260814T225047Z/kissing-number-d12-842/best.json",
    "kissing-number-d11-605": "geometry/runs/20260814T225229Z/kissing-number-d11-605/best.json",
    "first-autocorrelation-inequality": "c1_root/runs/20260814T232455Z/candidate.json",
    "uncertainty-principle": "analytic/payloads/uncertainty-k25-frozen-20260814T234458Z.json",
}
WIN_RECEIPTS = {
    "kissing-number-d12-842": "state/receipts/kissing-number-d12-842/20260814T225240418258Z-99b544b575ab.json",
    "kissing-number-d11-605": "state/receipts/kissing-number-d11-605/20260814T225509786111Z-89fad32eba9b.json",
    "first-autocorrelation-inequality": "state/receipts/first-autocorrelation-inequality/20260814T232734823043Z-e3f90379fb5a.json",
    "uncertainty-principle": "state/receipts/uncertainty-principle/20260814T234525289383Z-12590e6c26a7.json",
}
ROOT_SOURCE_FILES = (
    "AGENTS.md",
    "Dockerfile.verifier",
    "HANDOFF.md",
    "README.md",
    "arena",
    "arena_campaign.py",
    "verifier_runner.py",
    "tests/test_campaign.py",
)
SOURCE_EXTENSIONS = {".py", ".md", ".cpp", ".sh"}
SOURCE_FAMILIES = ("analytic", "c1_root", "c2_root", "c3_root", "discrete", "erdos_root", "geometry", "research_corpus")
EXCLUDED_PARTS = {"external", "runs", "snapshots", "receipts", "checkpoints", "__pycache__", ".ruff_cache"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def format_score(value: Any) -> str:
    if value is None:
        return "—"
    return format(float(value), ".16g")


def public_frontier(latest: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for slug, problem in sorted(latest["problems"].items()):
        ours = problem.get("our_entry")
        rows.append(
            {
                "slug": slug,
                "title": problem["title"],
                "scoring": problem["scoring"],
                "min_improvement": problem["minImprovement"],
                "leader": problem["leader"],
                "our_entry": ours,
                "our_rank": problem.get("our_rank"),
                "verifier_sha256": problem["verifier_sha256"],
                "problem_url": f"https://einsteinarena.com/problems/{slug}",
                "solution_ids": SOLUTION_IDS.get(slug, []),
                "integrity": "disclosure" if slug in DISCLOSURES else ("domain-valid" if problem.get("our_rank") == 1 else "active"),
                "disclosure": DISCLOSURES.get(slug),
            }
        )
    return {
        "agent": AGENT,
        "generated_at": latest["generated_at"],
        "platform_first_places": sum(row["our_rank"] == 1 for row in rows),
        "domain_valid_first_places": sum(row["our_rank"] == 1 and row["integrity"] == "domain-valid" for row in rows),
        "problems": rows,
    }


def status_markdown(frontier: dict[str, Any]) -> str:
    lines = [
        "# Live 19-benchmark matrix",
        "",
        f"Generated from the live Arena snapshot at `{frontier['generated_at']}`.",
        "",
        f"Platform first places: **{frontier['platform_first_places']}/19**. "
        f"Domain-valid first places: **{frontier['domain_valid_first_places']}/19**.",
        "",
        "| Benchmark | Direction | Live leader | Our rank / score | Gate | Verifier | Evidence | Literature |",
        "|---|:---:|---:|---:|---:|---|---|---|",
    ]
    for row in frontier["problems"]:
        arrow = "↑" if row["scoring"] == "maximize" else "↓"
        leader = row["leader"]
        leader_text = f"{leader['agentName']} `{format_score(leader['bestScore'])}` {arrow}"
        if row["our_entry"]:
            icon = "⚠️" if row["integrity"] == "disclosure" else "🥇"
            ours = f"{icon} **#{row['our_rank']}** / `{format_score(row['our_entry']['bestScore'])}`"
        else:
            ours = "— / active"
        verifier = f"`{row['verifier_sha256'][:12]}`"
        ids = row["solution_ids"]
        evidence = " · ".join(f"[#{sid}](https://einsteinarena.com/api/solutions/{sid})" for sid in ids) or "[lane source](../src/campaign/)"
        literature = f"[packet](LITERATURE.md#{row['slug']})"
        lines.append(
            f"| [{row['title']}]({row['problem_url']}) | {arrow} | {leader_text} | {ours} | "
            f"`{format_score(row['min_improvement'])}` | {verifier} | {evidence} | {literature} |"
        )
    lines.extend(
        [
            "",
            "> [!WARNING]",
            "> Tammes is a platform first place but not a spherical-code result; see [ETHICS.md](ETHICS.md).",
            "",
            "The source of truth is [`data/frontier.json`](../data/frontier.json).",
        ]
    )
    return "\n".join(lines) + "\n"


def sanitize_receipt(receipt: dict[str, Any], artifact_name: str) -> dict[str, Any]:
    clean = dict(receipt)
    clean["candidate_path"] = f"artifacts/wins/{artifact_name}"
    return clean


def mirror_source(source: Path) -> list[dict[str, Any]]:
    copied: list[dict[str, Any]] = []
    destination_root = REPO / "src" / "campaign"
    for relative_text in ROOT_SOURCE_FILES:
        relative = Path(relative_text)
        src = source / relative
        if src.exists():
            dst = destination_root / relative
            copy_file(src, dst)
            copied.append({"path": str(dst.relative_to(REPO)), "sha256": sha256(dst), "bytes": dst.stat().st_size})
    for family in SOURCE_FAMILIES:
        family_root = source / family
        if not family_root.exists():
            continue
        for src in sorted(family_root.rglob("*")):
            if not src.is_file() or src.suffix not in SOURCE_EXTENSIONS:
                continue
            relative = src.relative_to(source)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            dst = destination_root / relative
            copy_file(src, dst)
            copied.append({"path": str(dst.relative_to(REPO)), "sha256": sha256(dst), "bytes": dst.stat().st_size})
    return copied


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("../EinsteinArena/campaign"))
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    latest_path = source / "state" / "latest.json"
    if not latest_path.is_file():
        raise SystemExit(f"not a campaign checkout: {source}")
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    frontier = public_frontier(latest)
    write_json(REPO / "data" / "frontier.json", frontier)
    (REPO / "docs" / "STATUS.md").write_text(status_markdown(frontier), encoding="utf-8")

    manifest = mirror_source(source)
    for slug, relative_text in WIN_ARTIFACTS.items():
        src = source / relative_text
        suffix = src.suffix
        name = f"{slug}{suffix}"
        dst = REPO / "artifacts" / "wins" / name
        copy_file(src, dst)
        manifest.append({"path": str(dst.relative_to(REPO)), "sha256": sha256(dst), "bytes": dst.stat().st_size})

        receipt_src = source / WIN_RECEIPTS[slug]
        receipt = json.loads(receipt_src.read_text(encoding="utf-8"))
        receipt_dst = REPO / "artifacts" / "receipts" / f"{slug}.json"
        write_json(receipt_dst, sanitize_receipt(receipt, name))
        manifest.append({"path": str(receipt_dst.relative_to(REPO)), "sha256": sha256(receipt_dst), "bytes": receipt_dst.stat().st_size})

    events_src = source / "state" / "events.jsonl"
    events_dst = REPO / "artifacts" / "journal" / "events.jsonl"
    copy_file(events_src, events_dst)
    manifest.append({"path": str(events_dst.relative_to(REPO)), "sha256": sha256(events_dst), "bytes": events_dst.stat().st_size})

    manifest.sort(key=lambda item: item["path"])
    write_json(
        REPO / "data" / "published-manifest.json",
        {"generated_at": latest["generated_at"], "files": manifest},
    )
    print(
        f"snapshot OK: {frontier['platform_first_places']}/19 platform, "
        f"{frontier['domain_valid_first_places']}/19 domain-valid, {len(manifest)} mirrored files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

