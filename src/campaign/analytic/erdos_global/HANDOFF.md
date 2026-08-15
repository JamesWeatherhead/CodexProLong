# Erdős global-lane handoff — 2026-08-15

No gate-clearing construction was found.  This lane made public GET requests
only; it did not submit, post, vote, register, or mutate any Arena state.

## Live gate and best local construction

The live API was refreshed at `2026-08-15T02:27:51Z`.  Leader #2440 remains
`0.38085867721583955`, `minImprovement` remains `1e-7`, and the strict gate is
therefore score `< 0.38085857721583954`.  The live verifier SHA-256 still is:

`7c0e78d9dc40f27584ee2de01348fddcc6ff4a540908ddc902a4c6ef920920b0`

The frozen n=3584 local frontier is:

- payload: `slp_runs/20260815T063000Z-n3584-trust25e5/best.json`
- payload SHA-256:
  `1d319d75970d206a92996934b0a8aa283d772cf9c4db23f854cad471e87a99d3`
- exact verbatim-verifier score: `0.38085862169567786`
- improvement over #2440: `5.552016169030338e-8`
- remaining strict-gate gap: `4.4479838312572184e-8`
- domain: 3,584 finite values, sum exactly 1,792, range
  `[2.1693819491119065e-15, 0.9999999999999826]`.

`independent_replay.py` imports none of the optimization code.  It both
executes the frozen server verifier verbatim and independently evaluates the
literal float64 `np.correlate` path, requiring the two scores to be equal:

```bash
cd /Users/jacweath/EinsteinArena
.venv/bin/python campaign/analytic/erdos_global/independent_replay.py
```

The public mirror packages the same payload with a compact frozen-verifier
snapshot, so the same replay is also self-contained from its repository root:

```bash
python3 src/campaign/analytic/erdos_global/independent_replay.py
```

The machine-readable result is `replay_receipt.json`.  The snapshot SHA-256
is `84a2322ab4cf15b7f89d795e6032b62b39ccd4a8e4b258360998c611f16dcb25`.

## Local continuation frontier

The literal-correlation active-bundle SLP lowered the n=3584 smooth seed from
`0.3808588431595513` to the construction above.  Its final stage had
2,466--2,469 active signed lags and five consecutive accepted gains of about
`0.85e-9`--`1.19e-9` at trust radius `2.5e-4`.  This is an empirical bounded
frontier, not a proof of local or global optimality.  It is below the public
leader but does not meet the platform's required `1e-7` improvement.

## Lifted seed comparison

The bounded n=32/n=64 Shor--McCormick plus SROCR experiment is fully logged in
`srocr_runs/20260815T080000Z-n64-final/summary.json` (SHA-256
`0e7daf2c6ee3d5dc6cce9fa2ee601f6783c734e8acfeefe970fa1d29487e5321`).

At n=64, the untouched public-rebin seed scores `0.38645119108757653`, already
`0.005592569391898672` worse than the local frontier.  The unconditioned lift
has a deceptively small relaxed epigraph (`1.1366976602610722e-8`) but extracts
the nearly constant half function at exact score `0.4999999999979555`.
SROCR from the public eigendirection yields exact scores `0.44228741379588893`,
`0.4389710511325953`, and `0.4345688198244092`; the best final extracted stage
is `0.053710198128731346` worse than the local frontier.  Two independent
balanced-binary starts finish near `0.468`.  Thus the tested lift concentrates
rank only by entering poor feasible basins; its low relaxed objective is not a
useful topology signal.

The final public-direction extraction is
`srocr_runs/20260815T080000Z-n64-final/public_rebin_stage_03.json`, SHA-256
`b88bfdfd0770122daa56682e5981c7dc47e9982ebe4fdfb8eb318f0f33b4159b`;
`independent_replay.py --payload PATH` returns the exact score above.  A fresh
bounded reproduction is:

```bash
cd /Users/jacweath/EinsteinArena
.venv/bin/python campaign/analytic/erdos_global/srocr_seed.py \
  --run-root campaign/analytic/erdos_global/srocr_replays \
  --n 64 --random-seeds 2 --stages 4 --eps 3e-6 --max-iters 50000
```

This negative result is limited to the tested relaxation and seeds.  A future
lift would need an explicit symmetry/topology condition that excludes the
constant-half relaxation before spending on a larger SDP.
