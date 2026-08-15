# Erdős global / multiresolution lane

## 2026-08-15 corpus gate

- Read all 42 problem threads and all 134 replies in
  `research_corpus/snapshots/20260815T003306Z/corpus.sqlite3`.
- Searched the complete 1,021-reply corpus for Erdős references and read the
  19 cross-problem matches (7 threads, 12 replies).
- Loaded and literal-`numpy.correlate` replayed all 44 retained public
  constructions.  The frozen verifier hash is
  `7c0e78d9dc40f27584ee2de01348fddcc6ff4a540908ddc902a4c6ef920920b0`.
- Read the complete prior `campaign/erdos_root` no-go record: 20,711 exact
  rebin/phase/block/swap/polarization/zero-run/blend trials around n=1024,
  plus the converged n=2560 basin.  Those families are excluded here.

## New hypothesis

The public trajectory contains a dyadic resolution ladder that the prior lane
did not optimize at its next rung: solution 2407 has n=512 and score
`0.38085905681456067`; solution 2440 has n=1024 and score
`0.38085867721583960`.  Their macroscopic three-packet support boundaries
agree at dyadic coordinates, while n=1024 adds within-cell degrees of freedom.

Experiment A therefore doubles solution 2440 to n=2048 and performs a
sum-constrained continuation at the new resolution.  This is not a rebin
screen or n=1024 KKT polish: the new variables include within-parent-cell
antisymmetric packet modes and one-sided births at inherited zero/one cells.
Every accepted checkpoint is rescored by the literal verifier expression;
FFT is used only for analytic gradients.

Strict gate: score `< 0.38085857721583954`.

## Global-family results

- n=2048 dyadic continuation: `0.3808587246005157` after a projected
  contact-release polish; the repeated n=1024 incumbent remains better.
- n=1536, n=2560, n=3584 half-integer ladder: respectively
  `0.3808589961423988`, `0.3808588815857411`, and
  `0.3808588431595513`.  The ladder approaches from above and its fitted
  limit does not clear the gate.
- n=3072 three-child continuation: no gain over the inherited incumbent.
- Exhaustive two-channel block-circulant screen: 73,728 interleavings of all
  three public n=512 near-leader basins; the unshifted repeat is optimal.
- The inherited Haar packet space (627 feasible fine modes) and the full
  self-similar n=512 -> 1024 mean/packet correction both return to zero.

The remaining local diagnostic is `active_slp.py`, which uses a scaled HiGHS
interior-point solve of the exact active-lag linearization and then accepts
only a literal-`numpy.correlate` line-search decrease.  `highspy==1.15.1` was
installed in the project venv for this diagnostic.

## Active-bundle continuation

The n=3584 active-bundle SLP reduced the smooth-start score from
`0.3808588431595513` to an optimizer-log value of `0.3808586216956778`.
The final five accepted exact line searches used a `2.5e-4` box trust radius,
2,466--2,469 active signed lags, and gained between `8.49e-10` and
`1.19e-9` each.  This is a strong local construction but not a gate-clearer.

An independent script, importing none of the optimization code, executed the
frozen verifier source verbatim and separately evaluated its expression in
the same float64 operation order.  Both return `0.38085862169567786`.  (The
last digit differs from the optimization log because the older score helper
multiplied by `2/n` rather than applying the verifier's `/n*2` order.)  This
improves public solution #2440 by `5.552016169030338e-8` but remains
`4.4479838312572184e-8` above the strict gate.

## Lifted/SROCR global-seed screen

A new coarse Shor lift used `X = ff^T`, the PSD block matrix
`[[X,f],[f^T,1]]`, box/McCormick constraints, all lag epigraph constraints,
and sequential leading-eigenspace rank concentration.  Literal verifier
replay was the only acceptance criterion.

- At n=64 the unconditioned relaxation attained epigraph
  `1.1366976602610722e-8` but extracted the nearly constant half function,
  whose exact score is `0.4999999999979555`.  This exposes a severe relaxation
  gap rather than a constructive gain.
- The public-rebin coarse seed itself scores `0.38645119108757653`.
  Rank-concentrating stages score `0.44228741379588893`,
  `0.4389710511325953`, and `0.4345688198244092`; every stage is worse.
- Two balanced-binary eigenspace starts finish at `0.4682590250484766` and
  `0.46876483659625434`.  Some terminal SCS statuses are
  `optimal_inaccurate`, so their rank ratios are diagnostics, not
  certificates; all extracted vectors were nevertheless independently
  accepted and scored by the exact verifier.

The tested lift is therefore frozen as a negative global-topology route.  It
does not rule out a materially tighter lift that explicitly breaks the
constant-function symmetry, but increasing coarse resolution inside this
same relaxation is not supported by the n=32 and n=64 trajectories.
