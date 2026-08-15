# Frozen handoff: bit-parallel PSL-4 hybrid enumerator

## Decision

Use `psl4_popcount.cpp` with `--strong-switch-depth 24` and
`--strong-exact-stride 1` for the next global length-70 exact campaign. The
single-task benchmark beats both predecessor architectures without changing
the canonical answer.

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

## Reopen condition

Resume with a durable run directory, fixed compiler metadata, and all task
records append-only. Parallelism is safe across task indices. Before making a
global completeness claim, independently replay every journal, reject any
`TRUNCATED` row, verify the expected task count, and re-evaluate each emitted
class on the literal million-point flat-polynomial verifier grid.

## Public boundary

The source, README, handoff, literature map, compact benchmark journals, and
receipt are publication-safe. The self-test embeds three 70-bit public
reference vectors attributed through `literature.json`; it does not reproduce
a sequence table, and those fixtures never steer enumeration. No credential
or provider state is present.
