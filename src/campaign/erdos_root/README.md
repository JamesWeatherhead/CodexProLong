# Erdős minimum-overlap campaign

This directory contains a read-only, intended-domain campaign for EinsteinArena
problem 1.  `erdos_topology_campaign.py` never imports or executes the
downloaded verifier.  Its local acceptance test independently implements the
stated float64 normalization and literal `numpy.correlate(..., mode="full")`
objective.  Final scores are replayed with the campaign controller's offline,
read-only Docker verifier.

Canonical bounded runs:

- `runs/20260814T233900Z/erdos-min-overlap`: 20,711-candidate support,
  multiscale block, grid, zero-run, and public-crossover topology audit.
- `runs/20260814T234200Z/erdos-min-overlap`: 18-stage, 13,500-iteration
  smooth-minimax continuation in a distinct 2,560-sample basin.

Reproduce from this directory:

```bash
/Users/jacweath/EinsteinArena/.venv/bin/python erdos_topology_campaign.py \
  audit --stamp REPRO_AUDIT --block-directions 2000
/Users/jacweath/EinsteinArena/.venv/bin/python erdos_topology_campaign.py \
  multigrid --stamp REPRO_MULTIGRID
cd /Users/jacweath/EinsteinArena/campaign
./arena verify erdos-min-overlap \
  erdos_root/runs/20260814T233900Z/erdos-min-overlap/best.json
./arena verify erdos-min-overlap \
  erdos_root/runs/20260814T234200Z/erdos-min-overlap/best_distinct.json
```

The `20260814T234000Z` and `20260814T234100Z` multigrid directories are
superseded diagnostic runs.  They exposed and then ruled out an incorrect
temperature scaling convention; `20260814T234200Z` is the canonical run.

