# C3 Fourier-dual / semismooth-Newton lane

This lane tests the signed C3 construction as a polynomial-square minimax
problem.  For mass-normalized values `f`, the verifier score is

```text
2 n max_k [z^k] F(z)^2,   F(z) = sum_j f[j] z^j.
```

That identity matters: the transform of an **autoconvolution** is `F(omega)^2`,
not `|F(omega)|^2`.  Consequently, a generic nonnegative-spectrum relaxation
does not describe the Arena domain.

`fourier_dual_newton.py` implements two bounded clean-room probes:

1. project the coefficients of `F^2` onto a lower one-sided cap with fixed
   total mass, choose the nearest frequencywise square-root signs, inverse
   transform, causally truncate, and line-search the resulting direction;
2. solve a matrix-free generalized Newton system for the high-temperature
   finite-max KKT equations, including the complete softmax covariance term.

The first operation is a proposal heuristic, not an exact causal spectral
factorization: frequencywise roots generally have support beyond the first
`n` coordinates before truncation.

`audit_corpus.py` parses all 40 frozen C3 construction arrays, all 20 C3 thread
bodies, and all 97 C3 reply bodies from the hash-pinned SQLite corpus.  It emits
only hashes, finite-vector features, duplicate groups, and method coverage—no
third-party candidate bytes.

Portable packet replay (standard library only):

```sh
python3 -B campaign/analytic/c3_fourier_dual_newton/replay.py
python3 -B campaign/analytic/c3_fourier_dual_newton/publication_selftest.py
python3 -B campaign/analytic/c3_fourier_dual_newton/test_publication.py
```

The same commands work under `src/campaign/...`.  The publication packet does
not contain the frozen candidate array, verifier source, or corpus database.
With those hash-pinned external inputs available, reproduce the corpus audit
and numerical search with:

```sh
OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 \
  .venv/bin/python campaign/analytic/c3_fourier_dual_newton/audit_corpus.py

OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OMP_NUM_THREADS=1 \
  .venv/bin/python campaign/analytic/c3_fourier_dual_newton/fourier_dual_newton.py
```

Every score produced by this tool is explicitly an FFT proposal diagnostic.
Only `./campaign/arena verify` may produce an official receipt, and no proposal
from this bounded lane approached the current gate.

Frozen outcome: six coefficient-cap projections and 3,980 Fourier branch
proposals produced no FFT improvement.  Four generalized Newton systems found
at most `2.30e-11` of FFT-scale slack, while the official gate remains
`3.52e-6` away.  See `HANDOFF.md`, `receipt.json`, and
`PUBLICATION_MANIFEST.json` for the bounded claim and exact publication
boundary.  First-party code and documentation are MIT-licensed; factual and
bibliographic metadata have the narrower rights treatment in
`PROVENANCE_AND_RIGHTS.md`.
