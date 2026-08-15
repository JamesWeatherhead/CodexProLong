# Reproducible H100 continuation specification

The bounded Mac run established implementation behavior, not meaningful
global coverage. The continuation uses four independent native-grid histories
instead of crossover, interpolation, or an incumbent primary seed.

## Frozen environment

- Python 3.12
- NumPy 2.5.2
- SciPy 1.18.0
- PyTorch 2.13.0 with CUDA
- one H100 with at least 80 GB device memory
- `N = 1,999,999`, zero-padded FFT length `4,194,304`
- independent seeds `2026081511` through `2026081514`

Run the non-optimizing preflight from either supported layout:

```sh
PYTHONDONTWRITEBYTECODE=1 python \
  campaign/analysis/second_autocorrelation_native_basin/public_packet/h100_preflight.py
```

or insert `src/` before `campaign/`.

## Phase A: native histories

The exact machine-readable settings are in `configs/h100_phase_a.json`.
Launch one history per seed with population 16 and 50,000 optimizer steps.
This is 800,000 member-steps per history and 3,200,000 across four histories.
At the initial, each 500-step audit, and final audit, evaluate all 16 members:
102 audit passes per history, 1,632 exact member evaluations per history, and
6,528 across four histories. This frozen count includes the harness's separate
final audit even when the final step also triggered its scheduled audit. A
refactor that de-duplicates that pass changes the expected total to 6,464 and
must be recorded as a plan deviation.

Start with population 16. After a separate 20-step throughput preflight, only
the population may be adjusted to 8 or 24; record that deviation and do not
compare its throughput as if it used the frozen plan. Every 5,000 steps retain
the top four members within that history and respawn the other twelve from
fresh independently randomized spike/comb parameters.

Proposal settings are learning rate `4e-7`, noise scale `1e-3`, and noise
gamma `0.65`. Native initializers independently randomize period, phase,
orientation, spike width/location/mass, tooth width/amplitude, chirp,
envelope, secondary lattice, and optional dense background.

## Acceptance boundary

Accelerator values only propose checkpoints. Accept a strict run-best
improvement only when an independent CPU float64 clean-room computation and a
separately governed, unchanged, hash-pinned verifier agree within the frozen
tolerance. The verifier is not downloaded or executed by this packet. If that
authorized adapter is unavailable, retain proposal receipts only and make no
candidate-grade claim.

Candidate threshold: `0.963598110582029`. This is the recorded public leader
`0.963588110582029` plus `0.00001`.

## Phase B: exact bundle and insertion

For the highest exact checkpoint from each Phase-A history, use
`configs/h100_phase_b.json`. At every sampled point collect all exact argmax
lags; do not substitute a single lag for a true multi-active Clarke hull.
Escalate sampling radius only to observe distinct active branches. Run support
insertion only after a multi-active bundle is present, and recompute the exact
certificate after every accepted insertion.

If the bundle remains single-active through radius `1e-3`, record
`multi_active_lag_not_reached` and stop insertion, as the Mac pilot did. No
Arena, GitHub, or other external write belongs to either phase.
