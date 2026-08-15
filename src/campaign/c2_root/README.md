# Second-autocorrelation root lane

This lane attacks the live two-million-point C2 construction while the other
campaign workers cover the geometry, analytic, and discrete frontiers.

`fetch_live.py` snapshots the public best-solution trajectory and writes the
leader as a NumPy checkpoint. `optimize_mps.py` performs projected,
persistent-dual smooth-minimax descent on Apple Metal, but accepts checkpoints
only after a float64 replay of the arena's exact SciPy verifier formula.
`support_harvest.py` tests support-opening moves selected by a high-beta dual
plateau gradient and likewise accepts only exact float64 improvements.

The implementation is derived independently from the equations and compares
against the public ClaudeExplorer campaign at git commit
`04eba482710e013f14e669be53d6fea89342cc99`; that repository's documented
negative results are treated as an exclusion list.

Run:

```sh
../../.venv/bin/python fetch_live.py
../../.venv/bin/python optimize_mps.py --minutes 20
```

No script in this directory posts discussions or submits solutions.
