# Difference-global frozen handoff

Frozen at 2026-08-15T04:05Z. No Arena or GitHub mutation occurred.

## Decision

Do not submit either candidate. The exact live gate remains
`2.6390274685066077`. The raw topology frontier scores
`150544/2405 = 62.596257796257795`; the 24-birth patched frontier scores
`115600/4077 = 28.3541819965661`. Both are verifier-valid but far worse than
the incumbent.

The decisive quantitative failure is integer carry order:

- raw p=97 frontier: 2,405 coverage versus 57,046 required (gap 54,641);
- best size-normalized p=79 seed: 2,351 versus 37,839 (gap 35,488);
- p=79 seed after 24 exact births: 4,077 versus 43,805 (gap 39,728).

The negative result is bounded, not universal. A future reopening must change
the integer embedding/carry topology itself—for example, a provable terrace or
ordering that coordinates adjacent cell carries. More random GL matrices or a
deeper first-gap patch is not supported by this frontier.

## Frozen receipts

- Live verifier SHA-256:
  `a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`
- Incumbent payload SHA-256:
  `02b16426d5a66feb480d79c7e1c7c26bb18ffb50730c5a2c76861584ec59183b`
- Raw relative-graph payload SHA-256:
  `ebbc8fb5fea1332dc8a4a67a0cf1aaed6d2e21f9f42602034a33e5e898f513c8`
- Size-normalized p=79 seed payload SHA-256:
  `8d97a646a20bebd030aed172d6c7226ed531a204fff782601ede964db472099f`
- Patched payload SHA-256:
  `5c26fa610cf0ee469ec731f5969aaf40cf65d2ddf314aa32f413b258d2c736cb`
- Complete relative search checkpoint SHA-256:
  `6d7c73477d249b37a5adacd83c0a3c132262beb415661f81af8863b92687db64`
- Complete sparse-patch checkpoint SHA-256:
  `4cfe9b6f8c3504842f7c6ece3607c1086bd5ef2785919628197129e08f73f4d1`
- Complete public snapshot SHA-256:
  `6159d144ae3c57dc740cd4fd5b54e1a467589c44b355dcef98ceb4b0bc6d0d69`

## Publish-safe inclusion list

- `README.md`
- `HANDOFF.md`
- `PROVENANCE.md`
- `exact.py`
- `relative_graph_search.py`
- `sparse_patch_search.py`
- `refresh_public.py`
- `test_exact.py`
- `freeze_receipt.py`
- `checkpoints/relative_graph.json`
- `checkpoints/sparse_patch.json`
- `candidates/relative_graph_best.json`
- `candidates/sparse_patch_best.json`
- `checkpoints/audit_receipt.json` (after generation)

Keep these local/private unless Einstein Arena's API-content license is
clarified:

- `checkpoints/public_latest.json`
- `snapshots/public_20260815T040127Z.json`

The source files are original campaign code. Literature licenses and the Exa
fallback are recorded in `PROVENANCE.md`.
