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
        "full advertised verifier horizon checked exactly; #2506 violates the "
        "written all-x bound, already at x=1"
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
    "prime-number-theorem-global-proof": (
        "discrete/prime_number_theorem_global_proof/receipt.json"
    ),
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
    "difference-interval-constructions": "discrete/difference_interval_constructions/receipt.json",
    "difference-interval-replay": "discrete/difference_interval_constructions/replay_receipt.json",
    "circle-packing-multicontact-precision": "geometry/circle_packing_multicontact_precision/receipt.json",
    "circle-packing-multicontact-replay": "geometry/circle_packing_multicontact_precision/replay_receipt.json",
    "circle-packing-codim3-global": "geometry/circle_packing_multicontact_global/receipt_v2.json",
    "claudeevolve-circle-recovery": "geometry/claudeevolve_circle_recovery/publication/RECOVERY_RESULT.json",
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
    "circle-packing": "Exact replay reaches 2.635983095281623, still 7.92e-11 short. Beyond one-contact continuation, relocation, and 550 contact-graph recombinations, the codimension-two campaign solved 9,270 systems and deduplicated 5,147 unlabeled WL classes. A disjoint codimension-three campaign then tested 3,500 release triples and 2,848 genuine changed graphs. Exa archive recovery found the complete linked ClaudeEvolve strict generator, but it reproduces only 2.6359829285577328; the higher README headline has no recoverable candidate bytes and used a looser -1e-6 gap allowance. No tested topology or recovered asset escaped the canonical tolerance ceiling.",
    "circles-rectangle": "Exact replay reaches 2.365832385227916, still 8.01e-11 short. The latest simultaneous-contact campaign exhausts all 2,016 two-contact and 41,664 three-contact releases from both rigid public graph classes: 11,933 nonlinear systems, 11,884 accepted endpoints, and 8,828 unlabeled WL classes. The canonical tolerance ceiling remains best, so a higher-codimension or genuinely different topology is required.",
    "difference-bases": "All relevant 1-swaps, exact 2-for-2 exchanges, block repairs, and a separate quadratic relative-difference-set family are closed. A carry-exact CSP proves infeasibility for every size 320..720 within the fixed 90-point cyclic-core/shell-0..7 family. An exhaustive Banakh–Gavrylkiv four-block interval-basis sweep covers every unit multiplier and cyclic cut for 114 prime powers q<=499. A separate clean-room Wichmann/Leech gap-family sweep exact-checks 498,002 parameter pairs; its best 360-mark basis covers only 43,318 versus 49,110 required. Finally, an unrestricted changed-core evolutionary run exact-replays 27 retained arrays but never improves the incumbent; its farthest accepted state changes five marks. These are bounded family/search closures, not a global lower bound.",
    "edges-vs-triangles": "Exact dynamic programming solves all 8,514 branch/count states and the complete 18-branch allocation; a 131,071-mask transition-topology screen finds no escape. Exact replay gains 7.61e-9, still 9.92e-7 short of the gate.",
    "erdos-min-overlap": "Active-bundle sequential linear programming over n=3,584 coordinates crossed the strict 1e-7 gate after 58 exact-accepted stages. Independent literal replay and evaluated solution #2507 agree at 0.3808585748578584.",
    "first-autocorrelation-inequality": "Exact-accepted high-beta FFT continuation; evaluated solution #2504.",
    "flat-polynomials": "Exact radius-six closure plus global pair-topology, block-family, SAT, and annealing tools cover 144,193,119 local masks, 8,388,608 block constructions, and more than 403 million global proposals. Archival recovery reconstructed three of 72 published PSL-4 classes but found no missing table bytes after exact Exa, Paperclip, archive, code-index, and 25-slide visual audits. The clean-room hybrid visits 143.67x fewer nodes than raw, and its active-lag kernel replays a fixed 82,824,482-node task 1.461x faster. An independent SAT/PB formulation exactly agrees on 256 cubes, but MiniCard is 46.5x and CaDiCaL 661.9x slower than even the raw C++ DFS solve-only, so the resumable 730,810-task distributed C++ enumeration remains the honest exact route.",
    "heilbronn-triangles": "A 100-digit active root, 462 topology trials, and exact q=25 lattice closure are supplemented by exact q=143 and q=144..220 rational-mesh campaigns. The latest packet closes 72 distinct finite labeled domains: 18 by determinant upper bounds and 57 fresh uncapped SAT formulas, with no candidate. These are finite-domain no-gos, not global proofs. An independent Escher asset replay scored 0.03372654309850653, below the gate.",
    "kissing-number-d11": "An exhaustive exact-rational audit verifies public solution #1492 as a genuine 594-vector score-0 construction over all 176,121 pairs. Zero is the objective floor, and the live API assigns later exact ties ordinal ranks rather than joint first place.",
    "kissing-number-d11-605": "Sparse tangent-space active-set SLP; evaluated solution #2500.",
    "kissing-number-d12": "Published 841-code replays at exact verifier score 0 with 1.24497e-7 distance-squared margin; submission is blocked by HTTP 409, tracked in issue #59.",
    "kissing-number-d12-842": "Sparse tangent-space active-set SLP; evaluated solution #2499.",
    "min-distance-ratio-2d": "A 100-digit active root, 280 release/promote trials, and 550 canonical contact-graph recombinations all return the same micro-polished basin. A separate adjacent-cardinality topology campaign exact-replayed 214 births/deaths and found 153 corpus-novel contact graphs; the best novel graph remains 0.00577 worse, while the overall best gains only 2.35e-11 against a 1e-7 gate.",
    "prime-number-theorem": "Changed-reach cutting planes produce platform #1 solution #2506 at 0.9976572852677297, but an exact all-x audit proves it is not a mathematical certificate: S(1)=1.000099989952235... and S(8,015,392)=106.150121507295.... A nonnegative exact weak dual bounds every assignment on the same 2,000-key support by 0.997625778304447..., below the historical gate. The strongest new globally certified periodic divisor support scores 0.970073558281127. The complete Bober height-one classification peaks at Chebyshev 0.921292022934091; a 23-point symbolic dual proves Chebyshev optimal over all nonnegative combinations of 5,200 sporadic atoms at dilations 1..100. An Exa/Paperclip-grounded sweep of 3,312,606 explicit height-2/3 lists and 52 smooth divisor lattices also fails to improve on Chebyshev. A fundamentally different support identity is required.",
    "second-autocorrelation-inequality": "Exact replay reaches 0.9635881192968997 after changed-support packet births and a 2,184-call SimpleTES topology-transfer campaign. Paperclip/Exa-grounded multiscale and sliding-support campaigns then reconstructed 360 coordinated mosaics plus 64 exact relocation paths; 56 sliding paths changed topology, but none improved the seed materially. A separate 200-member-step native-grid pilot established implementation behavior but reached only 0.3593416133285091; its public packet contains receipt replay, generated-fixture tests, and a four-history H100 continuation plan, not the omitted optimizer, private acceptance adapter, or native checkpoint. No C2 gate was cleared; the retained local frontier remains 9.9913e-6 short.",
    "tammes-problem": "Platform #1 uses an interior zero vector admitted by the verifier; disclosed and not claimed as a spherical construction.",
    "third-autocorrelation-inequality": "Boundary-cell sign-topology escapes plus exact all-coordinate continuation now reach 1.4515653796072292. The latest lane screened 14,333 deletions, 100,152 block transplants, 20,000 single sign walls, and 7,140 wall pairs; two exact-accepted orthant crossings gained another 5.41e-9, leaving a 3.5157e-6 gate gap.",
    "thomson-problem": "A literature-grounded N=72 to N=282 split campaign enumerated 48 alternative defect-free source triangulations and realized 30 distinct defect-free N=282 initial graphs, all returning to the incumbent. A disjoint direct-N282 scar campaign then tested 49 deterministic mutation paths spanning 44 exact graph classes at two amplitudes: all 98 releases again returned to the incumbent topology. The best score differs only by float dust and remains 9.99986e-7 short.",
    "uncertainty-principle": "k=25 contact-manifold continuation with fresh-process high-precision replay; evaluated solution #2505.",
}
SOURCE_ENTRYPOINTS = {
    "circle-packing": "geometry/circle_packing_multicontact_global/HANDOFF.md",
    "circles-rectangle": "geometry/rectangle_multicontact_precision/HANDOFF.md",
    "difference-bases": "discrete/difference_exact_synthesis/HANDOFF.md",
    "edges-vs-triangles": "discrete/edges_vs_triangles/HANDOFF.md",
    "erdos-min-overlap": "analytic/erdos_global/HANDOFF.md",
    "flat-polynomials": "flat_psl4_global_exact/HANDOFF.md",
    "heilbronn-triangles": "geometry/heilbronn_rational_mesh_global/HANDOFF.md",
    "kissing-number-d11": "kissing_d11_594_audit/README.md",
    "min-distance-ratio-2d": "geometry/min_distance_ratio_global_escape/HANDOFF.md",
    "kissing-number-d12": "geometry/kissing_d12/HANDOFF.md",
    "prime-number-theorem": "discrete/prime_number_theorem_global_proof/HANDOFF.md",
    "second-autocorrelation-inequality": (
        "analysis/second_autocorrelation_native_basin/public_packet/README.md"
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
    Path("analytic/flat_psl4_accelerator"),
    Path("analytic/flat_psl4_sat_pb"),
    Path("analytic/flat_psl4_table_recovery_exa"),
    Path("analytic/flat_psl4_hardware"),
    Path("discrete/difference_exact_synthesis"),
    Path("discrete/prime_number_theorem_global_proof"),
    Path("discrete/pnt_factorial_ratio_landau"),
    Path("discrete/pnt_landau_atom_packing"),
    Path("geometry/circle_packing_multicontact_precision"),
    Path("geometry/rectangle_multicontact_precision"),
    Path("discrete/difference_interval_constructions"),
    Path("discrete/difference_global_evolution"),
    Path("discrete/difference_wichmann_leech"),
    Path("discrete/pnt_factorial_ratio_higher_height"),
    Path("geometry/circle_packing_multicontact_global"),
    Path("geometry/claudeevolve_circle_recovery"),
    Path("geometry/heilbronn_flow_topology_global"),
    Path("geometry/thomson_282_scar_escape"),
}

PUBLICATION_MANIFESTS = (
    Path("analytic/flat_psl4_accelerator/PUBLICATION_MANIFEST.json"),
    Path("analytic/flat_psl4_sat_pb/PUBLICATION_MANIFEST.json"),
    Path("analytic/flat_psl4_table_recovery_exa/PUBLICATION_MANIFEST.json"),
    Path("discrete/pnt_factorial_ratio_landau/PUBLICATION_MANIFEST.json"),
    Path("discrete/pnt_factorial_ratio_higher_height/PUBLICATION_MANIFEST.json"),
    Path("discrete/pnt_landau_atom_packing/PUBLICATION_MANIFEST.json"),
    Path("discrete/prime_number_theorem_global_proof/PUBLICATION_MANIFEST.json"),
    Path("discrete/difference_wichmann_leech/PUBLICATION_MANIFEST.json"),
    Path("discrete/difference_global_evolution/PUBLICATION_MANIFEST.json"),
    Path("geometry/circle_packing_multicontact_precision/PUBLICATION_MANIFEST.json"),
    Path("geometry/rectangle_multicontact_precision/PUBLICATION_MANIFEST.json"),
    Path("geometry/circle_packing_multicontact_global/PUBLICATION_MANIFEST.json"),
    Path("discrete/difference_interval_constructions/PUBLICATION_MANIFEST.json"),
    Path("geometry/claudeevolve_circle_recovery/PUBLICATION_MANIFEST.json"),
    Path("geometry/heilbronn_flow_topology_global/PUBLICATION_MANIFEST.json"),
    Path("geometry/thomson_282_scar_escape/PUBLICATION_MANIFEST.json"),
)

# These packets authenticate their own exact file set and must be copied
# byte-for-byte.  In particular, do not add the generic PUBLICATION_EXPORT.json
# sidecar inside the packet: doing so would invalidate its allowlist replay.
EXACT_PUBLICATION_MANIFESTS = {
    Path("analysis/second_autocorrelation_native_basin/public_packet/manifest.json"): (
        "1766c2348daa062be65d98a8cc269108e0ac192e47a01babcb41609cedf9877b"
    ),
}

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
            "> PNT solution #2506 is a platform-only finite-horizon result: an exact audit proves it violates the written all-x bound already at x=1; see its global-proof handoff.",
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
        path = Path(value)
        try:
            path.relative_to(source.parent)
            return portable_campaign_path(value, source)
        except ValueError:
            pass
        host_roots = (
            Path("/Users"),
            Path("/home"),
            Path("/tmp"),
            Path("/private/var"),
            Path("/var/folders"),
        )
        if any(path.is_relative_to(root) for root in host_roots):
            return path.name
    return value


def frontier_artifact_destination(slug: str, source: Path) -> Path:
    """Return the public artifact path without losing its source suffix."""
    artifact_source = source / FRONTIER_ARTIFACTS[slug]
    return REPO / "artifacts" / "frontier" / f"{slug}{artifact_source.suffix}"


def publication_allowlist(publication: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize supported publication-manifest allowlist schemas."""
    entries = publication.get("include", publication.get("allowlist"))
    if entries is not None:
        if not isinstance(entries, list):
            raise ValueError("publication manifest allowlist must be a list")
        return entries

    files = publication.get("files")
    if isinstance(files, dict):
        return [{"path": path, **metadata} for path, metadata in files.items()]
    raise ValueError("publication manifest has no allowlist")


def exact_publication_paths(
    source: Path,
    manifest_relative: Path,
    detached_manifest_sha256: str,
) -> list[Path]:
    """Validate an exact, self-allowlisted packet and return source-relative paths."""
    manifest_path = source / manifest_relative
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError(f"exact publication manifest is not a regular file: {manifest_relative}")
    if sha256(manifest_path) != detached_manifest_sha256:
        raise ValueError(f"exact publication detached hash mismatch: {manifest_relative}")

    publication = json.loads(manifest_path.read_text(encoding="utf-8"))
    packet_root = manifest_relative.parent
    entries = publication_allowlist(publication)
    paths: list[Path] = []
    seen: set[Path] = set()
    self_entry_seen = False

    for entry in entries:
        value = entry.get("path")
        if not isinstance(value, str) or not value:
            raise ValueError("exact publication path must be a nonempty string")
        entry_path = Path(value)
        if entry_path.is_absolute() or ".." in entry_path.parts:
            raise ValueError(f"unsafe exact publication path: {value!r}")
        if entry_path in seen:
            raise ValueError(f"duplicate exact publication path: {value}")
        seen.add(entry_path)

        relative = packet_root / entry_path
        src = source / relative
        if src.is_symlink() or not src.is_file():
            raise ValueError(f"exact publication entry is not a regular file: {relative}")
        if relative == manifest_relative:
            self_entry_seen = True
            if entry.get("sha256") is not None or entry.get("bytes") is not None:
                raise ValueError("exact publication manifest self hash/size must be null")
        else:
            if sha256(src) != entry.get("sha256") or src.stat().st_size != entry.get("bytes"):
                raise ValueError(f"exact publication manifest mismatch: {relative}")
        paths.append(relative)

    if not self_entry_seen:
        raise ValueError("exact publication manifest must allowlist itself")

    packet_source = source / packet_root
    if any(path.is_symlink() for path in packet_source.rglob("*")):
        raise ValueError(f"exact publication packet contains a symlink: {packet_root}")
    actual = {
        path.relative_to(source)
        for path in packet_source.rglob("*")
        if path.is_file()
    }
    if actual != set(paths):
        raise ValueError(f"exact publication file-set mismatch: {packet_root}")
    return paths


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
        packet_destination = destination_root / packet_root
        if packet_destination.exists():
            # Publication packets are allowlist snapshots. Purge the previous
            # export first so a file removed by a newer manifest cannot linger
            # in the public tree as stale, untracked evidence.
            shutil.rmtree(packet_destination)
        export_entries: list[dict[str, Any]] = []
        try:
            entries = publication_allowlist(publication)
        except ValueError as exc:
            raise ValueError(
                f"publication manifest has no allowlist: {manifest_relative}"
            ) from exc
        for entry in entries:
            entry_path = Path(entry["path"])
            if entry_path.parts and entry_path.parts[0] == "campaign":
                relative = Path(*entry_path.parts[1:])
                public_entry_path = str(relative.relative_to(packet_root))
            else:
                relative = packet_root / entry_path
                public_entry_path = entry["path"]
            src = source / relative
            if sha256(src) != entry["sha256"] or src.stat().st_size != entry["bytes"]:
                raise ValueError(f"publication manifest mismatch: {relative}")
            export_record = copy_portable_publication_entry(relative)
            export_record["path"] = public_entry_path
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

    for manifest_relative, detached_sha256 in EXACT_PUBLICATION_MANIFESTS.items():
        relatives = exact_publication_paths(
            source,
            manifest_relative,
            detached_sha256,
        )
        packet_root = manifest_relative.parent
        packet_destination = destination_root / packet_root
        if packet_destination.exists():
            shutil.rmtree(packet_destination)
        for relative in relatives:
            copy_relative(relative)
        exported = {
            path.relative_to(destination_root)
            for path in packet_destination.rglob("*")
            if path.is_file()
        }
        expected = {relative.relative_to(packet_root) for relative in relatives}
        if exported != expected:
            raise ValueError(f"exact publication export mismatch: {packet_root}")

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
