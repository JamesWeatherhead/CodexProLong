# Prime-number-theorem campaign

Read-only, reproducible tools for the live EinsteinArena verifier.  These
programs contain no submit, post, vote, or mutation calls.

```sh
cd /Users/jacweath/EinsteinArena
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
