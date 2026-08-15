<div align="center">
  <img alt="Codex with ProLong memory, using Exa and Paperclip as research tools" src="assets/prolong-memory-codex.jpg" width="100%">

  <h1>CodexProLong</h1>
  <h2>We gave Codex a memory. It built a research lab.</h2>

  <p>
    An open computational-mathematics experiment by James Weatherhead,
    built with OpenAI Codex.
  </p>

  <p>
    <strong>7 platform #1s</strong> ·
    <strong>5 domain-valid #1s</strong> ·
    <strong>19 benchmarks</strong> ·
    <strong>every claim receipt-backed</strong>
  </p>

  <p>
    <a href="docs/STATUS.md"><strong>Explore the results</strong></a> ·
    <a href="docs/ARCHITECTURE.md"><strong>See how it works</strong></a> ·
    <a href="artifacts/receipts/"><strong>Verify the receipts</strong></a>
  </p>

  <sub>Live snapshot: August 15, 2026. Rankings can change; archived hashes do not.</sub>
</div>

## The experiment

> We did not give Codex a single fixed solver. We gave it a goal, research
> tools, frozen verifiers, and a filesystem.

Most agent sessions end when the context window ends. CodexProLong asks what
happens when the useful output of reasoning becomes durable software instead:
programs, tests, checkpoints, experiment journals, and handoffs that the next
agent can actually use.

Each of the 19 EinsteinArena construction benchmarks begins in an isolated
workspace. Within that boundary, Codex can investigate the problem, read the
literature, build new tools, run experiments, and change strategy when an idea
fails. It has produced exact C++ enumerators, Apple Metal search kernels,
SAT/PB models, nonlinear optimizers, topology searches, archival-recovery
tools, and independent replay harnesses. Different problem, different program.

The human collaborator sets the goal, guards the external-action boundary,
and decides what counts as a scientifically honest claim. The verifier—not the
narrative—decides whether an experiment advances the frontier.

## How the lab works

- **Discover.** Codex uses [Exa Search](https://exa.ai) for web and publication
  discovery and [Paperclip](https://paperclip.gxl.ai) for searchable full-text
  literature. Exa and Paperclip are tools, not subagents.
- **Build.** Codex turns promising ideas into problem-specific programs rather
  than repeatedly trying to solve the problem in prose.
- **Verify.** Frozen evaluators, live improvement gates, and explicit domain
  checks separate a real construction from a numerical mirage.
- **Remember.** ProLong filesystem memory preserves code, evidence, failures,
  and resumable state across context windows and parallel workstreams.

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

> **Integrity note.** Seven entries lead the current platform snapshot; five
> also satisfy the written mathematical domain. Two depend on disclosed
> verifier/domain differences. A separate domain-valid construction verifies
> perfectly but cannot be submitted because that lane is closed. The complete
> distinction is preserved in the [19-lane status matrix](docs/STATUS.md) and
> [integrity policy](docs/ETHICS.md).

## Why it matters

- **Reasoning becomes reusable software.** A successful idea is compiled into
  something that can run thousands or billions of times.
- **Long-horizon work survives context boundaries.** New agents inherit tested
  machinery and evidence instead of rediscovering yesterday's dead ends.
- **Verification comes before amplification.** Every positive claim is tied to
  the evaluator bytes and conditions under which it is true.
- **Failures become research memory.** Bounded negative results narrow the next
  search instead of disappearing into a transcript.

The larger bet is simple: as coding agents improve, the most capable research
harness may be the one that gives them freedom to build what each problem
requires—while making the evidence harder to fake than the story is to tell.

## Every claim carries a receipt

A leaderboard score is the beginning of the audit, not the end. A publishable
result records the exact candidate bytes and SHA-256, the verifier source hash
and scoring direction, the live leader and improvement gate, an isolated
replay receipt, and an integrity label distinguishing mathematical results
from platform-only behavior.

The public repository is deliberately not a mirror of the working machine. It
keeps the owned code and irreducible evidence needed to reproduce or challenge
a claim, while excluding credentials, private sessions, unlicensed corpora,
and replaceable caches.

## Explore the lab

- **[Results](docs/STATUS.md)** — all 19 benchmarks, current ranks, frontiers,
  disclosures, and next attacks.
- **[Open notebook](docs/OPEN_LAB_NOTEBOOK.md)** — the decisions, successful
  experiments, failed routes, and resumable checkpoints.
- **[Architecture](docs/ARCHITECTURE.md)** — the harness, trust boundaries,
  verifier gate, and public-memory pipeline.
- **[Literature](docs/LITERATURE.md)** — the Exa/Paperclip research map and
  line-pinned primary sources.
- **[Integrity](docs/ETHICS.md)** — domain-valid wins, verifier disclosures,
  submission rules, and evidence policy.

## The collaboration

CodexProLong is built in public by
[James Weatherhead](https://github.com/JamesWeatherhead) with OpenAI Codex.
James owns the research direction and repository; Codex is the research and
coding agent. Exa and Paperclip extend the literature workflow as tools. See
[CONTRIBUTORS.md](CONTRIBUTORS.md) for the attribution policy.

---

<div align="center">
  <strong>Scores move; hashes don't.</strong>
</div>
