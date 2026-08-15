#!/usr/bin/env python3
"""Segmented clean-room integer-breakpoint scanner for a finite PNT payload."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
DEFAULT_PAYLOAD = HERE / "input_payload.json"
EXPECTED_PAYLOAD_SHA256 = (
    "d43c5531d562d06981a55829deb1c579a87a7c02405d69688dcc79e7f45f22c1"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path, scale_to_f1_one: bool) -> tuple[np.ndarray, np.ndarray, float, float]:
    if path == DEFAULT_PAYLOAD and sha256_file(path) != EXPECTED_PAYLOAD_SHA256:
        raise RuntimeError("frozen #2506 payload hash mismatch")
    payload = json.loads(path.read_text())
    raw = payload["partial_function"]
    if len(raw) > 2_000:
        raise ValueError("too many submitted keys")
    parsed = {int(label): float(np.clip(float(value), -10.0, 10.0)) for label, value in raw.items()}
    total = sum(value / key for key, value in parsed.items())
    parsed[1] = parsed.get(1, 0.0) - total
    scale = 1.0
    if scale_to_f1_one:
        scale = 1.0 / parsed[1]
        parsed = {key: value * scale for key, value in parsed.items()}
    keys = np.array(sorted(parsed), dtype=np.int64)
    values = np.array([parsed[int(key)] for key in keys], dtype=np.float64)
    normalization_residual = float(np.sum(values / keys.astype(np.float64)))
    return keys, values, normalization_residual, scale


def scan(keys: np.ndarray, values: np.ndarray, upper: int, chunk: int) -> dict[str, float | int]:
    f1 = float(values[np.flatnonzero(keys == 1)[0]])
    nontrivial = [(int(k), float(v)) for k, v in zip(keys, values, strict=True) if k != 1]
    cumulative = 0.0
    maximum = -np.inf
    argmax = -1
    first_over_one = -1
    for start in range(1, upper + 1, chunk):
        stop = min(upper + 1, start + chunk)
        increments = np.full(stop - start, f1, dtype=np.float64)
        for key, value in nontrivial:
            first = ((start + key - 1) // key) * key
            if first < stop:
                increments[first - start :: key] += value
        states = np.cumsum(increments, dtype=np.float64) + cumulative
        local_index = int(np.argmax(states))
        local_maximum = float(states[local_index])
        if local_maximum > maximum:
            maximum = local_maximum
            argmax = start + local_index
        if first_over_one < 0:
            violations = np.flatnonzero(states > 1.0)
            if violations.size:
                first_over_one = start + int(violations[0])
        cumulative = float(states[-1])
        print(
            json.dumps(
                {
                    "through": stop - 1,
                    "maximum": maximum,
                    "argmax": argmax,
                    "first_over_one": first_over_one,
                    "terminal": cumulative,
                },
                sort_keys=True,
            ),
            flush=True,
        )
    return {
        "upper": upper,
        "maximum": maximum,
        "argmax": argmax,
        "first_over_one": first_over_one,
        "terminal": cumulative,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    parser.add_argument("--upper", type=int, default=100_000_000)
    parser.add_argument("--chunk", type=int, default=2_000_000)
    parser.add_argument("--scale-to-f1-one", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    keys, values, residual, scale = load(args.payload, args.scale_to_f1_one)
    result = scan(keys, values, args.upper, args.chunk)
    result.update(
        {
            "payload": args.payload.name,
            "payload_sha256": sha256_file(args.payload),
            "normalization_residual_float64": residual,
            "coordinate_scale": scale,
        }
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
