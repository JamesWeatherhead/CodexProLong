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
  It is labeled a numerical certificate: the advertised finite verifier horizon
  is covered exactly, while the stronger all-\(x\) analytic claim remains open.
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

## Current high-information lanes

- **Erdős minimum overlap:** the changed-grid n=3,584 exact active-set SLP has
  reached `0.3808585875055632`, only `1.0289724e-8` above the strict gate, with
  every continuation stage accepted so far.
- **Difference bases:** Singer-product local neighborhoods and the independent
  quadratic relative-difference-set topology are both frozen. The next credible
  route must coordinate integer carry order directly rather than add more
  finite-group randomization or first-gap patch depth.
- **Third autocorrelation:** boundary-cell topology changes plus exact
  all-coordinate continuation reached `1.4515653850221024`; this is a genuine
  new basin but remains about `3.52e-6` short of the gate.
- **Geometry contact recombination:** Exa/Paperclip asset recovery replayed 17
  primary-source constructions without a gate-clearer. The current bounded lane
  canonicalizes their contact graphs, crosses compatible subgraphs, and subjects
  every child to fixed-center LP plus exact active-set refinement.

Machine-generated scores and ranks live in [STATUS.md](STATUS.md); solver-level
details live in `src/campaign/**/README.md` and `HANDOFF.md`.
