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
