# EinsteinArena geometry campaign

Read-only research and local optimization for the live geometry problems.
External posting and submission are deliberately outside these programs.

Refresh the public inventory:

```bash
../../.venv/bin/python live_inventory.py
```

Run a bounded checkpointed SLP campaign:

```bash
../../.venv/bin/python slp_search.py kissing-number-d12-842 --rounds 6
../../.venv/bin/python slp_search.py kissing-number-d11-605 --rounds 4 \
  --trusts 1e-10,3e-10,1e-9,3e-9,1e-8,3e-8,1e-7,3e-7,1e-6
```

Every run records the live problem, leaderboard, source candidates, an
append-only event log, atomic checkpoints, the verifier hash, and a standalone
reproduction command in `summary.json`.

Continue from a prior checkpoint with `--seed-payload /absolute/path/best.json`.

Run the strict-domain packing searches and rigid active-set refinement:

```bash
../../.venv/bin/python circle_packing_search.py --source-count 8 --restarts 32
../../.venv/bin/python rectangle_packing_search.py --source-count 8 --restarts 24
../../.venv/bin/python rectangle_active_refine.py /absolute/path/best.json \
  --digits 100
```

These packing programs reject any negative geometric slack themselves; they do
not use the arena verifiers' `1e-9` overlap/perimeter allowance as construction
space. `rectangle_active_refine.py` solves the 65-equation rigid contact system
at high precision and rounds it back with representable-radius safety steps.

Run the bounded Thomson tangent-coordinate polish:

```bash
../../.venv/bin/python thomson_polish.py --maxiter 300 --maxfun 1200
```

Run the topology-changing Thomson global-basin campaign (cap transport,
vacancy/interstitial defect relocation, bond flips, and alternate public
graphs):

```bash
../../.venv/bin/python thomson_global_basin.py \
  --trial-limit 48 --relax-rounds 2 --maxiter 700
```

Run exact active refinement and depth-four topology campaigns for the two
rigid planar maximin problems:

```bash
../../.venv/bin/python min_distance_active_refine.py --digits 100
../../.venv/bin/python min_distance_topology_search.py \
  runs/20260814T231106Z/min-distance-ratio-2d/best.json
../../.venv/bin/python heilbronn_active_refine.py --digits 100
../../.venv/bin/python heilbronn_topology_search.py \
  runs/20260814T231710Z/heilbronn-triangles/best.json
```

The refinement programs reconstruct the square active systems at arbitrary
precision. The topology programs force weak active constraints or boundary
contacts open, checkpoint each trial, and replay every payload through the
unchanged live verifier. They reject nonfinite, coincident, or out-of-domain
geometries and do not use verifier tolerances as construction space.
