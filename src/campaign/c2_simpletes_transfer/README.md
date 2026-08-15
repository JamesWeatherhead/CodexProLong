# C2 SimpleTES support-topology transfer

This bounded lane tested whether the independently recovered SimpleTES
fine-comb topology could escape the frozen C2 incumbent's basin. It used
SimpleTES as a support geometry, not merely as a vector of amplitudes:

1. compare 2,048-bin normalized mass and material-support signatures;
2. align the source by scale, shift, and reflection;
3. resample its run geometry to the incumbent's 1,999,999-cell resolution;
4. test raw, thresholded, support-birth, block-local mass-preserving, signed,
   and exact integer-repeat crossovers; and
5. polish only candidates that improve under the unchanged frozen verifier.

## Result

The route is a quantified no-go for the current `1e-5` gate.

| Quantity | Exact result |
| --- | ---: |
| Starting checkpoint | `0.9635881172701123` |
| Best retained checkpoint | `0.9635881192968997` |
| Total gain | `2.026787404574293e-9` |
| Strict live gate | `0.963598110582029` |
| Remaining gap | `9.991285129351546e-6` |
| Gap / whole observed gain | `4929.616745595535` |

The best affine signature alignment was scale `0.97`, shift `0.03`, with no
reflection. Its mass correlation was `0.997227535985581` and its support
correlation was `0.9962358850529099`. That high alignment shows that the
apparently independent SimpleTES comb is not a distinct macro basin after
registration. Full transfers were strongly downhill: the best full affine
resample scored `0.9270728466237924`, the best full block-local transplant
scored `0.5699232199190288`, and the best full new-support component scored
`0.45753420218598767`.

Only tiny signed, blockwise reweightings improved the incumbent. A first fine
cycle gained `8.011969976351452e-10`; an identical continuation gained only
`5.6110893709160337e-11`, or `7.003%` as much. An exact sevenfold
sample-repeat plus padding preserved the source score near
`0.962693774995514`, but every tested crossover with the incumbent was
downhill. Across 2,184 exact verifier calls, there is no plausible trajectory
to the current gate.

## Exact replay

```sh
cd /path/to/EinsteinArena
.venv/bin/python campaign/c2_simpletes_transfer/replay_exact.py
```

The replay script imports the frozen verifier itself and pins both verifier
and checkpoint hashes. The retained payload has SHA-256
`b122a49ed64b07217948baa2119e28efe81e8179fd7f9e97da5e3717fea257bd`;
its contiguous float64 values have SHA-256
`8ad79d6fa04b566b852138709d959df928a7ec7cd36143d03a80901c1b485e34`.

`receipt.json` is the compact evidence index. The generated NumPy checkpoints
are intentionally ignored for publication; their hashes, exact scores, event
logs, and run-summary hashes remain recorded locally. SimpleTES provenance and
its GNU AGPL-3.0-or-later upstream license are pinned in the prior
`campaign/c2_asset_recovery/receipt.json`.

No Arena submission, post, vote, issue, or GitHub mutation was made.
