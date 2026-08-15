# Provenance and literature pins

## Primary mathematical sources

- Taras Banakh and Volodymyr Gavrylkiv, *Difference bases in cyclic groups*,
  arXiv:1702.02631v6. Theorem 4.7 constructs an integer interval basis from a
  cyclic basis while adding a dedicated carry layer:
  `Delta[nm + delta_k[C_m] - 1] <= Delta[n] Delta[C_m] + k`.
  The proof's constructed set is
  `{a+md : a in A, d in D} union
  {a+m(lambda+1) : a in A intersect [0,delta_k[C_m])}`.
  Primary record: https://arxiv.org/abs/1702.02631 . The GET-only v6 e-print
  was gzip SHA-256
  `905fb6012cfcbf8898a77e40e5915cbd7f920cfcd48e5e24ea22acc1f2576dd4`;
  decompressed TeX SHA-256
  `50dc3dc03dd6a3a76f9f9cb209d6cdf7cdf04fad5d7faeee3b0b83a1f0a5235b`.
  No third-party full text is stored here.

- Shuxing Li and Chi Hoi Yip, *Generalized additive bases and difference bases
  for Cartesian product of finite abelian groups*, arXiv:2509.24034. Paperclip
  lines [5–9](https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L5-L9)
  define the representation-function setting; lines
  [73–81](https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L73-L81)
  give quotient/direct-product constructions; lines
  [119–133](https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L119-L133)
  describe the relative-difference-set graph construction and completion of
  the forbidden subgroup. These motivate changing the product topology, but
  this packet makes no claim that their finite-abelian bounds transfer to the
  Arena integer-prefix objective.

- Eric Schmutz and Michael Tait, *Cardinalities of g-difference sets*,
  arXiv:2501.11736. Paperclip lines
  [8–20](https://paperclip.gxl.ai/citations/papers/arx_2501.11736#L8-L20)
  state the exact integer-interval definition and limiting-constant context;
  lines
  [213–217](https://paperclip.gxl.ai/citations/papers/arx_2501.11736#L213-L217)
  record the covering-code relationship. This is background, not candidate
  evidence.

## Arena and local inputs

- Complete GET-only public snapshot:
  `campaign/discrete/difference_global/checkpoints/public_latest.json`,
  SHA-256
  `6159d144ae3c57dc740cd4fd5b54e1a467589c44b355dcef98ceb4b0bc6d0d69`.
  It contains 23 public solutions, 11 threads, and 78 nested replies. It is an
  input only and should remain excluded from a publish-safe packet because it
  contains third-party payloads and discussion text.
- Frozen verifier:
  `campaign/state/problems/difference-bases/a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585.py`,
  SHA-256
  `a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`.
- Public leader #634 is referenced by id, score, coverage, payload hash, and
  the 90 normalized residues modulo 8011 needed to rebuild the formulas. The
  derived residue core is attributed in `frozen_inputs.json`; the full
  360-integer payload is not copied into this subtree.

## Research conduct

All literature and Arena access was read-only. No submission, comment, post,
issue, GitHub push, or credential material was produced. Generated formulas,
events, and receipts contain only derived counts/hashes and no third-party
arrays.
