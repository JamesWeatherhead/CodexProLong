# C2 global topology lane

Read-only with respect to EinsteinArena.  This lane excludes the exhausted
packet-birth continuation and searches coordinated, whole-region comb phase
topologies.  Every retained checkpoint is scored with a literal copy of the
live SciPy verifier expression.

Live state at `2026-08-15T03:07Z`:

- leader `#2416`: `0.963588110582029`;
- strict gate: `0.963598110582029`;
- verifier SHA-256:
  `dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`.

The evidence gate includes all 29 retained C2 threads, all 120 replies, all
cross-problem C2 references, the complete Jaech--Joseph Paperclip ingest, the
ClaudeExplorer experiment guide/Hyra campaign, `c2_root`, and the prior
`c2_secondary` negative frontier.

## Completed phase-schedule screen

`macro_phase_search.py` tested 362 whole-region comb offsets, affine row-phase
schedules, deterministic joint schedules, and a greedy macro coordinate
sweep. The exact best was only `0.9635881106065262`, a `+2.4496183e-11`
gain over public solution `#2416` and still `9.9999755e-6` below the strict
gate. The atomic receipt is `runs/20260815T034500Z-phase/summary.json`.

## Finite-mass cluster split

`terminal_split_search.py` tests a discontinuous two-cluster to three-cluster
topology jump. It replaces a finite fraction of the complete terminal
spike/comb component by a translated or mirrored coherent copy in the void,
while preserving terminal mass exactly. This does not continue the exhausted
cell/packet-birth family.

The 378-candidate screen found no improvement. The best translated and
mirrored changes both occurred at the smallest tested mass fraction `1e-8`
and were already downhill; finite fractions fell rapidly away from the live
frontier. Receipt: `runs/20260815T041000Z-terminal-split/summary.json`.

See `HANDOFF.md` for independent replay, hashes, exact gaps, and reproduction
commands.
