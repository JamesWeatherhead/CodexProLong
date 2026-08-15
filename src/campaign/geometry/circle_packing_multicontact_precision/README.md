# Circle-packing codimension-two precision/topology lane

This isolated campaign explores two-contact graph pivots from the 78-contact
`n=26` incumbent.  It does not repeat same-topology polishing, one-contact
continuation, stochastic void/global fields, or graph-module recombination.

The live verifier has a `1e-9` tolerance only on circle-circle overlap.  Wall
containment has no tolerance.  Results are therefore recorded as either
physical-strict or verifier-only, with maximum pair and wall overruns reported
separately.

The frozen campaign contains three exhaustive runs: the canonical incumbent, a
neutral edge-flip representative, and the strongest public noncanonical seed
(submission 1462).  Reproduce the frozen receipts with:

```bash
# From the EinsteinArena repository root:
.venv/bin/python campaign/geometry/circle_packing_multicontact_precision/freeze_receipt.py
.venv/bin/python campaign/geometry/circle_packing_multicontact_precision/replay_exact.py
.venv/bin/python campaign/geometry/circle_packing_multicontact_precision/replay_external_asset.py
```

`receipt.json` reports 9,270 solved two-contact graph systems, 8,699 accepted
labeled solutions, and 5,147 distinct unlabeled Weisfeiler-Lehman graph
classes.  No changed topology clears the gate.  `external_asset_replay.json`
also records the exact replay of a recovered ClaudeEvolve coordinate table.

`verifier_formula.py` is a clean-room mirror of the literal float64 formula.
The programs SHA-check the frozen verifier bytes but never import or execute
that downloaded file.

No Arena or GitHub write operation is performed by these programs.
