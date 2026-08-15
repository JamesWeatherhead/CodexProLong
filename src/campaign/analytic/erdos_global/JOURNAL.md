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
