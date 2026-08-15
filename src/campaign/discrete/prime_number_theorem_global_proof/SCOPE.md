# Prime-number-theorem global-proof lane

This isolated lane asks whether evaluated solution `#2506` can be upgraded
from a finite verifier-horizon construction to the mathematical condition

```text
sum_k f(k) floor(x/k) <= 1  for every real x >= 1.
```

This condition is one-sided.  Negative values, however large in magnitude,
are permitted; they are retained in receipts only as diagnostics.  The ideal
constant `1` is also stricter than the live verifier's numerical `1.0001`
threshold.

The work is read-only with respect to EinsteinArena, GitHub, and discussion
systems.  The frozen verifier is only read and SHA-256 checked; it is never
imported or executed.  Candidate evaluation uses an independently written
formula mirror.

The planned certificate has four layers:

1. audit the submitted decimal and binary64 payload semantics, including the
   verifier's clipping and normalization;
2. use the fact that integer denominators make the floor sum constant on every
   interval `[m,m+1)`, and that exact normalization makes it periodic modulo
   the least common multiple of the support;
3. seek an explicit analytic tail bound from primary sources on finite
   Möbius approximants and summatory-function estimates, with interval or
   rational arithmetic for all finite exceptions; and
4. if `#2506` is obstructed, test only minimally changed constructions that
   still clear the historical acceptance gate.

Downloaded verifier code is not executed, and third-party paper bytes are not
stored in this subtree.
