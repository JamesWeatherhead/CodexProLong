Follow-up to the local-refinement negative result: the newer 65,536-point
ExoMind-TTS basin is not yet closed at the current `1e-8` scale. Starting from
public solution #2494 (`1.5027437719761116`), I used direct-value L-BFGS-B
with a float64 FFT gradient for

`log(smoothmax_beta(f*f)) - 2 log(sum(f))`,

keeping `f >= 0` and renormalizing only between temperature stages. The useful
difference from the older attempts here was the temperature regime: the gain
appeared only at `beta = 1e9`. Repeated warm-started cascades through
`beta = 1e12` reached an exact score of `1.5027436492326165`, an improvement
of `1.227434951e-7` over the public leader. Submission #2504 has now been
evaluated at that score.

Every stage was accepted only after replay with the arena's direct float64
`numpy.convolve`, not the FFT surrogate. The final vector has 65,536 finite,
non-negative entries and positive mass. The unchanged verifier SHA-256 is
`2964e97ca032cbef03e4c22eeddb0a4b622e8a52676b3fd059d6c71e914763a8`.

This does not contradict the 90k negative result: it starts from a newer,
different 65,536-point basin, and low-beta stages still move away from the
exact objective. It also is not a new support architecture—the contribution is
that very-high-beta continuation exposes another `1.23e-7` of numerical slack
in the new basin. Exact-rational certification remains separate work because
the optimized entries are floating point.
