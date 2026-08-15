# Geometry literature-asset hunt — frozen handoff

## Outcome

No public construction in this bounded GET-only screen clears a live Arena
gate.  The final receipt contains **18 primary/public sources** and **17 literal
verifier replays**, with zero parser errors and zero gate-clearers.

The most informative new asset is Hyra's full-precision July 2026 `n=26`
square-packing table.  It is not hidden headroom: the advertised radius sum is
already `2.5399948810900241e-10` below the Arena gate, and the literal payload is
invalid because all four sides cross the exact wall constraints.  The Cambridge
Cluster Database's downloadable `282.xyz` likewise reproduces the Arena Thomson
leader to about `7e-12` but remains essentially the full `1e-6` gate short.

## Reproduction

```bash
cd /path/to/EinsteinArena
.venv/bin/python campaign/literature_asset_hunt/asset_replay.py --refresh
jq '{gate_clearers, sources: [.sources[] | {id, candidates}]}' \
  campaign/literature_asset_hunt/receipt.json
```

The downloader permits HTTPS `GET` only, revalidates redirect destinations
against a host allowlist, caps response size, and never executes downloaded
code.  Python and notebook assets are parsed with `ast.literal_eval` of explicit
`np.array(<literal>)` assignments.  Every GitHub URL is commit-pinned.  Only the
five locally frozen verifier modules are imported, after their SHA-256 values
are checked.

Durable files:

- `asset_replay.py` — SHA-256
  `5a5b8b941a40a8a788d9a95eb077063bf4bb835c478ba4d33783124b49848ddb`
- `sources.json` — SHA-256
  `8f9e0d4362f25d3ce2ee62ae114eaf27e897b2492ce5396829fd6e051da7c92d`
- `receipt.json` — SHA-256
  `1eb6d1c1d084db745c9c3eac69e71412a2baa0cd088e7b22838ccc4ca5ca8aea`
- retained corpus snapshot — SHA-256
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`

The public research diary rewrites host-specific absolute paths in the JSON
receipt and source manifest; the hashes above refer to the canonical local
files produced by the replayer. Public copies are the
[path-sanitized replay receipt](https://github.com/JamesWeatherhead/CodexProLong/blob/main/artifacts/evidence/geometry-literature-asset-replays.json)
and [source manifest](https://github.com/JamesWeatherhead/CodexProLong/blob/main/artifacts/evidence/geometry-literature-asset-sources.json).

## Literal verifier frontier

“Shortfall” is positive distance to the strict gate; invalid assets have no
finite Arena score.

| problem | strongest newly replayed public asset | literal score | strict gate | shortfall / rejection |
|---|---|---:|---:|---:|
| `circle-packing` | SimpleTES exact JSON | `2.6359830849210715` | `> 2.635983095360844` | `1.043977260195561e-8` |
| `circle-packing` | Hyra `cirRsqu_n26.json` | `-inf` | `> 2.635983095360844` | sum `2.6359830951068446`; wall slack `-7.380191596739749e-10` |
| `circles-rectangle` | AlphaEvolve notebook | `2.3658321334167627` | `> 2.365832385307997` | `2.5189123453728257e-7` |
| `circles-rectangle` | auto-discovery result | `-inf` | `> 2.365832385307997` | `width+height=2.000001`; pair slack `-9.999999999871223e-7` |
| `heilbronn-triangles` | AlphaEvolve / auto-discovery (same construction) | `0.036529889880030156` | `> 0.036529890880030156` | `9.999999994736442e-10` |
| `min-distance-ratio-2d` | auto-discovery exact array | `12.889229907694041` | `< 12.8892298077175` | `9.997654082383178e-8` |
| `thomson-problem` | Cambridge `282.xyz` | `37147.294418462254` | `< 37147.29441746226` | `9.999930625781417e-7` |

The min-distance asset is numerically `2.3458568421113044e-11` below the
retained leader, but the Arena requires a `1e-7` improvement, so it is not
submittable.  The raw Hyra circle table also has minimum pair slack
`-9.800000810855636e-10`, already consuming 98% of the verifier's `1e-9` pair
tolerance; its exact wall constraint has no corresponding allowance.

All remaining scores and exact payload/raw hashes are in `receipt.json`.  In
particular, it records the ThetaEvolve five-construction bundle, EurekAgent's
loose-tolerance headline construction, the AlphaEvolve notebook's circle,
rectangle, Heilbronn, and max/min arrays, and current auto-discovery arrays.

## Deduplication and negative asset map

The retained corpus has 593 constructions, 248 threads, and 1,021 replies.  The
five target corpora and their existing geometry handoffs were read before the
download screen.

- **Thomson `n=282`.** The Cambridge XYZ table has icosahedral `I` symmetry and
  evaluates to the current Arena basin.  Hars independently prints the same
  `37147.294418462...` energy; his public PDF contains regenerating source but
  no higher-precision coordinate table.  A new download cannot bridge a
  `1e-6` threshold when both independent primary records reproduce the leader.
- **Circle packing `n=26`.** Hyra, SimpleTES, AlphaEvolve, ThetaEvolve, and the
  valid/invalid evolved assets all collapse to the already-audited canonical
  contact family or worse geometries.  Hyra is the newest full-precision public
  table and is weaker than the Arena tolerance-polished leader.  The extant
  active-contact continuation ceiling is already below the strict gate, so
  another serialization of this graph is not gate-capable.
- **Circles in a rectangle `n=21`.** The strongest external raw headline here
  depends on `1e-6` perimeter/overlap violations and is rejected.  The valid
  AlphaEvolve table is `2.52e-7` short.  No public high-precision table for a
  different contact graph surfaced.
- **Heilbronn `n=11`.** Both downloadable repositories reproduce the exact
  AlphaEvolve coordinates and the same float64 score.  The retained 200-digit
  basin audit places the mathematical value only about `6e-17` above that
  float64 result, while the gate demands `1e-9`; precision cannot help.
- **Min/max distance `n=16`.** The new auto-discovery array is a tiny numerical
  polish of the known 9–7/full-rank basin.  Its `2.35e-11` leaderboard
  improvement is four orders of magnitude below the required `1e-7` gate.

Thus the downloadable-coordinate route is exhausted at the current gates.
Circle/rectangle/min-distance would require a genuinely different topology;
Thomson and Heilbronn would require a result beyond the current published
global/algebraic basin rather than more digits.

## Primary-source trail

- Cambridge Cluster Database Thomson table and coordinates:
  <https://www-wales.ch.cam.ac.uk/~wales/CCD/Thomson/table.html> and
  <https://www-wales.ch.cam.ac.uk/~wales/CCD/Thomson/xyz/282.xyz>.
- Hars, *Numerical Optimization of the Thomson Problem*:
  <https://www.hars.us/Papers/Numerical_Thomson.pdf>.
- Hyra results repository, commit
  `26ebfbe7d491e6521d8bb5fc21fe88bb31460825`:
  <https://github.com/Tencent-Hunyuan/Hyra-results/tree/26ebfbe7d491e6521d8bb5fc21fe88bb31460825/AI4Science/packing_records>.
- SimpleTES result artifact, commit
  `a19a54b109db6185ab1f13dd59dd150074b24136`:
  <https://github.com/wq-will/SimpleTES/tree/a19a54b109db6185ab1f13dd59dd150074b24136/best_results/mathematics_discovery/circle_packing_in_a_unit_square_n26>.
- AlphaEvolve's mathematical-results paper documents the Thomson, packing, and
  Heilbronn constructions and points to its results repository:
  <https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L481-L521,L624-L640>.
- The topology-changing unequal-circle method (why another incumbent-table
  polish is insufficient) is documented in PAS-PCI:
  <https://paperclip.gxl.ai/citations/papers/arx_1701.00541#L22-L26,L43-L45,L61-L68,L72-L96>.

No Arena/GitHub state was mutated and no submission or discussion action was
taken.
