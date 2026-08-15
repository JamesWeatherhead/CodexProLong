# Thomson N=282: exact split-topology negative frontier

## Result

No gate-clearer was found. The strongest frozen-verifier replay is
`37147.29441846225`, compared with the public leader
`37147.29441846226` and the strict gate `37147.29441746226`. The apparent
`1.4551915228366852e-11` decrease is float64 convergence dust in the incumbent
graph; it misses the required improvement by `9.999857866205275e-7`.
The leaderboard, 14-solution count, gate, and verifier hash were rechecked by
public GET at `2026-08-15T06:06:02Z` in
[`live_read_check.json`](live_read_check.json).

This was a topology search, not incumbent polishing:

- 49 pairwise WL-distinct, defect-free N=72 triangulation classes were frozen:
  one Cambridge source and 48 alternatives;
- every alternative is reached by up to four degree-preserving two-flip macro
  moves (at most eight individual flips), with exact replayable face sets;
- the literature-prescribed edge split inserts one normalized midpoint on each
  of the 210 N=72 edges, producing 282 vertices;
- 30 pairwise WL-distinct geometric N=282 initial triangulations survived the
  strict `(5^12,6^270)` filter;
- three tangent-coordinate L-BFGS releases per seed used 3,439 iterations and
  3,810 objective/gradient evaluations in total;
- all 30 final triangulations are exactly graph-isomorphic to the incumbent,
  independently checked with NetworkX VF2-style isomorphism rather than merely
  inferred from a shared hash.

The raw split energies ranged from `37159.37882086272` to
`37190.639833575275`. After release, all scores lay between
`37147.29441846225` and `37147.29441846229`. No distinct final topology
survived, so `best_distinct_final_topology` is intentionally `null`.

## Why this search

The complete frozen Arena corpus for this lane contains all 14 public
constructions, all four threads, and their replies. Its SHA-256 is
`4e7c1ccf2b31a03841791a796bdea8a21a0408778f593e7110de2a026bbdb0cd`.
Earlier local work had already tested 48 cap transports,
vacancy/interstitial moves, individual bond flips, public alternate basins, and
random topology-changing controls. The missing experiment was a systematic
family of *new triangulations with exactly twelve pentagons and no 5/7 defect
pairs*.

Primary literature gives a constructive route. Altschuler and Perez-Garrido
define the split operation as adding one point on every one of the `3N-6`
edges, yielding `4N-6` points, and identify `(72,282)` as a successful split
pair of apparent global minima [1]. Their table reports the N=282 `(h,k)=(4,2)`
energy as `37147.294418474`, already matching the live configuration to the
published precision [2]. Ono independently identifies N=282 as an icosahedral
vibrational magic number [3] and describes random-start BFGS plus Cambridge
Cluster Database coordinates as the numerical protocol [4]. Continuum defect
theory also predicts twelve positive fivefold disclinations as the minimal
topological content in this size regime [5].

Paperclip provided the line-pinned full text; Exa deep publication search was
used only to discover and cross-check the relevant primary-source surface. The
machine-readable source map is [`literature.json`](literature.json).

## Frozen evidence

Canonical run:

`runs/20260815T_THOMSON_SPLIT_V1/`

| Artifact | SHA-256 |
|---|---|
| `search.py` | `0afa1b045b7379b63aea9854268b72de3ee1df9a4485d5c6400d293c91dc2e13` |
| `replay.py` | `f598c16ca1b84a18da7b9fb8107569342b1b8fa80c5cf496bd0e84fe1dfcd35a` |
| `isomorphism_audit.py` | `c0a6213a2a064013eaf93ecfaeb233ef8c01f985bbc21478a0f073a5540b3de9` |
| `literature.json` | `c6180ac7a51427f42e84cd55212e0bd4ade587695af5f7bef6fde6e00559c3f3` |
| live public-GET check | `b23fe364d014714c5d1daf42d98d03954eedd6038a35a5188492b9b1d6c71663` |
| N=72 source bytes | `2e2cede090d3498e42c3b360f2aa6847bb3d813de9ff573aa6d654e1e4b3f883` |
| event log | `a6de412b54248d88a8613b88e7c8a48b19f4c72ed8d0eb5739eb74738cc4e2e1` |
| summary | `433dc3a15d958f4029f9d1152d4065bf4a29087c828ad1c5aa0b6fd411919cf3` |
| search receipt | `a10a926ff92f30a8166e50862a777226091a29f505de0469d8a176bb02df68a1` |
| independent replay | `9b6f7237e6c71ee91b7a60516256a0c2cc554ac87f1d4884b4c90d70b63a2398` |
| exact isomorphism audit | `a5c6be49706dbde39e0e179c3ad4c5ef46b6a87e26abd0ed71e0edb9f1bd7346` |
| best candidate | `fab938c8a6aecfbf19576935805010cf8abe32f09483dfba41548d458d6ad667` |
| frozen verifier | `4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af` |

The independent replay re-hashed 782,212 candidate bytes, replayed all 49
combinatorial paths from the frozen N=72 source, reconstructed all 30 initial
split geometries, and re-evaluated every final candidate with the frozen
verifier. The best candidate is finite, shape `(282,3)`, with input norms in
`[0.9999999999999999, 1.0000000000000002]`.

## Reproduce

From this directory, with the project virtual environment:

```bash
/Users/jacweath/EinsteinArena/.venv/bin/python search.py \
  --class-limit 49 \
  --macro-depth 4 \
  --trial-limit 72 \
  --relax-rounds 3 \
  --maxiter 700 \
  --stamp REPRO_THOMSON_SPLIT

/Users/jacweath/EinsteinArena/.venv/bin/python replay.py \
  runs/REPRO_THOMSON_SPLIT

/Users/jacweath/EinsteinArena/.venv/bin/python isomorphism_audit.py \
  runs/REPRO_THOMSON_SPLIT
```

The canonical audit environment was Python `3.12.13`, NumPy `2.5.2`, SciPy
`1.18.0`, and NetworkX `3.6.1`.

## Evidence boundary

This closes only the enumerated two-flip-connected N=72 defect-free classes,
their retained split realizations, and unconstrained Coulomb release under the
frozen float64 verifier. It is not a proof over every fullerene-dual
triangulation on 282 vertices or every basin of the continuous Thomson energy.
It is strong negative evidence for this specific, literature-grounded topology
family, not a claim that the global N=282 problem is mathematically solved.

No external write was made: no Arena submission, discussion post, issue, Git
commit, or push.

--------
REFERENCES

[1] E. L. Altschuler and A. Perez-Garrido. “Defect free global minima in Thomson's problem of charges on a sphere.” *Phys. Rev. E* 73, 036108 (2006). doi:10.1103/PhysRevE.73.036108
    https://paperclip.gxl.ai/citations/papers/arx_cond-mat0509501#L5-L16

[2] E. L. Altschuler and A. Perez-Garrido. “Defect free global minima in Thomson's problem of charges on a sphere.” *Phys. Rev. E* 73, 036108 (2006). doi:10.1103/PhysRevE.73.036108
    https://paperclip.gxl.ai/citations/papers/arx_cond-mat0509501#L25-L28

[3] S. Ono. “Magic numbers for vibrational frequency of charged particles on a sphere.” *Phys. Rev. B* 104, 094105 (2021). doi:10.1103/PhysRevB.104.094105
    https://paperclip.gxl.ai/citations/papers/arx_2107.06519#L4-L10

[4] S. Ono. “Magic numbers for vibrational frequency of charged particles on a sphere.” *Phys. Rev. B* 104, 094105 (2021). doi:10.1103/PhysRevB.104.094105
    https://paperclip.gxl.ai/citations/papers/arx_2107.06519#L44-L47

[5] M. Bowick, A. Cacciuto, D. R. Nelson, and A. Travesset. “Crystalline Order on a Sphere and the Generalized Thomson Problem.” *Phys. Rev. Lett.* 89, 185502 (2002). doi:10.1103/PhysRevLett.89.185502
    https://paperclip.gxl.ai/citations/papers/arx_cond-mat0206144#L8-L16
