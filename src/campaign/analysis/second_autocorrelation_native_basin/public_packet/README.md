# C2 native-basin portable replay packet

This is the exact public allowlist for the C2 native-grid lane. It is
self-contained for receipt replay, source/license scanning, and deterministic
small-fixture numeric tests. It neither downloads nor dynamically executes a
verifier, and it does not inspect state outside this directory.

## Quick replay

From a repository using the canonical layout:

```sh
PYTHONDONTWRITEBYTECODE=1 python \
  campaign/analysis/second_autocorrelation_native_basin/public_packet/replay_public.py
PYTHONDONTWRITEBYTECODE=1 python \
  campaign/analysis/second_autocorrelation_native_basin/public_packet/test_packet.py
PYTHONDONTWRITEBYTECODE=1 python \
  campaign/analysis/second_autocorrelation_native_basin/public_packet/scan_packet.py
```

From a repository using the mirrored `src` layout, insert `src/` before
`campaign/` in the same three commands:

```sh
PYTHONDONTWRITEBYTECODE=1 python \
  src/campaign/analysis/second_autocorrelation_native_basin/public_packet/replay_public.py
PYTHONDONTWRITEBYTECODE=1 python \
  src/campaign/analysis/second_autocorrelation_native_basin/public_packet/test_packet.py
PYTHONDONTWRITEBYTECODE=1 python \
  src/campaign/analysis/second_autocorrelation_native_basin/public_packet/scan_packet.py
```

All programs resolve data relative to their own file, not the current working
directory. `replay_public.py` and `scan_packet.py` use only the Python standard
library. `test_packet.py` additionally needs NumPy and SciPy. Exact tested
versions and platform boundaries are in `DEPENDENCIES.md`.

## What replay means

The public replay verifies every allowlisted byte against `manifest.json`,
checks quantitative receipt identities, checks provenance boundaries, and
runs an independent objective/gradient/Clarke-hull test suite on generated
fixtures. It intentionally does not claim to recompute the omitted
1,999,999-cell checkpoint. The checkpoint hash remains a falsifiable receipt
for an authorized holder of that separately governed array.

`copy_allowlist_test.py` copies only the allowlist into fresh canonical and
mirrored directory trees, then reruns replay, tests, and scans in both. The
temporary trees are created under the lane and removed automatically.

## Scope

- Native dimension recorded by the pilot: 1,999,999 cells.
- Public packet: no arrays, no frozen verifier, no raw logs, no upstream bytes.
- H100 material: a pinned plan, compact phase configs, and a non-optimizing
  hardware/dependency preflight.
- External writes: none.

The full search implementation and raw runs are not on the public allowlist
because their acceptance path depends on a separately controlled verifier and
their raw manifests contain private machine paths. The public H100 plan is
therefore a reproducible execution specification, not a claim that the
excluded private acceptance step can be reproduced from this packet alone.
