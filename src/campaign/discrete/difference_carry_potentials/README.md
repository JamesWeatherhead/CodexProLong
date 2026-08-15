# Difference Bases: exact unbounded carry potentials

This isolated lane closes a genuinely larger fixed-core family than the prior
shell and local-repair searches. It found no candidate and performed no Arena,
GitHub, discussion, issue, or submission mutation.

The live leader has 360 points, covers `1..49,109`, and scores
`129600/49109 = 2.639027469506608`. At the live `1e-9` gate, another
360-point set clears first place exactly when it also covers the single next
difference `49,110`.

## Exact family closed

Fix only the leader's 90-element perfect cyclic residue core `R` modulo
`m=8011`. Precisely, the closed family consists of every finite set

```text
A = {c + r + 8011*h : r in R, h in H_r},
```

where `c` is any integer, every `H_r` is an arbitrary finite nonempty subset
of the integers, and `sum_r |H_r| = 360`. Thus the residue support is exactly
a global translate of `R`.

The heights need not lie in `0..7`, need not be translates of `{0,1,4,6}`,
need not share a shape, have no span bound, and may be negative (a harmless
global translation makes a finite construction nonnegative). Distinctness is
the ordinary set condition within each `H_r`.

No member of this family covers every difference through `49,110`.

## Why the reduction is finite and exact

The core is a `(8011,90,1)` cyclic difference set, so each nonzero residue has
one ordered residue-column witness. For an actual positive residue gap `g`,
literal coverage through `49,110` forces a consecutive set of height
differences:

- `[-6,6]` for 1,043 low-boundary pairs;
- `[-6,5]` for 2,961 middle pairs;
- `[-7,5]` for the unique high-boundary pair `(6967,0)`.

Every pair therefore needs at least 12 distinct cross-height differences.
The exact cardinality count rules out minimum column sizes 1 and 2. A
size-3 column would force all other columns to have size at least 4, leaving
room for only one size-5 column, but its minimum low-boundary degree is 14 and
each of those neighbors must have size at least 5. Thus all 90 columns have
exactly four heights.

On a 13-value boundary edge, at least 13 of the 16 cross pairs land in an
interval of diameter 12. Any two points on one side share an opposite point
among those in-interval pairs, so their separation is at most 12. Every column
touches the connected low-boundary graph, hence every normalized four-height
shape is one of exactly `C(12,3)=220` shapes.

The solver exhaustively enumerates compatible shape-pair/translation triples:
238 for `[-6,6]` and 238 for `[-7,5]`. It then builds a necessary relaxation
containing all 1,043 low-boundary edges and the unique high-boundary edge while
deliberately omitting all 2,961 middle edges and all residue-zero requirements.
Even this relaxation is `INFEASIBLE`.

This is a CP-SAT exact finite-model result, not a DRAT/LRAT proof certificate.
`cleanroom_replay.py` imports no local lane code: it independently derives the
edge partition, cardinality inequalities, shapes, tables, variable bounds,
constraints, and deterministic model bytes, then reproduces `INFEASIBLE` with
one worker. Its reconstructed bytes exactly equal the frozen formula.

## Frozen evidence

The retained run is `runs/20260815T121057Z/`.

- OR-Tools: 9.14.6206, one worker, 30-second cap;
- solve status: `INFEASIBLE` in 1.604 seconds, zero branches/conflicts after
  presolve;
- fresh replay: `INFEASIBLE` in 1.570 seconds;
- model: 1,224 variables, 2,089 constraints, 1,928,061 bytes;
- model SHA-256:
  `0fcb2054f099e398959e5318033f8969582becb5d6bbce072c40a6d455b0e4b4`;
- unchanged verifier SHA-256:
  `a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`.

## Reproduction

From this directory, using a Python environment with OR-Tools 9.14.6206:

```sh
python3 -m unittest -v test_solver.py
python3 audit.py \
  runs/20260815T121057Z --seconds 30
python3 cleanroom_replay.py --seconds 30
python3 test_packet.py
python3 copied_allowlist_test.py
```

To create a new timestamped run, omit `--run-dir`:

```sh
python3 solver.py \
  --seconds 30 --seed 20260815
```

## Limits

This result does not constrain a changed residue core, residues outside the
fixed 90-column core, a different modulus, sizes other than 360, or global
optimality. Those are the only honest reopening directions for this lane.

`test_packet.py` uses only the Python standard library and runs from its own
directory, so the exact allowlist is portable. `copied_allowlist_test.py`
copies only that allowlist into both `campaign/discrete/...` and
`src/campaign/discrete/...` temporary layouts, runs both the stdlib integrity
test and the independent formula reconstruction/solve in each, verifies that
no extra file was created, and removes the temporary copies. The MIT `LICENSE`
covers only the repository-authored code/documentation; `frozen_inputs.json`
labels the attributed residue core as derived factual metadata without
asserting license ownership over Arena API content.
