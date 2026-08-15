# Difference Bases changed-shape search

This directory extends the exhausted one-edit search with larger, independently
checkable neighborhoods around live leader #634.  It is read-only with respect
to EinsteinArena.

```sh
cd /Users/jacweath/EinsteinArena
.venv/bin/python campaign/discrete/difference_bases/two_swap.py
.venv/bin/python campaign/discrete/difference_bases/block_repair.py
```

`two_swap.py` exhausts every exact two-remove/two-add route capable of covering
the incumbent's first missing difference.  It splits the proof into
new-to-old and new-to-new representations, uses only optimistic pruning, and
atomically checkpoints both branches.  Therefore a zero result excludes the
entire same-cardinality two-swap neighborhood, not just a chosen coordinate
radius.

`block_repair.py` recognizes the incumbent as four translates of one 90-point
block and evaluates repairs with exact integer bitsets.  It exhausts every
relevant one-block replacement, every two-offset perturbation in radius 500,
and the full three-offset cube in radius 50.  Overlapping block ranges are
handled by cached absolute-difference patterns rather than an unsafe shift
shortcut.
