# Frozen handoff: exact PSL-4 Metal accelerator

## Status

Frozen, publication-safe candidate with a retained **two-stream isolated GPU
validation pilot**. Independent re-audit passed and a separate 8,192-shard
shadow run is active. It paused after each of its first two new classes,
independently replayed both on CPU and under the unchanged Arena verifier, then
resumed; its mutable `production_runs/` state is excluded from this packet and
is not a completion claim. Do not merge it into or modify the currently running
canonical CPU run. No Arena submission, issue, comment, post, credential, or
other external-state write occurred in this lane.

Isolated WIP/publication root:

```text
campaign/analytic/flat_psl4_hardware/
```

## Exact result

Final engine source SHA-256:

```text
d10accf9ebaf7355e11df53df2808736271dbd5019e829cb91418a7d8ba18893
```

Deterministic arm64 binary SHA-256 under Apple clang 21.0.0 / SDK 26.5:

```text
ea5b8b3605db160bd4718ffbf185e49b3447c09c091eacdc48880f7daf17e707
```

The frozen full replay (`runs/20260815T093000Z/receipt.json`) used macOS
26.5.1, Apple M4 Max, 48 GiB unified memory, Metal execution width 32, and
30,150,672,384-byte `maxBufferLength`.

### First production discovery

The excluded production run found a fourth retained symmetry-distinct PSL-4
class at shard 64 / task 549676:

```text
0011001101001101100011001010100101010000110100000101000000000111111100
```

The Metal task and an independent CPU replay agree exactly on 103,573,514
nodes, 439 leaves, 438 central rejects, 87,570,847 cheap prunes, 220,369,636
exact checks, 117,766,375 exact prunes, and one valid leaf. Standard-library
replay verifies PSL 4, canonicality, and non-equivalence to the three retained
public fixtures. The unchanged Arena verifier returns `1.5233061447261282`,
which misses the minimizing gate `1.280726494964255`; no submission was made.
Only the compact authored record `discoveries/psl4_class_04.json` is published.

### Second production discovery

The same excluded production run found a fifth retained symmetry-distinct
PSL-4 class at shard 261 / task 357625:

```text
0000100000001100010011101010111010010000111111010011001011000110100110
```

The Metal task and independent CPU replay agree exactly on 91,069,979 nodes,
181 leaves, 180 central rejects, 80,148,941 cheap prunes, 190,152,440 exact
checks, 99,994,624 exact prunes, and one valid leaf. Standard-library replay
verifies PSL 4, canonicality, and non-equivalence to the three fixtures and the
first published discovery. A hash-pinned audit of all 24 retained
flat-polynomials corpus rows found no symmetry match. The unchanged Arena
verifier returns `1.551067003100272`, again missing the minimizing gate, so no
submission was made. Only the compact authored record
`discoveries/psl4_class_05.json` is published.

### Hard task #351916

- nodes: 82,824,482
- leaves: 101
- central rejects: 100
- valid leaves/classes: 1/1
- cheap prunes: 66,160,332
- exact checks: 182,221,485
- exact prunes: 100,048,090
- exact canonical class:
  `0000011100001011111111110101001010111100110011001101010110010110010110`
- final external wall: 1.110 seconds, including process startup, runtime Metal
  compilation, deterministic 1,408-parent differential, three public fixtures,
  task generation, transfer/synchronization, host replay, and JSON output.

### Completed canonical shard 0

Every one of 84 task rows matches the frozen canonical journal:

- nodes: 2,657,274,264
- leaves/central rejects: 5,209/5,209
- valid leaves/classes: 0/0
- cheap prunes: 2,380,084,186
- exact checks: 5,513,165,177
- exact prunes: 2,883,827,168
- Metal dispatches: 829
- counter/answer mismatches: 0
- external wall: 22.973 seconds
- frozen CPU solver/dispatcher: 2,415.090/2,415.455 seconds
- end-to-end speedup: 105.13×

### Completed canonical shard 1 and bare-engine concurrency

All 98 shard-1 rows also match exactly. One stream takes 30.178 seconds.
Running shard 0 and shard 1 concurrently:

- nodes: 6,127,055,662
- Metal dispatches: 1,775
- external wall: 35.730 seconds
- exact row mismatches: 0 across 182 tasks
- throughput: 171,481,238 nodes/second
- gain over the measured single-stream throughput: 1.488×
- child swaps: 0

The pinned bare-engine receipt records a 10,447,060,992-byte maximum resident
size for a directly launched child and zero child swaps. That is not an
aggregate concurrent-memory measurement. Two is the largest tested stream
count; three or more have no safety or throughput claim.

### Durable dispatcher concurrency

The production-shaped wrapper starts a fresh process for each task so every
task becomes an individually fsynced, resumable receipt. A new exact replay of
shards 0 and 1 verifies 182/182 rows and records:

- nodes: 6,127,055,662
- external pair wall: 41.188 seconds
- throughput: 148,757,560 nodes/second
- shard task-wall sums: 32.410/40.795 seconds
- counter/answer mismatches: 0
- task receipts: 182; complete shard receipts: 2
- initialization: hash-pinned 1,408-parent/three-fixture self-test

This is the evidence that governs deployment ETA. The faster 35.730-second
batch result is an engine ceiling, not the durable-dispatcher rate. The exact
binary/config/init/task/journal/shard tree is retained under
`runs/20260815T104000Z/`; its independently reconstructible artifact-set hash
is `58ef80c142d9fc907ba0e716147f3ebb32a952fe0f4eaa7c89ed3a7020a18a31`.
The retained audit is intentionally `incomplete` globally because the bounded
pilot ran exactly shards 0 and 1, not all 8,192 shards.

## Whole-run ETA, including skew

`fixtures/completed_shard_sample.tsv` freezes 11 completed random shards:

- mean: 3,058,258,138 nodes/shard
- range: 2,494,612,395–3,688,507,832
- population standard deviation: 414,448,291
- coefficient of variation: 13.55%

Seven shards known to have started from empty journals average 2,733.998 CPU
solver-seconds. At eight workers, that projects 32.40 days for all 8,192
shards. The retained two-stream durable-dispatcher rate projects 46.78 hours;
applying the sample minimum/maximum shard sizes gives 38.16–56.42 hours. Thus
the evidence-backed whole-run estimate is roughly **16.62× faster than the
active eight-worker CPU route**, not the 105× one-process headline. Pilot
overhead and heavier unseen tails justify budgeting beyond this envelope.

## Exactness gates in source

- split-depth-12 universe must equal 730,810 tasks;
- `SplitMix64(1)` must equal `0x910A2DEC89025CC1`;
- all active templates at depths 25…34 must occur in the frozen 34-lag order;
- random CPU/Metal child sets and every step counter must match for 128 parents
  at each depth 24…34;
- nonleaf `output_count == nodes` and all leaf counter identities are checked;
- every GPU complete leaf is replayed by an independent scalar host verifier;
- frontier/output count, Metal maximum buffer length, allocations, command
  status, and output capacity fail closed;
- switch depth is fixed at 24 and exact stride at 1.

The full-shard comparison is row-by-row, not merely aggregate. This prevents
equal aggregate totals from masking task-index drift.

## Resume and receipt compatibility

The bare C++ engine is intentionally not a drop-in replacement for the frozen
CPU dispatcher. `gpu_dispatch.py` supplies a separate append-only boundary:

1. requires a narrowly timestamped, caller-owned run root and rejects packet
   descendants, canonical campaign state, broad roots, symlinks, and unsafe
   ancestors;
2. uses an explicit locked/idempotent initialization that resumes from an
   interrupted pre-config source archive, archives the binary, freezes exact
   source/binary/config hashes, and persists independent self-test evidence;
3. invokes one explicit task per process, rejecting truncated or mismapped
   engine envelopes;
4. atomically creates collision-checked read-only task receipts, fsyncs files
   and parent directories, and validates them on resume;
5. writes the canonical-shape task journal only after the full shard exists;
6. atomically finalizes a hash-pinned shard receipt;
7. `audit_run.py` independently reconstructs journal records, totals,
   task-index/receipt hashes, answer hashes, frozen pins, and initialization
   evidence before considering completeness;
8. global completion requires all 730,810 indices exactly once in their correct
   SplitMix64 shards, with every shard complete.

Read-only modes prevent accidental mutation but are not cryptographic
immutability against the directory owner. The copied-allowlist regression
races two explicit initializers after simulating an interrupted setup, runs two
real streams, checks byte-identical resume, and rejects six adversarial
journal/summary/provenance mutations. It also re-audits the retained 182-task
tree and validates the summary receipt semantically rather than trusting only
its file hash. No GPU output should be copied into the live CPU directory by
hand.

## Migration recommendation

The independent deployment audit has changed the long-run hold to GO. Any
deployment—including the separate shadow run now in progress—must still use a
new isolated root and obey this sequence; mutable `production_runs/` evidence
is outside this frozen publication packet:

1. run `gpu_dispatch.py --init-only` against a new, narrowly named run root;
2. launch two dispatcher processes on two untouched shards in that root;
3. inspect their task/shard receipts and run `audit_run.py --allow-incomplete`;
4. repeat over a bounded 8–16-shard pilot and confirm memory/time tails;
5. continue with at most two streams if source, binary, config, task sets, and
   counters remain pinned;
6. at completion require `audit_run.py` status `complete`/`exactly_once=true`;
7. merge by an explicit, separately reviewed operation only after both proof
   inventories agree—never by mutating the active run in place.

## Primary grounding

Paperclip source `/papers/arx_1212.4930/content.lines`, lines 8–34, documents
GPU/package exhaustive PSL search, outside-in branching, XOR/popcount, prefix
parallelism, and CUDA package mode:
https://paperclip.gxl.ai/citations/papers/arx_1212.4930#L8-L34

Apple's primary Metal documentation states that diverging SIMD lanes execute
both branches. This is why the accelerator uses level-synchronous compaction
instead of recursive per-lane DFS:
https://developer.apple.com/documentation/metal/creating-threads-and-threadgroups#SIMD-groups

## Publication boundary

Publish only files named in `PUBLICATION_MANIFEST.json`. The retained validation
Mach-O is deliberately allowlisted for byte-reproducible evidence; exclude all
unretained compiled binaries, `__pycache__`, temporary outputs, canonical run
state, host logs, environment dumps, and every credential. License holder:
James Weatherhead; packet license: MIT.
