# Exact PSL-4 Metal accelerator

This packet demonstrates a clean-room, exact Apple Metal route for the active
length-70 PSL ≤ 4 proof. On an Apple M4 Max, one completed 8,192-way canonical
shard was replayed with **zero mismatches across all 84 tasks and 2,657,274,264
search nodes**. Final external wall was 22.973 seconds, versus 2,415.09
solver-seconds and 2,415.46 dispatcher wall-seconds for the corresponding CPU
shard: 105.13× end-to-end on that shard. The durable evidence is in
`runs/20260815T093000Z/receipt.json`.

The hard reference task #351916 also reproduces every frozen counter and the
known canonical PSL-4 class:

```text
0000011100001011111111110101001010111100110011001101010110010110010110
```

## What changed

The frozen CPU engine recursively explores one outside-in branch at a time.
That maps poorly to a GPU because recursive branch lengths diverge. This engine
keeps the exact CPU task generator through depth 24, then runs a
level-synchronous breadth-first frontier from depth 24 through 35:

1. one Metal thread evaluates one of the four outside-in children;
2. exact integer outer-lag, cheap-lag, and active-lag bounds are applied in the
   frozen order;
3. atomic compaction creates the next depth's frontier;
4. every surviving complete leaf is replayed independently by the host before
   canonicalization.

All feasibility decisions use integer correlations, XOR/popcount, parity, and
closed integer intervals. Floating point is used only for timing.

## Reproduce

Requirements: macOS, Apple Metal, Apple clang with Objective-C++ support, and
Python 3.9 or newer. No API key, network access, package install, downloaded
verifier, or canonical campaign tree is needed.

Quick differential test (about two seconds on the measured M4 Max):

```bash
python3 campaign/analytic/flat_psl4_hardware/benchmark.py
```

Full 84-task shard replay (about 25 seconds on the measured M4 Max):

```bash
python3 campaign/analytic/flat_psl4_hardware/benchmark.py --full
```

Write a new append-only receipt:

```bash
python3 campaign/analytic/flat_psl4_hardware/benchmark.py --full \
  --out /tmp/psl4-metal-receipt.json
```

Replay the first class recovered by the separate production search using only
Python's standard library:

```bash
python3 campaign/analytic/flat_psl4_hardware/verify_discovery.py
```

`test_packet.py` copies only the publication allowlist, reruns itself from that
copy, recompiles with warnings enabled, races two initializers, dispatches two
real one-task streams, verifies that six adversarial receipt mutations are
rejected, re-audits the retained 182-task tree, and semantically checks the
dispatcher receipt's schema, pins, cardinalities, fixture totals, hashes, and
throughput arithmetic.

The publication freezer is also fail-safe: ordinary invocation verifies the
current manifest without writing, and regeneration is explicit. Even
`--help` is covered by a byte-immutability regression.

```bash
python3 campaign/analytic/flat_psl4_hardware/freeze.py
python3 campaign/analytic/flat_psl4_hardware/freeze.py --help
# Maintainers only, after reviewing every changed allowlisted byte:
python3 campaign/analytic/flat_psl4_hardware/freeze.py \
  --write --refresh-timestamp
```

An isolated, append-only dispatcher is included for controlled deployment:

```bash
python3 campaign/analytic/flat_psl4_hardware/gpu_dispatch.py \
  --run-dir /private/tmp/psl4-metal-run-20260815T120300Z-pilot \
  --virtual-shards 8192 --init-only
python3 campaign/analytic/flat_psl4_hardware/gpu_dispatch.py \
  --run-dir /private/tmp/psl4-metal-run-20260815T120300Z-pilot \
  --virtual-shards 8192 --shard 123
python3 campaign/analytic/flat_psl4_hardware/audit_run.py \
  --run-dir /private/tmp/psl4-metal-run-20260815T120300Z-pilot \
  --allow-incomplete
```

Initialization is explicit, locked, idempotent, and resumes after a pre-config
interruption. It archives and hashes the exact source and binary and freezes a
standalone differential-self-test receipt before any shard can start. The
dispatcher creates one collision-checked, read-only task receipt at a time,
fsyncs each file and its directory, validates every prior receipt on resume,
rejects truncated results, and atomically finalizes the shard journal and
receipt. “Read-only” protects against accidental rewrites; it is not a claim
of tamper resistance against an owner who can chmod and coherently replace an
entire run tree.

The auditor independently reconstructs journal bytes, counters, task-index and
task-receipt hashes, canonical-answer hashes, frozen source/binary/config pins,
and self-test evidence. It accepts a global proof only when all 730,810 task
indices occur exactly once in the correct SplitMix64 shard and every shard is
complete. Run roots must have the narrow timestamped name shown above and may
not be inside this packet, the campaign state, a symlinked path, or a broad
filesystem root.

## Exact evidence

- Random parent differential: 128 parents at each depth 24…34, 1,408 total,
  comparing CPU and Metal child sets and all per-step counters.
- Public fixtures: three known PSL-4 sequences survive the complete-leaf
  kernel and host check.
- Hard task: #351916 matches nodes, leaves, central rejects, cheap prunes,
  exact checks, exact prunes, and the canonical answer.
- Full shard 0: all 84 task rows match `fixtures/shard0_reference.tsv`; aggregate
  totals are 2,657,274,264 nodes, 5,209 leaves/rejects, 2,380,084,186 cheap
  prunes, 5,513,165,177 exact checks, and 2,883,827,168 exact prunes.
- Full shard 1: all 98 rows independently match
  `fixtures/shard1_reference.tsv`; two concurrent processes reproduce both
  shards without a counter or answer mismatch.
- Resource stress: shard 0 executes 829 completed Metal dispatches in one
  process. The bare batch-engine two-stream test executes 1,775 dispatches and
  6.127 billion nodes in 35.730 seconds. Per-dispatch autorelease pools prevent
  command and resource references from accumulating. Its pinned receipt
  records a 10,447,060,992-byte maximum directly launched child resident size
  and zero child swaps. That maximum is not aggregate concurrent GPU memory.
- Durable dispatcher: two explicit-task streams reproduce all 182 shard-0/1
  rows, create 182 individually fsynced task receipts, and process 6.127
  billion nodes in 41.188 seconds: 148.758 million nodes/second. Unlike the
  earlier disposable-root timing sample, this validation preserves its exact
  binary, config, initialization receipt, 182 task receipts, journals, shard
  receipts, and audit tree under `runs/20260815T104000Z/`. Its reconstructed
  artifact-set SHA-256 is
  `58ef80c142d9fc907ba0e716147f3ebb32a952fe0f4eaa7c89ed3a7020a18a31`.
- First production discovery: shard 64 / task 549676 produced
  `0011001101001101100011001010100101010000110100000101000000000111111100`.
  Independent CPU replay matched all seven counters exactly, including
  103,573,514 nodes and one valid leaf. The class has exact PSL 4, is canonical
  under the eight retained symmetries, and is distinct from all three public
  fixtures. The unchanged Arena verifier scores it `1.5233061447261282`, so it
  does not clear the `1.280726494964255` first-place gate and was not submitted.
  The compact, self-checking record is `discoveries/psl4_class_04.json`; mutable
  production receipts remain excluded.

The engine fails closed if a frontier would exceed the 32-bit output counter,
the device's `maxBufferLength`, a Metal allocation fails, a command fails, or a
GPU leaf fails the independent host replay.

## Migration recommendation

The exact kernel and isolated dispatcher are ready for a controlled GPU shadow
pilot and offer a material path to shorten the proof. They are deliberately
**not** wired into the currently running CPU directory:

- the bare engine emits batch JSON, while `gpu_dispatch.py` invokes explicit
  tasks so interruption loses only the in-flight task;
- all GPU artifacts live in a new run directory and must never be mixed into
  the active journal;
- a bare-engine `--max-tasks` result is labeled `truncated`, and the dispatcher
  refuses it;
- global completion still requires the exactly-once audit.

Recommended deployment sequence: leave the active CPU run untouched; launch a
new, hash-pinned GPU shadow run on untouched shards; use at most **two**
concurrent Metal processes; require the built-in self-test, host leaf replay,
atomic task receipts, and final exactly-once audit; merge only after task set,
config, source, binary, journal, and receipt hashes agree.

The deployment estimate uses the durable dispatcher—not the faster bare batch
engine and not the 105× single-shard headline.
Eleven completed CPU shards average 3.058 billion nodes with 13.55% coefficient
of variation. Seven shards known to have started from empty journals project
the active eight-worker CPU run at 32.40 days. Two durable streams sustain
148.758 million nodes/second, yielding a 46.78-hour point estimate and a
38.16–56.42-hour envelope from the observed shard-size range: about 16.62×
faster than the eight-worker CPU estimate. Two is the largest tested stream
count. Three or more are untested, so this packet makes no safety or throughput
claim for them. See `runs/20260815T104000Z/dispatcher_receipt.json`; the
separate 09:30 `concurrency_receipt.json` is the bare-engine ceiling and the
09:30 dispatcher receipt is a superseded disposable-root sample.

The retained audit correctly reports `status: incomplete`: this was exactly a
two-shard, 182-task validation pilot, not a claim that the 730,810-task proof
has run. An independent deployment audit later released a separate shadow run.
It paused on the first new class, completed independent CPU and Arena replay,
then resumed with that exact shard hash acknowledged; its changing
`production_runs/` state and control handoffs are deliberately excluded from
this frozen publication packet. Nothing here claims that live run is complete.

The canonical CPU run and every frozen accelerator packet were read-only
throughout this experiment.
