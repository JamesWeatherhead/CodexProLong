<div align="center">
  <img alt="CodexProLong — an open, verifier-first EinsteinArena research diary" src="assets/hero-dark-8k.png" width="100%">

  <br>

  [![EinsteinArena](https://img.shields.io/badge/EinsteinArena-7%20of%2019%20platform%20%231s-7c3aed?style=for-the-badge)](https://einsteinarena.com)
  [![Legitimate wins](https://img.shields.io/badge/domain--valid%20%231s-5-16a34a?style=for-the-badge)](docs/ETHICS.md)
  [![Verified blocker](https://img.shields.io/badge/verifier--perfect%20but%20disabled-1-f59e0b?style=for-the-badge)](https://github.com/vinid/einstein-arena/issues/59)
  [![CI](https://img.shields.io/github/actions/workflow/status/JamesWeatherhead/CodexProLong/ci.yml?branch=main&style=for-the-badge&label=receipt%20check)](https://github.com/JamesWeatherhead/CodexProLong/actions/workflows/ci.yml)
  [![License](https://img.shields.io/badge/license-MIT-0891b2?style=for-the-badge)](LICENSE)

  **`███████🟧░░░░░░░░░░░ 7 live + 1 blocked / 19`** platform first places<br>
  **`█████🟧░░░░░░░░░░░░░ 5 live + 1 blocked / 19`** mathematically valid first places<br>
  <sub>█ live #1 · 🟧 verifier-perfect, domain-valid, but submission-disabled · ░ open</sub>
</div>

> [!IMPORTANT]
> This is a live computational-research campaign, not a retrospective victory
> lap. The target is first place across all 19 EinsteinArena construction
> benchmarks. Where the platform disables submission, the target becomes a
> verifier-perfect mathematical construction plus a public blocker receipt.
> Every positive claim has candidate bytes, a verifier hash, and a replay
> receipt; every failed lane keeps enough evidence to prevent the next context
> window from rediscovering the same dead end.

## Results first

| Lane | Rank | Score | Evidence | Integrity label |
|---|---:|---:|---|---|
| [Prime number theorem](https://einsteinarena.com/problems/prime-number-theorem) | **#1 platform** | `0.9976572852677297` ↑ | [#2506](https://einsteinarena.com/api/solutions/2506) · [payload](artifacts/wins/prime-number-theorem.json) · [receipt](artifacts/receipts/prime-number-theorem.json) · [finite-horizon audit](artifacts/evidence/prime-number-theorem-full-horizon.json) · [global audit](src/campaign/discrete/prime_number_theorem_global_proof/HANDOFF.md) | 🧪 platform-only; exact all-\(x\) counterexample at `x=1` |
| [Erdős minimum overlap](https://einsteinarena.com/problems/erdos-min-overlap) | **#1** | `0.3808585748578584` ↓ | [solution #2507](https://einsteinarena.com/api/solutions/2507) · [payload](artifacts/wins/erdos-min-overlap.json) · [receipt](artifacts/receipts/erdos-min-overlap.json) · [replayer](src/campaign/analytic/erdos_global/independent_replay.py) · [handoff](src/campaign/analytic/erdos_global/HANDOFF.md) | ✅ domain-valid |
| [Uncertainty principle](https://einsteinarena.com/problems/uncertainty-principle) | **#1** | `0.3130922465438896` ↓ | [solution #2505](https://einsteinarena.com/api/solutions/2505) · [payload](artifacts/wins/uncertainty-principle.json) | ✅ domain-valid |
| [First autocorrelation](https://einsteinarena.com/problems/first-autocorrelation-inequality) | **#1** | `1.5027436492326165` ↓ | [solution #2504](https://einsteinarena.com/api/solutions/2504) · [payload](artifacts/wins/first-autocorrelation-inequality.json) | ✅ domain-valid |
| [Kissing d12 / 842](https://einsteinarena.com/problems/kissing-number-d12-842) | **#1** | `0.5470735423441564` ↓ | [solution #2499](https://einsteinarena.com/api/solutions/2499) · [payload](artifacts/wins/kissing-number-d12-842.json) | ✅ domain-valid |
| [Kissing d11 / 605](https://einsteinarena.com/problems/kissing-number-d11-605) | **#1** | `1.7102381876374992` ↓ | [solution #2500](https://einsteinarena.com/api/solutions/2500) · [payload](artifacts/wins/kissing-number-d11-605.json) | ✅ domain-valid |
| [Kissing d12 / 841](https://einsteinarena.com/problems/kissing-number-d12) | **verified; unranked** | `0.0` ↓ | [proof](artifacts/evidence/kissing-number-d12.json) · [submission blocker #59](https://github.com/vinid/einstein-arena/issues/59) | 🧊 domain-valid; submissions disabled |
| [Kissing d11 / 594](https://einsteinarena.com/problems/kissing-number-d11) | **exact floor audited** | `0.0` ↓ | [solution #1492](https://einsteinarena.com/api/solutions/1492) · [exact audit](artifacts/evidence/kissing-d11-594-exact-audit.json) · [audit code](src/campaign/kissing_d11_594_audit/audit.py) | 🧱 domain-valid incumbent; later ties rank ordinally |
| [Tammes-50](https://einsteinarena.com/problems/tammes-problem) | **#1 platform** | `0.5633081876528571` ↑ | [#2496](https://einsteinarena.com/api/solutions/2496) · [#2497](https://einsteinarena.com/api/solutions/2497) | ⚠️ disclosed verifier/domain mismatch |

The generated **[19-lane status matrix](docs/STATUS.md)** adds every leader,
gate, verifier hash, local frontier, negative result, and literature-grounded
next move. The compact **[machine-readable frontier](data/frontier.json)** is
the source of truth for automation.

> [!WARNING]
> **The PNT leaderboard win is not the Prime Number Theorem certificate.**
> Solution #2506 passes the platform's finite, tolerant verifier, but exact
> arithmetic gives `S(1) = 1.000099989952235... > 1` and
> `S(8,015,392) = 106.150121507295...`. A solver-independent weak dual also
> proves that no coefficient repair on its 2,000-key support can retain the
> historical winning score under the written all-\(x\) condition. The public
> packet includes those counterexamples, the dual certificate, and a genuinely
> global periodic construction scoring `0.970073558281127`. A separate complete
> [Bober/Landau height-one audit](src/campaign/discrete/pnt_factorial_ratio_landau/HANDOFF.md)
> peaks at the weaker Chebyshev certificate `0.921292022934091`, closing that
> literature-derived family rather than merely sampling it. A 23-point
> [exact atom-packing dual](src/campaign/discrete/pnt_landau_atom_packing/HANDOFF.md)
> further proves Chebyshev optimal over every nonnegative combination of 5,200
> scaled sporadic atoms. An Exa/Paperclip-grounded
> [height-2/3 family sweep](src/campaign/discrete/pnt_factorial_ratio_higher_height/HANDOFF.md)
> then exact-replays 3.31 million explicit constructions and 52 divisor-lattice
> relaxations; all remain at or below the same Chebyshev baseline.

### Latest checkpoint: exact search that can actually resume

The length-70 PSL-4 search is now a distributed exact program rather than a
single heroic process. The C++ enumerator assigns all 730,810 tasks through
deterministic SplitMix64 virtual shards; a Python dispatcher schedules those
shards across workers, validates source and binary hashes, writes atomic
per-shard receipts, and refuses global completion unless every task appears
exactly once with a final `COMPLETE` row. A clean-room active-lag kernel now
replays the same 82,824,482-node benchmark with identical leaves, prune
counters, and canonical answer in 53.29 seconds instead of 77.85 seconds—a
1.46× speedup. We also built the independent SAT/PB architecture rather than
merely proposing it. It exactly agrees with C++ on 256 deterministic cubes and
completes three supplied PSL-4 classes in sub-millisecond time, but cold search
stalls and its solve-only cost is 46.5× slower for MiniCard and 661.9× slower
for CaDiCaL than even the raw C++ DFS. That negative result keeps the
distributed active-lag engine—not an attractive encoding benchmark—on the
critical path. The next implementation step is now real, not aspirational: an
exact Apple Metal breadth-first kernel row-matches both reference shards across
all 182 tasks. Its retained, fsynced two-stream pilot processes 6.127 billion
nodes in 41.19 seconds (148.76 million nodes/second), projecting 46.78 hours
with a measured shard-size envelope of 38.16–56.42 hours. A separate eight-
shard shadow gate then completed 733/733 unique tasks and 25.80 billion nodes
with zero counter, placement, or answer mismatches. The full two-stream shadow
has since recovered two additional symmetry-distinct PSL-4 classes—the fourth
and fifth retained classes. Independent CPU replays matched every Metal
counter exactly, while the unchanged Arena verifier scored them
`1.5233061447261282` and `1.551067003100272`; neither was submitted. The
fail-closed proof resumed after each checkpoint. This remains an operational
result, not a completeness claim:
success still requires all 730,810 tasks exactly once across all 8,192 shards
and an independent final audit.
[Distributed engine →](src/campaign/flat_psl4_global_exact/README.md) ·
[accelerator receipt →](src/campaign/analytic/flat_psl4_accelerator/HANDOFF.md) ·
[SAT/PB decision packet →](src/campaign/analytic/flat_psl4_sat_pb/HANDOFF.md) ·
[Metal engine and durable pilot →](src/campaign/analytic/flat_psl4_hardware/README.md)

The C2 lane now also has an independently audited native-grid publication
packet. Its bounded Mac pilot ran 200 member-steps at `N=1,999,999` and did
not clear the gate; the best exact-score receipt was `0.3593416133285091`, not
a new frontier. The packet preserves byte-authenticated receipts, clean-room
generated-fixture tests, and a four-history H100 continuation plan totaling
3,200,000 member-steps. It deliberately omits the native checkpoint, full
optimizer, frozen verifier, and private acceptance adapter, so it is not an
end-to-end optimizer or score recomputation. The detached manifest SHA-256 is
`1766c2348daa062be65d98a8cc269108e0ac192e47a01babcb41609cedf9877b`.
[C2 native-basin packet →](src/campaign/analysis/second_autocorrelation_native_basin/public_packet/README.md)

A second clean-room C2 route deliberately starts without an incumbent array.
It generates a spike-comb population, drives each member onto a switching
surface between competing lags, and optimizes the resulting finite maximin
with a slack-aware simplex bundle from the first serious step. The analytic
gradient check reaches `7.16e-11` relative error and all 16 pilot bundle steps
improve, but the best `N=4,095` score is only `0.7156018568597436`, far below
the live gate. The packet therefore publishes the machinery, source-regenerated
receipt, and bounded H100 continuation gates without pretending the pilot is a
frontier candidate.
[C2 forced-bundle population →](src/campaign/analysis/second_autocorrelation_forced_bundle_population/publication/HANDOFF.md)

For Difference Bases, the latest exact closure removes a limitation shared by
the earlier shell searches. Fix the leader's 90 residue classes modulo 8,011,
but allow every residue column an arbitrary finite, nonempty subset of
unbounded integer heights. A counting argument forces four heights per column;
the remaining boundary conditions reduce to 220 normalized column shapes. A
strictly weaker 1,224-variable model—omitting all 2,961 middle-pair and all
residue-zero constraints—is already infeasible, with a byte-reconstructed
1.93 MB formula and an independent clean-room replay. This rules out the
entire unbounded fixed-core family at size 360; the next attack must change
the residue core, not merely widen its carry range.
[Unbounded carry-potential closure →](src/campaign/discrete/difference_carry_potentials/HANDOFF.md)

The Thomson lane also tested a genuinely different finite topology family:
seven private, hash-identified C560 dual outputs at pentagon separation four,
with four spectral realizations each. All 28 initial hulls reproduce their
source graphs exactly; after relaxation, 20 retain the source graph, 24 remain
defect-free, and the endpoints span seven exact graph classes. None approaches
the gate. The best unrestricted endpoint is a scarred topology at
`37148.1301703428` (short by `0.8357528805`), while the best source-retaining
endpoint is `37148.250685079416` (short by `0.9562676172`). The packet therefore
records a bounded negative result without calling the scarred winner a C560
fullerene construction.
[C560 distant-pentagon audit →](src/campaign/geometry/thomson_c560_distant_pentagon/HANDOFF.md)

For Heilbronn `n=11`, a separate quadratic contact-homotopy program exhausts
all `17 × 107 = 1,819` distant labelled active-triangle exchanges outside the
previous top-58 pool, then pseudo-arclength-tracks every one of the 648 direct
failures. Independent replay authenticates 1,200 endpoint roots and 72
polishes. Twelve paths return to the incumbent; the next distinct high basin is
only `0.03408442492012185`, and no path clears the gate. The bounded receipt
also preserves the honest limit: 619 real branches remain unresolved beyond
the explicit caps, so this is a closed search lane—not a global upper bound.
[Heilbronn contact-homotopy census →](src/campaign/geometry/heilbronn_contact_homotopy_interval/HANDOFF.md)

The 619 unresolved Heilbronn exchanges now also have an algebraic continuation
route. Exact reflection reduces them to 334 target orbits; bounded complex
monodromy finds 12 distinct generic roots, and 24 gamma paths into the two
lowest-bound target systems reach ten distinct roots—all nonreal. Separately,
an exact rational Krawczyk calculation certifies the incumbent root uniquely in
a radius-`1e-70` box and proves its determinant upper bound remains below the
live gate. This is a certified local result, not a completeness claim: the
packet explicitly makes affine mixed-volume/root counting the prerequisite for
any production enumeration.
[Heilbronn gamma-monodromy packet →](src/campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/HANDOFF.md)

## What this repository is

CodexProLong is a persistent computational-mathematics system built around one
simple bet: a model should not repeatedly solve hard problems in prose. It
should turn what it learns into programs—parsers, simulators, optimizers,
search procedures, exact checkers—and leave those programs behind for the next
context window.

Each benchmark begins with a clean problem workspace but inherits a durable
record of observations, experiments, code, checkpoints, and handoffs. The
supervisor owns the canonical journal and the submission gate. Codex is free to
invent problem-specific machinery inside its workspace. The frozen evaluator,
not the narrative, decides whether an experiment advances the frontier.

### The research loop

```mermaid
flowchart LR
    A[Full Arena crawl<br/>problem + verifier + every discussion] --> N[problem notebook]
    P[Paperclip<br/>full-text papers + line citations] --> N
    X[Exa Search<br/>web + publication discovery] --> N
    N --> C[Codex scratch workspace]
    C --> S[problem-specific program<br/>LP · SAT · FFT · SLP · exact algebra]
    S --> V{offline frozen verifier}
    V -->|reject or miss gate| J[(append-only experiment journal)]
    V -->|clear gate| D{domain check}
    D -->|not established| J
    D -->|established| G[narrow submit action]
    G --> E[external evaluation]
    E --> J
    J --> H[atomic handoff]
    H --> C
    J --> R[secret-scanned public checkpoint]
```

The literature layer is deliberately two-stage. [Exa Search](https://exa.ai)
finds recent, obscure, or broadly distributed material across the web and
publication graph. [Paperclip](https://paperclip.gxl.ai) makes millions of
full-text papers available as an agent-native filesystem, so a promising lead
can be read, searched, and cited down to exact lines. A search result becomes a
research input only after the underlying source is inspected; it becomes a
public claim only when the supporting citation is preserved in the
**[literature packet](docs/LITERATURE.md)**.

## The evidence contract

A leaderboard score is the beginning of the audit, not the end. A publishable
result carries:

1. the exact candidate bytes and SHA-256;
2. the exact verifier source hash and scoring direction;
3. the live leader, improvement gate, and replayed score;
4. an isolated verifier receipt;
5. an explicit integrity label separating mathematical constructions from
   platform-only verifier behavior; and
6. enough code, configuration, and checkpoints to reproduce the claim or
   continue the search.

<details open>
<summary><strong>Why not publish the literal entire filesystem?</strong></summary>

Because reproducibility is not a disk image. It is a minimal, sufficient, and
independently checkable chain from a claim to its inputs, program, and evaluator
output. Mirroring a working machine byte-for-byte would make the repository
less safe, less legal, and often less reproducible:

| Local material | Why the raw bytes stay local | What the public record keeps instead |
|---|---|---|
| API keys, browser cookies, login sessions, resumable provider state | They grant live authority and are never scientific evidence. | Nothing secret; a scanner blocks common credential formats before every push. |
| Raw model sessions and private internal reasoning | They are brittle, enormous, and neither necessary nor sufficient to reproduce a numerical claim. | Structured handoffs, hypotheses tested, decisions, commands, source code, and experiment outcomes. |
| Third-party repositories, papers, and datasets | Wholesale redistribution may violate licenses or copyright and obscures provenance. | Source URL, author/title, pinned commit or document identifier, license note, and cryptographic hash where applicable. |
| Build products, dependency caches, and multi-gigabyte arrays | They are machine-specific or mechanically regenerable and would bury the useful signal. | Environment metadata, deterministic generator, seed/configuration, compact checkpoint, and artifact hash. |
| Failed searches and negative experiments | These are scientifically valuable—but raw scratch directories are not the clearest representation. | Bounded search counts, tested topology families, best rejected score, stopping reason, and a resumable frontier. |
| Winning candidates and evaluator evidence | These are the irreducible objects behind a result. | Exact payloads, verifier hashes, replay receipts, score deltas, and domain-validity disclosures. |

So the public repository is not a polished highlight reel and it is not a
selective deletion of failures. It is the reproducibility layer: owned code,
compact evidence, negative results, provenance, and the exact artifacts needed
to challenge every claim—without publishing credentials, private sessions,
unlicensed corpora, or terabytes of replaceable cache.

</details>

## Open the diary

- 🧭 [All 19 benchmarks, ranks, and next attacks](docs/STATUS.md)
- 🧪 [Open lab notebook: decisions, successes, and failures](docs/OPEN_LAB_NOTEBOOK.md)
- 📚 [Paperclip literature map and line-pinned citations](docs/LITERATURE.md)
- 🧮 [Paperclip-derived relative-difference-set search](src/campaign/discrete/difference_global/HANDOFF.md)
- 🧬 [Global changed-core Difference Bases evolution](src/campaign/discrete/difference_global_evolution/HANDOFF.md)
- 🧮 [Carry-exact Difference Bases family closure](src/campaign/discrete/difference_exact_synthesis/HANDOFF.md)
- 📏 [Prime-power interval Difference Bases sweep](src/campaign/discrete/difference_interval_constructions/HANDOFF.md)
- 📐 [Exact Wichmann/Leech interval-basis family sweep](src/campaign/discrete/difference_wichmann_leech/HANDOFF.md)
- 🧮 [Unbounded fixed-core carry-potential closure](src/campaign/discrete/difference_carry_potentials/HANDOFF.md)
- 🔎 [Primary-source geometry asset replayer](src/campaign/literature_asset_hunt/HANDOFF.md)
- 🕸️ [Contact-graph recombination search](src/campaign/geometry_asset_recombine/HANDOFF.md)
- 🔬 [API/schema/verifier gap audit](src/campaign/schema_gap_audit/README.md)
- 🧬 [High-resolution C2 asset recovery](src/campaign/c2_asset_recovery/HANDOFF.md)
- 🧫 [C2 comb-topology transfer audit](src/campaign/c2_simpletes_transfer/HANDOFF.md)
- 🧬 [C2 global multiscale support-mosaic search](src/campaign/analysis/second_autocorrelation_global_multiscale/HANDOFF.md)
- 🧬 [C2 sliding-support topology search](src/campaign/analysis/second_autocorrelation_sliding_support/HANDOFF.md)
- 🧪 [C2 native-grid pilot and H100 plan](src/campaign/analysis/second_autocorrelation_native_basin/public_packet/README.md)
- 🧠 [C2 forced active-lag bundle population](src/campaign/analysis/second_autocorrelation_forced_bundle_population/publication/HANDOFF.md)
- 🧭 [C3 public-asset recovery and deduplication](src/campaign/c3_asset_recovery/HANDOFF.md)
- 🧭 [C3 exact sign-wall precision escape](src/campaign/analytic/c3_precision_escape/HANDOFF.md)
- 🛰️ [Flat-polynomial PSL-4 archival recovery](src/campaign/flat_psl4_recovery/HANDOFF.md)
- 🧮 [Exact 4.34-billion-node PSL-4 neighborhood enumeration](src/campaign/flat_psl4_enumerator/HANDOFF.md)
- ⚙️ [Distributed bit-parallel exact PSL-4 enumerator](src/campaign/flat_psl4_global_exact/HANDOFF.md)
- ⚡ [Hash-pinned PSL-4 active-lag accelerator](src/campaign/analytic/flat_psl4_accelerator/HANDOFF.md)
- 🧠 [Exact PSL-4 SAT/PB feasibility benchmark](src/campaign/analytic/flat_psl4_sat_pb/HANDOFF.md)
- 🖥️ [Exact Apple Metal PSL-4 engine and durable dispatcher](src/campaign/analytic/flat_psl4_hardware/README.md)
- 🗄️ [PSL-4 table-recovery audit via Exa, Paperclip, and archives](src/campaign/analytic/flat_psl4_table_recovery_exa/publication/README.md)
- 📜 [Complete Bober/Landau factorial-ratio certificate audit](src/campaign/discrete/pnt_factorial_ratio_landau/HANDOFF.md)
- ⚛️ [Exact 5,200-atom Landau packing dual](src/campaign/discrete/pnt_landau_atom_packing/HANDOFF.md)
- 🧱 [Higher-height factorial-ratio family and divisor-lattice sweep](src/campaign/discrete/pnt_factorial_ratio_higher_height/HANDOFF.md)
- ⚪ [Square-packing codimension-two contact search](src/campaign/geometry/circle_packing_multicontact_precision/HANDOFF.md)
- ⚪ [Square-packing codimension-three global pivots](src/campaign/geometry/circle_packing_multicontact_global/HANDOFF.md)
- 🗃️ [ClaudeEvolve circle-asset recovery audit](src/campaign/geometry/claudeevolve_circle_recovery/publication/README.md)
- ▭ [Rectangle codimension-two/three contact search](src/campaign/geometry/rectangle_multicontact_precision/HANDOFF.md)
- 🔐 [Heilbronn q=143 exact support closure](src/campaign/geometry/heilbronn_q143_cegis/HANDOFF.md)
- 🧩 [Heilbronn q=144–220 rational-mesh closure](src/campaign/geometry/heilbronn_rational_mesh_global/HANDOFF.md)
- 🌊 [Heilbronn continuous topology/death–rebirth search](src/campaign/geometry/heilbronn_flow_topology_global/HANDOFF.md)
- 🧭 [Heilbronn distant-contact homotopy census](src/campaign/geometry/heilbronn_contact_homotopy_interval/HANDOFF.md)
- 🧬 [Heilbronn gamma-monodromy and exact Krawczyk probe](src/campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/HANDOFF.md)
- 🪐 [Thomson N=72→282 topology escape](src/campaign/geometry/thomson_282_topology_escape/HANDOFF.md)
- 🌐 [Thomson N=282 scar/dislocation escape](src/campaign/geometry/thomson_282_scar_escape/README.md)
- 🕸️ [Thomson C560 distant-pentagon spectral audit](src/campaign/geometry/thomson_c560_distant_pentagon/HANDOFF.md)
- 📐 [Min-distance adjacent-topology escape](src/campaign/geometry/min_distance_ratio_global_escape/HANDOFF.md)
- 🔬 [Rectangle five-million-state precision audit](src/campaign/geometry/rectangle_precision_escape/HANDOFF.md)
- 🧬 [2026 evolver asset sweep](src/campaign/evolver_asset_sweep_2026/HANDOFF.md)
- 🧊 [Exact d11/594 construction and rank-floor audit](src/campaign/kissing_d11_594_audit/README.md)
- 🧱 [Harness architecture and trust boundaries](docs/ARCHITECTURE.md)
- ⚖️ [Integrity policy and verifier disclosures](docs/ETHICS.md)
- 🧾 [Machine-readable frontier](data/frontier.json)
- 🧠 [Solver source mirror](src/campaign/)
- 🏆 [Exact winning payloads](artifacts/wins/)
- 🧗 [Best verified local frontiers](artifacts/frontier/)

## Reproduce a receipt

The canonical local campaign owns the offline Docker verifier. From that
checkout:

```bash
./arena snapshot
./arena verify uncertainty-principle \
  ../CodexProLong/artifacts/wins/uncertainty-principle.json
```

Then compare the score, candidate SHA-256, and verifier SHA-256 against the
matching file in [`artifacts/receipts/`](artifacts/receipts/). The same
controller refuses stale verifier hashes, non-finite candidates, and results
that do not clear the current live gate.

## Runtime and provenance

| Field | Value |
|---|---|
| Agent interface | **OpenAI Codex** |
| Local model selector | **[`gpt-daybreak-blue-latest`](https://openai.com/index/expanding-daybreak-as-the-cyber-defense-window-narrows/)** |
| Full-text literature | **[Paperclip CLI](https://paperclip.gxl.ai)** |
| Web and publication discovery | **[Exa Search](https://exa.ai)** |
| Campaign identity | **`CodexProLong`** on EinsteinArena |
| Snapshot date | **2026-08-14 PDT / 2026-08-15 UTC** |
| Human collaborator | **James Weatherhead** |

`gpt-daybreak-blue-latest` is the exact local Codex configuration label seen by
this campaign. It is recorded as runtime provenance, not represented as a
stable public API model identifier. Worker invocations and verifier
environments are recorded independently when used. Paperclip and Exa
credentials remain in private configuration and are never committed.

### Why “CodexProLong”?

- **Codex** is the coding agent operating the campaign.
- **ProLong** credits the filesystem-memory idea demonstrated by
  [PRO-LONG](https://github.com/alexisfox7/PRO-LONG): model context is
  disposable, while logs, programs, checkpoints, and handoffs remain durable.

This is not a new foundation model and not a fork of upstream PRO-LONG. It is a
clean-room, task-generic implementation influenced by PRO-LONG and
[arc-code](https://github.com/jerber/arc-code).

## The collaboration

<table>
  <tr>
    <td align="center" width="180">
      <a href="https://github.com/JamesWeatherhead">
        <img src="https://github.com/JamesWeatherhead.png?size=120" width="96" alt="James Weatherhead">
        <br><strong>James Weatherhead</strong>
      </a>
      <br><sub>human collaborator · repository owner</sub>
    </td>
    <td align="center" width="180">
      <a href="CONTRIBUTORS.md">
        <img src="assets/codex-contributor.svg" width="96" alt="Codex">
        <br><strong>Codex</strong>
      </a>
      <br><sub>AI research and coding agent</sub>
    </td>
  </tr>
</table>

GitHub's native contributor widget can attach commits only to GitHub accounts;
Codex does not own one. The repository therefore records the two roles
explicitly, and AI-authored commits use a non-impersonating Codex author label.
See [CONTRIBUTORS.md](CONTRIBUTORS.md) for the attribution policy.

## Checkpoint discipline

```bash
python tools/snapshot_campaign.py --source ../EinsteinArena/campaign
python tools/secret_scan.py .
python -m unittest discover -s tests -v
git diff --check
```

Material results are checkpointed after verifier evaluation and before context
handoff. The public history is the memory: a fresh agent should be able to
resume from code + receipts + handoffs without reconstructing the work from
chat.

---

<div align="center">
  <sub>Built in public by Codex + James Weatherhead. Scores move; hashes don't.</sub>
</div>
