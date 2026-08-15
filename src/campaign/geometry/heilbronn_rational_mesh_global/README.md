# Heilbronn rational-mesh global escape

Outcome: **no gate-clearer**.  The bounded campaign screened every denominator
`q=144..220`, selected the four meshes with the smallest exact integer-threshold
overshoot, and exactly closed 72 distinct finite domains around all public
rounded basins plus deliberately changed boundary/contact topologies.

The live score to beat was `0.036529889880030156`; the strict target was
`0.036529890880030155`.  No payload was produced and nothing was written to the
Arena, GitHub, an issue, a post, or a discussion.

## Exact denominator screen

For a barycentric integer grid of denominator `q`, normalized triangle areas
are integers divided by `q^2`.  Therefore the first gate-clearing numerator is
`ceil(target*q^2)`.  `denominator_screen.json` records all 77 denominators and
all public-seed roundings.  The four smallest exact overshoots were:

| q | required numerator | exact threshold | threshold minus target | best public rounding | deficit |
|---:|---:|---:|---:|---:|---:|
| 156 | 889 | 889/24336 | 3.5238098233678e-7 | 851 | 38 |
| 152 | 844 | 844/23104 | 5.8003409726882e-7 | 789 | 55 |
| 174 | 1106 | 1106/30276 | 6.9440204145287e-7 | 1078 | 28 |
| 210 | 1611 | 1611/44100 | 7.2136486780418e-7 | 1532 | 79 |

The smallest overshoot here is about 27.6 times the earlier `q=143` gate
margin, so this is a genuinely separate, coarser rational-mesh lane.

## Search families

`PUBLIC_V2` closes 34 distinct radius-2 domains: every D3-distinct public
rounding at each selected denominator (9, 8, 9, and 8 domains respectively).

`TOPOLOGY_V2` enumerates 41 cases representing 38 distinct domains:

- nine one-boundary-birth cases and three two-boundary-birth cases from public
  solution #1015's topology-preserving three-boundary rounding;
- all six one-boundary and all fifteen two-boundary deaths from the six-boundary
  leader #630, forcing the surviving incidence pattern exactly;
- eight disconnected, label-aligned cross-basin unions among #630, #1015,
  #1006, and #649 at `q=156` and `q=174`.

Coordinates above a `1e-10` zero tolerance were constrained to remain positive
during rational rounding; smaller numerical residues were treated as intended
zeros. This matters: ordinary nearest rounding collapses #1015 and #1006 onto
the leader's six-boundary topology at both q156 and q174, while #649 collapses
there at q156. The topology phase instead preserves this tolerance-classified
boundary incidence before explicitly birthing or deleting boundary contacts.

Each case first receives an exact product-domain test: if one labeled triple
cannot reach the required integer determinant even when its three point choices
are optimized independently, the whole domain is impossible.  Remaining cases
use an exactly-one SAT model.  For every label triple and each assignment of a
pivot pair, a support clause permits exactly those third-label points whose
integer determinant reaches the threshold.  Exactly-one makes these support
clauses equivalent to enumerating every forbidden triple.

## Result and independent replay

Across 75 enumerated cases (72 distinct domains):

- 18 were closed by exact per-triple product-domain upper bounds;
- 57 rebuilt support formulas returned exact UNSAT;
- there were no timeouts, SAT models, candidates, or verifier payloads.

`case_manifest.json` is the compact deterministic projection of the final raw
runs. `replay_no_go.py` reconstructs every domain from the pinned public
snapshot, checks every domain and clause hash against that manifest, and asks
fresh uncapped CaDiCaL instances to prove all 57 formulas UNSAT. The successful
replay rebuilt 164,140 clauses and used 5,530 conflicts. Its durable record is
`replay_receipt.json`. The same fresh process also converted the public leader's
integer grid at all four denominators and replayed it through the frozen live
verifier; rational and verifier scores agreed within `2.1e-17`. Raw `runs/`
remain local and are not needed for replay.

```bash
.venv/bin/python campaign/geometry/heilbronn_rational_mesh_global/screen_denominators.py \
  --output /tmp/denominator_screen.json

.venv/bin/python campaign/geometry/heilbronn_rational_mesh_global/replay_no_go.py
```

## Scope

This is an exact no-go for the 72 recorded finite **labeled rational-mesh
domains only**.  It is not a proof about every point on any selected mesh, all
meshes `q=144..220`, or the continuous 11-point Heilbronn problem.  CaDiCaL
returned exact UNSAT in fresh processes, but this packet does not include an
independently checkable DRAT/LRAT proof trace.

## Literature grounding

The triangle-domain boundary theorem says that, unless all three vertices are
occupied, an optimum for `n>=5` can be represented with at least four boundary
points, with two on one edge; affine `S3` symmetry strengthens the exact model
[1].  That directly motivated the boundary-birth/death families.  Recursive
fine-grid branch-and-bound, adaptive discretization, and binary discretization
with exact binary-continuous linearization motivated the mesh screen and exact
support representation [2].  Boundary symmetry plus numerical-to-symbolic
refinement supports separating topology discovery from exact certification
[3].  The latter two papers study the square, so only their algorithms—not
their domain-specific theorems—are transferred here.

--------
REFERENCES

[1] N. Sudermann-Merx. "Heilbronn's Problem in the Unit Triangle: Certified Optimal Configurations for up to n <= 8." arXiv (2026).
    https://paperclip.gxl.ai/citations/papers/arx_2607.15021#L1

[2] A. Monji, A. Modir, and B. Kocuk. "Solving the Heilbronn Triangle Problem using Global Optimization Methods." arXiv (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L18-L22,L63-L79

[3] N. Sudermann-Merx. "From Computational Certification to Exact Coordinates: Heilbronn's Triangle Problem on the Unit Square Using Mixed-Integer Optimization." arXiv (2026).
    https://paperclip.gxl.ai/citations/papers/arx_2603.11107#L1

## Frozen hashes

- frozen verifier: `6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d`
- public snapshot: `e6332c0715a82c9e62d9029385a7db1cab46549bf482ff65dca30e9ee5468d90`
- denominator screen: `5d24c5e559e50374b27ae22383fd8c9dbf0ffca14bb4f0342285320375d4d066`
- search source: `67ac382fa33eafbfec8233f59b0269533e2cecafbcb8c05c754843024fc77271`
- public summary: `237a4e4d83225678fc4cddfadd25e58a27eb17bd3d101b8962f315ec70d390ce`
- topology summary: `e9687326a5447a8e715a5ecb5538f93f0cedcbabaf2047661af9e74074c45523`
- compact case manifest: `4aef22d0653edbb2833bdcc2cd6bf1a4ea070cef32ad0666f44aed53756203c9`
- manifest compiler: `0f212096a09cf8d6c56a28fc7386ddae0b6f08414bc81231a5c06f0015e847f2`
- replay source: `9b4da41c5281bb5eeb4b99945666e1c46b194f11c86669ba4e976dada5fac914`
- replay receipt: `81bb128183c221c3b7998cff6935a6b28d8937716a5f3f80e9e9d12e1d3d3a25`
