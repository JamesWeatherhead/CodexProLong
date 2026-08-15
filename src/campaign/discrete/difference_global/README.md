# Global Difference Bases topology audit

Status: bounded search complete; **no live gate-clearer**. This directory is a
local, GET-only research lane. Nothing here was submitted, posted, commented,
or pushed.

## Exact live frontier

The refreshed verifier SHA-256 is
`a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`.
Public solution 634 (AlphaEvolve) remains first with 360 points, consecutive
coverage 49,109, and exact score `129600/49109 = 2.639027469506608`.
With `minImprovement = 1e-9`, a 360-point candidate must cover at least
49,110. The live corpus contains 23 solutions, 11 threads, and 78 replies.

The pre-existing local campaign had already closed the incumbent's ordinary
neighborhoods:

- 360 deletions, 156,165 one-swaps, and 435 one-adds;
- every 64,620 two-removal pair, with 28,109,700 optimistic triples and
  264,569 forced placements;
- 236,326 globally bounded one-block replacements;
- 3,006,003 radius-500 two-block and 1,030,301 radius-50 three-block offset
  placements.

All retained results stayed at coverage 49,109. The public discussion corpus
also records negative affine Singer orbit, layer-stagger, nearby-prime,
q=97, CRT/product, Paley, Golomb, and bounded heterogeneous-block probes.

## New topology

The new route comes from Li and Yip's relative-difference-set construction,
located through Paperclip full text. For each odd prime `p`, it builds four
different quadratic graphs

```text
{(x, q*x^2 + c_h*x + d_h) : x in F_p}
```

applies a common invertible `GL(2,p)` coordinate map, encodes the two finite
field coordinates as a base-`p` integer, and places the supports at sparse
ruler heights `{0,1,4,6}` or `{0,2,5,6}`. This changes every block's support;
it is not a point swap, an offset repair, or four copies of the leader's
Singer block.

The modular construction is excellent, but exact integer carries are fatal.
The deterministic budget used primes 79, 83, 89, and 97; 300 random starts
per prime/height orthant; two elites per orthant; and a full 13-coordinate
finite-field descent for each elite. Every trial was evaluated by a literal
Python-integer difference bitset. The best raw prefix was:

| family | size | coverage | required | exact score |
|---|---:|---:|---:|---:|
| quadratic graph, p=97 | 388 | 2,405 | 57,046 | 150544/2405 |
| best normalized seed, p=79 | 316 | 2,351 | 37,839 | 99856/2351 |
| seed + 24-point sparse patch | 340 | 4,077 | 43,805 | 115600/4077 |

The patch beam is the paper's “repair the forbidden subgroup” idea translated
to integer carry space. At every depth it exhausts all births capable of
covering the current first gap, keeps eight exact states, and replays the
frontier through the pinned verifier. It evaluated 121,111 children. The
result quantifies a strong topology mismatch; it is not a proof against all
relative-difference-set embeddings.

## Reproduction

Run from the repository root with its Python 3.12 environment:

```bash
.venv/bin/python campaign/discrete/difference_global/test_exact.py -v
.venv/bin/python campaign/discrete/difference_global/refresh_public.py
.venv/bin/python campaign/discrete/difference_global/relative_graph_search.py \
  --primes 79,83,89,97 --random-starts 300 --elite 2 --sweeps 1 \
  --seed 2026081501
.venv/bin/python campaign/discrete/difference_global/sparse_patch_search.py \
  --beam 8 --max-additions 24
.venv/bin/python campaign/discrete/difference_global/freeze_receipt.py
```

`exact.py` independently computes the consecutive prefix and exact rational
score, then requires byte-pinned live-verifier agreement for every retained
frontier. `refresh_public.py` uses GET requests only and explicitly raises the
reply limit above the API's silent default of 20.

See [PROVENANCE.md](PROVENANCE.md) for Paperclip line pins, primary sources,
and upstream licenses. The full Arena snapshot has no asserted redistribution
license and is local evidence only; it is excluded from the publish-safe list
in [HANDOFF.md](HANDOFF.md).
