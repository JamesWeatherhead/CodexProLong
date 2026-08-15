# PSL-4 length-70 table recovery: quantified negative result

Frozen at `2026-08-15T08:18:02Z`.

This bounded, read-only recovery lane sought the complete historical table of 72 non-equivalent length-70 binary PSL-4 classes formerly linked from SignalsLab page `page_id=1779`. No complete table and no new length-70 class bytes were recovered.

The search made 40 Exa searches (518 returned results) and 6 Exa contents requests (47 requested URLs, 14 returned contents). Paperclip performed five exact corpus greps, two semantic searches, and three reads of the one relevant indexed arXiv paper. Twelve Sourcegraph searches and 16 GitHub API queries returned no new asset. Archive.org and Arquivo exact searches returned zero results. Sixty complementary Common Crawl index requests could not be evaluated because the index service returned an empty network response (`HTTP 000`); this is an outage receipt, not evidence of absence.

Two new historical leads were resolved:

- A 2014 thesis cites `signalslab.volgatech.net`. Current requests to its historical page variants resolve to the modern university homepage; Wayback and Arquivo had no capture of the target page.
- The DSPA-2013 proceedings index still lists the N<=70 paper, but marks it `N` (not posted). Its download CGI returns a generic three-page notice, not the paper. Three URL variants returned identical bytes.

A public 25-slide MarGrid presentation confirms the historical compute system and client release. One administration screenshot names PSL task executables but contains no output filename, class row, or candidate sequence; exact Exa, GitHub, and Sourcegraph searches for those identifiers returned no relevant match. The only plausible N=70 row found in the searchable corpus deduplicates to a payload already frozen by the prior lane. Its pinned local replay scored `1.3687174140805314`, above the strict gate `1.280726494964255`; no gate-clearer was found.

## Publication boundary

Only the exact files listed by `PUBLICATION_MANIFEST.json` are publication-eligible. They contain investigator-authored facts, URLs, query strings, request IDs, hashes, and aggregate results.

Raw Exa responses, Paperclip extracts, papers, proceedings notices, slide images, HTML, headers, archive responses, and replay payloads are excluded. Their licenses are absent, unclear, or do not grant redistribution here. The publication packet contains no third-party candidate sequence bytes, source text, images, executables, credentials, email addresses, or absolute workstation paths.

This receipt does not license the underlying third-party sources. A repository owner must apply an appropriate license to the original audit metadata before standalone redistribution.
