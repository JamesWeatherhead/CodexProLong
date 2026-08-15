# Erdős minimum overlap: certificate record

Paul Erdős posed the finite partition problem in 1955. Given a partition of
`1, …, 2n` into two sets of size `n`, count how often each integer occurs as a
difference between opposite colors; then minimize the largest count. The exact
asymptotic constant remains unknown.

CodexProLong continued Hyra's public [solution #2440](https://einsteinarena.com/api/solutions/2440)
and submitted [solution #2507](https://einsteinarena.com/api/solutions/2507).
The frozen result is an explicit 3,584-step construction with recorded
continuous objective bound

`0.3808585748578583091444423330164409480469`.

This is an upper-bound improvement, not a determination of the unknown
constant. The selected machine-readable certificate record is
[`artifacts/certificates/erdos-min-overlap-continuous.json`](../artifacts/certificates/erdos-min-overlap-continuous.json),
and the campaign verification receipt is
[`artifacts/receipts/erdos-min-overlap.json`](../artifacts/receipts/erdos-min-overlap.json).

## Continuous reduction recorded by the certificate

The submitted payload contained `n = 3,584` binary64 values. The certification
procedure parsed every value as binary64, converted it with
`as_integer_ratio()`, lifted the dyadic rationals to a shared denominator, and
normalized them exactly.

Write the resulting integer numerators as `X_i`, set `T = Σ X_i`, and let
`m = n/2 = 1,792`. Define `f_i = m X_i / T` on consecutive subintervals of
width `1/m` in `[0, 2]`, and let `g = 1 − f` on that interval and zero outside
it. The recorded checks establish exact integral `1`, values in `[0, 1]`, and
all `2n − 1 = 7,167` grid lags.

For grid lag `k`, if `A_k` is the sum of source numerators in the overlapping
range and `B_k` is the corresponding sum of products `X_i X_j`, the overlap is
the rational

`(T A_k - m B_k) / T²`.

The unique recorded maximizing lag is `−192`.

## Why grid lags cover every real shift

Both `f` and its complement are constant on the same regular grid. Between
consecutive grid shifts, the set of intersecting interval pairs is fixed and
each intersection length is affine in the shift. Their weighted sum is
therefore affine there, so its maximum occurs at an endpoint. This reduces the
continuous maximum to the checked grid boundaries.

## Evidence limitation

The receipt pins candidate SHA-256
`43d6096c5ebd143a03f56e5c07de335e2c1b64bf3485336633df16d7f8257db6`
and verifier SHA-256
`7c0e78d9dc40f27584ee2de01348fddcc6ff4a540908ddc902a4c6ef920920b0`.
The certificate preserves the exact fraction, normalization facts, maximizing
lag, and continuous-reduction statement.
Its `certificate_source_sha256` pins the certification program from an earlier
public revision; that program is not included in the current release tree.

The candidate bytes are not redistributed in this release because the search
continued a public Arena payload whose redistribution terms were not
established. Consequently, this page documents the frozen certificate and its
claim boundary; it does not claim that a fresh clone can recompute the
certificate without obtaining the referenced payload through authorized means.

## Sources

- Paul Erdős, “Some remarks on number theory” (1955).
- Jan Kristian Haugland,
  [*The minimum overlap problem revisited*](https://arxiv.org/abs/1609.08000)
  (2016).
- Ethan Patrick White,
  [*Erdős' minimum overlap problem*](https://arxiv.org/abs/2201.05704)
  (2022).
- Bogdan Georgiev, Javier Gómez-Serrano, Terence Tao, and Adam Zsolt Wagner,
  [*Mathematical exploration and discovery at scale*](https://arxiv.org/abs/2511.02864)
  (2025).
- Sungyoon Kim and Mert Pilanci,
  [*AI-Assisted Discovery of Convex Relaxations via Dual Agents*](https://arxiv.org/abs/2606.31182)
  (2026).

## Claim boundary

The approved claim is: **CodexProLong recorded an improved upper-bound
construction with an exact-arithmetic certificate record.** It must not be
shortened to “Codex solved the problem.” The exact constant remains open.
