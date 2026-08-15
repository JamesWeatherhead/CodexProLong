# Kissing number d=11 / 594 exact audit

## Result

**Yes: a domain-valid exact score-0 construction is already recoverable from
public EinsteinArena data.**  It is public solution **1492**, submitted by
**KawaiiCorgi** on 2026-04-10. The standalone recovered local payload is
`payload.json`, SHA-256
`b64f05c374548b2ff4a83deac3fe60d79b62d609f7d67d4986354efdf73bf6bf`.

This is not a float64 accident and does not merely exploit the verifier.  With
every JSON number interpreted as the exact rational represented by its decimal
lexeme, an exhaustive check of all `C(594,2) = 176,121` unordered pairs gives:

| Quantity | Exact result |
|---|---:|
| Shape / distinct vectors | `594 x 11` / `594` |
| Maximum raw squared norm | `4` |
| Minimum raw squared pair distance | `4` |
| Raw lemma margin | `0` |
| Maximum positive normalized cosine | `1/2` |
| Minimum normalized center distance squared | `4` |
| Exact 60-degree contact pairs | `17,088` |
| Normalized kissing violations | `0` |
| Frozen verifier score | `0.0` |

The sufficient lemma used by AlphaEvolve says that nonzero vectors satisfying
`min ||x-y|| >= max ||x||` yield a valid kissing configuration after radial
normalization [1].  Solution 1492 satisfies its squared form exactly, including
the allowed equality case.  The audit also independently checks the normalized
condition over `Q`: for each positive dot product,
`4 <x,y>^2 <= ||x||^2 ||y||^2`, with equality at the contacts.

## What the construction actually contains

The exact decomposition is:

- 16 integer axis rows of the form `+/- 2e_i`;
- 480 integer rows with four `+/-1` coordinates;
- 98 finite-decimal rational rows.

Thus 496 rows have squared norm exactly 4, while the other 98 have smaller
squared norms (minimum `399894019/100000000 = 3.99894019`).  There are 248
antipodal pairs.  This corrects one detail in discussion reply 849: the reply's
rigor conclusion is right, but its statement that all 594 norms equal 4 is not.
The verifier's exact branch nevertheless passes because it converts *every*
coordinate to an 80-digit `Decimal`; it does not actually require integer
coordinates, and the global raw distance/norm inequality holds.

## Exhaustive public-data audit

The frozen corpus contains every public record exposed for this problem at the
snapshot time:

- 99 solutions, all with shape `594 x 11`;
- exactly one recorded score-0 solution: id 1492;
- 25 discussion threads;
- 86 replies.

Every solution, thread, and reply was parsed and its canonical record hash was
replayed. The local `corpus_manifest.json` lists every covered id and hash. The
most relevant discussion sequence is:

- thread 192 identifies the `16 + 480 + 98` structure, but incorrectly calls it
  a float64 artifact;
- thread 200 repeats that claim;
- reply 847 points out the verifier's 80-digit Decimal arithmetic;
- replies 848 and 849 retract the artifact claim after an exact-rational check;
- thread 218 and reply 866 recognize the exact 594 construction.

The exhaustive audit resolves the dispute directly from the payload rather
than relying on any discussion assertion.  The pre-Arena literature cited by
the problem reaches 592 via Ganzhinov's explicit spherical code [2], then 593
via AlphaEvolve [1,3].  The exact 594 coordinates are recoverable from the
public Arena best-solutions endpoint, not from those earlier papers.

## Rank-1 tie semantics

**A second score-0 entry would not count as joint rank 1 under the current API.**
There is no live score-0 tie to observe directly, so this conclusion uses two
independent read-only checks:

1. The live API currently assigns exact best-score ties ordinal ranks `1,2`
   on `min-distance-ratio-2d` and `1,2,3` on `thomson-problem`.
2. The MIT-licensed leaderboard GET route sorts ties by `evaluated_at ASC` and
   unconditionally emits `rank: i + 1`; it has no score-zero special case [4].

Therefore, if another evaluated entry ties KawaiiCorgi at zero, the older entry
remains rank 1 and the later tie is rank 2. Frozen response hashes and rows are
in the local `live_api_evidence.json`.

## Reproduction

Offline replay from the full local campaign checkout (no network):

```bash
python3 campaign/kissing_d11_594_audit/audit.py
```

Refresh the GET-only live evidence as well:

```bash
python3 campaign/kissing_d11_594_audit/audit.py --refresh-live
```

The script checks the frozen corpus and verifier hashes before doing any work,
extracts solution 1492, preserves exact decimal coordinates, evaluates the
frozen verifier in a fresh import, exhaustively checks the geometry over
`fractions.Fraction`, and atomically regenerates all JSON artifacts. It makes no
Arena or GitHub writes. The compact audit receipt is published separately from
the unlicensed coordinate payload.

The public research-diary mirror includes this audit code, source hashes, and a
sanitized receipt, but deliberately excludes the coordinate payload and raw
submission corpus because no redistribution license was found. A public-mirror
checkout therefore documents the exact procedure and expected hashes; a full
geometry rerun additionally requires retrieving the cited public Arena record.

## Provenance and rights

The coordinates are attributed to KawaiiCorgi, EinsteinArena solution 1492.
EinsteinArena intentionally exposes full evaluated submissions through its
public best-solutions API, but no explicit license for user-submitted solution
content was found.  This audit therefore records and verifies the construction
without asserting broader republication rights.  The EinsteinArena platform
source and frozen verifier are MIT-licensed.  Paper and data-source license
details are recorded in [`LICENSES.md`](LICENSES.md).

## References

1. Novikov et al., *AlphaEvolve: A coding agent for scientific and algorithmic
   discovery*: the 593-vector result and the exact normalization lemma
   ([Paperclip full text, lines 236-246](https://paperclip.gxl.ai/citations/papers/arx_2506.13131#L236-L246)).
2. Ganzhinov, *Highly symmetric lines*: the explicit 592-vector construction in
   `R^11` ([Paperclip full text, lines 231-233](https://paperclip.gxl.ai/citations/papers/arx_2207.08266#L231-L233)).
3. Georgiev, Gomez-Serrano, Tao, and Wagner, *Mathematical exploration and
   discovery at scale*: historical bounds and AlphaEvolve's numerical-to-exact
   workflow ([Paperclip full text, lines 145-151](https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L145-L151)).
4. EinsteinArena leaderboard GET route at commit `98073fca`, lines 14-37
   ([GitHub](https://github.com/vinid/einstein-arena/blob/98073fca26654d048d70acdfe1e319a23e8e41c6/web/src/app/api/leaderboard/route.ts#L14-L37)).
