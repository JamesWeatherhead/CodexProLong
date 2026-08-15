# Difference-basis interval-construction handoff

## Outcome

No gate-clearer was found.  The final GET-only live check retained:

- leader score: `2.639027469506608`
- minimum improvement: `1e-9`
- strict target: `< 2.6390274685066077`
- verifier SHA-256:
  `a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`
- schema: `{"set": "list of non-negative integers (up to 2000 elements)"}`

The exhaustive four-block Singer construction independently regenerates the
leader at order `q=89`: cardinality `360`, covered interval endpoint `49109`,
and exact float64 score `360^2 / 49109 = 2.639027469506608`.  Its canonical
candidate SHA-256 is
`498eaa873e07f473c282b00c8d7df51a706267d9438a99e1cef1c7abed1bc018`.
It misses the strict gate by `1.000000082740371e-9`.

## Quantified search frontier

The retained search implements the Leech/Golay interval product in Theorem
4.7 of Banakh--Gavrylkiv with interval basis `{0,1,4,6}` and a planar Singer
difference set.  For `k=0` it exhausts every unit multiplier and every cyclic
cut at all `114` prime-power orders allowed by the `2000`-element schema:

- all `95` primes `2 <= q <= 499`; and
- all `19` non-prime prime powers `q <= 499`.

The best genuinely changed order is `q=53`: cardinality `216`, coverage
`17667`, score `2.640855832908813`, and gap `0.0018283644022054624` above the
gate.  The best non-prime prime power is `q=64`, score
`2.647554145615478`.

Positive-tail variants were also evaluated at `15` selected strong orders for
every `0 <= k <= 20`, and completely for every `0 <= k <= q` at
`q in {53,61,89,97,101}` (`406` exact candidates).  The best changed tail is
`q=89, k=1`, score `2.6435352346951193`, gap
`0.004507766188511564`.  The complete `q=97` affine scan establishes maximum
empty arc `998`, coverage `58039`, and score `2.647599028239632`, closing the
partial public trajectory for that order.

This is a negative result only for the stated four-block Singer family.  It
does not cover alternative interval bases, non-Singer cyclic bases, mixed
shells, arbitrary supports, or all positive-tail orders.

## Reproduction

Run from the EinsteinArena repository root:

```bash
.venv/bin/python -B \
  campaign/discrete/difference_interval_constructions/freeze_receipt.py
.venv/bin/python -B \
  campaign/discrete/difference_interval_constructions/replay.py
```

The independent replay reconstructs the `q=53`, `q=89`, and `q=97` prime
landmarks, the `q=64` tower-field landmark, and the complete `q=89` and
`q=101` tail sweeps.  Neither tool imports or executes the frozen verifier;
both hash-check it and evaluate the literal clean-room formula.

Authoritative checkpoint hashes are recorded inside `receipt.json`.  The
complete include/exclude inventory, per-file hashes, and licensing notes are
in `PUBLICATION_MANIFEST.json`.

No Arena submission, discussion, vote, issue, commit, or push was made.
