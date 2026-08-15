# EinsteinArena campaign handoff

Updated: 2026-08-15T02:01Z

## Objective

Achieve the top leaderboard position on every actionable EinsteinArena
construction benchmark using verifier-valid, mathematically honest candidates,
persistent filesystem memory, and problem-specific solver programs.

## Controller state

- Live snapshot: `state/latest.json`, generated 2026-08-15T01:34:31Z.
- Frontier: 19 listed problems; `CodexProLong` is rank 1 on 5/19 at snapshot.
- Verifier sandbox image: `einsteinarena-verifier:2026-08-14`, arm64 image ID
  `sha256:3fd6a7bc24c5da2c6d42ab6827dd4814f09e8b542b22e3d422b2154a6a6c38bd`.
- Campaign tests: 7 passing.
- Canonical event log: `state/events.jsonl` (sequence-checked SHA-256 chain),
  through event 51 (`discussion_reply`).
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
- Kissing d12/841 now has a domain-valid exact score-0 construction from the
  Takhanov--Assylbekov--Yun published coordinates. Candidate SHA-256 is
  `236d3931724d28cf306ecbda064c1ffb84e8a106e363227f00e6d5b147eb4749`;
  verifier SHA-256 is `eb043620439a6631451657013a12c66e55db43589431bcdad08e3b2189246ca8`;
  all 353,220 pairs pass with Decimal squared-distance margin
  `1.2449713530886666648293011033664e-7`. The one validated submit attempt
  returned HTTP 409, "Submissions are disabled for this problem," so no rank
  exists. The blocker is [vinid/einstein-arena#59](https://github.com/vinid/einstein-arena/issues/59).
  A source-pinned structural update was posted to thread #198 as reply #1081;
  it was pending moderation in the write response and must not be reposted.

## Active workstreams

- `geometry/`: q=25 Heilbronn is completely certified and q=30/q=143 have
  bounded partial certificates. A fresh square-circle lane is now testing only
  changed contact graphs because same-topology verifier precision is closed.
- `analytic/`: uncertainty k=25 is evaluated as #2505. The n=3,584 Erdős
  active-set SLP has exact score `0.3808586421686005`, improving the public
  leader by `3.5047e-8` but remaining `6.4953e-8` short of the strict gate;
  continuation is checkpointed under `analytic/erdos_global/slp_runs/`.
- `c3_root/`: repeated exact-accepted high-beta FFT smooth-max continuation is
  at `1.4515655298503767` with 102,400 values, a `6.3340398302e-6` gain;
  another `3.6659601699e-6` is required to clear the strict gate. The current
  checkpoint is `runs-102400/20260815T011534Z/best.npy`. A
  signed-square update was posted to thread #181 as reply #1077. A pivoted
  68-mode all-lag epigraph model closed after 4,666 cuts but gained only
  `8.9195e-10`, leaving `3.6651e-6`; a new lane is testing genuinely
  support/topology-changing multiresolution escapes without repeating the
  logged noisy, pair-split, or local-bundle routes.
- The secret-scrubbed public campaign mirror is
  `https://github.com/JamesWeatherhead/CodexProLong`; its local checkout is
  `/Users/jacweath/CodexProLong`. It records four domain-valid first places,
  the separately labeled Tammes verifier disclosure, all 19 live lanes, owned
  solver source, payloads, receipts, and a public decision log. Commit
  `aeb53ae` is authored as Codex and committed by James Weatherhead; the README
  explicitly credits both roles and links the Daybreak and Paperclip pages.
- `discrete/`: PNT exact cutting planes and 600 stratified support-exchange
  topologies are complete. Best full-stream feasible score is
  `0.9976493205324761`; the preserved group payload replays at
  `0.9976492989838522`, both below the `1e-6` gate.
- `c2_root/`: all logged support births, shifts, multiresolution tangents, and
  depth-20 propagation are frozen; best public gain is only `6.6881e-9`, far
  below the `1e-5` gate.

## Compacted negative results

- Flat polynomials: all 13,077,134 Hamming-radius 1–5 neighbors of the current
  leader are rigorously unable to clear the gate on a literal verifier-grid
  subset. See `discrete/checkpoints/reproduction.json`.
- Difference bases: all 156,165 relevant one-swaps, 360 deletes, and 435
  one-add frontier candidates failed. Same reproduction receipt.
- Erdős n=1,024 local/rebin/phase/swap routes are closed, but the changed-grid
  n=3,584 active-set branch is still improving and is the active exception.
- Edges-vs-triangles leader rows already lie on the exact multipartite curve;
  the best curve-mesh topology transfer gains only `7.6055e-9`, far below the
  `1e-6` gate, and has a positive-definite local certificate.
- C2 live leader is a hard exact-max kink. A 6,401-step Metal campaign, global
  run shifts, 336 partial run-shift line searches, and iterative targeted
  support opening failed to approach the `1e-5` gate. Best exact support gain:
  `2.3598e-9`; see `c2_root/runs/*-support`.
- Literal-tolerance square/rectangle active roots remain only `7.92e-11` and
  `8.01e-11` below their gates; full-rank KKT systems close those incumbent
  topologies. Only new contact graphs can win. Thomson tangent polish also
  produced no meaningful decrease.
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
