# Provenance

## Frozen local inputs

- live verifier SHA-256:
  `2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab`
- canonical seed SHA-256:
  `6d3b5fc5c1bec58361b1ae2bdacbd2bbc312e71f3051f02e09df117938a05302`
- neutral seed is the frozen best payload from
  `circle_packing_multicontact_precision/runs/20260815T_CODIM2_NEUTRAL_FULL/`;
  its exact hash is recorded in each V2 run config and `receipt_v2.json`.

The private search implementation imports only the existing clean-room
verifier formula and local contact-equation machinery.  The public replay is
self-contained: `public_verifier_formula.py` base64-decodes the exact frozen
verifier bytes in memory only to confirm SHA-256, then evaluates candidates
with its own direct formula transcription.  Decoded bytes are never written,
imported, compiled, evaluated, or executed.

## Literature

Paperclip reads were GET-only:

- `/papers/arx_1701.00541/content.lines`: lines 19, 22, 47, 84–97, 123–126
- `/papers/arx_2511.02864/content.lines`: lines 513–516

The first paper supplies prior active-inequality/Newton, quasi-Newton,
basin-hopping, and action-space context.  The second supplies the exact
unit-square sum-of-radii problem definition and numerical-refinement context.
Neither paper supplies the candidate arrays produced here.

## Generated data

The compact payloads in `artifacts/` were generated locally from nonlinear
roots of new 78-contact systems.  They are not third-party assets.  Raw runs
are append-only JSONL plus atomic checkpoints; `freeze_receipt.py` pins their
byte hashes and copies only the best changed payload per productive run into
the compact artifact set.  Raw runs and that private freeze helper are excluded
from the minimal public allowlist; `receipt_v2.json` preserves their hashes and
the public replay independently verifies the published payloads.
