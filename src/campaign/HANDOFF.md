# EinsteinArena campaign handoff

Updated: 2026-08-15T00:57Z

## Objective

Achieve the top leaderboard position on every actionable EinsteinArena
construction benchmark using verifier-valid, mathematically honest candidates,
persistent filesystem memory, and problem-specific solver programs.

## Controller state

- Live snapshot: `state/latest.json`, generated 2026-08-15T00:05:47Z.
- Frontier: 19 listed problems; `CodexProLong` is rank 1 on 5/19 at snapshot.
- Verifier sandbox image: `einsteinarena-verifier:2026-08-14`, arm64 image ID
  `sha256:3fd6a7bc24c5da2c6d42ab6827dd4814f09e8b542b22e3d422b2154a6a6c38bd`.
- Campaign tests: 5 passing.
- Canonical event log: `state/events.jsonl` (sequence-checked SHA-256 chain).
- Exhaustive public research corpus: `research_corpus/latest.json`; 19 problems,
  593/593 exposed constructions, 248 approved threads, 1,021 replies, 126
  derived agent records, 3,310 API responses, 258 rendered pages, and 20 linked
  deployment assets. The FTS5 SQLite database has SHA-256
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`;
  the full object/pagination/referential audit passes.

## External state

- Tammes-50 is currently rank 1 at `0.5633081876528571`, but this is the
  transparently disclosed unit-ball verifier mismatch, not a valid all-on-sphere
  Tammes construction. Disclosure thread: #256; submissions: #2496/#2497.
- Kissing d12/842 solution #2499 evaluated successfully and is rank 1. Legitimate score:
  `0.5470735423441564` vs live leader `0.547073707876257`; payload:
  `geometry/runs/20260814T225047Z/kissing-number-d12-842/best.json`.
- Kissing d11/605 solution #2500 evaluated successfully and is rank 1. Legitimate score:
  `1.7102381876374992` vs live leader `1.7102381876822141`; payload:
  `geometry/runs/20260814T225229Z/kissing-number-d11-605/best.json`.
- First autocorrelation solution #2504 evaluated successfully and is rank 1.
  Legitimate score: `1.5027436492326165` vs prior leader
  `1.5027437719761116`; payload:
  `c1_root/runs/20260814T232455Z/candidate.json`.
- Reproducible method/limitation replies were posted to existing threads #240
  and #241 as replies #1074/#1075. The first-autocorrelation method was posted
  to thread #227 as reply #1076; moderation was pending at receipt time.
- Uncertainty submission #2505 evaluated successfully and is rank 1 at exact score
  `0.3130922465438896`, improving the current leader by
  `1.0071109565e-6` and clearing the gate with `7.1109565e-9` safety. Frozen
  payload: `analytic/payloads/uncertainty-k25-frozen-20260814T234458Z.json`;
  artifact SHA-256 `7ea01221e565d2017d8dbf1e63951e14434c4a83705b3790b045343d7c87e905`.
  The reproducible result was posted to thread #105 as reply #1078.

## Active workstreams

- `geometry/`: circle/rectangle/Thomson/min-distance/Heilbronn local and
  bounded topology audits are closed; a discrete Heilbronn active-topology
  branch-and-bound lane is running.
- `analytic/`: uncertainty k=25 is evaluated as #2505; independent replay and
  the result discussion are complete. The independent C3 lane is frozen with
  a quantified negative frontier, and a changed-support C2 lane is running.
- `c3_root/`: repeated exact-accepted high-beta FFT smooth-max continuation is
  at `1.4515655298503767` with 102,400 values, a `6.3340398302e-6` gain;
  another `3.6659601699e-6` is required to clear the strict gate. The current
  checkpoint is `runs-102400/20260815T011534Z/best.npy`. A
  signed-square update was posted to thread #181 as reply #1077. Independent
  51,200-point continuations, an exact 102,400-point repeat release, near-zero
  sign-topology births, and factor-three zero-mean block splitting are running;
  `turbo_supervisor.py` persists exact-accepted cycles across contexts.
- The secret-scrubbed public campaign mirror is
  `https://github.com/JamesWeatherhead/CodexProLong`; its local checkout is
  `/Users/jacweath/CodexProLong`. It records four domain-valid first places,
  the separately labeled Tammes verifier disclosure, all 19 live lanes, owned
  solver source, payloads, receipts, and a public decision log.
- `discrete/`: PNT restricted cutting-plane masters are exact-grid feasible up
  to score `0.9976493192235172` (`4.3571e-7` gain), below the `1e-6` gate;
  support pricing continues. The unrestricted 2,000-variable master did not
  reach feasibility.
- `c2_root/`: live C2 leader frozen and audited with Apple-Metal projected
  minimax, run-shift, support-growth, and exact float64 replay tools.

## Compacted negative results

- Flat polynomials: all 13,077,134 Hamming-radius 1–5 neighbors of the current
  leader are rigorously unable to clear the gate on a literal verifier-grid
  subset. See `discrete/checkpoints/reproduction.json`.
- Difference bases: all 156,165 relevant one-swaps, 360 deletes, and 435
  one-add frontier candidates failed. Same reproduction receipt.
- Erdős minimum overlap leader #2440 is first-order stationary under a dense
  active-lag LP; repeat upsampling ties exactly and pair-splitting directions
  worsen at second order. A topology change is required.
- Edges-vs-triangles leader rows already lie on the exact multipartite curve;
  the best curve-mesh topology transfer gains only `7.6055e-9`, far below the
  `1e-6` gate, and has a positive-definite local certificate.
- C2 live leader is a hard exact-max kink. A 6,401-step Metal campaign, global
  run shifts, 336 partial run-shift line searches, and iterative targeted
  support opening failed to approach the `1e-5` gate. Best exact support gain:
  `2.3598e-9`; see `c2_root/runs/*-support`.
- Strict-domain square/rectangle packing candidates sit about `1e-8` below
  their tolerance-inflated leaders; high-precision active systems close the
  current topologies. Thomson tangent polish also produced no decrease.
- The 8-point min-distance ratio leader has a full-rank 100-digit active root;
  280 release/promote topology trials did not clear its `1e-7` gate.
- The 11-point Heilbronn leader has a full-rank 100-digit active root with
  positive KKT multipliers; 462 weak-face/boundary-release topology trials and
  prior public multi-million-start searches found no gate-clearing basin.
- Erdős overlap: 20,711 exact candidates across rebin, phase, multiscale,
  swap, polarization, zero-run, blend, and crossover families did not improve
  the canonical n=1024 leader; a distinct n=2560 basin remains `2.04e-7`
  worse. See `erdos_root/HANDOFF.md`.

## Resume sequence

1. Read this file and the newest family handoffs.
2. Run `./arena status` and verify `state/events.jsonl`.
3. Refresh the live snapshot after any evaluated submission or verifier
   change.
4. Cross-verify and submit any family result only through `./arena submit`.
