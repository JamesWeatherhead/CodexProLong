# C2 global topology: publish-safe handoff

No gate-clearing candidate was found, and no external post, vote, or
submission was made.

## Frozen live target

- problem: `second-autocorrelation-inequality`;
- leader `#2416`: `0.963588110582029`;
- strict gate: `0.963598110582029`;
- verifier SHA-256:
  `dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`.

The evidence gate covered all 29 retained C2 threads and all 120 replies,
cross-problem C2 references, the complete Jaech--Joseph Paperclip source,
ClaudeExplorer's Hyra-basin source and negative experiments, and the complete
`c2_root` / `c2_secondary` frontier. Jaech--Joseph's spike-plus-asymmetric-comb
structure motivated preserving coherent components rather than smearing or
interpolating them.

## Best retained exact payload

The strongest payload remains the prior changed-support checkpoint inherited
as this lane's seed:

`runs/20260815T041000Z-terminal-split/best.npy`

- independent literal-verifier replay: `0.9635881172701123`;
- gain over public `#2416`: `6.6880833e-9`;
- gap to strict gate: `9.99331191675612e-6`;
- `n = 1,999,999`, nonzeros `747,463`;
- value-byte SHA-256:
  `27d26ffb728ed8a6058c4828b337af0b28c3ed24fd8c5e8f5338a129aa75ffe9`;
- `.npy` file SHA-256:
  `17ae46a8532acd2ed6eb355b968e9e59936adc0335975fd18b67251e0040e640`.

Replay from `/Users/jacweath/EinsteinArena`:

```sh
.venv/bin/python campaign/analytic/c2_secondary/replay_exact.py \
  campaign/analytic/c2_global_topology/runs/20260815T041000Z-terminal-split/best.npy
```

## New bounded global screens

1. `macro_phase_search.py`: 362 exact evaluations of seven-region offsets,
   affine phase schedules, joint schedules, and greedy macro coordinates.
   Best `0.9635881106065262` (`+2.4496183e-11` over public), still
   `9.9999755e-6` below gate. Every change to a non-negligible region was
   sharply negative.
2. `terminal_split_search.py`: 378 exact evaluations that moved `1e-8` to
   `0.9` of the entire 29.15%-mass terminal spike/comb into the void as a
   translated or mirrored coherent copy. Even the smallest fraction was
   downhill. Best translated `0.9635881164544261`; best mirrored
   `0.9635881125281137`.

Reproduce the two screens:

```sh
.venv/bin/python campaign/analytic/c2_global_topology/macro_phase_search.py \
  --run-root campaign/analytic/c2_global_topology/runs \
  --stamp reproducible-phase --random-schedules 96

.venv/bin/python campaign/analytic/c2_global_topology/terminal_split_search.py \
  --run-root campaign/analytic/c2_global_topology/runs \
  --stamp reproducible-terminal-split
```

## Narrowed frontier

Whole-region phase surgery and a finite-mass two-cluster to three-cluster jump
are both closed at exact-verifier precision. Together with the retained
negative results (packet births, tangent packet projections, value polish,
tooth splitting, chirps, interpolation, and inverse-autoconvolution
projections), the remaining credible route is a genuinely independent
full-resolution optimization history that discovers a new coherent lattice
before exact active-bundle polishing. More surgery on `#2416` is not supported
by the measured first variations.

Publish-safe result summary (not posted):

> We ran two verifier-exact global-topology screens from the C2 frontier: 362
> coordinated comb-phase schedules and 378 finite-mass terminal-cluster splits.
> The former gained only 2.45e-11 over public #2416, while every coherent
> two-cluster-to-three-cluster split was downhill even at 1e-8 transferred
> mass. The best retained changed-support payload replays at
> 0.9635881172701123, still 9.9933e-6 below the submission gate. These results
> close phase surgery and terminal-cluster splitting, but not independent
> high-resolution spike/comb basin discovery.
