# Edges-vs-triangles mesh optimization

This campaign stays on the legitimate complete-multipartite Razborov curve. It
keeps ten zero-triangle nodes at edge densities `0.05, ..., 0.50`, retains every
curve transition, and optimizes the remaining scallop-interior nodes with a
damped tridiagonal Newton method. A one-node exchange audit then checks the
integer allocation between scallops.

Nothing here submits, posts, votes, or otherwise mutates EinsteinArena.

```sh
cd /Users/jacweath/EinsteinArena/campaign/discrete/edges_vs_triangles
../../../.venv/bin/python refresh.py
../../../.venv/bin/python optimize.py
../../../.venv/bin/python verify.py
```

`candidate.json` is the best legal local construction found, whether or not it
clears the live `1e-6` first-place gate. `checkpoints/optimization.json` records
stationarity, Hessian, kink-subgradient, and node-transfer diagnostics;
`checkpoints/reproduction.json` replays both payloads with the current live
verifier.
