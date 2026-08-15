# Next discrete lane: adaptive q=143 mesh

Among denominators up to 500, q=143 is the first especially favorable exact
gate approximation:

```text
ceil(0.036529890880030155 * 143^2) = 747
747 / 143^2 = 0.03652990366277079563792850506
overshoot = 1.2782740640637929e-8
```

This is roughly 10,700 times closer to the live gate than q=30's
`33/900`.  A uniform q=143 grid has 10,440 points and is not a reasonable
global hypergraph instance, so the next construction family should be an
adaptive exact mesh.

## Proposed family

1. Convert every public distinct basin to barycentric coordinates and round
   each labeled point to q=143.
2. Give each point an initial hexagonal integer window of L1 radius 2.  Include
   exact boundary candidates and all D3 images; do not fix the incumbent active
   triples.
3. Enumerate forbidden labeled triples with exact numerator `<747`.  Solve the
   resulting one-of-window constraint problem with branch-and-cut.
4. For any failed label/triple core, expand only the implicated point windows
   to radii 3, 5, then 8.  Keep all other windows frozen.  This is the
   nonuniform refinement step.
5. After every feasible discrete leaf, run the unchanged exact determinant
   check, convert to Cartesian coordinates, and use Docker `./arena verify`
   before any consideration of submission.

To allow topology changes rather than merely rounding the incumbent, add a
second pool for one or two released labels: q=143 representatives of the
q=30 cells adjacent to the active forbidden-triple core.  Branch on which
labels are released and cap each run independently.

## Hard initial budget

- 17 public/distinct seeds, 3 D3-canonical orientations each.
- Radius schedule `2,3,5,8`; stop a seed after two unchanged unsat cores.
- At most 50,000 branch nodes or 120 seconds per seed/radius.
- Release depth at most two labels in the first campaign.
- Atomic checkpoint after every seed/radius and every feasible leaf.

This family targets the quantization bottleneck exposed by q=25/q=30 while
remaining an exact intended-domain construction search.  It is not a license
to exploit verifier tolerances.

## Completed initial campaign — 2026-08-15

The hard-budget campaign above completed against all 17 public solutions,
which collapse to ten distinct integer center sets after q=143 rounding,
label sorting, and D3 canonicalization.  It produced no feasible leaf.

- Canonical summary:
  `runs/20260815T031000Z/heilbronn-triangles/summary.json`.
- Summary SHA-256:
  `7cc482375bcd6f55401ef9b13372dafe6d64df1ced9c399f9451a7042d8f7655`.
- Search implementation: `adaptive_q143_sat.py`.
- Implementation SHA-256:
  `855e4c6775bf84515272edb5271642be2bfbcbe0a1a9bd718201ca683ba3383c`.
- Exact threshold: determinant numerator at least `747`, or
  `747/143^2 = 0.0365299036627708`.
- Solver: CaDiCaL 1.5.3 through `python-sat==1.9.dev14`.
- Exact stages: 28 total; 24 UNSAT and four unresolved at the fixed
  50,000-conflict limit.
- Work audited: 24,078,131 CNF clauses, 72,460,844 candidate triple
  combinations, 23,878,428 forbidden combinations, and 287,546 SAT
  conflicts.
- Timed work: 81.054 seconds of exact clause construction and 64.860 seconds
  of SAT solving on the campaign host.

All ten radius-2 windows are exactly UNSAT.  Core-directed expansion also
proves every tested radius-3/mixed-radius stage UNSAT.  For the four strongest
public basins, the next core expansion creates 3,186,766--3,762,438-clause
instances and reaches the 50,000-conflict cap without a model or proof.  Two
weaker basins continue to exact mixed-radius-8 UNSAT certificates.  Four
others stop after two unchanged UNSAT cores, exactly as prescribed by the
initial budget.

This is a bounded adaptive-window certificate, not a global q=143 closure and
not a continuous Heilbronn upper bound.  In particular, the four capped
radius-5 instances remain logically unresolved.  No candidate payload was
written, so there was nothing to replay through Docker and no external action
was taken.

Reproduce from the campaign root:

```bash
PYTHONPATH=geometry/heilbronn_bnb \
  ../.venv/bin/python geometry/heilbronn_bnb/adaptive_q143_sat.py \
  --max-seeds 10 --max-stages 4 --stage-seconds 120 \
  --conflict-budget 50000 --clause-limit 8000000 \
  --stamp REPRO_Q143
```

An interrupted run resumes atomically with `--resume RUN_DIRECTORY`.
