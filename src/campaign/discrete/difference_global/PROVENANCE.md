# Difference-global research provenance

This lane used public GET requests and local exact computation only. It made no
Einstein Arena, GitHub, or discussion mutations.

## Paperclip full-text sources

1. Shuxing Li and Chi Hoi Yip, *Generalized additive bases and difference
   bases for Cartesian product of finite abelian groups*, arXiv:2509.24034.
   Paperclip's line-addressed full text records:

   - the quotient/direct-product construction at
     [L73–L78](https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L73-L78);
   - the definition of a relative difference set and the quadratic graph
     \(\{(x,x^2)\}\) at
     [L119–L123](https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L119-L123);
   - the quadratic-graph core plus a basis on its forbidden complement at
     [L129–L132](https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L129-L132);
   - a related multi-line construction at
     [L281–L291](https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L281-L291).

   The arXiv record declares the
   [arXiv non-exclusive distribution license](https://arxiv.org/licenses/nonexclusive-distrib/1.0/).
   No paper text or code was copied into the implementation; the construction
   was independently re-derived and tested.

2. Eric Schmutz and Michael Tait, *Cardinalities of g-difference sets*,
   arXiv:2501.11736. The problem definition and limiting regime appear at
   [L8–L22](https://paperclip.gxl.ai/citations/papers/arx_2501.11736#L8-L22),
   and the relationship with radius-two covering codes at
   [L213–L217](https://paperclip.gxl.ai/citations/papers/arx_2501.11736#L213-L217).
   The arXiv record declares
   [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

## Primary-source web discovery

- Taras Banakh and Volodymyr Gavrylkiv, *Difference bases in cyclic groups*,
  [arXiv:1702.02631](https://arxiv.org/abs/1702.02631). Theorem 4.7 gives the
  cyclic-to-interval product recursion. Its arXiv record declares the arXiv
  non-exclusive distribution license. The incumbent Singer residue set times
  the four-mark ruler is already an instance of this topology, so the global
  lane did not relabel that known construction as a new escape.
- Bogdan Georgiev, Javier Gómez-Serrano, Terence Tao, and Adam Zsolt Wagner,
  *Mathematical exploration and discovery at scale*,
  [arXiv:2511.02864](https://arxiv.org/abs/2511.02864), Section 6.7. This is the
  primary public account of the prior 2.6571 bound and the 2.6390 AlphaEvolve
  construction. Its arXiv record declares CC BY 4.0.

An Exa connector was not callable in this session. Primary-source web search
and arXiv's own API/abstract pages were used as the explicit fallback; no
secondary blog was treated as mathematical evidence.

## Arena corpus

`refresh_public.py` uses only documented public GET routes. The complete live
snapshot contains 23 public solutions, 11 threads, and 78 replies; requesting
`limit=500` on the reply endpoint is essential because its silent default of
20 truncates threads 147 and 213. Einstein Arena does not state a content
license in these API responses. Therefore the dated full-text JSON snapshot is
local audit evidence, not part of the publish-safe source list.
