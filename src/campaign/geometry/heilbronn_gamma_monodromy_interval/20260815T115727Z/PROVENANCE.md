# Provenance and license boundary

This publication packet is a project-authored analysis of the eleven-point
Heilbronn problem in a unit equilateral triangle. It contains no Arena API
payload, corpus database, verifier source, raw contact-homotopy run, credential,
or copied third-party paper or software package.

## Included material

The Python source, README, handoff, and this provenance note are project-authored
and distributed under the MIT license in `LICENSE`. The numerical JSON files are
outputs of that source. They are distributed with the packet under the same
license only to the extent the project has rights in their selection, structure,
and project-authored computation.

`derived_inputs.json` contains two narrow projections:

- a solver-refined 17-coordinate center of the active polynomial system, rather
  than a byte copy of the private seed artifact;
- 619 integer records encoding an active-equation index, incoming triple, and
  two status codes, rather than any raw pseudo-arclength result row.

These projections and the detached SHA-256 values are factual metadata. No
ownership or license assertion is made over underlying private source facts.
Their source license identifier is therefore `NOASSERTION`.

## Excluded private sources

The following source bytes are not redistributed. Logical identifiers replace
machine paths.

| Logical identifier | SHA-256 |
|---|---|
| `incumbent_seed_best_json` | `bb81f8055ff6bcf8127d0bf81f694aa78986b8fd5e2d8fe41b92c81b9c658850` |
| `distant_exchange_results_jsonl` | `d7afe047c49709d7c5c99d04fcca5d695b898a82a8f84e35c7ce607dd2b63fdc` |
| `pseudo_arclength_results_jsonl` | `bad3bc662ae9363894e3418fe4dc71a7ea90e13883b1956a7fa57ac463f77a91` |
| `research_corpus_sqlite3` | `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb` |

The pre-publication target manifest had SHA-256
`73eeb34b478c50cd468011812c83e267987f51a2889079ef56a5a29108f06e50`.
It was normalized into the portable v2 target manifest; the original is not
redistributed because it contained machine paths.

## Research references and dependencies

`literature_sources.json` contains only bibliographic facts, URLs, query request
IDs, and investigator-authored scope notes. Papers and web pages are not copied.
The offline replay performs no network access.

`public_replay.py` uses only the Python standard library. NumPy and mpmath are
not vendored; their packages and license texts are not part of this allowlist.
They are needed only for the optional scientific-generation scripts and are
declared in `requirements.txt`.

Dependency metadata, recorded without redistribution, is: CPython
`PSF-2.0`; NumPy `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`; and
mpmath `BSD-3-Clause`. Consult each upstream distribution for its authoritative
notices and transitive binary-library terms.

The bounded monodromy output is a historical, capped numerical probe. Its
wall-clock field and floating path tracking are not byte-reproducible claims.
The public replay instead checks the stored roots, all relevant polynomial
residuals and geometric filters, reflection orbits, and the exact rational
Krawczyk certificate.
