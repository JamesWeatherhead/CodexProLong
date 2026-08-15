# EinsteinArena discrete frontier

Read-only, reproducible campaign tools for legitimate verifier-domain
constructions. Nothing in this directory submits, posts, votes, or mutates the
arena.

```sh
cd /Users/jacweath/EinsteinArena/campaign/discrete
../../.venv/bin/python refresh_frontier.py
../../.venv/bin/python difference_search.py --restart
../../.venv/bin/python flat_search.py --max-radius 5 --grid 512 --chunk 2048 --restart
../../.venv/bin/python verify_results.py
```

`refresh_frontier.py` snapshots all live problem/leader metadata and the full
leader/discussion state for the two attack targets. The search programs pin the
live verifier and leader payload hashes in atomic JSON checkpoints. They can be
resumed by rerunning without `--restart`.

- `difference_search.py` exhausts every legal one-delete and one-swap move, and
  every one-add move capable of covering the incumbent's first missing
  difference. This is exhaustive for a score-improving same-cardinality
  one-swap because any such move must cover that first gap.
- `flat_search.py` screens the complete requested Hamming ball. Its pruning
  grid consists only of exact points from the live million-point verifier grid,
  so a sampled maximum is a valid lower bound; every unpruned candidate is
  replayed through the unmodified live verifier.
