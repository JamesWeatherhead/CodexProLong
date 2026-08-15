# CodexProLong

**I gave a Codex agent running OpenAI’s Daybreak Blue model persistent memory
and sent it into EinsteinArena.**

The agent could search the web with Exa, search scientific literature with
Paperclip, write and run its own solvers, and continue from earlier attempts
instead of starting over.

**One persistent campaign reached five valid #&#8203;1 constructions across 17
rankable EinsteinArena benchmarks.**

Every positive claim links to public evidence.

<!-- BEGIN GENERATED:SNAPSHOT -->
<p align="center">
  <strong>5</strong> valid #1s &nbsp;·&nbsp;
  <strong>17</strong> rankable benchmarks &nbsp;·&nbsp;
  <strong>1</strong> persistent campaign
</p>
<p align="center">
  <sub>“Valid #&#8203;1” means the construction ranked first in the frozen snapshot,
  passed the unchanged verifier, and followed the written problem rules.</sub>
</p>
<!-- END GENERATED:SNAPSHOT -->

<p align="center">
  <a href="https://einsteinarena.com"><strong>EinsteinArena</strong></a> ·
  <a href="docs/STATUS.md"><strong>Results</strong></a> ·
  <a href="artifacts/receipts/"><strong>Public evidence</strong></a>
</p>

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

EinsteinArena turns open mathematical problems into executable benchmarks: an
agent submits a construction, and a verifier scores it.

- **Model:** OpenAI Daybreak Blue
- **Agent:** Codex
- **Memory:** an append-only [PRO-LONG-inspired](https://github.com/alexisfox7/PRO-LONG) research journal
- **Research tools:** [Exa Search](https://exa.ai) and [Paperclip](https://paperclip.gxl.ai)
- **Environment:** 17 rankable EinsteinArena benchmarks with frozen verifiers

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
the benchmark verifier and the written problem rules:

- **Erdős minimum overlap** — [#1 result](https://einsteinarena.com/api/solutions/2507) · [evidence](docs/ERDOS_MINIMUM_OVERLAP.md)
- **Uncertainty principle** — [#1 result](https://einsteinarena.com/api/solutions/2505) · [evidence](artifacts/receipts/uncertainty-principle.json)
- **First autocorrelation inequality** — [#1 result](https://einsteinarena.com/api/solutions/2504) · [evidence](artifacts/receipts/first-autocorrelation-inequality.json)
- **Kissing number, dimension 12 / 842** — [#1 result](https://einsteinarena.com/api/solutions/2499) · [evidence](artifacts/receipts/kissing-number-d12-842.json)
- **Kissing number, dimension 11 / 605** — [#1 result](https://einsteinarena.com/api/solutions/2500) · [evidence](artifacts/receipts/kissing-number-d11-605.json)

These are improved mathematical constructions on verifier-backed benchmarks.
They are not claims that five underlying open problems have been completely
solved.

## Why persistent memory matters

Most agent sessions lose their working state when the context window ends.
CodexProLong stores experiments, code, failures, scores, checkpoints, hashes,
and handoffs in an append-only research journal.

A later context can search that record, avoid measured dead ends, reuse working
programs, and resume the strongest checkpoint. The context is temporary. The
research state is not.

## Open by construction

The frozen snapshot contains seven platform-leading scores. Five are counted
as valid #1s because they also follow the written mathematical rules.

The other two remain public and explicitly labeled:

- the Prime Number Theorem entry passes the finite platform verifier but not
  the full written all-`x` statement;
- the Tammes entry uses a point outside the required sphere.

The 17-benchmark denominator is the rankable set: seven frozen leaders plus ten
live frontiers. Two retired lanes remain outside that denominator because
platform rules currently prevent a new first place.

Every positive claim links to the candidate, verifier, hashes, score, and
receipt.

[Results](docs/STATUS.md) ·
[Open notebook](docs/OPEN_LAB_NOTEBOOK.md) ·
[Architecture](docs/ARCHITECTURE.md) ·
[Integrity](docs/ETHICS.md) ·
[Retired lanes](docs/BLOCKED_LANES.md)

<details>
<summary><strong>Run details and exact configuration</strong></summary>

- **Model evidence:** local campaign session metadata records all five winning
  submission events under the selector
  [`gpt-daybreak-blue-latest`](docs/PROVENANCE.md) at `ultra` effort. That
  selector is a runtime label, not a claim of a public API identifier or
  permanently identical weights.
- **Snapshot:** frozen August 15, 2026 at 12:07 UTC.
- **Verification:** candidates were replayed against frozen verifier hashes;
  submissions required both domain validity and human confirmation.
- **Human boundary:** James set the campaign direction and authorized external
  submissions and publication; Codex performed research, programming, and
  verifier-backed search.
- **Public boundary:** owned code, candidates, hashes, scores, and receipts are
  published; credentials, private session text, unlicensed corpora, and
  replaceable caches are excluded.

```bash
python tools/certify_erdos_continuous.py --check
python tools/check_readme_claims.py
python tools/check_local_links.py
python -m unittest discover -s tests -v
```

</details>

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

CodexProLong is an independent experiment, not an official OpenAI,
EinsteinArena, PRO-LONG, or ARC Prize product.
