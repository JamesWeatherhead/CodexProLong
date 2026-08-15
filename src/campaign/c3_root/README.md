# Third-autocorrelation root lane

The C3 verifier has the same normalized maximum-autoconvolution algebra as C1,
but its intended domain explicitly permits negative values. This lane reuses
the float64 high-beta machinery against the public 25,600-point leader while
preserving a nonzero integral and accepting only exact NumPy-verifier gains.

`signed_square_polish.py` adds a second local geometry, `f = u * abs(u)`,
which preserves signed constructions while giving near-zero coordinates a
vanishing parameter-space gradient. Each temperature stage is still accepted
only when direct float64 `numpy.convolve` improves the exact score. By default,
the next beta is warm-started from the surrogate iterate even when that stage
was not exact-accepted; `--reset-on-reject` enables conservative restarts.

The first exact same-resolution endpoint is `1.4515678053995411`; the
reproducible method and its below-gate limitation are recorded in
`discussion.md`.

`split_pairs.py` performs the block-repeat lift while adding an antisymmetric
perturbation inside each repeated pair. Pair sums—and therefore total mass—are
preserved, so the experiment isolates the new within-block degrees of freedom.

`pair_split_polish.py` goes further by holding every pair mean fixed and
optimizing only those antisymmetric differences. This is the normal space to
the block-repeat embedding; exact gains here demonstrate a real
higher-resolution escape before a full-coordinate release.

`extrapolate.py --base CHECKPOINT` can transplant a direction measured between
two public trajectory points onto a newer local checkpoint. This supports
controlled basin nudges without conflating them with the checkpoint's own
optimization history.

`turbo_supervisor.py` runs repeated exact-accepted cascades under an atomic
filesystem state file and append-only event journal. Each child receives only
the prior cycle's best direct-`numpy.convolve` checkpoint; interrupted work can
resume with `--resume` without relying on conversational context.

`signed_power_polish.py` generalizes the signed-square map to
`f = sign(u) * abs(u)**power`. This changes the optimizer's local metric while
preserving the full finite signed search domain; only unchanged-verifier gains
are checkpointed.

`sign_topology_seed.py` makes reproducible zero/flip changes among near-zero
coordinates so sign-pattern births and deaths can be tested independently of
ordinary Gaussian noise.

`block_split_polish.py` performs an exact factor-`k` repeat lift and optimizes
only the `k-1` zero-mean modes inside each repeated block. It is the generalized
factor-three-or-higher counterpart of `pair_split_polish.py`, with the original
block means and total mass held fixed.

## Current exact frontier

As of 2026-08-15T01:15Z, the best unchanged-verifier replay is
`1.4515655298503767` at n=102,400 in
`runs-102400/20260815T011534Z/best.npy`. This improves the public leader by
`6.3340398302e-6`; the strict first-place gate still requires another
`3.6659601699e-6`. The accepted continuation used beta stages from `1e7`
through `1e9`, and every saved gain was rescored with direct float64
`numpy.convolve`.

Two Gaussian basin escapes were also bounded without an accepted gain. The
n=102,400 noisy full-coordinate continuation exhausted 20,919 evaluations
through beta `1e9` and retained only its seed (`1.451565876634116`). The
n=204,800 noisy continuation was stopped after 13,206 evaluations through beta
`1e8`: its best retained seed was `1.4515658271807341`, while surrogate
candidates remained roughly `3e-4` worse. These runs rule out those specific
noise/temperature paths; they do not rule out the active-lag epigraph method.

## Active-bundle epigraph checkpoint

`active_bundle_epigraph.py` implements the Paperclip-grounded active-lag
experiment: a deterministic, rank-revealed 68-dimensional Fourier/Haar/grid
basis; a cutting-plane epigraph SLP; an omitted-lag scan after every LP; and an
exact quadratic line search that crosses max-lag boundaries. FFTs build only
proposal derivatives. Every accepted checkpoint is rescored with direct
float64 `numpy.convolve` under verifier SHA-256
`b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9`.

The cleaned bounded run is
`runs-active-bundle/20260815T015806Z/`. Its exchange loop closed all omitted
linearized constraints after 4,666 cuts at a `1e-9` violation tolerance. The
globally checked linear model predicted a maximum-convolution change of only
`-4.5667645768e-5`; the exact accepted score was
`1.4515655289584310`, a gain of `8.9194585e-10`. The strict gate remains
`3.6650682e-6` away. This quantifies the negative frontier for this particular
68-dimensional local model; it does not rule out a larger changed-support or
global basin move.

Deterministic rerun and independent replay:

```sh
.venv/bin/python -u campaign/c3_root/active_bundle_epigraph.py \
  --input campaign/c3_root/runs-102400/20260815T011534Z/best.npy \
  --trusts 0.1 --cycles 1 --alpha-max 8 --alpha-grid 129

.venv/bin/python campaign/analytic/c3_secondary/replay_exact.py \
  campaign/c3_root/runs-active-bundle/20260815T015806Z/best.npy
```

The replayed payload SHA-256 is
`a9c9385dc51556952785f638418dd86517c0274eae97434250b6f50ca1985a88`.
