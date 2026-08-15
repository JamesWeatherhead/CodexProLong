#!/usr/bin/env python3
"""Archive every public rendered page and deployment asset linked from it."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

from crawl import Archiver, atomic_json


ROOT = Path(__file__).resolve().parent


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: set[str] = set()

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.values.add(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--request-delay", type=float, default=0.03)
    args = parser.parse_args()
    latest_path = args.root / "latest.json"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    manifest_path = args.root / latest["manifest"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    snapshot_dir = manifest_path.parent
    output = snapshot_dir / "web_pages.json"
    if output.exists():
        raise RuntimeError(f"page supplement already exists: {output}")

    archive = Archiver(args.root, manifest["base_url"], args.request_delay)
    seeds = {"/", "/search"}
    for slug in manifest["problems"]:
        seeds.add(f"/problems/{urllib.parse.quote(slug)}")
    for thread_id, item in manifest["threads"].items():
        slug = item.get("problem_slug")
        if slug:
            seeds.add(
                f"/problems/{urllib.parse.quote(slug)}/threads/{int(thread_id)}"
            )

    pages: dict[str, dict] = {}
    assets: set[str] = {"/logo.png", "/favicon.ico"}
    for route in sorted(seeds):
        status, body, ref = archive.fetch(
            route, allow_statuses={200, 404}, expect_json=False
        )
        pages[route] = ref
        if status != 200:
            continue
        parser_html = Links()
        parser_html.feed(body.decode("utf-8", errors="replace"))
        for raw in parser_html.values:
            parsed = urllib.parse.urlsplit(raw)
            if parsed.scheme and parsed.netloc != urllib.parse.urlsplit(manifest["base_url"]).netloc:
                continue
            candidate = parsed.path
            if parsed.query:
                candidate += "?" + parsed.query
            if candidate.startswith("/_next/static/") or candidate in {
                "/logo.png",
                "/favicon.ico",
            }:
                assets.add(candidate)

    asset_refs: dict[str, dict] = {}
    for route in sorted(assets):
        _, _, ref = archive.fetch(route, allow_statuses={200, 404}, expect_json=False)
        asset_refs[route] = ref

    supplement = {
        "schema_version": 1,
        "snapshot": manifest["snapshot"],
        "base_url": manifest["base_url"],
        "page_count": len(pages),
        "asset_count": len(asset_refs),
        "pages": pages,
        "assets": asset_refs,
        "responses": archive.entries,
    }
    atomic_json(output, supplement)
    latest["web_pages"] = str(output.relative_to(args.root))
    latest["web_pages_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    atomic_json(latest_path, latest)
    print(json.dumps({
        "pages": len(pages),
        "assets": len(asset_refs),
        "responses": len(archive.entries),
        "output": str(output),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
