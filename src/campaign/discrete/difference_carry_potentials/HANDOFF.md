# Handoff: unbounded fixed-core carry potentials

## Decision

Freeze as a bounded exact no-go. There is no payload to verify or submit.

The exact result closes every 360-point integer construction whose residue
support modulo 8011 is exactly a global translate of the attributed 90-residue
core of public solution 634, while allowing arbitrary unbounded and
independent finite nonempty height supports in every residue column. None can
cover the one missing difference `49,110` while retaining `1..49,109`.

Formally, for frozen core `R`, the family contains every
`A={c+r+8011*h : r in R, h in H_r}` with `c in Z`, finite nonempty
`H_r subset Z`, and `sum |H_r|=360`. No sign, span, shell, common-shape, or
height-range condition is imposed.

This is materially different from:

- affine Singer-orbit/cut sweeps and point swaps;
- arbitrary supports restricted to shells `0..7`;
- interval and Wichmann/Leech constructions;
- quadratic relative-graph embeddings;
- unrestricted heuristic global evolution;
- the 22 finite exact-LNS coordinate pools.

It closes unbounded carry potentials over the fixed core, rather than a
coordinate neighborhood or bounded shell box.

## Exact reduction

The full exhaustive public corpus was read before opening the lane: 23
difference-bases constructions, 11 threads, and 78 replies in the FTS5
database with SHA-256
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.
The live verifier remained
`a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`.

Measured facts:

- the core has 90 residues and exactly 8,010 unique ordered nonzero cyclic
  differences;
- literal target `49,110` partitions the 4,005 unordered residue pairs into
  1,043 requirements `[-6,6]`, 2,961 requirements `[-6,5]`, and one
  requirement `[-7,5]` on the pair `(6967,0)`;
- the `[-6,6]` boundary graph is connected, has minimum degree 14, and
  maximum distance 7 from residue 0;
- the total-size/product count forces exactly four heights in every column;
- every boundary-compatible normalized column has span at most 12, yielding
  exactly 220 shapes;
- exhaustive compatibility enumeration gives 238 allowed triples for each
  of the low and high boundary relation types;
- the necessary relaxation omits all 2,961 middle-pair constraints and every
  residue-zero constraint, yet is still `INFEASIBLE`.

## Durable run

Retained run: `runs/20260815T121057Z/`.

- formula SHA-256:
  `0fcb2054f099e398959e5318033f8969582becb5d6bbce072c40a6d455b0e4b4`;
- 1,224 variables, 2,089 constraints, 1,928,061 serialized bytes;
- OR-Tools 9.14.6206, one worker, seed 20260815, 30-second bound;
- original solve: `INFEASIBLE`, 1.604 seconds, zero branches/conflicts;
- fresh audit solve: `INFEASIBLE`, 1.570 seconds;
- separately authored local-import-free reconstruction: byte-identical model
  and fresh `INFEASIBLE` solve;
- five semantic/unit tests pass;
- no candidate-like file exists in the run;
- Arena actions, external writes, submissions, posts, comments, issues, and
  GitHub actions: zero.

The per-run `manifest.json` authenticates the five portable frozen run files;
the original solve payload and model are preserved within them. `audit.json`
records the later fresh replay. Top-level `MANIFEST.json` is a byte-identical
local alias of `PUBLICATION_MANIFEST.json`.
The stdlib-only copied-allowlist test passes in both canonical
`campaign/discrete/...` and public `src/campaign/discrete/...` layouts.

For publication portability, machine-local launch paths in `config.json`, its
hash-chained config event, and `audit.json` were replaced with stable
repository-relative paths; the event hashes, checkpoint, and run manifest
were then recomputed. The solver response, mathematical facts, summary, and
serialized formula bytes were not changed.

The MIT license applies to repository-authored code and documentation only.
The attributed 90-residue core is marked as derived factual metadata, with no
ownership or license claim over Arena API content. No full public solution
payload, verifier source, snapshot, credentials, or candidate array appears in
the allowlist.

## Scope boundary

Allowed claim:

> No 360-point integer set whose residue support modulo 8011 is exactly a
> global translate of the leader's 90 residue classes can cover every
> difference through 49,110, even with arbitrary unbounded and independently
> chosen finite integer height supports.

Do not claim optimality, closure of changed or incomplete residue supports,
closure of other moduli, closure of sizes other than 360, or solver-independent
certified unsatisfiability. CP-SAT emitted no DRAT/LRAT proof; the retained
evidence is a deterministic finite formula, an exact derivation, an
`INFEASIBLE` solver result, and two reconstruction/replay implementations.

## Reopen criterion

Only reopen with a changed residue core/topology, not more carry ranges or a
larger height bound on this core. The reduction already permits unbounded
heights and arbitrary column shapes.
