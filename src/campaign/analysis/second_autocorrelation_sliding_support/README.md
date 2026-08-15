# Second autocorrelation: native sliding-support exchange

Status: **frozen negative frontier; not a submission candidate**.

This isolated lane tested a native nonlinear support-changing operator against
the actual second-autocorrelation max-ratio.  It starts from the frozen
`0.9635881192968997` construction, inserts a new packet at a certificate-ranked
off-support location, relocates incumbent and inserted packets, jointly
re-optimizes all packet weights, and lets only the unchanged Arena verifier
decide acceptance.  It is not another interpolation between known basins.

No candidate met the live gate.

## Exact result

- public leader at the frozen read: `0.963588110582029`
- minimum platform improvement: `1e-5`
- strict acceptance gate: `0.9635981105820289`
- frozen seed: `0.9635881192968997`
- seed gap to gate: `9.991285129240524e-6`
- exact verifier evaluations: `64`
- genuine support-topology candidates: `56`
- gate clearers: `0`

| Replay class | Exact score | Gap to gate | Support change | Decision |
| --- | ---: | ---: | --- | --- |
| frozen seed | `0.9635881192968997` | `9.991285129240524e-6` | none | baseline only |
| best overall event | `0.9635881193286749` | `9.991253353991425e-6` | 22 births, XOR 22, moved L1 `4.116340084940196e-11` | vanishing insertion; fails the predeclared topology gate |
| best genuine topology change | `0.9635327720022921` | `6.533857973678447e-5` | 92 births, XOR 92, moved L1 `8.03385930279921e-6` | valid topology change, but worse than the seed |
| best joint relocation | `0.9603462119745643` | `0.003251898607464665` | 42 births, 21 deaths, XOR 63, moved L1 `0.0026490495535611285` | native relocation is strongly destructive in this bounded grid |

The best overall event improves the seed by only
`3.1775249098586755e-11`.  It is not a qualifying topology change and remains
below the platform gate.  The best genuine topology event is evaluation 50;
its value-byte SHA-256 is
`07dcd3b995b68a75eb078b07e9efa57b2024c379027ba392c6c0e8703774c991`.

## What was tested

The operator follows the useful computational pattern from Sliding
Frank--Wolfe and exchange methods, while making no claim that their convex
theory transfers here:

1. Differentiate the exact unique-active-lag branch of the C2 log-ratio.
2. Use the resulting certificate as a linear oracle for a previously empty
   target window.
3. Copy a native packet template to that target and augment the support.
4. Search bounded integer packet relocations and jointly solve every packet
   amplitude against the actual nonsmooth C2 objective.
5. Permit a new atom to return to zero weight, then classify material support
   change before exact-verifier acceptance.

The finite grid used packet widths `65, 257, 1025, 5455`, movable-incumbent
counts `4, 8`, one certificate-ranked birth per specification, and eight
weight/location configurations per specification.  Configurations included
free insertion, insertion floors of `1e-6` and `1e-5` seed mass, simultaneous
one-cell relocation, middle- and bound-scale relocation, and an alternating
subset move.  The canonical run used at most eight L-BFGS-B iterations per
fixed support configuration.

A candidate was predeclared as a genuine topology change only if it had at
least one material birth, support XOR at least two, and moved L1 mass fraction
at least `1e-6`.  Material support means values above
`5.035052906511295e-14`.  This reporting gate prevents numerical dust from
being mistaken for a new support geometry.

## Interpretation

The certificate consistently supports an *infinitesimal* new packet: allowing
the inserted mass to vanish yields only tens of picounits of score change.
Requiring `1e-6` mass produces a real support birth but lowers the objective;
moving existing sharp packets is much more damaging.  Within this bounded
operator family, the incumbent therefore behaves like a support-stable local
optimum whose active-lag balance is sensitive to integer relocation.

This is a quantified negative result for this finite search, not a theorem
against Sliding Frank--Wolfe on C2.  It does not exclude repeated adaptive
insertions, shape-changing atoms, a bundle treatment of multiple active lags,
or a continuation scheme that crosses support kinks more smoothly.

## Independent replay

From the repository root:

```sh
./.venv/bin/python \
  campaign/analysis/second_autocorrelation_sliding_support/replay.py \
  --run campaign/analysis/second_autocorrelation_sliding_support/runs/20260815T064800Z-sliding-support
```

`replay.py` does not import `search.py`.  It reconstructs all 64 candidate
arrays from the frozen seed plus logged atom parameters, checks every value-byte
hash and topology classification, and calls the untouched verifier.  The
independent receipt reports zero candidate-hash mismatches and zero score
drift.  Its SHA-256 is
`0d6c208556b00bb32bd1306f0e7fd9e79b693a252987d236949fee3ab4ac0b21`.

The verifier SHA-256 is
`dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`.
The previously audited frozen Arena corpus SHA-256 is
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.

## Evidence and publication boundary

Paperclip supplied line-addressable full text for the exact
support-augmentation, weights-only correction, joint parameter descent, and
zero-weight pruning sequence.  Exa independently discovered and inspected the
primary Sliding Frank--Wolfe and measure-exchange literature.  The source
links, line pins, request provenance, and explicit scope limits are recorded in
`literature.json`.

The scripts, documentation, and compact JSON audit trail are publication-safe.
All NumPy arrays are intentionally ignored: they are large, and the frozen seed
inherits SimpleTES/AGPL-derived provenance requiring a separate licensing
decision.  Exact local replay remains possible because every payload is retained
locally and hash-pinned.

No Arena submission, post, vote, issue, GitHub commit, or push was made by this
lane.
