# Handoff: carry-exact global support synthesis

## Outcome

No gate-clearer. The exact bounded frontier is publish-safe and frozen:

- live leader: id 634, size 360, coverage 49,109, score
  2.639027469506608;
- live strict gate: score `< 2.6390274685066077` (`minImprovement=1e-9`);
- leader payload SHA-256:
  `02b16426d5a66feb480d79c7e1c7c26bb18ffb50730c5a2c76861584ec59183b`;
- exact family: the leader's 90 perfect cyclic residues modulo 8011, with an
  arbitrary independent subset of shells `{0,...,7}` at every residue and no
  other support restriction;
- closed gate-capable sizes: every integer 320–411;
- sizes 412–720: structurally blocked by the unique residue-1 carry requiring
  shell difference 8; sizes above 720 do not exist in this family;
- unresolved scope: sizes below 320, other shell ranges, other residue cores,
  and non-quotient constructions.

## Durable runs

`runs/20260815T063528Z_height7_full_support/` contains 12 direct, size-specific
formulas for 360–371. All returned `INFEASIBLE`.

- config SHA-256:
  `a74caa86a4d7375f24ef166c9e4bd15b332cc1b6a66c34569f9ccf6fe8880360`
- events SHA-256:
  `7692fa0315ae2d11539d9598eba8226521f9aa32765bf5dace046517b60a63af`
- summary SHA-256:
  `7a90e785d8ba5a8ed04e32454e4f0e17a2ff6b4e23d069801197aaa936cb413f`
- semantic config SHA-256:
  `80ec23bce4367bee44a613bcb996f6a12defb6902e0b0a64d1ca282d28c6964a`

`runs/20260815T073000Z_complete_capacity_closure/` contains seven monotone
capacity formulas closing 320–359 and 372–411. It uses all 255 nonempty
supports, including singleton columns. All returned `INFEASIBLE`.

- config SHA-256:
  `b1a7bd8a49bab69a085174da105261336ccac01b6465e3b30c5f0e293d2b094c`
- events SHA-256:
  `abfa10b822706892cb56ba910c93b71fe3fcf0f4b12770030cbc6173abbc2116`
- summary SHA-256:
  `a7ca5d878ddcf40d85eab5892c62d631a60d18277c63142870922f21c3b4a904`
- semantic config SHA-256:
  `c2c8cfed650c1ac5fd4dba08dcc9b14a51f986437da38b88ab87d29b49208fc0`

The seven capacity blocks and weakest required prefixes are:

| Sizes closed | Capacity | Prefix required |
|---:|---:|---:|
| 320–329 | 329 | 38,803 |
| 330–339 | 339 | 41,266 |
| 340–349 | 349 | 43,805 |
| 350–356 | 356 | 46,419 |
| 357–359 | 359 | 48,294 |
| 372–384 | 384 | 52,438 |
| 385–411 | 411 | 56,167 |

The direct run fills the only gap, 360–371. The maximum serialized formula was
253,226,572 bytes. CP-SAT exact UNSAT is solver evidence for each finite model;
no DRAT/LRAT proof was requested or produced.

## Why the encoding is exact

The 90 residues form a `(8011,90,1)` difference set, verified locally: each
nonzero residue has exactly one ordered pair. For every unordered residue gap,
`cross_requirements()` enumerates both the raw integer representative and its
quotient carry, through the requested literal prefix. An allowed table row is
present iff the selected shell supports realize every one of those required
height differences. Multiples of 8011 are enforced separately as same-column
differences. Therefore the CSP is equivalent to literal prefix coverage within
the stated support family.

The monotone range argument is also exact: adding an unused point cannot
remove an existing difference. If any `k` in a closed block worked, it could be
padded to that block's capacity while retaining at least the weakest gate
prefix in the block, contradicting the capacity formula's UNSAT result.

## Publish-safe inclusion list

Include only:

- `README.md`
- `HANDOFF.md`
- `PROVENANCE.md`
- `carry_exact_csp.py`
- `complete_capacity_closure.py`
- `test_carry_exact_csp.py`
- `frozen_inputs.json` (attributed 90-residue derived core; no full payload)
- `public_replay.py` (network-free, verifier-free deterministic formula replay)
- `runs/20260815T063528Z_height7_full_support/` and
  `runs/20260815T073000Z_complete_capacity_closure/`, each with `config.json`,
  `events.jsonl`, and `summary.json`
- `receipt.json` after regeneration by `freeze_receipt.py`
- `freeze_receipt.py`

Exclude:

- `__pycache__/`
- `capacity_closure.py` and `runs/20260815T065500Z_capacity_closure/` (a
  superseded exploratory singleton-presolved run retained locally only as an
  audit trail)
- `campaign/discrete/difference_global/checkpoints/public_latest.json`
- all other Arena snapshots/full discussions and any third-party payload arrays

The frozen lane itself performed no Arena or GitHub mutation. Publication is
handled separately by the campaign root through the secret-scanned mirror.
