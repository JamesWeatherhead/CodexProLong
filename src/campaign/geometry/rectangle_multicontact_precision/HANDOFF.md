# Rectangle codimension-two/three topology handoff

## Outcome

No gate-clearer was found.  The live leaderboard remained unchanged under a
final GET-only check:

- leader: `2.365832385207997`
- minimum improvement: `1e-10`
- strict target: `> 2.365832385307997`
- verifier SHA-256:
  `c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9`
- schema: `{"circles": "array of 21 [x, y, r] triples"}`

The canonical tolerance root still replays at `2.365832385227916`, only
`8.008127494463224e-11` short of the gate.  It is explicitly verifier-only:
the independent replay measures pair overrun `9.999999717180685e-10` and
perimeter overrun `1.000000082740371e-9`, accepted because the literal
float64 comparison is against the representable value of `2 + 1e-9`.

## Changed-topology search

The perimeter equation remained active in every system.  For each of the two
retained rigid public graph classes, the campaign ran:

1. every one of `C(64,2) = 2,016` simultaneous two-contact releases, followed
   to every visible two-new-contact vertex of the linearized flex polygon;
2. every one of `C(64,3) = 41,664` simultaneous three-contact releases, with
   every non-box vertex returned by direct three-dimensional half-space
   intersection defining a three-new-contact child; and
3. nonlinear literal-tolerance and physical-strict roots, unchanged-verifier
   replay, labeled graph hashes, and unlabeled Weisfeiler-Lehman hashes.

The two seeds are the canonical 47-pair/17-wall/perimeter graph and the only
other rigid public class, solution 1010's 46-pair/18-wall/perimeter graph.

Aggregate frontier:

- linear vertices / graph systems tested: `11,933`
- literal-verifier accepted labeled children: `11,884`
- union unlabeled Weisfeiler-Lehman graph classes: `8,828`
- best changed child: `2.36211732869399` verifier-only
- best changed physical-strict root: `2.3621173193750487`
- changed-topology gap to gate: `0.003715056614007395`

The best changed graph releases pair contacts `(0,15)`, `(11,14)` and the top
wall contact of circle 6, then adds pair contacts `(6,15)`, `(10,19)`, and
`(11,16)`.  Its payload SHA-256 is
`4373d7be1a42b5be67b518352c35fb552ca393466e5981b5ec1b4e2fd4dc7bf1`.

This closes the configured linearized codimension-two and codimension-three
children of both known rigid public classes.  It is not a proof over remote
contact graphs or a certified exact enumeration of nonlinear singular
branches; the three-dimensional vertex enumeration uses float64 Qhull and
then validates every retained child nonlinearly.

## Reproduction

```bash
# From the EinsteinArena repository root:

.venv/bin/python campaign/geometry/rectangle_multicontact_precision/codim2_pivots.py \
  --stamp REPRO_RECT_CODIM2_CANONICAL

.venv/bin/python campaign/geometry/rectangle_multicontact_precision/codim3_pivots.py \
  --stamp REPRO_RECT_CODIM3_CANONICAL

.venv/bin/python campaign/geometry/rectangle_multicontact_precision/freeze_receipt.py
.venv/bin/python campaign/geometry/rectangle_multicontact_precision/replay_exact.py
```

The two distinct-1010 runs use:

```text
--seed campaign/geometry/rectangle_topology/runs/20260815T022200Z/
       stochastic_relax/topologies/0ac751712a4691f5/candidate.json
```

Frozen hashes:

- `verifier_formula.py`: `3d9f1c877c0dc43159c7b33c31bdf8fe366baa74324bfbe9c604b67e1179a460`
- `codim2_pivots.py`: `54f58b937c4b3572a550570074133bc4052d9657d13a0102dcad140f22451d6b`
- `codim3_pivots.py`: `ae0963d58a17d8e37c112cb749fecc38825d445df85fe9c1e325f47881d9764a`
- `freeze_receipt.py`: `0d80948c43ba21d656dd67c96e21da014c0aca88f8c116eff75faca5de04217c`
- `replay_exact.py`: `eab1bee393d655fba32d1800858d5e51b5b4efb5142b27f080077972a13a0744`
- `receipt.json`: `ef77ffec6af00ce878099e2210aeec97058a404df0702cda082e95345a028a94`
- `replay_receipt.json`: `108f6bd2925f9aafe632dcd6db2b7bc3200cdac88fbdf1ae7ee55c7c22938668`

No Arena submission, discussion, vote, issue, commit, or push was made.
