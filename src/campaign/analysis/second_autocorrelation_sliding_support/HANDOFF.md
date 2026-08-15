# Frozen handoff: C2 native sliding-support exchange

## Decision

Do not submit.  Neither the live `1e-5` gate nor the retained seed was cleared
by a genuine support-topology change.  The useful result is a bounded,
independently replayed negative frontier for certificate-guided insertion plus
joint packet relocation.

## Reproducible frontier

- canonical run: `runs/20260815T064800Z-sliding-support`
- exact evaluations: `64`
- genuine topology evaluations: `56`
- gate clearers: `0`
- frozen seed: `0.9635881192968997`
- live gate: `0.9635981105820289`
- seed gap: `9.991285129240524e-6`
- best overall: `0.9635881193286749` at evaluation 57; non-genuine
- best genuine topology: `0.9635327720022921` at evaluation 50
- best joint relocation: `0.9603462119745643` at evaluation 21
- independent replay: `PASS`, 64/64 exact value hashes, maximum score delta 0
- independent replay SHA-256:
  `0d6c208556b00bb32bd1306f0e7fd9e79b693a252987d236949fee3ab4ac0b21`

Evaluation 50 inserts `1e-6` seed mass in a width-5455 packet.  It creates 92
material births, support XOR 92, and moved L1 fraction
`8.03385930279921e-6`, but loses `5.534729460754395e-5` from the seed.  The
best event overall lets the birth collapse to `1.6111592554725864e-11` mass;
its picounit gain is numerical local adjustment rather than a qualifying new
support topology.

## Exact independent replay

```sh
cd /path/to/EinsteinArena
./.venv/bin/python campaign/analysis/second_autocorrelation_sliding_support/replay.py --run campaign/analysis/second_autocorrelation_sliding_support/runs/20260815T064800Z-sliding-support
```

Expected fields are `status: PASS`, `evaluation_count: 64`,
`reconstructed_candidate_hash_mismatches: 0`,
`maximum_absolute_score_delta: 0.0`, and `gate.cleared: false`.

The replayer checks the frozen verifier's SHA-256, but it does not import or
execute downloaded verifier code on host. It independently implements the
small published scoring formula. Submission-grade acceptance remains isolated
behind the campaign's Docker controller.

## Publish-safe include/exclude boundary

Include exactly:

- `.gitignore`
- `README.md`
- `HANDOFF.md`
- `literature.json`
- `receipt.json`
- `search.py`
- `replay.py`
- `runs/20260815T064800Z-sliding-support/events.jsonl`
- `runs/20260815T064800Z-sliding-support/gradient_check.json`
- `runs/20260815T064800Z-sliding-support/independent_replay.json`
- `runs/20260815T064800Z-sliding-support/input_manifest.json`
- `runs/20260815T064800Z-sliding-support/specs.json`
- `runs/20260815T064800Z-sliding-support/summary.json`

Exclude exactly:

- `runs/SMOKE/**`
- `runs/20260815T064500Z-sliding-support/**`
- `runs/**/*.npy`
- `__pycache__/**`
- `*.pyc`
- `*.tmp`

The `064500Z` run is an explicitly aborted pre-canonical run.  Smoke output is
noncanonical.  NumPy arrays are large, and the frozen seed inherits
SimpleTES/AGPL-derived provenance requiring separate licensing review.  Keep
the arrays locally for exact replay.

## Reopen condition

Reopen only with a support mechanism not represented here: repeated adaptive
insertion with re-computed certificates, jointly shape-changing rather than
copied atoms, a true multi-active-lag bundle/subgradient step, or continuation
through the support kink.  Do not rerun this exact packet-width/location grid,
smaller birth floors, longer fixed-support L-BFGS polishing, cross-basin
mosaics, global phase offsets, terminal-cluster splitting, or tiny packet
births.

No external write was made.
