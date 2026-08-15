# C2 global topology journal

## Exclusions

- no fixed-support full-vector polish;
- no one/two-point micro-runs, run shifts, or scalar packet rescans;
- no local packet births into the `#2416` dead band;
- no linear interpolation, ordinary block repeat, direct trajectory
  extrapolation, tooth-split relattice, fresh envelope-times-comb descent, or
  Gerchberg--Saxton projection sweeps.

## Hypothesis

At period 5,455, the live leader separates into a graded main comb/ramp
(rows 0--255), a large void (256--317), a weak bridge (318--326), and a dense
terminal spike/comb (329--366).  Adjacent tail rows follow a coherent
alternating phase pattern near +950/-1180 cells, whereas the main ramp mostly
uses -1/+8-cell phase increments.  The new search changes coordinated regional
phase schedules while preserving every within-row tooth profile and the macro
mass envelope.  This is a global lattice-topology screen, not support growth.

## Phase result

- 362 exact live-verifier evaluations.
- Best: `0.9635881106065262` (`+2.4496183e-11`), from moving only the
  negligible right-bridge region by 1,192 cells.
- All non-negligible regional offsets and affine phase changes were sharply
  negative. The whole-region phase family is not gate-capable.

## Next bounded topology

The terminal split screen moves fractions from `1e-8` through `0.9` of the
complete terminal component into the void, using translated and mirrored
copies. It directly tests whether a finite-mass three-cluster basin exists
behind the locally negative packet frontier.

## Terminal split result

- 378 exact live-verifier evaluations from the strongest retained support
  checkpoint (`0.9635881172701123`).
- Best translated change: `0.9635881164544261`, at fraction `1e-8` and shift
  `-20,000`.
- Best mirrored change: `0.9635881125281137`, at fraction `1e-8` and shift
  `-20,000`.
- Neither family improved its seed. Since the one-sided response is already
  negative at `1e-8` and larger finite fractions deteriorate monotonically at
  each screened displacement, this coherent three-cluster family has no
  observed mass-transfer bifurcation.
