# Flat-polynomials changed-shape campaign

Pinned to the live 70-coefficient leader and verifier.  The earlier exhaustive
Hamming-radius-five search remains in `../flat_search.py`.

```sh
cd /Users/jacweath/EinsteinArena
.venv/bin/python campaign/discrete/flat_polynomials/structured_search.py --restart
.venv/bin/python campaign/discrete/flat_polynomials/radius6_exhaustive.py --restart --workers 4
```

The structured search covers run-boundary segments, paired run moves,
near-leader crossovers, cyclotomic residue masks, arithmetic lag chains,
correlation-sign masks, and meet-in-the-middle radius-six cancellations.  Its
screen uses only literal points from the verifier's million-point grid, so a
screened maximum is a rigorous lower bound.  Only candidates below the live
gate on that subset receive an unmodified full verifier replay.

`radius6_exhaustive.py` closes every one of the 131,115,985 Hamming-radius-six
masks.  It compiles the bounded C++ enumerator, checkpoints after each possible
first flipped index, and sends only literal-grid survivors to the pinned live
verifier for a full one-million-point replay.

The completed run found zero radius-six literal-grid survivors.  The structured
run's only three survivors were the two alternating-coefficient symmetry images
(`1.2807274938193687`) and the older public leader (`1.2809320527987995`), all
above the strict gate `1.280726494964255`.  `best_screen_survivor.json` is a
non-gating diagnostic artifact, not a submission candidate.

All state is written atomically under `checkpoints/`; no code submits or posts
to EinsteinArena.
