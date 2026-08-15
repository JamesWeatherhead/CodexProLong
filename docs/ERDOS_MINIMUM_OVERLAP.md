# Erdős minimum overlap: exact construction certificate

Paul Erdős posed the finite partition problem in 1955. Given a partition of
`1, …, 2n` into two sets of size `n`, count how often each integer occurs as a
difference between opposite colors; then minimize the largest count. The exact
asymptotic constant is still unknown.

CodexProLong publishes an explicit step-function construction with a rigorous
continuous objective bound

`0.3808585748578583091444423330164409480469`.

This improves the public reference upper-bound value `0.38087131058` by more
than `0.0000127357221416908555576669835590519531`. It is an improvement to the
upper side of the problem, not a determination of the unknown constant. The
best certified lower bound reported by Kim and Pilanci is `0.37912`, so a real
gap remains.

![Three panels showing the candidate density, a shifted complement, and the maximum overlap across every shift](../assets/erdos-overlap-explainer.svg)

*The search changes the density while trying to lower the largest overlap
created by any shift. The display is downsampled; the certificate uses all
3,584 values.*

## From 3,584 numbers to a continuous density

The public payload contains `n = 3,584` binary64 values. Parse each JSON number
as binary64, convert it with `as_integer_ratio()`, and lift the dyadic rationals
to a shared denominator. Write the resulting integer numerators as `X_i`, set
`T = Σ X_i`, and let `m = n/2 = 1,792`.

Define `f_i = m X_i / T` on consecutive subintervals of width `1/m` in
`[0, 2]`, a translation of the customary `[-1, 1]` domain. Let `g = 1 − f`
on that interval and zero outside it. Then `Σ f_i / m = 1` exactly. Every
value remains in `[0, 1]` under this exact normalization.

For grid lag `k`, let `A_k` be the sum of the source numerators in the
overlapping range and `B_k` the sum of the corresponding products `X_i X_j`.
The overlap is the exact rational

`(T A_k - m B_k) / T²`.

The certificate evaluates all `2n − 1 = 7,167` grid lags with Python integers.
The unique maximizing lag is `−192`.

## Why grid lags cover every real shift

Both `f` and its complement are constant on the same regular grid. Between two
consecutive grid shifts, the set of intersecting interval pairs is fixed and
each intersection length is affine in the shift. The overlap—the weighted sum
of those lengths—is therefore affine on that interval.

An affine function reaches its maximum at an endpoint. Applying this to every
shift interval reduces the continuous maximum to the grid boundaries already
checked exactly.

## Reproduce the certificate

From the repository root:

```bash
python tools/certify_erdos_continuous.py --check
python -m json.tool artifacts/certificates/erdos-min-overlap-continuous.json >/dev/null
```

The machine-readable certificate pins the payload, frozen verifier, exact
fraction, upward-rounded decimal bound, maximizing lag, and comparison values.
The Arena receipt and optimization-independent float64 replay remain separate
evidence for the submitted leaderboard result.

## Sources and lineage

- Paul Erdős, “Some remarks on number theory” (1955), the source of the
  original partition question.
- Jan Kristian Haugland,
  [*The minimum overlap problem revisited*](https://arxiv.org/abs/1609.08000)
  (2016), including the step-function route to upper bounds.
- Ethan Patrick White,
  [*Erdős' minimum overlap problem*](https://arxiv.org/abs/2201.05704)
  (2022), improving the lower-bound side.
- Mert Yuksekgonul et al.,
  [*Learning to Discover at Test Time*](https://arxiv.org/abs/2601.16175)
  (2026), coauthored by James Zou and featuring this problem as a test-time
  mathematical-discovery task.
- Bogdan Georgiev, Javier Gómez-Serrano, Terence Tao, and Adam Zsolt Wagner,
  [*Mathematical exploration and discovery at scale*](https://arxiv.org/abs/2511.02864)
  (2025), reporting the reference upper-bound construction.
- Sungyoon Kim and Mert Pilanci,
  [*AI-Assisted Discovery of Convex Relaxations via Dual Agents*](https://arxiv.org/abs/2606.31182)
  (2026), certifying the `0.37912` lower bound and recording the then-known
  upper-bound value used for comparison here.

## Claim boundary

The approved claim is: **CodexProLong found an explicit, exactly certified
upper-bound construction for the Erdős minimum-overlap problem.** It must not
be shortened to “Codex solved the problem.” The exact constant remains open.
