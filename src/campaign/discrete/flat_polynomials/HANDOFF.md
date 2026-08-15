# Flat-polynomials handoff

This lane is frozen with no gate-clearing candidate.

## Pinned frontier

- Live snapshot: `../checkpoints/flat-polynomials-live.json`
- Leader: solution `2475`, score `1.2807274949642549`
- Required strict gate: `< 1.280726494964255`
- Verifier SHA-256:
  `ff991bd84aec2b5b5d44f58a68dba00f961e01d517ec1de3225e0902f0f2fce2`
- Leader canonical-payload SHA-256:
  `4cfa023b9e86e1a77af92fe17942efd2d6a9cfc2210ebb57bd376cdcf2f974d0`

## Closed regions

The prior `../flat_search.py` run exhaustively screened every Hamming-radius
one through five mask, 13,077,134 candidates total, with zero literal-grid
survivors.

`structured_search.py` screened 422,983 unique changed-shape masks.  The
families comprise every contiguous run-boundary segment, every XOR of two such
segments, old/new-leader crossovers over both families, every nontrivial union
of residue classes modulo 2 through 13, every length-at-least-six arithmetic
lag-chain segment for lags 2 through 23, all correlation-sign endpoint masks,
and a peak-cancellation meet-in-the-middle radius-six family.

Only three structured masks survived the literal subset.  Full pinned-verifier
replay returned `1.2807274938193687` for each of the two alternating-sign
symmetry images and `1.2809320527987995` for the old public leader.  None clears
the gate.

`radius6_exhaustive.py` then enumerated all `C(70,6) = 131,115,985` masks.  Its
994-point screen consists exclusively of literal verifier roots: 512 coarse
points plus neighborhoods of the incumbent peak and conjugate, offsets
`-6000..6000` in steps of 50.  A conservative `1e-10` raw-magnitude margin is
included before rejecting.  It found zero survivors, completing the exhaustive
radius-six closure.  The closest first-point rejection certificate recorded was
`1.2807264953375146`, still above the gate; independent NumPy evaluation of
that mask on the full 994-point subset was `1.8490269207505645`.

## Reproduction

```sh
cd /Users/jacweath/EinsteinArena
.venv/bin/python campaign/discrete/flat_polynomials/structured_search.py --restart
.venv/bin/python campaign/discrete/flat_polynomials/radius6_exhaustive.py --restart --workers 4
```

Primary receipts are `checkpoints/structured_search.json` and
`checkpoints/radius6_exhaustive.json`.  The full-radius run completed in about
40 seconds on four local workers.  No tool in this directory submits, posts, or
otherwise writes to EinsteinArena.
