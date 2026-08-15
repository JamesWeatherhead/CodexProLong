# C3 asset-recovery handoff

## Frozen decision

Stop this lane as a quantified no-go. Ten public constructions were recovered,
deduplicated against all 40 frozen C3 submissions, and replayed through the
unchanged verifier. No distinct asset is close enough to support the requested
bounded topology transplant.

- Public leader: `1.4515718638902069`
- Minimum improvement: `0.00001`
- Strict gate: `1.4515618638902068`
- Local n=102,400 frontier: `1.4515653850221024`
- Remaining local gate gap: `0.000003521131895611873`
- Best distinct recovered seed: SimpleTES n=400,
  `1.4536754655951831`
- SimpleTES gap to local frontier: `0.002110080573080708`
- Best high-resolution recovered seed: jmsung n=100,000,
  `1.452521155046884`, exactly duplicated by submissions #1188 and #1422

The SimpleTES construction has values SHA-256
`63d4d512d032f2ca03315661d4cd1eaf66c3bb48fa1b4b5e2c4b5a066b8e4075`.
The high-resolution jmsung construction has values SHA-256
`ad4403f4f560ce298d0d4e0552154694c612c26c095e9781f1fa1dd9fed8cbd5`.
The local frontier has values SHA-256
`d047ef4d92f27ff2cd8c2d01a2e63eb896dc28a9c03979a1ae101fd7411736c8`.

## Coverage

- Downloaded arrays: SimpleTES; Together 2026; Together's AlphaEvolve mirror;
  official AlphaEvolve notebook; five ThetaEvolve variants; jmsung's n=100,000
  seed.
- Downloaded programs, statically inspected only: SimpleTES; five ThetaEvolve
  programs; GigaEvo starter/helper/metric; OpenEvolve starter; ShinkaYale
  starter.
- Complete-tree negative audits: Hyra-results has C1/C2 only; MLEvolve exposes
  no C3 artifact. ImprovEvolve's paper result is C2. GigaEvo has no frozen C3
  output.
- Fork audit: 16 SimpleTES forks and the ahead official AlphaEvolve fork add no
  distinct C3 asset.

## Exact evidence

- `asset_replay.py`: commit-pinned GET, hash verification, safe literal parsing,
  corpus deduplication, unchanged-verifier replay, atomic receipt generation.
- `replay_local.py`: network-free replay over cached files and payloads.
- `receipt.json`: compact provenance and exact results; contains no arrays.
- Verifier SHA-256:
  `b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9`.
- Frozen corpus SHA-256:
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.

Fresh local replay returned `status: ok`, with 25 source artifacts, ten
payloads, and 40 corpus rows checked. The exact scores in `receipt.json` are
literal results from the frozen evaluator, not rounded literature claims.

## Publication boundary

Publish-safe files:

- `.gitignore`
- `README.md`
- `HANDOFF.md`
- `asset_replay.py`
- `replay_local.py`
- `receipt.json`

Keep private/excluded:

- `cache/` (third-party source/license blobs and GitHub inventory)
- `payloads/` (third-party numerical arrays)
- `__pycache__/` and `*.pyc`

Licensing is preserved in the receipt. SimpleTES is AGPL-3.0-or-later;
AlphaEvolve, ThetaEvolve, Hyra-results, and OpenEvolve are Apache-2.0; jmsung and
GigaEvo are MIT. Together and ShinkaYale are `NOASSERTION`; their files remain
local. The audit made HTTP GETs only and performed no Arena or GitHub mutation.
