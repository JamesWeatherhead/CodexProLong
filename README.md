<div align="center">
  <img alt="Codex with ProLong memory, using Exa and Paperclip as research tools" src="assets/prolong-memory-codex.jpg" width="100%">

  <h1>CodexProLong</h1>

  <p><strong><em>I gave Codex a memory. It built a research lab.</em></strong></p>

  <p>
    An open computational-mathematics experiment by
    <a href="https://github.com/JamesWeatherhead">James Weatherhead</a>,
    built with OpenAI Codex.
  </p>
</div>

<table align="center">
  <tr>
    <td align="center" width="33%"><strong>7</strong><br><sub>platform #1s</sub></td>
    <td align="center" width="33%"><strong>5</strong><br><sub>domain-valid #1s</sub></td>
    <td align="center" width="33%"><strong>19</strong><br><sub>open benchmarks</sub></td>
  </tr>
</table>

<p align="center">
  <a href="docs/STATUS.md"><strong>Explore the results</strong></a> ·
  <a href="docs/ARCHITECTURE.md"><strong>See how it works</strong></a> ·
  <a href="artifacts/receipts/"><strong>Verify the receipts</strong></a>
  <br>
  <sub>Live snapshot: August 15, 2026. Rankings can change; archived hashes do not.</sub>
</p>

## The idea

> **The operating idea:** I did not give Codex a single fixed solver. I gave it
> a goal, research tools, frozen verifiers, and a filesystem.

Most agent sessions end when the context window ends. CodexProLong preserves
the useful output of reasoning as durable software instead: programs, tests,
checkpoints, experiment journals, and handoffs that the next agent can use.

Each of the 19 EinsteinArena construction benchmarks begins in an isolated
workspace. Codex can study the problem, read the literature, build new tools,
run experiments, and change strategy when an idea fails. It has produced exact
C++ enumerators, Apple Metal search kernels, SAT/PB models, nonlinear
optimizers, topology searches, archival-recovery tools, and independent replay
harnesses. Different problem, different program.

I set the research goals, control external actions, and decide what qualifies
as a scientifically honest claim. The verifier—not the narrative—decides
whether an experiment advances the frontier.

## Why “ProLong”?

The name credits [PRO-LONG](https://github.com/alexisfox7/PRO-LONG), the
open-source programmatic-memory harness that demonstrated a powerful idea:
model context can be disposable while files, programs, logs, and checkpoints
remain durable.

**Codex** is the research and coding agent. **ProLong** is the memory
philosophy. CodexProLong is a clean-room, task-generic implementation inspired
by that concept—not a fork, a new foundation model, or an official OpenAI
product.

## How the lab works

| | |
|---|---|
| **1 · Discover**<br>Codex uses [Exa Search](https://exa.ai) for web and publication discovery and [Paperclip](https://paperclip.gxl.ai) for searchable full-text literature. | **2 · Build**<br>Codex turns promising ideas into problem-specific programs instead of repeatedly solving the problem in prose. |
| **3 · Verify**<br>Frozen evaluators, live improvement gates, and domain checks separate real constructions from numerical mirages. | **4 · Remember**<br>ProLong filesystem memory preserves code, evidence, failures, and resumable state across context windows. |

<p align="center">
  <sub>Exa and Paperclip are research tools used by Codex, not subagents or collaborators.</sub>
</p>

## Selected results

The campaign currently holds five first-place constructions that also satisfy
the written mathematical domain.

| Benchmark | Result | Evidence |
|---|---|---|
| [Erdős minimum overlap](https://einsteinarena.com/problems/erdos-min-overlap) | **Domain-valid #1** | [solution #2507](https://einsteinarena.com/api/solutions/2507) · [receipt](artifacts/receipts/erdos-min-overlap.json) |
| [Uncertainty principle](https://einsteinarena.com/problems/uncertainty-principle) | **Domain-valid #1** | [solution #2505](https://einsteinarena.com/api/solutions/2505) · [payload](artifacts/wins/uncertainty-principle.json) |
| [First autocorrelation](https://einsteinarena.com/problems/first-autocorrelation-inequality) | **Domain-valid #1** | [solution #2504](https://einsteinarena.com/api/solutions/2504) · [payload](artifacts/wins/first-autocorrelation-inequality.json) |
| [Kissing number, d12 / 842](https://einsteinarena.com/problems/kissing-number-d12-842) | **Domain-valid #1** | [solution #2499](https://einsteinarena.com/api/solutions/2499) · [payload](artifacts/wins/kissing-number-d12-842.json) |
| [Kissing number, d11 / 605](https://einsteinarena.com/problems/kissing-number-d11-605) | **Domain-valid #1** | [solution #2500](https://einsteinarena.com/api/solutions/2500) · [payload](artifacts/wins/kissing-number-d11-605.json) |

**Integrity:** Seven entries lead the current platform snapshot; five also
satisfy the written mathematical domain. Two depend on disclosed
verifier/domain differences. A separate domain-valid construction verifies
perfectly but cannot be submitted because that lane is closed. The full record
is preserved in the [19-lane status matrix](docs/STATUS.md) and
[integrity policy](docs/ETHICS.md).

## Why it matters

- **Reasoning becomes reusable software.** A successful idea can run thousands
  or billions of times.
- **Long-horizon work survives context boundaries.** New agents inherit tested
  machinery instead of rediscovering yesterday's dead ends.
- **Verification comes before amplification.** Every positive claim is tied to
  the evaluator bytes and the conditions under which it is true.
- **Failures become research memory.** Bounded negative results narrow the next
  search instead of disappearing into a transcript.

The larger bet is simple: as coding agents improve, the most capable research
harness may be the one that gives them freedom to build what each problem
requires—while making the evidence harder to fake than the story is to tell.

## Open by construction

A leaderboard score is the beginning of the audit, not the end. A publishable
result records the exact candidate bytes and SHA-256, the verifier source hash,
the live leader and improvement gate, an isolated replay receipt, and an
integrity label distinguishing mathematical results from platform-only
behavior.

The repository keeps the owned code and irreducible evidence needed to
reproduce or challenge a claim while excluding credentials, private sessions,
unlicensed corpora, and replaceable caches.

## Explore the lab

<p align="center">
  <a href="docs/STATUS.md"><strong>Results</strong></a> ·
  <a href="docs/OPEN_LAB_NOTEBOOK.md"><strong>Open notebook</strong></a> ·
  <a href="docs/ARCHITECTURE.md"><strong>Architecture</strong></a> ·
  <a href="docs/LITERATURE.md"><strong>Literature</strong></a> ·
  <a href="docs/ETHICS.md"><strong>Integrity</strong></a>
</p>

---

<p align="center">
  Built in public by <a href="https://github.com/JamesWeatherhead">James Weatherhead</a>
  with OpenAI Codex · <a href="CONTRIBUTORS.md">Attribution</a> ·
  <a href="LICENSE">MIT License</a>
  <br>
  <strong>Scores move; hashes don't.</strong>
</p>
