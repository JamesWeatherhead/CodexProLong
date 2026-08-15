# Handoff: Heilbronn n=11 gamma-monodromy and exact Krawczyk probe

Status: frozen bounded no-candidate packet. No Arena command, live verifier,
submission, discussion, issue, GitHub action, or other external write was made.

## Outcome

The strict gate remains `> 0.036529890880030155`. This lane found no real,
intended-domain gate clearer.

The useful result is a working algebraic route plus a quantified go/no-go
boundary:

- six boundary equalities reduce the incumbent contact equations to 17 integer
  quadratics in 16 free barycentric coordinates and the common determinant
  `z`;
- the 619 exchange systems left beyond the earlier pseudo-arclength caps reduce
  to 334 exact orbits under the incumbent reflection;
- a 14.19-second RHS-monodromy probe discovered 12 distinct generic complex
  roots, so the method does move between sheets and is not merely replaying the
  known real branch;
- 24 gamma paths into the two lowest multihomogeneous-bound target systems
  produced ten distinct successful roots, all nonreal;
- exact rational interval arithmetic certifies the incumbent root uniquely in
  a radius-`1e-70` box and proves its `z` box is strictly below the gate.

This is not a complete root enumeration. The monodromy run stopped at its
12-root cap while still discovering new roots, and the target tracker is only a
small double-precision prototype.

## Non-duplication and corpus scope

The exhaustive retained corpus was parsed from the FTS5 database with SHA-256
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`:
17 construction records, four threads, and all 23 replies for
`heilbronn-triangles`. Every construction JSON was fully decoded and all point
arrays were inspected. The newest public record still reports 2,471,800
asymmetric/depth-1-to-3 starts without a leader beat.

The following local lanes were also read and are not repeated here:

- `heilbronn_flow_topology_global`: all 23 feasible outer-contact templates,
  6,624 depth-4/5/6/8/11 population members, and 398 independent replays; best
  distinct score `0.034498013012460894`;
- `heilbronn_bnb` and `heilbronn_q143_cegis`: complete q=25 closure, bounded q=30
  closure, and all recorded q=143 radius-8 one/two-label releases;
- `heilbronn_rational_mesh_global`: 77 denominator screens (`q=144..220`) and
  72 distinct exact finite domains;
- `heilbronn_contact_homotopy_interval`: all 1,819 distant one-for-one real
  paths, 1,200 reached target roots, 7,249 detected folds, and 619 paths left
  past explicit caps.

Unlike those searches, this packet perturbs all 17 equation right-hand sides
over the complex numbers, uses monodromy to move between isolated roots, then
specializes sheets into target contact systems.

## Exact system and symmetry reduction

The eliminated variables are

```text
c0 = c1 = b5 = b8 = 0,
c7 = 1-b7,
c10 = 1-b10.
```

The remaining variables are

```text
b0,b1,b2,c2,b3,c3,b4,c4,c5,b6,c6,b7,c8,b9,c9,b10,z.
```

Each equation is `sign(i,j,k)*det(i,j,k)-z=0` with integer coefficients.
At the solver-refined center in the portable derived fixture, the 17-by-17
Jacobian has numerical rank 17, smallest singular value
`0.037825878214982664`, and maximum double-precision equation residual
`3.469446951953614e-17`. These are fixture-center diagnostics; the historical
bounded probe started from the predecessor seed identified by detached hash.

The exact reflection has label involution

```text
(0 10)(1 7)(2 6)(4 9)(5 8)(3)
```

and barycentric spatial map `(a,b,c)->(c,b,a)`. It preserves the active system.
Quotienting the 619 unresolved outgoing/incoming pairs gives 334 orbits, with
two fixed pairs.

The natural point-group multihomogeneous Bezout bounds are:

```text
incumbent system             35,490
target min / median / max    14,364 / 31,913 / 53,915
all 619 target-bound sum     19,695,934
334 representative sum      10,649,655
```

These are rigorous degree/path upper bounds, not mixed volumes or actual root
counts. They show why an all-target total-degree run (131,072 paths per system)
or even a blind multihomogeneous run is the wrong first production step.

## Bounded complex probe

`F(x)=p` was used as the monodromy family. Its incidence variety is the graph
of the polynomial map `F`, hence irreducible; over a generic regular value its
monodromy action is therefore transitive. This is the standard setting in
which a single seed can populate a generic fiber [1].

Fixed seed `20260815115727` and RHS scale `0.025` gave:

```text
wall time                         14.191915957955644 s
generic base roots stored         12
monodromy loops attempted         13
maximum generic residual          5.482172335836425e-12
minimum generic-root separation   0.7058883192660059
incumbent specializations         12 / 12 successful
real incumbent specializations    1
intended-domain specializations   1 (the known incumbent)
```

The first two loops returned to the seed sheet. Each of loops 2 through 12
found a new generic root; the run stopped at the root cap with zero consecutive
fruitless loops. Thus stabilization was not reached.

The two target probes were the lowest-bound reflection orbits:

```text
out (1,2,3), in (5,8,10)   bound 14,364
out (1,2,3), in (0,5,8)    bound 14,586
```

Of 24 gamma paths, ten reached distinct roots with residual at most `1e-9`.
Their smallest maximum imaginary coordinate was `0.82353103221943`; none was
real, in-domain, or gate-clearing. Fourteen paths hit the bounded prototype's
step floor or a divergent endgame. This failure rate is why production should
use a mature adaptive-precision/endgame tracker rather than enlarge this local
prototype.

## Exact-rational Krawczyk certificate

The certificate stores a 110-significant-digit center and inverse-Jacobian
preconditioner as decimal rationals. Replay converts them to exact
`fractions.Fraction` values and performs every interval operation exactly.
For radius `1e-70`:

```text
exact preconditioner rank       17
maximum Krawczyk/radius ratio   4.5716567890385193e-41
strict Krawczyk inclusion       true
z upper bound                   0.0365298898800302164248471279...
z upper < strict gate           true
```

The Krawczyk inclusion proves a unique real root in the box [3]. Because every
active signed determinant equals `z` at that root, the exact comparison
`z_upper < gate` proves this isolated incumbent root cannot clear the live
gate. This strengthens the prior numerical 100-digit root, but it does not
exclude other roots of the same polynomial system.

## Production continuation decision

The next run should begin with one preprocessing fact, not more random loops:

1. Compute the affine mixed-volume/root count for the RHS-augmented incumbent
   supports. Coordinate-hyperplane solutions must be included; a torus-only
   BKK count is insufficient. Polyhedral homotopy tracks a mixed-volume-sized
   start set, while monodromy can often populate the same fiber with far fewer
   paths [1] [2].
2. Enumerate the generic RHS fiber with adaptive precision. Stop only at the
   proven count or a validated sparse/multiprojective trace test; ten fruitless
   loops are only a heuristic [1] [2]. Official HomotopyContinuation.jl exposes
   both `monodromy_solve` and a trace-based completeness check [5].
3. Track the complete generic fiber once to each of the 334 reflection-orbit
   representatives, using gamma coefficient homotopies, endgames, and
   conjugate/reflection closure.
4. Filter every endpoint by reality, all 33 barycentric domain inequalities,
   pair separation, and all 165 absolute determinants. Produce an exact
   rational Krawczyk certificate for each surviving root before treating it as
   a construction.

The go/no-go threshold is the affine root count. If it is near the 35,490
multihomogeneous bound, 334 full parameter specializations are too expensive
for this host; prioritize target systems by low bound and pseudo-path fold
severity or pivot to interval branch-and-bound. If the count is in the low
hundreds, a complete parameter-homotopy pass is realistic.

The fallback is proof-producing barycentric MIQCP/interval branch-and-bound.
The published orientation-count idea is promising, but its source formulation
is for the unit square, not the equilateral domain here, so every count and
symmetry cut must be rederived before use [4].

## Portable replay and publication boundary

From a repository root in the campaign layout:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/public_replay.py

PYTHONDONTWRITEBYTECODE=1 python3 -B \
  campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/publication_selftest.py
```

For a public-source mirror, replace the leading `campaign/` with
`src/campaign/`. The copied-allowlist self-test exercises both layouts itself.

`public_replay.py` is read-only and standard-library-only. It verifies all
publication hashes, all 619 unique exchange/status records, the 334 symmetry
orbits, pairwise separation of the 12 generic roots, every stored residual and
geometric filter, all exact-rational Krawczyk inequalities, and the
zero-gate-clearer decision. It requires no private seed, raw path run, corpus,
verifier, network connection, NumPy, or mpmath.

The optional scientific audit uses dependencies from `requirements.txt`:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/audit.py --check

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/exact_krawczyk.py \
  --replay campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/incumbent_krawczyk.json
```

The bounded tracker is intentionally not presented as a byte-for-byte
reproducer: its elapsed time, floating linear algebra, and wall-clock cap are
environment-sensitive.

Publish exactly the list in `PUBLICATION_MANIFEST.json` plus that manifest
envelope. `PROVENANCE.md` records the detached private hashes, `NOASSERTION`
source-license boundary, excluded bytes, and dependency boundary. The manifest
omits its own hash by design; a detached SHA-256 anchors the frozen release.

--------
REFERENCES

[1] T. Duff, C. Hill, A. Jensen, K. Lee, A. Leykin, and J. Sommars. “Solving
polynomial systems via homotopy continuation and monodromy.” *arXiv* (2016).
    https://paperclip.gxl.ai/citations/papers/arx_1609.08722#L17-L25,L122-L128,L210-L214

[2] T. Brysiewicz and M. Burr. “Sparse trace tests.” *arXiv* (2022).
    https://paperclip.gxl.ai/citations/papers/arx_2201.04268#L5-L18,L32-L36

[3] K. Lee. “A priori bounds for certified Krawczyk homotopy tracking.”
*arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2512.01355#L28-L38,L52-L69

[4] A. Monji, A. Modir, and B. Kocuk. “Solving the Heilbronn Triangle Problem
using Global Optimization Methods.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L8-L13,L233-L238

[5] HomotopyContinuation.jl. “Solving parameterized systems with monodromy.”
Official documentation.
    https://www.juliahomotopycontinuation.org/HomotopyContinuation.jl/v1.1/monodromy/
