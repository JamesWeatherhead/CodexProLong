# Circle-packing multigraph/precision handoff

## Outcome

No gate-clearer was found.  The frozen live gate is strictly above
`2.635983095360844`; verifier SHA-256 is
`2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab`.
The API schema is exactly `{"circles": "array of [x, y, r] triples"}`.

The incumbent contact graph has a verifier-only tolerance ceiling of
`2.635983095281623`, just `7.922107414515267e-11` below the gate.  It uses
`9.999999994736442e-10` of circle-pair overlap.  Walls have zero tolerance
and zero overrun.  Its physical-strict counterpart scores
`2.6359830849176076`.

## New negative frontier

For each of three graph-distinct seeds, every pair of active contacts was
released.  A 513-direction sweep of the resulting two-dimensional linearized
flex cone identified vertices at which two inactive pair/wall constraints
became active; each replacement graph was then solved nonlinearly and replayed
with the unchanged verifier.

- 9,270 replacement graph systems solved
- 8,699 literal-verifier accepted labeled systems
- 5,147 distinct unlabeled Weisfeiler-Lehman graph classes across all seeds
- best changed graph from the strongest noncanonical seed:
  `2.63429241243708` verifier-only, `2.6342924020713743` physical-strict
- best changed graph reached from the canonical basin:
  `2.630713207896856` verifier-only, `2.6307131975275695` physical-strict

This closes exhaustive codimension-two active-contact replacement from the
canonical, neutral edge-flip, and strongest public noncanonical seed at the
chosen linear-visibility resolution.  It does not prove that more distant
three-or-more-contact graph mutations are impossible.

## External asset audit

An indexed ClaudeEvolve README claims `2.6359835671240317`, but no coordinates
for that headline survived bounded exact-score, filename, fork, Wayback, and
Common Crawl searches.  The same project's paper gives a complete strict table
with score `2.6359829286`; the recovered 12-decimal table independently replays
at exactly `2.635982928558`, with minimum pair gap
`9.998709471492617e-09` and minimum wall slack
`9.99999993922529e-09`.  It is valid but `1.6680284398162826e-07` below the
gate.  The headline is therefore unsupported by recovered candidate bytes and
must not be submitted.

## Reproduction

```bash
# From the EinsteinArena repository root:
.venv/bin/python campaign/geometry/circle_packing_multicontact_precision/freeze_receipt.py
.venv/bin/python campaign/geometry/circle_packing_multicontact_precision/replay_exact.py
.venv/bin/python campaign/geometry/circle_packing_multicontact_precision/replay_external_asset.py
```

Primary frozen outputs are `receipt.json`, `replay_receipt.json`,
`external_asset_replay.json`, and `asset_audit.json`.  No external write was
performed.

Pinned SHA-256 values:

- live verifier: `2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab`
- clean-room `verifier_formula.py`: `ad11321f9c010f03f850f6ebf41fb82533f772dad8b8ee080386de275bce830a`
- `receipt.json`: `044fca92a7f702d3337d0a62dff5e7b9fa0f3aec6071e28db289e588182a81a7`
- `replay_receipt.json`: `03693cd85607412d970b138d83db7a228605e1636a8c397dffe590a397486f55`
- `external_asset_replay.json`: `9c6115a4f976279ab12fd85cd2b91d97f9a19a9f7424d21cb9085e7d062cf1a1`
- recovered ClaudeEvolve table: `b87a7364229f23aeae949f745b678ef36cdf72d5fc60153cbe0cf93e701e6643`
