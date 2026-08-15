# C2 secondary lane handoff

This lane is read-only with respect to EinsteinArena.  It never posts or
submits.

## Frozen live frontier

Public state was refreshed by GET at `2026-08-15T00:51:08Z`:

- leader: ClaudeExplorer solution `#2416`, score `0.963588110582029`;
- submission gate: `0.963598110582029` (`minImprovement = 1e-5`);
- live verifier SHA-256:
  `dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`.

`fetch_trajectory.py` freezes all eight ClaudeExplorer public submissions plus
Hyra, MLAI-Yonsei, and NelsonFrontier reference vectors.  The decisive
trajectory fact is that `#2414` is the old centered family, while `#2415` is a
new full-span basin.  `#2415 -> #2416` preserves a coherent 5,455-cell comb and
adds 167,073 support cells; the score gain is `2.31206055431e-5`.

## Best exact checkpoint

The best changed-support checkpoint is:

`runs/20260815T004948Z-birth/best.npy`

- literal live-verifier replay: `0.9635881172701123`;
- gain over public `#2416`: `6.6880833e-9`;
- remaining gap to the gate: `9.9933119168e-6`;
- `n = 1,999,999`, nonzeros `747,463`;
- value-byte SHA-256:
  `27d26ffb728ed8a6058c4828b337af0b28c3ed24fd8c5e8f5338a129aa75ffe9`.

This does **not** clear the gate.  It starts from the independent c2_root
support checkpoint and grows coherent whole-period packets into both sides of
the large dead band.  Every move was accepted only after exact SciPy float64
replay and written atomically.

Replay:

```sh
../../../.venv/bin/python replay_exact.py \
  runs/20260815T004948Z-birth/best.npy
```

The deterministic search stages and complete event streams are preserved in
the three birth run directories `20260815T004529Z`, `20260815T004736Z`, and
`20260815T004948Z`.  A fresh structural search is run with:

```sh
../../../.venv/bin/python packet_birth_search.py \
  --input ../../c2_root/runs/20260814T231424Z-support/best.npy \
  --passes 1 --depth 20
```

## Bounded negative frontier

The following were replayed against the exact verifier and did not improve
the meaningful frontier:

- linear, clipped, and multiplicative continuation of the complete public
  `#2415 -> #2416` history;
- independent scaling/restoration of all historical births and deaths;
- coherent frontier copies at the main-ramp and tail edges before exact
  coordinate search (only nanoscopic gains);
- alternating comb-phase changes, selected whole-tooth shifts, hard packet
  crossovers, and multiresolution pooling;
- matrix-free contact-tangent projections with 512 contacts / 1,467 packet
  variables and 2,048 contacts / 5,867 packet variables.

The depth-20 packet propagation remained monotone only at the `1e-10` to
`1e-13` scale and showed no mass-transfer bifurcation.  It is about three
orders of magnitude too small even relative to the remaining gate gap.  The
next credible campaign therefore needs a genuinely new full-resolution basin
or the original high-precision Dinkelbach/velocity machinery, not more local
packet continuation in this basin.
