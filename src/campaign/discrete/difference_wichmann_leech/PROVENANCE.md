# Primary-source provenance

## Wichmann formula and completeness

Aleksi Saarela and Aleksi Vanhatalo, *A Connection Between Unbordered Partial
Words and Sparse Rulers*, Electronic Journal of Combinatorics 33(1), P1.40
(2026), DOI `10.37236/13806`.

- canonical article: <https://doi.org/10.37236/13806>
- openly distributed PDF:
  <https://www.combinatorics.org/ojs/index.php/eljc/article/download/v33i1p40/pdf/>
- downloaded PDF SHA-256 (PDF not copied):
  `b6f32a562a4f421496b94c0c4ab61079df623e59afd8e32da0f1b06561475fce`;
- license: CC BY 4.0, stated on the article's first page;
- Definition 16, page 6: finite Wichmann gap representation;
- Definition 17 and Theorem 18, pages 6--8: extensions and completeness;
- Theorem 19, pages 8--9: mark and length formulas.

The article explicitly gives a self-contained proof because Wichmann's original
paper omitted it. This packet independently translates only the mathematical
formula into code; no article text, program, or array is copied.

Original source metadata: B. A. Wichmann, *A Note on Restricted Difference
Bases*, Journal of the London Mathematical Society 38 (1963), 465--466, DOI
`10.1112/jlms/s1-38.1.465`.

## Paperclip literature cross-check

Paperclip full text for Taras Banakh and Volodymyr Gavrylkiv, *Difference Bases
in Cyclic Groups*, arXiv `1702.02631`, lines 68--82, defines interval difference
size, records the Rédei--Rényi and Leech--Golay bounds, and identifies
`{0,1,4,6}` plus Singer sets as the separate four-block construction:

<https://paperclip.gxl.ai/citations/papers/arx_1702.02631#L68-L82>

Lines 136--150 give that product construction and were used only to enforce the
non-overlap boundary, not to generate this Wichmann sweep:

<https://paperclip.gxl.ai/citations/papers/arx_1702.02631#L136-L150>

## Arena sources

- frozen public corpus SHA-256 (database not copied):
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`;
- frozen verifier SHA-256 (source not copied):
  `a7521e8a701ac31131932d2a732769d65426d329f4a933c4819516adacf2e585`;
- corpus audit scope: 23 public solutions, 11 direct threads, and 78 replies;
- the targeted discussion search found no prior Wichmann or Leech construction
  in the difference-bases thread corpus.

All external access in this lane was read-only.
