# Geometry campaign handoff — 2026-08-14

All research code uses public GET endpoints and local verifier replay. No tool in
this directory posts discussions or submits solutions. Searches keep every
vector finite, nonzero, and normalized; verifier/domain bugs are out of scope.

## Live inventory

The ten geometry problems were refreshed in:

`snapshots/geometry_20260814T224631Z.json`

The two attackable legitimate frontiers are `kissing-number-d12-842` and
`kissing-number-d11-605`. Both minimize overlap loss and currently have
`minImprovement = 0`, so any reproducible decrease is leaderboard-relevant.
The older packing/Tammes/Thomson/Heilbronn/min-ratio frontiers are rigid at
their present gates; D12/841 is archived; D11/594's zero-score lane is not a
legitimate target for this campaign.

## Primary result: D12 / 842

- Live leader at search start: `0.547073707876257` (ExoMind-TTS).
- Best exact live-verifier replay: `0.5470735423441564`.
- Improvement: `1.65532100582233e-7`.
- Payload: `runs/20260814T225047Z/kissing-number-d12-842/best.json`.
- Event log: `runs/20260814T225047Z/kissing-number-d12-842/events.jsonl`.
- Verifier SHA-256:
  `54dc5d8c02a6370dfd24688da5c5745399437e4e5d3b9fdc6c523bb0112f88be`.
- Shape and domain checks: 842x12, all finite/nonzero, row norms in
  `[0.9999999999999998, 1.0000000000000002]`.
- Solution `#2499` evaluated at this score and is the live rank-1 entry.

Reproduce:

```bash
/Users/jacweath/EinsteinArena/.venv/bin/python \
  /Users/jacweath/EinsteinArena/campaign/geometry/verify_payload.py \
  kissing-number-d12-842 \
  /Users/jacweath/EinsteinArena/campaign/geometry/runs/20260814T225047Z/kissing-number-d12-842/best.json
```

## Secondary result: D11 / 605

- Live leader at search start: `1.7102381876822141` (ExoMind-TTS).
- Best exact live-verifier replay: `1.7102381876374992`.
- Improvement: `4.4714898450592955e-11`.
- Payload: `runs/20260814T225229Z/kissing-number-d11-605/best.json`.
- Event log: `runs/20260814T225229Z/kissing-number-d11-605/events.jsonl`.
- Verifier SHA-256:
  `9bb3804dc09dfaa3400beced301c2fd446123e765053dd0f4b04e5686191d4ef`.
- Shape and domain checks: 605x11, all finite/nonzero, row norms in
  `[0.9999999999999999, 1.0000000000000002]`.
- This is a precision-level but independently replayed reduction of the intended
  overlap objective, obtained by moving active-contact vertices rather than by
  altering the verifier domain.
- Solution `#2500` evaluated at this score and is the live rank-1 entry.

The reproducible method and its limitations were shared as replies #1074 and
#1075 on existing discussion threads #240 and #241. Local idempotency receipts
are in `receipts/`.

Reproduce:

```bash
/Users/jacweath/EinsteinArena/.venv/bin/python \
  /Users/jacweath/EinsteinArena/campaign/geometry/verify_payload.py \
  kissing-number-d11-605 \
  /Users/jacweath/EinsteinArena/campaign/geometry/runs/20260814T225229Z/kissing-number-d11-605/best.json
```

## Method and next search

`slp_search.py` constructs a sparse sequential LP over tangent-space motions of
currently overlapping vertices. It linearizes all incident pairs within a
configurable distance margin, solves a bounded hinge-loss model, renormalizes,
and accepts a step only after the unchanged live Decimal verifier improves.
Every accepted payload is atomically checkpointed.

For D11, an all-605-variable continuation was deliberately stopped after a
60-second LP timeout and two worsening trials. Its partial log and stop note are
under `runs/20260814T225317Z/kissing-number-d11-605/`. The best next bounded
experiment is a block-coordinate SLP over connected components of the exact
60-degree contact graph, rather than another monolithic all-point LP. A more
substantive advance still requires a different 605-point architecture: the
published 604-point frame is saturated and its attempted extra point has three
large overlaps.

## Packing gate audit

The packing verifiers permit approximately `1e-9` geometric violations. The
campaign treats those allowances only as verifier diagnostics: every local
candidate separately requires nonnegative exact-domain pair and container
slack.

### Circle packing, n=26 square

- Live leader: `2.635983095260844`; target: `2.635983095360844`.
- Best strict-domain score: `2.635983084916047`.
- Shortfall: `1.0444797027275854e-8`.
- Payload: `runs/20260814T225916Z/circle-packing/best.json`.
- Event log: `runs/20260814T225916Z/circle-packing/events.jsonl`.
- Verifier SHA-256:
  `2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab`.
- Strict slack: pair `9.46e-14`, wall `1.00e-13`.
- Search coverage: seven distinct public source geometries, 32 bounded
  restarts, and 141 intermediate labeled contact signatures. Every competitive
  trajectory returned to the known 58-pair/20-wall basin.

The public leader itself has minimum pair slack about `-9.98e-10`; its score is
therefore not a mathematically disjoint-circle construction. The highest
strict public/campaign basin cannot clear the present tolerance-inflated gate
without a genuinely new contact topology.

### Circles in a rectangle, n=21

- Live leader: `2.365832385207997`; target: `2.365832385307997`.
- Best strict-domain score: `2.365832375910829`.
- Shortfall: `9.397168376779064e-9`.
- Payload: `runs/20260814T230726Z/circles-rectangle/best.json`.
- Event log: `runs/20260814T230726Z/circles-rectangle/events.jsonl`.
- Verifier SHA-256:
  `c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9`.
- Decimal-real strict slack: pair
  `1.9202708840160429e-16`, perimeter `4.6e-16`.

The final rectangle payload comes from a 100-digit Newton solve of the canonical
47 pair contacts + 17 wall contacts + active perimeter equation. That 65-by-65
active Jacobian has rank 65 and smallest singular value `0.2575430975`; the
high-precision objective is
`2.3658323759108327415720797222914393717978579202568`. A multi-source strict
SLP explored 95 intermediate labeled pair-contact signatures before refinement.
This strongly closes precision polishing of the incumbent topology: the live
leader spends approximately the full verifier tolerance (`-9.99e-10` pair
slack and `-9.90e-10` perimeter slack), so a legitimate gate-clearer again
requires a new topology.

Reproduce the two packing verifier scores:

```bash
/Users/jacweath/EinsteinArena/.venv/bin/python \
  /Users/jacweath/EinsteinArena/campaign/geometry/verify_payload.py \
  circle-packing \
  /Users/jacweath/EinsteinArena/campaign/geometry/runs/20260814T225916Z/circle-packing/best.json
/Users/jacweath/EinsteinArena/.venv/bin/python \
  /Users/jacweath/EinsteinArena/campaign/geometry/verify_payload.py \
  circles-rectangle \
  /Users/jacweath/EinsteinArena/campaign/geometry/runs/20260814T230726Z/circles-rectangle/best.json
```

### Literal verifier-tolerance ceiling

A follow-up campaign deliberately used the verifiers' explicit `1e-9`
allowances and labels every artifact tolerance-dependent.  It solved the
unchanged active systems at 100-digit precision, first at zero violation and
then at the exact tolerance boundary.

- Square packing: the 58-pair/20-wall system has full rank 78.  At pair
  overlap exactly `1e-9`, its high-precision objective is
  `2.635983095281624698268961702...`, still `7.92193e-11` below the strict
  leaderboard gate.  A `2e-15`-buffered payload replays in Docker at
  `2.6359830952815937`, only `2.07496e-11` above the leader.  All active KKT
  multipliers are positive, ranging from `0.0106061` to `0.4269004`.
- Rectangle packing: the 47-pair/17-wall/perimeter system has full rank 65.
  At pair overlap and perimeter overrun both exactly `1e-9`, its
  high-precision objective is `2.365832385227916553616663352...`, still
  `8.00808e-11` below the gate.  The buffered Docker score is
  `2.365832385227898`, only `1.99010e-11` above the leader.  All active KKT
  multipliers are positive, from `0.1143742` to `1.1829162`.

Thus merely consuming the remaining verifier slack cannot clear either
`1e-10` gate in the incumbent topology; an actual topology improvement of
roughly `8e-11` is still necessary.  No submission or discussion post was
made.

Artifacts and receipts:

- Square summary:
  `runs/20260815T035000Z/circle-packing/summary.json` (SHA-256
  `0a6684bd36d52334ad50ee267a4fde9dcf36d377df53ee7e61a35b5e52f1b548`).
- Rectangle summary:
  `runs/20260815T035100Z/circles-rectangle/summary.json` (SHA-256
  `0ed05540096c8bcb8eef1bf777eb23094f1032aef98b92935c4d58aade38e603`).
- Offline verifier receipts:
  `../state/receipts/circle-packing/20260815T012622298989Z-29636addc7b5.json`
  and
  `../state/receipts/circles-rectangle/20260815T012622297420Z-9d4e289e2bb8.json`.

Reproduce the roots, then replay only through Docker:

```bash
../.venv/bin/python geometry/packing_tolerance_refine.py \
  circle-packing \
  geometry/runs/20260814T225916Z/circle-packing/best.json \
  --digits 100 --stamp REPRO_SQUARE_TOLERANCE
../.venv/bin/python geometry/packing_tolerance_refine.py \
  circles-rectangle \
  geometry/runs/20260814T230726Z/circles-rectangle/best.json \
  --digits 100 --stamp REPRO_RECTANGLE_TOLERANCE
./arena verify circle-packing \
  geometry/runs/REPRO_SQUARE_TOLERANCE/circle-packing/candidate.json
./arena verify circles-rectangle \
  geometry/runs/REPRO_RECTANGLE_TOLERANCE/circles-rectangle/candidate.json
```

## Tammes-50 strict unit-sphere pass

The full frozen corpus contains 27 constructions and all 31 replies in three
threads.  A new symmetry audit answers an open question in threads #118/#224:
the genuine all-on-sphere incumbent has an exact rotational D6 group of order
12.  Its 50 vertices split into four generic 12-point orbits plus two
antipodal poles.  The D6 reconstruction matches the public coordinates within
`1.2124e-15` and reproduces the score within `3e-16`.

This reduces the symmetric construction family to eight parameters.  Four
warm and four cold differential-evolution runs made 540,320 objective
evaluations.  After constrained epigraph polishing, every run returned to the
same 102-edge contact graph and score `0.5134720846805647`; no strict-sphere
candidate improved the incumbent.

Canonical summary:
`runs/20260815T034000Z/tammes-problem/summary.json` (SHA-256
`ae7f3435faf7ee2ed9b6de2178b7dae847baf90bad5f69f953d2f2be5285b71f`).
Search program: `tammes_d6_search.py` (SHA-256
`39926a169772d22bcdfd444365a987907876d133db2e1d82156c180c21e477b0`).
Every generated point was finite and unit norm; the zero-norm/unit-ball
verifier mismatch was not used.  This closes only the bounded D6 family
search, not arbitrary 50-point sphere codes, and produced no external action.

Reproduce:

```bash
../.venv/bin/python geometry/tammes_d6_search.py \
  --trials 8 --maxiter 450 --population 160 --stamp REPRO_TAMMES_D6
```

## Thomson pivot

A six-restart tangent-coordinate L-BFGS audit (kicks `0` through `1e-6`) of the
live n=282 leader produced no verifier decrease. The best stayed
`37147.29441846226`, versus the gate target `37147.29441746226`. The normalized
payload is finite/nonzero with norms in
`[0.9999999999999999, 1.0000000000000002]`; verifier SHA-256 is
`4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af`.
Run artifacts are under `runs/20260814T230703Z/thomson-problem/`.

### Topology-changing global-basin audit

The full public problem, all 14 public solutions, and all four discussion
threads/replies were refreshed in
`snapshots/thomson-problem_20260814T234236Z.json`.  Public results and the
leader's spherical Delaunay graph show a sharp structural split: the incumbent
is the defect-minimal `(5: 12, 6: 270)` T=28 Goldberg topology, while the next
public basin at `37147.52530668977` contains one extra 5/7 defect pair.

`thomson_global_basin.py` ran 48 contact-scale, topology-changing seeds:

- 12 pentagonal-defect cap transports;
- 12 vacancy/interstitial defect relocations;
- 12 forced Delaunay bond flips;
- five structurally distinct public minima and seven accepted
  topology-changing random controls.

Two rounds of tangent L-BFGS per seed used 5,324 total iterations and 5,772
objective/gradient evaluations.  The runs finished in ten graph-distinct
Weisfeiler-Lehman topology classes.  Twenty-nine trials returned to the unique
12-pentagon leader graph.  Every alternate graph remained much higher: the
best one-extra-pair topology was the public `37147.52530668976`; direct
vacancy/interstitial surgery reached `37147.55693416176`.

The best exact Docker replay is `37147.294418462254`, only
`7.275957614183426e-12` below the displayed leader and still
`9.999930625781417e-7` short of the gate.  This is float convergence dust in
the same T=28 graph, not a new construction.  Payload:
`runs/20260814T234800Z/thomson-problem/best.json`; offline receipt:
`../state/receipts/thomson-problem/20260814T234737334915Z-74de8b51d666.json`.
Verifier SHA-256:
`4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af`.

Reproduce:

```bash
../../.venv/bin/python thomson_global_basin.py \
  --stamp REPRO_THOMSON --trial-limit 48 --relax-rounds 2 --maxiter 700
cd ..
./arena verify thomson-problem \
  geometry/runs/20260814T234800Z/thomson-problem/best.json
```

## Minimum-distance ratio n=16 closure

The complete live problem, first 100 solutions, leaderboard, and all 29
discussion threads/replies were refreshed in
`snapshots/min-distance-ratio-2d_20260814T230858Z.json`.

- Live leader: `12.889229907717521` (minimize); current target:
  `12.889229807717522`.
- Verifier SHA-256:
  `2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad`.
- The leader topology has 22 minimum edges and 8 diameter edges. Its rigidity
  matrix has rank `29 = 2n-3`, with one stress dependency and all KKT weights
  positive. The exact edge lists and multipliers are in
  `runs/20260814T231106Z/min-distance-ratio-2d/active_set.json`.
- A 100-digit Newton solve of the square active system gives
  `12.8892299076940063123234388343458553...`; its float64 verifier score is
  `12.88922990769401`, only `2.3511859e-11` below the live leader and therefore
  not gate-clearing. Payload SHA-256 is
  `1627e06f81f2448ad5e05ea0f75c321c8b66a4fa0029e88610b4671e1924bbf9`.
- A depth-four contact campaign tested all `C(8,4)=70` weakest-contact
  quadruples at two forcing gaps, with and without promotion of the closest
  inactive edge: 280 trials and 227 labeled topologies. The best forced release
  face scored `12.889372676159294`; the best promoted `(1,6)` face scored
  `12.895159504161988`. Every unconstrained valid polish returned to the
  canonical active root.

Artifacts are under `runs/20260814T231106Z/min-distance-ratio-2d/` (exact
root) and `runs/20260814T231326Z/min-distance-ratio-2d/` (topology campaign).

Reproduce:

```bash
../../.venv/bin/python min_distance_active_refine.py --digits 100 --iterations 10
../../.venv/bin/python min_distance_topology_search.py \
  runs/20260814T231106Z/min-distance-ratio-2d/best.json \
  --weak-edge-count 8 --release-count 4 --trial-limit 70 \
  --gaps 0.005,0.02 --modes release,promote
../../.venv/bin/python verify_payload.py min-distance-ratio-2d \
  runs/20260814T231106Z/min-distance-ratio-2d/best.json
```

## Heilbronn triangle n=11 closure

The live verifier, first 100 solutions, leaderboard, and every reply in all
four discussion threads were refreshed in
`snapshots/heilbronn-triangles_20260814T231406Z.json`.

- Live leader: `0.036529889880030156` (maximize); current target:
  `0.036529890880030155`.
- Verifier SHA-256:
  `6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d`.
- Active triples are
  `(0,1,6)`, `(0,2,4)`, `(0,3,9)`, `(0,4,8)`, `(0,5,9)`,
  `(1,2,3)`, `(1,3,7)`, `(2,5,8)`, `(2,7,10)`, `(3,4,5)`,
  `(3,4,10)`, `(3,6,7)`, `(3,8,9)`, `(4,8,10)`, `(5,6,8)`,
  `(5,9,10)`, and `(6,9,10)`. Boundary contacts are points 0/1 on
  the bottom, 5/8 on the left, and 7/10 on the right.
- Those 17 area equations plus six boundary equations form a rank-23 square
  system in 22 coordinates and the common area; its smallest singular value is
  `0.01814383295`. All 23 KKT multipliers are positive; the smallest active
  triple multiplier is `0.02027811786`.
- The 100-digit root is
  `0.036529889880030216424847127961580112238472866000589...`. Rounding
  to float64 replays at exactly the live score, so it gains nothing toward the
  `1e-9` gate. Exact-root payload SHA-256 is
  `bb81f8055ff6bcf8127d0bf81f694aa78986b8fd5e2d8fe41b92c81b9c658850`.
- Public discussion already records 2,471,800 asymmetric/topology-replacement
  starts with no leader beat; its best distinct basin is
  `0.036167621590172186`.
- Our additional depth-four campaign ran 420 weakest-active-quadruple trials
  (two gaps and release/one-promotion/pair-promotion modes) plus 42 one/two
  boundary-contact releases. It visited 241 canonical labeled faces. The best
  forced depth-four face scored `0.03652984839027851`; the best boundary-release
  face scored `0.036529886803327756`. All 459 intended-domain topology stages
  polished back to the canonical 17+6 topology; three other apparent generic
  outcomes collapsed points and were rejected by the intended-domain check.

Artifacts are under `runs/20260814T231710Z/heilbronn-triangles/` (exact root)
and `runs/20260814T231912Z/heilbronn-triangles/` (topology campaign). There is
no gate-clearing candidate and no external post/submission from this campaign.

Reproduce:

```bash
../../.venv/bin/python heilbronn_active_refine.py --digits 100 --iterations 12
../../.venv/bin/python heilbronn_topology_search.py \
  runs/20260814T231710Z/heilbronn-triangles/best.json \
  --combination-limit 70 --relative-gaps 0.0005,0.005 \
  --active-modes release,promote_one,promote_pair \
  --boundary-depths 1,2 --boundary-gaps 0.0001,0.001
../../.venv/bin/python verify_payload.py heilbronn-triangles \
  runs/20260814T231710Z/heilbronn-triangles/best.json
```

### Exact discrete-family extension

`heilbronn_bnb/` now contains an exact determinant-hypergraph campaign rather
than another incumbent polish.  On the barycentric q=25 grid, a gate-clearer
would require integer determinant numerator at least 23, i.e. score
`23/625 = 0.0368`.  The search proved that no 11-point subset of the full
351-point grid meets that threshold.

The proof covers the exhaustive fixed-corner family and, without corners, all
ten boundary-count orbits modulo D3: `(222)`, `(221)`, `(220)`, `(211)`,
`(210)`, `(200)`, `(111)`, `(110)`, `(100)`, and `(000)`.  The fully interior
case was partitioned over all 37,950 first-selected-pair roots.  The combined
certificate audits 51,494,145 exact DFS nodes and hashes every source interval:

`heilbronn_bnb/runs/20260815T002500Z/heilbronn-triangles/q025_complete_certificate.json`

Certificate SHA-256:
`2cf96140b095b10b0c2a2c310090b9fe78d2c7a0511ce134acf393485022b9fe`.
The incumbent-like `(2,2,2)` family is additionally closed for every q=8–32,
and the full corner-containing family for q=8–25.  This is a discrete lattice
closure, not a continuous Heilbronn proof.  It produced no candidate payload;
therefore no Docker verifier replay, external post, or submission was made.
See `heilbronn_bnb/HANDOFF.md` for exact scope and reproduction.

The follow-on q=30 campaign (threshold `33/900`) completely closes five of ten
non-corner side-count orbits—`(222)`, `(221)`, `(220)`, `(211)`, and `(200)`—and
preserves certified partial intervals for all remaining orbits.  The strongest
partial is 56,318/82,215 fully-interior first-pair roots (68.50%); `(210)` is
203/406 side roots (50%).  Canonical hashed summary:
`heilbronn_bnb/runs/20260815T020000Z/heilbronn-triangles/q030_campaign_summary.json`
(SHA-256
`349ffb0ea5659120f06441a50f39c4f34929716c2cb147bebd122f88b695fe94`).
No feasible leaf was found in 121,384,089 audited nodes.  The next recommended
family is the adaptive q=143 exact mesh documented in
`heilbronn_bnb/ADAPTIVE_Q143.md`.

That q=143 family has now also completed at its initial bounded scope.  Across
all ten rounded/D3-distinct public basins it generated 28 exact SAT stages:
24 are UNSAT and four radius-5-scale stages exhausted the 50,000-conflict cap.
It audited 24,078,131 clauses and 72,460,844 exact labeled-triple
combinations, with no feasible leaf.  Canonical summary:
`heilbronn_bnb/runs/20260815T031000Z/heilbronn-triangles/summary.json`
(SHA-256
`7cc482375bcd6f55401ef9b13372dafe6d64df1ced9c399f9451a7042d8f7655`).
This is a nonuniform-window certificate rather than a full-grid or continuous
closure; exact scope and reproduction are in `heilbronn_bnb/ADAPTIVE_Q143.md`.

## Verification

- `python -m py_compile campaign/geometry/*.py` passes.
- Ruff passes on the newly added/refined campaign programs.
- The D12, D11, square-packing, rectangle-packing, and Thomson payloads were
  independently replayed from disk against freshly fetched verifier source,
  with hashes matching their run snapshots.
