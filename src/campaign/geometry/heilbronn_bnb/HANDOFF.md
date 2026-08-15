# Heilbronn discrete-family handoff — 2026-08-15

## Outcome

No gate-clearing construction was found.  The strongest result is an exact
closure of **every** 11-point subset of the full barycentric q=25 grid at the
live gate.

- Live leader: `0.036529889880030156`.
- Required target: strictly above `0.036529890880030155`.
- q=25 integer threshold: numerator 23, score `23/625 = 0.0368`.
- Result: infeasible across all 351 grid points and all boundary/corner
  topologies.
- Master certificate:
  `runs/20260815T002500Z/heilbronn-triangles/q025_complete_certificate.json`.
- Certificate SHA-256:
  `2cf96140b095b10b0c2a2c310090b9fe78d2c7a0511ce134acf393485022b9fe`.
- Exact search nodes: 51,494,145, including repeated work from partial prefixes.
- Verifier SHA-256:
  `6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d`.
- Frozen public snapshot SHA-256:
  `e6332c0715a82c9e62d9029385a7db1cab46549bf482ff65dca30e9ee5468d90`.

The certificate hashes the exact summary/aggregate backing each of the ten
non-corner side-count orbits and the exhaustive corner family.  The fully
interior orbit covers all 37,950 first-pair roots.  A small-instance self-check
also finds constructions below threshold, proves the next thresholds
infeasible, and agrees with the independent HiGHS MILP at q=8/d=2:
`runs/20260815T002500Z/heilbronn-triangles/self_check.json`.

## Additional exact scope

- Non-corner `(2,2,2)`: all q=8 through q=32 infeasible at the live gate.
- Corner-containing: all q=8 through q=25 infeasible.
- Every non-corner side-count orbit: q=25 infeasible.
- Coarser denominator sweeps for the other orbits remain preserved under
  `runs/`; the master q=25 certificate is the canonical result.

At positive score any side count of three or more is immediately impossible
because those three points are collinear.  After excluding corners, the ten
sorted triples in the certificate therefore cover every side-count topology
modulo D3.

## Limits and next move

This closes a discrete construction family only.  It is not a continuous
Heilbronn upper bound and yields no candidate payload, so no live-verifier
Docker replay was appropriate.  Do not repeat q=25 or incumbent polishing.
The next legitimate discrete move is a different denominator selected for a
favorable exact threshold (or a nonuniform/rational mesh with adaptive cells),
using the same side-orbit and first-pair decomposition.  A continuous move
would need a genuinely new active topology rather than another random restart.

No external post or submission was made.

## q=30 continuation

The distinct q=30 lane uses exact numerator 33 (`33/900 =
0.03666666666666667`) on the 493-point non-corner grid.  Its canonical summary
is:

`runs/20260815T020000Z/heilbronn-triangles/q030_campaign_summary.json`

SHA-256:
`349ffb0ea5659120f06441a50f39c4f34929716c2cb147bebd122f88b695fe94`.

Five of the ten D3 side-count orbits are completely infeasible:
`(222)`, `(221)`, `(220)`, `(211)`, and `(200)`.  The five harder orbits have
the following exact, disjoint partial coverage:

- `(210)`: 203/406 canonical side roots (50.0%).
- `(111)`: 70/841 typed first-pair roots (8.32%).
- `(110)`: 75/841 typed first-pair roots (8.92%).
- `(100)`: 1,604/11,774 typed first-pair roots (13.62%).
- `(000)`: 56,318/82,215 interior first-pair roots (68.50%).

The summary hashes every complete aggregate and partial interval aggregate.
The bounded campaign audited 121,384,089 DFS nodes, including overlap from
timed-out prefixes.  Every individual segment was capped at 60 or 90 seconds
and 100,000,000 nodes.  No feasible leaf or payload appeared.

`typed_pair_dfs.py` is the new low-boundary decomposition.  It was checked on
both feasible and infeasible small-grid transitions against the original
category DFS; `self_check.json` in the q=30 canonical run also retains the
independent q=8 HiGHS comparison.

Do not blindly extend the remaining q=30 gaps: the low-boundary roots deliver
too little certified coverage per CPU minute.  The recommended next discrete
family is the sparse adaptive q=143 mesh in `ADAPTIVE_Q143.md`, where the exact
threshold `747/143^2` overshoots the gate by only
`1.2782740640637929e-8`.

## q=143 adaptive-window result

The recommended q=143 campaign is complete at its initial hard budget.  The
17 public solutions reduce to ten distinct rounded/D3-canonical seeds.  Exact
SAT across 28 adaptive stages proves 24 windows UNSAT; four radius-5-scale
instances remain unresolved after exactly 50,000 conflicts each.  No feasible
leaf or candidate appeared.

Canonical summary:
`runs/20260815T031000Z/heilbronn-triangles/summary.json`
(SHA-256
`7cc482375bcd6f55401ef9b13372dafe6d64df1ced9c399f9451a7042d8f7655`).
The run audited 24,078,131 clauses and 72,460,844 exact labeled-triple
combinations.  See `ADAPTIVE_Q143.md` for the stage-level scope, limits, and
reproduction command.

The exact UNSAT statements apply only to the recorded nonuniform windows.
They do not close the four conflict-capped stages, the full q=143 grid, or the
continuous problem.  Re-running unchanged at the same budget is not useful;
a continuation would need clause learning persisted across bounds, a
different encoding, or released-label pools.  No Docker replay or external
write occurred because there was no payload.
