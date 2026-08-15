# Circle-packing-in-square topology handoff — 2026-08-15

## Result

No gate-clearing strict-domain construction was found, and no submission or
external post was made.  The live leader remains `2.635983095260844`; the
required score is strictly above `2.635983095360844`.

The strongest offline-controller replay is the tolerance-dependent neutral
edge-flip root at `2.635983095281624`.  It improves the leader by only
`2.077982230730413e-11` and misses the gate by `7.922018596673297e-11`.
Its strict zero-overlap root is `2.635983084917608`, so it does not improve the
strict incumbent basin.  The controller explicitly reports
`clears_first_place_gate: false`.

- Payload:
  `runs/20260815T021013Z/topologies/1a3ddda1ed2e3083/candidate.json`.
- Physical artifact SHA-256:
  `e03c16d923ab3170442dcbc6c6984f8d34ec67cd7a9ccc87d1d17a6c9008a131`.
- Controller canonical-candidate SHA-256:
  `aec5513d9a987e8d490ad41c7a2fc4d2175472d93112c05fba6b7e0a6681f1ad`.
- Receipt:
  `../../../state/receipts/circle-packing/20260815T021217553153Z-aec5513d9a98.json`
  (file SHA-256
  `99fbedabc950498d7d2767843d8ac9505ac6b5f1401db9772160ab20f96c35ba`).
- Verifier SHA-256:
  `2dee3fad3cfc2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab`.

## Corpus and prior-work audit

The complete frozen problem corpus was read before searching: all 25 retained
solutions, all three discussion threads, and all 26 replies for problem 14.
The corpus database SHA-256 is
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.
This included the incumbent graph, every reported perturbation/contact-swap
negative result, and the strongest distinct public rigid graph, solution
`#1462` at tolerance-root score `2.6342924124370812`.  Thus the runs below do
not repeat the already closed fixed-center radius LP, same-topology precision,
one-contact swap, or small random-block searches.

The mathematical-exploration paper defines the same objective—maximizing the
sum of radii of non-overlapping circles in a square—and describes later gains
as continued numerical refinement [1].  The topology campaign therefore used
two literature-grounded changed-shape families.  PAS-PCI groups circles by
size, ranks painful circles, relocates them into large or matching empty action
spaces, splits narrow spaces into neighbor spaces, and then locally optimizes;
it also prescribes structured perturbation after repeated basin hops [2].
FlowBoost explicitly combines geometric generation with action exploration and
stochastic local refinement for this sum-of-radii circle-packing problem [3].

## Quantified topology frontier

### 1. Exact one-contact continuation

`continue_contacts.py` releases each of the 78 contacts of a rigid source,
traces the resulting one-dimensional equality manifold to the first new
contact, then solves both the strict and literal-`1e-9` systems.  It exhausts
all 78 releases from both the incumbent and public solution `#1462`:

- 156 releases; 151 first-contact crossings and five bounded no-crossings;
- 151 distinct labeled adjacent rigid systems;
- one neutral flip, `(0,21) -> (18,24)`, returns the incumbent objective;
- the next-best non-neutral adjacent graph scores
  `2.6359774051184153`, already `5.6901632087e-6` below the incumbent
  tolerance ceiling;
- best buffered score `2.6359830952816226`, controller replay
  `2.6359830952816226`, not gate-clearing.

Run: `runs/20260815T020538Z/`.  Summary SHA-256:
`b4842bc3fe4263d23b109f995de0d2a28b492a663a62bfbaefdda89efccda5ae`;
events SHA-256:
`6acd97afff93c2b023c76c5ae670492a91a25d63ceab09429afcef095b8471e3`.

### 2. Pain-ranked void/action-space relocation

`void_relocate.py` is a deterministic clean-room PAS-PCI adaptation.  It uses
four radius groups, squared KKT-load concentration for pain ranking, polished
empty-action-space centers, single relocations, and split-neighbor two-circle
relocations.  Every seed is repaired by a strict fixed-centers HiGHS radius LP,
optimized by strict sequential LP, and rigid-root refined.

- 58 generated and optimized seeds: 22 single relocations and 36 split-neighbor
  relocations;
- 58 refined labeled rigid systems;
- best literal score `2.6358957489458694`, short of the gate by
  `8.73464149746539e-5`.

Run: `runs/20260815T020753Z/`.  Summary SHA-256:
`e438b5dc70172162b30eae350817c621d4c79ebe3d498c4f42f0d78e64ff3650`;
events SHA-256:
`f9ec9e50c1f641bd8f422b78e4aabe66676ac115e99a4c0498657ad88374dbbe`.

### 3. Coordinated stochastic relaxation

`stochastic_relax.py` clean-room implements global all-center jitter plus
coordinated shear, vortex, wave, and quadrant-flow fields.  It uses a staged
elastic penalty relaxation, then the same fixed-center radius LP, strict SLP,
and rigid refinement.  This reads only the ideas from the official FlowBoost
repository at commit
`95d6feef0f6c9aaa2c28727910b2eecebeeb9026`; it neither trains FlowBoost nor
copies or executes its code.  No root license was present in that repository.

- 80 seeds: two rigid sources, five perturbation fields, four scales
  (`0.004, 0.01, 0.025, 0.05`), two repeats;
- all 80 optimized and rigid-refined; 23 labeled rigid signatures reached;
- best is the same neutral edge-flip root; no strict or literal gain.

Run: `runs/20260815T021013Z/`.  Summary SHA-256:
`577db131a70af7e90d48fe2084f2291e70c2cd62fcadbbc10d8d27fb4fd58dbc`;
events SHA-256:
`28456d6668a9b578102bb97638af6b7aacc4087958046f210bb570199146ab3e`.

Program SHA-256 values are:

- `continue_contacts.py`:
  `1a0386195597aecf1e8362d74a94c79252aed5e787fe1ebbdc0b31bdb27fefcb`;
- `void_relocate.py`:
  `5da21ca451206048a22f30f8ccd02b4c4ea8e9717dc554a940504c45029bf03c`;
- `stochastic_relax.py`:
  `f2592c5b6864b99776950f88fe4e5da33fa0f6f576ce5a69e690a749854dbc0a`.

## Reproduction

From `/Users/jacweath/EinsteinArena/campaign`:

```bash
../.venv/bin/python geometry/circle_packing_topology/continue_contacts.py \
  --seed geometry/runs/20260815T035000Z/circle-packing/candidate.json \
  --corpus-solution-ids 1462 --release-limit 78 --max-steps 80 \
  --stamp REPRO_CONTACT_CONTINUATION

../.venv/bin/python geometry/circle_packing_topology/void_relocate.py \
  --seed geometry/runs/20260815T035000Z/circle-packing/candidate.json \
  --corpus-solution-ids 1462 --grid-size 35 --spaces-per-circle 3 \
  --pain-per-group 1 --split-pairs 6 --split-spaces 2 --split-angles 4 \
  --rounds 18 --max-seeds 120 --stamp REPRO_VOID_RELOCATE

../.venv/bin/python geometry/circle_packing_topology/stochastic_relax.py \
  --seed geometry/runs/20260815T035000Z/circle-packing/candidate.json \
  --corpus-solution-ids 1462 --scales 0.004,0.01,0.025,0.05 \
  --repeats 2 --penalties 1e3,3e4,1e6 --elastic-maxiter 220 \
  --slp-rounds 22 --max-seeds 80 --stamp REPRO_STOCHASTIC_RELAX

./arena verify circle-packing \
  geometry/circle_packing_topology/runs/20260815T021013Z/topologies/1a3ddda1ed2e3083/candidate.json
```

Each run has atomic checkpoints and an append-only `events.jsonl`.  Downloaded
verifier code is never run on the host.

## Remaining genuinely different route

The local frontier now includes all single-contact continuations, explicit
void relocation/splitting, and broad coordinated center flows.  A meaningfully
different next attack is a simultaneous multi-contact homotopy or explicit
unlabeled contact-graph enumeration with interval-certified realizability.
That would search branch points inaccessible before the first-contact event;
more same-topology polishing, one-edge swaps, or ordinary random perturbation
is not justified by these results.

## References

1. Bogdan Georgiev, Javier Gómez-Serrano, Terence Tao, Adam Zsolt Wagner,
   “Mathematical exploration and discovery at scale,” arXiv (2025).
   https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L513-L516
2. Kun He, Mohammed Dosh, Shenghao Zou, “Packing Unequal Circles into a Square
   Container by Partitioning Narrow Action Spaces and Circle Items,” arXiv
   (2017).
   https://paperclip.gxl.ai/citations/papers/arx_1701.00541#L76-L80,L84,L87-L93,L123-L126
3. Gergely Bérczi, Baran Hashemi, Jonas Klüver, “Flow-based Extremal
   Mathematical Structure Discovery,” arXiv (2026).
   https://paperclip.gxl.ai/citations/papers/arx_2601.18005#L1
