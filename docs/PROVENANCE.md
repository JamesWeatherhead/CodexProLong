# Provenance

Campaign window: **August 14–15, 2026 PDT**. Frozen public snapshot:
**2026-08-15T12:07:25.964492Z**.

- Agent interface: OpenAI Codex.
- Local model selector: [`gpt-daybreak-blue-latest`](https://openai.com/business/solutions/cybersecurity/).
- Scientific-literature search: [Paperclip](https://paperclip.gxl.ai/).
- Web and publication discovery: [Exa Search](https://exa.ai/).
- Competition identity: `CodexProLong` on [EinsteinArena](https://einsteinarena.com/).
- Human collaborator and repository owner: James Weatherhead.
- Long-horizon design influences: [PRO-LONG](https://github.com/alexisfox7/PRO-LONG)
  and [arc-code](https://github.com/jerber/arc-code).

## Model evidence

The model selector comes from local Codex session metadata. The five winning
submission events were recorded under one campaign turn using that selector at
`ultra` reasoning effort, and the candidate hashes in those events match the
five retained receipts.

This is local provenance, not an OpenAI-signed attestation. The identifier is a
runtime label and may not be publicly selectable or permanently resolve to
identical weights. Public claims are therefore anchored to Arena solution IDs,
candidate hashes, verifier hashes, scores, and timestamps rather than to a
claim of model reproducibility.

## Construction lineage

The campaign did not start every construction from zero. It continued public
Arena solutions from Hyra, ExoMind-TTS, and BasinHopper, then searched and
verified new constructions. The exact source solution for each result is
listed in the [evidence index](../artifacts/README.md). This lineage is part of
the result, not a footnote to omit.

## Public release boundary

The current release tree contains selected project-authored documentation,
receipts, hashes, a frozen snapshot, and one certificate record. The production
controller, prompts, private session text, raw research journal, retrieved
corpora, tool outputs, problem-specific solver implementations, checkpoints,
and executable world models are not included at the branch tip; earlier
MIT-licensed revisions remain in repository history.

PRO-LONG is an independent MIT-licensed project and is credited as a design
influence. No claim is made that CodexProLong is an official OpenAI,
EinsteinArena, PRO-LONG, Exa, or Paperclip product.
