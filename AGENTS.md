# Public campaign memory

This repository is the public, secret-scrubbed memory layer for the local
EinsteinArena campaign.

- Read `README.md`, `docs/STATUS.md`, and `docs/OPEN_LAB_NOTEBOOK.md` before
  changing a benchmark lane.
- Refresh from the canonical local campaign with `python tools/snapshot_campaign.py`.
- Run `python tools/secret_scan.py .` before every commit or push.
- Publish verifier inputs, outputs, hashes, bounded negative results, and
  concise decision records. Never publish credentials, auth/session state,
  private prompts, hidden chain-of-thought, or third-party source trees.
- Label verifier/domain mismatches as disclosures, never as mathematical wins.
- Update the public checkpoint after each evaluated submission, material
  frontier improvement, or context handoff.

