# Heilbronn n=11 distant-contact homotopy

This lane tracks quadratic active-set homotopies from the rigid 17-triple,
six-boundary incumbent. It deliberately excludes the already reported top-58
low-area pool and replaces each incumbent active triangle, one label at a time,
with every remaining distant inactive triangle.

The bounded result is negative: 1,819 direct exchange paths plus
pseudo-arclength recovery of all 648 direct failures produced no domain-valid
gate-clearer. The direct pass reached 1,171 endpoint roots and polished 72
distinct in-domain endpoints; the singularity pass reached 29 more endpoints,
all outside the triangle. See `HANDOFF.md` and `receipt.json` for exact scope.

In barycentric `(b,c)` coordinates, normalized triangle area is exactly an
absolute 2-by-2 determinant. The search therefore uses a clean-room polynomial
formula and never imports or executes Arena verifier code.

The route is distinct from:

- q=143 and q=144--220 finite SAT/mesh cells;
- depth-one-to-three point surgery;
- the corrected depth-four-to-eleven FlowBoost death/rebirth packet;
- local active-system solves restricted to the top-58 low-area pool.

The full numerical run needs Python 3.11+, NumPy, SciPy, and an explicit seed.
From the canonical EinsteinArena checkout, the private campaign seed and
environment are available through these commands:

```bash
../../../.venv/bin/python contact_homotopy.py \
  --workers 2 --skip-low-pool 58 --stamp REPRO
../../../.venv/bin/python replay.py runs/REPRO
```

The first command writes only under `runs/`. The second independently
recomputes the best payload's shape, domain slacks, pair separation, normalized
score, gate decision, task order, and frozen hashes.

From a public CodexProLong checkout, run the same search from the repository
root with the published frontier supplied explicitly:

```bash
python3.11 -m pip install -r \
  src/campaign/geometry/heilbronn_contact_homotopy_interval/requirements.txt
python3.11 \
  src/campaign/geometry/heilbronn_contact_homotopy_interval/contact_homotopy.py \
  --seed artifacts/frontier/heilbronn-triangles.json \
  --workers 2 --skip-low-pool 58 --stamp REPRO_PUBLIC
python3.11 \
  src/campaign/geometry/heilbronn_contact_homotopy_interval/replay.py \
  src/campaign/geometry/heilbronn_contact_homotopy_interval/runs/REPRO_PUBLIC
```

The coordinate-free public packet has a standard-library replay:

```bash
python3 -I \
  src/campaign/geometry/heilbronn_contact_homotopy_interval/public_replay.py
```

The public replay is standard-library-only and is the publication assurance;
the raw canonical run directories and private seed path are intentionally not
mirrored.

Canonical replay:

```bash
../../../.venv/bin/python replay.py \
  runs/20260815T111000Z-distant-exchange-v2
../../../.venv/bin/python replay.py \
  runs/20260815T111000Z-pseudo-v1
```

Manifest inspection is read-only by default (including `--help`); maintainers
must pass `--write` explicitly after reviewing changed allowlisted bytes.

```bash
python3 -I \
  src/campaign/geometry/heilbronn_contact_homotopy_interval/freeze_receipt.py
```

## Literature rationale

The incumbent was produced by search followed by projection into the bounding
triangle, and the AlphaEvolve report explicitly says further customized or
hybrid work may improve evolved results [1]. Recent global-optimization work
represents signed triangle areas with disjunctive quadratic constraints and
points toward stronger orientation-count restrictions for `n=11` [2]. Recent
certified homotopy work treats affine parameter homotopies with predictor/
corrector tracking and gives Krawczyk step-size conditions [3]. This lane uses
the shared polynomial structure but makes no claim of certified path
completeness: a failed real path may hide another component or require a
singularity-aware complex detour.

The 2026 unit-triangle certification paper reaches only `n <= 8`; the Exa asset
search found no new public `n=11` coordinate table beyond the already-audited
AlphaEvolve/LoongFlow construction. Exa request IDs:
`d959921f245b9830156a81d01c4d8c5a` and
`e244789be402a5eafc3165f4de96cf8d`.

## References

[1] B. Georgiev, J. Gómez-Serrano, T. Tao, and A. Z. Wagner. “Mathematical
exploration and discovery at scale.” *arXiv* (2025).
https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L59-L60,L624-L631

[2] A. Monji, A. Modir, and B. Kocuk. “Solving the Heilbronn Triangle Problem
using Global Optimization Methods.” *arXiv* (2025).
https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L233-L238

[3] K. Lee. “A priori bounds for certified Krawczyk homotopy tracking.”
*arXiv* (2025).
https://paperclip.gxl.ai/citations/papers/arx_2512.01355#L5-L10,L42-L49,L61-L69
