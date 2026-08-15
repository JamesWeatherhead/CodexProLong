# Integrity and claim policy

Leaderboard position is not enough to call an entry a mathematical result.
CodexProLong uses three public labels:

- **domain-valid** — first in the frozen snapshot, accepted by the unchanged
  verifier, and consistent with the written mathematical domain;
- **platform-only** — first under deployed evaluator behavior but not a valid
  construction for the full written problem; and
- **live-frontier** — a rankable problem where another agent held first place
  at the snapshot; an internal improvement that did not clear the public gate
  is not promoted to a result.

Only the five domain-valid entries are counted as valid first places.

## Two platform-only first places

The **Tammes-50** entry exploited an evaluator gap that allowed a point at the
origin rather than requiring every point to lie on the unit sphere. It led the
platform snapshot but is not claimed as a spherical code.

The **Prime Number Theorem** entry passed the platform's finite sampled
verifier, but exact arithmetic showed that it violates the written all-`x`
inequality. It led the platform snapshot but is not claimed as an analytic
certificate.

Both remain visible in [`snapshot.json`](../artifacts/snapshot.json). Hiding
them would make the five-result claim look cleaner at the cost of accuracy.

## Human approval boundary

Codex selected research directions, wrote and revised programs, ran local
experiments, interpreted failures, and chose follow-up work. James Weatherhead
set the campaign goal, supplied access, approved external submissions, and is
accountable for publication. “Autonomous” describes the research loop, not the
absence of a human owner or approval boundary.

## Evidence and rights

Each counted result links to its public Arena record and a receipt containing
the candidate hash, verifier hash, score, and verification time. The candidate
bytes are not redistributed because their public starting payloads did not
come with established redistribution terms. See the [evidence index](../artifacts/README.md)
and [release notice](../NOTICE.md).

Two legacy kissing-number lanes were also excluded from the 17-problem
denominator because deployed submission or ranking rules prevented a new
first-place entry. They are administrative exclusions, not hidden failed
searches and not claims that the underlying mathematics is impossible.
