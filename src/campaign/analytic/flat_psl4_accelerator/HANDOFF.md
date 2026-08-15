# Frozen handoff: PSL-4 active-lag accelerator

## Decision

Use the generated accelerator for any continuation of the global length-70
PSL-4 enumeration. It is exact-search equivalent to the frozen parent engine
and completed the fixed hard task in 53.2857 seconds instead of 77.8516
seconds (1.461x). Do not modify `campaign/flat_psl4_global_exact/`; regenerate
from its SHA-pinned source with `build_accelerator.py`.

Do **not** claim a full enumeration or a new flat-polynomials construction.
Only task 351916 was completed in this packet. It returned the already-known
PSL-4 class with frozen-verifier score `1.309817443680567`, which misses the
current minimizing gate.

## Exact invariant

The accelerated and frozen complete-task records agree on the canonical
answer and every search counter:

- nodes: 82,824,482
- leaves: 101
- cheap prunes: 66,160,332
- exact checks: 182,221,485
- exact prunes: 100,048,090
- classes: 1

The paired full receipt is
`runs/20260815T080000Z/benchmark.json` (SHA-256
`a8ceffa47fbea1095919a1cd28561cff32d58c12ac1828670ef0b29156baf6d5`).
The exact PSL/clean-room verifier-formula replay is
`runs/20260815T080000Z/verifier_replay_cleanroom.json` (SHA-256
`cbac86d9ee4d5695e93f40168202bd2e5df69959f3e2eff4f0f9d61722fd274b`).
It retains the frozen verifier SHA as provenance metadata and has no canonical
state-tree dependency.

## Why the pruning remains exact

After the cheap range test, no-gap lags reduce to a fixed sum plus independent
free edges, whose step-two progression intersects `[-4,4]`; a nontrivial
strong restriction needs a fixed-endpoint gap. Cheap checks are omitted only
where `fixed_edge_count <= 4 + remaining`, making violation arithmetically
impossible, or where `Extend` already checked a fully determined outer lag.
All retained exact constraints are conjoined in a fail-first order, which does
not change the feasible set. Optional moment mode falls back to the parent
all-lag kernel.

## Resume recipe

```sh
python3 campaign/analytic/flat_psl4_accelerator/build_accelerator.py \
  --output /tmp/psl4_accelerated.cpp
clang++ -std=c++20 -O3 -DNDEBUG -march=native \
  -Wall -Wextra -Wpedantic /tmp/psl4_accelerated.cpp \
  -o /tmp/psl4_accelerated
python3 campaign/analytic/flat_psl4_accelerator/test_packet.py
```

After that, point the frozen dispatcher at the generated source and binary and
use a new durable global run directory. Preserve switch depth 24 and exact
stride 1 unless a new paired exact benchmark proves otherwise. Never mix a
node-limited journal into an exact global run.

## Literature

Paperclip `/papers/arx_1212.4930/content.lines` lines 8–34 describes the
length-scaling problem, exact outside-in branch-and-bound, PSL symmetry,
XOR/popcount evaluation, and parallel/CUDA implementations. Coxson–Russo DOI
10.1109/TAES.2005.1413763 is the primary outside-in source. The inherited Exa
request is recorded in `literature.json`; it is an algorithmic analogy only.

## Publication boundary

Publish only the allowlist in `PUBLICATION_MANIFEST.json`. In particular,
exclude `runs/smoke-20260815T0757Z/`, whose exploratory receipt contains a
host-temporary binary path. No credentials, downloaded verifier copy,
third-party arrays, Arena writes, GitHub writes, or generated binaries belong
in this packet.
