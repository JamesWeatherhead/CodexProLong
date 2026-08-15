# Difference-bases interval-construction lane

This isolated, GET-only lane tests a classical global construction that is not
an incumbent point swap or a shell-0..7 CP-SAT variant.  It implements the
Rédei--Rényi/Leech--Golay product as formalized by Banakh and Gavrylkiv,
Theorem 4.7: combine the interval basis `{0,1,4,6}` with a planar cyclic Singer
difference set, then choose the best integer cut of the cyclic set.

`search.py` constructs each Singer set from finite-field arithmetic, verifies
the planar difference property, exhausts every unit multiplier and cyclic cut,
builds the corresponding integer basis, and applies a clean-room copy of the
literal Arena score formula.  It never imports or executes downloaded code.

Run from the EinsteinArena repository root:

```bash
.venv/bin/python -B \
  campaign/discrete/difference_interval_constructions/search.py \
  --q 59-199
```

The checkpoint is replaced atomically after every completed prime.  No Arena,
GitHub, discussion, voting, or submission write is performed.

`tail_sweep.py` separately exhausts the positive-`k` form of Theorem 4.7:
for every affine Singer representative it adds the prescribed copy of each
early cyclic residue and exact-replays the resulting larger integer basis.

`prime_power_sweep.py` implements deterministic tower-field arithmetic and
completes the same `k=0` affine sweep for every non-prime prime power
`q <= 499`; together with `search.py`, this reaches the schema ceiling for the
four-block Singer family.

Freeze and independently replay the retained frontier with:

```bash
.venv/bin/python -B \
  campaign/discrete/difference_interval_constructions/freeze_receipt.py
.venv/bin/python -B \
  campaign/discrete/difference_interval_constructions/replay.py
```

The final quantified result and scope limitations are in `HANDOFF.md`.
`PUBLICATION_MANIFEST.json` records the conservative public include/exclude
inventory, per-file hashes, dependency provenance, and licensing notes.
