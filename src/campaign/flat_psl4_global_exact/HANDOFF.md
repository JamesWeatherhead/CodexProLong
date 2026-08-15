# Frozen handoff: bit-parallel PSL-4 hybrid enumerator

## Decision

Use `psl4_popcount.cpp` with `--strong-switch-depth 24` and
`--strong-exact-stride 1`, launched through `psl4_dispatch.py`, for the next
global length-70 exact campaign. The single-task benchmark beats both
predecessor architectures without changing the canonical answer, and the
dispatcher makes the full run restartable and exactly auditable.

Do **not** claim a full enumeration. Only one seed-adjacent global task was used
for the architecture comparison; the task universe contains 730,810 entries.

## Exact benchmark

- raw popcount: 11,899,530,408 nodes, 82.2746 seconds
- bit-parallel hybrid: 82,824,482 nodes, 76.8479 seconds
- prior strong exact: 82,687,840 nodes, 103.6990 seconds
- canonical answer from every regime:
  `0000011100001011111111110101001010111100110011001101010110010110010110`
- hardware: Apple M4 Max, 16 logical CPUs, 48 GiB RAM
- compiler: Apple clang 21.0.0, `-std=c++20 -O3 -Wall -Wextra -Wpedantic`

The hybrid journal also records 66,160,332 cheap strong prunes, 182,221,485
exact checks, and 100,048,090 exact prunes. The 101 surviving complete leaves
contain one valid canonical class.

## Deterministic scaling profile

- task assignment: `SplitMix64(task_index) % 7308`
- 100k-node cap: 825 tasks, 105 complete, 720 truncated, 72,497,902 nodes
- 500k-node cap: 101 tasks, 15 complete, 86 truncated, 43,716,792 nodes
- dispatcher smoke: a one-task virtual shard completed, receipt-hashed, and
  resumed without re-execution

The exact raw rows and SHA-256s are frozen in `scaling_profile.json` and
`runs/profile-20260815T0714Z/`. Capped rows are profiling evidence only. The
dispatcher refuses to certify a shard if any final row is `TRUNCATED`.

## Global launch

```sh
python3 campaign/flat_psl4_global_exact/psl4_dispatch.py \
  --binary /tmp/psl4_hybrid \
  --source campaign/flat_psl4_global_exact/psl4_popcount.cpp \
  --run-dir campaign/flat_psl4_global_exact/runs/global-v1 \
  --virtual-shards 4096 --workers 15
```

Many more virtual shards than workers are intentional: the dynamic queue
absorbs the observed task-time skew while keeping every assignment stable
across machines and restarts. A full-range run emits `COMPLETE.json` only after
all 730,810 task indices pass membership, uniqueness, status, and count checks.

## Reopen condition

Resume the dispatcher against the same durable run directory and frozen
source/binary hashes. Parallelism is safe across task indices. Before making a
global completeness claim, independently replay the dispatcher coverage
receipt and every journal, reject any `TRUNCATED` row, verify all 730,810 task
indices exactly once, and re-evaluate each emitted class on the literal
million-point flat-polynomial verifier grid.

## Public boundary

The source, dispatcher, README, handoff, literature map, compact benchmark and
profile journals, and receipt are publication-safe. The self-test embeds three
70-bit public reference vectors attributed through `literature.json`; it does
not reproduce a sequence table, and those fixtures never steer enumeration.
No credential or provider state is present.
