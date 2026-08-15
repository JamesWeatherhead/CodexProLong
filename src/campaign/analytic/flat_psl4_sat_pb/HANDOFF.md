# Frozen handoff: PSL-4 SAT/PB feasibility

## Decision

Keep native MiniCard as a hinted exact verifier/completer. Do not replace the
active-lag C++ global enumerator with any tested SAT/PB regime.

The positive result is narrow but strong: MiniCard reproduces three
successively full-symmetry-blocked canonical PSL-4 fixtures in 0.000756 seconds
total with zero conflicts. The negative frontier is decisive for autonomous
enumeration: every cold and post-three-class-block CaDiCaL/MiniCard job hit the
five-second process cap; CP-SAT remained unknown at three seconds; reversal
lex symmetry did not change that classification.

## Cube comparison

On 256 deterministic depth-28 cubes (14 free middle bits), all engines agree
exactly on three SAT and 253 UNSAT cubes. The raw C++ outside-in baseline took
0.00137529 seconds. MiniCard took 0.108046 seconds total and 0.063984 seconds
inside solve calls; CaDiCaL took 0.995885 and 0.910260 seconds respectively.
Thus MiniCard was 46.5x slower even after excluding formula/bootstrap overhead,
and CaDiCaL was 662x slower. The stronger active-lag C++ engine would only
widen this gap.

## Exact evidence

- SAT/PB matrix:
  `runs/20260815T085500Z/benchmark.json`, SHA-256
  `db6bbfd8cd81422aed55775a9f5b309b0d31db8fd22e585332611e19ae0d0a09`
- cube comparison:
  `runs/20260815T084700Z/cube_benchmark.json`, SHA-256
  `141d6284bddfb579b64a2688b43ade448482142d223b20de7ce0c14bfadcec48`

Every SAT model is re-evaluated using integer autocorrelations. The known-chain
stage adds one blocking clause for each of the eight
reversal/negation/alternation transforms before requesting the next fixture.
Cube SAT/UNSAT classifications are independently matched against exhaustive
C++ continuation.

## Reopen condition

Reopen only for a topology/decomposition change that makes *unhinted* or
post-class-block instances solve materially faster on unseen cubes. Do not
repeat sequential counter, cardinality network, totalizer, modulo totalizer,
k-modulo totalizer, native MiniCard, CP-SAT, the tested lex leader, or depth-28
incremental assumptions without a new mechanism.

## Public boundary

Publish only `PUBLICATION_MANIFEST.json` and its allowlist. Exclude both smoke
runs, `__pycache__/`, generated binaries, and every unlisted file. PySAT and
OR-Tools are pinned runtime dependencies, not vendored assets. No verifier,
canonical-state file, credential, Arena write, or GitHub write is present.
