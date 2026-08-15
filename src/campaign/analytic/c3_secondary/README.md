# C3 secondary lane

Live public leader (read-only refresh, 2026-08-14): solution `#2493`, score
`1.4515718638902069`, 25,600 entries.  The frozen verifier SHA-256 is
`b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9`.
The required first-place gate is `1.4515618638902069`.

The independent starting checkpoint was the root lane's 25,600-entry
signed-square endpoint at `1.4515678053995413`.  The best secondary-lane
construction is the 51,200-entry pair-split continuation:

`runs-pair-split/20260814T235436Z/best.npy`

Direct float64 `numpy.convolve` replay gives `1.4515678014928040`, a gain of
`3.9067378e-9` and a remaining gate gap of `5.9376026e-6`.  Artifact SHA-256:
`03f5054c019c3fc0bf55e831e1580e0dfcc8c171f964d51a7d1b22b90a0fe933`.
This is not submission-ready.

Replay:

```sh
/Users/jacweath/EinsteinArena/.venv/bin/python \
  /Users/jacweath/EinsteinArena/campaign/analytic/c3_secondary/replay_exact.py \
  /Users/jacweath/EinsteinArena/campaign/analytic/c3_secondary/runs-pair-split/20260814T235436Z/best.npy
```

## Narrowed frontier

At the 25,600-point endpoint the exact convolution has 23,601 lags within
`1e-8` relative of the maximum, 21,619 within `1e-9`, and 68 within `1e-10`.
All-lag proximal bundle attempts therefore encountered moving omitted
constraints rather than a stable small active set.  After 5,000 Frank-Wolfe
atoms, predicted maximum changes were still positive (`+0.0092`, `+0.0308`,
and `+0.0929` for eta `3e-4`, `1e-3`, and `3e-3`), and direct verifier replay
accepted no step.

The exact block-repeat nullspace was then parameterized by
`x[2i]=f[i]+d[i]`, `x[2i+1]=f[i]-d[i]`.  A scaled beta continuation through
`3e10` found only the `3.9e-9` gain above.  Allowing all 51,200 coordinates
and carrying low-beta states reached a distinct but worse endpoint,
`1.4515733939939344`.  Same-resolution perturbations at RMS `0.0012` and
`0.1335`, plus three locked sign-support changes, all converged above the
starting checkpoint.  The remaining route is therefore a genuinely global
basin/support change, not a small active-set, within-pair, or single-sign-flip
correction.
