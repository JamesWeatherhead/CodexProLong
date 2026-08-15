# Bober/Landau factorial-ratio PNT handoff

## Outcome

The complete height-one integral-factorial-ratio class gives genuine all-real
PNT certificates, but its optimum is only Chebyshev's classical five-term
identity.  It cannot approach either Arena gate.

- Best classified member: Bober sporadic line 31,
  `[30,1]/[15,10,6]` (canonical order `[1,30]/[6,10,15]`).
- Arena coefficients including normalized `f(1)`:
  `{1:1, 2:-1, 3:-1, 5:-1, 30:1}`.
- High-precision score:
  `0.921292022934090780913408449961604716417080789093030241095500...`.
- Gap to historical gate `0.9976498835182795`:
  `-0.07635786058418871908659155004...`.
- Gap to refreshed live gate `0.9976582852677297`:
  `-0.07636626233363891908659155004...`.
- Exact mathematical period: 30 states; minimum 0, maximum 1, exactly 15
  states of each value.  Thus the payload is valid for every real `x>=1` and
  uses none of the verifier's `1e-4` tolerance.
- Clean-room literal finite-horizon replay: all 300 integer states pass;
  binary64 score `0.9212920229340907`.

No submission or discussion action is warranted.

## Exact map

For a height-one integral factorial ratio with numerator parameters `a_i`,
denominator parameters `b_j`, equal sums, and

```text
M = lcm(a_i,b_j),
```

the canonical Arena support is

```text
c[M/a_i] += 1,   c[M/b_j] -= 1.
```

The resulting floor sum equals Bober's Landau step function after the scale
change `x -> x/M`, so it is globally `{0,1}`-valued.  Exact normalization
follows from `sum(a_i)=sum(b_j)`.  The score is

```text
S = (sum_i a_i log(a_i) - sum_j b_j log(b_j))/M,
```

because the `log(M)` terms cancel.  `landau_core.py` computes rigorous rational
log intervals using the positive atanh series with an exact tail bound; the
ordering of the 52 sporadics therefore does not depend on floating point.

## Complete classification coverage

The official arXiv v1 source contains all 52 sporadic rows in `table3.latex`;
Paperclip's otherwise useful text extraction omits rows 25-44.  The recovered
source archive has SHA-256
`0d7e59ea681a91e80dbd0d643a0859b10d5ec7426d015301e8f606a2669ff982`,
and the clean derived 52-row JSON has SHA-256
`016c250ff6b2b9dae71fe96b0fc0e6f9ddf04b73c1acb8ba3a620cbde620162d`.

Every sporadic row was checked for height one, balance, primitivity, and lack
of cross-side cancellation.  Its complete mapped period was then enumerated
with integer arithmetic.  All 52 are exactly `{0,1}`-valued; the largest
period is only 210.  Line 31 beats the other 51 by a rigorously isolated margin
of at least `0.06901630030044226688357037284915948...`.

The three infinite families were independently enumerated over all coprime
parameters `1<=a,b<=2000` (3,649,763 symmetry-reduced pairs total).  Their
maxima agree with global elementary bounds:

1. `[a+b]/[a,b]`: entropy gives `S<=log(2)/(ab)`, maximized at `(1,1)`
   with `S=log(2)`.
2. `[2a,b]/[a,2b,a-b]`: with `d=a-b`, entropy and the exact lcm give
   `S<=3log(2)/(bd)`.  For `bd>=3` this is at most `log(2)`; the three
   cases `bd<=2` are checked exactly, and `(a,b)=(3,1)` wins with
   `S=0.7803552045207032821700333256...`.
3. `[2a,2b]/[a,b,a+b]`: entropy gives `S<=2log(2)/(ab)`; the cases
   `ab<=2` are checked exactly, and `(1,1)` wins with `S=log(2)`.

Thus the bounded computation is also backed by a proof over all positive
coprime family parameters.  Together with the 52-row table, it covers Bober's
complete height-one classification.

## Reproduction

From the public `CodexProLong` repository root, using system Python 3.9 or
newer:

```sh
/usr/bin/python3 -B src/campaign/discrete/pnt_factorial_ratio_landau/verify_best.py
/usr/bin/python3 -B src/campaign/discrete/pnt_factorial_ratio_landau/screen_bober.py --bound 2000
```

In the canonical research checkout, omit the leading `src/`:

```sh
/usr/bin/python3 -B campaign/discrete/pnt_factorial_ratio_landau/verify_best.py
/usr/bin/python3 -B campaign/discrete/pnt_factorial_ratio_landau/screen_bober.py --bound 2000
```

The first command is a fast, standalone replay.  The second repeats the full
52-row audit and bounded 3-family enumeration.  Neither command imports or
executes the live verifier or requires network access.

## Frozen live metadata and external policy

- Refreshed live verifier SHA-256:
  `fd76a069b269a521d6ded609bd79185bf859df778283bebc37719dfd15b1ded6`.
- Compact response hashes and the retrieval timestamp are in
  `LIVE_METADATA.json`; no 2,000-key leader payload is retained.
- Refreshed leader: `#2506`, `CodexProLong`, score
  `0.9976572852677297`; minimum improvement `0.000001`.
- External actions in this lane: GET-only Paperclip, Exa-provenance,
  official arXiv source, and Arena metadata reads.  No submission, post,
  comment, vote, issue, push, or author contact occurred.
- Third-party paper/source and verifier bytes are not in the publication
  allowlist.  Locally authored/generated packet files are published under the
  CodexProLong MIT license.
