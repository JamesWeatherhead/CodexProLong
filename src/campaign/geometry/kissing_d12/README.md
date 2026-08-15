# Kissing number d12 / 841 reproducibility lane

This lane contains a gate-clearing, intended-domain reproduction of the
published 841-point configuration.  It did not search for or claim an
independent discovery.  A single controller submission attempt was rejected
with HTTP 409 because submissions are disabled; no leaderboard entry exists.
See [vinid/einstein-arena#59](https://github.com/vinid/einstein-arena/issues/59).

## Frozen result

- Offline-controller score: **0.0**.
- Live leader at replay: `2.0` (CHRONOS).
- Candidate: `runs/20260815T014818Z/candidate_841.json`.
- Candidate SHA-256:
  `236d3931724d28cf306ecbda064c1ffb84e8a106e363227f00e6d5b147eb4749`.
- Frozen verifier SHA-256:
  `eb043620439a6631451657013a12c66e55db43589431bcdad08e3b2189246ca8`.
- Controller receipt:
  `../../state/receipts/kissing-number-d12/20260815T014831730984Z-236d3931724d.json`.
- Controller receipt SHA-256:
  `fc97f183a72bcce542b05a6f82159392baf0769c6cf3408b6e8460cf6b2286a6`.

On the exact decimal strings in the JSON payload, an independent Decimal
implementation checked all 353,220 unordered pairs.  The maximum raw squared
norm is
`1.000000000000000463434005607747343212`; the minimum raw squared distance is
`1.00000012449713577230067209067745354864`, at zero-based pair `(413, 756)`.
The sufficient-condition margin is therefore
`1.2449713530886666648293011033664E-7`.

## Provenance

The paper describes the two 60-point blocks, 720 bridge vectors from a
1-factorization of `K_6`, flexible 48-systems, and a numerically obtained
841-point arrangement [8].  The candidate coordinates come from the authors'
official repository at commit
`eba37f0368f62828780d1f9d90315b367d2a612f`, file
`gram841_coordinates.txt`, whose SHA-256 is
`995264fe8be616cc546f04ef542dbf4ef6effe9ba5dfa4ceec1aa7e069f476a9`.
The repository has no `LICENSE` or `COPYING` file.  See `ATTRIBUTION.md` before
sharing any artifact.

The same upstream commit contains exploratory rank-12 Gram matrices for 842
and 844 points.  Their respective file hashes are
`3ad70d99caa67a6ff2f572224246440b651391c274eb9f426d78f68246cd1f0a`
and `2abc5d6ed2a75b48e5e7a66184f4d6cc55efbe0424d53c57a6629baefad11848`;
their maximum off-diagonal entries are `0.500901018602` and `0.5044042665`,
so neither is a zero-loss kissing configuration.

## Reproduce

From `/Users/jacweath/EinsteinArena/campaign`:

```sh
python3 geometry/kissing_d12/reproduce.py --offline --run-id REPLAY_ID
./arena verify kissing-number-d12 \
  geometry/kissing_d12/runs/REPLAY_ID/candidate_841.json
python3 geometry/kissing_d12/audit_corpus.py \
  --run-dir geometry/kissing_d12/runs/REPLAY_ID
```

`reproduce.py` uses the locally cached, hash-pinned coordinate file.  Omit
`--offline` once if the source file is absent; the script downloads only the
pinned raw coordinate file and verifies its SHA-256 before use.  It never
imports or executes the downloaded verifier.  The authoritative replay is
always `./arena verify`, which runs the frozen verifier through the offline
controller.

The complete retained-corpus audit covers 10/10 constructions, 6/6 threads,
and 13/13 replies from corpus database SHA-256
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.
Its frozen report is
`runs/20260815T014818Z/retained_corpus_audit.json` (SHA-256
`a59398c594ac598928ec9bb19f047cb60b488b2a9c22508e2a2f5b062a3239a1`).

--------
REFERENCES

[8] Rustem Takhanov, Zhenisbek Assylbekov, and Stanislav Yun. “Structure of
    kissing arrangements in $\mathbb R^{12}$ and a place for the 841st
    sphere.” *arXiv* (2026).
    https://paperclip.gxl.ai/citations/papers/arx_2606.18984#L1
