# Circles in a rectangle changed-topology handoff — 2026-08-15

## Outcome

No strict leaderboard gate-clearer was found and no Arena or GitHub write was
made.  The strongest unchanged offline-controller replay is the known
tolerance-dependent canonical 47-pair/17-wall contact graph:

- live leader: `2.365832385207997`;
- required improvement: `1e-10`, so the score must be strictly greater than
  `2.365832385307997`;
- replayed score: `2.365832385227916`;
- margin over the leader: `1.991873332940486e-11`;
- remaining gate shortfall: `8.008126667059514e-11`;
- verifier SHA-256:
  `c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9`.

The encoded rectangle is `1.0232688969582717` by
`0.9767311040417284`; its minimum literal pair slack is
`4.215971933352133e-17`, its perimeter slack is zero, and its minimum radius
is `0.07474150053446214`.  This payload deliberately uses the verifier's
explicit `1e-9` overlap and perimeter allowances.  It is therefore a
literal-verifier artifact, not a strict disjoint-circle construction.

The same active system at zero mathematical violation has high-precision
objective
`2.3658323759108327415720797222914393717978579202568`; its encoded score in
this run is `2.3658323759108324`.  The roughly `9.32e-9` difference between
the strict and tolerance-dependent roots must not be described as a geometric
improvement.

## Frozen receipt

- Candidate:
  `runs/20260815T022200Z/stochastic_relax/topologies/cdea3037dafa48f9/candidate.json`
- Artifact-file SHA-256:
  `0423ef27077517c0b7b60ea482f822e7b1b363e4733f6e9f9887055aa534d93c`
- Controller canonical-JSON SHA-256:
  `dec42df705d59fb35d9573b3201a983b4ef661fb4cac1a65dcfeb1c924cf12b1`
- Receipt:
  `../../state/receipts/circles-rectangle/20260815T022302550954Z-dec42df705d5.json`
- Receipt SHA-256:
  `72840edba68584ec15a673627e6534ed4942965a8c7454e3f6bbb94d813f9d52`

Replay only through the offline controller:

```bash
cd /Users/jacweath/EinsteinArena/campaign
./arena verify circles-rectangle \
  geometry/rectangle_topology/runs/20260815T022200Z/stochastic_relax/topologies/cdea3037dafa48f9/candidate.json
```

The controller independently returned the score and hashes above with
`clears_first_place_gate: false`.

## Corpus and discussion audit

Before searching, `audit_corpus.py` read all 24 retained constructions, all
four problem threads (`#141`, `#142`, `#178`, `#185`), and all 27 retained
replies.  The frozen corpus database SHA-256 is
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.
Up to circle relabeling and rectangle dihedral/transposition symmetry, the 24
public constructions form 11 contact-graph classes.  Fourteen records have a
full-rank 65-equation rigid system, but they collapse to only two invariant
rigid classes:

1. the canonical class led by solution `#1626`, invariant hash
   `28076556a777372983dfc77ea7e86035`;
2. the distinct CHRONOS construction `#1010`, score about
   `2.343316496209888`, invariant hash
   `ed659c370399eecb30aa59dc0efed9c7`.

Audit artifacts:

- `runs/20260815T022500Z/audit/corpus_audit.json`, SHA-256
  `1b2a22c2495fb520ad9dd82c9871adda6bd679c38f7b91950ab62cdc331d7038`;
- `runs/20260815T022500Z/audit/summary.json`, SHA-256
  `5d1bc9e924da98ece97525debf3c11d31c3229dcfa0212c692e6fff064fa8433`.

The retained work already closes same-topology precision polishing,
fixed-center radius LP, 34 one-contact basis releases, nearest-pair forcing,
wall add/drop, non-nearest planar-graph forcing, widened contact scouts, and
ordinary random perturbations.  Repeating any of those lanes is low value.

## Changed-contact searches

### Pain-ranked void and split relocation

The clean-room PAS-PCI adaptation groups circles by radius, ranks them by
squared KKT contact load, relocates the most loaded members to geometric voids,
and also splits narrow voids into two-neighbor relocation seeds.  Centers,
radii, and the rectangle aspect are then optimized together by strict
sequential LP before rigid-root refinement.

The bounded run generated 27 nontrivial seeds and refined 20.  Those endpoints
formed 20 labeled and 17 invariant topologies.  All 17 invariant topologies
are novel relative to the full public corpus.  The best novel graph scored
only `2.359691363376021`, a target shortfall of
`0.006141021931976187`; its strict local score was `2.359691354030148`.

- Summary: `runs/20260815T022100Z/void_relocate/summary.json`, SHA-256
  `ce75d64d0c77ca4f6fe5599ba92efa3659d7a19c1cfc60ec873601f6747467fc`.
- Append-only events: `runs/20260815T022100Z/void_relocate/events.jsonl`,
  SHA-256
  `2fef1bf7183864f216450ca188eedfee35b0fe1adffa5a7068a553cb617b9623`.

### Global fields, aspect motion, and exact radius LP

The clean-room FlowBoost-inspired lane perturbs all centers with five global
field families (independent, shear, vortex, wave, and quadrant), kicks the
aspect ratio, runs staged elastic relaxation, solves the fixed-center/fixed-
aspect radii subproblem exactly with SciPy HiGHS, then applies strict
free-aspect SLP and rigid-root refinement.  The official FlowBoost repository
was inspected read-only at commit
`95d6feef0f6c9aaa2c28727910b2eecebeeb9026`; it has no root license, and no
upstream source was copied or executed.

All 80 deterministic seeds completed.  They reached seven invariant
topologies: the two public rigid classes and five novel classes.  The best
endpoint returned to the canonical class and produced the frozen controller
receipt above.  The strongest newly reached global-field topology was already
below `2.346`.

- Summary: `runs/20260815T022200Z/stochastic_relax/summary.json`, SHA-256
  `8fb3917fba0d45e158cfe091aa52659d833dc0b46f382cf7a8b30b04401b36bc`.
- Append-only events: `runs/20260815T022200Z/stochastic_relax/events.jsonl`,
  SHA-256
  `a7812dc25d4841ae3bd512960f6e8a43809fc45ca9cdaa642116fe1d079f38da`.

Combined, the two lanes rigid-refined 100 endpoints into 24 invariant
contact-graph classes.  Twenty-two classes were absent from every retained
public construction.  None approached the canonical objective: the best novel
class remained about `0.00614` below the gate target.

## Reproduction

```bash
cd /Users/jacweath/EinsteinArena/campaign

../.venv/bin/python geometry/rectangle_topology/audit_corpus.py \
  --stamp REPRO_RECT_AUDIT

../.venv/bin/python geometry/rectangle_topology/void_relocate.py \
  --seed geometry/runs/20260815T035100Z/circles-rectangle/candidate.json \
  --corpus-solution-ids 1010 \
  --audit geometry/rectangle_topology/runs/20260815T022500Z/audit/corpus_audit.json \
  --grid-size 35 --spaces-per-circle 3 --pain-per-group 1 \
  --split-pairs 6 --split-spaces 2 --split-angles 4 \
  --rounds 18 --max-seeds 120 --stamp REPRO_RECT_VOID

../.venv/bin/python geometry/rectangle_topology/stochastic_relax.py \
  --seed geometry/runs/20260815T035100Z/circles-rectangle/candidate.json \
  --corpus-solution-ids 1010 \
  --audit geometry/rectangle_topology/runs/20260815T022500Z/audit/corpus_audit.json \
  --scales 0.004,0.01,0.025,0.05 --repeats 2 \
  --aspect-kick-scale 1 --penalties 1e3,3e4,1e6 \
  --elastic-maxiter 220 --slp-rounds 22 --max-seeds 80 \
  --stamp REPRO_RECT_FLOW
```

Program SHA-256 values:

- `audit_corpus.py`:
  `1c22d82b01484e05ecd4d8d563903df7d64e1a03f3695901d9b8fd1d96c23337`;
- `core.py`:
  `042757bf680bceb3d1f5bebcec53d9bc8e04042fe0afeda06d83ff3b3f87fbd6`;
- `void_relocate.py`:
  `e28a954c9180e67597682d4fc8dabe674fbcc2955a4ca29a82d8a7aec449cc34`;
- `stochastic_relax.py`:
  `208e621709a9b85cbfd602be360d2046b34c3f0bf1b2dfe78f575d25f6399f7d`.

## Frontier and next distinct route

This is bounded evidence, not a proof over all contact graphs.  It does show
that two qualitatively different basin-hopping families found 22 public-novel
rigid graphs without producing a near competitor.  The next genuinely
different route is an explicit simultaneous multi-active homotopy or
symmetry-quotiented contact-graph enumeration: release and introduce several
contacts together, continue through rank-deficient transitions, and certify
each rigid child.  More one-edge forcing, local trust expansion, or unguided
random perturbation would repeat closed work.

## Literature and provenance

The benchmark is the exact 21-circle, perimeter-four rectangle objective
described in AlphaEvolve; that source characterizes later gains in this family
as continued numerical refinement [1].  The pain-ranked void, narrow-space
split, group-swap, LBFGS, and structured restart ideas come from PAS-PCI [2].
The global-field lane uses only the high-level geometry-aware stochastic-search
and exploration ideas described by FlowBoost [3], plus a clean-room exact
radius LP implementation.

1. Bogdan Georgiev, Javier Gómez-Serrano, Terence Tao, and Adam Zsolt Wagner,
   “Mathematical exploration and discovery at scale,” arXiv (2025),
   [lines 513–516](https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L513-L516).
2. Kun He, Mohammed Dosh, and Shenghao Zou, “Packing Unequal Circles into a
   Square Container by Partitioning Narrow Action Spaces and Circle Items,”
   arXiv (2017),
   [lines 76–80, 84, 87–93, 123–126](https://paperclip.gxl.ai/citations/papers/arx_1701.00541#L76-L80,L84,L87-L93,L123-L126).
3. Gergely Bérczi, Baran Hashemi, and Jonas Klüver, “Flow-based Extremal
   Mathematical Structure Discovery,” arXiv (2026),
   [line 1](https://paperclip.gxl.ai/citations/papers/arx_2601.18005#L1),
   official repository `https://github.com/berczig/FlowBoost`, commit
   `95d6feef0f6c9aaa2c28727910b2eecebeeb9026`.
