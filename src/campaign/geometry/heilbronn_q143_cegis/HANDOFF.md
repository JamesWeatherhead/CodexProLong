# Handoff: q=143 bounded closure

Status: frozen bounded no-go; no candidate and no external write.

## What is now closed

- All four formerly unresolved heterogeneous radius-3/5 cells represented by
  public IDs 630, 1005, 1004, and 649 are exact support-formula UNSAT.
- For each representative, the four labels ranked by prior small radius and
  low-determinant pressure were pre-expanded to hex radius 8.
- Every single-label and two-label release among those four labels is UNSAT.
- Total durable release inventory: 44 scenarios = 4 bases + 16 singles + 24
  pairs. A second fresh process reproduced every deterministic formula,
  scenario-assumption fingerprint, and UNSAT status.

This closes the four logical timeouts in
`campaign/geometry/heilbronn_bnb/ADAPTIVE_Q143.md`; it does not close all q=143
cells or the continuous problem.

## Evidence

- Exact base formula: 131,298 clauses, 3,298,876 literals, SHA-256
  `d317f82ee2e014ec1ec92087f0446c3fe102cbead33f25f4d6044fb5f15f3461`.
- Exact release formulas:
  - 630: `9ca91328d3cf50a5db59ad41c8562f7b44ff6b85d0a979377221af0590270bee`
  - 1005: `1f1a451645501aa0a383957352566fc3d13f929f69ec46d8061fd61b30d5e994`
  - 1004: `48b2da2bb0775bc7ed6ebf1c21f8cb1c8815a29c08b06bb80de325e2956e3f28`
  - 649: `87bd75112cf6dea0897cff801a4ebc0999188d6750d5916eec0c39097b114efa`
- `receipt.json` is the compact durable record, including input/source hashes,
  every union-domain coordinate hash, every scenario allowed-map hash and
  assumption hash, run hashes, replay agreement, and Paperclip line citations.
- Raw checkpoints under `runs/` are local reproducibility evidence and remain
  excluded from publication because they are large.

The solver receipt is not a proof-checker-validated DRAT/LRAT certificate. Any
public claim must say “exact finite support formulation returned UNSAT and was
replayed,” not “formal global proof.”

## Files

Publish-safe include list:

- `.gitignore`
- `README.md`
- `HANDOFF.md`
- `q143_cegis.py`
- `support_closure.py`
- `verify_candidate.py`
- `freeze_receipt.py`
- `receipt.json`

Keep excluded:

- `runs/`
- `__pycache__/`
- `*.pyc`
- `/tmp/q143-replay-*.log`

## Next move

Do not rerun tuple-at-a-time CEGIS or these radius-8 one/two-label cells. A
meaningfully new q=143 attack must expand three or more coupled labels, change
seed/topology, or use an independently proof-producing CSP/SAT backend. Given
the zero candidate yield here, another unsolved Arena problem may have higher
expected value.
