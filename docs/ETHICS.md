# Integrity policy

Leaderboard position is not enough to call something a mathematical result.

We label each claim as one of:

- **domain-valid** — conforms to the written mathematical domain and passes the
  unchanged live verifier;
- **numerical certificate** — satisfies the verifier's complete advertised
  finite horizon and tolerance, but does not establish a stronger analytic
  statement made in the problem text;
- **verifier-valid only** — accepted by evaluator code but violates or escapes
  the written domain;
- **local frontier** — improves our artifact but does not clear the live gate;
- **negative result** — a bounded, reproducible search that found no candidate.

The Tammes-50 platform first place is deliberately labeled verifier-valid only.
The evaluator leaves an exact zero vector at the origin instead of rejecting it
or projecting it onto the unit sphere. We disclosed the mismatch publicly and
do not represent that payload as a 50-point spherical code.

The Prime Number Theorem platform first place is labeled a numerical
certificate. An exact rational sweep verifies every floor-sum state throughout
the server's full advertised horizon and the unchanged 10-million-sample
verifier accepts it. Its maximum nevertheless exceeds the ideal analytic bound
of 1 by less than the verifier's `1e-4` tolerance, and no proof for all
`x >= 1` is claimed.

The controller now forbids submission unless both `--confirm-domain-valid` and
`--confirm-submit` are present. A separate Edges-vs-Triangles schema mismatch
was disclosed, tested, and then closed by the API's 500-row validation; it was
not resubmitted after rejection.
