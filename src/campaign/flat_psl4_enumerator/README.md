# Exact length-70 PSL-4 neighborhood enumerator

This packet implements an outside-in, symmetry-reduced branch-and-bound for
binary sequences of length 70 whose every nonzero aperiodic autocorrelation has
absolute value at most four.  It was built to test whether three independently
published PSL-4 representatives hide an unexamined nearby class capable of
beating the live EinsteinArena flat-polynomial gate.

The search is exact inside each selected split subtree.  A single-lag bound
decomposes the lag graph into paths and computes the exact attainable
correlation progression from the fixed endpoints.  Negation, reversal, and
alternation symmetries are quotiented before answers are recorded.  The Python
regression test brute-forces more than 70,000 small partial states and verifies
that the bound never disagrees with direct completion.

## Frozen result

- Three source classes: Leukhin–Potekhin, Dimitrov–Baitcheva–Nikolov, and
  PslRK/Mertens.
- 24 nearest viable split-depth-12 tasks per class; 72 exact tasks total.
- 4,338,836,968 DFS nodes.
- Exactly three symmetry classes rediscovered—the three source classes.
- Zero novel class and zero candidate below the live strict gate
  `1.280726494964255`.

This is a **bounded negative result**, not a complete enumeration of all
length-70 PSL-4 sequences.  There are 678,165 viable split-depth-12 tasks; the
packet closes the 72 tasks selected by stable border-distance ordering.

## Reproduce

On macOS with Homebrew `libomp`:

```bash
clang++ -std=c++20 -O3 -Xpreprocessor -fopenmp \
  -I"$(brew --prefix libomp)/include" psl4_exact.cpp \
  -L"$(brew --prefix libomp)/lib" -lomp -o psl4_exact
./psl4_exact --self-test --moment-depth 30
../../.venv/bin/python -m unittest tests/test_exact_bound.py
../../.venv/bin/python freeze_receipt.py --output /tmp/flat-psl4-receipt.json
cmp receipt.json /tmp/flat-psl4-receipt.json
```

To recompute a journal, remove only that journal from a disposable copy and run
the corresponding command in [HANDOFF.md](HANDOFF.md).  The journal is
append-only, so rerunning in place safely resumes rather than duplicating work.

## Literature routing

Paperclip grounded the broader search design in Fekete/Littlewood structure and
exact low-autocorrelation enumeration:

- [Klurman–Lamzouri–Munsch, Fekete polynomial structure](https://paperclip.gxl.ai/citations/papers/arx_2306.07156#L9-L12,L64-L74)
- [Balister et al., constructive flat Littlewood polynomials](https://paperclip.gxl.ai/citations/papers/arx_1907.09464#L23,L32-L38,L79-L85)
- [Mertens, exhaustive low-autocorrelation search](https://paperclip.gxl.ai/citations/papers/arx_cond-mat9605050#L28-L67)
