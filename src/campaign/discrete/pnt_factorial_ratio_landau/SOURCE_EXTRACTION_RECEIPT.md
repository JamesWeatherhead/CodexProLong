# Official-source extraction receipt

Retrieved 2026-08-15 using GET-only requests.

- Official abstract: <https://arxiv.org/abs/0709.1977>
- Official source endpoint: <https://export.arxiv.org/e-print/0709.1977>
- Server source filename: `arXiv-0709.1977v1.tar.gz`
- Source archive SHA-256:
  `0d7e59ea681a91e80dbd0d643a0859b10d5ec7426d015301e8f606a2669ff982`
- Main TeX SHA-256:
  `635d1794774eac9fbf654fc70331a4e5cdaae23e14e106f98794815310956000`
- `table3.latex` SHA-256:
  `72e4c6c97179e474eb0b988f3c17b2a3c0d0b213082f6c7b14381d1a7365031b`
- Clean derived 52-row JSON SHA-256:
  `016c250ff6b2b9dae71fe96b0fc0e6f9ddf04b73c1acb8ba3a620cbde620162d`

Main-source lines 288-314 state Theorem 1.2 and its three family hypotheses;
lines 1427-1468 introduce the classification tables and include
`table3.latex`.  The table's lines 2-1016 contain rows 1-52; OCR-missing rows
25-44 are at lines 430-849.  All extracted rows pass exact height, balance,
gcd, cross-cancellation, and full-period checks in `screen_bober.py`.

The downloaded source bytes remain excluded research inputs.  The published
JSON is a clean, locally generated transcription of factual integer parameter
sets; no paper prose, TeX, figures, or verifier source is copied.
