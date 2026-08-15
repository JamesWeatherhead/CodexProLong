# Higher-height factorial-ratio PNT handoff

## Outcome

No gate-capable higher-height factorial ratio was found.  The strongest exact
height-two or height-three construction is simply the repeated Chebyshev
identity:

```text
2 * [30,1,-15,-10,-6]
```

After normalization by height, its Arena payload is unchanged:

```json
{"partial_function":{"1":1.0,"2":-1.0,"3":-1.0,"5":-1.0,"30":1.0}}
```

- Rigorous high-precision score:
  `0.921292022934090780913408449961604716417080789093030241095500...`
- Exact Landau period: 30 states, minimum 0, maximum 2 before height
  normalization; hence the Arena curve is globally in `[0,1]` for every real
  `x`.
- Clean-room literal verifier mirror: binary64 score
  `0.9212920229340907`, horizon maximum `1.0`.
- Gap to the globally certified changed-support frontier
  `0.9700735582811269039224111546813584...`:
  `-0.04878153534703612300900270472...`.
- Gap to the refreshed live gate `0.9976582852677297`:
  `-0.07636626233363891908659155004...`.

There is no reason to submit this payload: it is the already-known classical
baseline and is materially below both frontiers.

## Primary-family search

`family_search.py` reconstructs the primary-source formulas rather than
executing downloaded code.  Its frozen bounds are:

- every one of Soundararajan's 26 two-parameter Section 3 families for
  coprime `1 <= a,b <= 160`;
- both three-parameter Section 3 families for parameters through 36;
- all 43 Section 5 construction rows for signed coprime parameters in
  `[-160,160]` (excluding zero);
- the explicit Askey, Wider, and Landau--Picon height-two families through
  160;
- Gessel's four-parameter height-three family through 18; and
- repeated Chebyshev products at heights two and three.

The search generated 3,312,606 lists.  After cancellation, 1,031,225 had
height two or three.  It retained and exactly replayed the best member of 77
named families; their total retained exact periods contain 4,065 states.  A
10,000,000-state cap excluded 394,535 nonwinning parameter choices; the best
excluded choice scored only `0.00014286159762919254`, so the cap cannot hide a
contender within the declared enumeration.

As an input-integrity check, the 43 Section 5 base pairs were also rebuilt
through Theorem 1.4: every pair has nonzero coprime sums and every resulting
height-one premise passed a complete exact Landau replay (largest period 180).

The best genuinely irreducible family member was Section 5 row 14 at
`(a,b)=(1,2)`:

```text
[1,6,6,-2,-2,-3,-3,-3],  D=2,  M=6,
score = 0.73675119254032429579363272353608247...
```

The best Section 3 irreducible family member was equation (23) at `(1,4)`,
score `0.58526640339052746162752499421049128...`.  Gessel's height-three
family peaks within the declared box at `(1,1,1,1)`, score
`0.46209812037329687294482141430545104...`.

One source-level issue is handled explicitly: the displayed left side of
Soundararajan's equation (11) omits `-b`, while its decomposition on the same
line contains it.  Exact balance forces the retained `-b`; the code comments
this correction.

## Complete divisor-lattice screens

For each height `D=2,3`, `divisor_lattice_screen.py` optimizes over every real
multiplicity `g(q)` on all divisors of each of 26 declared smooth periods:

```text
30, 60, 120, 180, 210, 360, 420, 840, 1260, 1680, 2520, 5040,
7560, 9240, 13860, 18480, 27720, 30030, 60060, 120120, 180180,
360360, 510510, 1021020, 1531530, 9699690.
```

The constraints are exactly the nonnegative Landau conditions
`0 <= F(m) <= D`, balance, height, and the Arena coordinate bounds.  Complete
period separation was performed in every run.  All 52 floating continuous
relaxations returned the Chebyshev value within `2e-12`; rounding gave the
exact repeated-Chebyshev list in every case, and all 52 rounded candidates
were independently period-replayed.

This is deliberately scoped: the rounded-candidate replays are rigorous,
while HiGHS optimality is numerical negative evidence, not an exact dual
certificate and not a theorem over untested periods.

## Why signed higher-height atoms do not define a new search space

Put `B_j=[j+1,-j,-1]`, a binomial height-one factorial ratio.  Exact
telescoping gives

```text
sum_{j=1}^{n-1} B_j = [n] - n[1].
```

Every finite balanced rational list `g` therefore has the decomposition

```text
g = sum_{n>=2} g(n) * ([n]-n[1]).
```

But `2 B_j` and `3 B_j` are theorem-valid products of heights two and three,
so rationally scaling them by `1/2` or `1/3` shows that the signed rational
span of height-two or height-three product atoms is the entire finite
balanced-list space.  `verify_span_identity.py` checks this identity exactly
on deterministic rational test vectors.

Thus allowing negative atom weights does not create a narrower new
higher-height ansatz: it collapses to the unrestricted normalized floor-sum
problem already attacked by the divisor-support lane.  Negative combinations
are not themselves claimed to be integral factorial ratios and still require
independent upper-only replay.

## Reproduction

From the public `CodexProLong` repository root:

```sh
/usr/bin/python3 -B src/campaign/discrete/pnt_factorial_ratio_higher_height/verify_best.py
/usr/bin/python3 -B src/campaign/discrete/pnt_factorial_ratio_higher_height/verify_span_identity.py
.venv/bin/python -B src/campaign/discrete/pnt_factorial_ratio_higher_height/family_search.py --bound 160 --three-bound 36 --gessel-bound 18 --max-exact-period 10000000
.venv/bin/python -B src/campaign/discrete/pnt_factorial_ratio_higher_height/divisor_lattice_screen.py
```

In the canonical research checkout, omit the leading `src/` from those four
paths.

The first two commands are fast standalone checks.  The latter two reproduce
the bounded searches and require NumPy/SciPy.  No command imports or executes
the Arena verifier.

## Frozen verifier and external policy

- Live verifier SHA-256:
  `fd76a069b269a521d6ded609bd79185bf859df778283bebc37719dfd15b1ded6`.
- Verifier bytes are not retained or executed.
- Soundararajan was discovered through Exa request
  `46effd356f06fc91ffcddbacc130c0a3` and read through Paperclip with line-pinned
  primary citations in `SOURCES.md`.
- The official arXiv source was downloaded GET-only to validate the dense
  tables, but is excluded from publication.
- No submission, post, comment, vote, issue, push, or author contact occurred.
- Locally authored/generated packet files are published under CodexProLong
  MIT; third-party papers and verifier are citation/hash metadata only and are
  not copied.
