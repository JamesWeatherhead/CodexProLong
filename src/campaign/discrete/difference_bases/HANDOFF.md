# Difference Bases handoff

Pinned live state: leader #634, score `2.639027469506608`, 360 points,
coverage 49,109, verifier SHA-256
`a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`.

Closed neighborhoods:

- Existing one-edit search: all 360 deletions, 156,165 deficit-capable swaps,
  and 435 target-capable additions.
- Exact two-remove/two-add search: all 64,620 removal pairs.  The
  new-to-old branch screened 28,109,700 triples and exactly enumerated the four
  optimistic survivors; the new-to-new branch screened 264,569 forced
  placements.  No candidate covers 49,110.
- Translated-block bitset repair: 236,326 bounded global one-block
  replacements, 3,006,003 radius-500 two-offset placements, and 1,030,301
  radius-50 three-offset placements.  Best coverage remains 49,109.

Reproduction:

```sh
cd /Users/jacweath/EinsteinArena
.venv/bin/python campaign/discrete/difference_bases/two_swap.py
.venv/bin/python campaign/discrete/difference_bases/block_repair.py
```

No candidate was submitted or posted externally.
