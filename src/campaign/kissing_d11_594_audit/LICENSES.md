# Provenance and license notes

This directory combines an original audit program, hashes/metadata derived from
a public corpus, a recovered public construction, and citations to literature.
Their rights status is not uniform.

| Material | Provenance | License / handling |
|---|---|---|
| `audit.py`, audit prose, generated receipts/manifests | This audit | Original local work; no separate outbound license grant is made here. |
| Frozen verifier and leaderboard implementation | [vinid/einstein-arena](https://github.com/vinid/einstein-arena/tree/98073fca26654d048d70acdfe1e319a23e8e41c6) | [MIT License](https://github.com/vinid/einstein-arena/blob/98073fca26654d048d70acdfe1e319a23e8e41c6/LICENSE); retain the copyright and permission notice when copying substantial source portions. No substantial source portion is copied into this directory. |
| `payload.json` coordinates | Public EinsteinArena solution 1492, submitted by KawaiiCorgi | Publicly retrievable at [`GET /api/solutions/best?problem_id=6&limit=1`](https://einsteinarena.com/api/solutions/best?problem_id=6&limit=1). No explicit license for user-submitted solution content was located. Attribution and record hash are preserved; this audit does not assert unrestricted redistribution rights. |
| Novikov et al., arXiv:2506.13131 | Paperclip/arXiv full text | [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) as shown on the [arXiv record](https://arxiv.org/abs/2506.13131). Only a paraphrase and line-pinned citation are used. |
| Georgiev et al., arXiv:2511.02864 | Paperclip/arXiv full text | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) as shown on the [arXiv record](https://arxiv.org/abs/2511.02864). Only a paraphrase and line-pinned citation are used. |
| Ganzhinov, arXiv:2207.08266 | Paperclip/arXiv full text | [arXiv non-exclusive distribution license 1.0](https://arxiv.org/licenses/nonexclusive-distrib/1.0/) as shown on the [arXiv record](https://arxiv.org/abs/2207.08266). Only a paraphrase and line-pinned citation are used. |

Source record anchors:

- Solution id: `1492`
- Agent: `KawaiiCorgi`
- Created: `2026-04-10T23:13:59.050Z`
- Canonical Arena record SHA-256:
  `a1921fc7e26323d603cb267a4837689b3361d0f4481a3073ec3042ae44503bc0`
- Frozen exhaustive corpus SHA-256:
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`

