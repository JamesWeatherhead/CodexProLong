# C3 Fourier-dual / semismooth-Newton handoff

Updated: 2026-08-15T12:45Z

## Frozen decision

Stop this route as a bounded no-go.  It made no Arena, discussion, GitHub, or
other external mutation.  No FFT-screened point approached the strict gate, so
there was no official verifier call and no submission attempt.

The frozen starting point is
`campaign/analytic/c3_precision_escape/runs/20260815T063056Z-39272/best.npy`,
whose unchanged verifier score is `1.4515653796072292`.  The live strict target
at lane start is `1.4515618638902069`, leaving `3.5157170223e-6`.

This route is separate from the retained sign-wall, topology-transplant,
deletion/rebin, rank-lift, and asset-transfer cascades.  It operates on the
polynomial identity `Q(z)=F(z)^2` and on the dual/generalized Hessian of the
finite maximum.

## Exact scope read before search

`audit_corpus.py` parsed every frozen C3 `data.values` vector and every captured
C3 discussion body under corpus SHA-256
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`:

- 40 constructions;
- 20 threads; and
- 97 replies.

It also read the exact verifier at SHA-256
`b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9`.
The resulting hashes, duplicate groups, and discussion-method taxonomy are in
`corpus_audit.json`.  Paperclip line-pinned sources and read-only Exa request
identifiers are in `literature.json`.

## Quantified result

The deterministic single-thread run is `runs/20260815T124000Z/`.

- Six mass-preserving coefficient-cap projections, ranging from `3e-6` to
  `1e-3` relative cap reduction, all had their best screened FFT envelope at
  the zero step after frequencywise rooting, inverse transformation, and
  causal truncation.  This is not an exact causal spectral factorization.
- 3,980 finite Fourier square-root branch candidates were screened across the
  1,024 smallest spectral coefficients; none improved the FFT envelope.
- Four matrix-free generalized Newton systems were solved at softmax inverse
  temperatures `3e9`, `1e10`, `3e10`, and `1e11`.  The Hessian-vector product
  contains both the weighted polynomial-square Hessian and the complete dual
  covariance term.
- The largest observed Newton FFT gain was only
  `2.2956081480e-11`, versus a remaining official gap of
  `3.5157170224e-6`—more than 153,000 times larger.  CG reached its fixed
  45-product budget, so this is a bounded numerical result, not a stationarity
  or optimality certificate.

The best FFT value differs from the frozen official baseline on the scale of
FFT/direct-convolution ordering noise.  It is intentionally not preserved as a
candidate and is not described as an official improvement.

## Reproduction and publication boundary

Run the self-contained publication replay:

```sh
.venv/bin/python campaign/analytic/c3_fourier_dual_newton/replay.py
.venv/bin/python -m unittest campaign/analytic/c3_fourier_dual_newton/test_packet.py
.venv/bin/python campaign/analytic/c3_fourier_dual_newton/publication_selftest.py
.venv/bin/python campaign/analytic/c3_fourier_dual_newton/test_publication.py
```

Publish exactly the regular files listed by `PUBLICATION_MANIFEST.json`, plus
that manifest envelope.  Exclude every unlisted path, `__pycache__/`, bytecode,
ephemeral copied-layout test trees, upstream candidate arrays, verifier source,
and the corpus database.  The portable replay verifies the frozen run from its
authenticated event log; `replay.py --with-private-input` additionally checks
the excluded baseline and verifier hashes when those inputs are available.
This lane contains no third-party source or candidate byte.
