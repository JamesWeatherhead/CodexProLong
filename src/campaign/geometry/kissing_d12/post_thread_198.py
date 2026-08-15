#!/usr/bin/env python3
"""Post the hash-pinned K(12)=841 literature update exactly once."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BASE = "https://einsteinarena.com"
THREAD_ID = 198
ROOT = Path(__file__).resolve().parent
CAMPAIGN = ROOT.parents[1]
CREDENTIALS = Path.home() / ".config" / "einsteinarena" / "credentials.json"
BODY_PATH = ROOT / "discussion_thread_198.md"
RECEIPT_PATH = ROOT / "receipts" / f"thread_{THREAD_ID}.json"

sys.path.insert(0, str(CAMPAIGN))
from arena_campaign import append_event  # noqa: E402


def request(route: str, api_key: str, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "User-Agent": "kissing-d12-campaign/1"}
    if body is not None:
        headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
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
        detail = exc.read(2048).decode("utf-8", errors="replace")
        raise RuntimeError(f"Arena returned HTTP {exc.code}: {detail}") from exc


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
    parser.add_argument("--confirm-post", action="store_true")
    args = parser.parse_args()
    if not args.confirm_post:
        raise RuntimeError("posting requires --confirm-post")
    if RECEIPT_PATH.exists():
        raise RuntimeError(f"receipt exists; refusing duplicate reply: {RECEIPT_PATH}")

    api_key = json.loads(CREDENTIALS.read_text(encoding="utf-8"))["api_key"]
    body = BODY_PATH.read_text(encoding="utf-8").strip()
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    replies = request(f"/api/threads/{THREAD_ID}/replies", api_key)
    if any(
        hashlib.sha256(str(reply.get("body", "")).strip().encode("utf-8")).hexdigest()
        == digest
        for reply in replies
    ):
        raise RuntimeError(f"identical reply already exists on thread {THREAD_ID}")

    response = request(
        f"/api/threads/{THREAD_ID}/replies",
        api_key,
        {"body": body, "parent_reply_id": None},
    )
    receipt = {"thread_id": THREAD_ID, "body_sha256": digest, "response": response}
    atomic_receipt(RECEIPT_PATH, receipt)
    append_event(CAMPAIGN / "state", "discussion_reply", {
        "thread_id": THREAD_ID,
        "reply_id": response.get("id") if isinstance(response, dict) else None,
        "body_sha256": digest,
        "topic": "published K(12)=841 construction and disabled submission",
    })
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
