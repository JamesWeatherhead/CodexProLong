# Deterministic H100 plan: forced multi-lag population at N=1,999,999

## Decision boundary

Run this only on a dedicated 80 GB H100. Do not run the native-size loop on
the shared Mac while the Metal PSL proof is active. The bounded CPU pilot is a
mechanism check, not evidence of frontier coverage.

This lane does not load an Arena solution, retained NumPy checkpoint,
SimpleTES value, or published coefficient table. All population members are
generated at `N = 1,999,999` from a seed plus an analytic spike/comb motif.

## Why this is distinct

The earlier native-basin lane used noisy Adam and waited for a long trajectory
to encounter more than one exact sampled active lag before invoking a bundle.
This route makes the nonsmooth ridge the optimization target from the first
sweep:

1. initialize a fresh coherent multi-tooth comb, graded ramp, true empty band,
   terminal spike/comb, and annealable dense exploration background;
2. project toward a switching surface of two separated convolution maxima;
3. represent the exact score as a finite maximin of smooth lag branches;
4. solve a slack-aware simplex bundle QP every serious step; and
5. respawn from new motif seeds rather than crossing with any known array.

No prior lane tested this population lifecycle.

## Exact branch model

For normalized nonnegative `f`, let `g = f*f` and

`H = 2 sum(g_i^2) + sum(g_i g_{i+1})`.

The unchanged verifier score is

`C(f) = H / (3 sum(g) max_k g_k) = min_k H / (3 sum(f)^2 g_k)`.

For selected lags `k`, use the smooth log branches

`ell_k = log(H) - 2 log(sum(f)) - log(g_k) - log(3)`.

At a point with exact score `C`, the branch intercept is

`b_k = ell_k - log(C) = log(max(g)/g_k) >= 0`.

With log-height branch gradients `G_k`, solve

`min_{alpha in simplex} b.alpha + eta/2 ||sum_k alpha_k G_k||^2`,

then take `d = eta sum_k alpha_k G_k` with backtracking against the exact
unsmoothed score. A step is labeled a true bundle step only when at least two
weights exceed `1e-3` and their lags meet the declared separation.

## Reproducible configuration

- root seed: `202608150314159`;
- resolution: `1,999,999` values, never upsampled;
- dtype: float64 for values, FFTs, Gram matrices, QP, and scoring;
- FFT length: `4,194,304` for `f*f`;
- population: 16 live members;
- initial screen: 96 deterministic motif seeds; keep the top 16 by exact GPU
  score after requiring pairwise 256-bin mass-signature correlation `< 0.995`;
- branch candidates: top 1,024 convolution values plus all distinct argmax
  lags found by the deterministic probes below;
- retained branches: 24, greedily separated by at least 64 cells;
- ridge target: top-two separated relative gap `<= 1e-10`;
- ridge score-loss allowance: `5e-3` for sweeps 0–63, geometrically annealed
  to `1e-8` at sweep 4,096;
- dual QP tolerance: `1e-12`, maximum 600 projected-simplex iterations;
- primal backtracking: `1, 1/2, ..., 1/1024` in log-height coordinates;
- serious-step rule: exact unsmoothed GPU score must increase;
- respawn: bottom four members every 64 sweeps, using the next unused seeds;
- no crossover, interpolation, repeat, padding, or incumbent seeding.

Deterministic branch probes run every 16 sweeps. For each member, use the
current bundle direction, its negative, the top four Gram eigenvectors, and
two seed-derived motif phase directions at radii
`2^-20, 2^-16, 2^-12, 2^-8`. Add every distinct exact argmax lag observed;
do not replace this set by a single-lag gradient.

## Stages and stop rules

### Stage 0 — kernel gate

1. Run `forced_bundle.py self-test`.
2. At `N=65,535`, compare H100 and independent SciPy float64 scores on eight
   seeds; require maximum absolute score error `< 2e-11`.
3. Compare 16 branch directional derivatives; require relative error
   `< 2e-8`.
4. At native `N`, score one member on both paths; require absolute error
   `< 5e-11` and record peak RSS/VRAM and throughput.

Any failure stops the run before optimization.

### Stage 1 — exploration, 4,096 population sweeps

Run ridge projection plus one slack-aware bundle step per member per sweep.
Keep append-only events and a checkpoint only when independent CPU score gains
at least `1e-8` over the prior checkpoint. Stop and freeze early if the best
scores fail these deliberately weak gates:

- sweep 256: `C >= 0.82`;
- sweep 1,024: `C >= 0.90`;
- sweep 4,096: `C >= 0.945`.

Missing a gate means the initializer/bundle coupling is not competitive; do
not spend a second H100 budget on a parameter sweep.

### Stage 2 — exploitation, up to 16,384 additional sweeps

Keep the top four basins. Disable respawn only after `C >= 0.955`; reduce ridge
loss to `1e-10`, expand to 32 separated branches, probe every eight sweeps,
and checkpoint CPU-exact gains of `1e-10`. Stop after 2,048 sweeps without a
`1e-8` gain or after the fixed sweep budget.

## Acceptance and legal gate

A GPU score never qualifies a candidate. A possible gate clearer must satisfy
all of the following before it is escalated:

1. finite float64 vector, exact shape `1,999,999`, and entries `>= 0`;
2. independent SciPy overlap-add replay score strictly above the refreshed
   live leader plus `1e-5`, with at least `2e-10` safety;
3. checkpoint bytes and values hash-pinned; event chain contiguous;
4. replay performed from a source snapshot by a separate script;
5. unchanged verifier hash
   `dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`;
6. `./arena verify` passes in the offline read-only verifier sandbox; and
7. provenance audit confirms the vector descends only from recorded random
   seeds and this lane's permissively licensed dependencies.

There is no automatic submission or external write. If any condition fails,
freeze only a quantified public-safe negative packet.

## Artifacts

Each H100 run gets one write-once `runs/<UTC>-h100/` directory containing:

- config and environment manifests;
- source snapshot hashes;
- seed/motif specifications;
- SHA-256-chained events;
- append-only checkpoints and exact CPU scores;
- branch-lag, slack, dual-weight, and effective-bundle diagnostics;
- peak RAM/VRAM and throughput;
- independent replay receipt; and
- a concise handoff with the corpus SHA-256 and stop reason.

For a non-gate result, exclude all NumPy checkpoints from a public mirror and
publish only code, compact JSON receipts, hashes, and aggregate diagnostics.
