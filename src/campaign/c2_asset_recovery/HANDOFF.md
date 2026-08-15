# C2 asset-recovery handoff

Frozen result: a public SimpleTES construction absent from the prior local
corpus was recovered and exactly replayed, but it does not clear the gate.

- SimpleTES: `n=262144`, score `0.9626937749955136`, value SHA-256
  `8a526d01d12973ead4e62797bf419e358718d92ae9264c6fc1778e957cb13f20`.
- Hyra: `n=524288`, score `0.9629011010961758`, value SHA-256
  `538e0194c38c81afc48151bdca770486429fb3fa857869771a79e35ceac3a382`;
  exact match for Arena `#2361` and the existing local reference.
- Live strict gate: `0.9635981105820289`.
- Frozen verifier SHA-256:
  `dc5ccffaa20ba6c112cab36ffe602c657372d192d8b486abd66b14bcad1ca768`.
- Frozen Arena corpus SHA-256:
  `9d447872f2f38f0bcec004f683ea098b938f7e68e8bd16707f4a2effe5e1c5bb`.

The SimpleTES asset is structurally useful as an independent 3,141-run
fine-comb basin, but its direct gap is `9.043355865153702e-4`; no direct
candidate is submission-capable. Do not repeat Jaech--Joseph upsampling or
Hyra recovery. If resumed, the only justified use is a clearly new
cross-basin/topology experiment seeded by `payloads/simpletes.npy`, with every
candidate accepted only by the same frozen verifier.

Publish-safe files are `.gitignore`, `asset_replay.py`, `README.md`,
`HANDOFF.md`, and `receipt.json`. Keep `cache/`, `payloads/`, and
`__pycache__/` local unless upstream licenses and redistribution notices are
handled explicitly.

No external write occurred.
