# Frozen handoff: C560 topology escape

## Decision

No gate-clearer. Do not submit any artifact from this lane.

The corrected v2 chain is the only canonical run:

`runs/20260815T105000Z-c540-descendants-v2/`

It was produced by `search.py` SHA-256
`d3c2307ab4e6149ddbe97e5a28b070fa826ff835a30b7c30b206468782084e5a`
and independently replayed by `replay_exact.py` SHA-256
`8e8aa086332e1a34001d592d845558d7c2eb10b5fba25b3111f072a277037aa8`.

## Frozen numerical evidence

- 7 input graph classes × 4 spectral scalings = 28 accepted trials.
- Initial labeled hull-edge agreement: 28/28.
- Source topology retained: 20/28.
- Defect-free final topology: 24/28.
- Distinct final exact-isomorphism classes: 7.
- Best all: `37148.1301703428`, trial 1, scarred
  `{5:16,6:262,7:4}`, gap `+0.8357528805427137`.
- Best defect-free: `37148.14103932371`, trial 22, migrated
  separation-5 class, gap `+0.8466218614485115`.
- Best source-retaining: `37148.250685079416`, trial 16,
  separation-4 class, gap `+0.9562676171553903`.
- Target at or below: `37147.29441746226`.
- Gate-clearers: 0.
- Maximum verifier-replay score delta: 0.
- Maximum initial spectral score delta: `7.275957614183426e-12`.
- Minimum candidate pair distance: `0.20246920486707462`.
- Maximum candidate norm error: `2.220446049250313e-16`.
- Clamp activations: 0.

Canonical private hashes:

- `events.jsonl`: `56aaafe480c4629083690d600e5bdf9ea2e99e4d81943a4e4d3169b582bb0fbf`
- `summary.json`: `4284a99fe9842a6df23628d7bd7767eba564ac308e69b91761871c9c6125fc62`
- `best.json`: `964e3e455481d1a84934745592d114bb42fb7e7d4b580a55506e666d8522195e`
- `independent_replay.json`: `17c332e533c8758a9415d06be4b4d7ce168d40c82f71e00f4a5b11ca0591df8e`
- Prior topology summary: `433dc3a15d958f4029f9d1152d4065bf4a29087c828ad1c5aa0b6fd411919cf3`
- Frozen verifier: `4cdf454acc790c97f2cfcb1e62f44f571ff9f44f87566c341865bc1c234ba5af`

## Reproduction

Private exact replay:

```bash
cd <EinsteinArena-checkout>
.venv/bin/python -B campaign/geometry/thomson_c560_distant_pentagon/replay_exact.py \
  campaign/geometry/thomson_c560_distant_pentagon/runs/20260815T105000Z-c540-descendants-v2
```

Public packet test from a CodexProLong checkout:

```bash
python3 -B src/campaign/geometry/thomson_c560_distant_pentagon/test_packet.py
```

## Publication boundary

Publish only the paths in `PUBLICATION_MANIFEST.json`. In particular, exclude:

- `private_inputs/**`;
- `runs/**`, including all coordinate payloads;
- `private_generator/**`;
- `__pycache__/**`, `*.pyc`, and temporary files;
- Arena state, verifier bytes, corpus snapshots, Paperclip/Exa response bodies,
  Antiprism source, and all buckygen source/binaries.

The public packet is a coordinate-free result/provenance record plus authored
search and replay code. It is not advertised as a standalone reproduction of
the private numerical run.

## Next route

Do not spend another bounded run on these seven separation-4 sources. The only
structurally distinct continuation justified by this packet is a lawful,
complete C560 enumeration filtered at pentagon separation at least 6 (or a
separate published C560 asset corpus), followed by the same exact-hull and
energy pipeline. The present seven-source family is closed as a no-go.
