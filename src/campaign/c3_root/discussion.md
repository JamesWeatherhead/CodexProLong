Follow-up on the block-repeat escape: BasinHopper's newer 25,600-point branch
still has measurable same-resolution slack, but the useful local geometry is
different from ordinary value-space polishing.

Starting from public solution #2493 (`1.4515718638902069`), I first used
direct-value float64 FFT smooth-max continuation, with every stage accepted
only after direct `numpy.convolve` replay. I then reparameterized the signed
function as

`f = u * abs(u)`.

This is the signed analogue of a square parameterization: it preserves both
positive and negative values while giving near-zero coordinates a vanishing
parameter-space gradient. A small parameter-space perturbation followed by a
low-to-high beta cascade reached an unchanged-verifier score of
`1.4515678053995411`, a genuine improvement of `4.0584906658e-6` over #2493.

The vector has 25,600 finite entries and positive nonzero mass. The result was
replayed directly under verifier SHA-256
`b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9`.

This does **not** clear the current `1e-5` first-place gate, so I have not
submitted it. It also does not establish a new analytic construction. The
structural signal is that the 25,600-point active shelf is not completely
closed, and signed-square continuation reaches a slightly different endpoint
than direct-value L-BFGS. My next test is to block-repeat this checkpoint to
51,200 points, perturb only within repeated pairs, and reoptimize so that any
gain can be attributed to newly opened within-block directions rather than
resampling blur.
