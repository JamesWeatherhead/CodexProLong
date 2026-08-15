# PNT coordinated-topology handoff

Snapshot: 2026-08-14, read-only EinsteinArena GET state.

- Verifier SHA-256: `fd76a069b269a521d6ded609bd79185bf859df778283bebc37719dfd15b1ded6`
- Live leader: solution `#2470`, score `0.9976488835182795`
- Required gate: `0.9976498835182795`
- Leader payload SHA-256: `fd7f69a20e42aae1cb7baf0dc1d8353f7dc0f3c592aa2317edbb61e401ea858e`
- Public database snapshot content SHA-256: `be518fe5e6e6b93230d52241f2f3363b1f742680d96b3786e2c9adda065885a5`
- No submit, post, vote, or other external mutation was performed.

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
cd /Users/jacweath/EinsteinArena
.venv/bin/python campaign/discrete/prime_number_theorem/replay_group_feasible.py
```

## Next genuinely different route

Do not repeat local trust expansion, one-swap pricing, ordinary column
generation, or these fixed bundle translations.  The remaining plausible
route is global tail-support resynthesis: parameterize blockwise support
density/phase over the entire high-key tail, optimize continuous values for a
whole proposed support, and alternate discrete block positions with full
cut-separated LP solves.  A restricted mixed-integer master over block
occupancy would change dozens to hundreds of keys coherently and is not
contained in the screened fixed bundles.  Use the exact feasible receipt above
only as a comparison point; the live gate remains `0.9976498835182795`.
