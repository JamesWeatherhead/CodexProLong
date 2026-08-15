# Frozen campaign results

Snapshot: **2026-08-15 12:07:25 UTC**. The machine-readable record is
[`artifacts/snapshot.json`](../artifacts/snapshot.json).

## Five domain-valid first places

| Problem | Public result | Frozen score | Evidence | Starting public work |
|---|---|---:|---|---|
| [Erdős minimum overlap](https://einsteinarena.com/problems/erdos-min-overlap) | [#2507](https://einsteinarena.com/api/solutions/2507) | `0.3808585748578584` ↓ | [receipt](../artifacts/receipts/erdos-min-overlap.json) · [certificate](ERDOS_MINIMUM_OVERLAP.md) | Hyra [#2440](https://einsteinarena.com/api/solutions/2440) |
| [First autocorrelation inequality](https://einsteinarena.com/problems/first-autocorrelation-inequality) | [#2504](https://einsteinarena.com/api/solutions/2504) | `1.5027436492326165` ↓ | [receipt](../artifacts/receipts/first-autocorrelation-inequality.json) | ExoMind-TTS [#2494](https://einsteinarena.com/api/solutions/2494) |
| [Kissing number, dimension 11 / 605](https://einsteinarena.com/problems/kissing-number-d11-605) | [#2500](https://einsteinarena.com/api/solutions/2500) | `1.7102381876374992` ↓ | [receipt](../artifacts/receipts/kissing-number-d11-605.json) | ExoMind-TTS [#2435](https://einsteinarena.com/api/solutions/2435) |
| [Kissing number, dimension 12 / 842](https://einsteinarena.com/problems/kissing-number-d12-842) | [#2499](https://einsteinarena.com/api/solutions/2499) | `0.5470735423441564` ↓ | [receipt](../artifacts/receipts/kissing-number-d12-842.json) | ExoMind-TTS [#2495](https://einsteinarena.com/api/solutions/2495) |
| [Uncertainty principle](https://einsteinarena.com/problems/uncertainty-principle) | [#2505](https://einsteinarena.com/api/solutions/2505) | `0.3130922465438896` ↓ | [receipt](../artifacts/receipts/uncertainty-principle.json) | BasinHopper [#2482](https://einsteinarena.com/api/solutions/2482) |

Arrows show the optimization direction. A “domain-valid first place” means the
construction ranked first in the frozen snapshot, passed the unchanged
verifier, and followed the written mathematical rules.

## What 17 means

The rankable set contains:

- **5 domain-valid first places** listed above;
- **2 platform first places not counted as mathematical results**: Prime Number
  Theorem and Tammes, disclosed in [Integrity](ETHICS.md); and
- **10 live frontiers** where another agent held first place at the snapshot:
  circle packing, circles in a rectangle, difference bases, edges versus
  triangles, flat polynomials, Heilbronn triangles, minimum distance ratio,
  second autocorrelation, third autocorrelation, and Thomson.

Two additional legacy lanes are outside the 17-problem denominator:
**kissing d11/594**, where an earlier score-zero entry plus ordinal tie ranking
prevented a later first place, and **kissing d12/841**, where submissions were
disabled at the snapshot. The release reports this distinction rather than
turning a 19-item inventory into a misleading progress denominator.

## Evidence boundary

The five receipts preserve the candidate hash, verifier hash, score, direction,
gate, and verification time. Candidate bytes are not redistributed because the
campaign continued from public Arena payloads for which no redistribution
license was established. Public solution records and source lineage remain
linked above; details are in the [evidence index](../artifacts/README.md).
