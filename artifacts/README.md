# Public evidence index

This directory contains a deliberately small, static evidence release. It is
not a dump of the live campaign workspace.

## Result records

| Result | Score | Candidate SHA-256 | Verifier SHA-256 | Receipt | Public lineage |
|---|---:|---|---|---|---|
| [Erdős minimum overlap #2507](https://einsteinarena.com/api/solutions/2507) | `0.3808585748578583` | `43d6096c…57db6` | `7c0e78d9…920b0` | [JSON](receipts/erdos-min-overlap.json) | Continued from Hyra [#2440](https://einsteinarena.com/api/solutions/2440) |
| [First autocorrelation #2504](https://einsteinarena.com/api/solutions/2504) | `1.502743649232617` | `e3f90379…8f018` | `2964e97c…763a8` | [JSON](receipts/first-autocorrelation-inequality.json) | Continued from ExoMind-TTS [#2494](https://einsteinarena.com/api/solutions/2494) |
| [Kissing number d11/605 #2500](https://einsteinarena.com/api/solutions/2500) | `1.7102381876374992` | `89fad32e…83de` | `9bb3804d…d4ef` | [JSON](receipts/kissing-number-d11-605.json) | Continued from ExoMind-TTS [#2435](https://einsteinarena.com/api/solutions/2435) |
| [Kissing number d12/842 #2499](https://einsteinarena.com/api/solutions/2499) | `0.5470735423441564` | `99b544b5…e4ec7f` | `54dc5d8c…f88be` | [JSON](receipts/kissing-number-d12-842.json) | Continued from ExoMind-TTS [#2495](https://einsteinarena.com/api/solutions/2495) |
| [Uncertainty principle #2505](https://einsteinarena.com/api/solutions/2505) | `0.3130922465438896` | `12590e6c…dedf2` | `8986d94f…7289` | [JSON](receipts/uncertainty-principle.json) | Continued from BasinHopper [#2482](https://einsteinarena.com/api/solutions/2482) |

The full 64-character hashes are in each receipt. Receipt scores are frozen
local verifier outputs; the public API values in
[`docs/STATUS.md`](../docs/STATUS.md) can differ in the final binary64 digit.
`prior_leader_agent` and `prior_leader_score` identify the benchmark head used
to compute the recorded margin before the campaign result. `artifact_sha256`
identifies the exact candidate mirror in an earlier public revision, while
`candidate_sha256` is the controller's canonical candidate hash; the underlying
payload is intentionally omitted from this release.

## Snapshot and certificate

- [`snapshot.json`](snapshot.json) records the 17 rankable problems, frozen
  leaders, verifier hashes, campaign ranks, and integrity labels at
  `2026-08-15T12:07:25.964492Z`.
- [`certificates/erdos-min-overlap-continuous.json`](certificates/erdos-min-overlap-continuous.json)
  records the exact rational bound and continuous reduction for the Erdős
  submission. Its interpretation and limitations are documented in
  [`docs/ERDOS_MINIMUM_OVERLAP.md`](../docs/ERDOS_MINIMUM_OVERLAP.md).

## Why candidate bytes are absent

All five results refined public Arena starting points. The platform records
make those lineages visible, but no general redistribution license for the
underlying submitted payloads was established during this release audit.
Accordingly, this repository publishes links, hashes, scores, receipts, and
selected project-authored certificate metadata—not the payload bytes.

That choice avoids implying that the root MIT License relicenses other agents'
work. This release supports provenance and public-result traceability; it does
not support independent offline reproduction or verification from this
repository alone.
