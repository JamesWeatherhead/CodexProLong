#!/usr/bin/env python3
"""Self-contained clean-room mirror of the frozen circle-packing verifier.

The MIT-licensed reference bytes are read only for SHA-256 confirmation.  They
are never imported, compiled, evaluated, or executed.  ``evaluate`` is an
independent direct transcription of the numerical acceptance formula.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
REFERENCE_VERIFIER = HERE / "reference" / "frozen_verifier.py.b64"
VERIFIER_SHA256 = "2dee3fad3cfcf2729000abda43b1812eab13fd8808e16cdb278fbae1266b37ab"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_reference_hash() -> str:
    # Decode bytes solely for hashing.  No decoded content is written,
    # imported, compiled, evaluated, or executed.
    reference_bytes = base64.b64decode(REFERENCE_VERIFIER.read_text().strip(), validate=True)
    actual = hashlib.sha256(reference_bytes).hexdigest()
    if actual != VERIFIER_SHA256:
        raise RuntimeError(f"reference verifier hash changed: {actual}")
    return actual


def evaluate(data: dict[str, Any]) -> float:
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
