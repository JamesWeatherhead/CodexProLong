# Flat-polynomials global changed-basin handoff

Frozen 2026-08-14. This lane performed no Arena posts, votes, or submissions.
There is no gate-clearing payload.

## Live target and exact receipts

- Verifier SHA-256: `ff991bd84aec2b5b5d44f58a68dba00f961e01d517ec1de3225e0902f0f2fce2`
- Literal verifier: 70 coefficients in `{-1,+1}`, `np.poly1d`, one million points from
  `np.linspace(0,2*pi,1_000_000)`, divided by `sqrt(71)`.
- Live leader #2475: `1.2807274949642549`.
- Strict improvement gate: `< 1.280726494964255` (leader minus `1e-6`).
- Current leader payload SHA-256:
  `4cfa023b9e86e1a77af92fe17942efd2d6a9cfc2210ebb57bd376cdcf2f974d0`.

Exact frozen replays are in `receipts/`:

| preset | exact score | payload SHA-256 |
| --- | ---: | --- |
| current | 1.2807274949642549 | `4cfa023b9e86e1a77af92fe17942efd2d6a9cfc2210ebb57bd376cdcf2f974d0` |
| old | 1.2809320527987995 | `f5abb3fdde99805a2787cd820f3c464a9f467b81069c6ec62c8188cd011bdb7a` |
| PSL-4 example | 1.309817443680567 | `4b734358439b30b556c0130eac1f11f8db082ae308435a40f88d3165cd3c340e` |

Reproduce:

```bash
cd /path/to/EinsteinArena/campaign/analytic/flat_global
python3 exact_replay.py --preset current
python3 exact_replay.py --preset old
python3 exact_replay.py --preset psl4-example
```

## Corpus and literature read before search

The complete retained Arena corpus was read from
`campaign/research_corpus/snapshots/20260815T003306Z/corpus.sqlite3`: all 24
flat-polynomial solutions, all 5 direct threads, all 19 direct replies, and relevant
cross-problem threads. The current `campaign/literature` packet was also read in full.

The construction choices were guided by:

- Balister et al., centered cosine/sine pair decomposition and Rudin-Shapiro recursion:
  <https://paperclip.gxl.ai/citations/papers/arx_1907.09464#L23,L32-L38,L79-L85>
- Klurman--Lamzouri--Munsch, Fekete/Legendre family and shifted process:
  <https://paperclip.gxl.ai/citations/papers/arx_2306.07156#L9-L12,L64-L74>
- Odlyzko, meet-in-the-middle ultraflat search and online-table statement:
  <https://www-users.cse.umn.edu/~odlyzko/doc/ultraflat.pdf>

The prior local frontier was not repeated: radii 1--6 (144,193,119 total exact
candidates) and 422,983 structured masks were already closed. The corpus also records
an exhaustive roughly 69-billion-member closure of the two direct skew-symmetric
degree-69/71 mappings, so Odlyzko's even-degree skew table is seed-only here.

## New bounded searches

### Centered four-state pair anneal

`pair_topology_anneal.cpp` represents all 35 centered pairs as cosine-plus/minus or
sine-plus/minus states. It seeded shifted Legendre/Fekete primes 67--257, Rudin-Shapiro
128 windows, current/old leaders, and mixed topologies; every chain began outside the
closed radius-six orbit.

- 145,513,585 proposals, 208,041 accepts, 11 dense validations.
- Best 65,536-grid score: `1.3753949499029809`, orbit distance 29.
- Atomic receipt: `pair_topology_checkpoint.json`.

Reproduce:

```bash
clang++ -O3 -std=c++20 pair_topology_anneal.cpp -o pair_topology_anneal
./pair_topology_anneal --seconds 60 --threads 16 --grid 1024 --seed 2026081502
```

### First unclosed Hamming shells (heuristic only)

`radius_frontier_anneal.cpp` sampled shells 7--14 with shell-preserving swaps. This is
not an exhaustive certificate.

- 258,147,679 proposals, 459,941 accepts, 4 dense validations.
- Best radius-9 65,536-grid score: `1.3660733025312393`.
- Atomic receipt: `radius_frontier_checkpoint.json`.

### Literature-derived centered discrepancy screens

`pair_partition_screen.cpp` enumerates every sign assignment of each cosine or sine
component for a fixed pair-type topology. It then exhaustively optimizes all sine signs
against the 512 globally lowest-sup cosine bases, excluding the already closed current
neighborhood.

Structural result for the incumbent's 16-cosine/19-sine topology:

- Its sine signing is globally minimum among all `2^19` sine signings.
- Its cosine signing ranks 20th among all `2^16` cosine signings on grid 1024.
- The only retained near-1.28 combinations are exact symmetry-orbit copies of the live
  leader (`1.2807274949642533` on independent exact replay); retained novel combinations
  were at least about 1.43 on the 65,536 grid.

The same conditional exhaustive screen was run for the old-leader and published PSL-4
topologies. Their known seeds were best (`1.280932...` and `1.309817...`); retained novel
constructions were above 1.41. Fifteen additional top shifted Fekete and Rudin-Shapiro
pair-type patterns were screened; their best retained dense score was `1.39654954`.

Reproduce representative screens:

```bash
clang++ -O3 -std=c++20 pair_partition_screen.cpp -o pair_partition_screen
./pair_partition_screen 256 512 1024 current 20
./pair_partition_screen 256 512 1024 old 20
./pair_partition_screen 256 512 1024 psl4 20
```

### Global length-7 block substitution/crossover

`block_global_screen.cpp` exhaustively evaluates `4^10 = 1,048,576` constructions per
family. Eight families (8,388,608 constructions) were screened:

- within-block reversal/sign for current, Rudin-Shapiro, and Fekete sources;
- current/old, current/PSL-4, and current/RS block source/sign choices;
- four-source current/old/PSL-4/Fekete and current/old/PSL-4/RS choices.

Only the known old and PSL-4 seeds occupied the useful top positions. The best genuinely
mixed retained construction was about `1.41322` on 65,536 points.

Reproduce all eight families:

```bash
clang++ -O3 -std=c++20 block_global_screen.cpp -o block_global_screen
./block_global_screen 512 16 50
```

## Archived PSL-4 family lead

Leukhin--Potekhin report exactly 72 non-equivalent length-70 PSL-4 sequences and 115 at
length 71. The printed highest-merit-factor length-70 example is
`01C2FFD4AF33356596` and exact-replays to `1.309817443680567`.

The former SignalsLab landing page was recovered from Common Crawl and Wayback, but the
`page_id=1779` PSL-4 attachment itself was not captured. Wayback CDX, Common Crawl
2013--2015, Arquivo.pt, GitHub code search, the historical server IP, and exact-title web
search were checked. Two exact SAT encodings are retained in `enumerate_psl4.py` and
`enumerate_psl4_native.py`; MiniCard immediately validates the published phase-seeded
witness but finding a second model stalls for minutes. The naive outside-in DFS is also
retained as `psl4_dfs.cpp`, but is not computationally competitive and is not a completed
enumeration.

If the 72/115 tables are recovered, exact-replay all 72 length-70 classes and every
single-deletion/cyclic truncation of the 115 length-71 classes. This remains the strongest
finite unexecuted lead.

## Interpretation and next search

No evidence supports spending more time on local bit flips, the incumbent fixed pair
topology, direct skew tables, or the tested block families. The next materially different
route is one of:

1. Recover and screen the historical complete PSL-4 tables.
2. Obtain Odlyzko's actual coefficient tables and replay any non-skew or otherwise new
   length-70 mapping (the already-closed direct skew mappings should not be repeated).
3. Implement Odlyzko's 32-witness meet-in-the-middle over a genuinely new unrestricted
   split, with rigorous derivative-based rejection, rather than another stochastic local
   basin search.

No payload in this directory is authorized for submission because none clears the strict
live gate.
