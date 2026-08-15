# Thomson `n = 282`: bounded C560 topology escape

Status: **frozen quantified no-go**. No submission candidate was produced.

The live score to beat was `37147.29441846226`; the platform required a score
at or below `37147.29441746226`. This lane tested seven graph-distinct C560
fullerene-dual outputs that were absent from the 30 retained N72-split WL
hashes. Each graph received four numerical spectral realizations and four
tangent L-BFGS releases.

| Result class | Exact verifier score | Gap above target | Topology after release |
| --- | ---: | ---: | --- |
| best of all 28 | `37148.1301703428` | `0.8357528805427137` | scarred `{5:16,6:262,7:4}` |
| best defect-free | `37148.14103932371` | `0.8466218614485115` | new separation-5 class |
| best source-retaining | `37148.250685079416` | `0.9562676171553903` | original separation-4 class |

All seven starting graphs have 282 dual vertices, 840 edges, degree histogram
`{5:12,6:270}`, and pentagon separation 4. Every numerical spectral start
reconstructed its intended labeled convex-hull edge set exactly. After energy
release, 20 of 28 trials retained the source graph and 24 of 28 remained
defect-free. No norm or distance clamp was active.

## Why this family

An icosahedral fullerene with Coxeter coordinates `(p,q)` has
`20(p²+pq+q²)` vertices and pentagon separation `p+q`; for even separation
`d`, the unique smallest example is `(d/2,d/2)` with `15d²` vertices.[1]
That makes the C540 `(3,3)` cage the exact smallest separation-6 control and
the C560 `(4,2)` cage another separation-6 control. The paper's published
enumeration only reaches 400 vertices and used buckygen plus a separate
separation filter.[1] This lane therefore tested a bounded seed-descendant
route; it did **not** enumerate every C560 fullerene.

## Reproduction boundary

The private exact replay is:

```bash
cd <EinsteinArena-checkout>
.venv/bin/python -B campaign/geometry/thomson_c560_distant_pentagon/replay_exact.py \
  campaign/geometry/thomson_c560_distant_pentagon/runs/20260815T105000Z-c540-descendants-v2
```

It requires the excluded graph inputs, candidate coordinates, frozen verifier
bytes, and prior topology summary. The public packet deliberately contains
authored code and a coordinate-free receipt, not those private or third-party
inputs. Public integrity checks are standalone:

```bash
python3 -B src/campaign/geometry/thomson_c560_distant_pentagon/test_packet.py
```

The WL hashes are metadata pinned to NetworkX `3.6.1`; all within-packet class
counts and source-return decisions use exact graph isomorphism instead.

## Scope

- This is seven private hash-identified C560 dual outputs, not a complete or
  canonical C560 enumeration.
- The best numerical endpoint is scarred and must not be described as a
  defect-free fullerene-dual result.
- No claim is made that pentagon separation predicts Thomson energy globally.
- The frozen verifier was hashed and mirrored clean-room; downloaded verifier
  code was never imported or executed on the host.

--------
REFERENCES
[1] Jan Goedgebeur and Brendan D. McKay. “Fullerenes with distant pentagons.” arXiv (2015).
    https://paperclip.gxl.ai/citations/papers/arx_1508.02878#L24-L26,L56-L59
