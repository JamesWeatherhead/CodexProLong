# Handoff: Heilbronn n=11 distant-contact homotopy

Status: frozen bounded no-go; no candidate, verifier run, submission, discussion
post, issue, pull request, or GitHub write.

## Outcome

The strict gate remains
`> 0.036529890880030155`. This lane found no domain-valid gate-clearer.

The direct run exhausts all `17 * 107 = 1,819` labelled one-for-one exchanges
between an incumbent active triangle and an inactive triangle outside the
already reported top-58 low-area pool. It preserves the other 16 active
triangles and all six incumbent boundary contacts while tracking

```text
(1-t) (signed_det_out - z) - t (signed_det_in - z) = 0,
```

from `t=0` to `t=1`. Barycentric coordinates make each normalized area exactly
an integer-coefficient quadratic determinant.

- 1,171 direct paths reached `t=1`; 648 hit a numerical fold/singular tangent.
- 73 direct endpoints were finite, separated, and inside the unit triangle.
- Their best true minimum area was only `0.007736471515783469`, even though its
  exchanged equality level was `0.027084299401141945`. Other triangle
  inequalities therefore cut it off strongly.
- All 72 coordinate-distinct in-domain endpoints polished successfully under
  all 165 triangle inequalities and all 33 barycentric domain inequalities.
- Twelve returned to the incumbent basin. The strongest clean-room polished
  value was `0.036529889880029975`, below the public float64 incumbent; the
  next distinct high basin was `0.03408442492012185`.
- Zero direct endpoint or polish cleared the gate.

The pseudo-arclength recovery then traced every one of the 648 failed direct
paths under fixed finite caps.

- 547 paths crossed at least one fold; 7,249 tangent-sign folds were recorded.
- 29 more paths reached `t=1`, but none had an in-triangle endpoint.
- 384 reached the 1,000-step arclength cap, 233 reached `|t|=5`, and two reached
  the adaptive step floor.
- The largest algebraic endpoint score (`0.1585461569537974`) had minimum
  barycentric domain slack `-14.86511327209002`; it is not a construction.

Together, the two searches reached 1,200 endpoint roots, tested the bounded
real branch on all 1,819 exchanges, and left 619 paths unresolved past the
explicit pseudo-arclength caps. This is not a complete real-root enumeration,
a complex-path enumeration, or a global Heilbronn upper bound.

## Independent replay

`replay.py` does not import the search formula or Arena verifier. It
independently recomputes determinant scores, domain slacks, and pair separation
from every stored endpoint and polish, authenticates every frozen hash, and
replays the final gate decision.

```bash
../../../.venv/bin/python replay.py \
  runs/20260815T111000Z-distant-exchange-v2
../../../.venv/bin/python replay.py \
  runs/20260815T111000Z-pseudo-v1
```

The first replay checked 1,171 endpoints and 72 polishes; the second checked
29 endpoints. Maximum independent score delta was exactly zero and maximum
domain-slack delta was `2.220446049250313e-16` in both runs.

The best payload retained by both runs is the known incumbent, not a new
candidate. Its clean-room operation order gives `0.03652988988003019`; the
unchanged Arena score is `0.036529889880030156`, and the 100-digit active root
from the earlier lane is still only
`0.036529889880030216424847127961580112...`. All are roughly `1e-9` short of
the gate. Because no new legal candidate cleared the clean-room gate, this lane
did not call `./campaign/arena verify`.

## Distinctness and corpus scope

Before the run, the exhaustive retained corpus was read in full: 17 solutions,
four threads, and all 23 replies for `heilbronn-triangles`, from FTS5 database
SHA-256
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.
All earlier Heilbronn handoffs were also read.

This lane deliberately does not repeat:

- q=143 cells or q=144--220 exact rational-mesh cases;
- the corrected 23-template/depth-4,5,6,8,11 FlowBoost packet;
- 2.47 million depth-1--3 point-replacement starts;
- incumbent precision polishing, tolerance harvesting, or the top-58
  low-area active-system pool.

The first attempted full run stopped after 377 durable rows when a singular
path raised an unhandled numerical exception. It is preserved under
`runs/20260815T110500Z-distant-exchange/` but is superseded and excluded from
all counts and the receipt. `runs/SMOKE/` and `runs/PSEUDO_SMOKE/` are also
excluded.

## Literature and asset audit

AlphaEvolve generated points, projected any outside points back into the
bounding triangle, and reported the improved `n=11` construction; its authors
explicitly identify customized numerics and hybrid follow-up as plausible
routes [1]. The 2025 global-optimization paper reaches certification only at
smaller sizes and specifically points to orientation-count restrictions as a
route toward `n=11` [2]. Affine parameter homotopy with predictor/corrector and
Krawczyk conditions supplies the relevant certification framework [3].

Exa request IDs `d959921f245b9830156a81d01c4d8c5a` and
`e244789be402a5eafc3165f4de96cf8d` found no new public `n=11` coordinate asset.
The July 2026 unit-triangle certification reaches only `n <= 8`; the MIT
`spiralulam/heilbronn` data set is for the unit square. No Exa response bodies,
third-party source trees, or candidate arrays are retained here.

## Next route

Do not rerun these real one-swap paths with larger local-optimizer budgets. The
next mathematically distinct route is a complex `gamma`-homotopy/monodromy
enumeration of all isolated roots for the 619 capped target systems, followed
by real/domain filtering and interval Krawczyk certification. If that tooling
is unavailable, pivot to proof-producing MIQCP/interval branch-and-bound in
barycentric coordinates with orientation-count constraints; this attacks
whole sign/topology chambers rather than another incumbent perturbation.

## Publication boundary

Publish only `PUBLICATION_MANIFEST.json`'s allowlist. Raw `runs/` contain
coordinate arrays and detailed numerical traces and remain excluded. The
compact `receipt.json` retains exact counts, extrema, and hashes. Run
`python3 -I src/campaign/geometry/heilbronn_contact_homotopy_interval/public_replay.py`
from a public repository root to authenticate the allowlist and all receipt
arithmetic without opening the raw run tree. Full numerical reproduction needs
Python 3.11+, the pinned requirements, and an explicit published seed path;
see `README.md`. The repository-level MIT license covers this packet.

--------
REFERENCES

[1] B. Georgiev, J. Gómez-Serrano, T. Tao, and A. Z. Wagner. “Mathematical
exploration and discovery at scale.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L59-L60,L624-L631

[2] A. Monji, A. Modir, and B. Kocuk. “Solving the Heilbronn Triangle Problem
using Global Optimization Methods.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L233-L238

[3] K. Lee. “A priori bounds for certified Krawczyk homotopy tracking.”
*arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2512.01355#L5-L10,L42-L49,L61-L69
