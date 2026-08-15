# Frozen handoff: C2 global multiscale support topology

## Decision

Do not submit. The run cleared neither the live `1e-5` platform gate nor the
retained local seed. The useful result is a bounded negative frontier against
coherent cross-basin support mosaics.

## Reproducible frontier

- canonical run: `runs/20260815T062500Z-bundle`
- exact evaluations replayed: `360`
- accepted checkpoints: `0`
- retained seed: `0.9635881192968997`
- live acceptance gate: `0.9635981105820289`
- retained gap: `9.991285129240524e-6`
- independent replay status: `pass`
- independent replay SHA-256:
  `f7956bebaee7f4597e169f331d46acda8622850c9b8c14b04abeee0864fb656a`

The apparent event maximum is only the exact reflection control:
`0.9635881192968996`, one binary64 ulp below the seed. The best genuinely new
non-control is `0.9635782863504964`. The best material-support-changing mosaic
is `0.9635776917997542` with 38 births. Under the predeclared finite-topology
classification (support XOR at least 1,000 and moved L1 fraction at least
`0.001`), the best mosaic is `0.9625196080123224`, with 67,855 births, 8 deaths,
and support XOR 67,863.

## Exact replay

```sh
cd /Users/jacweath/EinsteinArena
.venv/bin/python campaign/analysis/second_autocorrelation_global_multiscale/replay.py campaign/analysis/second_autocorrelation_global_multiscale/runs/20260815T062500Z-bundle
```

Expected summary fields are `status: pass`, `evaluations_replayed: 360`,
`gate_cleared: false`, and `gap_to_gate: 9.991285129240524e-6`.

## Publish-safe include/exclude boundary

Include exactly:

- `.gitignore`
- `README.md`
- `HANDOFF.md`
- `literature.json`
- `receipt.json`
- `search.py`
- `replay.py`
- `runs/20260815T062500Z-bundle/events.jsonl`
- `runs/20260815T062500Z-bundle/independent_replay.json`
- `runs/20260815T062500Z-bundle/selected_specs.json`
- `runs/20260815T062500Z-bundle/source_manifest.json`
- `runs/20260815T062500Z-bundle/summary.json`

Exclude exactly:

- `runs/SMOKE/**`
- `runs/**/*.npy`
- `__pycache__/**`
- `*.pyc`
- `*.tmp`

Reason: smoke output is noncanonical; NumPy arrays are large and the retained
seed inherits SimpleTES/AGPL-derived provenance. Keep the arrays locally for
exact replay unless licensing is reviewed. Do not treat any reflected or
whole-parent control as a new construction.

## Reopen condition

Reopen this family only with evidence for a new global basin mechanism not
represented by cross-basin segment replacement: for example, a joint support
relocation method that optimizes the nonlinear C2 ratio natively rather than
interpolating between known parents. Do not spend another budget on smaller
alphas, more segment counts, phase shifts, terminal splitting, or packet births.

No external write was made.
