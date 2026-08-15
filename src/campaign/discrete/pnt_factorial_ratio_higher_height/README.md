# PNT higher-height factorial-ratio screen

This packet is a bounded, exact-replay search of height-two and height-three
Landau step functions motivated by primary factorial-ratio literature.  It
found no improvement: the best exact construction is the repeated Chebyshev
identity at score `0.9212920229340907809...`.

Start with `HANDOFF.md`. From the public `CodexProLong` repository root, run:

```sh
/usr/bin/python3 -B src/campaign/discrete/pnt_factorial_ratio_higher_height/verify_best.py
/usr/bin/python3 -B src/campaign/discrete/pnt_factorial_ratio_higher_height/verify_span_identity.py
```

In the canonical research checkout, omit the leading `src/`:

```sh
/usr/bin/python3 -B campaign/discrete/pnt_factorial_ratio_higher_height/verify_best.py
/usr/bin/python3 -B campaign/discrete/pnt_factorial_ratio_higher_height/verify_span_identity.py
```

The publication packet contains only locally authored/generated code, data,
and metadata under MIT.  Primary papers and the live verifier are cited or
hash-pinned but not copied or executed.
