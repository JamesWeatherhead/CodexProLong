# C2 public asset recovery

This read-only lane looked for downloadable, high-resolution extremizers for
the second autocorrelation inequality beyond the already tested
Jaech--Joseph profile. It recovered one previously absent local asset:
SimpleTES' 262,144-value construction.

## Exact outcome

Every score below is from the unchanged frozen Arena verifier with SHA-256
`dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`.
The live leader is solution `#2416` at `0.963588110582029`; the strict gate is
`0.9635981105820289`.

| Asset | n | Exact replay | Gate gap | Corpus status |
| --- | ---: | ---: | ---: | --- |
| SimpleTES | 262,144 | `0.9626937749955136` | `9.043355865153702e-4` | no exact match among all 38 frozen public C2 solutions |
| Hyra | 524,288 | `0.9629011010961758` | `6.970094858531617e-4` | exact match for Arena `#2361` and the prior local reference |

SimpleTES reports `0.9626937749954642`; the independent replay differs by
only `4.94e-14`. Its material support (relative threshold `1e-8`) has 3,141
runs with median width 7, confirming that the recovered data is a genuine
fine spike/comb construction rather than a smooth low-resolution profile.
It is nevertheless about ninety submission gates below the current target.

## Provenance

- SimpleTES repository `wq-will/SimpleTES`, pinned commit
  `a19a54b109db6185ab1f13dd59dd150074b24136`; raw construction SHA-256
  `cd9d2fb1ba5280f46dbe8a836d1dc65c2b0c9e6a2c0cd9f857c47cee7d555ccd`.
  The repository is GNU AGPL-3.0-or-later.
- Hyra repository `Tencent-Hunyuan/Hyra-results`, pinned commit
  `26ebfbe7d491e6521d8bb5fc21fe88bb31460825`; raw construction SHA-256
  `7e5fc9864969d100982fdd56b085c996e62b42e2cf2f632d9f22bb1cd8ce893a`.
  The repository is Apache-2.0.
- The frozen exhaustive Arena database has SHA-256
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.

Jaech--Joseph explicitly describe a tall spike followed by a fine comb, link
their high-resolution coefficients, and argue that full-resolution search is
important [1]. ImprovEvolve independently describes AlphaEvolve's irregular
50,000-step seed and a continuation to 1.6 million steps scoring 0.96258 [2],
and publishes the evolved program plus the edited multigrid schedule [3]. The
primary sources inspected did not expose that final ImprovEvolve array. This
lane used Paperclip plus commit-pinned primary-source web/GitHub API reads;
campaign-wide Exa discovery is tracked in the literature ledger.

## Reproduce

```sh
cd /path/to/EinsteinArena
.venv/bin/python campaign/c2_asset_recovery/asset_replay.py
```

The script uses GET only, verifies every remote blob before parsing, writes
downloads and NumPy payloads atomically, imports the frozen verifier directly,
and audits exact duplication against all public C2 solutions. Generated raw
assets and arrays are intentionally git-ignored; `receipt.json` contains the
full hashes, source URLs, scores, support statistics, and corpus matches.

No Arena submission, post, vote, issue, or GitHub mutation was made.

## References

[1] Aaron Jaech and Alan Joseph. “Further Improvements to the Lower Bound for
an Autoconvolution Inequality.” arXiv (2025).
<https://paperclip.gxl.ai/citations/papers/arx_2508.02803#L27-L34>

[2] Alexey Kravatskiy, Valentin Khrulkov, and Ivan Oseledets.
“ImprovEvolve: Basin-Hopping Meets LLM-Guided Evolutionary Search.” arXiv
(2026).
<https://paperclip.gxl.ai/citations/papers/arx_2602.10233#L87-L98>

[3] Kravatskiy, Khrulkov, and Oseledets, evolved C2 code and edited schedule.
<https://paperclip.gxl.ai/citations/papers/arx_2602.10233#L240-L245>
