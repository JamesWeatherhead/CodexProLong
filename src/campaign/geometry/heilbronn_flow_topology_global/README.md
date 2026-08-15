# Heilbronn continuous topology escape

This packet records a bounded, genuinely continuous changed-topology search
for 11 points in the unit equilateral triangle. The corrected runs annealed
6,624 population members, retained and privately replayed 398 candidates, and
found no strict gate clearer. Their best score is
`0.034498013012460894`, short of the required
`>0.036529890880030155` gate by `0.002031877867569261`.

This is a quantified search frontier, not a global upper bound or proof of
optimality.

## Exact search scope

The global run enumerated all 23 positive-score outer-edge/vertex contact
patterns modulo the six symmetries of the equilateral triangle. Each island
used unconstrained barycentric genes, an annealed smooth minimum over all 165
triangle determinants, L-BFGS-B, and a released 165-constraint SLSQP polish.

The frozen snapshot has 17 public rows but only 13 D3-distinct public basins.
After merging generated islands and public basins by score, the global
death/rebirth phase selected ten parents: eight public basins and two generated
template basins. The larger continuation selected the four strongest public
basins. Both branches reinitialized 4, 5, 6, 8, or all 11 points; the public
discussion already records 2,471,800 depth-one-to-three replacement starts,
so those depths were not repeated.

Nearest-public distance is the true D3-invariant RMS: for every D3 image, the
Hungarian assignment minimizes the sum of **squared** Euclidean distances.
The corrected metadata has minimum retained-to-public RMS
`0.04054608891852764`, so all 398 retained records remain distinct at the
stated `1e-4` threshold. Recomputing the metric changed only 13
nearest-ID/distance metadata records (11 global, 2 continuation); candidate
coordinates, payload hashes, and verifier scores did not change.

The boundary convention also has an explicit regression. Geometric domain
slacks are ordered `C/B/A`, while zero-barycentric edge modes are ordered
`A/B/C`; the conversion is `(2, 1, 0)`. The earlier pre-fix comparison is
clearly scoped in the receipt as a private, non-publicly-replayable audit over
excluded v1 runs. Its counts are not part of the public replay assurance.

## Two different replay boundaries

### Public coordinate-free receipt replay

The public exporter copies the manifest allowlist to:

`src/campaign/geometry/heilbronn_flow_topology_global/`

From the public repository root, run:

```bash
python3.11 -I \
  src/campaign/geometry/heilbronn_flow_topology_global/public_replay.py
```

This test uses Python 3.11's standard library only. It authenticates every
allowlisted byte; checks receipt arithmetic, hashes, parent counts, scope
labels, and the absence of candidate arrays; and verifies that the private v1
comparison is labeled nonreplayable. It does **not** open raw runs, a campaign
snapshot, the corpus, NumPy/SciPy/Torch, or any verifier. No downloaded or
local verifier is executed by the public test.

That boundary is deliberate: coordinates and raw logs are excluded, so the
public test cannot independently recompute the geometric scores. The receipt
records that the private audit did so; it does not turn those private numerical
checks into a stronger public claim.

### Private full numerical reproduction

The search and private audit require Python `>=3.11` plus the versions bounded
in `requirements.txt`:

- NumPy `>=1.26,<3`
- SciPy `>=1.11,<2`
- PyTorch `>=2.1,<3`

Install into a private environment from the campaign checkout:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r \
  campaign/geometry/heilbronn_flow_topology_global/requirements.txt
```

Reproduce the two bounded searches:

```bash
.venv/bin/python \
  campaign/geometry/heilbronn_flow_topology_global/global_search.py \
  --population 48 --steps 1000 --top-k 3 \
  --maxiter 1400 --lbfgs-maxiter 900 \
  --mutation-depths 4,5,6,8,11 \
  --mutation-parents 10 --mutation-population 8 --mutation-steps 700 \
  --seed 20260815 --stamp REPRO_GLOBAL

.venv/bin/python \
  campaign/geometry/heilbronn_flow_topology_global/global_search.py \
  --skip-template-phase --population 2 --steps 2 --top-k 1 \
  --maxiter 2000 --lbfgs-maxiter 1200 \
  --mutation-depths 4,5,6,8,11 --mutation-parents 4 \
  --mutation-population 256 --mutation-top-k 4 \
  --mutation-steps 2000 --mutation-freeze-fraction 0.65 \
  --seed 2026081502 --stamp REPRO_CONTINUATION
```

The advertised arbitrary run names are accepted by the audit. Write their
receipt away from the canonical freeze:

```bash
.venv/bin/python \
  campaign/geometry/heilbronn_flow_topology_global/audit_packet.py \
  campaign/geometry/heilbronn_flow_topology_global/runs/REPRO_GLOBAL \
  campaign/geometry/heilbronn_flow_topology_global/runs/REPRO_CONTINUATION \
  --receipt-out \
  campaign/geometry/heilbronn_flow_topology_global/runs/REPRO_AUDIT/receipt.json
```

The private audit checks each payload hash, executes two fresh copies of the
SHA-pinned local verifier per run, separately recomputes all 165 triangle
areas, and recomputes true squared-cost Hungarian RMS metadata. It also reads
the frozen snapshot and research corpus. These dependencies are intentionally
absent from the public packet.

For the canonical local packet, write the receipt and freeze the manifest
**last**:

```bash
.venv/bin/python \
  campaign/geometry/heilbronn_flow_topology_global/audit_packet.py \
  campaign/geometry/heilbronn_flow_topology_global/runs/global-20260815T100000Z-v2 \
  campaign/geometry/heilbronn_flow_topology_global/runs/continuation-20260815T103000Z-v2 \
  --write

python3.11 \
  campaign/geometry/heilbronn_flow_topology_global/freeze_publication.py
```

`freeze_publication.py` copies only the allowlist into a temporary public
`src/campaign/...` layout inside this subtree, runs `public_replay.py` under
isolated Python, and writes `PUBLICATION_MANIFEST.json` only after that copied
test passes.

## Why this lane

The global-optimization literature models signed triangle determinants with
MIQCP/QCP disjunctions, bound tightening, symmetry breaking, and adaptive
discretization [1]. Earlier recursive rectangle-cell branch-and-bound work is
certifying but already required roughly 31 GPU-days at `n=9` [1], making it a
poor first discovery lane at continuous `n=11`. FlowBoost instead supplies a
practical smooth-absolute, annealed-soft-min, stochastic-relaxation,
L-BFGS-B, and active max-min stack [2]. AlphaEvolve projected proposed points
into the bounding triangle [3], while GigaEvo combined quasi-random starts,
annealing, critical-triangle repair, and quality-diversity archives [4]. The
recent optimize-then-refine work describes the appropriate exact follow-up if
a new active topology is discovered [5].

This implementation transfers those ideas without copying paper code or
candidate arrays.

## References

[1] A. Monji, A. Modir, and B. Kocuk. “Solving the Heilbronn Triangle Problem
using Global Optimization Methods.” *arXiv* (2025).
<https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L7-L22,L27-L79,L89-L97,L168-L176>

[2] G. Bérczi, B. Hashemi, and J. Klüver. “Flow-based Extremal Mathematical
Structure Discovery.” *arXiv* (2026). <https://arxiv.org/html/2601.18005>

[3] B. Georgiev, J. Gómez-Serrano, T. Tao, and A. Z. Wagner. “Mathematical
exploration and discovery at scale.” *arXiv* (2025).
<https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L624-L640>

[4] V. Khrulkov et al. “GigaEvo: An Open Source Optimization Framework Powered
By LLMs And Evolution Algorithms.” *arXiv* (2025).
<https://paperclip.gxl.ai/citations/papers/arx_2511.17592#L1-L20,L33-L46,L76-L98>

[5] N. Sudermann-Merx. “From Computational Certification to Exact Coordinates:
Heilbronn's Triangle Problem on the Unit Square Using Mixed-Integer
Optimization.” *arXiv* (2026). <https://arxiv.org/html/2603.11107>
