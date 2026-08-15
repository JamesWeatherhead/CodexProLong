# C3 topology-escape handoff

Updated: 2026-08-15T03:15Z

## Frozen status

This bounded lane did not clear the Arena gate and made no Arena, discussion,
issue, or GitHub write.  The best payload is
`turbo-topology-continuation-v2/runs/20260815T031008Z/best.npy`.

The unchanged public verifier returns `1.4515653850221024`.  A direct
`2*n*max(np.convolve(f,f))/sum(f)^2` replay returns
`1.4515653850221026`; the `2e-16` difference is only floating-point operation
ordering.  Payload SHA-256 is
`c3af7761fd3cf1a9a812b1ed04219eb17ceb5821946990efbd6f09d4d31679bd`.

- Public leader: `1.4515718638902069` (minimize).
- Strict target after the `1e-5` improvement rule: `1.4515618638902069`.
- Remaining official-verifier gap: `3.521131895611873e-6`.
- Improvement over the pre-topology n=102,400 checkpoint
  `1.4515654065478694`: `2.1525766946695057e-8`.
- Verifier SHA-256:
  `b8288d5943d72032f1d2bcf5d8a3b3a00cfd428ae0347a26bfc53974ec7ebce9`.

The exact receipt, including both score operation orders, source hashes,
lineage, and a clean rerun command, is
`turbo-topology-continuation-v2/runs/20260815T031008Z/receipt.json`.

## Evidence read before the experiment

The exhaustive C3 corpus was read from
`research_corpus/snapshots/20260815T003306Z/corpus.sqlite3`: all 40 solutions,
20 threads, and 97 replies for problem 4.  Its SHA-256 is
`9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.
The existing noisy continuation, simple pair/block split, low-beta upsample,
single-coordinate support, and cleaned 68-mode active-bundle routes were
treated as closed rather than rerun.

Paperclip supplied the following line-pinned evidence:

- Lin, Chang, and Su formulate peak-sidelobe minimization as an SDP with a
  rank-one constraint and describe SROCR's trace/eigenvalue relaxation,
  adaptive tightening, and leading-eigenvector extraction
  ([arXiv:2504.06038, lines 3, 14, 95–129](https://paperclip.gxl.ai/citations/papers/arx_2504.06038#L3,L14,L95-L129)).
- Jaech and Joseph warn that coarse upsampling may inherit the same local
  maximum and explicitly identify peak locking and rugged nonsmooth surfaces
  in the first and third autoconvolution inequalities
  ([arXiv:2508.02803, lines 23–38](https://paperclip.gxl.ai/citations/papers/arx_2508.02803#L23-L38)).
- Gaitan and Madrid reduce a related Poisson-binomial convolution minimax to
  intersections where adjacent convolution coefficients are equal
  ([arXiv:2512.18188, lines 78–80](https://paperclip.gxl.ai/citations/papers/arx_2512.18188#L78-L80)).
  This is motivation for active-lag equality exchange only, not a theorem for
  signed C3.
- AlphaEvolve's mathematics report motivates chained, deterministic
  evaluator-scored improvers and search diversity
  ([arXiv:2511.02864, lines 21–33 and 43](https://paperclip.gxl.ai/citations/papers/arx_2511.02864#L21-L33,L43-L43));
  ImprovEvolve specifically motivates perturbation/local-improvement
  basin-hopping
  ([arXiv:2602.10233, line 1](https://paperclip.gxl.ai/citations/papers/arx_2602.10233#L1)).

These papers motivate algorithms; none certifies the C3 optimum or transfers a
bound to this signed finite-grid verifier.

## Implemented topology changes

`topology_escape.py` is a checkpointed proposal-and-polish program.  FFT
convolution is used only for screening and smooth surrogate gradients.  Every
seed selected for polishing and every saved endpoint is replayed with literal
float64 `numpy.convolve`; only a strict exact improvement replaces `best.npy`.

The new families are finite rather than infinitesimal:

- unequal-cell phase slips, including an automatic first-sign-wall crossing;
- contiguous block death/rebirth and coordinated weak-cell support births;
- periodic residue-class death/rebirth;
- Nyquist/reflection spectral crossover; and
- cross-basin recombination that superposes independently polished finite
  displacements before exact replay.

Changed signs can be locked through the signed-square polish stages and then
released in a full-coordinate cascade.  The winning lineage temporarily
entered a one-flip orthant and later returned near the original sign topology;
the finite crossing nevertheless reached a different full-resolution basin.

`rank_lift_escape.py` implements the independent coarse lifted route.  For an
augmented rank-one matrix, each sampled autoconvolution lag is linear in
anti-diagonal entries.  SROCR stages, full-grid cut discovery, topology
constraints, leading-eigenvector extraction, and exact fine-grid replay are
checkpointed.  The pinned environment is CVXPY `1.7.5`, SCS `3.2.11`, NumPy
`2.5.2`, and SciPy `1.18.0`; the two SDP packages are frozen in
`requirements-rank-lift.txt`.

## Quantified frontier

| Route | Exact endpoint | Result |
| --- | ---: | --- |
| 64-block support-periodic SROCR, tight schedule | `1.4515654294085765` | no gain; extracted topology seed was `1.4515669038430643` |
| coordinated 8-cell support birth | `1.4515654296029852` | worse than its input by `1.944087e-10` |
| periodic p=25,600 support death/rebirth + release | `1.4515658938010034` | remained `4.7835e-7` above its input |
| full width-32 unequal-cell slip | `1.4515744041405358` | rejected |
| left width-8 first useful crossing | `1.4515654056587153` | exact gain `8.8915408e-10` |
| dense left width-8 crossing | `1.4515654054997493` | exact gain `1.0481200e-9` |
| left width-5 crossing | `1.4515654053250722` | exact gain `1.2227972e-9` |
| independent right width-4 crossing | `1.4515654052797646` | exact gain `1.2681047e-9` |
| two-flip cross-basin recombination | `1.4515654030256808` | strongest locked topology endpoint; gain `3.5221885e-9` |
| right-orthant release | `1.4515653999695135` | release gain `5.3102511e-9`; below global frontier |
| two-flip recombination release | `1.4515653975868070` | release gain `5.4388738e-9`; below global frontier |
| winning topology release | `1.4515654006545770` | release gain `5.0041382e-9` |
| three exact-accepted continuation cycles | `1.4515653850221024` official | final frozen frontier |

The topology generator and releases consumed 80,459 fine-grid optimizer
evaluations, in addition to the bounded SDP solves.  The last three continuation
gains were `5.3364e-9`, `5.2501e-9`, and `5.0459e-9`.  At the recent
`~5.25e-9` rate, the remaining gate is roughly 671 more full cascades away even
under an unjustified linear extrapolation.  This is a publishable numerical
frontier, not a gate-clearer and not evidence that all topology changes fail.

## Clean reproduction

Rebuild the first successful topology crossing:

```sh
.venv/bin/python -u campaign/c3_root/topology_escape.py \
  --input campaign/c3_root/turbo-102400/runs/20260815T023145Z/best.npy \
  --families unequal-cell-slip --slip-widths 8 \
  --slip-alphas 0.025263283930190995 --positions-per-width 192 \
  --family-keep 6 --screen-penalty 0.0001 --max-seeds 1 \
  --betas 3e7,1e8,3e8,1e9 --maxiter 1200 --maxcor 100 \
  --lock-stages 4
```

Rerun the frozen three-cycle continuation from the atomically recovered bridge
payload into a fresh state directory:

```sh
.venv/bin/python -u campaign/c3_root/turbo_supervisor.py \
  --input campaign/c3_root/runs-topology-continuation/20260815T025347Z/best.npy \
  --cycles 3 --state-dir campaign/c3_root/turbo-topology-continuation-rerun \
  --betas 3e7,1e8,3e8,1e9 --maxiter 1200 --maxcor 100
```

The supervisor now resolves `--state-dir` before launching its child from the
campaign directory.  Its explicit no-write path regression is:

```sh
.venv/bin/python campaign/c3_root/turbo_supervisor.py \
  --state-dir campaign/c3_root/path-check-sentinel --path-check-only
test ! -e campaign/c3_root/path-check-sentinel
test ! -e campaign/campaign/c3_root/path-check-sentinel
```

The check returns `path_check_passed: true`; no sentinel directory is created.
The accidental pre-fix output under `campaign/campaign/` was independently
replayed and atomically recovered into
`runs-topology-continuation/20260815T025347Z/`.  The duplicated directory is
not canonical and must not be published.

## Minimum coherent publication inclusion list

Include these exact source/document paths:

- `campaign/c3_root/TOPOLOGY_ESCAPE_HANDOFF.md`
- `campaign/c3_root/topology_escape.py`
- `campaign/c3_root/rank_lift_escape.py`
- `campaign/c3_root/requirements-rank-lift.txt`
- `campaign/c3_root/turbo_supervisor.py`

Include these exact audit directories if generated artifacts are mirrored:

- `campaign/c3_root/runs-rank-lift/20260815T022739Z/`
- `campaign/c3_root/runs-topology-escape/20260815T024626Z/`
- `campaign/c3_root/runs-topology-escape/20260815T024900Z/`
- `campaign/c3_root/runs-topology-escape/20260815T025317Z/`
- `campaign/c3_root/runs-topology-escape/20260815T025901Z/`
- `campaign/c3_root/runs-topology-continuation/20260815T025347Z/`
- `campaign/c3_root/runs-topology-release-right/20260815T030457Z/`
- `campaign/c3_root/runs-topology-release-recombine/20260815T030658Z/`
- `campaign/c3_root/turbo-topology-continuation-v2/`

Explicitly exclude `campaign/campaign/`.  It is the noncanonical duplicate
created by the fixed relative-path bug.  No credentials or hidden reasoning
traces are present in the inclusion set.
