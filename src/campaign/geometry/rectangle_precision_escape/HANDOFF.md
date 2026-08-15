# Rectangle precision/lattice escape — frozen negative handoff

No gate-clearing candidate was found, and no external state was changed.

The live target is strictly above `2.365832385307997`.  The frozen canonical
47-pair/17-wall tolerance root remains `2.365832385227916`, short by
`8.008126667059514e-11` under verifier
`c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9`.

## Asset recovery

Two new primary-source checks did not supply n=21 bytes.  Berthold et al.,
*Global Optimization for Combinatorial Geometry Problems* (arXiv:2601.05943),
formulate the exact fixed-perimeter objective, but Table 2 reports only n=26 and
n=27 rectangle packings at five decimals and gives no n=21 coordinates.
EMO-STA (arXiv:2605.22613) publishes task-family prompts and normalized metrics,
not a final n=21 construction or primary artifact repository.

## Literal-verifier numerical audit

The older public discussion's `2^50` lattice trick is closed by the current
`MAX_COORD=1e6` and `radius >= 1e6*ulp(coord)` checks.  A new bounded screen
nevertheless tested whether the remaining legal float64 lattice could hide the
very small gate gap:

- 5,000,000 deterministic translation/binade/rounding-phase trials at a radius
  dilation safely above the gate;
- zero candidates simultaneously cleared the active 47-pair bundle and the
  verifier's computed perimeter;
- best joint slack was still `-1.0667147194332864e-11`;
- a separate 12,000-state reflection-symmetric lattice/LP screen had best raw
  strict-LP value `2.365832384953663` and best exact replay
  `2.36583238466807`, both below the gate.

Reproduce the first result:

```bash
cd /Users/jacweath/EinsteinArena
.venv/bin/python \
  campaign/geometry/rectangle_precision_escape/audit_numeric_lattice.py \
  --samples 5000000
```

The search is read-only, retains no downloaded bytes, and exact-replays every
screening hit before reporting it.  The only justified next rectangle move is
a genuinely different coordinated multi-contact topology; another same-cage
precision or legal-coordinate translation pass is not supported by this audit.
