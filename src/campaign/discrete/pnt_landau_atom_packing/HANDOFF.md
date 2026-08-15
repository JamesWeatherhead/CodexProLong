# Frozen handoff: exact Landau atom-packing dual

## Result

No gate-clearer.  Among every nonnegative combination of the 52 sporadic
Bober height-one step functions and every integer dilation `1 <= d <= 100`,
the exact optimum is the undilated line-31 Chebyshev atom:

```text
score = 0.9212920229340907809134084499...
```

This covers 5,200 atoms.  A 23-point nonnegative dual measure upper-bounds
every atom's score and has objective symbolically identical to Chebyshev.  The
proof reconstructs each score as a rational linear combination of prime
logarithms, solves the 23x23 dual basis over `fractions.Fraction`, and proves
all signs using outward rational bounds for the atanh series for `log`.

There are 23 exact equality constraints and 5,177 strict inequalities.  The
smallest rigorous strict slack is `0.00015886800044671016`; the smallest dual
weight is at least `0.00023381674270912052`.

## Reproduce from the public repository root

```sh
python3 src/campaign/discrete/pnt_landau_atom_packing/prove_dual.py
```

In the canonical research checkout, omit the leading `src/`:

```sh
python3 campaign/discrete/pnt_landau_atom_packing/prove_dual.py
```

`prove_dual.py` uses only the Python standard library and the packet-local
52-row derived parameter table.  `search.py` preserves the SciPy
constraint-generation route that discovered the basis; its output alone is
not used as a proof.

## Scope

The theorem is exact for nonnegative real combinations of the 52 sporadic
atoms at integer dilations through 100.  It does not cover negative atom
weights, the three infinite Bober families inside a joint packing, dilations
above 100, or unrelated support identities.  The sibling complete-class audit
does prove the best *individual* member of all three infinite families.

No Arena submission, verifier execution, GitHub write, discussion post, issue,
or third-party code execution occurred in this lane.
