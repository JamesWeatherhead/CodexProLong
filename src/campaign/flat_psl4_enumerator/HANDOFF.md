# Flat PSL-4 exact-neighborhood handoff

## Outcome

No gate-clearer.  The frozen live verifier hash is
`ff991bd84aec2b5b5d44f58a68dba00f961e01d517ec1de3225e0902f0f2fce2`;
the strict gate is `< 1.280726494964255`.

The exact task totals are:

| Seed | Tasks | DFS nodes | Classes | Best live score |
|---|---:|---:|---:|---:|
| Leukhin–Potekhin | 24 | 1,399,351,462 | 1 | `1.309817443680567` |
| Dimitrov et al. | 24 | 2,286,029,507 | 1 | `1.3687174157251323` |
| PslRK/Mertens | 24 | 653,455,999 | 1 | `1.370142837431983` |

`receipt.json` is generated directly from the task journals and is
authoritative for every counter and hash.

## Exact search commands

```bash
./psl4_exact --split-depth 12 --threads 6 --max-tasks 24 \
  --near-bits 1001011001011001010100110011001100001010110101000000000010111100011111 \
  --journal runs/near-leukhin-24.jsonl

./psl4_exact --split-depth 12 --threads 6 --max-tasks 24 \
  --near-bits 1010110101101010101110011001110110010111100111100110110110000000001111 \
  --journal runs/near-dimitrov-24.jsonl

./psl4_exact --split-depth 12 --threads 6 --max-tasks 24 \
  --near-bits 1000000101010100010010000011011011110011100011010010001100110111101001 \
  --journal runs/near-pslrk-24.jsonl
```

## Scope boundary

Each task fixes the outer 12 coefficients on each side and exhausts all 46
interior coefficients consistent with that boundary.  Tasks are selected after
the exact cheap/single-lag pruning used by the task generator, then stably
ordered by Hamming distance between their assigned border and the named seed.
Only the first 24 viable tasks per seed were executed.  Equal-distance tasks
beyond that cap may remain, so this must not be described as closing a complete
Hamming ball or all 678,165 viable tasks.

## Public packet

Include `psl4_exact.cpp`, `tests/test_exact_bound.py`, `freeze_receipt.py`,
`receipt.json`, this handoff, the README, and the three 24-line journals.
Exclude compiled binaries, CP-SAT experiments, solver logs, caches, and every
other run file.
