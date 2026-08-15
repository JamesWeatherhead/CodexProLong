# Provenance

## Literature

Li and Yip define difference representation functions and distinguish exact
difference sets from difference bases [1]. Their quotient/direct-product lemma
shows why a cyclic residue core plus independent quotient coordinates is a
natural construction surface [1]. This lane does not transfer their
finite-abelian bounds to the Arena objective; it derives every literal integer
carry requirement directly.

Paperclip was loaded with `paperclip skill`, searched explicitly, and the
supporting full-text lines were read before the model was written.

Exa was also queried read-only. It located Banakh and Gavrylkiv's primary
arXiv record, *Difference bases in cyclic groups* (arXiv:1702.02631v6), and
the ar5iv full text. The official record defines difference bases and records
the cyclic-group setting; Theorem 4.7 constructs interval bases by coupling a
cyclic basis to quotient layers with explicit carry handling. Primary links:

- https://arxiv.org/abs/1702.02631
- https://ar5iv.labs.arxiv.org/html/1702.02631

The present carry-table CSP is a clean-room specialization to the literal
Arena prefix and is not code or data copied from either paper. Exact Exa query
provenance is frozen in `EXA_PROVENANCE.json`.

--------
REFERENCES
[1] Shuxing Li and Chi Hoi Yip. "Generalized additive bases and difference bases for Cartesian product of finite abelian groups." *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L5-L13,L73-L81

## Arena inputs

- Complete exhaustive public corpus database:
  `research_corpus/snapshots/20260815T003306Z/corpus.sqlite3`, SHA-256
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.
- Difference-bases scope read in full: 23 construction records, 11 threads,
  and 78 replies.
- Public leader: solution 634, referenced by id, score, payload hash, and its
  attributed normalized residue core. The full 360-coordinate third-party
  payload is not redistributed.
- Frozen verifier path:
  `state/problems/difference-bases/a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585.py`.
  It is hash-checked but never imported or executed by the solver.

## Conduct

Research access was GET/read-only. No credentials, source downloads, public
payload arrays, Arena writes, submissions, posts, comments, issues, commits,
or pushes were produced. Every generated file is confined to
`campaign/discrete/difference_carry_potentials/`.

## Independent replay

`cleanroom_replay.py` was separately authored and imports no code from
`solver.py`, `audit.py`, or any other local lane module. Starting only from the
frozen residue metadata, it independently reconstructs the cyclic-difference
check, literal carry intervals, boundary graph, cardinality reduction, 220
normalized shapes, both 238-row tables, all variable domains and constraints,
and the deterministic CP-SAT bytes. The bytes equal the frozen `model.pb`, and
a one-worker fresh solve returns `INFEASIBLE`. The copied-allowlist harness
repeats that reconstruction and solve in both canonical and `src/` layouts.

## License boundary

`LICENSE` applies to the clean-room code and repository-authored
documentation. The 90 normalized residues in `frozen_inputs.json` are derived
factual metadata from attributed public solution 634; the packet makes no
copyright or license-ownership claim over EinsteinArena API content. The full
third-party construction, discussion bodies, corpus snapshot, and verifier
source are excluded. `PUBLICATION_MANIFEST.json` records the license class of
every copied file.
