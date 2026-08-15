# Exact PSL-4 SAT/PB feasibility frontier

Status: **frozen as a fast hinted verifier/completer, rejected as the next
global enumeration engine**.

This clean-room lane encodes length-70 binary sequences with aperiodic peak
sidelobe at most four as exact Boolean cardinality constraints. It benchmarks
five CNF cardinality encodings with CaDiCaL, MiniCard native cardinalities,
OR-Tools CP-SAT, reversal lex symmetry, full eight-element symmetry-class
blocking, and deterministic outside-in cubes.

## Exact reduction

Let `x_i` be a sequence bit and `y_(i,k) = x_i XOR x_(i+k)`. For lag `k`, set
`m = 70-k` and `S_k = sum_i y_(i,k)`. The aperiodic correlation is exactly

```text
C_k = m - 2 S_k.
```

Therefore `abs(C_k) <= 4` is equivalent to the two integer bounds

```text
ceil((m-4)/2) <= S_k <= floor((m+4)/2).
```

Each XOR uses four CNF clauses. The benchmark fixes negation/alternating-sign
symmetry with `x_0=x_1=0`, optionally adds `x <= reverse(x)` through a prefix
automaton, and blocks all eight reversal/negation/alternation transforms of
every accepted class. Every returned model is independently rechecked with
literal integer autocorrelations.

## Decisive result

The encoding is excellent when a valid phase/hint is already known:

| Backend | Formula | First hinted fixture | Three blocked hinted classes |
|---|---:|---:|---:|
| CaDiCaL + sequential counter | 57,995 vars / 120,246 clauses | 0.0517 s | 0.0864 s |
| CaDiCaL + totalizer | 28,709 / 145,426 | 0.0587 s | 0.1867 s |
| CaDiCaL + modulo totalizer | 21,595 / 69,330 | 0.0381 s | 1.0649 s |
| CaDiCaL + k-modulo totalizer | 20,223 / 61,936 | 0.0329 s | 0.8312 s |
| **MiniCard native** | **2,485 vars / 9,662 CNF / 130 native bounds** | **0.000226 s** | **0.000756 s** |
| CP-SAT | 2,485 vars / 2,625 constraints | 0.0181 s | 0.0504 s |

All three phase-guided outputs exactly equal three public canonical PSL-4
fixtures, remain distinct after full symmetry-class blocks, and have exact
PSL four. Forced-witness solves also pass for every backend and symmetry mode.

The global-search signal is negative:

- Every CaDiCaL encoding and MiniCard timed out under the external five-second
  cold cap, both before any model and after blocking the three fixture classes.
- CP-SAT returned `UNKNOWN` at its deterministic three-second limit in both
  cold and post-class-block stages.
- Adding the reversal lex leader did not resolve any cold or post-block case.

These timeouts are not UNSAT proofs. They show that exact phase injection is
doing the work; this packet does not establish an autonomous route to all 72
reported classes.

## Cube-and-conquer check

A deterministic depth-28 sample fixes 56 outside bits and leaves 14 middle
bits. It contains three fixture cubes plus 253 seeded valid outside-in paths.
All 256 cubes were resolved exactly by the C++ DFS, MiniCard, and CaDiCaL with
identical status: three SAT and 253 UNSAT.

| Engine | Total time | Solve-only time | Relative to C++ |
|---|---:|---:|---:|
| Exact C++ newly-fixed-sidelobe DFS | 0.001375 s | 0.001375 s | 1.0x |
| MiniCard native incremental | 0.108046 s | 0.063984 s | 78.6x total / 46.5x solve-only slower |
| CaDiCaL sequential incremental | 0.995885 s | 0.910260 s | 724x total / 662x solve-only slower |

The C++ comparator is the simpler raw outside-in branch engine, not the
stronger active-lag accelerator. Losing even to that conservative baseline
rules out this tested cube regime as an order-of-magnitude replacement.

## Reproduce

```sh
.venv/bin/python campaign/analytic/flat_psl4_sat_pb/test_packet.py
.venv/bin/python campaign/analytic/flat_psl4_sat_pb/sat_pb_benchmark.py \
  --hard-time-limit 3 --run-id NEW_RUN_ID
.venv/bin/python campaign/analytic/flat_psl4_sat_pb/cube_benchmark.py \
  --cube-count 256 --depth 28 --conflict-budget 5000 --run-id NEW_CUBE_RUN
```

Pinned Python dependencies are in `requirements.txt`. The frozen decisive
receipts are `runs/20260815T085500Z/benchmark.json` and
`runs/20260815T084700Z/cube_benchmark.json`.

## Scope and next use

MiniCard is worthwhile as an exact candidate completer when another method
supplies a near-complete phase assignment, and as a sub-millisecond verifier
for known classes. It should not replace the 1.461x active-lag C++ engine for
global enumeration based on this evidence. A reopen requires a genuinely new
decomposition that makes cold/post-block solves fast on unseen cubes—not more
cardinality-encoding swaps or longer timeouts.
