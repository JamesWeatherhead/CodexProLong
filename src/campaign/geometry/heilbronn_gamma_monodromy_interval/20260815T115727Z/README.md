# Heilbronn n=11 gamma-monodromy and interval packet

This is a portable, offline, bounded no-candidate packet. It models the 17
active signed-area equations after eliminating six boundary equalities, probes
complex monodromy sheets, filters target roots in the real intended domain, and
replays an exact-rational Krawczyk exclusion for the known incumbent root.

The run is not a complete root enumeration or a global upper bound. It found 12
distinct generic complex roots and ten successful roots in two target systems;
all ten target roots were nonreal. No legal gate clearer was found.

## Public replay

The public replay uses only Python 3.9 or newer and the standard library. From a
repository root, use the path matching the checkout layout:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/public_replay.py
```

or:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  src/campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/public_replay.py
```

The copied-allowlist test relocates the exact manifest allowlist into both
layouts inside a temporary subtree, runs the isolated replay in each copy, and
removes the temporary trees:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/publication_selftest.py
```

`PUBLICATION_MANIFEST.json` is authoritative. Publish exactly its `files` list
plus the manifest itself. The manifest intentionally omits its own hash, so a
detached SHA-256 must accompany a frozen release.

## What the replay checks

The replay verifies every allowlisted byte when the publication manifest is
present, then independently checks:

- the compact fixture and all 619 unique exchange/status records;
- the 334 reflection orbits and target status aggregates;
- all 12 generic-root residuals and their pairwise distinctness;
- every stored incumbent and target endpoint residual;
- reality, 33 barycentric inequalities, pair separation, and all 165 absolute
  determinants for every endpoint;
- ten distinct successful target roots and zero legal gate clearers;
- the certificate payload hash and every exact `Fraction` Krawczyk inequality.

No private seed file, pseudo-arclength run, corpus database, verifier, network
connection, or third-party Python package is needed.

## Optional scientific generation

The generation and audit scripts use NumPy; certificate generation additionally
uses mpmath. These packages are not vendored. Install `requirements.txt` in an
environment of your choice, then check the frozen target audit without writing:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/audit.py --check
```

The bounded tracker has a wall-clock cutoff and floating linear algebra, so it
is method code rather than a byte-for-byte artifact reproducer. The exact
certificate can be replayed with:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B \
  campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/exact_krawczyk.py \
  --replay campaign/geometry/heilbronn_gamma_monodromy_interval/20260815T115727Z/incumbent_krawczyk.json
```

See `PROVENANCE.md` for the source-hash, license, redistribution, and dependency
boundary. No Arena, verifier, GitHub, or other external write was made.
