# EinsteinArena literature packet

Generated 2026-08-15 from full text read through Paperclip. This directory is
public-safe: it contains no API keys, cookies, account identifiers, or private
clipboard paths. It is a direct-citation packet, not a Paperclip repository.

Machine-readable coverage and the reproducible query log live in
[`literature/literature_map.json`](../literature/literature_map.json) and
[`literature/QUERY_LOG.md`](../literature/QUERY_LOG.md).

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

7. **Variable-radius circle packing needs topology-changing center moves.**
   PAS-PCI ranks squeezed circles by a normalized pain score, moves them into
   large or size-matched voids, splits narrow voids for paired relocations, and
   alternates those jumps with continuous polishing [11]. FlowBoost independently
   separates global center discovery from an exact fixed-center radius LP and
   stochastic local refinement [12]. GigaEvo's n=26 run returned essentially
   the established geometry at only rounded precision [13], reinforcing that
   another decimal polish of the incumbent graph is not the useful frontier.

8. **The two remaining convolution gaps admit coarse lifted searches.** A
   recent discrete-cube result reduces a related convolution minimax to
   intersections where adjacent convolution coefficients agree [15]. Peak
   sidelobe design supplies a complementary computational route: lift quadratic
   lag responses into a semidefinite variable and recover rank one
   sequentially [16]. At high resolution, higher-order trust-region bundle
   models are designed specifically for finite max-type objectives [17]. For
   C3 and Erdős, use the lifted formulation only to discover new coarse
   support/topology basins, then upscale and accept exclusively by the literal
   convolution/correlation verifier.

9. **PNT support design has a classical finite-scheme interpretation.** The
   Chebyshev--Sylvester framework replaces the Möbius function with a finite
   arithmetic surrogate and studies its periodic floor-sum error function
   [18]. Its historical schemes combine structured divisor blocks, and the
   modern review shows that hybridizing two schemes can improve the resulting
   bound [18]. Granville--Koukoulopoulos--Maynard make the complementary
   smoothing principle explicit: useful squarefree weights take the form
   `mu(d) f(log(d)/log(R))`, commonly with a polynomial taper, while a sharp
   cutoff leaves isolated-divisor mass too large [19]. For the Arena, this
   supports coherent block/tail changes and smoothly varying log-scale support
   density rather than isolated key pricing; every proposed support still
   requires the exact fixed-stream LP and verifier replay. Heath-Brown's
   account of the Rosser--Iwaniec construction adds a discrete topology:
   retain `mu(d)` only on squarefree integers satisfying nested inequalities
   in the descending prime factors of `d` [20]. Those weights solve a
   classical dimension-one sieve problem, but the Arena's normalization and
   all-integer floor-sum constraint are different, so we use the rule only to
   generate coherent global support pools before exact replay.

10. **Flat-polynomial search should change pair topology, not just bits.**
    Fekete polynomials provide an explicit Legendre-symbol family whose unit-
    circle values admit a shifted random-process representation [21]. More
    directly, the constructive flat-Littlewood proof centers the polynomial,
    assigns coefficient pairs to a symmetric cosine component or an
    antisymmetric sine component, seeds the cosine part with Rudin--Shapiro,
    and uses discrepancy to push the sine part on the cosine part's dangerous
    intervals [22]. At degree 70 this becomes a bounded global operator:
    optimize pair type and pair sign against the current active unit-circle
    peaks, then replay the complete million-point verifier grid.

11. **Difference bases need an integer-carry construction, not another modular
    seed.** Li and Yip's quadratic relative-difference-set graph gives excellent
    coverage in a finite product group and explicitly patches the forbidden
    subgroup [23]; Schmutz and Tait connect generalized difference sets to
    radius-two covering codes [24]. Exact Arena experiments show that naive
    base-​(p) embedding destroys the modular advantage at carry boundaries.
    The next useful family must therefore build a terrace or ordering whose
    adjacent carries are part of the construction, rather than deepening local
    patches around the same embedding.

## Public-safe map for all 19 Arena slugs

| Arena slug | Literature-grounded direction |
|---|---|
| `erdos-min-overlap` | Combine exact-correlation SLP with coarse lifted rank-one relaxations that search globally over lag-active support patterns, then upscale and replay every shift [1, 16, 17]. |
| `first-autocorrelation-inequality` | Piecewise-constant counterexamples, Newton-type intelligent perturbation directions, cubic backtracking, and adjacent-convolution equality manifolds are the documented route; expect irregular optimizers [1, 15]. |
| `second-autocorrelation-inequality` | Run high-resolution projected Adam with noise, elitist respawn, upsampling, and explicit spike/comb initialization [1, 3]. |
| `third-autocorrelation-inequality` | Treat the maximum convolution lag as an active bundle, use peak-switching basin hops, and test coarse SDP/rank-one topology seeds before exact high-resolution polishing [1, 3, 15, 16, 17]. |
| `min-distance-ratio-2d` | Share heuristics across nearby \((d,n)\) instances, normalize similarity degrees of freedom, then polish the active diameter/contact graph [1]. |
| `kissing-number-d11` | Retired platform lane: preserve the exact score-zero audit and monitor only for a ranking-policy change [1, 10]. |
| `prime-number-theorem` | Combine truncated Möbius structure with periodic Chebyshev--Sylvester schemes, smoothly tapered log-scale density, and nested Rosser--Iwaniec prime-factor support families, then require exact fixed-stream and analytic floor-sum checks [1, 18, 19, 20]. |
| `uncertainty-principle` | Search Laguerre/Hermite Fourier-eigenfunction families through prescribed double roots, while testing the paper's warning that the best profile may be nonanalytic [1, 9]. |
| `thomson-problem` | Seed nearly uniform spherical configurations, alternate gradient and stochastic perturbations, and use asymptotic energy residuals to compare basins [1]. |
| `tammes-problem` | Combine contact-graph topology, LP/SDP pruning, and multi-start spherical-code basin hopping [1, 6, 7]. |
| `flat-polynomials` | Combine reversal/sign symmetries with Fekete/Legendre seeds and a centered symmetric-cosine/antisymmetric-sine pair-topology search inspired by Rudin--Shapiro plus discrepancy, then replay every candidate on the full verifier grid [1, 21, 22]. |
| `edges-vs-triangles` | Generate complete multipartite rows analytically from the exact Razborov curve and allocate rows to minimize the verifier's largest edge-density gap [1]. |
| `circle-packing` | Keep centers as the global-search variables, solve radii exactly for each center set, and generate changed contact graphs with pain-ranked void relocation, split-neighbour moves, and stochastic center perturbations [1, 11, 12, 13]. |
| `heilbronn-triangles` | Use barycentric symmetry breaking, active signed-area constraints, lattice seeds, and fixed-sign MIQCP/MINLP branch-and-bound certificates; the newer exact-coordinate workflow is certified only through \(n\leq 9\), so it supplies machinery rather than an \(n=11\) construction [1, 4, 5, 12, 13, 14]. |
| `circles-rectangle` | Jointly optimize rectangle aspect ratio and the active tangency graph, reusing fixed-center radius optimization and topology-changing void moves from square circle packing [1, 11, 12]. |
| `difference-bases` | Construct carry-aware terraces/orderings that preserve relative-difference-set coverage after embedding finite product groups into an integer interval; naive quadratic-graph embeddings and local subgroup patches are now a quantified no-go [1, 23, 24]. |
| `kissing-number-d12` | Retired platform lane: preserve the verified score-zero construction and monitor issue #59 for endpoint reopening [8]. |
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

[11] Kun He, Mohammed Dosh, and Shenghao Zou. “Packing Unequal Circles into a Square Container by Partitioning Narrow Action Spaces and Circle Items.” *arXiv* (2017).
    https://paperclip.gxl.ai/citations/papers/arx_1701.00541#L22-L26,L43-L45,L61-L68,L72-L96

[12] Gergely Bérczi, Baran Hashemi, and Jonas Klüver. “Flow-based Extremal Mathematical Structure Discovery.” *arXiv* (2026).
    https://paperclip.gxl.ai/citations/papers/arx_2601.18005#L1

[13] Valentin Khrulkov, Andrey Galichin, Denis Bashkirov, Dmitry Vinichenko, Oleg Travkin, Roman Alferov, Andrey Kuznetsov, and Ivan Oseledets. “GigaEvo: An Open Source Optimization Framework Powered By LLMs And Evolution Algorithms.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2511.17592#L15-L20,L33-L46

[14] Nathan Sudermann-Merx. “From Computational Certification to Exact Coordinates: Heilbronn's Triangle Problem on the Unit Square Using Mixed-Integer Optimization.” *arXiv* (2026).
    https://paperclip.gxl.ai/citations/papers/arx_2603.11107#L1

[15] José Gaitán and José Madrid. “On suprema of convolutions on discrete cubes.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2512.18188#L13-L24,L33-L45,L75-L80

[16] Weiting Lin, Yuwei Chang, and Borching Su. “Unimodular Waveform Design that Minimizes PSL of Ambiguity Function over a Continuous Doppler Frequency Shift Region of Interest.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2504.06038#L9-L14,L183-L183

[17] Bennet Gebken and Michael Ulbrich. “Enclosing minima in nonsmooth optimization via trust regions of higher-order cutting-plane models.” *arXiv* (2026).
    https://paperclip.gxl.ai/citations/papers/arx_2603.23261#L1

[18] Tsogtgerel Gantumur. “An expository review of the Chebyshev-Sylvester method in prime number theory.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2512.02466#L3,L24-L29,L62-L70,L115-L138,L283-L305

[19] Andrew Granville, Dimitris Koukoulopoulos, and James Maynard. “Sieve weights and their smoothings.” *arXiv* (2016).
    https://paperclip.gxl.ai/citations/papers/arx_1606.06781#L13-L27,L35-L42,L49-L58

[20] D. R. Heath-Brown. “Lectures on sieves.” *arXiv* (2002).
    https://paperclip.gxl.ai/citations/papers/arx_math0209360#L444-L460,L501-L510

[21] Oleksiy Klurman, Youness Lamzouri, and Marc Munsch. “$L_q$ norms and Mahler measure of Fekete polynomials.” *arXiv* (2023).
    https://paperclip.gxl.ai/citations/papers/arx_2306.07156#L9-L12,L64-L74

[22] Paul Balister, Béla Bollobás, Robert Morris, Julian Sahasrabudhe, and Marius Tiba. “Flat Littlewood Polynomials Exist.” *Annals of Mathematics* 192, 977–1004 (2020).
    https://paperclip.gxl.ai/citations/papers/arx_1907.09464#L23,L32-L38,L79-L85

[23] Shuxing Li and Chi Hoi Yip. “Generalized additive bases and difference bases for Cartesian product of finite abelian groups.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2509.24034#L73-L78,L119-L123,L129-L132,L281-L291

[24] Eric Schmutz and Michael Tait. “Cardinalities of g-difference sets.” *arXiv* (2025).
    https://paperclip.gxl.ai/citations/papers/arx_2501.11736#L8-L22,L213-L217
