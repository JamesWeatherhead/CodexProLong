# Second autocorrelation: global multiscale support-bundle crossover

Status: **frozen negative frontier; not a submission candidate**.

This isolated lane tested whether a current high-scoring second-autocorrelation
extremizer could escape its basin by replacing *coordinated, macroscopic support
regions* with regions from independent public basins. It deliberately did not
repeat the previously exhausted SimpleTES transfer directions, a global phase
offset, a terminal-cluster split, tiny packet births, or incumbent float polish.

The search evaluated 360 deterministic candidates with the unchanged Arena
verifier. No candidate met the live acceptance gate.

## Exact result

At the live read used for this run:

- public leader: `0.963588110582029`
- minimum improvement: `1e-5`
- acceptance gate: `0.9635981105820289`
- retained local seed: `0.9635881192968997`
- retained seed gap to gate: `9.991285129240524e-6`
- accepted checkpoints: `0`

The seed is slightly above the displayed public leader, but it is still below
the platform's minimum-improvement gate and therefore is not publishable as an
Arena submission.

| Replay class | Exact score | Gap to gate | Support change | Interpretation |
| --- | ---: | ---: | ---: | --- |
| retained seed | `0.9635881192968997` | `9.991285129240524e-6` | none | baseline only |
| exact reflection control | `0.9635881192968996` | `9.991285129351546e-6` | XOR `570,932` | expected symmetry; not a discovery |
| best new non-control | `0.9635782863504964` | `1.982423153257251e-5` | XOR `0` | block-mass mosaic, worse |
| best new material-support mosaic | `0.9635776917997542` | `2.041878227476701e-5` | 38 births | tiny boundary effect, worse |
| best finite topology mosaic | `0.9625196080123224` | `1.078502569706541e-3` | XOR `67,863` | genuine topology change, substantially worse |

For this receipt, a finite topology mosaic means material-support XOR at least
1,000 and moved L1 mass fraction at least `0.001`, excluding the exact
reflection and whole known-parent controls. The threshold is a reporting
classification, not an optimization constraint.

## Search design

`search.py` builds five independent source directions from three public C2
basins, the reflection of the strongest public basin, and the reflection of the
retained seed. Several dual-gradient summaries rank coherent segment bundles:
the unique exact maximum, soft maxima at beta `1e5` and `1e6`, and a uniform
top-512 active-lag surrogate.

The finite grid was:

- segment counts: `4, 8, 16, 32, 64`
- replacement modes: raw and block-mass-preserving
- coordinated masks: always at least two segments
- interpolation weights: `0.003, 0.01, 0.03, 0.1, 0.3, 1.0`
- enumerated mask specifications: `450`
- deterministically selected broad/diverse specifications: `60`
- exact verifier evaluations: `360`

All candidates were clipped nonnegative, renormalized to the seed mass, hashed,
and evaluated through the frozen verifier. Every evaluation is recorded in
`events.jsonl`; no accepted checkpoint exists.

## Independent replay

From the repository root:

```sh
.venv/bin/python \
  campaign/analysis/second_autocorrelation_global_multiscale/replay.py \
  campaign/analysis/second_autocorrelation_global_multiscale/runs/20260815T062500Z-bundle
```

The replay is independent of `search.py`. It verifies the frozen verifier and
all input hashes, reconstructs all 360 candidates, checks every candidate-value
hash, topology metric, and exact score, and verifies the existing append-only
receipt byte-for-byte. It does not overwrite any artifact.

The canonical verifier SHA-256 is
`dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`.
The complete frozen Arena corpus audited before the run has SHA-256
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.

## Literature routing

Paperclip full-text reads established that high-resolution C2 work uses
spike-plus-comb structure, direct full-resolution optimization, and multiscale
continuation. Boyer--Li explicitly report simulated annealing across a
`23 -> 115 -> 575` hierarchy. ImprovEvolve reports learned improvement and
perturbation operators with basin hopping. Exa primary-source discovery added
sliding Frank--Wolfe and exchange methods over measures, whose support-insertion
and joint-relocation pattern motivated the coordinated support-bundle probe.

That last connection is heuristic only: finite-convergence results for convex
sparse inverse problems do **not** transfer to the nonconvex C2 max-ratio
objective. Source URLs, line pins, query provenance, and scope limits are in
`literature.json`.

## Publication boundary

The scripts, documentation, and JSON receipts are publication-safe. NumPy
payloads are intentionally ignored: they are large, and the retained seed has
SimpleTES/AGPL-derived provenance that requires a separate licensing decision.
The local replay remains exact because those arrays are retained in the WIP
directory and identified by cryptographic hashes.

No Arena submission, post, vote, issue, GitHub commit, or push was made by this
lane.
