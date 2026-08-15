# Higher-height Landau/factorial-ratio PNT lane

This bounded, clean-room lane tests balanced integral factorial ratios of
height two and three as all-real certificates for the Arena PNT inequality.
For a signed factorial list `g(q)` with

```text
sum_q q*g(q) = 0,     D = -sum_q g(q) > 0,
```

Landau integrality is checked by exhaustively verifying

```text
0 <= F(m) = sum_q g(q)*floor(q*m/M) <= D
```

for every `m=0,...,M-1`, where `M=lcm(q)`.  The Arena map is
`f(M/q)=g(q)/D`; therefore `F/D` is a globally valid upper-only certificate
and its exact period replay also covers every real `x`.

The search covers:

- the 28 explicit height-two families in Soundararajan's Section 3;
- the 43 constructive height-two families in his Section 5;
- the explicit Askey, Wider, Gessel, Landau/Picon, multinomial, and product
  families quoted by the primary papers;
- integer height-two/three Landau functions on a declared finite collection
  of complete divisor lattices; and
- signed rational spans only as a separate structural experiment.  A signed
  span is not itself claimed to be an integral factorial ratio.

Floating-point optimization is candidate generation only.  Retained claims
must be replayed with integer/rational arithmetic over the complete period.
No downloaded verifier or third-party source code is executed.  External
research is GET-only; there are no Arena, GitHub, issue, post, or submission
writes in this lane.
