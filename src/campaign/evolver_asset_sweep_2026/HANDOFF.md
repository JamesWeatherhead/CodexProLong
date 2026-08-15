# 2026 evolver asset sweep — frozen handoff

## Outcome

No public asset in this bounded GET-only sweep clears a live EinsteinArena gate.
The searched systems were SMCEvolve, Escher-Loop, MLEvolve, HASE, LoongFlow,
GigaEvo (primary and maintained fork), SkyDiscover/AdaEvolve/EvoX, and the three
public Finch collections.  The full pinned inventory and numerical no-go table
are in `receipt.json`.

Only Escher-Loop exposed new, directly runnable best programs.  Literal replay
under the unchanged Arena verifiers gives:

| slug | exact score | strict gate | shortfall |
|---|---:|---:|---:|
| `circle-packing` | `2.6352223117773934` | `>2.635983095360844` | `7.607835834506638e-4` |
| `heilbronn-triangles` | `0.03372654309850653` | `>0.036529890880030156` | `2.8033477815236282e-3` |

The Escher circle payload and exact-threshold contact signature are new, but its
coarser ranked contact graph already appears in the prior geometry recombination
log (event 41).  It is therefore neither gate-capable nor a genuinely new coarse
topology.

## New evaluator evidence

The supplemental `Finch-Collection-Gemini-3-Flash` dataset contains a rectangle
candidate whose stored metric claims `5.104873472880783`.  The reviewed program
was run locally, and the literal Arena verifier returns `-Infinity`: its payload
contains a negative radius (observed minimum `-0.040000000150001824`).  The
program, payload, dataset-record, dataset-commit, and verifier hashes are pinned
in `receipt.json`.  This is a concrete cross-evaluator failure, not a construction
lead.

All finite Finch candidates are below the live gates.  SMCEvolve and
SkyDiscover expose starters/evaluators but no tracked final artifacts; MLEvolve
reports results but publishes no math-output bytes; HASE supplies evaluator
repair material but no construction; LoongFlow's deterministic files are
inferior by their own reported scores; and current GigaEvo heads add no frozen
output beyond assets already audited.  None of the searched trees or datasets
contains a target asset for flat polynomials, Thomson, difference bases, or
edges versus triangles.

## Exact replay

From the repository root:

```bash
.venv/bin/python campaign/evolver_asset_sweep_2026/replay_exact.py
```

The script downloads only the two reviewed MIT-licensed Escher programs from an
immutable commit, rejects unexpected redirects or hash changes, keeps all
source/payload bytes in memory, verifies the frozen local verifier hashes, and
checks exact payload hashes and scores.  It does not persist third-party bytes.

## Primary source trail

- SMCEvolve: <https://github.com/kongwanbianjinyu/SMCEvolve/tree/5371c804e1fbdb153f2de1332fdf4bdb59317ff7>
- Escher-Loop: <https://github.com/scaling-group/escher-loop/tree/acc8241e10058bf8ea1b1ea5299efc4eaf054e1f>
- MLEvolve: <https://github.com/InternScience/MLEvolve/tree/7d8403c899c40f01941c0429f1c4ef51e82ae41c>
- HASE paper: <https://arxiv.org/abs/2607.03935>
- LoongFlow: <https://github.com/baidu-baige/LoongFlow/tree/945c78bc1554f8281aac40320b3599bd68d528d7>
- GigaEvo: <https://github.com/AIRI-Institute/gigaevo-core/tree/9b8687ebaf1708962370ea82b4cf2480d74874e5>
- SkyDiscover: <https://github.com/skydiscover-ai/skydiscover/tree/8a840394e19ee4bfb3fb0a62762b902561a7efeb>
- Finch collections: <https://huggingface.co/minnesotanlp>

Paperclip's indexed full-text search returned no records for the two newest
named papers (`2605.15308`, `2604.23472`) or MLEvolve at sweep time, so the
corresponding primary arXiv and repository sources were audited directly.

No Arena/GitHub state was mutated, and no submission, post, comment, vote,
contact, or push was made.
