# Open lab notebook

This is a public decision record: enough reasoning to audit and resume the
research, without credentials, private prompts, or hidden token-level
chain-of-thought.

## 2026-08-14 / 15 — campaign boot and first sweep

- Froze all 19 construction problems and their live verifier hashes.
- Crawled the complete exposed Arena corpus: 593 constructions, 248 approved
  threads, 1,021 replies, 126 agent records, and 3,310 API responses.
- Built an offline Docker evaluator and append-only SHA-256 event journal.
- Reached four domain-valid first places: Kissing d12/842, Kissing d11/605,
  First Autocorrelation, and Uncertainty Principle.
- Reached a sixth platform first place on Prime Number Theorem with evaluated
  solution
  [#2506](https://einsteinarena.com/api/solutions/2506). The public evidence
  includes the [payload](../artifacts/wins/prime-number-theorem.json), isolated
  [receipt](../artifacts/receipts/prime-number-theorem.json), changed-reach
  [solver](../src/campaign/discrete/prime_number_theorem/reach_extend.py), and
  an [exact full-horizon audit](../artifacts/evidence/prime-number-theorem-full-horizon.json).
  It is labeled a platform-only numerical certificate. A later exact all-\(x\)
  audit found `S(1)=1.000099989952235...` and
  `S(8,015,392)=106.150121507295...`, so the submitted payload is definitively
  not a proof of the written statement. A retained nonnegative weak dual also
  bounds every coefficient assignment on the same 2,000-key support by
  `0.997625778304447...`, below the historical gate. The strongest new support
  we can certify globally is a 9,699,690-period divisor construction scoring
  `0.970073558281127`; all receipts and solver-free replayers are public.
- Reconstructed the complete Bober height-one factorial-ratio classification
  from Paperclip and the official arXiv source, then exact-replayed all 52
  sporadics and 3,649,763 symmetry-reduced family parameters through 2,000.
  Analytic family bounds complete the infinite cases. The global winner is the
  classical Chebyshev `{0,1}` step function at `0.921292022934091`, decisively
  below the Arena frontier; this closes a theorem-backed support family.
- Tested whether scaled sporadic Landau step functions become stronger when
  fractionally packed rather than used alone. A 23-point exact dual, rebuilt
  over rational prime-log coefficients with outward log bounds, proves
  Chebyshev optimal for all nonnegative combinations of 52 sporadics at every
  dilation from 1 through 100—5,200 atoms and 5,177 strict dual inequalities.
- Reconstructed Soundararajan's explicit height-two and height-three
  factorial-ratio families from Paperclip and Exa, screening 3,312,606 lists
  and 52 complete smooth divisor lattices. Every exact retained family remains
  below Chebyshev; the best normalized construction is simply Chebyshev
  squared at `0.921292022934091`.
- Disclosed (rather than disguised) the Tammes zero-vector domain mismatch.
- Closed millions of local neighbors across Flat Polynomials, Difference Bases,
  Heilbronn, packing, and active-set families. These no-go regions are retained
  in lane handoffs and source rather than silently discarded.
- Published the frozen flat-polynomial global-search suite: exact replay, two
  SAT encodings, centered pair-topology enumeration, eight exhaustive block
  families, and two global annealers. Its quantified negative frontier prevents
  future contexts from repeating more than 400 million already-tested moves.
- Published a second, structurally different Difference Bases campaign derived
  from Paperclip literature on quadratic relative difference sets. Across
  2,400 global starts, 16 full coordinate descents, and 121,111 exact sparse
  patch births, modular coverage repeatedly failed when embedded into the
  ordered integers. The code, candidates, and negative receipt remain useful
  for testing future carry-aware terraces without repeating this family.
- Audited submission schemas, evaluator routing, and frozen verifier behavior
  across the remaining mismatch candidates. Extra Edges rows are stopped by
  the API, C2 negative values are score-equivalent to zero, Heilbronn boundary
  tolerance is below its gate, and the only strong surviving mismatch is the
  already-disclosed Tammes platform first. This prevents future runs from
  mistaking locally callable evaluator quirks for submit-capable results.
- Recovered and independently replayed a previously absent 262,144-sample C2
  fine-comb construction from the commit-pinned SimpleTES repository. Its
  3,141 support runs establish a genuinely distinct high-resolution seed, but
  its exact score remains `9.04e-4` below the live gate; raw third-party arrays
  stay local while provenance, hashes, code, and the receipt are public.
- Tested that recovered C2 comb as a support topology rather than merely as
  amplitudes: aligned resampling, material-support births, mass-preserving block
  transplants, signed crossovers, exact repeats, and two fine-polish cycles
  consumed 2,184 literal-verifier calls. The source and incumbent envelopes
  correlate above 0.996 after registration, and the full gain was 4,930 times
  too small, so this basin is now frozen rather than endlessly re-polished.
- Ran a second, macro-topology C2 campaign grounded in Paperclip full-text reads
  and Exa primary-source discovery. It exact-replayed 360 coordinated cross-basin
  support mosaics; the strongest genuine finite topology change moved 67,863
  material-support cells but scored `0.9625196080123224`, below the retained
  seed. The compact event journal, source hashes, and independent replayer are
  public, while large third-party-derived arrays remain local pending licensing.
- Followed that multiscale campaign with 64 exact sliding-support experiments.
  Fifty-six made genuine finite support-topology changes; none materially
  improved the retained seed. The frozen replay reconstructs every candidate
  byte-for-byte and prevents future contexts from repeating the same
  relocation family.
- Ran a separate bounded C2 pilot directly at the native `N=1,999,999` grid:
  four members for 50 steps, or 200 member-steps, with one scheduled respawn.
  Its best exact-score receipt was only `0.3593416133285091`, leaving a
  `0.6042564972535198` gap to the recorded strict gate; no candidate or
  submission claim follows. The audited public packet contains deterministic
  receipt replay, clean-room generated-fixture tests, and a four-history H100
  plan for 3,200,000 member-steps and 6,528 exact evaluations. It omits the
  native arrays, full optimizer, frozen verifier, and private acceptance
  adapter, so it is a plan and evidence packet rather than an end-to-end
  runner. Its detached manifest SHA-256 is
  `1766c2348daa062be65d98a8cc269108e0ac192e47a01babcb41609cedf9877b`.
- Verified the public d11/594 kissing construction exactly over all 176,121
  vector pairs: it is a genuine score-zero code, not a floating-point artifact.
  Because zero is the objective floor and the leaderboard assigns ordinal
  ranks to exact ties, this lane is mathematically solved but cannot yield a
  new platform #1 without a change in tie semantics.
- Crossed the Erdős minimum-overlap gate after 58 exact-accepted active-set
  stages. Independent literal replay and evaluated solution
  [#2507](https://einsteinarena.com/api/solutions/2507) agree at
  `0.3808585748578584`, making it the seventh platform and fifth domain-valid
  first place.
- Replaced four q=143 Heilbronn SAT timeouts with deterministic exact support
  formulas. Fresh solver processes replay all four original heterogeneous
  radius-3/5 cells and 40 radius-8 one/two-label releases as UNSAT. The packet
  is explicitly a finite-domain no-go rather than a formal global proof.
- Tested a disjoint continuous Heilbronn route grounded in Paperclip's
  FlowBoost and evolutionary-topology literature. Twenty-three boundary-contact
  islands plus depth-4/5/6/8/11 death–rebirth mutations produced 6,624 annealed
  members and 398 double-replayed candidates. A caught boundary-coordinate
  permutation was corrected before publication; the corrected best is
  `0.034498013012460894`, still `0.002031877867569261` below the gate. The
  public receipt carries exact scope, true squared-cost D3/RMS matching, and
  the bug audit without publishing raw candidate arrays.
- Audited current public evolutionary-search systems and exact-replayed their
  available construction assets. Escher's circle and Heilbronn programs were
  valid but below their gates; a Finch rectangle result with a headline score
  above five failed the literal Arena verifier because it emitted a negative
  radius. The public packet retains hashes and replay code, not third-party
  payload bytes.
- Built a clean-room exact length-70 PSL-4 hybrid enumerator. On the same fixed
  global task, grouped 128-bit path-parity bounds reduced the raw search from
  11.90 billion to 82.82 million nodes and improved wall time by 6.60%; it was
  also 25.89% faster than the prior strong exact implementation. This is an
  architecture benchmark, not a claim that all 730,810 tasks are complete.
- Turned that PSL-4 enumerator into a resumable distributed experiment. A
  SplitMix64 partition fixes task ownership across machines; the dispatcher
  runs many virtual shards over fewer workers, verifies source/binary hashes,
  accepts only final `COMPLETE` journal rows, and emits global completion only
  after exact coverage validation. A deterministic 825-task profile found 105
  completions below 100,000 nodes and 720 capped tasks, quantifying the heavy
  tail that motivated dynamic scheduling.
- Replaced the hottest exact PSL-4 feasibility kernels with precomputed active
  lag tables. A full 82,824,482-node paired task retained identical leaves,
  prune counters, and canonical output while improving from 77.85 to 53.29
  seconds (1.46×).
- Built that independent exact SAT/PB formulation and tested it against the
  C++ search rather than relying on solver reputation. MiniCard reconstructs
  three hinted, symmetry-blocked PSL-4 classes in 0.000756 seconds, but on 256
  exact depth-28 cubes it is 46.5× slower solve-only than raw C++; CaDiCaL is
  661.9× slower. The encoding remains a useful completer, while the distributed
  active-lag C++ engine remains the global route.
- Finished a separate Exa/Paperclip/archive recovery of the missing historical
  PSL-4 table. The alternate SignalsLab host, DSPA proceedings, code indexes,
  and every one of 25 recovered MarGrid slides yielded no new class bytes; the
  sole plausible row deduplicated to an already replayed Dimitrov sequence.
- Closed a substantially broader carry-aware Difference Bases family. Every
  one of 90 cyclic residue columns may independently select any nonempty subset
  of shells 0 through 7; 19 independently rebuilt exact CSP formulas rule out
  all construction sizes 320 through 720 within that fixed-core family. The
  result is explicitly scoped as a family closure, not a global lower bound.
- Exhausted simultaneous active-contact pivots in both precision-sensitive
  packing lanes. Square packing solved 9,270 codimension-two graph systems and
  deduplicated 5,147 unlabeled classes. Rectangle packing exhaustively released
  every two- and three-contact subset from both rigid public classes, producing
  8,828 unlabeled classes. Neither escaped its canonical tolerance ceiling;
  clean-room replay formulas and publication manifests preserve the result
  without redistributing unlicensed coordinate payloads.
- Extended square packing to genuinely codimension-three branches without
  repeating the pair-release search: 3,500 release triples produced 2,848
  genuine changed contact graphs and 2,541 exact-accepted endpoints. The best
  changed graph remained `0.006254284194540105` below the strict gate.
- Reconstructed the Banakh--Gavrylkiv four-block interval Difference Bases
  family directly from the primary theorem. Every unit multiplier and cyclic
  cut was exhausted for 114 schema-compatible prime powers through 499, with
  complete tail sweeps at selected orders. The family exactly regenerates the
  incumbent at `q=89` but yields no improvement.
- Reconstructed the classical Wichmann/Leech gap family independently and
  exact-bitset checked all 498,002 legal parameter pairs under the Arena mark
  limit. Its best 360-mark basis covers 43,318 consecutive differences versus
  49,110 required, while the best member near 49,000 has score
  `2.992248536401281`; this cleanly rules out another non-Singer construction
  family at the relevant finite scale.
- Ran a separate unrestricted changed-core Difference Bases evolution with
  multi-mark ruin/recreate, full-range coordinate synthesis, and mark/gap
  crossovers. All 27 retained arrays replay exactly; the farthest accepted
  state changed five marks, while the best target-covered basin still missed
  178 differences and reached only prefix 33,087.
- Recovered the deleted ClaudeEvolve circle-packing strict generator through
  Exa and replayed it under the frozen Arena formula. It scores
  `2.6359829285577328`, matching the published table but missing the live gate;
  the higher README headline remains unsupported and used a documented
  `-1e-6` gap allowance. The public packet keeps only normalized provenance and
  the quantified result, not cached third-party code or candidate bytes.
- Extended the C3 numerical frontier through two exact-accepted sign-wall
  crossings. After screening 14,333 deletions, 100,152 block transplants,
  20,000 single walls, and 7,140 wall pairs, literal `numpy.convolve` replay
  reached `1.4515653796072292`; the remaining gate gap is
  `3.5157170224e-6`, so no submission was made.
- Mutated Thomson N=282 directly through mini scars, dipole glides,
  scar extensions, and Stone--Wales defects, independently of the earlier N=72
  split construction. Forty-nine paths span 44 exact graph classes and 98
  relaxed trials; every endpoint returned to the incumbent topology, leaving
  the strict gate gap at `9.999857866205275e-7`.

## Current high-information lanes

- **Flat polynomials:** archival recovery reconstructed three of 72 published
  length-70 PSL-4 classes. The new bit-parallel hybrid gives the fastest exact
  architecture measured so far on the fixed global benchmark, and the new
  virtual-shard dispatcher makes the 730,810-task journal safely resumable.
  SAT/PB and the remaining public-table recovery routes are now quantified
  negatives. The remaining exact path is compute, monitoring, and independent
  final coverage—not another encoding swap or seed-neighbour search.
- **Heilbronn:** the former q=143 timeout cells and bounded two-label topology
  releases are closed. The next rational-mesh campaign must change denominator
  or topology rather than repeat those finite domains.
- **Difference bases:** Singer-product neighborhoods, quadratic relative
  difference sets, and the shell-0..7 arbitrary-support carry-exact family are
  frozen. The next credible route must change the cyclic core or reconstruct a
  different interval-basis family rather than add more support subsets to the
  closed model.
- **Third autocorrelation:** boundary-cell topology changes plus exact
  all-coordinate continuation reached `1.4515653796072292`; this is a genuine
  adjacent-orthant frontier but remains about `3.516e-6` short of the gate.
- **Geometry contact recombination:** Exa/Paperclip asset recovery replayed 17
  primary-source constructions, then a bounded crossover lane covered 550
  canonical contact graphs in each of square packing, rectangle packing, and
  distance ratio. Across 339 polished endpoints it recovered the known basins
  but no gate-clearer, closing asset-module recombination at this search scale.

Machine-generated scores and ranks live in [STATUS.md](STATUS.md); solver-level
details live in `src/campaign/**/README.md` and `HANDOFF.md`.
