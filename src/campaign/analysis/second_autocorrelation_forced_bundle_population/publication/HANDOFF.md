# Frozen handoff: C2 forced-bundle population

## Decision

No candidate is submission-capable. Freeze the Mac work as a validated
clean-room reference and run only the bounded stages in `H100_PLAN.md` on a
dedicated H100. Do not spend shared Metal compute or claim frontier coverage.

## Distinct route

The lane uses no incumbent or retained array. It differs from the earlier
native-basin work by forcing a separated top-lag switching surface before each
serious step, then optimizing the exact finite maximin through a slack-aware
simplex bundle QP. The bundle is present from initialization rather than gated
on a random Adam trajectory later discovering a tie.

The self-generated population also uses a coherent many-tooth lattice inside
each macro comb period. Respawn is from unused random seeds, never from a
public or local candidate crossover.

## Evidence gate

- frozen corpus SHA-256:
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`;
- all 38 public C2 constructions fully decoded (15,656,738 values), hashed,
  and discarded;
- all 29 C2 threads and 120 replies fully read and hashed;
- coefficient values retained from the corpus: zero;
- verifier SHA-256:
  `dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`.

The literature packet uses Paperclip line-pinned full text and read-only Exa
primary-source/license discovery. Jaech--Joseph's source repository is MIT;
NumPy, SciPy, and planned PyTorch runtime sources use permissive licenses. No
third-party source or coefficients were copied.

## Bounded result

Canonical run: `runs/20260815T120831Z-reference-pilot`.

- `N=4,095`, population 4, four ridge+bundle steps per member;
- analytic directional-gradient relative error: `7.1584e-11`;
- exact two-active-lag test: bundle weights `0.42424`, `0.57576`;
- best score: `0.7156018568597433`;
- strict gate: `0.9635981105820289`;
- gap: `0.24799625372228562`;
- all 16 exact bundle steps improved;
- effective bundle size: 7–8 throughout;
- independent replay: `PASS`, score `0.7156018568597436`;
- checkpoint SHA-256:
  `32f3e85f848da524de2c78de31062d2020c251272ef3e635eb4a4d541c76a5c3`;
- event-chain head:
  `ab11c45b9e80fd3ad4c7d2018c29f91eb6f797050876874052909106e89da37d`.

This is deliberately far below the live gate and was not passed to the Arena
verifier.

## Reopen condition

Reopen only on a dedicated H100 under the exact stage gates in `H100_PLAN.md`.
If the native population misses `0.82` at sweep 256, `0.90` at sweep 1,024, or
`0.945` at sweep 4,096, freeze a quantified negative packet and do not retune.

Only a finite, intended-domain candidate independently replaying strictly
above the refreshed leader plus `1e-5` with declared safety may be escalated to
`./arena verify`. There is no automatic submit or external write.

## Publish-safe boundary

Include code, Markdown, `literature.json`, `corpus_audit.json`, and compact
canonical-run JSON/JSONL receipts. Exclude `runs/**/*.npy` from a public mirror
unless a future gate-clearing clean-room candidate needs an explicitly reviewed
payload release. No credentials, third-party source trees, or candidate arrays
from outside this lane are present.
