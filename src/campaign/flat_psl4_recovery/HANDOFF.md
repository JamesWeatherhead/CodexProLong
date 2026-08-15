# Flat PSL-4 recovery handoff

Frozen 2026-08-15. All remote work was GET-only. There were no Arena or
GitHub writes, author contacts, purchases, posts, votes, or submissions.

## Outcome

The historical complete length-70 PSL-4 table was **not** recovered. Three of
the reported 72 non-equivalent classes were recovered from independent public
sources. None improves the live Flat Polynomials leader, and no payload in this
packet is authorized for submission.

- Frozen verifier SHA-256:
  `ff991bd84aec2b5b5d44f58a68dba00f961e01d517ec1de3225e0902f0f2fce2`
- Live leader #2475: `1.2807274949642549`
- Strict gate: `< 1.280726494964255`
- Verifier semantics: exactly 70 coefficients in `{-1,+1}`, `np.poly1d`,
  `np.linspace(0,2*pi,1_000_000)`, divided by `sqrt(71)`.

Exact independent replays:

| candidate | exact score | gap above gate | canonical payload SHA-256 |
|---|---:|---:|---|
| best printed-source neighbor, N=71 delete position 70 | 1.2809320527987995 | 0.00020555783454456744 | `60ba7b635d0815b6f031c358d8d0ce056132a67f267f250bfc7e8d5f9fab9c50` |
| Leukhin--Potekhin 2013 N=70, `01C2FFD4AF33356596` | 1.309817443680567 | 0.029090948716312015 | `f95180d9b80ef1329f0e4118aa0c06fb6b2a147fd9f6625fbc51768629e60d9c` |
| Dimitrov--Baitcheva--Nikolov 2021 N=70, `2B5AAE6765E79B600F` | 1.3687174140805314 | 0.08799091911627643 | `69ee18c669959c2c1026c81d28058c3f15ee3eb6b747090ff0e47cd2ed2ab0a7` |
| PslRK/Coxson--Russo N=70, `1A133B4E3093EDD57E` | 1.3701428391952217 | 0.08941634423096678 | `5fd8d6e5ee02cf4d54e9cd85b2bee3c18f413cc0c91bd375d4d102dd17e2d77a` |

Each receipt is under `receipts/`. A second existing replay implementation at
`campaign/analytic/flat_global/exact_replay.py` reproduced all three highlighted
scores and hashes.

## What was recovered

1. The former SignalsLab hierarchy is now pinned. Its 2014 Wayback sitemap
   places `page_id=1779`, “Minimum peak sidelobe sequences (PSL-4),” beneath
   Binary / Optimal by minmax criteria. The page itself and its attachment were
   not captured.
2. The PslRK repository is mirrored at commit
   `91ddd173e221073f90086d7a0163bdedcc6b5e6b`. Its 169-row catalog contains
   exactly one N=70 code, identical to Coxson--Russo 2025 Table 4.3. The only
   exhaustive XML dumps are N=49 and N=50. Three of four GitHub fork heads are
   identical to upstream; the fourth is older. GitLab has no forks. Full `git
   fsck` found zero unreachable objects.
3. Potekhin's 2014 dissertation lead is resolved. The public 17-page abstract
   explicitly reports complete optimal sets through N=80, but says the thesis
   appendices provide *examples* of optimal sequences. RSL record 01007860659
   confirms a digitized 184-page scan, but its access notice limits the full
   text to RSL and virtual reading rooms. The direct full-PDF path serves that
   notice; Wayback and sampled Common Crawl indexes contain no public scan.
4. The surviving papers, SETA 2014 chapter, Nunn--Coxson paper, 2025 book
   snippet, OEIS entry, Paperclip corpus, and public code searches expose class
   counts or one representative per length—not the 72-class table.

The SHA-pinned evidence is in `source_manifest.json` (20 artifacts; manifest
SHA-256 `1000d7c68c168481e906b9cc62248b5fbfb450d036cd74d7e03f45a5bbf8f03a`).
The detailed quantified no-go is `archive_audit.json` (SHA-256
`e151892821f25c73ae39c986cc43174a57ac196c7903c50fbc1a432f27472c14`).

## Bounded construction screen

`screen_printed_neighbours.py` uses eleven independently printed PSL-4 codes at
lengths 69--72. It generates every one-symbol insertion from N=69, direct N=70
code, one-symbol deletion from N=71, and two-symbol deletion from N=72.

- 1,657 unique length-70 candidates
- 32,768-point FFT ranking grid
- 64 literal one-million-point verifier replays
- best score `1.2809320527987995`
- zero gate clearers

The complete screen receipt is `printed_neighbour_screen.json`, SHA-256
`84fb4cf3a379384b07c912d31664ffa053591ce55027456a235de962269bc5ff`.
Its best row is symmetry-equivalent to the former Arena leader, so this route
does not reveal a new basin.

## Reproduction

```bash
cd /path/to/EinsteinArena

# Verify every cached source hash.
.venv/bin/python campaign/flat_psl4_recovery/build_source_manifest.py

# Rebuild the bounded printed-source screen.
.venv/bin/python campaign/flat_psl4_recovery/screen_printed_neighbours.py \
  --grid 32768 --exact-top 64 \
  --out campaign/flat_psl4_recovery/printed_neighbour_screen.json

# Literal live-verifier replay of the closest recovered construction.
.venv/bin/python campaign/flat_psl4_recovery/exact_replay.py \
  campaign/flat_psl4_recovery/payloads/best_printed_neighbor_n71_delete70.json \
  --receipt /tmp/flat-psl4-replay.json
```

## Highest-EV next lead

The best archival route is a lawful public WordPress SQL/media backup or
institutional export containing SignalsLab `page_id=1779`. The sitemap proves
the exact page existed, and a single recovered attachment would enable a finite
72-class exact replay.

If no such public backup surfaces, the computational fallback is not another
local flat-polynomial search: port the retained outside-in PSL-4 branch-and-bound
enumerator to bit-sliced/GPU C++, enumerate normalized classes, and use the
published count 72 as the completion certificate before verifier replay.
