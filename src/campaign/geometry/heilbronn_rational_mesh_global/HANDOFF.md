# Handoff: rational-mesh global escape

Status: frozen exact finite-domain no-go; no gate-clearer and no external writes.

## Quantified frontier

- Screened all 77 denominators `q=144..220` using exact Decimal arithmetic.
- Best four exact gate thresholds: `q156:889`, `q152:844`, `q174:1106`,
  `q210:1611`; their threshold overshoots are respectively `3.52381e-7`,
  `5.80034e-7`, `6.94402e-7`, and `7.21365e-7`.
- `PUBLIC_V2`: 34 distinct D3-reduced public radius-2 domains; 18 exact
  product-domain obstructions and 16 exact UNSAT formulas.
- `TOPOLOGY_V2`: 41 enumerated topology cases / 38 distinct domains; all 41
  exact UNSAT.  Families are constrained boundary births from the three-boundary
  basin, all one/two boundary deaths from the six-boundary leader, and
  disconnected cross-basin unions at q156/q174.
- Fresh replay: all 75 records reconstructed, all hashes matched, 57 uncapped
  formulas UNSAT (164,140 clauses; 5,530 conflicts), no candidate.
- Frozen-verifier coordinate conversion independently matched exact rational
  scores at all four selected denominators within `2.1e-17`.

Exact scope is only the 72 distinct finite labeled domains.  This does not close
the full rational meshes or continuous problem, and there is no DRAT/LRAT trace.

## Publish-safe include

- `.gitignore`
- `README.md`
- `HANDOFF.md`
- `literature_sources.json`
- `screen_denominators.py`
- `denominator_screen.json`
- `rational_mesh_search.py`
- `freeze_manifest.py`
- `case_manifest.json`
- `replay_no_go.py`
- `replay_receipt.json`

## Exclude

- `runs/` (all raw runs; the compact manifest is sufficient for replay)
- `/tmp/heilbronn_public_v2.log`
- `/tmp/heilbronn_mesh_replay.log`
- `/tmp/heilbronn_mesh_replay_v2.log`

No credential material or third-party payload arrays are present.
