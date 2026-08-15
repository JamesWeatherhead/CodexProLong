# EinsteinArena literature packet

Generated 2026-08-15 from full text read through Paperclip. This directory is
public-safe: it contains no API keys, cookies, account identifiers, or private
clipboard paths. It is a direct-citation packet, not a Paperclip repository.

## Highest-value search implications

1. **Third autocorrelation is a nonsmooth active-set problem.** The signed
   problem is explicitly the non-positive variant of the first inequality, and
   the published numerical baseline is a piecewise-constant search [1]. A
   direct gradient tends to reinforce whichever convolution lag is currently
   maximal ("peak-locking") [3]. The next search should therefore optimize an
   epigraph over a changing bundle of near-maximal lags, deliberately cross lag
   boundaries, and keep basin-hopping/perturbation restarts. Smooth log-sum-exp
   continuation is useful for discovery, but every accepted move must replay
   against the exact maximum.

2. **The second inequality supplies transferable machinery, not the same loss.**
   High-resolution Adam, decaying gradient noise, elitist respawn, and
   interpolate-then-polish upsampling are documented effective operators [3].
   The extremizer's spike-plus-comb shape produces a broad, nearly flat
   autoconvolution plateau [3]. For the signed third inequality, reuse the
   multi-resolution and restart machinery while replacing the second
   inequality's peak-flattening gradient with an explicit active-lag minimax
   step.

3. **Heilbronn should combine continuous polishing with certified topology
   pruning.** MIQCP/QCP formulations expose the signed-area bilinearity and use
   bound tightening plus symmetry breaking to turn small cases into certified
   global optima [4]. The asymptotic literature also supplies explicit
   no-three-collinear lattice constructions [5]. For the Arena's 11-point
   equilateral-triangle instance, translate these ideas into barycentric
   coordinates, enumerate boundary-occupancy/contact types, and solve fixed
   sign patterns before polishing the continuous coordinates.

4. **Tammes and kissing searches benefit from structural initialization.**
   Contact-graph enumeration, linear elimination, and SDP edge bounds form a
   rigorous Tammes playbook [6]. ImprovEvolve reports that decomposing the
   program into initialization, local improvement, and scheduled perturbation
   yields basin hopping and improves many spherical-code records [7]. The new
   12-dimensional 841 construction is even more specific: retain the two
   60-point blocks and 720 bridge vectors induced by a 1-factorization of
   \(K_6\), exploit the flexible 48-systems, and initialize logarithmic Riesz
   optimization from that family [8].

5. **Edges-vs-triangles is analytically solved at the graphon level.** The
   multipartite formula is exact by Razborov, and the valid finite envelope is
   horizontal to the left and slope 3 to the right [1]. Search should spend
   effort on sampling/quantizing the exact multipartite curve under the
   verifier's 20-bin and 500-row restrictions, not on discovering a different
   graphon family.

6. **Do not discard singular or highly irregular convolution profiles.** The
   arcsine distribution's square-root boundary singularity keeps translated
   overlap bounded away from zero [2], while the best modern second-inequality
   examples are highly irregular combs [1, 3]. Coarse smooth ansatzes can erase
   precisely the structures that improve the bound.

## Public-safe map for all 19 Arena slugs

| Arena slug | Literature-grounded direction |
|---|---|
| `erdos-min-overlap` | Use bounded fixed-grid step functions, convex lower-bound diagnostics, and exact correlation replay; the published interval and construction history are summarized in [1]. |
| `first-autocorrelation-inequality` | Piecewise-constant counterexamples, Newton-type intelligent perturbation directions, and cubic backtracking are the documented route; expect irregular optimizers [1]. |
| `second-autocorrelation-inequality` | Run high-resolution projected Adam with noise, elitist respawn, upsampling, and explicit spike/comb initialization [1, 3]. |
| `third-autocorrelation-inequality` | Treat the maximum convolution lag as an active bundle and use peak-switching basin hops; signed values make naive single-peak gradients especially brittle [1, 3]. |
| `min-distance-ratio-2d` | Share heuristics across nearby \((d,n)\) instances, normalize similarity degrees of freedom, then polish the active diameter/contact graph [1]. |
| `kissing-number-d11` | Optimize finite vector configurations, then exactify a sufficiently accurate zero-loss candidate; preserve reusable subcodes and share partial constructions [1, 10]. |
| `prime-number-theorem` | Start from truncated Möbius functions and structured divisor blocks, but replace Monte Carlo acceptance with an analytic all-\(x\) floor-sum certificate [1]. |
| `uncertainty-principle` | Search Laguerre/Hermite Fourier-eigenfunction families through prescribed double roots, while testing the paper's warning that the best profile may be nonanalytic [1, 9]. |
| `thomson-problem` | Seed nearly uniform spherical configurations, alternate gradient and stochastic perturbations, and use asymptotic energy residuals to compare basins [1]. |
| `tammes-problem` | Combine contact-graph topology, LP/SDP pruning, and multi-start spherical-code basin hopping [1, 6, 7]. |
| `flat-polynomials` | Exploit reversal/sign symmetries, FFT-based exact-grid screening, and targeted bit flips at active unit-circle maxima; published asymptotics show why merely smooth profiles are insufficient [1]. |
| `edges-vs-triangles` | Generate complete multipartite rows analytically from the exact Razborov curve and allocate rows to minimize the verifier's largest edge-density gap [1]. |
| `circle-packing` | Maintain the active tangency/boundary graph, solve fixed-topology systems, and perturb topology when the KKT residual stalls; the literature characterizes this as continuing numerical refinement [1]. |
| `heilbronn-triangles` | Use barycentric symmetry breaking, active signed-area constraints, lattice seeds, and fixed-sign MIQCP/branch-and-bound certificates [1, 4, 5]. |
| `circles-rectangle` | Jointly optimize rectangle aspect ratio and the active tangency graph, reusing fixed-topology continuation from square circle packing [1]. |
| `difference-bases` | Seed Singer difference sets, then perform deficit-aware swaps while maintaining a fast difference-multiplicity table [1, 2]. |
| `kissing-number-d12` | Archived target: retain the documented 60+60+720 block/bridge decomposition and 48-system flexibility as the reproducible explanation for the 841 construction [8]. |
| `kissing-number-d11-605` | Build on collaborative 11-dimensional subcodes, optimize with structural perturbations, and require exact integer verification at the end [1, 10]. |
| `kissing-number-d12-842` | Start inside the 840/841 structured family, perturb the flexible 48-systems under logarithmic Riesz energy, then search for an exactifiable 842nd-vector rearrangement [7, 8]. |

## What Paperclip did and did not return

Paperclip authentication and server health are good. Direct full-text reads and
corpus-wide grep work. However, as of this snapshot, semantic/keyword searches
against `-s arxiv` return no result for known indexed documents such as the
Barnard--Steinerberger paper, and `lookup arxiv 1903.08731` plus exact-title
lookup also return nothing. The same document is present and readable at its
virtual-filesystem path, and corpus grep finds it. This is an arXiv search/
metadata-index coverage issue, not an authentication issue.

The CLI also had a separate local routing fault: `cli_cwd` had persisted as
`/papers/`, causing commands to be prefixed with `cd /papers/` and, in some
paths, surfaced as `Unknown command: cd` or empty output. Resetting `cli_cwd` to
`/` restored normal `paperclip head`, `cat`, `grep`, and `scan` behavior.

A DOI fetch for Razborov's paper resolved the correct Cambridge page but the
publisher temporarily served a disruption page instead of the PDF; the useless
clipboard capture was soft-deleted. The line-pinned Razborov formula below is
therefore taken from the AlphaEvolve paper's full-text account rather than a
private clipboard artifact.

--------
REFERENCES

[1] Bogdan Georgiev, Javier Gómez-Serrano, Terence Tao, and Adam Zsolt Wagner. “Mathematical exploration and discovery at scale.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L95-L151,L190-L207,L361-L398,L481-L521,L597-L640

[2] Richard C. Barnard and Stefan Steinerberger. “Three Convolution Inequalities on the Real Line with Connections to Additive Combinatorics.” *Journal of Number Theory* 207, 42–55 (2020).
    https://paperclip.gxl.ai/citations/papers/arx_1903.08731#L35-L61,L142-L172

[3] Aaron Jaech and Alan Joseph. “Further Improvements to the Lower Bound for an Autoconvolution Inequality.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2508.02803#L5-L38

[4] Amirali Modir, Amirhossein Monji, and Burak Kocuk. “Solving the Heilbronn Triangle Problem using Global Optimization Methods.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2512.14505#L7-L22,L30-L53,L168-L176

[5] Alex Cohen, Cosmin Pohoata, and Dmitrii Zakharov. “A new upper bound for the Heilbronn triangle problem.” *arXiv* (2023).
    https://paperclip.gxl.ai/citations/papers/arx_2305.18253#L5-L24

[6] Oleg R. Musin. “An extension of the semidefinite programming bound for spherical codes.” *arXiv* (2019).
    https://paperclip.gxl.ai/citations/papers/arx_1903.05767#L154-L165

[7] Alexey Kravatskiy, Valentin Khrulkov, and Ivan Oseledets. “ImprovEvolve: Basin-Hopping Meets LLM-Guided Evolutionary Search.” *arXiv* (2026).
    https://paperclip.gxl.ai/citations/papers/arx_2602.10233#L1

[8] Rustem Takhanov, Zhenisbek Assylbekov, and Stanislav Yun. “Structure of kissing arrangements in $\mathbb{R}^{12}$ and a place for the 841st sphere.” *arXiv* (2026).
    https://paperclip.gxl.ai/citations/papers/arx_2606.18984#L1

[9] Henry Cohn and Felipe Gonçalves. “An optimal uncertainty principle in twelve dimensions via modular forms.” *Inventiones Mathematicae* 217, 799–831 (2019).
    https://paperclip.gxl.ai/citations/papers/arx_1712.04438#L15-L34

[10] Federico Bianchi, Yongchan Kwon, Aneesh Pappu, and James Zou. “Harnessing the Collective Intelligence of AI Agents in the Wild for New Discoveries.” *arXiv* (2026).
    https://paperclip.gxl.ai/citations/papers/arx_2606.10402#L1
