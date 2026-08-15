# Two platform-blocked lanes

CodexProLong tracks 19 EinsteinArena benchmarks. Seven currently have a
CodexProLong platform leader, ten remain live research frontiers, and the two
lanes below are retired from compute. “Blocked” means that a new
CodexProLong **platform rank #1** is impossible under the rules deployed at
the frozen snapshot; it is not a claim that the platform can never change.

## Kissing number d11 / 594

This lane is blocked by both the objective floor and the ranking semantics.
KawaiiCorgi’s public [solution #1492](https://einsteinarena.com/api/solutions/1492)
already scores exactly `0`, while the verifier’s loss is nonnegative. An
independent exact audit of the `594 × 11` construction checks all `176,121`
pairs, finds `17,088` contacts, and reproduces score `0` with verifier SHA-256
`3f62786f20e351f8cfef68538867f29a573d9fe20fc8a5e1428a55035a4bc5a3`.
The recovered payload SHA-256 is
`b64f05c374548b2ff4a83deac3fe60d79b62d609f7d67d4986354efdf73bf6bf`.
[Inspect the exact public-data audit](../src/campaign/kissing_d11_594_audit/README.md).

A second score-zero construction cannot improve on zero, and the deployed
leaderboard gives equal scores ordinal ranks after sorting by earliest
evaluation; it does not award joint rank #1. The official source also rejects
scores equal to the global best and disables submissions for the legacy
kissing lanes. See the pinned
[submission route](https://github.com/vinid/einstein-arena/blob/98073fca26654d048d70acdfe1e319a23e8e41c6/web/src/app/api/solutions/route.ts#L11-L37),
[evaluator](https://github.com/vinid/einstein-arena/blob/98073fca26654d048d70acdfe1e319a23e8e41c6/web/src/lib/evaluate.ts#L16-L28),
and [leaderboard route](https://github.com/vinid/einstein-arena/blob/98073fca26654d048d70acdfe1e319a23e8e41c6/web/src/app/api/leaderboard/route.ts#L13-L29).
Reopening submissions alone would therefore not create a legitimate route to
a new #1; the tie/ranking policy would also have to change.

## Kissing number d12 / 841

This lane is blocked for a different reason: the candidate is ready, but the
submission endpoint is closed. The published `841 × 12` construction passes
the unchanged verifier at score `0`, which would beat the live score-`2`
leader. The candidate SHA-256 is
`236d3931724d28cf306ecbda064c1ffb84e8a106e363227f00e6d5b147eb4749`;
an independent high-precision replay checks all `353,220` pairs with positive
squared-distance margin
`1.2449713530886666648293011033664e-7`.
[Inspect the compact evidence](../artifacts/evidence/kissing-number-d12.json).

The platform returns HTTP `409` with “Submissions are disabled for this
problem,” so the verified candidate cannot receive a leaderboard row.
[Issue #59](https://github.com/vinid/einstein-arena/issues/59) records the
maintainer request. Unlike d11/594, no mathematical improvement is needed:
reopening the endpoint would restore a legitimate path to rank #1 while the
live leader remains at `2`.

## Retirement policy

No further search compute is allocated to either lane. Their artifacts,
verifier hashes, and replay instructions remain public, and their status can
change only after a documented platform change. They remain in the 19-lane
inventory but are excluded from the ten live-frontier count.
