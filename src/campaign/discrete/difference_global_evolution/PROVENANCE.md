# Provenance and literature

The implementation is clean-room and repository-authored. No third-party
source code or construction array is copied into the public packet.

## Literature-grounded operators

1. The ALNS cycle and its random/related destroy plus random/greedy repair
   families were grounded in the full-text Paperclip record
   [PMC11470144, lines 115–149](https://paperclip.gxl.ai/citations/papers/PMC11470144#L115-L149).
   We used the general destroy/repair/adaptive-weight pattern, not source code.

2. The ruin/recreate and regret-style repair concepts were grounded in the
   full-text Paperclip record
   [PMC12832582, lines 130–214](https://paperclip.gxl.ai/citations/papers/PMC12832582#L130-L214).
   Again, only the algorithmic ideas were used.

3. Iván Dotú and Pascal Van Hentenryck, “A Simple Hybrid Evolutionary
   Algorithm for Finding Golomb Rulers,” IEEE CEC 2005, pp. 2018–2023,
   [DOI 10.1109/CEC.2005.1554943](https://doi.org/10.1109/CEC.2005.1554943),
   motivated feasibility-first search, mark/gap recombination, local-search
   mutation, and diversity restarts.

Golomb rulers optimize distinct differences, whereas Difference Bases require
complete interval coverage. The literature therefore informed operators only;
it is not cited as a theorem or construction for this Arena objective.

## Arena-derived inputs

The private frozen snapshot supplies public leader submission `634` and its
360-mark payload. The public packet retains only the submission id, score,
coverage, verifier/payload/snapshot hashes, and compact derived metrics. The
snapshot and every construction array are excluded.

The scaled Wichmann donor is generated clean-room from its finite gap formula;
no external array is embedded. It was used only as a low-weight crossover and
repair donor. In the smoke screen it had coverage 77 after scaling and did not
produce a competitive seed.
