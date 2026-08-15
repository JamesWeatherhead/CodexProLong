# Architecture

The campaign separates powers that are easy to blur in an agent demo:

1. The controller owns the immutable event journal, live snapshot, budgets,
   verifier hash, and terminal decision.
2. Codex owns a persistent scratch workspace and may write arbitrary local
   parsers, simulators, optimizers, and search programs.
3. A narrow action CLI validates every external write.
4. Candidate evaluation occurs in an offline, read-only Docker sandbox with
   dropped capabilities and only the candidate, verifier, and runner mounted.
5. Every material transition creates an atomic handoff that is sufficient for
   a fresh context to resume.
6. The public mirror exports owned source and evidence, then scans the entire
   staged tree for credential formats before a push.

This implements the useful core of filesystem memory without coupling the
agent to ARC grids, a particular action enum, or one optimizer family.

## Executable world models

François Chollet describes the broader pattern as
[“LLM-guided on-the-fly synthesis of a symbolic world model”](https://x.com/fchollet/status/2088243704603824311):
the model makes its theory executable, tests it against evidence, and rewrites
the program when the theory fails. Here, Codex can build a different parser,
optimizer, simulator, or exact checker for each mathematical benchmark.

Exa Search supplies web research and Paperclip supplies scientific literature.
They are tools called by Codex, not subagents. Verified outcomes and failed
experiments return to the append-only journal, so a later context can inspect
the evidence behind the current world model instead of reconstructing it from
scratch.

## Batch-action rule

Actions may be proposed in a batch for efficiency, but the controller records
each result atomically and cancels the remainder whenever score, progress,
state, or terminal status changes. That prevents stale plans from running after
the world has changed.

## Context rollover rule

Context is disposable. Before rollover, the agent writes a handoff containing:

- the current best verified artifact and hash;
- live leader, direction, and strict gate;
- what was tried, with quantified bounds;
- active processes/checkpoints;
- the next highest-information experiment.

The next context reads the journal and handoff instead of relying on chat
memory.
