# C3 precision/topology escape handoff

Updated: 2026-08-15T06:40Z

## Frozen decision

This bounded lane found a real changed-orthant improvement but did not clear
the Arena gate. It made no Arena, discussion, GitHub, or other external write.

The unchanged public verifier returns **`1.4515653796072292`** for
`runs/20260815T063056Z-39272/best.npy`. Payload SHA-256 is
`39c72ab7147413ded04ee4af3c6a15a0d4d66a91e05102b1ad3edac9dba6d13e`.

- Frozen input: `1.4515653850221024`.
- Exact gain: `5.414873216480487e-9`.
- Public leader: `1.4515718638902069`.
- Gate target: `1.4515618638902069`.
- Remaining exact gap: `3.5157170223953926e-6`.
- Verifier SHA-256:
  `b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9`.

Independent network-free replay:

```sh
cd /path/to/EinsteinArena
.venv/bin/python campaign/analytic/c3_precision_escape/replay_exact.py
```

The replay checks the frozen verifier hash and independently evaluates the C3
formula; it never imports or executes downloaded verifier code on host.
Submission-grade acceptance remains the Docker controller's responsibility.

## Changed route and negative frontier

The schema leaves the discretization length free, so the lane first tested
mass-preserving global rebinning over lengths 76,800 through 140,800, then
global cell-phase/filter transforms, endpoint extension, 14,333 exact-replayed
deletions, and directions from all distinct retained public constructions.
None descended from the frozen input.

Finite donor topology was then screened in 100,152 block/sign transplants.
Because FFT cancellation can mis-rank single-cell changes, the final wall
selection used the algebraically exact rank-two convolution update and literal
`numpy.convolve` replay. Twenty thousand low-amplitude walls and 7,140 pairs
were ranked. No pair entered more cheaply than the strongest remaining single
wall.

The accepted lineage crossed index 78,284, released back to the original
orthant for a `4.1386266e-9` exact gain, then crossed index 39,272. The second
sign remains changed after full release and adds `1.2762467e-9`. This is a
genuine adjacent-orthant result, not a byte-level replay of the input.

The progress scale closes this route for the present gate: the full two-wall
walk gained `5.415e-9`, while another `3.516e-6` is required. Linear
extrapolation would need roughly 1,299 more comparable wall steps, and the
next entry penalty is already larger. That extrapolation is not a proof of a
local or global optimum; it is the bounded numerical stopping reason.

## Reproduction and publication boundary

The two optimizer commands, hashes, corpus counts, and exact lineage are in
`receipt.json`. `topology_transplant.py` writes atomic binary checkpoints and
an append-only event journal; FFTs are used only for smooth proposals and
every saved improvement is accepted with literal float64 `numpy.convolve`.

Publish-safe source/document files:

- `README.md`
- `HANDOFF.md`
- `receipt.json`
- `replay_exact.py`
- `topology_transplant.py`

The `runs/` arrays are original campaign-generated numerical artifacts. No
third-party source or payload byte is present in this lane.
