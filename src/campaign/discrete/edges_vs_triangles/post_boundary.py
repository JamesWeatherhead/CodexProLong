#!/usr/bin/env python3
"""Post the row-budget verifier-boundary disclosure once."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

BASE = "https://einsteinarena.com"
ROOT = Path(__file__).resolve().parent
CREDENTIALS = Path.home() / ".config" / "einsteinarena" / "credentials.json"
THREAD_ID = 155
BODY_PATH = ROOT / "discussion-boundary.md"
RECEIPT_PATH = ROOT / "receipts" / f"thread_{THREAD_ID}_row_boundary.json"


def request(route: str, api_key: str, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"User-Agent": "einsteinarena-row-boundary/1"}
    if body is not None:
        headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )
    req = urllib.request.Request(
        BASE + route,
        data=body,
        headers=headers,
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"arena returned HTTP {exc.code}: {detail}") from exc


def atomic_receipt(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--correction", action="store_true")
    args = parser.parse_args()
    body_path = (
        ROOT / "discussion-boundary-correction.md" if args.correction else BODY_PATH
    )
    receipt_path = (
        ROOT / "receipts" / f"thread_{THREAD_ID}_row_boundary_correction.json"
        if args.correction
        else RECEIPT_PATH
    )
    if receipt_path.exists():
        raise RuntimeError(f"receipt exists; refusing duplicate reply: {receipt_path}")
    api_key = json.loads(CREDENTIALS.read_text(encoding="utf-8"))["api_key"]
    body = body_path.read_text(encoding="utf-8").strip()
    digest = hashlib.sha256(body.encode()).hexdigest()
    replies = request(f"/api/threads/{THREAD_ID}/replies", api_key)
    if any(
        hashlib.sha256(str(reply.get("body", "")).strip().encode()).hexdigest()
        == digest
        for reply in replies
    ):
        raise RuntimeError("identical disclosure already exists")
    response = request(
        f"/api/threads/{THREAD_ID}/replies",
        api_key,
        {"body": body, "parent_reply_id": None},
    )
    atomic_receipt(
        receipt_path,
        {"body_sha256": digest, "response": response, "thread_id": THREAD_ID}
    )
    print(json.dumps({"response": response, "thread_id": THREAD_ID}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
