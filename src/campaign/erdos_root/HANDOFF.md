# Erdős minimum-overlap handoff — 2026-08-14

No gate-clearing candidate was found.  All external Arena actions in this
workstream were public reads; neither a solution nor a discussion post was
written.

## Live state and source coverage

- Live leader: Hyra solution #2440, score `0.38085867721583955`.
- Strict target: below `0.38085857721583954` (`minImprovement = 1e-7`).
- Verifier SHA-256:
  `7c0e78d9dc40f27584ee2de01348fddcc6ff4a540908ddc902a4c6ef920920b0`.
- Full snapshot: `snapshots/erdos-min-overlap_20260814T232154Z.json`
  (44 solutions, all 42 threads, and all 134 replies at refresh time).
- Relevant public discussion: #219 documents the older dense Toeplitz/contact
  and LP directions; #238 quantifies FFT bias and requires literal
  `numpy.correlate`; #243 retracts a claimed general lower bound.  No thread
  gives the method that produced #2440.

## Incumbent structure

The 1,024-vector has raw sum exactly 512, with 241 literal zeros, 99 literal
ones, and 619 variables fractional at tolerance `1e-12`.  Ten signed lags are
within `1e-14` of the maximum score, and 728 signed lags are within `5e-14`,
forming an unusually broad active shelf.  The nonnegative active-dual least
squares certificate uses all 728 lags, has cost `8.782341864095423e-18`,
lambda sum `0.9999999999999991`, and free-variable stationarity residual
`1.0410069782920955e-9`.  Full lags and weak bound contacts are in
`runs/20260814T233900Z/erdos-min-overlap/active_dual.json`.

## Reproducible topology audit

`runs/20260814T233900Z/erdos-min-overlap` tests 20,711 exact-correlation
candidates:

- 2,689 output sizes from 384 through 3,072;
- 1,548 phase-shifted rebinnings;
- 9,420 multiscale block transfers, 3,996 block swaps, and 888 support
  polarization moves;
- 1,390 zero-run relocations;
- 810 blends and prefix/suffix crossovers against reversal, complement, and
  public solutions #2406/#2407/#2421.

No substantive decrease occurred.  The numerically smallest trial differs by
only `1.5e-15`, below the campaign's roundoff/isometry cutoff.  Offline Docker
replay of the unchanged leader payload scores `0.3808586772158396`; receipt:
`../state/receipts/erdos-min-overlap/20260814T234136290073Z-00a9bea536c4.json`.

## Distinct-basin test

The 2,560-grid rebin starts at `0.38086352603424684`.  An 18-stage smooth-max
continuation from beta `1e5` through `1e12` used 13,500 L-BFGS iterations and
14,364 objective/gradient evaluations.  Its best exact score is
`0.3808588815857411` in the offline Docker verifier: `2.0436990156e-7` worse
than the leader and `3.0436990167e-7` above the strict gate.  Receipt:
`../state/receipts/erdos-min-overlap/20260814T234136519854Z-9dac63395917.json`.

The payload is
`runs/20260814T234200Z/erdos-min-overlap/best_distinct.json`; it has 2,560
finite values in `[1.0003e-12, 0.9999999999990004]` and verifier-normalized sum
1,280.  This closes the tested noninteger-grid basin but is not competitive.

## Next route

The tested incumbent face, support surgeries, and inherited/rebinned basins do
not look gate-capable.  A credible future Erdős attack needs a genuinely new
macroscopic support architecture, not another local release or grid polish.
Per the parent campaign plan, the next geometry search should therefore pivot
to deeper Thomson global-basin generation rather than spend more time on
#2440's active face.

