# First-autocorrelation root lane

This lane freezes the public 65,536-point frontier and searches for an exact
`1e-8` gate-clearing reduction of the normalized maximum autoconvolution.
All proposals use FFTs for ranking, then the unchanged NumPy direct
convolution for final acceptance.

`smooth_polish.py` runs a float64 high-beta L-BFGS cascade and writes a
checkpoint only when the direct verifier score decreases.

Best run so far: `runs/20260814T231830Z`, direct-verifier score
`1.5027437355322677` versus the frozen leader `1.5027437719761116`. Candidate
submission #2502 is pending evaluation; do not post `discussion.md` until it
has evaluated successfully.
