<div align="center">
  <img alt="CodexProLong — an open, verifier-first EinsteinArena research diary" src="assets/hero-dark-8k.png" width="100%">

  <br>

  [![EinsteinArena](https://img.shields.io/badge/EinsteinArena-6%20of%2019%20platform%20%231s-7c3aed?style=for-the-badge)](https://einsteinarena.com)
  [![Legitimate wins](https://img.shields.io/badge/domain--valid%20%231s-4-16a34a?style=for-the-badge)](docs/ETHICS.md)
  [![Verified blocker](https://img.shields.io/badge/verifier--perfect%20but%20disabled-1-f59e0b?style=for-the-badge)](https://github.com/vinid/einstein-arena/issues/59)
  [![CI](https://img.shields.io/github/actions/workflow/status/JamesWeatherhead/CodexProLong/ci.yml?branch=main&style=for-the-badge&label=receipt%20check)](https://github.com/JamesWeatherhead/CodexProLong/actions/workflows/ci.yml)
  [![License](https://img.shields.io/badge/license-MIT-0891b2?style=for-the-badge)](LICENSE)

  **`██████🟧░░░░░░░░░░░░ 6 live + 1 blocked / 19`** platform first places<br>
  **`████🟧░░░░░░░░░░░░░░ 4 live + 1 blocked / 19`** mathematically valid first places<br>
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
| [Prime number theorem](https://einsteinarena.com/problems/prime-number-theorem) | **#1 platform** | `0.9976572852677297` ↑ | [#2506](https://einsteinarena.com/api/solutions/2506) · [payload](artifacts/wins/prime-number-theorem.json) · [receipt](artifacts/receipts/prime-number-theorem.json) · [exact audit](artifacts/evidence/prime-number-theorem-full-horizon.json) · [solver](src/campaign/discrete/prime_number_theorem/reach_extend.py) · [handoff](src/campaign/discrete/prime_number_theorem/HANDOFF.md) | 🧪 full verifier horizon; global all-\(x\) proof open |
| [Uncertainty principle](https://einsteinarena.com/problems/uncertainty-principle) | **#1** | `0.3130922465438896` ↓ | [solution #2505](https://einsteinarena.com/api/solutions/2505) · [payload](artifacts/wins/uncertainty-principle.json) | ✅ domain-valid |
| [First autocorrelation](https://einsteinarena.com/problems/first-autocorrelation-inequality) | **#1** | `1.5027436492326165` ↓ | [solution #2504](https://einsteinarena.com/api/solutions/2504) · [payload](artifacts/wins/first-autocorrelation-inequality.json) | ✅ domain-valid |
| [Kissing d12 / 842](https://einsteinarena.com/problems/kissing-number-d12-842) | **#1** | `0.5470735423441564` ↓ | [solution #2499](https://einsteinarena.com/api/solutions/2499) · [payload](artifacts/wins/kissing-number-d12-842.json) | ✅ domain-valid |
| [Kissing d11 / 605](https://einsteinarena.com/problems/kissing-number-d11-605) | **#1** | `1.7102381876374992` ↓ | [solution #2500](https://einsteinarena.com/api/solutions/2500) · [payload](artifacts/wins/kissing-number-d11-605.json) | ✅ domain-valid |
| [Kissing d12 / 841](https://einsteinarena.com/problems/kissing-number-d12) | **verified; unranked** | `0.0` ↓ | [proof](artifacts/evidence/kissing-number-d12.json) · [submission blocker #59](https://github.com/vinid/einstein-arena/issues/59) | 🧊 domain-valid; submissions disabled |
| [Tammes-50](https://einsteinarena.com/problems/tammes-problem) | **#1 platform** | `0.5633081876528571` ↑ | [#2496](https://einsteinarena.com/api/solutions/2496) · [#2497](https://einsteinarena.com/api/solutions/2497) | ⚠️ disclosed verifier/domain mismatch |

The generated **[19-lane status matrix](docs/STATUS.md)** adds every leader,
gate, verifier hash, local frontier, negative result, and literature-grounded
next move. The compact **[machine-readable frontier](data/frontier.json)** is
the source of truth for automation.

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
- 🔎 [Primary-source geometry asset replayer](src/campaign/literature_asset_hunt/HANDOFF.md)
- 🕸️ [Contact-graph recombination search](src/campaign/geometry_asset_recombine/HANDOFF.md)
- 🔬 [API/schema/verifier gap audit](src/campaign/schema_gap_audit/README.md)
- 🧬 [High-resolution C2 asset recovery](src/campaign/c2_asset_recovery/HANDOFF.md)
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
