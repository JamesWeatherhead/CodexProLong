#!/usr/bin/env python3
"""Clean-room mirror of the hash-pinned circle-packing score formula.

The frozen verifier file is read only to confirm its SHA-256.  It is never
imported or executed; ``evaluate`` below is a direct transcription of the
small numerical acceptance formula recorded in the campaign receipt.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
VERIFIER = (
    CAMPAIGN
    / "state/problems/circle-packing"
    / "2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab.py"
)
VERIFIER_SHA256 = "2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_verifier_hash() -> str:
    """Confirm the frozen verifier bytes without loading them as Python."""
    actual = sha256_file(VERIFIER)
    if actual != VERIFIER_SHA256:
        raise RuntimeError(f"verifier hash changed: {actual}")
    return actual


def evaluate(data: dict[str, Any]) -> float:
    """Apply the literal float64 acceptance and score formula."""
    circles = np.array(data["circles"], dtype=np.float64)
    assert circles.shape == (26, 3), f"Expected (26, 3), got {circles.shape}"
    centers = circles[:, :2]
    radii = circles[:, 2]
    if not np.isfinite(centers).all() or not np.isfinite(radii).all():
        return -float("inf")
    if not (radii >= 0).all():
        return -float("inf")
    contained = (radii[:, None] <= centers) & (centers <= 1 - radii[:, None])
    if not contained.all():
        return -float("inf")
    for first in range(26):
        for second in range(first + 1, 26):
            distance = np.sqrt(np.sum((centers[first] - centers[second]) ** 2))
            if radii[first] + radii[second] > distance + 1e-9:
                return -float("inf")
    return float(np.sum(radii))
