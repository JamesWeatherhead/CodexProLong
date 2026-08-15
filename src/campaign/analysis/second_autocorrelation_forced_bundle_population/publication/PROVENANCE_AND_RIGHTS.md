# Provenance and rights boundary

## Included material

The Python, Markdown, JSON, and JSONL payloads in this packet are clean-room
lane material and are released under the included MIT License. The compact run
receipts were produced solely from recorded random seeds and the clean-room
analytic motif. No Arena candidate, retained prior-lane array, SimpleTES
coefficient, published coefficient table, or third-party candidate payload is
included.

`corpus_audit.json` is a sanitized metadata audit. It contains record hashes,
counts, aggregate statistics, and method tags, but retains zero coefficient
values and no thread/reply bodies. The 174,448,640-byte source SQLite snapshot
is not included and is identified by exact SHA-256 in the publication manifest.

The canonical 32,888-byte `best.npy` is also not included. It is a clean-room,
far-below-gate reference checkpoint, not a third-party candidate. Its exact NPY
and little-endian value hashes remain in the compact receipt. `source_replay.py`
reconstructs the array in memory from the authenticated seed/configuration,
checks both hashes, recomputes the independent SciPy formula, and writes no
candidate file. Thus the text-only packet is self-contained for source replay.

## Primary literature and code provenance

Paperclip line-pinned primary/full-text reads are recorded in
`literature.json` for Jaech--Joseph (2025), Burke et al. (2018), Boyer--Li
(2025), and ImprovEvolve (2026). Read-only Exa request identifiers and primary
license URLs are recorded there as well.

- `ajaech/autocorrelation_inequality`: MIT; provenance and description
  cross-check only, with no source or coefficients copied.
- NumPy: BSD-3-Clause project license; runtime dependency, not vendored.
- SciPy: BSD-3-Clause; independent replay dependency, not vendored.
- PyTorch: BSD-style/BSD-3-Clause project license; named only in the future
  H100 plan and not required by this packet.

The finite-branch maximin formula, analytic derivatives, motif generator, and
replay machinery were independently written from the published mathematical
objective and generic gradient-sampling concepts. No third-party source file is
embedded.

## Verifier and external-write boundary

Only the frozen verifier SHA-256 is recorded. Verifier source is absent, and no
Arena verifier was executed for this packet or its bounded pilot. The included
scorers are independent formula implementations, not the Arena verifier. No
Arena, GitHub, issue, comment, vote, post, submission, or other external write
occurred.
