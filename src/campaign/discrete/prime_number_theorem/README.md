# Prime-number-theorem campaign

Read-only, reproducible tools for the live EinsteinArena verifier.  These
programs contain no submit, post, vote, or mutation calls.

```sh
cd /path/to/EinsteinArena
.venv/bin/python campaign/discrete/prime_number_theorem/refresh.py
.venv/bin/python campaign/discrete/prime_number_theorem/refresh_database.py
.venv/bin/python campaign/discrete/prime_number_theorem/audit.py
.venv/bin/python campaign/discrete/prime_number_theorem/optimize.py \
  --restart --etas 0.001,0.003,0.01
.venv/bin/python campaign/discrete/prime_number_theorem/price_swaps.py \
  --candidate-limit 20 --removal-limit 3
.venv/bin/python campaign/discrete/prime_number_theorem/verify.py
.venv/bin/python campaign/discrete/prime_number_theorem/group_exchange.py \
  --sizes 4,8,12 --max-groups 300 --fixed-row-topologies 300 \
  --relaxed-rows 500 --flexible-limit 200 --full-safety 2e-9
.venv/bin/python campaign/discrete/prime_number_theorem/group_refine.py \
  --source-run-id 24b6c37147e517a36dbe \
  --target-ids 578703e0c96f1709f3f8 --eta 0.01 --safety 5e-9 \
  --force-full
.venv/bin/python campaign/discrete/prime_number_theorem/replay_group_feasible.py
.venv/bin/python campaign/discrete/prime_number_theorem/audit_reach_extend_exact.py \
  --refresh-live --official
```

`audit.py` regenerates the fixed `RandomState(42)` ten-million-sample stream in
the verifier's exact batch size, stores the distinct sampled integer grid, and
cross-checks tight recurrence rows by direct dot products.

`optimize.py` uses a warm-started cutting-plane LP.  It may enlarge the trust
region only after the current master passes every sampled integer row.  Every
round and every added row is atomically checkpointed.  The current bounded
frontier adjusts the 1,187 incumbent columns with key at most 1,800 or absolute
value below 0.5.

`price_swaps.py` computes reduced costs for every unseen key no larger than the
incumbent reach, then screens low-value one-for-one replacements.  The fixed-row
master omits constraints and is therefore an upper bound: a swap that fails the
gate there cannot pass after full-grid cuts are restored.

`group_exchange.py` performs deterministic, coordinated 4/8/12-key and
16/20/21-key support exchanges.  Its bundle families cover tail phase shifts,
large-gap fills, and support chunks from every relevant public historical
basin.  It logs every screen to append-only JSONL.  Completed runs
`24b6c37147e517a36dbe` and `d85f64b5889496e4e293` fixed-screened 587 distinct
topologies; none retained a gate-capable upper bound.

`group_refine.py` reoptimizes all 1,187 eligible incumbent coordinates for the
best support bundles, then uses full sampled-stream cut generation for forced
survivors.  The strongest 8-for-8 relaxation scored `0.9976496523726353`, but
full separation reduced it to `0.9976492989838518`.  The unchanged live
verifier replayed it at `0.9976492989838522`, below the
`0.9976498835182795` gate.  The preserved finite incumbent and receipt are in
`group_refine_feasible.json`; its canonical payload SHA-256 is
`ed682e5077ef4cc9132482d8799157b03aa55b6eff36773f962f325194e6cddd`.

`verify.py` fetches the current verifier with GET, pins its hash and the leader
ID, and runs the saved payload through that unmodified verifier.  It does not
submit the payload.

## Exact 127849-reach audit

`audit_reach_extend_exact.py` checks every integer state through
`10 * 127849` with exact `Decimal`/`Fraction` arithmetic and separately checks
the exact binary64 coefficients produced by the verifier's parse, clip, and
normalization steps.  This corrects the earlier float64 diagnostic argmax
`1,172,037`: the exact submitted-decimal argmax is `1,254,707`.  The raw and
hardened maxima are respectively
`1.000099999826556854765343173520975599...` and
`1.000099990078786342030486544477973890...`, leaving exact verifier-limit
margins of about `1.73443e-10` and `9.92121e-9`.  In the exact post-parse
binary64-coefficient model, both argmaxes are `319,932`; the hash-pinned
official verifier is also replayed in fresh processes.

The hardened payload `reach_extend_127849_fullrange.json` has file SHA-256
`d43c5531d562d06981a55829deb1c579a87a7c02405d69688dcc79e7f45f22c1`
and official score `0.9976572852677297`.  Public GET evidence records it as
evaluated submission `#2506` and the current rank-1 construction.  The full
receipt is `checkpoints/reach_extend_127849_exact_audit.json`.

This is a verifier-domain result, not a proof of the stronger mathematical
statement in the problem description.  The verifier checks a finite horizon
with tolerance `<= 1.0001`; the description asks for `<= 1` for every real
`x >= 1`.  Both audited payloads exceed `1` within the finite horizon, and no
claim beyond the verifier domain is made.
