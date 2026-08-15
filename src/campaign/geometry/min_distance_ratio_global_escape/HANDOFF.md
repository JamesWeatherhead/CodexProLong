# Handoff: `min-distance-ratio-2d` global topology/asset escape

## Frozen conclusion

No safe gate-clearer was found.  This lane is frozen as a quantified bounded
negative frontier.

| quantity | value |
|---|---:|
| live/retained leader (minimize) | `12.889229907717521` |
| strict target | `< 12.889229807717522` |
| best unchanged-verifier replay | `12.889229907694041` |
| improvement over leader | `2.347988470319251e-11` |
| gate shortfall | `9.997651950754971e-8` |
| generated/replayed candidates | `214` |
| distinct ranked endpoint graphs | `155` |
| ranked endpoint graphs absent from corpus | `153` |
| best corpus-novel graph score | `12.894999598753586` |

The overall best payload is the already-known auto-discovery/canonical basin,
not a novel construction.  It must not be represented as a gate-clearer.

## Why this lane is non-overlapping

Prior work already established:

- the canonical 22-minimum/8-diameter graph, positive KKT system, full planar
  rigidity rank, and 100-digit active-root value in
  `campaign/geometry/min_distance_active_refine.py` and
  `campaign/geometry/HANDOFF.md`;
- all 70 weakest-contact quadruples at two gaps and release/promotion modes
  (`280` trials, `227` labeled topologies) in
  `campaign/geometry/min_distance_topology_search.py`;
- `584` asset/recombination attempts, `550` ranked graphs, and `140` polished
  endpoints in `campaign/geometry_asset_recombine/`.

This lane instead recovered the public `n=14,15,17,18` contact systems,
performed point birth/death to change cardinality and graph topology, preserved
the inherited unit contacts in an intermediate equality-constrained solve, and
then released the full graph.  The exact finite screen consists of all `17`
`n=17 -> n=16` deletions, all `153` `n=18 -> n=16` two-point deletions, `32`
deterministic `n=15 -> n=16` births, and `12` deterministic
`n=14 -> n=16` two-point births.

The best novel ranked graph is candidate `55`, the `n=18` deletion `[2,8]`:

- score: `12.894999598753586`;
- ranked signature:
  `cac2cd4ff02ed5fc5e87d2e97997c2902a7790f9a1f120736aa9241676272035`;
- threshold signature:
  `649f2a039186a5788f0bc99208f3af429909a8a612717de3a27e775fcf9b215d`.

This closes only the stated finite deterministic screen.  It does not prove a
global lower bound for the continuous `n=16` problem, exhaust arbitrary contact
graphs, or certify the absence of a different unpublished construction.

## Corpus and literature audit

The complete retained snapshot at
`campaign/research_corpus/snapshots/20260815T003306Z/corpus.sqlite3` has SHA-256
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.
This lane replayed all `16` public solutions and audited all `29` threads plus
`167` replies.  A GET-only revalidation at `2026-08-15T05:55:20Z` matched the
snapshot.  Exact response hashes are in `receipt.json`.

Paperclip primary-source lines
[`arx_2511.02864#L636-L640`](https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L636-L640)
ground the objective, numerical history, and reported `n=16` result.  Additional
primary/public sources are Berthold et al. (`arXiv:2601.05943`), Friedman's
max/min-distance compendium, and Bateman–Erdős (1951).  The Friedman page and
GIFs do not state a reuse license.  Their bytes are excluded; only factual
measurements are retained in `assets.json`.

The recovered scores are:

| cardinality | reconstructed score | maximum equality residual |
|---:|---:|---:|
| 14 | `10.994717905673031` | `3.552713678800501e-15` |
| 15 | `12.038438277928686` | `3.552713678800501e-15` |
| 17 | `14.090518704772544` | `3.552713678800501e-15` |
| 18 | `14.725276091685885` | contact-lock then epigraph release |

The published `n=16` diagram's 22-edge minimum graph is exactly isomorphic to
the leader's 22-edge graph; one explicit isomorphism is recorded in
`runs/FINAL_V2/summary.json`.

## Reproduction and immutable evidence

Run from the repository root:

```bash
.venv/bin/python -m py_compile \
  campaign/geometry/min_distance_ratio_global_escape/adjacent_topology_escape.py \
  campaign/geometry/min_distance_ratio_global_escape/replay_receipt.py \
  campaign/geometry/min_distance_ratio_global_escape/freeze_receipt.py
.venv/bin/python campaign/geometry/min_distance_ratio_global_escape/replay_receipt.py
.venv/bin/python campaign/geometry/min_distance_ratio_global_escape/freeze_receipt.py
```

The replay script verifies all frozen hashes, all event counts and candidate
indices, all summary invariants, all four recovered-asset scores, and the best
payload in a fresh isolated process using verifier SHA-256
`2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad`.
`receipt.json` is create-once: its generator refuses any mismatching existing
receipt rather than overwriting it.

`events.jsonl` is the append-only search journal.  Independent `FINAL_V1` and
`FINAL_V2` runs produced byte-identical journals, but only `FINAL_V2` is
authoritative.

## Publish-safe manifest

Include:

- `README.md`
- `HANDOFF.md`
- `adjacent_topology_escape.py`
- `assets.json`
- `freeze_receipt.py`
- `replay_receipt.py`
- `receipt.json`
- `runs/FINAL_V2/best.json`
- `runs/FINAL_V2/corpus_audit.json`
- `runs/FINAL_V2/events.jsonl`
- `runs/FINAL_V2/reconstructed_assets.json`
- `runs/FINAL_V2/summary.json`

Exclude:

- `__pycache__/`
- `runs/FINAL_V1/`
- `runs/SMOKE_DEATHS/`

No Arena submission, post, comment, issue, GitHub commit, or push was made.
