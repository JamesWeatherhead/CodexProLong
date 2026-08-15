# Geometry asset topology-recombination handoff

## Outcome

No strict Arena gate was cleared.  All three applicable lanes exceeded the
requested search scale with **550 distinct canonical ranked-contact graphs per
lane**, then replayed their strongest polished payload through the literal,
SHA-pinned verifier.

| lane | exact best | movement vs retained leader | strict gate | gate shortfall |
|---|---:|---:|---:|---:|
| `circle-packing` | `2.6359830952816243` | `+2.078026639651398e-11` | `> 2.635983095360844` | `7.921974187752312e-11` |
| `circles-rectangle` | `2.365832385227916` | `+1.991873332940486e-11` | `> 2.365832385307997` | `8.008127494463224e-11` |
| `min-distance-ratio-2d` | `12.889229907694041` | `-2.345856842111971e-11` | `< 12.8892298077175` | `9.997654082383178e-8` |

The first two scores independently recover the known tolerance-dependent
contact-system ceilings.  The min-distance score recovers the public
auto-discovery micro-polish.  None has sufficient margin to submit.

## What was genuinely different

`recombine_search.py` consumes the full retained construction corpus, the
commit-pinned literature-asset receipt, and prior changed-topology endpoints.
It never performs a pointwise coordinate average.  Every proposal uses:

1. a whole connected contact-neighborhood transplant after only a rigid
   dihedral/similarity placement, or a low-contact geometric cut splice;
2. a simultaneous two-to-five-contact release plus cross-module contact
   promotion;
3. for the rectangle, a host, donor, geometric-mean, or perturbed aspect-ratio
   crossover;
4. exact fixed-center radii LP repair for the two packing lanes;
5. free-center/free-aspect active-set SLP, rigid-root recovery, verifier-
   tolerance buffering, and literal replay; or, for min-distance, an anchored
   epigraph SLP with a forced multi-contact stage followed by a free stage.

Packing graphs are canonicalized with an unlabeled Weisfeiler--Lehman hash of
circle vertices plus a four-node frame, typed frame/contact edges, and the
ranked pair/wall contact basis.  Min-distance graphs use typed minimum- and
maximum-distance edges.  A second threshold graph is recorded separately, so
the 550-count cannot be confused with the smaller number of converged rigid
basins.

## Coverage and negative frontier

| lane | sources | attempts | ranked graphs | threshold graphs | polished | polished/rigid graph classes |
|---|---:|---:|---:|---:|---:|---:|
| square circles | 133 | 572 | 550 | 550 | 100 | 53 threshold / 80 rigid |
| rectangle circles | 51 | 1,101 | 550 | 550 | 99 | 68 threshold / 93 rigid |
| min-distance | 18 | 584 | 550 | 31 pre-polish | 140 | 52 exact polished |

Generated operator counts were 371 module/179 cut splices for square circles,
377/173 for rectangle circles, and 369/181 for min-distance.

- Square packing reached two roundoff/neutral representations of the known
  ceiling.  The next non-neutral polished graph scored
  `2.635977405118414`, already `5.690242430134163e-6` short of the gate.
- Rectangle recombination improved the best noncanonical endpoint in this
  bounded screen to `2.364248211083011`, but that remains
  `0.001584174224986246` short.
- The next min-distance polished graph class scored `12.890516727902753`,
  `0.001286920185252782` above the target.

This is strong bounded evidence that graph module crossover and simultaneous
multi-contact release do not bridge the tolerance gates from the recovered
asset/corpus library.  It is not a proof over all unlabeled contact graphs.

## Frozen replay

```bash
cd /path/to/EinsteinArena
.venv/bin/python campaign/geometry_asset_recombine/replay_frozen.py
jq '{any_gate_clearer, results: [.results[] | {slug,score,target,gate_margin,payload_sha256,verifier_sha256}]}' \
  campaign/geometry_asset_recombine/replay_receipt.json
```

The independent replay receipt is
`replay_receipt.json`, SHA-256
`10e4b33d1f664f182f36ae92cc01a1cd9a7e21ac5a5fd45b3db589e06dac4918`.
It reports `any_gate_clearer: false`.

| lane | payload SHA-256 | verifier SHA-256 |
|---|---|---|
| square circles | `78d84e1d58e0181eaad7254089a558d7c13a48040ef2bca4ae40251987183fab` | `2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab` |
| rectangle circles | `65441bcf1ca179ec6cd79b99893f076436e78fe6f3dac1397dc655fce371f591` | `c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9` |
| min-distance | `db3b205e9a4e4df7fcc073bba55e5969da4a6fa0dfa98229cc81c14cc61bc8df` | `2971cbb9e16752afe8d1d8067e6358d924b117ebeac0db41434ab19bfc8436ad` |

Search artifacts:

| lane | summary SHA-256 | seed catalog SHA-256 | event log SHA-256 |
|---|---|---|---|
| square circles | `265a244800f81823d69209b9e442f8ea807d9ca109a7ba69907afd60020d70a0` | `7368ef2f27d1bc309ae857033be2304517d8faae46dc72caf5deca48e83f0e05` | `56296d4a28ce841ceee6d676a51b8e05bae3ffdb7d44ca1e5e4c240373aaf736` |
| rectangle circles | `85e20c5249ee2bed93017f7a58fc0cd8afc5529b6a161f65dae26941d1e06b89` | `ec727e70439c7e2f3ffe13f72156e0cd7a0ec487d19f7334c8bafe7332f7979c` | `252f39b9e7d881b3c613e536cd1ae0aab67a86ce30f4d22fff8c3d91be32f857` |
| min-distance | `5c48d4664e22c19b6e4c06d99d329987dcfb5d1bbb57d70f5ea81d7d1172b3c2` | `ddc8af835d9a1764044837e69cf1c68d882e9696b66abc2a02d556a6fa8ad6b7` | `d7f551c7251eed767a15f10888a10d7714ef4460c9e25463f21a8748548d23df` |

Authoritative run directories are:

- `runs/20260815T_RECOMB_CIRCLE/circle-packing/`
- `runs/20260815T_RECOMB_RECT_R2/circles-rectangle/`
- `runs/20260815T_RECOMB_MIN/min-distance-ratio-2d/`

`SMOKE_*` and the interrupted first rectangle run are diagnostic only; no
score or count above is taken from them.

## Reproduction of the searches

```bash
cd /path/to/EinsteinArena

.venv/bin/python campaign/geometry_asset_recombine/recombine_search.py \
  circle-packing --target-signatures 550 --attempt-limit 30000 \
  --polish-count 100 --slp-rounds 12 --time-limit-seconds 850 \
  --rng-seed 2026081511 --stamp REPRO_RECOMB_CIRCLE

.venv/bin/python campaign/geometry_asset_recombine/recombine_search.py \
  circles-rectangle --target-signatures 550 --attempt-limit 40000 \
  --polish-count 100 --slp-rounds 12 --time-limit-seconds 850 \
  --rng-seed 2026081512 --stamp REPRO_RECOMB_RECT

.venv/bin/python campaign/geometry_asset_recombine/recombine_search.py \
  min-distance-ratio-2d --target-signatures 550 --attempt-limit 30000 \
  --polish-count 140 --min-maxiter 700 --time-limit-seconds 850 \
  --rng-seed 2026081513 --stamp REPRO_RECOMB_MIN
```

Program hashes:

- `recombine_search.py`:
  `bcac67308145c0d1017c480b40a9082d9c0dc179aff8aa2d5021ea007548d827`
- `replay_frozen.py`:
  `b3349229e567c74d471eb6ccfe539785837cb62659c7ee551fd6a7219e4bf2c9`
- imported circle fixed-center LP:
  `78a05a8067000b2586b86bc691455b2438df8288172aa0aaa9bcc676723728fc`
- imported circle active-set/refinement module:
  `5da21ca451206048a22f30f8ccd02b4c4ea8e9717dc554a940504c45029bf03c`
- imported rectangle LP/active-set module:
  `042757bf680bceb3d1f5bebcec53d9bc8e04042fe0afeda06d83ff3b3f87fbd6`

Environment: Python 3.12.13, NumPy 2.5.2, SciPy 1.18.0, NetworkX 3.6.1.
The retained corpus SHA-256 is
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`;
the literature-asset receipt used as input is SHA-256
`1eb6d1c1d084db745c9c3eac69e71412a2baa0cd088e7b22838ccc4ca5ca8aea`.

No Arena or GitHub write, post, vote, or submission was made.
