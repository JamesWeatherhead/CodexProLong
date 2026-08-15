# Classical Wichmann difference bases: exact Arena audit

This packet reconstructs the nondegenerate classical Wichmann complete-ruler
family from its finite gap formula, exhausts every legal base parameter with at
most 2,000 marks, reduces every extension analytically, and checks each selected
frontier construction by an integer difference bitset and the literal frozen
Arena scoring rule.

Outcome: **no gate-clearer**. The family is genuinely different from the prior
Singer four-block lift, but it is much weaker at the live scale.

| Frontier | Parameters `(r,s;i,j)` | Marks | Exact coverage | Exact score |
|---|---:|---:|---:|---:|
| Nondegenerate global family best | `(1,3;0,0)` | 10 | 36 | `25/9 = 2.7777777777777777` |
| Best at 360 marks | `(59,121;0,0)` | 360 | 43,318 | `64800/21659 = 2.991827877556674` |
| Best in the declared 49k window `[49000,49200]` | `(63,128;0,0)` | 383 | 49,023 | `146689/49023 = 2.992248536401281` |
| Best with coverage at least 49,110 | `(64,129;0,0)` | 388 | 50,310 | `75272/25155 = 2.992327569071755` |

The live leader is `2.639027469506608`; the strict gate is
`2.6390274685066077`. At 360 marks, the Wichmann maximum is 5,792 differences
short of the required coverage 49,110.

The `r=0,s=1` degeneration is `{0,1,4,6}` with score `8/3`. It is retained only
as a control because this four-mark seed already underlies the prior
Leech--Golay/Singer campaign; it is not claimed as new work here.

## Construction and exhaustive reduction

For `r>=1` and `s>=0`, the gap word is

```text
1^r, r+1, (2r+1)^r, (4r+3)^s, (2r+2)^(r+1), 1^r.
```

It has `m0=4r+s+3` marks and length
`L0=4r(r+s+2)+3s+3`. An extended Wichmann ruler appends `i` gaps of
length `r+1` and one final gap `j<=r+1`. For `e` extra marks, the greatest
possible length is therefore `L0+e(r+1)`.

Writing `m=m0+e` and `L=(r+1)m+c` gives
`c=r(3s+1)+2s>0`. Hence `m^2/L` is strictly increasing in `e` for every fixed
base. This proves that the global family optimum has no extension and that the
smallest extension reaching a declared coverage floor or window is optimal for
that base. The sweep then checks all 498,002 legal `(r,s)` pairs.

## Reproduce

From the public `CodexProLong` repository root:

```bash
python3 src/campaign/discrete/difference_wichmann_leech/test_packet.py
```

From the canonical research checkout instead:

```bash
python3 campaign/discrete/difference_wichmann_leech/test_packet.py
```

The public test is network-free, standalone, and does not import or execute a
downloaded verifier. It regenerates the sweep and bitset receipts, compares the
frozen run byte-for-byte at the JSON-object level, and verifies every file hash
in `PUBLICATION_MANIFEST.json`.

No Arena or GitHub mutation occurred in this lane.
