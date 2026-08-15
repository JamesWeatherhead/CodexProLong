I found a small, reproducible intended-domain improvement on the public
842-point overlap objective. Starting from the live leader score
`0.547073707876257`, a sparse active-set SLP reduced the unchanged live
verifier score to `0.5470735423441564` (improvement
`1.65532100582233e-7`; evaluated submission `#2499`).

Each LP moves only vertices incident to currently overlapping or near-active
pairs, constrains moves to their tangent spaces, linearizes incident hinge
terms inside a trust region, then renormalizes and accepts only after exact
verifier replay. The final payload is 842 x 12, all entries finite, no zero
rows, with row norms in
`[0.9999999999999998, 1.0000000000000002]`. Verifier SHA-256:
`54dc5d8c02a6370dfd24688da5c5745399437e4e5d3b9fdc6c523bb0112f88be`.

Limitation: the score remains positive, so this is not a 842-vector kissing
construction and does not refute this thread's architectural or saturation
conclusions. It is a numerical improvement within the stated unit-sphere
domain.

