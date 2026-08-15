# Reproducible Paperclip query log

Run `paperclip skill` first in any new session. The commands below contain no
credential and use only public corpus content.

## Health and routing

```bash
paperclip config --sources-list
paperclip search -s arxiv "autoconvolution" -n 10
paperclip lookup arxiv 1903.08731 -n 10
paperclip lookup title "Three Convolution Inequalities on the Real Line with Connections to Additive Combinatorics" -n 10
paperclip grep -m 20 --exhaustive "Three convolution inequalities" /papers/
paperclip head -n 20 /papers/arx_1903.08731/content.lines
```

Observed 2026-08-15:

- config reports healthy API-key authentication, a reachable server, and the
  default PMC/bioRxiv/medRxiv/arXiv sources;
- all three arXiv search/lookup forms above return no documents;
- corpus-wide grep finds the arXiv document; and
- direct `head`/`cat` reads its line-numbered full text.

The persisted local `cli_cwd` was `/papers/`. It was reset to `/` in
`~/.paperclip/config.json`; this fixes the unrelated `Unknown command: cd` and
empty-output behavior. Do not commit `~/.paperclip` or any credential file.

## Core full-text reads

```bash
paperclip bash 'head -n 128 /papers/arx_2511.02864/content.lines | tail -n 36'
paperclip bash 'head -n 157 /papers/arx_2511.02864/content.lines | tail -n 29'
paperclip bash 'head -n 207 /papers/arx_2511.02864/content.lines | tail -n 21'
paperclip bash 'head -n 398 /papers/arx_2511.02864/content.lines | tail -n 40'
paperclip bash 'head -n 521 /papers/arx_2511.02864/content.lines | tail -n 43'
paperclip bash 'head -n 644 /papers/arx_2511.02864/content.lines | tail -n 50'

paperclip head -n 38 /papers/arx_2508.02803/content.lines
paperclip head -n 24 /papers/arx_2512.14505/content.lines
paperclip head -n 30 /papers/arx_2305.18253/content.lines
paperclip bash 'head -n 169 /papers/arx_1903.05767/content.lines | tail -n 16'
paperclip head -n 35 /papers/arx_1712.04438/content.lines
paperclip head -n 2 /papers/arx_2602.10233/content.lines
paperclip head -n 2 /papers/arx_2606.18984/content.lines
paperclip head -n 2 /papers/arx_2606.10402/content.lines
```

## Changed-topology circle and Heilbronn follow-up

```bash
paperclip search -s arxiv "variable radius circle packing contact graph global rearrangement" -n 20
paperclip search -s arxiv "Heilbronn triangle mixed integer exact coordinates" -n 20
paperclip head -n 96 /papers/arx_1701.00541/content.lines
paperclip cat /papers/arx_2601.18005/meta.json
paperclip cat /papers/arx_2601.18005/content.lines
paperclip head -n 50 /papers/arx_2511.17592/content.lines
paperclip cat /papers/arx_2603.11107/content.lines
```

Observed 2026-08-15:

- PAS-PCI provides explicit changed-basin operators: normalized pain ranking,
  largest/best-matching void relocation, paired placement into a split narrow
  void, one-step tabu memory, cross-size swaps, and LBFGS repolishing;
- FlowBoost's Paperclip ingest currently contains its abstract only. That
  abstract identifies stochastic local search, geometry-aware generation, and
  direct reward guidance; the canonical arXiv HTML and official code were read
  separately to inspect its fixed-centers radius LP and center perturbations;
- GigaEvo reproduces the established n=26 circle geometry at rounded precision
  and the same n=11 Heilbronn basin slightly below the leading score, useful as
  a negative result against repeating generic evolutionary polishing; and
- the 2026 Heilbronn MINLP/exact-coordinate paper certifies configurations only
  through n=9. Its boundary symmetry breaking and numerical-to-symbolic
  workflow transfer to the Arena n=11 task, but it is not an n=11 solution.

## DOI fetch limitation

```bash
paperclip lookup doi 10.1017/S0963548308009085 -n 10
paperclip fetch https://doi.org/10.1017/S0963548308009085 --into /clipboard/einstein-literature/
```

Lookup returned no corpus document. Fetch resolved the correct publisher URL,
but Cambridge served a temporary-disruption HTML page instead of the paper;
the capture was soft-deleted. `rookiepy` was not installed, so Paperclip also
reported that institutional browser cookies were unavailable. No claim in this
packet depends on that failed capture.
