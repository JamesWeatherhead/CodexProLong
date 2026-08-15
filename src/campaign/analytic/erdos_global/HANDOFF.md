# Erdős global-lane handoff — 2026-08-15

A gate-clearing construction was found and independently replayed.  This lane
made public GET requests and local controller verification calls only; it did
not submit, post, vote, register, or otherwise mutate Arena state.

## Live gate and best local construction

The controller snapshot was refreshed at `2026-08-15T03:32:26.037823Z`.
Leader #2440 remains
`0.38085867721583955`, `minImprovement` remains `1e-7`, and the strict gate is
therefore score `< 0.38085857721583954`.  The live verifier SHA-256 still is:

`7c0e78d9dc40f27584ee2de01348fddcc6ff4a540908ddc902a4c6ef920920b0`

The frozen n=3584 gate-clearer is:

- payload: `slp_runs/20260815T043300Z-n3584-margin03/best.json`
- payload SHA-256:
  `79d2122c7e62e6a07feaeb708fa2b1b4c072caa812693ce6b2d31c01cc60c3ee`
- exact independent and controller-verifier score: `0.3808585748578583`
- improvement over #2440: `1.0235798125757256e-7`
- safety below the strict gate: `2.3579812546969947e-9`
- domain: 3,584 finite values, normalized sum exactly 1,792, raw sum
  `1792.0000000000005`, and range
  `[1.8002169585663917e-15, 0.9999999999999839]`.
- controller candidate SHA-256:
  `43d6096c5ebd143a03f56e5c07de335e2c1b64bf3485336633df16d7f8257db6`
- controller receipt:
  `../../state/receipts/erdos-min-overlap/20260815T043446856333Z-43d6096c5ebd.json`

`independent_replay.py` imports none of the optimization code.  It both
executes the frozen server verifier verbatim and independently evaluates the
literal float64 `np.correlate` path, requiring the two scores to be equal:

```bash
cd /Users/jacweath/EinsteinArena
.venv/bin/python campaign/analytic/erdos_global/independent_replay.py \
  --payload campaign/analytic/erdos_global/slp_runs/20260815T043300Z-n3584-margin03/best.json
cd campaign
./arena verify erdos-min-overlap \
  analytic/erdos_global/slp_runs/20260815T043300Z-n3584-margin03/best.json
```

The machine-readable result is `replay_receipt.json`.  The snapshot SHA-256
is `84a2322ab4cf15b7f89d795e6032b62b39ccd4a8e4b258360998c611f16dcb25`.

## Local continuation frontier

The literal-correlation active-bundle SLP resumed the prior n=3584 frontier at
`0.38085862169567786`.  Run
`slp_runs/20260815T024500Z-n3584-adaptive60/` accepted all 56 relinearized
steps and first crossed at `0.3808585771560596`.  Because that was only
`5.98e-11` below the gate, three independently checkpointed one-stage margin
runs (`margin01` through `margin03`) lowered the score to the frozen result
above.  Trust probes at `5e-4`, `1.875e-4`, and `1.25e-4` were checkpointed;
none beat the retained `2.5e-4` path at matched mature stage counts.  This is
an empirical bounded frontier, not a proof of local or global optimality.

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
