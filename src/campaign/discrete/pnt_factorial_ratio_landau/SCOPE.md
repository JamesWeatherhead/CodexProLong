# PNT factorial-ratio / Landau lane

This isolated, read-only campaign asks whether Bober's complete classification of
height-one integral factorial ratios yields a stronger **global** certificate for
the Einstein Arena prime-number-theorem objective.

For numerator parameters `a=(a_i)` and denominator parameters `b=(b_j)` with
`len(b)=len(a)+1` and `sum(a)=sum(b)`, set

```
M = lcm(a_i, b_j)
c[M/a_i] += 1
c[M/b_j] -= 1.
```

Then

```
F(x) = sum_m c[m] floor(x/m)
     = sum_i floor(a_i x/M) - sum_j floor(b_j x/M).
```

Landau's theorem and Bober's height-one classification make `F(x)` exactly
`{0,1}`-valued for every real `x`; hence it satisfies the Arena's upper-only
constraint `F(x) <= 1` globally.  The Arena score simplifies exactly to

```
S = -sum_m c[m] log(m)/m
  = (sum_i a_i log(a_i) - sum_j b_j log(b_j))/M.
```

The lane covers Bober's three infinite families and all 52 sporadic cases,
canonicalizes cancellations and repeated support indices, replays the complete
integer period without executing downloaded verifier code, and performs a
bounded parameter search of each infinite family.

External policy: primary-source retrieval is GET-only.  No Arena submission,
discussion, issue, GitHub write, or author contact is permitted.  Third-party
paper/source bytes are research inputs only and are excluded from any public
allowlist; locally authored clean-room code and derived parameter data are the
only publication candidates.
