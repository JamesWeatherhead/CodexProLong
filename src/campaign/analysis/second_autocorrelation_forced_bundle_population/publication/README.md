# Second autocorrelation: forced-bundle population

Status: **frozen bounded mechanism validation; not a candidate**. No Arena,
GitHub, issue, comment, vote, verifier, submission, or post write occurred.

This lane is confined to this directory. It contains clean-room reference
machinery validated at `N = 4,095` and a frozen plan for a future native
`N = 1,999,999` spike/comb population designed to retain several competing
convolution-max branches from initialization. It does not load an incumbent,
a retained NumPy array, SimpleTES coefficients, or third-party candidate values.

The distinguishing hypothesis is that the high-scoring C2 face is easier to
reach by continuing an explicit multi-lag equioscillation constraint than by
first optimizing a single-active-lag smooth branch and waiting for an exact
tie. Proposed steps must improve a minimum over a bundle of branch objectives;
the unchanged verifier remains authoritative for any later acceptance.

## Corpus gate

`audit_corpus.py` fully decoded all 38 frozen public C2 construction records
(15,656,738 values), all 29 thread bodies, and all 120 replies from the
hash-pinned SQLite corpus. It retained no coefficient values. The audit found
public discussion of local active-lag/Remez ideas, but no completed fresh
native-resolution population that deliberately forces branch switching before
every bundle step.

## Reference implementation

`forced_bundle.py` implements, from the published formula:

- a deterministic spike/comb population generator with a coherent multi-tooth
  lattice, graded ramp, empty band, terminal spike/comb, and dense exploration
  background;
- exact lag-branch values and analytic log-height gradients;
- ridge balancing between separated convolution maxima;
- the slack-aware simplex dual of the finite-branch maximin model; and
- exact unsmoothed backtracking acceptance.

The derivative check passes at relative error `7.1584e-11`. A synthetic exact
two-lag kink gives two nonzero dual weights (`0.42424`, `0.57576`).

## Bounded pilot

The canonical 4-member, 4,095-cell run is
`runs/20260815T120831Z-reference-pilot`.

- best path: `0.7005292919979981 -> 0.7156018568597433`;
- all 16 bundle steps improved the exact reference score;
- effective bundle size was 7 or 8 at every step;
- checkpoint SHA-256:
  `32f3e85f848da524de2c78de31062d2020c251272ef3e635eb4a4d541c76a5c3`;
- independent replay: `PASS` at `0.7156018568597436`;
- strict live gate: `0.9635981105820289`;
- remaining gap: `0.2479962537222853`.

This validates the mechanism and determinism only. It provides no evidence
that the route will reach the native frontier.

## Reproduce

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  campaign/analysis/second_autocorrelation_forced_bundle_population/forced_bundle.py \
  self-test

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  campaign/analysis/second_autocorrelation_forced_bundle_population/replay.py \
  --run campaign/analysis/second_autocorrelation_forced_bundle_population/runs/20260815T120831Z-reference-pilot
```

`H100_PLAN.md` freezes the only justified continuation: a deterministic
float64 population at exactly `N=1,999,999`, with explicit early stop gates and
no automatic verifier or external write.

## Frozen publication copy

This directory is an exact text-only allowlist. `PUBLICATION_MANIFEST.json`
lists the byte length and SHA-256 of every payload file. It excludes all NumPy
checkpoints and the frozen corpus database, while preserving their exact hashes.

From the repository root, validate the copied allowlist and replay the canonical
receipt entirely from copied source (the reconstructed checkpoint remains only
in memory):

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  campaign/analysis/second_autocorrelation_forced_bundle_population/publication/test_publication.py

PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  campaign/analysis/second_autocorrelation_forced_bundle_population/publication/source_replay.py \
  --run campaign/analysis/second_autocorrelation_forced_bundle_population/publication/runs/20260815T120831Z-reference-pilot
```

The first command is standard-library only. Source replay additionally requires
the NumPy and SciPy versions pinned in `requirements-replay.txt`. No command in
the copied replay path invokes the Arena verifier or performs an external write.
