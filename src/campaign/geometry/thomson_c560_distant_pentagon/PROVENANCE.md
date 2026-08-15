# Provenance and rights

## Arena evidence

- Problem: `thomson-problem`, `n = 282`, minimize Coulomb energy.
- Live leader at freeze: `37147.29441846226`.
- Minimum improvement: `0.000001`.
- Target at or below: `37147.29441746226`.
- Frozen verifier SHA-256:
  `4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af`.
- Public-corpus audit: all 14 solutions, 4 threads, and 18 replies available
  in corpus snapshot SHA-256
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.

The verifier bytes were hashed but not imported, compiled, evaluated, or
executed on the host. `replay_exact.py` independently implements the documented
float64 row normalization, `1e-12` norm/distance clamps, and upper-triangle
reciprocal-distance sum.

## Literature routing

Paperclip full text establishes the precise Goldberg/Coxeter size and
pentagon-separation formulas and the unique even-`d` minimum.[1] It also states
that the reported enumeration reaches 400 vertices and was generated with
buckygen before a separate pentagon-separation filter.[1] Those facts justify
the topology family and, equally importantly, its explicit incompleteness at
C560.

Two Exa read-only searches were used for asset discovery; no response bodies
or credentials are retained:

| Request ID | Query | Outcome |
| --- | --- | --- |
| `192a855674e408bae177eb19607c7deb` | `C560 fullerene pentagon separation 6 enumeration coordinates graph database Thomson N=282` | primary fullerene papers; no downloadable complete C560 list |
| `1fe873b3e6c2e82548027962b62db0fb` | `"C560" fullerene isomer graph coordinates Goldberg (4,2)` | Goldberg/fullerene references; no alternative C560 coordinate asset |

## Generation controls

These dependencies and research artifacts remain private and are excluded from
the MIT publication packet:

- Antiprism 0.32 source archive SHA-256
  `3ea0a7482955feb1d9db31fdb92d1192a1c31918ff0e1a11cae98fc2f72ac837`;
  its `COPYING` SHA-256 is
  `0cf37aad9b533d054b16be63cfc1c60f4b8d89bd9c0ae27993dfcb8cacc16854`.
  It generated the exact `(3,3)` C540 and `(4,2)` C560 controls; the latter is
  exactly graph-isomorphic to the retained incumbent topology.
- Official buckygen 1.1 archive SHA-256
  `c151b33078913bed7f72977821d246c6dda5e01b64a53d963b5f95b65852e634`;
  guide SHA-256
  `fa0d202c67861e9da37e1fafcd71627823355507e4bc26501c76fce8b27a5d8e`.
  Buckygen is GPL-licensed. A disposable modified research build produced the
  seven private adjacency outputs; neither its source, binaries, nor output
  graph bytes enter the MIT packet.
- Modified private `buckygen.c` SHA-256
  `e8fb9e8b6535f45ed7e683075840ad9aeeef45f515902e49c5c370ff0791dd7a`.

The public result therefore describes the inputs only as seven private,
hash-identified C560 dual outputs. It does not assert a publicly reproducible
or canonical descendant lineage.

## Authored work

`search.py`, `replay_exact.py`, the documentation, receipt builder, and public
tests are original campaign code licensed under the packet MIT license. Private
candidate coordinates and graph inputs are omitted by default-deny policy.

--------
REFERENCES
[1] Jan Goedgebeur and Brendan D. McKay. “Fullerenes with distant pentagons.” arXiv (2015).
    https://paperclip.gxl.ai/citations/papers/arx_1508.02878#L24-L26,L56-L59
