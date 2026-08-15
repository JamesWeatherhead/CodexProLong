#!/usr/bin/env python3
"""Validate local Markdown links without crawling the public web."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
SKIP = ("http://", "https://", "mailto:", "#")


def main() -> int:
    errors: list[str] = []
    for markdown in sorted(ROOT.rglob("*.md")):
        if ".git" in markdown.parts:
            continue
        text = markdown.read_text(encoding="utf-8")
        for raw in LINK.findall(text):
            target_text = raw.split(maxsplit=1)[0].strip("<>")
            if target_text.startswith(SKIP):
                continue
            target_text = unquote(target_text.split("#", 1)[0])
            target = (markdown.parent / target_text).resolve()
            if not target.exists():
                errors.append(f"{markdown.relative_to(ROOT)} -> {raw}")
    if errors:
        print("local link check FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("local link check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
