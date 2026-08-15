# EinsteinArena campaign controller

This is a filesystem-first controller for long-running EinsteinArena research.
The current Codex session supplies reasoning and writes problem-specific tools;
the controller freezes live verifier code and leaderboards, journals actions,
runs candidates in an offline Docker sandbox, and guards external submissions.

## Commands

```sh
./arena build-sandbox
./arena snapshot
./arena status
./arena verify PROBLEM_SLUG candidate.json
./arena submit PROBLEM_SLUG candidate.json --confirm-domain-valid --confirm-submit
./arena record-rejection PROBLEM_SLUG candidate.json --http-status 409 \
  --reason 'Submissions are disabled for this problem' --confirm-record
./arena check SUBMISSION_ID
```

`submit` always refreshes the live problem and leaderboard, checks that the
verifier has not changed, re-runs the candidate, and refuses anything that does
not clear the current first-place gate. Large payloads automatically use the
documented blob-upload flow. The API key is read from
`EINSTEIN_ARENA_API_KEY` or
`~/.config/einsteinarena/credentials.json`; it is never written to campaign
state.

Every network submission attempt is journaled before transmission. HTTP
rejections and transport failures are then appended as explicit hash-chained
events. `record-rejection` exists only to backfill an already-observed failure;
it requires a matching gate-clearing `verify` event and performs no network
request.

Runtime state lives under `state/`:

```text
state/
  latest.json
  snapshots/*.json
  problems/SLUG/VERIFIER_SHA.{json,py}
  receipts/SLUG/*.json
  events.jsonl
```

`events.jsonl` is an append-only SHA-256 hash chain. Each verification receipt
binds the candidate bytes, verifier hash, score, and leaderboard snapshot.

The sandbox has no network, a read-only root filesystem, dropped Linux
capabilities, a PID limit, and only three read-only file mounts: the verifier,
candidate, and fixed runner. This keeps remote verifier code away from the host
and from credentials.
