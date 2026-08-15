#!/usr/bin/env python3
"""Post the two evaluated geometry results once, with local receipts."""

from __future__ import annotations

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
POSTS = (
    (240, ROOT / "discussion_d12_842.md", ROOT / "receipts" / "thread_240.json"),
    (241, ROOT / "discussion_d11_605.md", ROOT / "receipts" / "thread_241.json"),
)


def request(route: str, api_key: str, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"User-Agent": "geometry-campaign/1"}
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
        detail = exc.read().decode("utf-8", errors="replace")
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
    credentials = json.loads(CREDENTIALS.read_text(encoding="utf-8"))
    api_key = credentials["api_key"]
    results = []
    for thread_id, body_path, receipt_path in POSTS:
        if receipt_path.exists():
            raise RuntimeError(f"receipt exists; refusing duplicate reply: {receipt_path}")
        body = body_path.read_text(encoding="utf-8").strip()
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        replies = request(f"/api/threads/{thread_id}/replies", api_key)
        if any(
            hashlib.sha256(str(reply.get("body", "")).strip().encode("utf-8")).hexdigest()
            == digest
            for reply in replies
        ):
            raise RuntimeError(f"identical reply already exists on thread {thread_id}")
        response = request(
            f"/api/threads/{thread_id}/replies",
            api_key,
            {"body": body, "parent_reply_id": None},
        )
        atomic_receipt(
            receipt_path,
            {"thread_id": thread_id, "body_sha256": digest, "response": response},
        )
        results.append({"thread_id": thread_id, "response": response})
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

