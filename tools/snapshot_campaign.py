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
    "prime-number-theorem": [2506],
    "tammes-problem": [2496, 2497],
    "kissing-number-d12-842": [2499],
    "kissing-number-d11-605": [2500],
    "first-autocorrelation-inequality": [2504],
    "uncertainty-principle": [2505],
}
DISCLOSURES = {"tammes-problem": "verifier/domain mismatch: one point is not on S^2"}
NUMERICAL_CERTIFICATES = {
    "prime-number-theorem": (
        "full advertised verifier horizon checked exactly; the stronger all-x "
        "analytic PNT certificate remains open"
    )
}
VERIFIED_BLOCKED = {
    "kissing-number-d12": {
        "score": 0.0,
        "leader_score": 2.0,
        "candidate_sha256": "236d3931724d28cf306ecbda064c1ffb84e8a106e363227f00e6d5b147eb4749",
        "verifier_sha256": "eb043620439a6631451657013a12c66e55db43589431bcdad08e3b2189246ca8",
        "pair_count": 353_220,
        "exact_distance_margin": "1.2449713530886666648293011033664E-7",
        "source_repository": "https://github.com/k-nic/841_in_12D",
        "source_commit": "eba37f0368f62828780d1f9d90315b367d2a612f",
        "source_coordinate_sha256": "995264fe8be616cc546f04ef542dbf4ef6effe9ba5dfa4ceec1aa7e069f476a9",
        "paperclip_citation": "https://paperclip.gxl.ai/citations/papers/arx_2606.18984#L1",
        "submission_http_status": 409,
        "submission_error": "Submissions are disabled for this problem",
        "maintainer_issue": "https://github.com/vinid/einstein-arena/issues/59",
        "redistribution_note": "The upstream source has no license; this mirror publishes hashes and a reproducer, not the coordinate payload.",
    }
}
WIN_ARTIFACTS = {
    "prime-number-theorem": "discrete/prime_number_theorem/reach_extend_127849_fullrange.json",
    "kissing-number-d12-842": "geometry/runs/20260814T225047Z/kissing-number-d12-842/best.json",
    "kissing-number-d11-605": "geometry/runs/20260814T225229Z/kissing-number-d11-605/best.json",
    "first-autocorrelation-inequality": "c1_root/runs/20260814T232455Z/candidate.json",
    "uncertainty-principle": "analytic/payloads/uncertainty-k25-frozen-20260814T234458Z.json",
}
WIN_RECEIPTS = {
    "prime-number-theorem": "state/receipts/prime-number-theorem/20260815T032933818594Z-4082fb8c9b71.json",
    "kissing-number-d12-842": "state/receipts/kissing-number-d12-842/20260814T225240418258Z-99b544b575ab.json",
    "kissing-number-d11-605": "state/receipts/kissing-number-d11-605/20260814T225509786111Z-89fad32eba9b.json",
    "first-autocorrelation-inequality": "state/receipts/first-autocorrelation-inequality/20260814T232734823043Z-e3f90379fb5a.json",
    "uncertainty-principle": "state/receipts/uncertainty-principle/20260814T234525289383Z-12590e6c26a7.json",
}
FRONTIER_ARTIFACTS = {
    "circle-packing": "geometry/circle_packing_topology/runs/20260815T021013Z/topologies/1a3ddda1ed2e3083/candidate.json",
    "circles-rectangle": "geometry/rectangle_topology/runs/20260815T022200Z/stochastic_relax/topologies/cdea3037dafa48f9/candidate.json",
    "edges-vs-triangles": "discrete/edges_vs_triangles/runs/20260815T023100Z/global_dp/candidate.json",
    "erdos-min-overlap": "analytic/erdos_global/slp_runs/20260815T063000Z-n3584-trust25e5/best.json",
    "heilbronn-triangles": "geometry/runs/20260814T231710Z/heilbronn-triangles/best.json",
    "min-distance-ratio-2d": "geometry/runs/20260814T231106Z/min-distance-ratio-2d/best.json",
    "second-autocorrelation-inequality": "analytic/c2_global_topology/runs/20260815T041000Z-terminal-split/best.npy",
    "third-autocorrelation-inequality": "c3_root/turbo-topology-continuation-v2/runs/20260815T031008Z/best.npy",
    "thomson-problem": "geometry/runs/20260814T234800Z/thomson-problem/best.json",
}
FROZEN_VERIFIER_SNAPSHOTS = {
    "erdos-min-overlap": "erdos_root/snapshots/erdos-min-overlap_20260814T232154Z.json",
}
EVIDENCE_ARTIFACTS = {
    "prime-number-theorem-full-horizon": (
        "discrete/prime_number_theorem/checkpoints/"
        "reach_extend_127849_exact_audit.json"
    ),
}
SANITIZED_EVIDENCE_ARTIFACTS = {
    "geometry-literature-asset-replays": "literature_asset_hunt/receipt.json",
    "geometry-literature-asset-sources": "literature_asset_hunt/sources.json",
}
FRONTIER_RECEIPTS = {
    "edges-vs-triangles": "state/receipts/edges-vs-triangles/20260815T024004430186Z-c71bc6912f5a.json",
    "third-autocorrelation-inequality": "c3_root/turbo-topology-continuation-v2/runs/20260815T031008Z/receipt.json",
}
METHODS = {
    "circle-packing": "Exact replay reaches 2.635983095281624, still 7.92e-11 short after 156 one-contact releases, 58 PAS-PCI relocations, and 80 clean-room FlowBoost-inspired seeds; a genuinely new multi-contact topology is required.",
    "circles-rectangle": "Exact replay reaches 2.365832385227916, still 8.01e-11 short after 100 global/aspect and void endpoints spanning 24 graph classes, 22 absent from the full public corpus; a genuinely new multi-contact topology is required.",
    "difference-bases": "All relevant 1-swaps, exact 2-for-2 exchanges, and block repairs were exhausted without extending coverage 49,109.",
    "edges-vs-triangles": "Exact dynamic programming solves all 8,514 branch/count states and the complete 18-branch allocation; a 131,071-mask transition-topology screen finds no escape. Exact replay gains 7.61e-9, still 9.92e-7 short of the gate.",
    "erdos-min-overlap": "Independent literal-verifier replay of the n=3,584 active-bundle SLP reaches 0.38085862169567786, improving the public leader by 5.55e-8 but remaining 4.45e-8 short of the gate; a bounded n=64 Shor–McCormick/SROCR lift extracted only worse feasible basins.",
    "first-autocorrelation-inequality": "Exact-accepted high-beta FFT continuation; evaluated solution #2504.",
    "flat-polynomials": "Exact radius-six closure plus global pair-topology, block-family, SAT, and annealing tools now cover 144,193,119 local masks, 8,388,608 block constructions, and more than 403 million global proposals; the unrecovered 72/115 PSL-4 tables remain the strongest finite lead.",
    "heilbronn-triangles": "100-digit active root, 462 topology trials, complete q=25 lattice proof, partial q=30 proof, and adaptive q=143 SAT cores.",
    "kissing-number-d11": "The live score 0 is the exact objective floor; no strict numerical improvement below zero exists under this verifier.",
    "kissing-number-d11-605": "Sparse tangent-space active-set SLP; evaluated solution #2500.",
    "kissing-number-d12": "Published 841-code replays at exact verifier score 0 with 1.24497e-7 distance-squared margin; submission is blocked by HTTP 409, tracked in issue #59.",
    "kissing-number-d12-842": "Sparse tangent-space active-set SLP; evaluated solution #2499.",
    "min-distance-ratio-2d": "100-digit active root and 280 topology release/promote trials; best local gain is 2.35e-11 versus a 1e-7 gate.",
    "prime-number-theorem": "Changed-reach cutting planes produce evaluated solution #2506 at 0.9976572852677297. An exact rational sweep covers every real state in the advertised verifier horizon; a global all-x proof remains open.",
    "second-autocorrelation-inequality": "Exact replay reaches 0.9635881172701123 after changed-support packet births; 362 whole-region phase schedules and 378 finite-mass terminal split constructions found no global escape, leaving a 9.9933e-6 gate gap.",
    "tammes-problem": "Platform #1 uses an interior zero vector admitted by the verifier; disclosed and not claimed as a spherical construction.",
    "third-autocorrelation-inequality": "Boundary-cell sign-topology escapes plus exact all-coordinate continuation reach 1.4515653850221024; the frozen payload improves the pre-topology basin by 2.15e-8 but remains 3.52e-6 short of the gate.",
    "thomson-problem": "48 topology-changing seeds and exact tangent polishing return to the defect-minimal basin; no gate-clearer yet.",
    "uncertainty-principle": "k=25 contact-manifold continuation with fresh-process high-precision replay; evaluated solution #2505.",
}
SOURCE_ENTRYPOINTS = {
    "circle-packing": "geometry/circle_packing_topology/HANDOFF.md",
    "circles-rectangle": "geometry/rectangle_topology/HANDOFF.md",
    "difference-bases": "discrete/difference_bases/HANDOFF.md",
    "edges-vs-triangles": "discrete/edges_vs_triangles/HANDOFF.md",
    "erdos-min-overlap": "analytic/erdos_global/HANDOFF.md",
    "flat-polynomials": "analytic/flat_global/HANDOFF.md",
    "heilbronn-triangles": "geometry/heilbronn_bnb/HANDOFF.md",
    "kissing-number-d12": "geometry/kissing_d12/HANDOFF.md",
    "prime-number-theorem": "discrete/prime_number_theorem/HANDOFF.md",
    "second-autocorrelation-inequality": "analytic/c2_global_topology/HANDOFF.md",
    "third-autocorrelation-inequality": "c3_root/TOPOLOGY_ESCAPE_HANDOFF.md",
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
    "c3_root/requirements-rank-lift.txt",
)
SOURCE_EXTENSIONS = {".py", ".md", ".cpp", ".sh"}
SOURCE_FAMILIES = (
    "analytic",
    "c1_root",
    "c2_root",
    "c3_root",
    "discrete",
    "erdos_root",
    "geometry",
    "literature_asset_hunt",
    "research_corpus",
)
EXCLUDED_PARTS = {
    "external",
    "runs",
    "snapshots",
    "receipts",
    "checkpoints",
    "vendor",
    "cache",
    "payloads",
    # Active lanes are published only after their own frozen handoffs.
    "difference_global",
    "__pycache__",
    ".ruff_cache",
}
UNPUBLISHED_WORK_IN_PROGRESS = {
    Path("discrete/prime_number_theorem/tail_select_mip.py"),
}


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
        blocked = VERIFIED_BLOCKED.get(slug)
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
                "integrity": (
                    "disclosure" if slug in DISCLOSURES
                    else "numerical-certificate" if slug in NUMERICAL_CERTIFICATES
                    else "domain-valid-blocked" if blocked
                    else "domain-valid" if problem.get("our_rank") == 1
                    else "active"
                ),
                "disclosure": DISCLOSURES.get(slug),
                "numerical_certificate": NUMERICAL_CERTIFICATES.get(slug),
                "verified_blocked": blocked,
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
        if row["verified_blocked"]:
            ours = "🧊 **score `0` verified; submissions disabled**"
        elif row["our_entry"]:
            icon = (
                "⚠️"
                if row["integrity"] == "disclosure"
                else "🧪"
                if row["integrity"] == "numerical-certificate"
                else "🥇"
            )
            ours = f"{icon} **#{row['our_rank']}** / `{format_score(row['our_entry']['bestScore'])}`"
        else:
            ours = "— / active"
        verifier = f"`{row['verifier_sha256'][:12]}`"
        ids = row["solution_ids"]
        source_entrypoint = SOURCE_ENTRYPOINTS.get(row["slug"])
        source_link = (
            f"[handoff](../src/campaign/{source_entrypoint})"
            if source_entrypoint
            else "[lane source](../src/campaign/)"
        )
        if row["verified_blocked"]:
            evidence = "[proof](../artifacts/evidence/kissing-number-d12.json) · [blocker](https://github.com/vinid/einstein-arena/issues/59)"
        else:
            solution_links = " · ".join(
                f"[#{sid}](https://einsteinarena.com/api/solutions/{sid})"
                for sid in ids
            )
            evidence = " · ".join(part for part in (solution_links, source_link) if part)
        literature = "[map](LITERATURE.md#public-safe-map-for-all-19-arena-slugs)"
        lines.append(
            f"| [{row['title']}]({row['problem_url']}) | {arrow} | {leader_text} | {ours} | "
            f"`{format_score(row['min_improvement'])}` | {verifier} | {evidence} | {literature} |"
        )
    lines.extend(
        [
            "",
            "> [!WARNING]",
            "> Tammes is a platform first place but not a spherical-code result; see [ETHICS.md](ETHICS.md).",
            "> The PNT entry checks the complete advertised verifier horizon, but it is a numerical certificate rather than a proof of the all-x analytic statement.",
            "> Kissing d12/841 is domain-valid and verifier-perfect locally, but the Arena endpoint returns HTTP 409 because submissions are disabled; see [issue #59](https://github.com/vinid/einstein-arena/issues/59).",
            "",
            "The source of truth is [`data/frontier.json`](../data/frontier.json).",
            "",
            "## Research ledger",
            "",
            "| Benchmark | Current solution, artifact, or bound | Paperclip-grounded next move |",
            "|---|---|---|",
        ]
    )
    literature_path = REPO / "literature" / "literature_map.json"
    literature: dict[str, str] = {}
    if literature_path.is_file():
        packet = json.loads(literature_path.read_text(encoding="utf-8"))
        literature = {item["slug"]: item["research_direction"] for item in packet["problems"]}
    for row in frontier["problems"]:
        slug = row["slug"]
        artifact = FRONTIER_ARTIFACTS.get(slug)
        artifact_link = ""
        if artifact:
            suffix = Path(artifact).suffix
            artifact_link = f" [artifact](../artifacts/frontier/{slug}{suffix})"
        method = METHODS.get(slug, "Active corpus-first search.") + artifact_link
        next_move = literature.get(slug, "Literature packet pending.")
        lines.append(f"| [`{slug}`]({row['problem_url']}) | {method} | {next_move} |")
    return "\n".join(lines) + "\n"


def sanitize_receipt(receipt: dict[str, Any], artifact_name: str) -> dict[str, Any]:
    clean = dict(receipt)
    clean["candidate_path"] = f"artifacts/wins/{artifact_name}"
    return clean


def portable_campaign_path(value: str, source: Path) -> str:
    """Remove host-specific prefixes while retaining campaign provenance."""
    path = Path(value)
    if not path.is_absolute():
        return value
    try:
        return str(path.relative_to(source.parent))
    except ValueError:
        return path.name


def portable_json(value: Any, source: Path) -> Any:
    """Recursively remove host-specific prefixes from public JSON evidence."""
    if isinstance(value, dict):
        return {key: portable_json(item, source) for key, item in value.items()}
    if isinstance(value, list):
        return [portable_json(item, source) for item in value]
    if isinstance(value, str) and Path(value).is_absolute():
        return portable_campaign_path(value, source)
    return value


def frontier_artifact_destination(slug: str, source: Path) -> Path:
    """Return the public artifact path without losing its source suffix."""
    artifact_source = source / FRONTIER_ARTIFACTS[slug]
    return REPO / "artifacts" / "frontier" / f"{slug}{artifact_source.suffix}"


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
            if relative in UNPUBLISHED_WORK_IN_PROGRESS:
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
    write_json(
        REPO / "artifacts" / "evidence" / "kissing-number-d12.json",
        VERIFIED_BLOCKED["kissing-number-d12"],
    )

    manifest = mirror_source(source)
    blocked_evidence = REPO / "artifacts" / "evidence" / "kissing-number-d12.json"
    manifest.append({
        "path": str(blocked_evidence.relative_to(REPO)),
        "sha256": sha256(blocked_evidence),
        "bytes": blocked_evidence.stat().st_size,
    })
    for name, relative_text in EVIDENCE_ARTIFACTS.items():
        src = source / relative_text
        dst = REPO / "artifacts" / "evidence" / f"{name}{src.suffix}"
        copy_file(src, dst)
        manifest.append({
            "path": str(dst.relative_to(REPO)),
            "sha256": sha256(dst),
            "bytes": dst.stat().st_size,
        })
    for name, relative_text in SANITIZED_EVIDENCE_ARTIFACTS.items():
        src = source / relative_text
        dst = REPO / "artifacts" / "evidence" / f"{name}.json"
        evidence = json.loads(src.read_text(encoding="utf-8"))
        write_json(dst, portable_json(evidence, source))
        manifest.append({
            "path": str(dst.relative_to(REPO)),
            "sha256": sha256(dst),
            "bytes": dst.stat().st_size,
        })
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

    for slug, relative_text in FRONTIER_ARTIFACTS.items():
        src = source / relative_text
        dst = frontier_artifact_destination(slug, source)
        copy_file(src, dst)
        manifest.append({"path": str(dst.relative_to(REPO)), "sha256": sha256(dst), "bytes": dst.stat().st_size})

    for slug, relative_text in FRONTIER_RECEIPTS.items():
        receipt = json.loads((source / relative_text).read_text(encoding="utf-8"))
        artifact = frontier_artifact_destination(slug, source)
        receipt["candidate_path"] = str(artifact.relative_to(REPO))
        if "payload" in receipt:
            receipt["payload"] = receipt["candidate_path"]
        for key in ("baseline_payload", "verifier_path"):
            if key in receipt:
                receipt[key] = portable_campaign_path(receipt[key], source)
        for key in ("lineage", "reproduction_command"):
            if key in receipt:
                receipt[key] = [portable_campaign_path(item, source) for item in receipt[key]]
        dst = REPO / "artifacts" / "receipts" / f"{slug}.json"
        write_json(dst, receipt)
        manifest.append({"path": str(dst.relative_to(REPO)), "sha256": sha256(dst), "bytes": dst.stat().st_size})

    for slug, relative_text in FROZEN_VERIFIER_SNAPSHOTS.items():
        snapshot = json.loads((source / relative_text).read_text(encoding="utf-8"))
        compact_snapshot = {
            "fetched_at": snapshot["fetched_at"],
            "problem": {"verifier": snapshot["problem"]["verifier"]},
            "verifier_sha256": snapshot["verifier_sha256"],
        }
        dst = REPO / "artifacts" / "verifiers" / f"{slug}.json"
        write_json(dst, compact_snapshot)
        manifest.append({"path": str(dst.relative_to(REPO)), "sha256": sha256(dst), "bytes": dst.stat().st_size})

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
