# Landau atom packing for the PNT certificate

Status: frozen exact negative frontier; no gate-clearer.

This lane asks whether exact `{0,1}`-valued Landau step functions can be
combined into a stronger globally valid Prime Number Theorem certificate.  It
is separate from the height-one classification replay in
`pnt_factorial_ratio_landau/`.

For a Bober factorial ratio with numerator parameters `A`, denominator
parameters `B`, and `M = lcm(A union B)`, the Arena coefficients

```text
c[M/a] += 1  (a in A)
c[M/b] -= 1  (b in B)
```

give a periodic floor sum in `{0,1}`.  Replacing every support index `k` by
`d*k` scales its score by `1/d` and repeats each residue value `d` times.  A
nonnegative combination of these atoms is a global certificate exactly when
its value is at most one at every residue of the joint period.

`search.py` builds all 52 sporadic atoms, adds bounded dilations, and solves
the resulting fractional packing LP by exact-residue constraint generation.
Every proposed optimum is rescanned over the complete joint period.  A final
no-go claim requires a rational primal/dual certificate; floating LP output is
only a route-finding screen.

Primary source: Jonathan W. Bober, *Factorial ratios, hypergeometric series,
and a family of step functions*, arXiv:0709.1977.  The classification was read
through Paperclip and transcribed from the official arXiv source in the sibling
lane.  No paper bytes, credentials, Arena writes, or GitHub writes belong in
this directory.
