# Provenance and rights

## Clean-room boundary

The Python source and explanatory documentation in this packet were written
for this campaign without copying third-party implementation code or candidate
coefficients.  They are available under the MIT license in `LICENSE`.

The packet intentionally omits all candidate arrays, the hash-pinned Arena
verifier source, the frozen corpus database, credentials, environment dumps,
and host-private absolute paths.  The corpus audit retains hashes, public
record identifiers, scores, finite-vector features, duplicate groups, and an
aggregate discussion taxonomy.  It retains no discussion body, construction
author label, timestamp, or coefficient value.

## Factual and bibliographic metadata

`corpus_audit.json`, `receipt.json`, and `runs/20260815T124000Z/` primarily
record facts and numerical measurements.  No copyright claim is asserted over
third-party facts or public record identifiers.  `literature.json` contains
bibliographic facts, links, scope notes, and read-only request identifiers; it
does not contain paper text.

The cited papers remain governed by their respective publishers and authors.
They motivated method selection only.  No paper source code, table, figure,
coefficient list, or extended text is redistributed here.

## Dependencies

Dependencies are not vendored.  The reference run used Python 3.12.13, NumPy
2.5.2, and SciPy 1.18.0.  NumPy and SciPy use BSD-family project licenses.  The
self-contained receipt replay and publication self-test require only the
Python standard library; the numerical probes and unit tests require the
packages in `requirements.txt`.
