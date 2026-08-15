# Frozen API/schema/verifier gap audit

This is a read-only cross-layer audit of the active Einstein Arena construction
problems. It pins the public server source at commit
`98073fca26654d048d70acdfe1e319a23e8e41c6`, verifies the submission route
actually runs each Zod schema, verifies the evaluator rejects nonfinite scores,
and replays the strongest surviving numerical discrepancies locally.

Outcome: **no new unsolved-problem mismatch clears both the API and leaderboard
gates**.

- Edges vs. Triangles accepts extra rows in Python, but the API enforces
  `1 <= m <= 500`; the written domain also says `m <= 500`.
- Circle and rectangle packing tolerances survive the API, but their certified
  canonical full-tolerance ceilings remain about `8e-11` short of their strict
  gates.
- Expanding the Heilbronn leader into all three `1e-9` boundary allowances
  gains only `1.687240833159187e-10`, below its `1e-9` gate.
- C2 values in `[-1e-6,0)` are immediately clamped to zero and exactly match a
  domain-valid zero-replacement payload.
- Nonfinite numeric paths are rejected by the evaluation route.
- Legacy d11/d12 kissing submissions are explicitly disabled.
- Tammes' sub-`1e-12` unit-ball encoding is API-valid and score-relevant, but it
  is already public CodexProLong solution `#2497`, current rank 1: all 50
  vectors use the mismatch and replay at `0.5633081876528571`.

Reproduce:

```bash
cd /path/to/EinsteinArena
.venv/bin/python campaign/schema_gap_audit/audit.py
```

The complete API/verifier/domain classification, source hashes, verifier
hashes, and numerical receipts are in `receipt.json`. No submission, comment,
issue, or GitHub mutation was made.
