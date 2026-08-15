# Architecture

CodexProLong separates temporary model context from persistent research state.

```text
problem + verifier
        ↓
Codex research turn ──→ Exa / Paperclip
        ↓
problem-specific program or executable world model
        ↓
local experiment ──→ frozen verification
        ↓
append-only journal + files + checkpoint
        ↺ next context
```

## Persistent research memory

Every material observation, hypothesis, experiment, score, failure, and
handoff was appended to a filesystem journal. Codex could search that history
programmatically and keep working files across context rollovers. This follows
the core insight of [PRO-LONG](https://github.com/alexisfox7/PRO-LONG): preserve
the full trajectory outside the context window and let a coding agent retrieve
what it needs with code.

The journal was not a polished knowledge base. Its value came from fidelity:
failed attempts stayed available, successful programs remained executable, and
a later context could inspect the evidence behind an earlier conclusion.

## On-the-fly world models

Different problems produced different machinery. Codex could write a parser,
optimizer, simulator, exact checker, continuation method, or search program
when that representation was useful. François Chollet describes this broader
pattern as [“LLM-guided on-the-fly synthesis of a symbolic world model”](https://x.com/fchollet/status/2088243704603824311):
the model makes its theory executable, tests it, and revises the program when
the theory fails.

## Control boundary

The research loop could act autonomously inside its local workspace. External
submissions required human approval. Verification used pinned evaluator hashes,
and public claims were reduced to solution IDs, scores, receipt hashes, and
explicit integrity labels.

## What is not published here

This document describes the system at a high level. The production controller,
prompts, session transcripts, raw journal, research corpus, solver source,
checkpoints, and executable world models are not included in the current
release tree. Earlier source-bearing revisions remain available under their
original MIT grant; see [NOTICE.md](../NOTICE.md) for the licensing boundary.
