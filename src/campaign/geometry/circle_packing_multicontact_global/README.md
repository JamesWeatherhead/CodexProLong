# Circle packing: codimension-three topology screen

This packet tests a genuinely new local topology family for the 26-circle
unit-square problem.  It does **not** repeat the frozen codimension-two search:
three active contacts are opened simultaneously, the resulting 3-D
linearized flex polytope is intersected by a deterministic floating-point
half-space algorithm, and only
non-box vertices at which three inactive contacts become tight are converted
to nonlinear contact systems.

The unchanged frozen verifier has SHA-256
`2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab`.
The strict live gate is `> 2.635983095360844`.

## Result

No gate-clearer was found.

- 3,500 release triples screened across the canonical and neutral edge-flip
  basins
- 2,848 genuine codimension-three replacement graphs solved
- 2,541 exact-verifier accepted labeled roots
- 2,531 is the sum of per-run unlabeled WL-class counts (not a claim of global
  uniqueness across seeds)
- best changed graph: `2.629728811166304`
- best changed graph's gate gap: `-0.006254284194540105`
- strict physical counterpart of that graph: `2.6297288007960344`

The canonical low-KKT slice was especially restrictive: all 500 flex
polytopes had only vertices on lower-coordinate boundaries, so none qualified
as a genuine codimension-three pivot.  A deterministic whole-spectrum sample
was therefore used for both basins.

The best unchanged incumbent remains `2.635983095281623`, only
`7.922107414515267e-11` below the gate, but that value is a fixed-graph
verifier-tolerance ceiling already covered by the precision campaign.  It is
not a result of this topology screen.

## Reproduction

From the EinsteinArena workspace root:

```bash
python3 campaign/geometry/circle_packing_multicontact_global/test_public_replay.py
python3 campaign/geometry/circle_packing_multicontact_global/replay_public.py
python3 campaign/geometry/circle_packing_multicontact_global/verify_publication.py
```

All commands and receipt/artifact references are repository-relative.
`receipt_v2.json` independently hashes each frozen config/event/summary stream
and states the finite search scope.  `replay_public.py` verifies the compact
best-changed payloads through a self-contained clean-room formula.  The exact
MIT-licensed verifier bytes are base64-wrapped solely so their SHA-256 can be
confirmed in memory; they are never written as Python, imported, compiled, or
executed.  `verify_publication.py` copies only the manifest allowlist into a
temporary repository tree and reruns both public tests and replay there.

## Why this route

Packing literature explicitly describes moving between local minima using
active inequalities and Newton-type methods, alongside basin hopping and
action-space diversification [1].  The AlphaEvolve problem statement matches
the Arena objective—maximizing the sum of radii of disjoint disks in the unit
square—and reports that later-digit gains remain a numerical-refinement target
[2].  Here those ideas motivated a contact-graph mutation beyond all prior
one- and two-contact neighborhoods; they do not imply a global-optimality
claim.

--------
REFERENCES

[1] Kun He, Mohammed Dosh, Shenghao Zou. "Packing Unequal Circles into a Square
    Container by Partitioning Narrow Action Spaces and Circle Items." *arXiv*
    (2016).
    https://paperclip.gxl.ai/citations/papers/arx_1701.00541#L19,L22,L47,L84-L97,L123-L126

[2] Bogdan Georgiev, Javier Gómez-Serrano, Terence Tao, Adam Zsolt Wagner.
    "Mathematical exploration and discovery at scale." *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L513-L516
