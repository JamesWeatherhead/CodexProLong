# Provenance

This packet is a clean-room implementation. It does not copy external source
code, binaries, sequence tables, credentials, Arena data, or the frozen
enumerator. The only derived fixture is a compact table of factual counters
from one completed local canonical shard.

## Primary literature

- Anatolii Leukhin and Egor Potehin, *Binary Sequences with Minimum Peak
  Sidelobe Level up to Length 68*, arXiv:1212.4930. Paperclip full-text lines
  8–11 report the exponential search, eight-Tesla CUDA run, branch-and-bound,
  assembler popcount, and package regime; lines 13–21 define aperiodic
  autocorrelation/PSL and its symmetries; lines 23–34 describe outside-in tree
  search, XOR/popcount, independent prefixes, CUDA `__popcull`, and package
  mode. [Paperclip line-pinned source](https://paperclip.gxl.ai/citations/papers/arx_1212.4930#L8-L34),
  [primary arXiv record](https://arxiv.org/abs/1212.4930).
- Apple, *Creating threads and threadgroups*. Its SIMD-groups section explains
  that lanes execute the same code and divergent paths execute both branches.
  That hardware constraint motivated level-synchronous frontier expansion
  instead of assigning one recursive DFS to each lane.
  [Apple Metal documentation](https://developer.apple.com/documentation/metal/creating-threads-and-threadgroups#SIMD-groups).
- G. E. Coxson and J. Russo, *Efficient Exhaustive Search for Optimal-Peak-
  Sidelobe Binary Codes*, IEEE Transactions on Aerospace and Electronic
  Systems 41(1), 2005. This is the primary reference already associated with
  the frozen outside-in search.
  [DOI 10.1109/TAES.2005.1413763](https://doi.org/10.1109/TAES.2005.1413763).

No Paperclip material is vendored. Paperclip was used read-only for discovery
and line-pinned inspection.

## Frozen local inputs audited read-only

| Input | SHA-256 |
|---|---|
| base `psl4_popcount.cpp` | `a9c7dfd13aeb06302d192215a49888552925f76b3a96e33b2450d16661363b42` |
| canonical dispatcher | `59c659a4f582f87cf3f5f08fbe636973299ec738c1bcf2d0a4ee124dc43f2df2` |
| active-lag patch | `2ad9e2387e92c5b8ef8217e5d616a4ff41bc6da960ce821c22d4c4563992b51b` |
| active-lag builder | `bb767120eba083324a4e033a6c8001d9e5e5c5680b67bb951cb881423fe50e22` |
| generated active reference | `431ae5ed5c8800a0639cbd3cc7d298afc50d58b9b23e18a10634efd290f4c3ee` |
| completed canonical shard-0 journal | `36e09b797b978764074adc78f54b29272c6cde79d017292aca69b3abd6754a9d` |
| completed canonical shard-1 journal | `73f85fc7e360118e5488768099991b90a17e0c94031ecc644de8258a8f1e4889` |

`fixtures/shard{0,1}_reference.tsv` contain only canonical task identifiers,
six integer counters, and answer fields from those journals.
`fixtures/completed_shard_sample.tsv` contains shard id, task count, node
count, solver time, and whether the shard began from an empty journal for 11
completed shards. Paths, hostnames, logs, binaries, and unrelated run state
were deliberately omitted. Every fixture is independently hashed in the
benchmark or publication receipt.

`runs/20260815T104000Z/dispatcher_receipt.json` is a retained,
production-shaped two-stream measurement from this packet: explicit
initialization followed by only reference shards 0 and 1. It pins 182 task
receipts, both fixture hashes, all counter/answer comparisons, pair wall time,
source/binary/config hashes, exact ETA arithmetic, and the retained audit's
artifact-set hash. The full binary/config/initialization/task/journal/shard
tree remains under the same timestamped directory and independently
reconstructs to
`58ef80c142d9fc907ba0e716147f3ebb32a952fe0f4eaa7c89ed3a7020a18a31`.
The memory fields are copied by hash from the bare-engine concurrency receipt
and explicitly retain their limited scope: maximum resident size of a directly
launched child, not aggregate concurrent GPU allocation. No safety claim is
made for stream counts above the tested ceiling of two.

## Licensing

All original source and documentation in this packet are MIT licensed. The
fixture records factual measurements and contains no copied implementation.
No third-party license obligations are introduced by this packet.
