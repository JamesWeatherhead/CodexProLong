# Global length-70 PSL-4 exact search

Status: **exact hybrid enumerator and crash-safe distributed dispatcher frozen
at a benchmarked implementation frontier; the full 730,810-task search is not
complete**.

This clean-room C++20 solver combines two exact branch-and-bound regimes for
length-70 binary sequences with aperiodic peak sidelobe level at most four:

1. a Coxson--Russo outside-in tree whose newly fixed outer sidelobe is checked
   with XOR/popcount; and
2. a strong path-parity feasibility bound maintained incrementally after a
   configurable depth switch.

The strong bound groups all unresolved fixed-endpoint gaps of equal length. A
single 128-bit XOR and popcount then evaluates every endpoint product in a
group. At length 70 there are at most two gap-length groups per lag. This keeps
the exact path constraint while replacing hundreds of scalar endpoint tests
per node with roughly 50 grouped operations.

## Measured result

On the same seed-adjacent split-depth-12 task, the frozen depth-24 hybrid:

| Exact architecture | Nodes | Leaves | Seconds |
|---|---:|---:|---:|
| raw outside-in popcount | 11,899,530,408 | 6,501,699,893 | 82.2746 |
| prior strong enumerator | 82,687,840 | not recorded | 103.6990 |
| **bit-parallel hybrid, switch at depth 24** | **82,824,482** | **101** | **76.8479** |

The hybrid is 1.071x faster than raw popcount and 1.349x faster than the prior
strong enumerator on this task, while visiting 143.67x fewer nodes than raw
popcount. All three return the same canonical PSL-4 class. This is a
single-task architecture benchmark, not a claim that the full global search is
finished or that every task has the same speed ratio.

Machine-readable counters and exact commands are in `benchmarks.json`; the raw
one-line journals are under `runs/`.

## Workload profile and distributed execution

The global task tree is strongly heterogeneous. A deterministic SplitMix64
sample over eight virtual shards evaluated 825 tasks at a 100,000-node cap:
105 completed and 720 reached the cap. On one 101-task shard raised to 500,000
nodes, 15 completed and 86 still reached the cap. These are workload
measurements—not completeness records and not a statistical theorem about the
unseen tasks. Exact counters and journal hashes are in `scaling_profile.json`.

`psl4_popcount.cpp` now exposes `--task-shards` and `--task-shard` so a task is
assigned by `SplitMix64(task_index) % task_shards`. The hash makes many small
virtual shards substantially less sensitive to contiguous hard regions.
`psl4_dispatch.py` dynamically runs those virtual shards across local worker
processes and supplies the missing durability layer:

- an immutable source/binary/config hash at run start;
- one append-only solver journal and atomic receipt per virtual shard;
- safe restart that accepts only final `COMPLETE` rows;
- exact task-to-shard and task-count validation; and
- a final coverage receipt only after all 730,810 indices are present exactly
  once.

Example exact launch:

```sh
python3 campaign/flat_psl4_global_exact/psl4_dispatch.py \
  --binary /tmp/psl4_hybrid \
  --source campaign/flat_psl4_global_exact/psl4_popcount.cpp \
  --run-dir campaign/flat_psl4_global_exact/runs/global-v1 \
  --virtual-shards 4096 \
  --workers 15
```

The same command resumes after interruption. Node-limited profiling must use a
separate journal: `TRUNCATED` rows are intentionally rejected by the dispatcher
and can never satisfy an exact shard receipt.

## Correctness checks

`--self-test` compares the precomputed/grouped range with a deliberately slow
path decomposition for 20,000 random partial assignments across all 69 lags
(1.38 million range comparisons). It also checks both strong implementations
at every depth of all three recovered length-70 PSL-4 symmetry classes. Those
three short public reference vectors are embedded as attributed correctness
fixtures; they do not seed, prune, or otherwise steer the search.

Build and test:

```sh
clang++ -std=c++20 -O3 -Wall -Wextra -Wpedantic \
  campaign/flat_psl4_global_exact/psl4_popcount.cpp \
  -o /tmp/psl4_hybrid
/tmp/psl4_hybrid --self-test
python3 campaign/flat_psl4_global_exact/psl4_dispatch.py --self-test
```

The recommended exact regime is `--strong-switch-depth 24` with
`--strong-exact-stride 1`. Journals are append-only and completed tasks are
skipped on restart; the dispatcher additionally verifies global partition
coverage before emitting `COMPLETE.json`.

## Literature routing

Coxson and Russo introduced the outside-in exhaustive search, symmetry
reduction, bitwise sidelobe evaluation, and parallel partitioning used here.
The Paperclip-indexed Leukhin--Potekhin account supplies a line-pinned
description of the same search family. Exa then surfaced a structurally useful
QUBO branch-and-bound paper whose exact solver combines cheap and strong bounds
at a cutoff and caches parent state for incremental child updates. We borrowed
that operator pattern only; no QUBO theorem is asserted for PSL-4.

See `literature.json` for primary links, Paperclip lines, the Exa request ID,
and the explicit scope limit.

## Scope

The older `flat_psl4_enumerator/` packet exactly closed 72 seed-neighbour
subtrees. This solver targets the global task partition, but the global run is
still open. A complete claim requires all 730,810 split-depth-12 tasks to have
append-only `COMPLETE` records and an independently frozen union of canonical
classes.
