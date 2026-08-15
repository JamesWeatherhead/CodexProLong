# PSL-4 table recovery

Frozen GET-only archival recovery for the 72 non-equivalent length-70 binary
PSL-4 classes reported by Leukhin and Potekhin. The complete table was not
recovered and no candidate clears the current Flat Polynomials gate.

Start with `HANDOFF.md`. Source files and their exact hashes are pinned in
`source_manifest.json`; the quantified archive search is in
`archive_audit.json`.

Reproduce the bounded neighbor screen and literal verifier replays:

```bash
cd /path/to/EinsteinArena
.venv/bin/python campaign/flat_psl4_recovery/build_source_manifest.py
.venv/bin/python campaign/flat_psl4_recovery/screen_printed_neighbours.py \
  --grid 32768 --exact-top 64 \
  --out campaign/flat_psl4_recovery/printed_neighbour_screen.json
.venv/bin/python campaign/flat_psl4_recovery/exact_replay.py \
  campaign/flat_psl4_recovery/payloads/best_printed_neighbor_n71_delete70.json
```

No program here posts to EinsteinArena or GitHub, contacts authors, purchases
documents, or otherwise mutates external state.
