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
    "erdos-min-overlap": [2507],
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
    "erdos-min-overlap": "analytic/erdos_global/slp_runs/20260815T043300Z-n3584-margin03/best.json",
}
WIN_RECEIPTS = {
    "prime-number-theorem": "state/receipts/prime-number-theorem/20260815T032933818594Z-4082fb8c9b71.json",
    "kissing-number-d12-842": "state/receipts/kissing-number-d12-842/20260814T225240418258Z-99b544b575ab.json",
    "kissing-number-d11-605": "state/receipts/kissing-number-d11-605/20260814T225509786111Z-89fad32eba9b.json",
    "first-autocorrelation-inequality": "state/receipts/first-autocorrelation-inequality/20260814T232734823043Z-e3f90379fb5a.json",
    "uncertainty-principle": "state/receipts/uncertainty-principle/20260814T234525289383Z-12590e6c26a7.json",
    "erdos-min-overlap": "state/receipts/erdos-min-overlap/20260815T043510990584Z-43d6096c5ebd.json",
}
FRONTIER_ARTIFACTS = {
    "circle-packing": "geometry/circle_packing_topology/runs/20260815T021013Z/topologies/1a3ddda1ed2e3083/candidate.json",
    "circles-rectangle": "geometry/rectangle_topology/runs/20260815T022200Z/stochastic_relax/topologies/cdea3037dafa48f9/candidate.json",
    "edges-vs-triangles": "discrete/edges_vs_triangles/runs/20260815T023100Z/global_dp/candidate.json",
    "heilbronn-triangles": "geometry/runs/20260814T231710Z/heilbronn-triangles/best.json",
    "min-distance-ratio-2d": "geometry/runs/20260814T231106Z/min-distance-ratio-2d/best.json",
    "second-autocorrelation-inequality": "analytic/c2_global_topology/runs/20260815T041000Z-terminal-split/best.npy",
    "third-autocorrelation-inequality": "analytic/c3_precision_escape/runs/20260815T063056Z-39272/best.npy",
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
    "difference-global-audit": "discrete/difference_global/checkpoints/audit_receipt.json",
    "difference-global-relative-checkpoint": "discrete/difference_global/checkpoints/relative_graph.json",
    "difference-global-sparse-patch-checkpoint": "discrete/difference_global/checkpoints/sparse_patch.json",
    "difference-global-relative-candidate": "discrete/difference_global/candidates/relative_graph_best.json",
    "difference-global-sparse-patch-candidate": "discrete/difference_global/candidates/sparse_patch_best.json",
    "flat-psl4-archive-audit": "flat_psl4_recovery/archive_audit.json",
    "flat-psl4-source-manifest": "flat_psl4_recovery/source_manifest.json",
    "flat-psl4-printed-neighbours": "flat_psl4_recovery/printed_neighbour_screen.json",
    "flat-psl4-best-replay": "flat_psl4_recovery/receipts/best_printed_neighbor_n71_delete70.json",
    "flat-psl4-exact-neighbourhood": "flat_psl4_enumerator/receipt.json",
    "flat-psl4-global-hybrid": "flat_psl4_global_exact/receipt.json",
    "flat-psl4-global-hybrid-benchmarks": "flat_psl4_global_exact/benchmarks.json",
    "flat-psl4-global-scaling-profile": "flat_psl4_global_exact/scaling_profile.json",
    "difference-exact-synthesis": "discrete/difference_exact_synthesis/receipt.json",
    "circle-packing-multicontact-precision": "geometry/circle_packing_multicontact_precision/receipt.json",
    "circle-packing-multicontact-replay": "geometry/circle_packing_multicontact_precision/replay_receipt.json",
    "circles-rectangle-multicontact-precision": "geometry/rectangle_multicontact_precision/receipt.json",
    "circles-rectangle-multicontact-replay": "geometry/rectangle_multicontact_precision/replay_receipt.json",
    "geometry-literature-asset-replays": "literature_asset_hunt/receipt.json",
    "geometry-literature-asset-sources": "literature_asset_hunt/sources.json",
    "geometry-secondary-circle-assets": "literature_asset_hunt/secondary_circle_assets.json",
    "geometry-contact-recombination": "geometry_asset_recombine/replay_receipt.json",
    "schema-gap-audit": "schema_gap_audit/receipt.json",
    "c2-asset-recovery": "c2_asset_recovery/receipt.json",
    "c2-simpletes-transfer": "c2_simpletes_transfer/receipt.json",
    "c2-simpletes-repeat-probe": "c2_simpletes_transfer/repeat_probe.json",
    "c2-global-multiscale": (
        "analysis/second_autocorrelation_global_multiscale/receipt.json"
    ),
    "c2-global-multiscale-independent-replay": (
        "analysis/second_autocorrelation_global_multiscale/runs/"
        "20260815T062500Z-bundle/independent_replay.json"
    ),
    "c2-global-multiscale-source-manifest": (
        "analysis/second_autocorrelation_global_multiscale/runs/"
        "20260815T062500Z-bundle/source_manifest.json"
    ),
    "c2-sliding-support": (
        "analysis/second_autocorrelation_sliding_support/receipt.json"
    ),
    "c2-sliding-support-independent-replay": (
        "analysis/second_autocorrelation_sliding_support/runs/"
        "20260815T064800Z-sliding-support/independent_replay.json"
    ),
    "c2-sliding-support-gradient-check": (
        "analysis/second_autocorrelation_sliding_support/runs/"
        "20260815T064800Z-sliding-support/gradient_check.json"
    ),
    "c3-precision-escape": "analytic/c3_precision_escape/receipt.json",
    "c3-asset-recovery": "c3_asset_recovery/receipt.json",
    "kissing-d11-594-exact-audit": "kissing_d11_594_audit/receipt.json",
    "heilbronn-q143-exact-support-closure": "geometry/heilbronn_q143_cegis/receipt.json",
    "heilbronn-rational-mesh-closure": "geometry/heilbronn_rational_mesh_global/replay_receipt.json",
    "rectangle-precision-escape": "geometry/rectangle_precision_escape/receipt.json",
    "min-distance-global-topology-escape": "geometry/min_distance_ratio_global_escape/receipt.json",
    "thomson-topology-escape": "geometry/thomson_282_topology_escape/receipt.json",
    "thomson-topology-independent-replay": "geometry/thomson_282_topology_escape/runs/20260815T_THOMSON_SPLIT_V1/independent_replay.json",
    "thomson-topology-isomorphism-audit": "geometry/thomson_282_topology_escape/runs/20260815T_THOMSON_SPLIT_V1/exact_isomorphism_audit.json",
    "evolver-asset-sweep-2026": "evolver_asset_sweep_2026/receipt.json",
}
FRONTIER_RECEIPTS = {
    "edges-vs-triangles": "state/receipts/edges-vs-triangles/20260815T024004430186Z-c71bc6912f5a.json",
    "third-autocorrelation-inequality": "c3_root/turbo-topology-continuation-v2/runs/20260815T031008Z/receipt.json",
}
METHODS = {
    "circle-packing": "Exact replay reaches 2.635983095281623, still 7.92e-11 short. Beyond one-contact continuation, relocation, and 550 contact-graph recombinations, the latest clean-room codimension-two campaign solved 9,270 graph systems, accepted 8,699 labeled endpoints, and deduplicated 5,147 unlabeled WL classes. No changed topology escaped the canonical tolerance ceiling.",
    "circles-rectangle": "Exact replay reaches 2.365832385227916, still 8.01e-11 short. The latest simultaneous-contact campaign exhausts all 2,016 two-contact and 41,664 three-contact releases from both rigid public graph classes: 11,933 nonlinear systems, 11,884 accepted endpoints, and 8,828 unlabeled WL classes. The canonical tolerance ceiling remains best, so a higher-codimension or genuinely different topology is required.",
    "difference-bases": "All relevant 1-swaps, exact 2-for-2 exchanges, block repairs, and a separate quadratic relative-difference-set family are closed. The newest carry-exact CSP lets every residue column independently choose any nonempty subset of shells 0..7; 19 independently rebuilt formulas prove infeasibility for every size 320..720 within that fixed 90-point cyclic-core family. This is a family closure, not a global difference-basis proof.",
    "edges-vs-triangles": "Exact dynamic programming solves all 8,514 branch/count states and the complete 18-branch allocation; a 131,071-mask transition-topology screen finds no escape. Exact replay gains 7.61e-9, still 9.92e-7 short of the gate.",
    "erdos-min-overlap": "Active-bundle sequential linear programming over n=3,584 coordinates crossed the strict 1e-7 gate after 58 exact-accepted stages. Independent literal replay and evaluated solution #2507 agree at 0.3808585748578584.",
    "first-autocorrelation-inequality": "Exact-accepted high-beta FFT continuation; evaluated solution #2504.",
    "flat-polynomials": "Exact radius-six closure plus global pair-topology, block-family, SAT, and annealing tools cover 144,193,119 local masks, 8,388,608 block constructions, and more than 403 million global proposals. A separate 20-source archival recovery reconstructed three of 72 published PSL-4 classes. The newest clean-room exact hybrid combines outside-in XOR/popcount with a grouped path-parity bound; on one fixed global task it is 6.60% faster than raw popcount, 25.89% faster than the prior strong solver, and visits 143.67x fewer nodes than raw. Deterministic hash sharding, atomic per-shard receipts, resume validation, and a 926-task capped workload profile now make the open 730,810-task enumeration distributable.",
    "heilbronn-triangles": "A 100-digit active root, 462 topology trials, and exact q=25 lattice closure are supplemented by exact q=143 and q=144..220 rational-mesh campaigns. The latest packet closes 72 distinct finite labeled domains: 18 by determinant upper bounds and 57 fresh uncapped SAT formulas, with no candidate. These are finite-domain no-gos, not global proofs. An independent Escher asset replay scored 0.03372654309850653, below the gate.",
    "kissing-number-d11": "An exhaustive exact-rational audit verifies public solution #1492 as a genuine 594-vector score-0 construction over all 176,121 pairs. Zero is the objective floor, and the live API assigns later exact ties ordinal ranks rather than joint first place.",
    "kissing-number-d11-605": "Sparse tangent-space active-set SLP; evaluated solution #2500.",
    "kissing-number-d12": "Published 841-code replays at exact verifier score 0 with 1.24497e-7 distance-squared margin; submission is blocked by HTTP 409, tracked in issue #59.",
    "kissing-number-d12-842": "Sparse tangent-space active-set SLP; evaluated solution #2499.",
    "min-distance-ratio-2d": "A 100-digit active root, 280 release/promote trials, and 550 canonical contact-graph recombinations all return the same micro-polished basin. A separate adjacent-cardinality topology campaign exact-replayed 214 births/deaths and found 153 corpus-novel contact graphs; the best novel graph remains 0.00577 worse, while the overall best gains only 2.35e-11 against a 1e-7 gate.",
    "prime-number-theorem": "Changed-reach cutting planes produce evaluated solution #2506 at 0.9976572852677297. An exact rational sweep covers every real state in the advertised verifier horizon; a global all-x proof remains open.",
    "second-autocorrelation-inequality": "Exact replay reaches 0.9635881192968997 after changed-support packet births and a 2,184-call SimpleTES topology-transfer campaign. Paperclip/Exa-grounded multiscale and sliding-support campaigns then reconstructed 360 coordinated mosaics plus 64 exact relocation paths; 56 sliding paths changed topology, but none improved the seed materially. The strict gate gap remains 9.9913e-6.",
    "tammes-problem": "Platform #1 uses an interior zero vector admitted by the verifier; disclosed and not claimed as a spherical construction.",
    "third-autocorrelation-inequality": "Boundary-cell sign-topology escapes plus exact all-coordinate continuation now reach 1.4515653796072292. The latest lane screened 14,333 deletions, 100,152 block transplants, 20,000 single sign walls, and 7,140 wall pairs; two exact-accepted orthant crossings gained another 5.41e-9, leaving a 3.5157e-6 gate gap.",
    "thomson-problem": "A literature-grounded N=72 to N=282 split campaign enumerated 48 alternative defect-free source triangulations and realized 30 distinct defect-free N=282 initial graphs. Exact isomorphism replay shows all 30 releases return to the incumbent topology; the best score differs only by 1.46e-11 float dust and remains 9.99986e-7 short.",
    "uncertainty-principle": "k=25 contact-manifold continuation with fresh-process high-precision replay; evaluated solution #2505.",
}
SOURCE_ENTRYPOINTS = {
    "circle-packing": "geometry/circle_packing_multicontact_precision/HANDOFF.md",
    "circles-rectangle": "geometry/rectangle_multicontact_precision/HANDOFF.md",
    "difference-bases": "discrete/difference_exact_synthesis/HANDOFF.md",
    "edges-vs-triangles": "discrete/edges_vs_triangles/HANDOFF.md",
    "erdos-min-overlap": "analytic/erdos_global/HANDOFF.md",
    "flat-polynomials": "flat_psl4_global_exact/HANDOFF.md",
    "heilbronn-triangles": "geometry/heilbronn_rational_mesh_global/HANDOFF.md",
    "kissing-number-d11": "kissing_d11_594_audit/README.md",
    "min-distance-ratio-2d": "geometry/min_distance_ratio_global_escape/HANDOFF.md",
    "kissing-number-d12": "geometry/kissing_d12/HANDOFF.md",
    "prime-number-theorem": "discrete/prime_number_theorem/HANDOFF.md",
    "second-autocorrelation-inequality": (
        "analysis/second_autocorrelation_sliding_support/HANDOFF.md"
    ),
    "third-autocorrelation-inequality": "analytic/c3_precision_escape/HANDOFF.md",
    "thomson-problem": "geometry/thomson_282_topology_escape/HANDOFF.md",
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
    "geometry/heilbronn_rational_mesh_global/.gitignore",
    "geometry/heilbronn_rational_mesh_global/literature_sources.json",
    "geometry/heilbronn_rational_mesh_global/denominator_screen.json",
    "geometry/heilbronn_rational_mesh_global/case_manifest.json",
    "geometry/heilbronn_rational_mesh_global/replay_receipt.json",
    "geometry/thomson_282_topology_escape/.gitignore",
    "geometry/thomson_282_topology_escape/literature.json",
    "geometry/thomson_282_topology_escape/live_read_check.json",
    "geometry/thomson_282_topology_escape/receipt.json",
    "geometry/min_distance_ratio_global_escape/assets.json",
    "geometry/min_distance_ratio_global_escape/receipt.json",
    "geometry/min_distance_ratio_global_escape/runs/FINAL_V2/best.json",
    "geometry/min_distance_ratio_global_escape/runs/FINAL_V2/corpus_audit.json",
    "geometry/min_distance_ratio_global_escape/runs/FINAL_V2/events.jsonl",
    "geometry/min_distance_ratio_global_escape/runs/FINAL_V2/reconstructed_assets.json",
    "geometry/min_distance_ratio_global_escape/runs/FINAL_V2/summary.json",
    "flat_psl4_enumerator/.gitignore",
    "flat_psl4_enumerator/README.md",
    "flat_psl4_enumerator/HANDOFF.md",
    "flat_psl4_enumerator/psl4_exact.cpp",
    "flat_psl4_enumerator/freeze_receipt.py",
    "flat_psl4_enumerator/tests/test_exact_bound.py",
    "flat_psl4_enumerator/receipt.json",
    "flat_psl4_enumerator/runs/near-leukhin-24.jsonl",
    "flat_psl4_enumerator/runs/near-dimitrov-24.jsonl",
    "flat_psl4_enumerator/runs/near-pslrk-24.jsonl",
    "flat_psl4_global_exact/README.md",
    "flat_psl4_global_exact/HANDOFF.md",
    "flat_psl4_global_exact/psl4_popcount.cpp",
    "flat_psl4_global_exact/psl4_dispatch.py",
    "flat_psl4_global_exact/literature.json",
    "flat_psl4_global_exact/benchmarks.json",
    "flat_psl4_global_exact/scaling_profile.json",
    "flat_psl4_global_exact/receipt.json",
    "flat_psl4_global_exact/runs/benchmark-raw.tsv",
    "flat_psl4_global_exact/runs/benchmark-hybrid-d24.tsv",
    "flat_psl4_global_exact/runs/benchmark-prior-strong.tsv",
    "flat_psl4_global_exact/runs/profile-20260815T0714Z/psl4-cap100k-shard0.tsv",
    "flat_psl4_global_exact/runs/profile-20260815T0714Z/psl4-cap100k-shard1.tsv",
    "flat_psl4_global_exact/runs/profile-20260815T0714Z/psl4-cap100k-shard2.tsv",
    "flat_psl4_global_exact/runs/profile-20260815T0714Z/psl4-cap100k-shard3.tsv",
    "flat_psl4_global_exact/runs/profile-20260815T0714Z/psl4-cap100k-shard4.tsv",
    "flat_psl4_global_exact/runs/profile-20260815T0714Z/psl4-cap100k-shard5.tsv",
    "flat_psl4_global_exact/runs/profile-20260815T0714Z/psl4-cap100k-shard6.tsv",
    "flat_psl4_global_exact/runs/profile-20260815T0714Z/psl4-cap100k-shard7.tsv",
    "flat_psl4_global_exact/runs/profile-20260815T0714Z/psl4-cap500k-shard0.tsv",
    "analysis/second_autocorrelation_global_multiscale/.gitignore",
    "analysis/second_autocorrelation_global_multiscale/README.md",
    "analysis/second_autocorrelation_global_multiscale/HANDOFF.md",
    "analysis/second_autocorrelation_global_multiscale/literature.json",
    "analysis/second_autocorrelation_global_multiscale/search.py",
    "analysis/second_autocorrelation_global_multiscale/replay.py",
    (
        "analysis/second_autocorrelation_global_multiscale/runs/"
        "20260815T062500Z-bundle/events.jsonl"
    ),
    (
        "analysis/second_autocorrelation_global_multiscale/runs/"
        "20260815T062500Z-bundle/selected_specs.json"
    ),
    (
        "analysis/second_autocorrelation_global_multiscale/runs/"
        "20260815T062500Z-bundle/summary.json"
    ),
    "analysis/second_autocorrelation_sliding_support/.gitignore",
    "analysis/second_autocorrelation_sliding_support/README.md",
    "analysis/second_autocorrelation_sliding_support/HANDOFF.md",
    "analysis/second_autocorrelation_sliding_support/literature.json",
    "analysis/second_autocorrelation_sliding_support/receipt.json",
    "analysis/second_autocorrelation_sliding_support/search.py",
    "analysis/second_autocorrelation_sliding_support/replay.py",
    (
        "analysis/second_autocorrelation_sliding_support/runs/"
        "20260815T064800Z-sliding-support/events.jsonl"
    ),
    (
        "analysis/second_autocorrelation_sliding_support/runs/"
        "20260815T064800Z-sliding-support/gradient_check.json"
    ),
    (
        "analysis/second_autocorrelation_sliding_support/runs/"
        "20260815T064800Z-sliding-support/independent_replay.json"
    ),
    (
        "analysis/second_autocorrelation_sliding_support/runs/"
        "20260815T064800Z-sliding-support/input_manifest.json"
    ),
    (
        "analysis/second_autocorrelation_sliding_support/runs/"
        "20260815T064800Z-sliding-support/specs.json"
    ),
    (
        "analysis/second_autocorrelation_sliding_support/runs/"
        "20260815T064800Z-sliding-support/summary.json"
    ),
    "analytic/c3_precision_escape/receipt.json",
)
SOURCE_EXTENSIONS = {".py", ".md", ".cpp", ".sh"}
SOURCE_FAMILIES = (
    "analytic",
    "c2_asset_recovery",
    "c2_simpletes_transfer",
    "c3_asset_recovery",
    "c1_root",
    "c2_root",
    "c3_root",
    "discrete",
    "erdos_root",
    "evolver_asset_sweep_2026",
    "flat_psl4_recovery",
    "geometry",
    "literature_asset_hunt",
    "geometry_asset_recombine",
    "kissing_d11_594_audit",
    "research_corpus",
    "schema_gap_audit",
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
    "__pycache__",
    ".ruff_cache",
}
UNPUBLISHED_WORK_IN_PROGRESS = {
    Path("discrete/prime_number_theorem/tail_select_mip.py"),
}
UNPUBLISHED_SOURCE_PREFIXES = {
    Path("discrete/difference_exact_synthesis"),
    Path("discrete/prime_number_theorem_global_proof"),
    Path("geometry/circle_packing_multicontact_precision"),
    Path("geometry/rectangle_multicontact_precision"),
    Path("discrete/difference_interval_constructions"),
    Path("geometry/circle_packing_multicontact_global"),
    Path("geometry/claudeevolve_circle_recovery"),
}

PUBLICATION_MANIFESTS = (
    Path("geometry/circle_packing_multicontact_precision/PUBLICATION_MANIFEST.json"),
    Path("geometry/rectangle_multicontact_precision/PUBLICATION_MANIFEST.json"),
)

PUBLICATION_ALLOWLIST = (
    Path("discrete/difference_exact_synthesis/HANDOFF.md"),
    Path("discrete/difference_exact_synthesis/PROVENANCE.md"),
    Path("discrete/difference_exact_synthesis/README.md"),
    Path("discrete/difference_exact_synthesis/carry_exact_csp.py"),
    Path("discrete/difference_exact_synthesis/complete_capacity_closure.py"),
    Path("discrete/difference_exact_synthesis/freeze_receipt.py"),
    Path("discrete/difference_exact_synthesis/frozen_inputs.json"),
    Path("discrete/difference_exact_synthesis/public_replay.py"),
    Path("discrete/difference_exact_synthesis/test_carry_exact_csp.py"),
    Path("discrete/difference_exact_synthesis/receipt.json"),
    Path("discrete/difference_exact_synthesis/runs/20260815T063528Z_height7_full_support/config.json"),
    Path("discrete/difference_exact_synthesis/runs/20260815T063528Z_height7_full_support/events.jsonl"),
    Path("discrete/difference_exact_synthesis/runs/20260815T063528Z_height7_full_support/summary.json"),
    Path("discrete/difference_exact_synthesis/runs/20260815T073000Z_complete_capacity_closure/config.json"),
    Path("discrete/difference_exact_synthesis/runs/20260815T073000Z_complete_capacity_closure/events.jsonl"),
    Path("discrete/difference_exact_synthesis/runs/20260815T073000Z_complete_capacity_closure/summary.json"),
)


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

    def copy_relative(relative: Path) -> None:
        src = source / relative
        if not src.is_file():
            raise FileNotFoundError(src)
        dst = destination_root / relative
        copy_file(src, dst)
        copied.append(
            {
                "path": str(dst.relative_to(REPO)),
                "sha256": sha256(dst),
                "bytes": dst.stat().st_size,
            }
        )

    def copy_portable_publication_entry(relative: Path) -> dict[str, Any]:
        """Copy manifest-approved evidence while stripping local host paths.

        The canonical publication manifest continues to authenticate the source
        bytes.  When a JSON/JSONL file needs a portability rewrite, the generated
        PUBLICATION_EXPORT.json records both the canonical and public hashes.
        """
        src = source / relative
        if not src.is_file():
            raise FileNotFoundError(src)
        dst = destination_root / relative
        transformed = False

        if src.suffix == ".json":
            original = json.loads(src.read_text(encoding="utf-8"))
            public = portable_json(original, source)
            transformed = public != original
            if transformed:
                write_json(dst, public)
            else:
                copy_file(src, dst)
        elif src.suffix == ".jsonl":
            source_lines = src.read_text(encoding="utf-8").splitlines()
            public_lines: list[str] = []
            for line_number, line in enumerate(source_lines, start=1):
                if not line:
                    public_lines.append(line)
                    continue
                try:
                    original = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSONL at {relative}:{line_number}") from exc
                public = portable_json(original, source)
                if public != original:
                    transformed = True
                    public_lines.append(
                        json.dumps(public, sort_keys=True, separators=(",", ":"))
                    )
                else:
                    public_lines.append(line)
            if transformed:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text("\n".join(public_lines) + "\n", encoding="utf-8")
            else:
                copy_file(src, dst)
        else:
            copy_file(src, dst)

        public_record = {
            "path": str(dst.relative_to(REPO)),
            "sha256": sha256(dst),
            "bytes": dst.stat().st_size,
        }
        copied.append(public_record)
        return {
            "path": str(relative),
            "canonical_sha256": sha256(src),
            "canonical_bytes": src.stat().st_size,
            "public_sha256": public_record["sha256"],
            "public_bytes": public_record["bytes"],
            "portable_path_rewrite": transformed,
        }

    for relative_text in ROOT_SOURCE_FILES:
        relative = Path(relative_text)
        src = source / relative
        if src.exists():
            copy_relative(relative)

    for manifest_relative in PUBLICATION_MANIFESTS:
        manifest_path = source / manifest_relative
        publication = json.loads(manifest_path.read_text(encoding="utf-8"))
        packet_root = manifest_relative.parent
        export_entries: list[dict[str, Any]] = []
        for entry in publication["include"]:
            relative = packet_root / entry["path"]
            src = source / relative
            if sha256(src) != entry["sha256"] or src.stat().st_size != entry["bytes"]:
                raise ValueError(f"publication manifest mismatch: {relative}")
            export_record = copy_portable_publication_entry(relative)
            export_record["path"] = entry["path"]
            export_entries.append(export_record)
        copy_relative(manifest_relative)
        export_relative = packet_root / "PUBLICATION_EXPORT.json"
        export_path = destination_root / export_relative
        write_json(
            export_path,
            {
                "schema_version": 1,
                "canonical_manifest": str(manifest_relative),
                "canonical_manifest_sha256": sha256(manifest_path),
                "policy": (
                    "Canonical bytes are hash-checked before export. Absolute host "
                    "paths in manifest-approved JSON/JSONL are rewritten to portable "
                    "campaign-relative paths; all other bytes are copied verbatim."
                ),
                "files": export_entries,
            },
        )
        copied.append(
            {
                "path": str(export_path.relative_to(REPO)),
                "sha256": sha256(export_path),
                "bytes": export_path.stat().st_size,
            }
        )

    difference_receipt = json.loads(
        (source / "discrete/difference_exact_synthesis/receipt.json").read_text(
            encoding="utf-8"
        )
    )
    difference_hashes = difference_receipt["publish_safe_artifacts"]
    for relative in PUBLICATION_ALLOWLIST:
        if relative.name != "receipt.json":
            key = f"campaign/{relative}"
            if sha256(source / relative) != difference_hashes[key]:
                raise ValueError(f"difference publication hash mismatch: {relative}")
        copy_relative(relative)

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
            if any(relative.is_relative_to(prefix) for prefix in UNPUBLISHED_SOURCE_PREFIXES):
                continue
            copy_relative(relative)
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
