# C2 SimpleTES transfer handoff

Frozen classification: **quantified no-go; do not continue this basin.**

- Initial exact score: `0.9635881172701123`.
- Retained exact score: `0.9635881192968997`.
- Retained payload SHA-256:
  `b122a49ed64b07217948baa2119e28efe81e8179fd7f9e97da5e3717fea257bd`.
- Retained values SHA-256:
  `8ad79d6fa04b566b852138709d959df928a7ec7cd36143d03a80901c1b485e34`.
- Frozen verifier SHA-256:
  `dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`.
- Strict gate: `0.963598110582029`; gap: `9.991285129351546e-6`.
- Total exact verifier calls: 2,184 (1,714 definitive path, 444 preliminary,
  26 integer-repeat probes).

The registered source and incumbent envelopes are already nearly identical:
mass correlation `0.997227535985581`, support correlation
`0.9962358850529099`. Direct resamples, material-support births,
mass-preserving block transplants, signed finite crossovers, and an exact
integer-repeat/pad construction all failed. The complete gain was only
`2.026787404574293e-9`, leaving a gap 4,929.6 times larger; the second fine
cycle decayed to 7.0% of the first. Do not spend more compute on SimpleTES
alignment or blockwise support births without a mathematically different
topology-changing mechanism.

Publish-safe compact files:

- `.gitignore`
- `transfer_search.py`
- `fine_polish.py`
- `repeat_probe.py`
- `repeat_probe.json`
- `replay_exact.py`
- `receipt.json`
- `README.md`
- `HANDOFF.md`

The `runs/` JSON summaries and event logs are reproducible local evidence but
need not be mirrored. Keep all `runs/**/*.npy`, `__pycache__/`, and the
AGPL-licensed upstream SimpleTES payload out of a public snapshot unless its
redistribution and notice requirements are handled explicitly.

No external write occurred.
