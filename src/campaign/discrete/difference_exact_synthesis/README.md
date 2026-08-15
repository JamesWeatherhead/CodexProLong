# Carry-exact Difference Bases synthesis

No candidate cleared the live gate. The useful result is a genuinely global,
exact finite-family closure: for every cardinality from **320 through 411**, no
assignment of arbitrary per-residue supports in integer shells `0..7` over the
leader's 90-point perfect cyclic core can meet that cardinality's strict Arena
gate. Cardinalities `412..720` are structurally impossible in the same family:
the gate prefix already includes `8*8011+1`, whose unique residue-1 witness
would require height difference 8. The family contains at most `90*8=720`
points.

This is not another swap, common-height grid, or modular proxy. Each of the 90
residue columns independently chooses any support subset of `{0,...,7}`;
support points may be born or deleted, and only the total size is fixed. The
search therefore includes arbitrary heterogeneous shell sets `R_h` within
those eight shells.

## Exact formulation

The frozen leader has 360 points, coverage 49,109, score
`129600/49109 = 2.639027469506608`, and payload SHA-256
`02b16426d5a66feb480d79c7e1c7c26bb18ffb50730c5a2c76861584ec59183b`.
It factors as a 90-residue `(8011,90,1)` cyclic difference set with common
heights `{0,1,4,6}`. Every nonzero residue modulo 8011 consequently has exactly
one ordered witness pair.

For residue columns `a>b`, let `g=a-b`. A target integer can use either the raw
difference `g` or the carried difference `g-8011`. Thus the requirement that
all integers through `T` occur is exactly the binary relation

```text
q in H_a-H_b       for every q*8011+g <= T
-(q+1) in H_a-H_b  for every q*8011+(8011-g) <= T.
```

The complete capacity model materializes those relations as allowed tables
over all 255 nonempty supports of sizes 1 through 8. Empty columns are exactly
impossible: a missing residue column destroys its unique cyclic witnesses. The
size-specific 360–371 model uses a safe presolve to 247 supports of sizes 2
through 8, because those prefixes impose at least 12 cross differences and a
singleton paired with at most eight points cannot realize them. Any returned
model is reconstructed as literal integers, checked with a Python-integer
difference bitset, and replayed through the unchanged verifier SHA-256
`a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`.

## Frozen result

- Twelve direct formulas close sizes 360–371 at their exact strict-gate
  targets, from 49,110 through 52,156.
- Seven monotone capacity formulas close 320–359 and 372–411. If a support of
  size `k <= K` covered prefix `T`, adding unused shell points up to `K` could
  not remove a difference; UNSAT at capacity `K` therefore closes the whole
  stated block.
- All 19 formulas returned exact `INFEASIBLE`. The largest serialized formula
  was 253,226,572 bytes. OR-Tools was pinned as 9.14.6206.
- The search did not audit cardinalities below 320, supports outside shells
  0–7, a changed residue core, or constructions without the 8011 quotient.
  CP-SAT did not emit a DRAT/LRAT proof, so these are replayable solver
  closures, not independently checkable proof certificates.

The public packet contains only the attributed 90-residue core—not the full
third-party coordinate payload. Its network-free replayer rebuilds and hashes
all 19 deterministic CP-SAT protobufs without loading an Arena snapshot or
executing downloaded verifier code:

```bash
.venv/bin/python \
  campaign/discrete/difference_exact_synthesis/test_carry_exact_csp.py -v
.venv/bin/python \
  campaign/discrete/difference_exact_synthesis/public_replay.py
```

To rerun the expensive searches from scratch inside the canonical campaign:

```bash
.venv/bin/python campaign/discrete/difference_exact_synthesis/carry_exact_csp.py \
  --totals 360-371 --height-max 7 --seconds 180 --workers 8 \
  --run-dir campaign/discrete/difference_exact_synthesis/runs/20260815T063528Z_height7_full_support
.venv/bin/python \
  campaign/discrete/difference_exact_synthesis/complete_capacity_closure.py \
  --seconds 600 --workers 8 \
  --run-dir campaign/discrete/difference_exact_synthesis/runs/20260815T073000Z_complete_capacity_closure
```

The public replay validates formula bytes and solver receipts. Because the
original CP-SAT runs emitted no DRAT/LRAT proof, the recorded `INFEASIBLE`
statuses remain solver evidence rather than independently checkable proof
certificates.

The construction was grounded in Banakh–Gavrylkiv's carry-aware
cyclic-to-interval recursion (arXiv:1702.02631v6, Theorem 4.7), then strengthened
from common product supports to independent column supports. Paperclip's
full-text record for Li–Yip gives the relevant quotient/direct-product
construction framework at [lines 73–81](https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L73-L81)
and its relative-difference-set completion at
[lines 119–133](https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L119-L133).
See `PROVENANCE.md` for source pins and scope.
