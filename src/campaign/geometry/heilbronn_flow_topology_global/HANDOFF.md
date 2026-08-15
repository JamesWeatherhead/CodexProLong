# Handoff: continuous Heilbronn topology escape

Status: frozen bounded no-go; no external writes and no candidate submission.

## Distinct scope

- Continuous barycentric coordinates, not a rational mesh.
- All 23 feasible outer-edge/vertex contact templates modulo D3.
- Smooth-min stochastic relaxation, L-BFGS-B, and literal 165-constraint
  SLSQP replay.
- Point death/rebirth begins at depth four and reaches full-set depth eleven;
  this avoids duplicating the public 2,471,800-start depth-one-to-three lane.
- The snapshot has 17 public rows but 13 D3-distinct basins. The global branch
  selected eight public plus two generated-template parents; the continuation
  selected four public parents.
- Every retained candidate is compared against all 17 public rows using true
  squared-cost Hungarian RMS modulo D3, then evaluated twice by verifier
  `6afecf9539c4e9038cd6188e4e77efec00c9905b688728ad58f69dbfedc2441d`.

## Quantified frontier

`runs/global-20260815T100000Z-v2` completed 23 template islands and the first
depth-4/5/6/8/11 continuation. It annealed 1,504 population members, polished
238 serialized candidates, and produced no score above `0.035`. Its strongest
distinct basin is `0.034498013012460894`, D3-RMS distance
`0.041687179668865516` from the nearest public row. This is negative evidence,
not a global theorem.

`runs/continuation-20260815T103000Z-v2` then held the un-reborn points fixed for
65% of each anneal and tested 5,120 additional population members from four
strong public basins. It polished 160 candidates. Its best distinct result was
`0.03316028976182035`; no score reached `0.035`.

Together the two runs annealed 6,624 members and independently replayed 398
serialized candidates. The best score is `0.034498013012460894`, a shortfall
of `0.002031877867569261` from the strict gate
`>0.036529890880030155`. Every retained candidate is D3-RMS-distinct from the
17 public rows at threshold `1e-4`; the minimum true RMS is
`0.04054608891852764`. This freezes the explicit 23-template and
depth-4/5/6/8/11 FlowBoost-style family only; it is not a continuous global
optimality certificate.

The squared-cost correction changed nearest-ID/distance metadata for 11 global
and 2 continuation records. It changed no coordinates, payload hashes, or
verifier scores; the new result-file hashes and both before/after pins are in
the compact receipt.

The freeze audit loaded two copies of the unchanged verifier for every run and
also recomputed all 165 triangle areas per candidate without solver/verifier
geometry helpers. All 398 payload hashes and scores matched; the largest
independent-formula difference was `9.71445146547012e-17`.

## Corrected boundary-map audit

The first two runs without the `-v2` suffix are superseded and excluded. Their
public-parent continuation inferred boundary slacks in `C/B/A` order but fed
them to a zero-barycentric parameterization in `A/B/C` order. The corrected
map is the explicit permutation `(2, 1, 0)`, regression-tested by reconstructing
the live leader and recovering its exact `2/2/2` side-contact pattern.

The private bug audit potentially affected 5,440 of 6,624 annealed members and 240 of 398
polished records: precisely the public-parent death/rebirth branch. The 1,184
other members and 158 records were outside that branch; all 138 initial
template-phase payload hashes and scores agree before and after the fix.
The discarded frontier was `0.03315805897708453`; the corrected frontier is
`0.034498013012460894`, an increase of `0.0013399540353763659`. This comparison
quantifies impact only; none of the superseded records enter the receipt. The
underlying v1 payloads are excluded, so the receipt labels these counts and the
before/after comparison as private and not publicly replayable.

Canonical compact receipt and source allowlist:

- `publication/receipt.json`
- `PUBLICATION_MANIFEST.json`

## Publication boundary

Include only the files enumerated by `PUBLICATION_MANIFEST.json`. Exclude all
raw run directories: they contain generated candidate arrays and verbose event
logs. No third-party candidate bytes, API credentials, Arena writes, GitHub
writes, issues, comments, discussion posts, or submissions belong to this lane.

The public layout is
`src/campaign/geometry/heilbronn_flow_topology_global/`. Its standard-library
`public_replay.py` authenticates the copied allowlist without a campaign
snapshot, corpus, raw run, NumPy/SciPy/Torch, or verifier execution. The private
full search/audit requires Python `>=3.11` and `requirements.txt`. Regenerate
the receipt first and run `freeze_publication.py` last.
