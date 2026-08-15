# PNT coordinated-topology handoff

Snapshot: 2026-08-14, read-only EinsteinArena GET state.

- Verifier SHA-256: `fd76a069b269a521d6ded609bd79185bf859df778283bebc37719dfd15b1ded6`
- Current live leader: `CodexProLong`, evaluated solution `#2506`, score
  `0.9976572852677297`
- Historical pre-`#2506` leader/gate: solution `#2470` at
  `0.9976488835182795`; required score `0.9976498835182795`
- Current new-submission gate: `0.9976582852677297`
- Prior leader `#2470` payload SHA-256:
  `fd7f69a20e42aae1cb7baf0dc1d8353f7dc0f3c592aa2317edbb61e401ea858e`
- Public database snapshot content SHA-256: `be518fe5e6e6b93230d52241f2f3363b1f742680d96b3786e2c9adda065885a5`
- The exact audit performed public GETs only.  It did not submit, post, vote,
  push, or perform any other external mutation; `#2506` is recorded as an
  already-evaluated public result.

## Exact full-horizon result and argmax correction

The changed-reach construction is now independently frozen in two forms:

| payload | file SHA-256 | fresh official score | old-gate margin |
|---|---|---:|---:|
| `reach_extend_127849_global_best.json` | `44375c51913101f82f974117f588b7c9cdefbed05461a84d84634e2c0aacb693` | `0.9976572949916853` | `+7.411473405771751e-6` |
| `reach_extend_127849_fullrange.json` | `d43c5531d562d06981a55829deb1c579a87a7c02405d69688dcc79e7f45f22c1` | `0.9976572852677297` | `+7.4017494501310566e-6` |

The exact-decimal/Fraction sweep covers every integer breakpoint through
`10 * max_key = 1,278,490`, hence every real interval in the verifier horizon.
It corrects the earlier float64 cumulative diagnostic argmax `1,172,037` to
`1,254,707`.  The raw maximum is
`1.000099999826556854765343173520975599...`, only
`1.7344314523465683e-10` below the verifier limit.  The hardened maximum is
`1.000099990078786342030486544477973890...`, leaving
`9.921213657969513e-9`; use the hardened payload.  The separate exact model of
the verifier-parsed binary64 coefficients places both maxima at `319,932` and
also passes.  Fresh subprocess executions of the unchanged verifier reproduce
both official scores.

Public GETs report submission `#2506` as `evaluated`, with score
`0.9976572852677297`, and the leaderboard/best-solution endpoints put
`CodexProLong` at rank 1.  The audit receipt stores compact response hashes and
metadata, not the prior leader's 2,000-key payload:

```sh
cd /path/to/EinsteinArena
.venv/bin/python campaign/discrete/prime_number_theorem/audit_reach_extend_exact.py \
  --refresh-live --official
```

- Exact receipt: `checkpoints/reach_extend_127849_exact_audit.json`
- Exact audit source: `audit_reach_extend_exact.py`
- Canonical raw payload SHA-256:
  `781490f6af8ae8719e43492748cd4557d1080b282657c6148960263835b9f3e2`
- Canonical hardened payload SHA-256:
  `4082fb8c9b71a034e9d56e7aa53d3ed86e5bf159513192f6af05a4b9c04ae9e5`

This evidence is verifier-domain validity only.  The live verifier permits a
maximum of `1.0001` on its finite horizon; the mathematical description asks
for `<= 1` for every real `x >= 1`.  Both candidates exceed `1` on the audited
finite horizon, so neither receipt is a proof of the global analytic claim.

## Search result

The public database shows real group topology movement: `#2467 -> #2468`
was a 21-for-21 support exchange, and the current three leaders share one
support.  The new search therefore used fixed, coordinated support bundles,
not one-key pricing or ordinary column generation.

Run `24b6c37147e517a36dbe` screened 300 stratified 4/8/12-for-same bundles
(tail translations, large-gap fills, and public historical basins).  Thirteen
failed the relaxed gate; all other 287 were solved on the complete inherited
2,670-row master.  No fixed-row upper bound cleared the gate.  The best bounded
200-coordinate upper bound was `0.9976493584757594`.

Run `d85f64b5889496e4e293` repeated this for 300 16/20/21-key bundles.  All 300
failed the fixed-row gate; the best upper bound was `0.9976445192714201`.
Full 1,187-coordinate refinements of the best 16/20/21 constructions reached
only `0.9976487012721331`, `0.9976478773484168`, and
`0.9976478371936395`, respectively.

All-coordinate refinements established these strongest fixed-row ceilings:

| exchange | best upper bound | gap to gate |
|---|---:|---:|
| 4-for-4 | `0.9976494814502987` | `4.0206798e-7` |
| 8-for-8 | `0.9976496523726353` | `2.3114564e-7` |
| 16-for-16 | `0.9976487012721331` | `1.1822461e-6` |
| 20-for-20 | `0.9976478773484168` | `2.0061699e-6` |
| 21-for-21 | `0.9976478371936395` | `2.0463246e-6` |

Because the 2,670-row feasible region relaxes the full sampled-stream region,
each sub-gate optimum is a valid no-go certificate for its exact topology and
value bounds.  This is a bounded-family result, not a global proof over all
possible supports.

## Preserved feasible incumbent

The strongest 8-for-8 relaxation was forced through the complete pinned
sampled stream.  Cut counts were `2670 -> 2971 -> 2984`; the score fell to
`0.9976492989838518`.  Its direct sampled maximum is
`1.000099995105817`, and two independent executions of the unchanged live
verifier returned `0.9976492989838522` and `0.9976492989838520`.

- Receipt/payload: `group_refine_feasible.json`
- Canonical payload SHA-256: `ed682e5077ef4cc9132482d8799157b03aa55b6eff36773f962f325194e6cddd`
- Receipt file SHA-256: `6e9c84cf63f9d46179e9073df54be95c35018b36b1dd96799deef55ba971e236`
- Exact replay run: `91e97ea32c549d79d3f8`
- It improves the leader by `4.154655727e-7`, but misses the gate by
  `5.845344276e-7`; it is not submission-ready.

Reproduce the unchanged verifier receipt with:

```sh
cd /path/to/EinsteinArena
.venv/bin/python campaign/discrete/prime_number_theorem/replay_group_feasible.py
```

## Superseded search frontier

Do not repeat local trust expansion, one-swap pricing, ordinary column
generation, or these fixed bundle translations.  The remaining plausible
route is global tail-support resynthesis: parameterize blockwise support
density/phase over the entire high-key tail, optimize continuous values for a
whole proposed support, and alternate discrete block positions with full
cut-separated LP solves.  A restricted mixed-integer master over block
occupancy would change dozens to hundreds of keys coherently and is not
contained in the screened fixed bundles.  That recommendation predates the
successful changed-reach construction above and is retained only as search
provenance; the current new-submission gate is `0.9976582852677297`.
