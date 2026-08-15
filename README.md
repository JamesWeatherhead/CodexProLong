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

## What this is

CodexProLong is a long-running computational-mathematics experiment. I give
Codex a problem, a frozen verifier, and a goal—but not one universal solver.
Codex investigates the problem and writes whatever executable model it needs:
a search program, simulator, optimizer, SAT model, exact checker, or something
new.

François Chollet, creator of ARC-AGI and co-founder of ARC Prize, describes
this general pattern as
[**“LLM-guided on-the-fly synthesis of a symbolic world model.”**](https://x.com/fchollet/status/2088243704603824311)

A symbolic world model is an executable account of how a problem works. In
plain English: the LLM does not stop at explaining its theory. It turns the
theory into code, runs the code, checks it against evidence, and rewrites the
model when the theory is wrong. On ARC-AGI-3, that can mean learning the rules
of an unfamiliar game. Here, it means learning useful structure inside a
mathematical problem. Different problem, different program.

## The memory is the harness

Most agent sessions forget their work when the context window ends. This one
does not. The name credits
[PRO-LONG](https://github.com/alexisfox7/PRO-LONG), the open-source harness that
inspired the programmatic-memory design.

The core research journal is **append-only**: a new experiment adds a new
record; it does not silently rewrite the old one. Each record preserves the
route taken, the result, the relevant code or checkpoint, and the hashes that
identify the exact artifacts. If an earlier conclusion was wrong, the
correction is appended beside it, leaving the history inspectable.

Before starting another search, Codex searches the journal, handoffs, and
receipts:

- Has this route already been tried?
- What failed, and why?
- Is there a useful program or checkpoint to resume?
- Which verifier, target, and artifact hashes were current?

That makes the memory less like a saved chat and more like a searchable lab
notebook connected to a codebase. Context is disposable; the research state is
not.

## The loop

`set the gate → search memory → research → write code → run → verify → append → repeat`

1. **I set the problem and verification gate.** I control external actions and
   decide what qualifies as a scientifically honest claim.
2. **Codex searches the existing memory.** It resumes useful work and avoids
   repeating measured dead ends.
3. **Codex researches and builds.** It can use
   [Exa Search](https://exa.ai) and
   [Paperclip](https://paperclip.gxl.ai) as research tools, then create whatever
   problem-specific machinery it needs.
4. **The verifier decides.** Candidates are replayed against the frozen
   evaluator and checked against the written mathematical domain.
5. **The result becomes memory.** Code, evidence, failures, checkpoints, and
   receipts are appended for the next context to search.

Codex is the agent. ProLong is the memory around its work. Exa and Paperclip
are tools used by Codex, not subagents or collaborators. CodexProLong is an
independent, clean-room experiment—not a fork, a new foundation model, or an
official OpenAI or ARC Prize product.

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
