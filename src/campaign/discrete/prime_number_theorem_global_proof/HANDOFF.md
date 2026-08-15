# Global PNT certificate audit

## Outcome

Evaluated Arena solution `#2506` is a strong finite-horizon construction, but
it is not a certificate for the stated all-real inequality

```text
S(x) = sum_k f(k) floor(x/k) <= 1  for every real x >= 1.
```

This is an upper-only condition; negative values are unrestricted.  Three
independent conclusions close the attempted upgrade:

1. The exact submitted-decimal normalization gives
   `S(1)=1.000099989952235264... > 1`.  More importantly, well beyond the
   verifier horizon it gives `S(8,015,392)=106.150121507295472...`.
   Even uniform scaling that is exactly safe at every integer in the complete
   verifier horizon still gives `106.139508609467267...` at that point.
2. A retained nonnegative weak-dual vector proves that *every* coefficient
   assignment on the exact 2,000-key `#2506` support has score at most
   `0.99762577830444706730482048242952755...` under only 7,464 necessary
   upper inequalities.  This is `0.0000241052138324327...` below the
   historical acceptance gate `0.9976498835182795`.  The proof is a relaxation
   of the all-x problem, so omitted constraints can only lower the ceiling.
3. Genuinely changed periodic supports are globally certifiable but remain
   far below that gate.  The strongest bounded construction found uses all
   divisors of `L=9,699,690`; an exact scan of all 9,699,690 period states gives
   maximum exactly `1` and score
   `0.97007355828112690392241115468135842...`, a gate gap of
   `-0.027576325237152596...`.

The conclusion is therefore negative but sharp in scope: neither a tail
argument nor any coefficient-only repair on the existing support can turn
`#2506` into a gate-preserving global certificate.  A successful construction
would require a substantially different, nontrivial support identity.

## Why finite checking is exact for periodic candidates

After exact normalization `sum_k f(k)/k=0`, integer keys give

```text
S(m) = -sum_{k>1} f(k) (m mod k)/k.
```

If every support key divides `L`, this is `L`-periodic.  Since the floor sum is
constant on every real interval `[m,m+1)`, checking the `L` integer states is a
complete all-real proof.  The retained periodic candidates use rational
coefficients and integer recurrence arithmetic; floating-point LP output is
only a proposal that is rounded and rescaled before certification.

## Reproduction

From the repository root, with the existing Python environment:

```bash
.venv/bin/python -B campaign/discrete/prime_number_theorem_global_proof/certify_counterexample.py
.venv/bin/python -B campaign/discrete/prime_number_theorem_global_proof/verify_same_support_dual.py
.venv/bin/python -B campaign/discrete/prime_number_theorem_global_proof/chebyshev_baseline.py
.venv/bin/python -B campaign/discrete/prime_number_theorem_global_proof/verify_periodic_candidate.py selberg
.venv/bin/python -B campaign/discrete/prime_number_theorem_global_proof/verify_periodic_candidate.py divisor
```

The public replay commands require no solver and operate only on packet-local,
hash-pinned inputs.  They never import or execute the downloaded verifier.

## Frozen provenance

- `#2506` payload SHA-256:
  `d43c5531d562d06981a55829deb1c579a87a7c02405d69688dcc79e7f45f22c1`
- live verifier text SHA-256:
  `fd76a069b269a521d6ded609bd79185bf859df778283bebc37719dfd15b1ded6`
- same-support dual SHA-256:
  `673f2b70a55027534fa8d22b060d412d0d36bec641605034fa67ee34af66b7c9`
- strongest global candidate SHA-256:
  `58ef9323fa496b9e8779d00b532f88d75b995fe53950a745e2a15d694912f83a`

The bibliography and exact line-pinned source roles are in `SOURCES.md`.
No paper, verifier, or third-party code bytes are copied into this directory.
