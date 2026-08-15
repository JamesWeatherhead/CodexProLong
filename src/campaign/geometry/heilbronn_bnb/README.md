# Heilbronn exact lattice branch-and-bound

This directory searches genuinely new 11-point combinatorial families for the
Heilbronn triangle problem.  It does not polish the public incumbent and does
not use verifier tolerances or domain bugs.

For a barycentric q-grid point `(a,b,c)` with `a+b+c=q`, the normalized
double-area of a triple is an integer determinant divided by `q^2`.  At the
frozen live gate

```text
leader = 0.036529889880030156
target = 0.036529890880030155
```

a q=25 construction must therefore have every determinant numerator at least
23, giving score at least `23/625 = 0.0368`.

## Main result

The q=25 family is exhaustively closed: no 11-point subset of the full
351-point barycentric grid reaches determinant numerator 23.

The certificate is
`runs/20260815T002500Z/heilbronn-triangles/q025_complete_certificate.json`
(SHA-256
`2cf96140b095b10b0c2a2c310090b9fe78d2c7a0511ce134acf393485022b9fe`).
It audits 51,494,145 DFS nodes, including repeated work in timed-out prefixes.

Coverage is exhaustive within the q=25 family:

- any set containing a corner is D3-equivalent to the fixed-corner search;
- without corners, each point belongs to at most one outer side;
- three points on a side have determinant zero, so a positive-threshold set
  has at most two points per side;
- modulo D3 side permutations, the ten patterns `(222)`, `(221)`, `(220)`,
  `(211)`, `(210)`, `(200)`, `(111)`, `(110)`, `(100)`, and `(000)` exhaust
  the remaining cases;
- the fully interior `(000)` case was split over all 37,950 possible first
  selected pairs.

This is a discrete-family theorem, not a proof about arbitrary continuous
coordinates.  It produced no payload, so there is no Docker verifier replay or
submission.  A future lattice attack should skip q=25 and change denominator
or construction family.

## Programs

- `hypergraph_dfs.py`: exact side-count families with resumable canonical side
  roots and D3/reflection reductions.
- `corner_dfs.py`: exhaustive fixed-corner family with resumable second-point
  roots.
- `interior_pair_dfs.py`: exhaustive fully interior family, partitioned by the
  first selected pair.
- `lattice_bnb.py`: determinant arithmetic, payload conversion, and an
  independent HiGHS forbidden-face MILP.
- `aggregate_*_segments.py`: hash and merge disjoint completed root intervals.
- `build_q25_certificate.py`: verify the corner certificate plus all ten
  non-corner orbit classes and write one atomic coverage certificate.
- `self_check.py`: check feasible/infeasible threshold transitions and compare
  the DFS with the independent HiGHS model on q=8.

Every bounded run has an append-only `events.jsonl`, per-q atomic JSON,
`checkpoint.json`, and `summary.json`.  Downloaded verifier text is only hashed;
none of these programs executes it.

## Reproduction

From this directory:

```bash
PYTHONPATH=. ../../../.venv/bin/python self_check.py \
  --output runs/REPRO_SELF_CHECK/heilbronn-triangles/self_check.json

PYTHONPATH=. ../../../.venv/bin/python hypergraph_dfs.py \
  --denominators 25 --side-counts 2,2,1 \
  --time-limit 120 --node-limit 100000000 --stamp REPRO_SC221

PYTHONPATH=. ../../../.venv/bin/python corner_dfs.py \
  --denominators 25 --start-root 1 --end-root 40 \
  --time-limit 120 --node-limit 100000000 --stamp REPRO_CORNER_PREFIX

PYTHONPATH=. ../../../.venv/bin/python interior_pair_dfs.py \
  --denominators 25 --start-root 0 --end-root 4750 \
  --time-limit 180 --node-limit 100000000 --stamp REPRO_INTERIOR_PREFIX
```

The exact source summaries and their SHA-256 hashes are embedded in the master
certificate.  Rebuild it with `build_q25_certificate.py`, passing the same ten
`--entry COUNTS:PATH` records and the corner aggregate listed there.

## q=30 bounded continuation

The q=30 campaign summary is
`runs/20260815T020000Z/heilbronn-triangles/q030_campaign_summary.json`
(SHA-256
`349ffb0ea5659120f06441a50f39c4f34929716c2cb147bebd122f88b695fe94`).
It completely closes five of ten non-corner side-count orbits and records
hashed partial intervals for all five remaining orbits.  See `HANDOFF.md` for
the exact coverage fractions and `ADAPTIVE_Q143.md` for the next mesh.
