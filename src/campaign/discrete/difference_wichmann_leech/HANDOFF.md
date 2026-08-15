# Handoff: Wichmann/Leech classical interval construction

## Frozen result

No gate-clearer exists in the bounded nondegenerate Wichmann family audited
here. The run exhausts every integer pair

```text
r >= 1, s >= 0, 4r+s+3 <= 2000
```

and all Wichmann extensions by the exact monotonicity reduction documented in
the README and run receipt.

- parameter pairs enumerated: **498,002**;
- tuple-stream SHA-256:
  `0f43b984899e5ac20cbb3ea956f953c618b040cccd396137fed34ec4f57e86bf`;
- live leader: `2.639027469506608`;
- strict gate: `< 2.6390274685066077`;
- frozen verifier SHA-256:
  `a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`.

Every selected construction has a generated integer payload, a canonical
payload hash, an exact rational score, a bitset proof that each difference
`1..v` occurs, and a literal score replay. A separate read-only audit loaded the
unchanged frozen verifier and obtained byte-identical Python float scores for
all five control/frontier payloads; only its compact receipt is published.

## Quantified frontier

The strongest nondegenerate Wichmann ruler anywhere under the 2,000-mark schema
limit is the small `(r,s)=(1,3)` construction: 10 marks, coverage 36, score
`25/9`. It misses its own gate requirement by two differences.

At the live scale:

- 360 marks: `(59,121)`, coverage 43,318, deficit 5,792, score
  `2.991827877556674`;
- declared 49k window `[49,000,49,200]`: `(63,128)`, 383 marks, coverage
  49,023, score `2.992248536401281`;
- among all family members with coverage at least 49,110: `(64,129)`, 388
  marks, coverage 50,310, score `2.992327569071755`.

The last candidate would need coverage 57,046 at cardinality 388 to clear the
current gate, a deficit of 6,736. This is a family-level negative result, not a
claim about arbitrary difference bases.

## Non-overlap with prior campaigns

This lane does not regenerate the incumbent, optimize Singer cuts, use the
four-height Singer product, search shells `0..7`, perform 1-/2-swaps or block
repairs, or use quadratic relative-difference-set embeddings. The sole overlap
is the explicitly labelled degenerate `r=0,s=1` control `{0,1,4,6}`, which is
excluded from the novel frontier.

The result does not rule out other sparse-ruler families, the 128-mark Golay
basis at 6,166, non-Singer cyclic products, mixed recursive constructions, or
arbitrary supports.

## Durable evidence

The append-only run is
`runs/20260815T084100Z_exact_sweep/`:

- `config.json` SHA-256
  `fa26f6e963517f7576fd8ba53016c5a99fcc81d81e6bc979c22c02091d7f285e`;
- `events.jsonl` SHA-256
  `baecc7b5732398bf139ebabbb086f98e1e49c67c31a851df94db47a33cf829a6`;
- `summary.json` SHA-256
  `cc678a56cd5d9764494d9ad488f59b0b477da5826e727a9cfc9975da2fc9c5c9`.

Those hashes describe the original run. Publication hashes for all included
files are authoritative in `PUBLICATION_MANIFEST.json`.

## Publication boundary

Publish exactly the manifest allowlist. Exclude caches, the full Arena corpus,
the frozen verifier source, downloaded literature PDFs, credentials, and all
unrelated campaign state. No third-party array or submission payload is copied.
