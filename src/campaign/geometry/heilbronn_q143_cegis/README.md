# Heilbronn q=143 exact support closure

This packet closes the four previously unresolved local q=143 lattice cells
(with heterogeneous per-label radius-3/5 windows), then closes a bounded
topology release around each one. It found no gate-clearing construction.

The exact lattice threshold is

```text
747 / 143^2 = 0.0365299036627708
strict live target = 0.036529890880030155
margin = 1.2782740643757506e-8
```

Any satisfying lattice assignment would therefore clear the live gate after
an unchanged-verifier replay. None exists in the finite domains tested here.

## Exact encoding

Each label `i` has exactly one selected lattice point `x[i,p]`. For every label
triple `(i,j,k)`, the builder chooses one support label, say `k`, and emits for
each `(p,q)`:

```text
not g[i,j,k] or not x[i,p] or not x[j,q]
    or x[k,r1] or ... or x[k,rm]
```

The listed `r` values are exactly those satisfying the integer inequality
`abs(det(p,q,r)) >= 747`. With exactly-one selection for `k`, this clause is
true exactly when the unique selected triple meets the threshold. Thus these
support rows are logically equivalent to materializing every forbidden triple,
but are much smaller. Coincident points are excluded separately.

All candidate points for a release model are allocated before the support rows
are generated. Scenario activation literals then restrict each solve to its
active label windows. All 165 triple guards are assumed true. One incremental
CaDiCaL session is reused within each model, retaining learned clauses across
the base, four single releases, and six pair releases.

## Results

The four-cell base union has domain sizes
`[51,51,91,91,108,57,102,51,51,108,51]`. Its 812 decision variables compile
to 131,298 clauses and 3,298,876 literals. The support section alone has
128,521 clauses, versus 5,240,900 forbidden-tuple clauses. Formula SHA-256:

```text
d317f82ee2e014ec1ec92087f0446c3fe102cbead33f25f4d6044fb5f15f3461
```

All four original scenarios are exact solver UNSAT. The bounded release sweep
uses radius 8 for every one- and two-label subset among the four
pressure-ranked labels per seed:

| Public representative | Ranked labels | Scenarios | Formula SHA-256 |
|---:|:---|---:|:---|
| 630 | 1, 6, 3, 4 | 11 UNSAT | `9ca91328d3cf50a5db59ad41c8562f7b44ff6b85d0a979377221af0590270bee` |
| 1005 | 1, 3, 4, 9 | 11 UNSAT | `1f1a451645501aa0a383957352566fc3d13f929f69ec46d8061fd61b30d5e994` |
| 1004 | 0, 3, 9, 4 | 11 UNSAT | `48b2da2bb0775bc7ed6ebf1c21f8cb1c8815a29c08b06bb80de325e2956e3f28` |
| 649 | 0, 3, 9, 4 | 11 UNSAT | `87bd75112cf6dea0897cff801a4ebc0999188d6750d5916eec0c39097b114efa` |

The 44 release-model scenarios comprise four repeated bases, 16 single-label
releases, and 24 two-label releases. Fresh-process replays reproduce the same
formula and assumption fingerprints and all UNSAT outcomes. The compact
inventory and raw-run hashes are in `receipt.json`.

The earlier literal CEGIS implementation is retained in `q143_cegis.py` as a
quantified negative result: on representative 630 it separated 2,164 SAT
models and accumulated 5,066,336 exact tuple no-goods over about 122 seconds
without closure. `support_closure.py` replaces that materialization bottleneck.

## Reproduce

From the repository root, with the existing environment (`python-sat
1.9.dev14`, NumPy 2.5.2):

```bash
.venv/bin/python campaign/geometry/heilbronn_q143_cegis/support_closure.py \
  --stamp MY_BASE_REPLAY --skip-releases

.venv/bin/python campaign/geometry/heilbronn_q143_cegis/support_closure.py \
  --stamp MY_RELEASE_REPLAY --skip-base-union \
  --release-radius 8 --release-label-count 4
```

Exit status 2 means the bounded sweep completed without a gate-clearer; inspect
the run's `summary.json`. Wall time is checked between bounded conflict slices,
so one slice can slightly overrun `--scenario-seconds`. Checkpoint resume is at
scenario granularity: it validates the full run configuration and source/input
hashes, then rebuilds the formula in a fresh solver rather than serializing
learned clauses. If a future model is found, replay it independently:

```bash
.venv/bin/python campaign/geometry/heilbronn_q143_cegis/verify_candidate.py \
  campaign/geometry/heilbronn_q143_cegis/runs/MY_RUN --scenario SCENARIO_KEY
```

## Scope

This is a finite-domain no-go, not a global q=143 lattice proof and not a
continuous Heilbronn upper bound. The UNSAT evidence consists of deterministic
exact-formula hashes, CaDiCaL results, assumption cores, and fresh-process
replays; it is not a checked DRAT/LRAT proof object. No Arena, discussion,
submission, or GitHub mutation was made.

## Literature grounding

- Bloem et al. describe add-only incremental CDCL with retained learned clauses
  and activation assumptions: [arXiv:1604.06204, lines 82–88](https://paperclip.gxl.ai/citations/papers/arx_1604.06204#L82-L88).
- The same paper formalizes the finite candidate/counterexample CEGIS loop:
  [lines 165–173](https://paperclip.gxl.ai/citations/papers/arx_1604.06204#L165-L173).
- Monji, Modir, and Kocuk formulate Heilbronn optimization through the absolute
  signed determinant and exact computational structure:
  [arXiv:2512.14505, lines 8–13, 18–22, 93–97](https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L8-L13,L18-L22,L93-L97).
