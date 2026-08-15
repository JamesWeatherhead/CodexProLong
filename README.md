<div align="center">

# CodexProLong

### I gave a Codex agent running [OpenAI's Daybreak Blue model](https://openai.com/business/solutions/cybersecurity/) persistent memory, pointed it at EinsteinArena, and let it run.

[EinsteinArena](https://einsteinarena.com/) is an open arena where AI agents
collaborate and compete on unsolved science problems; its current problem set
focuses on mathematics.

The agent could search the web with [Exa](https://exa.ai/), search scientific
literature with [Paperclip](https://paperclip.gxl.ai/), write and run its own
solvers, and could learn from previous attempts.

Inspired by [Jeremy Berman's ARC-AGI-3 approach](https://x.com/jeremyberman/status/2087633198822117446),
Codex used what [François Chollet describes as LLM-guided on-the-fly synthesis
of a symbolic world model](https://x.com/fchollet/status/2088243704603824311):
writing executable code to encode its understanding, building the tools and
solvers it needed, and carrying that work forward with persistent memory.

<!-- BEGIN GENERATED:SNAPSHOT -->
**Following its first weekend of autonomous research, CodexProLong is #&#8203;1
on five of EinsteinArena's 17 rankable problems.**
<!-- END GENERATED:SNAPSHOT -->

<p align="center">
  <a href="https://einsteinarena.com"><strong>EinsteinArena</strong></a> ·
  <a href="docs/STATUS.md"><strong>Results</strong></a> ·
  <a href="artifacts/receipts/"><strong>Public evidence</strong></a>
</p>

</div>

<p align="center">
  <a href="assets/source/prolong-memory-codex.jpg">
    <img
      alt="Codex working with persistent ProLong memory, Exa Search, and Paperclip"
      src="assets/prolong-memory-codex.webp"
      width="92%">
  </a>
  <br>
  <sub>Codex is the agent. ProLong keeps its research state. Exa searches the
  web. Paperclip searches the literature.</sub>
</p>

## The experiment

EinsteinArena turns open, unsolved research questions into executable problems:
an agent submits a construction, and a frozen verifier scores it. The current
arena is focused on mathematical optimization.

- **Model:** [OpenAI Daybreak Blue](https://openai.com/business/solutions/cybersecurity/)
- **Agent:** Codex
- **Memory:** an append-only [PRO-LONG-inspired](https://github.com/alexisfox7/PRO-LONG) research journal
- **Research tools:** [Exa Search](https://exa.ai) and [Paperclip](https://paperclip.gxl.ai)
- **Environment:** 17 rankable, open mathematical problems with frozen verifiers

Codex was not given one universal math solver. It could study each problem,
search prior work, write whatever program it needed, run experiments, inspect
failures, and resume useful checkpoints later. Different problems produced
different programs; useful code and evidence survived while failed hypotheses
became constraints on the next attempt.

`read → research → build → run → verify → remember → repeat`

<p align="center">
  <a href="assets/source/codexprolong-system-loop.jpg">
    <img
      alt="CodexProLong architecture from research through verification and persistent memory"
      src="assets/codexprolong-system-loop.webp"
      width="100%">
  </a>
  <br>
  <sub>Each verified result returns to memory, so the next context inherits the
  work instead of starting over.</sub>
</p>

## What it found

At the frozen snapshot, five constructions held first place and passed both
the platform verifier and the written problem rules:

- **Erdős minimum overlap** — [#1 result](https://einsteinarena.com/api/solutions/2507) · [evidence](docs/ERDOS_MINIMUM_OVERLAP.md)
- **Uncertainty principle** — [#1 result](https://einsteinarena.com/api/solutions/2505) · [evidence](artifacts/receipts/uncertainty-principle.json)
- **First autocorrelation inequality** — [#1 result](https://einsteinarena.com/api/solutions/2504) · [evidence](artifacts/receipts/first-autocorrelation-inequality.json)
- **Kissing number, dimension 12 / 842** — [#1 result](https://einsteinarena.com/api/solutions/2499) · [evidence](artifacts/receipts/kissing-number-d12-842.json)
- **Kissing number, dimension 11 / 605** — [#1 result](https://einsteinarena.com/api/solutions/2500) · [evidence](artifacts/receipts/kissing-number-d11-605.json)

These are improved mathematical constructions for verifier-backed open
problems.
They are not claims that five underlying open problems have been completely
solved.

## Why persistent memory matters

Most agent sessions lose their working state when the context window ends.
CodexProLong stores experiments, code, failures, scores, checkpoints, hashes,
and handoffs in an append-only research journal.

A later context can search that record, avoid measured dead ends, reuse working
programs, and resume the strongest checkpoint. The context is temporary. The
research state is not.

## Explore the lab

[Results](docs/STATUS.md) ·
[Open notebook](docs/OPEN_LAB_NOTEBOOK.md) ·
[Architecture](docs/ARCHITECTURE.md) ·
[Compute plan](docs/COMPUTE.md) ·
[Literature](docs/LITERATURE.md) ·
[Integrity](docs/ETHICS.md)

---

Built in public by [James Weatherhead](https://github.com/JamesWeatherhead)
with OpenAI Codex · [Attribution](CONTRIBUTORS.md) · [MIT License](LICENSE)
