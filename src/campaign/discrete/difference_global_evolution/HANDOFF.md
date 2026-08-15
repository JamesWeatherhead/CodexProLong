# Handoff: global changed-core Difference Bases evolution

## Exact live boundary

- problem: `difference-bases`
- public leader: submission `634`
- leader payload SHA-256:
  `02b16426d5a66feb480d79c7e1c7c26bb18ffb50730c5a2c76861584ec59183b`
- verifier SHA-256:
  `a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`
- leader: 360 marks, coverage `49,109`, score `129600/49109`
- strict gate: score `< 2.6390274685066077`
- first gate-capable coverage at 360 marks: `49,110`

## Non-overlap

This lane does not repeat the exact one-/two-swap proof, translated four-block
offset repair, fixed Wichmann/Leech family scan, shell construction, Singer
four-block parameter search, or quadratic relative-difference-set embedding.
It maintains unrestricted 360-element integer sets and deliberately accepts
higher-deficit target-covered states to change the residue core.

## Method

`solver.py` uses literal Python-integer difference bitsets. A target-entrance
enumeration exactly screens all one-coordinate old/new witnesses of `49,110`.
The evolutionary portfolio then combines multi-mark ALNS destroy/repair,
full-coordinate target-preserving swaps, gap mutations, and mark/gap
crossovers. The full-coordinate operator screens every position `1..65,000`
for 12 selected removals, then exactly replays all shortlisted candidates.
Approximate NumPy multiplicity is ranking only and cannot authorize a result.

The final run is:

`runs/20260815T091243Z_final600/`

- solver source SHA-256:
  `90dbe434724367d67716eb9d5d083d5b2a305dd57b4839f1487cfbf2ee4381de`
- config SHA-256:
  `c4b63fdbbce8c20d6a1a08f5d324e5ca3b6dda1194ee13c339dd496c5378e7fe`
- events SHA-256:
  `7de78d99eaaa0c36f90d7e4e731c4947110ee752486765f4188b1d4e1b5583bf`
- checkpoint SHA-256 (private/excluded):
  `bcee6befb90ea7bf1b8faf86d7fb274b7d365c59d3b90995b6cbb031b9138fa8`
- summary SHA-256:
  `7fd0ff5aea3cda4808831770ee3876ab842e30f6b5e07efb0f0f818ac3ae8631`
- 600 proposals / 130 accepted / 312.1490815000143 seconds
- maximum accepted distance: five leader marks removed/replaced
- best target-covered frontier: 178 missing values, prefix `33,087`
- exact incumbent remained: one missing value, prefix `49,109`
- no gate-clearer

`audit_run.py` independently recomputed all 27 retained arrays without
importing `solver.py`, matched every recorded payload/marks hash and metric,
and emitted `receipt.json`.

## Claim boundary

This is a bounded heuristic no-go, not a proof for all 360-mark sets, all
integer ranges, or all changed-core distances. The five-mark distance is the
largest *accepted* state in this 600-proposal trajectory; the implemented
operators can change more marks, but the acceptance dynamics did not retain a
better farther state. The exact claims are only:

1. all retained arrays replay exactly under the clean-room formula;
2. none clears the frozen strict gate;
3. the frozen run and its hashes/stats are reproduced by the audit receipt.

No Arena submission, post, comment, issue, or GitHub mutation was performed.

## Publication

Publish only paths listed in `PUBLICATION_MANIFEST.json`. In particular, do
not publish any `checkpoint.json`, `public_latest.json`, smoke/pilot directory,
or unlisted file. The final public config/events/summary contain metadata and
hashes but no construction arrays.

From a public `CodexProLong` checkout, replay the standalone allowlist with:

```bash
python3 src/campaign/discrete/difference_global_evolution/test_packet.py
```

In the canonical research checkout, omit the leading `src/`. The deeper
`audit_run.py` replay additionally requires the private excluded checkpoint and
is therefore documented only in `README.md` as a canonical command. The
standalone check supports Python 3.9+; `solver.py` and `audit_run.py` require
Python 3.10+ for `int.bit_count()` and also require NumPy.
