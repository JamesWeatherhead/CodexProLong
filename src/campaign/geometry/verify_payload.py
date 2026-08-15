#!/usr/bin/env python3
"""Replay a payload against the current public EinsteinArena verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path


BASE = "https://einsteinarena.com"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    with urllib.request.urlopen(f"{BASE}/api/problems/{args.slug}", timeout=60) as response:
        problem = json.load(response)
    with args.payload.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    namespace: dict[str, object] = {}
    exec(problem["verifier"], namespace)
    score = float(namespace["evaluate"](payload))  # type: ignore[operator]
    print(
        json.dumps(
            {
                "slug": args.slug,
                "payload": str(args.payload.resolve()),
                "score": score,
                "verifier_sha256": hashlib.sha256(problem["verifier"].encode()).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
