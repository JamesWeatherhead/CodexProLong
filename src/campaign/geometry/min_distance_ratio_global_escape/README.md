# Min-distance ratio: adjacent-cardinality topology escape

## Result

This is a **bounded negative frontier**, not a global proof and not a candidate
for submission.  The frozen `min-distance-ratio-2d` verifier replays the best
payload at `12.889229907694041`.  The strict gate is
`< 12.889229807717522`, leaving a shortfall of
`9.997651950754971e-8`.

The screen deliberately did not refine the known 22-minimum/8-diameter active
root.  It reconstructed public adjacent-cardinality contact graphs and changed
the configuration topology before releasing it:

- every one-point deletion from the recovered `n=17` construction (`17`);
- every two-point deletion from the recovered `n=18` construction (`153`);
- `32` deterministic one-point births from the recovered `n=15` construction;
- `12` deterministic two-point births from the recovered `n=14` construction.

All `214` endpoints were evaluated by the unchanged verifier.  They yielded
`155` ranked minimum/maximum-contact signatures, `153` of which were absent
from the retained Arena corpus.  The best corpus-novel endpoint is the `n=18`
deletion `[2, 8]`, scoring `12.894999598753586`.  The overall best endpoint
merely returns to the already-known basin.

## Asset and corpus audit

The retained corpus contains `16` solutions, `29` threads, and `167` replies;
all solution scores replay with zero stored-score delta.  A GET-only live check
on `2026-08-15T05:55:20Z` matched the retained corpus.  No Arena, discussion,
issue, or GitHub mutation was made.

The public `n=16` Friedman diagram does not provide a distinct escape: its
22-edge minimum-contact graph is isomorphic to the current Arena leader's
22-edge graph.  The diagram assets for `n=14..18` state no upstream reuse
license, so this packet does not redistribute the GIF bytes.  `assets.json`
contains only factual pixel-center and colored-edge incidence measurements.

Primary grounding:

- [Paperclip lines 636–640](https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L636-L640)
  for the formal max/min-distance objective, prior numerical history, and the
  reported `n=16` AlphaEvolve result;
- [Berthold et al., arXiv:2601.05943](https://arxiv.org/abs/2601.05943);
- [Friedman's max/min-distance compendium](https://erich-friedman.github.io/packing/maxmin/);
- [Bateman–Erdős (1951)](https://www.renyi.hu/~p_erdos/1951-03.pdf).

## Verify

From the repository root:

```bash
.venv/bin/python campaign/geometry/min_distance_ratio_global_escape/replay_receipt.py
.venv/bin/python campaign/geometry/min_distance_ratio_global_escape/freeze_receipt.py
```

The first command checks every pinned byte, audits the append-only event log,
and invokes the frozen verifier in a fresh isolated Python process.  The second
command only creates `receipt.json` if it does not exist; on later runs it
requires an exact reproducible match and never overwrites the receipt.

The authoritative run is `runs/FINAL_V2/`.  `runs/FINAL_V1/`,
`runs/SMOKE_DEATHS/`, and `__pycache__/` are diagnostics and should not be
published.
