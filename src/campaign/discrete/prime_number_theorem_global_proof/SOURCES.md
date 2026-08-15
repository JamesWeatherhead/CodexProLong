# Source audit

## Primary construction source

Harold G. Diamond and Paul Erdős, “On sharp elementary prime number
estimates,” *L'Enseignement Mathématique* 26 (1980), 313–321,
DOI `10.5169/SEALS-51076`:

- <https://combinatorica.hu/~p_erdos/1981-11.pdf>
- <https://www.e-periodica.ch/digbib/view?pid=ens-001%3A1980%3A26%3A%3A456>

Pages 315–318 define the finitely supported approximation `mu_T`, normalize
its reciprocal sum to zero, and define its floor sum `G_T`.  They also record
Chebyshev's exact five-term example
`e_1-e_2-e_3-e_5+e_30`, whose floor sum lies between zero and one globally.
The same pages show why the tempting `mu_T` tail route is not an independent
PNT proof: their uniform tail lemma invokes both `sum mu(n)/n -> 0` and
`M(x)=o(x)`, explicitly identified there as PNT-equivalent estimates.

The five-term construction is independently enumerated over its complete
period by `chebyshev_baseline.py`; no paper code or table is copied.

The key-free Exa discovery query, request ID, DOI result, and public Exa
publication identifier are retained verbatim in `EXA_PROVENANCE.json`.

## Paperclip explicit-bound source

Florian Daval, “Conversions explicites entre des fonctions sommatoires de la
fonction de Möbius,” *Integers* / Contemporary Mathematics and Its
Applications 14 (2025), DOI `10.2140/cnt.2025.14.163`.

Paperclip lines 5–17 state explicit bounds for `M(x)`, `m(x)`, and a smoothed
Möbius sum; lines 19–27 explain the PNT equivalence and list explicit
`M(x)` bounds; lines 27–38 describe normalized finite floor functions and
the integral conversion framework:

<https://paperclip.gxl.ai/citations/papers/arx_2006.01295#L5-L17,L19-L38>

These estimates apply to the genuine Möbius function.  They cannot certify
the #2506 tail: direct comparison shows #2506 agrees with one common scaled
Möbius pattern only through key `329`, after which hundreds of optimized
coefficients and sparse far-tail keys depart from that arithmetic function.

## Paperclip finite-sieve support source

Barnabás Szabó, “On the Existence of Products of Primes in Arithmetic
Progressions,” arXiv:2208.05762.  Lines 39–50 state the standard finite
Selberg weights explicitly: `G(z)`, the squarefree-supported `rho_d`, the
least-common-multiple convolution `lambda_d`, and
`w(n)=sum_{d|n} lambda_d`:

<https://paperclip.gxl.ai/citations/papers/arx_2208.05762#L39-L50>

`selberg_support_screen.py` transcribes those formulas with exact rational
arithmetic only to generate support topologies.  The sieve theorem is not
transferred to the Arena inequality.  Each reported construction instead
gets an independent complete-period floor-sum check.  The enriched
`divisor_periodic_screen.py` similarly tests all divisors of a smooth period;
that enlargement is our experiment, not a construction claimed by Szabó.

## Frozen Arena evidence

- payload: `campaign/discrete/prime_number_theorem/reach_extend_127849_fullrange.json`
- payload SHA-256:
  `d43c5531d562d06981a55829deb1c579a87a7c02405d69688dcc79e7f45f22c1`
- verifier SHA-256:
  `fd76a069b269a521d6ded609bd79185bf859df778283bebc37719dfd15b1ded6`
- exact finite audit SHA-256:
  `1ec5b03f9b1d72af559df9b4240e8c2384068d267044b48f86138dd1424d5f7c`

The verifier source is hash-checked and read for its literal formula only.  It
is never imported, compiled, or executed in this lane.
