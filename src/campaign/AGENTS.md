# EinsteinArena long-horizon protocol

These instructions apply to this campaign tree.

- Begin every resumed session by reading `HANDOFF.md`, then run `./arena status`
  and validate the journal before doing research.
- Before opening a new benchmark lane, query the exhaustive public corpus at
  `research_corpus/latest.json` / its referenced FTS5 SQLite database. Read all
  captured constructions, threads, and replies for that problem; cite corpus
  scope in the lane handoff so prior work and negative results are not repeated.
- Before making literature-dependent claims, load the installed Paperclip skill
  with `paperclip skill`, search the appropriate source explicitly, read the
  supporting full-text lines, and use Paperclip's line-pinned citation format.
  Never put its API key in prompts, logs, artifacts, or repositories.
- Treat `state/` as controller-owned. Use `./arena snapshot|status|verify|submit|check`
  rather than editing state directly.
- Keep each problem family in its assigned `geometry/`, `analytic/`, or
  `discrete/` directory. Every bounded run needs a timestamped directory,
  checkpoint, reproduction command, verifier hash, and concise handoff.
- Compile repeated reasoning into programs. Record negative results with search
  scope and hashes so later sessions do not repeat them.
- Never place credentials in candidates, logs, prompts, or run directories.
- Never execute downloaded verifier code on the host. Use `./arena verify`,
  which runs it in the offline read-only Docker sandbox.
- A candidate may be submitted only after it passes the live verifier, clears
  the current first-place gate, conforms to the stated mathematical domain,
  and is independently shape/finiteness checked.
- Do not submit verifier exploits as mathematical constructions. Disclose any
  verifier/domain mismatch transparently and keep it distinct in the handoff.
- Do not poll pending submissions. Check once after the documented evaluation
  window, then return to research.
- External discussion posts must contain reproducible numbers or a genuinely
  useful structural result; do not spam progress logs.
- After an evaluated submission, material frontier gain, or context handoff,
  refresh the secret-scrubbed public mirror at `/Users/jacweath/CodexProLong`
  with `python tools/snapshot_campaign.py --source ../EinsteinArena/campaign`,
  run its credential scanner and tests, review the exact git diff, and push a
  deliberate checkpoint. Never mirror private prompts, hidden chain-of-thought,
  auth/session state, provider credentials, or third-party source trees.
