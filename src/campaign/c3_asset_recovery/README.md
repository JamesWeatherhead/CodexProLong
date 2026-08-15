# C3 public-asset recovery audit

This is a read-only, commit-pinned audit of downloadable constructions and search
programs for the third autocorrelation inequality. It uses the unchanged frozen
Arena verifier and compares every recovered construction with all 40 C3
submissions in the frozen corpus.

## Result

No recovered asset improves, or is competitive with, the frozen local frontier.

| Asset | bins | exact verifier score | Frozen-Arena duplicate |
|---|---:|---:|---|
| `jmsung-best` | 100,000 | 1.452521155046884 | #1188, #1422 |
| `simpletes` | 400 | 1.4536754655951831 | no |
| Together 2026 | 400 | 1.4545548626983331 | #12 |
| official AlphaEvolve | 400 | 1.4556427953745403 | #4 |

The local frontier is `1.4515653850221024`. The best newly distinct asset,
SimpleTES, is worse by `0.002110080573080708` and misses the strict live gate
`1.4515618638902068` by `0.00211360170497632`. A topology-transfer run was
therefore not justified under the bounded experiment rule.

ThetaEvolve's five distinct 300/400-bin arrays were also replayed; their best
score is `1.4930012021944892`. Hyra-results has only first- and second-
autocorrelation assets at the pinned commit. ImprovEvolve's reported
autocorrelation result is C2, while GigaEvo, OpenEvolve, and ShinkaYale expose C3
starters but no frozen evolved C3 output. MLEvolve reports scores but publishes
no downloadable C3 asset. A read-only fork scan found that all 16 public
SimpleTES forks and the ahead official AlphaEvolve fork retain byte-identical C3
assets.

## Reproduce

From the repository root:

```bash
.venv/bin/python campaign/c3_asset_recovery/asset_replay.py
.venv/bin/python campaign/c3_asset_recovery/replay_local.py
```

The first command performs commit-pinned HTTP GETs, verifies every source hash,
extracts literal arrays without executing third-party code, and regenerates
`receipt.json`. The second command is network-free and rechecks 25 cached source
artifacts, ten payloads, all 40 frozen corpus rows, and every exact verifier
score.

The verifier SHA-256 is
`b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9`.
The corpus SHA-256 is
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.

## Literature and provenance

- AlphaEvolve reports a 400-cell C3 construction at about 1.4557
  ([Paperclip lines 190–193](https://paperclip.gxl.ai/citations/papers/arx_2506.13131#L190-L193)).
- A later mathematical report restates the C3 setup and result
  ([Paperclip lines 118–121](https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L118-L121)).
- ImprovEvolve's autocorrelation result is C2, not C3
  ([Paperclip line 1](https://paperclip.gxl.ai/citations/papers/arx_2602.10233#L1)).
- GigaEvo's validation set does not include C3
  ([Paperclip lines 30–32 and 65–66](https://paperclip.gxl.ai/citations/papers/arx_2511.17592#L30-L32,L65-L66)).

All repository URLs, commits, raw-file hashes, and declared licenses are in
`receipt.json`. Third-party source blobs and arrays stay in git-ignored `cache/`
and `payloads/`; no third-party array is republished by this packet. Repositories
with no asserted license are recorded as `NOASSERTION` and their files remain
local. No Arena, discussion, submission, or GitHub write occurred.

