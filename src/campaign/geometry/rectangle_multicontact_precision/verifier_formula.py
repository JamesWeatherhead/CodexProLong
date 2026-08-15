#!/usr/bin/env python3
"""Clean-room mirror of the hash-pinned circles-rectangle score formula.

The frozen verifier file is read only to confirm its SHA-256.  It is never
imported or executed; ``evaluate`` below directly mirrors its float64 tests.
"""

from __future__ import annotations

import hashlib
import itertools
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parents[1]
VERIFIER = (
    CAMPAIGN
    / "state/problems/circles-rectangle"
    / "c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9.py"
)
VERIFIER_SHA256 = "c36cb4b5239e992b953f3839506562e15d21097830adc8881184c5a597866df9"
MAX_COORD = 1e6
ULP_SAFETY_FACTOR = 1e6


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
    if circles.shape != (21, 3):
        return -float("inf")
    if not np.isfinite(circles).all():
        return -float("inf")
    radii = circles[:, 2]
    if not (radii > 0).all():
        return -float("inf")
    coordinates = circles[:, :2]
    if np.abs(coordinates).max() > MAX_COORD:
        return -float("inf")
    ulp = np.maximum(
        np.abs(np.spacing(coordinates[:, 0])),
        np.abs(np.spacing(coordinates[:, 1])),
    )
    if (radii < ULP_SAFETY_FACTOR * ulp).any():
        return -float("inf")
    min_x = np.min(circles[:, 0] - radii)
    max_x = np.max(circles[:, 0] + radii)
    min_y = np.min(circles[:, 1] - radii)
    max_y = np.max(circles[:, 1] + radii)
    if (max_x - min_x) + (max_y - min_y) > 2 + 1e-9:
        return -float("inf")
    for first, second in itertools.combinations(circles, 2):
        distance = np.sqrt(
            (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2
        )
        if distance < first[2] + second[2] - 1e-9:
            return -float("inf")
    return float(np.sum(radii))
