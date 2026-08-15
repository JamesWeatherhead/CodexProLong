# Exact PSL-4 active-lag accelerator

Status: **frozen accelerator packet; one complete split-depth-12 task replayed,
the 730,810-task global enumeration remains open**.

This packet accelerates the exact length-70, PSL-at-most-4 enumerator in
`campaign/flat_psl4_global_exact/` without changing that frozen source. A
hash-pinned patch produces a generated engine whose search tree, counters, and
canonical answers are identical to the parent engine. On the complete fixed
task, wall time fell from 77.8516 seconds to 53.2857 seconds: a 1.461x speedup
and 31.55% less time.

## What changed

The parent strong kernel tests all 69 autocorrelation lags after a cheap bound.
Most of those exact tests cannot add information.

1. **Exact active-lag table.** Once the cheap bound passes, a lag without a
   fixed-endpoint gap has either a fully determined correlation or independent
   free edges. Its attainable progression must meet `[-4, 4]`; only
   gap-bearing lags can tighten that result. At length 70 such a gap needs at
   least two lag edges, so its lag is at most 34.
2. **Cheap active-lag table.** If `fixed_edges <= 4 + remaining_edges`, then
   `abs(fixed_correlation) <= fixed_edges` proves that the cheap test cannot
   fail. Fully determined outer lags were already checked by the outside-in
   `Extend` step. Both classes are omitted.
3. **Fail-first exact order.** The remaining conjunction is evaluated in a
   deterministic order learned from failing-lag masks on a 1,000,000-node
   profile. Reordering a conjunction changes runtime, not its truth value.
   Startup validation proves that every gap-bearing lag appears in the table.
4. **Moment-safe fallback.** If optional moment constraints are enabled, the
   generated engine falls back to the original all-lag kernel because those
   constraints aggregate every lag range.

These are clean-room scheduling and redundancy eliminations. The mathematical
search, outside-in topology, PSL-preserving symmetry quotient, grouped path
bound, task universe, journal format, and dispatcher remain unchanged.

## Exact paired benchmark

Apple M4 Max, Apple clang 21.0.0, C++20 `-O3 -DNDEBUG -march=native`, one
thread, fixed task 351916, strong switch depth 24, exact stride 1:

| Run | Frozen base | Accelerator | Speedup |
|---|---:|---:|---:|
| 5M-node cap, repetition 1 | 4.79568 s | 3.18264 s | 1.507x |
| 5M-node cap, repetition 2 | 4.75038 s | 3.18816 s | 1.490x |
| 5M-node cap, repetition 3 | 4.81994 s | 3.18279 s | 1.514x |
| **complete fixed task** | **77.8516 s** | **53.2857 s** | **1.461x** |

For the complete replay both engines recorded exactly:

- 82,824,482 nodes;
- 101 leaves;
- 66,160,332 cheap strong prunes;
- 182,221,485 exact checks;
- 100,048,090 exact prunes; and
- one identical canonical class,
  `0000011100001011111111110101001010111100110011001101010110010110010110`.

The standalone literal formula mirror of the hash-pinned flat-polynomials
verifier scores that class `1.309817443680567`; it is valid PSL-4 but does not
clear the live gate. This
packet is an enumeration accelerator, not a new Arena construction or a claim
that all global tasks are complete.

## Rebuild and verify

```sh
python3 campaign/analytic/flat_psl4_accelerator/build_accelerator.py \
  --output /tmp/psl4_accelerated.cpp
clang++ -std=c++20 -O3 -DNDEBUG -march=native \
  -Wall -Wextra -Wpedantic /tmp/psl4_accelerated.cpp \
  -o /tmp/psl4_accelerated
/tmp/psl4_accelerated --self-test
python3 campaign/analytic/flat_psl4_accelerator/test_packet.py
```

The extended self-test differentially checks the old and active exact kernels
on 20,000 random partial assignments, the old and active cheap kernels on
20,000 valid outside-in paths, and all three public PSL-4 fixtures. The packet
test additionally rebuilds from the pinned base, compiles both engines, runs a
fresh 100,000-node differential, checks the frozen paired receipt, and replays
the canonical class with the standalone clean-room scoring formula. No
canonical-state verifier file is imported or required.

`benchmark_accelerator.py` creates a new run directory and refuses to overwrite
an existing checkpoint. The frozen benchmark and verifier receipts are under
`runs/20260815T080000Z/`.

## Literature and provenance

Paperclip lines 8–34 of Leukhin and Potekhin's arXiv:1212.4930 ground the
aperiodic autocorrelation definition, outside-in branch-and-bound, symmetry
reductions, XOR/popcount evaluation, and parallel exact-search context. The
primary Coxson–Russo paper is DOI 10.1109/TAES.2005.1413763. The prior Exa
result is retained only as a cheap/strong-bound scheduling analogy. Exact line
pins and scope limits are in `literature.json`; no third-party source or array
is vendored here.

## Scope

The fixed task is an architecture benchmark, not evidence that every task has
the same speed ratio. A global completeness claim still requires append-only
`COMPLETE` records for all 730,810 tasks, exact task coverage, canonical-class
deduplication, and unchanged-verifier replay of every emitted class.
