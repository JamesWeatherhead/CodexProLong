# Rectangle packing codimension-two topology lane

This isolated lane attacks `circles-rectangle` by exhaustive simultaneous
two-contact pivots from a rigid 65-equation seed.  The perimeter equality is
kept active; every pair of the remaining 64 active pair/wall contacts is
released, the visible vertices of the resulting two-dimensional flex cone are
enumerated, and each two-new-contact child is solved nonlinearly.

The companion `codim3_pivots.py` enumerates all active-contact triples and
uses direct three-dimensional half-space intersection to recover every
non-box vertex before nonlinear replay.  Both searches were run from both
known rigid public contact-graph classes; the frozen aggregate result is in
`HANDOFF.md` and `receipt.json`.

This does not repeat same-topology precision, one-contact release, stochastic
global fields, void relocation, or float-lattice searches.  Every candidate is
replayed with the unchanged live verifier and API schema.  Results separately
report pair and perimeter tolerance use; both verifier tolerances are `1e-9`.

No Arena or GitHub write is performed.

`verifier_formula.py` cleanly mirrors the literal float64 acceptance formula.
The frozen verifier bytes are SHA-checked but never imported or executed.

```bash
# From the EinsteinArena repository root:
.venv/bin/python \
  campaign/geometry/rectangle_multicontact_precision/codim2_pivots.py \
  --stamp REPRO_RECT_CODIM2
```
