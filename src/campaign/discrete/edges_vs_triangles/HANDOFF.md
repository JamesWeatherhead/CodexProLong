# Edges vs triangles global-allocation handoff — 2026-08-15

## Outcome

No strict `1e-6` gate-clearer was found, and no Arena or GitHub write was made.
The strongest unchanged offline-controller replay remains the exact
complete-multipartite curve mesh:

- live leader: `-0.7117091757692579` (CHRONOS solution `#2367`);
- replayed score: `-0.7117091681637201`;
- improvement over the leader: `7.605537755139835e-9`;
- required improvement: `1e-6`;
- remaining gate shortfall: `9.923944622448601e-7`;
- verifier SHA-256:
  `800ae2fbd2619d50de2177d49609289813bb6a2000b350f63e22820ad667052e`.

The result is mathematically intended-domain: exactly 500 rows of 20 finite,
nonnegative weights, each row on the proven minimum-triangle curve.  The
largest edge-density gap is the unavoidable floating representation of
`0.05`.  The API-rejected over-500-row boundary is not used.

## Frozen controller receipt

- Candidate:
  `runs/20260815T023100Z/global_dp/candidate.json`
- Artifact-file SHA-256:
  `5754da3a85e78445fe5eebde5295de3ff28d00ed180e339de0e615b63868bfc4`
- Controller canonical-JSON SHA-256:
  `c71bc6912f5a57f1a6f22fac2c5f6007584eeca0de01877962cc14b57a89d6dc`
- Receipt:
  `../../state/receipts/edges-vs-triangles/20260815T024004430186Z-c71bc6912f5a.json`
- Receipt SHA-256:
  `74559e08b00b700c49d1d153c44ffc17e5e842e9419391dba7c26c10a7d5f4fb`

Replay only through the offline controller:

```bash
cd /Users/jacweath/EinsteinArena/campaign
./arena verify edges-vs-triangles \
  discrete/edges_vs_triangles/runs/20260815T023100Z/global_dp/candidate.json
```

The controller independently returned the score, shape acceptance, verifier
hash, and `clears_first_place_gate: false`.

## Complete retained-corpus audit

The audit read all 23 retained constructions, all three threads (`#116`,
`#155`, `#160`), and all 21 replies before the new search.  It parsed
`1,544,094` solution-record bytes and recomputed every score without importing
the downloaded verifier.  Sixteen constructions already lie on the exact
curve to `1e-12`; the rest are pointwise above it or lose on coverage.

- Frozen corpus database SHA-256:
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.
- Audit: `runs/20260815T023000Z/audit/corpus_audit.json`, SHA-256
  `3f6c5c2a9cb448931981292d8478c55dc25979a746c158f5ee18b9ae9f454434`.
- Summary: `runs/20260815T023000Z/audit/summary.json`, SHA-256
  `5aa5ea1366a9b2dccd4411aae70e924f92018ded7b20988ce468fe54ec444b32`.

The prior certificate had already closed coordinate polishing and found the
only improving one-row transfer.  The current work does not repeat that local
exchange: it solves the complete integer allocation and then changes multiple
transition-node topologies.

## Why arbitrary row families are dominated

For a normalized row `w`, the verifier's point is

```text
x = 1 - sum(w_i^2)
y = 1 - 3 sum(w_i^2) + 2 sum(w_i^3).
```

The clique-density theorem says the minimum feasible triangle density at fixed
edge density is attained by a complete multipartite graph with all but one
part equal [1].  In the triangle case, Razborov proved this exact curve with
flag algebras; the weighted-graph formulation and its equivalence to graph
blowups are explicit in Reiher's treatment [1].  The AlphaEvolve paper gives
the same closed form and explains the horizontal-left/slope-three-right
envelope used by this benchmark [2].

Each verifier segment area is nondecreasing in either endpoint height: on the
active cap branch it is

```text
A((x0,y0),(x1,y1)) = y1 (x1-x0) - (y1-y0)^2 / 6,
```

whose two height derivatives are nonnegative whenever the secant slope is in
`[0,3]`; the verifier's other branches preserve the same monotonicity.  Thus
replacing any off-curve row by the exact curve point at the same `x` cannot
increase area.  Alternative valid 20-bin weight families cannot beat the
pointwise curve; only global placement of the 500 edge-density nodes remains.

The 20-bin Cauchy bound forces `x <= 19/20`, hence a terminal gap of at least
`0.05`.  Ten zero-triangle rows at `0.05, 0.10, ..., 0.50` are the minimum
needed to attain that gap floor below `x=0.5`.  Spending more rows there does
not reduce area, while spending fewer increases the gap penalty by orders of
magnitude more than one high-density row can recover.

## Exact global branch allocation

`global_dp.py` computed the unique damped-Newton mesh cost for every count
`0..472` on every smooth scallop `r=3..20`: 8,514 independently optimized
branch/count states.  It then solved the full 18-branch resource allocation by
dynamic programming, cross-checked by globally sorting all marginal benefits.

All 18 branch cost arrays are strictly discretely convex over the complete
count range.  Their smallest second differences remain positive, from
`1.9428875869254014e-10` on branch 3 down to
`1.2490442707902005e-14` on branch 20.  Therefore the marginal-prefix solution
is also a global allocation certificate, not a one-exchange heuristic.

The unique optimum allocates the 472 smooth-interior nodes as follows:

```text
r:      3   4   5   6   7   8   9  10  11  12  13  14  15  16  17  18  19  20
count: 202  98  55  34  22  16  11   8   6   5   4   3   2   2   1   1   1   1
```

Together with ten zero-triangle rows and 18 transition rows this is exactly
500 rows.  The second-best complete allocation costs
`8.932553863250092e-10` more; the independently computed selected/rejected
marginal gap is `8.93255367243051e-10`.

- Summary: `runs/20260815T023100Z/global_dp/summary.json`, SHA-256
  `9db9c46da3f6364357db5c3aec3ca9e699deb8ff72675897f0ff215ae92e8d16`.
- Complete cost table: `runs/20260815T023100Z/global_dp/cost_table.json`,
  SHA-256
  `0e7846a50c030505594d897bf217f20c9054235a186bca7b22dcd882c95ee6d1`.
- Append-only events: `runs/20260815T023100Z/global_dp/events.jsonl`,
  SHA-256
  `8e67a5703a3e1742b882d7d243dfb9ac0ceeac4244b8047e4a7ec33e47f3f923`.

## Coordinated transition-topology search

There are 17 internal non-smooth curve transitions.  Removing `s` of their
rows frees `s` rows for global interior reallocation and creates coupled
multi-scallop blocks.  `transition_topology.py`:

1. screened every one of the `2^17-1 = 131,071` nonempty removal masks;
2. refined 323 masks, including every 153 contiguous removal block, the eight
   strongest additive masks at every cardinality, and deterministic stratified
   masks;
3. used three deterministic L-BFGS starts per multi-scallop block;
4. ran both a closure search (`1e-12` transition exclusion) and a genuinely
   separated search (`1e-6` exclusion); and
5. globally reallocated `472+s` interior rows for every removed cardinality.

No refined mask beat the retained-transition optimum.  The best closure mask
removes transition 7 but returns a row to within
`1.009969885501505e-12` of that same kink; its cost differs from the base by
only `+3.33e-16`, so it is the incumbent topology in the limit.  The best
genuinely separated mask removes transition 6 and is already
`2.402739673890153e-10` worse.  Its offline replay is
`-0.711709168403994`, versus `-0.7117091681637201` for the retained optimum.
For two or more simultaneous removals, the strongest refined closure is at
least `4.730867753099943e-9` worse; removing all 17 is about
`8.36e-7` worse.

- Summary: `runs/20260815T023200Z/transition_topology/summary.json`, SHA-256
  `52c6c96e4729c6b58e4e1a6d9cb47419d0a98366b69a1b698a2c3c4ef6fa379b`.
- Full screen/refinement table:
  `runs/20260815T023200Z/transition_topology/screening.json`, SHA-256
  `fa25f5eefeb7fd33b7000718822f860af42eadfd83ba1f843810c967de701f8e`.
- Append-only events:
  `runs/20260815T023200Z/transition_topology/events.jsonl`, SHA-256
  `983f483a3e5e62772cd303736a714d4283bb1f7ad928b5ca80c27de2352df048`.
- Separated candidate receipt:
  `../../state/receipts/edges-vs-triangles/20260815T024004645231Z-590ee7dd1b24.json`,
  SHA-256
  `485f1406afe7d288e01ed7881538450bae1570e64fad97b9f49615d4df34e9e5`.

This is exhaustive over integer allocation with all transitions retained and
exhaustive at the additive screen over transition masks.  The continuous
multi-scallop refinement is deliberately bounded, not a proof over every
branch-count vector for every mask.

## Reproduction

```bash
cd /Users/jacweath/EinsteinArena/campaign

../.venv/bin/python discrete/edges_vs_triangles/audit_corpus.py \
  --stamp REPRO_EDGES_AUDIT

../.venv/bin/python discrete/edges_vs_triangles/global_dp.py \
  --stamp REPRO_EDGES_GLOBAL_DP

../.venv/bin/python discrete/edges_vs_triangles/transition_topology.py \
  --global-summary \
    discrete/edges_vs_triangles/runs/20260815T023100Z/global_dp/summary.json \
  --stamp REPRO_EDGES_TRANSITIONS --top-per-size 8 \
  --random-per-size 4 --starts 3 --separated-exclusion 1e-6

./arena verify edges-vs-triangles \
  discrete/edges_vs_triangles/runs/20260815T023100Z/global_dp/candidate.json
```

Program SHA-256 values:

- `audit_corpus.py`:
  `c618478202ad52521d9ebeddc575090b4299b80cbd2a738e64eb13779aaec40a`;
- `global_dp.py`:
  `d3bfe05def39fe2e4402019cc6345a3c97636f38e3c3f18e5f05e7cf01839d02`;
- `transition_topology.py`:
  `db2c099dd2d42dea75457ed98437c6a0d8c08b085de4e162dde9f7f72ab7efa8`.

## Frontier

The retained-transition curve mesh is globally solved at the integer
allocation level, arbitrary off-curve weight families are pointwise dominated,
and the strongest coordinated transition-removal basins collapse back to a
kink or are worse.  The remaining rigorous route is a continuous
shortest-path/Monge certificate allowing every transition to be omitted while
optimizing branch counts jointly.  It would strengthen the bounded topology
screen into a theorem, but the observed scale is roughly three orders of
magnitude below the remaining leaderboard gate.  Further random weight noise,
single-coordinate polish, or ordinary one-row exchanges repeat closed work.

--------
REFERENCES

[1] Christian Reiher. “The Clique Density Theorem.” *Annals of Mathematics*
184(3), 683–707 (2016). doi:10.4007/annals.2016.184.3.1
https://paperclip.gxl.ai/citations/papers/arx_1212.2454#L3-L5,L11-L18,L29-L30,L32-L46

[2] Bogdan Georgiev, Javier Gómez-Serrano, Terence Tao, and Adam Zsolt Wagner.
“Mathematical exploration and discovery at scale.” arXiv (2025).
https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L597-L609
