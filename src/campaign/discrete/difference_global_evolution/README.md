# Difference Bases: global changed-core evolution

This packet records a bounded, exact, negative frontier for the live
`difference-bases` problem. It does **not** claim global impossibility.

The frozen public leader has 360 marks, covers `1..49,109`, and scores
`129600/49109 = 2.639027469506608`. The strict live gate is
`2.6390274685066077`, so a 360-mark construction must cover at least
`1..49,110`.

The solver is deliberately different from the exhausted one-/two-swap,
four-block repair, shell, Singer-family, and quadratic-relative-set lanes. It
first enters a basin where difference `49,110` is explicitly represented,
then evolves arbitrary normalized 360-mark sets with:

- multi-mark ruin/recreate (`k = 3,4,6,8,12,16`);
- full-range target-preserving coordinate synthesis over every integer in
  `[1,65,000]` for sampled removals;
- gap transfers and segment scrambles;
- mark/gap crossovers with the public incumbent and a scaled Wichmann donor;
- exact Python-integer difference bitsets, adaptive operator weights, and a
  checkpointed NumPy RNG.

## Frozen result

The final deterministic run used seed `20260815` for 600 proposals:

| quantity | result |
|---|---:|
| accepted moves | 130 |
| exact full-coordinate calls | 104 |
| accepted full-coordinate moves | 83 |
| maximum accepted marks changed from leader | 5 |
| best target-covered missing count | 178 |
| best target-covered prefix | 33,087 |
| incumbent prefix | 49,109 |
| gate cleared | no |

All 27 retained arrays were independently replayed by `audit_run.py`; the
compact result is in `receipt.json`. The construction arrays and frozen Arena
snapshot are intentionally excluded from the publication allowlist.

## Public replay

From the public `CodexProLong` repository root, the standalone copied-allowlist
check is:

```bash
python3 src/campaign/discrete/difference_global_evolution/test_packet.py
```

It validates the public metadata and hashes without needing the excluded
construction arrays and runs on Python 3.9 or newer. The performance solver
and private deep audit use `int.bit_count()` plus NumPy and require Python 3.10
or newer; they are not invoked by the public standalone check.

## Canonical private replay

From the canonical research checkout root, with the private run checkpoint
present:

```bash
.venv/bin/python campaign/discrete/difference_global_evolution/audit_run.py \
  --run-dir campaign/discrete/difference_global_evolution/runs/20260815T091243Z_final600 \
  --solver campaign/discrete/difference_global_evolution/solver.py \
  --output /tmp/difference-global-evolution-receipt.json
```

The same standalone check in the canonical checkout is:

```bash
python3 campaign/discrete/difference_global_evolution/test_packet.py
```

See `HANDOFF.md` for scope and `PROVENANCE.md` for source-pinned literature.
