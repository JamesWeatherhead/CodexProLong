#!/usr/bin/env python3
"""Reproduce the fixed-seed integer grid and audit the live leader exactly."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parent
LIVE = ROOT / "checkpoints" / "live.json"
MASK = ROOT / "checkpoints" / "sampled_grid.npy"
AUDIT = ROOT / "checkpoints" / "audit.json"
LIMIT = 1.0001
NUM_SAMPLES = 10_000_000
TARGET_BATCH_BYTES = 40 * 1024 * 1024


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, indent=2, sort_keys=True).encode())
            handle.write(b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_npy(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        with temporary.open("wb") as handle:
            np.save(handle, value, allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_leader() -> tuple[dict[str, Any], np.ndarray, np.ndarray]:
    live = json.loads(LIVE.read_text(encoding="utf-8"))
    raw = live["leader"]["data"]["partial_function"]
    keys = np.fromiter((int(key) for key in raw), dtype=np.int64)
    values = np.fromiter((float(value) for value in raw.values()), dtype=np.float64)
    return live, keys, values


def official_mask(keys: np.ndarray) -> np.ndarray:
    """Return exactly the set of integer floors visited by the verifier."""
    upper = 10 * int(keys.max())
    internal_key_count = len(keys) + (0 if 1 in keys else 1)
    batch_size = max(1, TARGET_BATCH_BYTES // (internal_key_count * 8))
    rng = np.random.RandomState(42)
    mask = np.zeros(upper + 1, dtype=np.bool_)
    remaining = NUM_SAMPLES
    while remaining:
        count = min(batch_size, remaining)
        sampled = np.floor(rng.uniform(1, float(upper), size=count)).astype(np.int64)
        mask[sampled] = True
        remaining -= count
    return mask


def recurrence_curve(
    keys: np.ndarray, values: np.ndarray, *, upper: int | None = None
) -> np.ndarray:
    """Compute g(n)=sum v_k(floor(n/k)-n/k) on every integer n."""
    if upper is None:
        upper = 10 * int(keys.max())
    f_one = -float(np.dot(values, 1.0 / keys))
    delta = np.empty(upper + 1, dtype=np.float64)
    delta[0] = 0.0
    delta[1:] = f_one
    for key, value in zip(keys, values, strict=True):
        delta[int(key) :: int(key)] += value
    return np.cumsum(delta)


def direct_rows(
    rows: Iterable[int], keys: np.ndarray, values: np.ndarray
) -> np.ndarray:
    rows_array = np.asarray(list(rows), dtype=np.int64)
    coefficients = -(
        (rows_array[:, None] % keys[None, :]) / keys[None, :]
    )
    return coefficients @ values


def mobius_sieve(limit: int) -> np.ndarray:
    """Integer Moebius values on 0..limit, without an optional dependency."""
    mu = np.ones(limit + 1, dtype=np.int8)
    prime = np.ones(limit + 1, dtype=np.bool_)
    prime[:2] = False
    for p in range(2, limit + 1):
        if not prime[p]:
            continue
        mu[p::p] *= -1
        square = p * p
        if square <= limit:
            mu[square::square] = 0
        if p <= int(math.isqrt(limit)):
            prime[p * p :: p] = False
        # Marking from 2p is redundant but keeps the routine self-contained.
        prime[2 * p :: p] = False
    mu[0] = 0
    return mu


def main() -> None:
    live, keys, values = load_leader()
    mask = official_mask(keys)
    atomic_npy(MASK, mask)
    curve = recurrence_curve(keys, values)
    sampled_rows = np.flatnonzero(mask)
    top_count = min(100_000, len(sampled_rows))
    top_rows = sampled_rows[
        np.argpartition(curve[sampled_rows], -top_count)[-top_count:]
    ]
    direct = direct_rows(top_rows, keys, values)
    order = np.argsort(direct)[::-1]
    direct_top = [
        {"n": int(top_rows[index]), "value": float(direct[index])}
        for index in order[:100]
    ]
    mu = mobius_sieve(int(keys.max()))
    support = set(map(int, keys))
    objective_contributions = -values * np.log(keys) / keys
    tiny_order = np.argsort(np.abs(values))[:100]
    audit = {
        "audited_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "verifier_sha256": live["verifier_sha256"],
        "leader_id": live["leader"]["id"],
        "leader_score_stored": live["leader"]["score"],
        "leader_score_recomputed": -float(np.dot(values, np.log(keys) / keys)),
        "raw_key_count": len(keys),
        "internal_key_count": len(keys) + (0 if 1 in support else 1),
        "minimum_key": int(keys.min()),
        "maximum_key": int(keys.max()),
        "upper_bound": 10 * int(keys.max()),
        "sampled_integer_count": int(mask.sum()),
        "unsampled_integer_count": int((~mask).sum()),
        "mask_sha256": hashlib.sha256(MASK.read_bytes()).hexdigest(),
        "f_one": -float(np.dot(values, 1.0 / keys)),
        "recurrence_sampled_max": float(curve[mask].max()),
        "direct_sampled_max": direct_top[0],
        "direct_slack": LIMIT - direct_top[0]["value"],
        "sampled_counts_above": {
            str(level): int(np.count_nonzero(mask & (curve >= level)))
            for level in (1.0, 1.00005, 1.00009, 1.000099)
        },
        "squarefree_support_count": int(np.count_nonzero(mu[keys] != 0)),
        "mobius_sign_match_count": int(
            np.count_nonzero(np.sign(values) == mu[keys])
        ),
        "absolute_value_counts": {
            "below_0.1": int(np.count_nonzero(np.abs(values) < 0.1)),
            "below_0.5": int(np.count_nonzero(np.abs(values) < 0.5)),
        },
        "top_direct_rows": direct_top,
        "smallest_absolute_support_values": [
            {
                "key": int(keys[index]),
                "value": float(values[index]),
                "mobius": int(mu[keys[index]]),
                "objective_contribution": float(objective_contributions[index]),
            }
            for index in tiny_order
        ],
    }
    atomic_json(AUDIT, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
