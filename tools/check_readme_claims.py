#!/usr/bin/env python3
"""Validate the README's generated facts, claim boundary, links, and images."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
FRONTIER = ROOT / "data/frontier.json"
SNAPSHOT_START = "<!-- BEGIN GENERATED:SNAPSHOT -->"
SNAPSHOT_END = "<!-- END GENERATED:SNAPSHOT -->"
FORBIDDEN = (
    "solved a 71-year-old problem",
    "solved a 71 year old problem",
    "fully autonomous",
    "five open problems solved",
    "solved five open problems",
    "seven mathematical discoveries",
    "10 problems solved",
    "all 19 solved",
    "openai's best model",
    "openai’s best model",
    "19 open math benchmarks",
    "assets/erdos-overlap-explainer.svg",
)


def frontier_partition(frontier: dict[str, object]) -> dict[str, int]:
    problems = list(frontier["problems"])
    blocked = sum(row["integrity"] == "domain-valid-blocked" for row in problems)
    live = sum(row["integrity"] == "active" for row in problems)
    leaders = sum(row["our_rank"] == 1 for row in problems)
    return {
        "blocked": blocked,
        "leaders": leaders,
        "live": live,
        "rankable": len(problems) - blocked,
        "total": len(problems),
    }


def expected_snapshot(frontier: dict[str, object]) -> str:
    counts = frontier_partition(frontier)
    valid = int(frontier["domain_valid_first_places"])
    return f"""{SNAPSHOT_START}
<p align="center">
  <strong>{valid}</strong> valid #1s &nbsp;·&nbsp;
  <strong>{counts['rankable']}</strong> rankable benchmarks &nbsp;·&nbsp;
  <strong>1</strong> persistent campaign
</p>
<p align="center">
  <sub>“Valid #&#8203;1” means the construction ranked first in the frozen snapshot,
  passed the unchanged verifier, and followed the written problem rules.</sub>
</p>
{SNAPSHOT_END}"""


def replace_block(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if len(pattern.findall(text)) != 1:
        raise AssertionError(f"expected exactly one generated block: {start}")
    return pattern.sub(replacement, text)


def jpeg_dimensions(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    if not raw.startswith(b"\xff\xd8"):
        raise ValueError("not a JPEG")
    index = 2
    while index + 9 < len(raw):
        if raw[index] != 0xFF:
            index += 1
            continue
        marker = raw[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(raw):
            break
        length = int.from_bytes(raw[index:index + 2], "big")
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height = int.from_bytes(raw[index + 3:index + 5], "big")
            width = int.from_bytes(raw[index + 5:index + 7], "big")
            return width, height
        index += length
    raise ValueError("JPEG has no size marker")


def validate_readme(text: str) -> list[str]:
    frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
    errors: list[str] = []
    counts = frontier_partition(frontier)

    if frontier["domain_valid_first_places"] != 5:
        errors.append("frontier domain-valid count is no longer 5")
    if frontier["platform_first_places"] != 7:
        errors.append("frontier platform count is no longer 7")
    if counts != {"blocked": 2, "leaders": 7, "live": 10, "rankable": 17, "total": 19}:
        errors.append(f"frontier 7+10+2 partition changed: {counts}")
    if frontier.get("rankable_benchmarks") != counts["rankable"]:
        errors.append("frontier rankable count disagrees with problem rows")
    if frontier.get("blocked_lanes") != counts["blocked"]:
        errors.append("frontier blocked count disagrees with problem rows")
    if frontier.get("live_frontiers") != counts["live"]:
        errors.append("frontier live count disagrees with problem rows")
    if counts["total"] != 19:
        errors.append("frontier problem count is no longer 19")
    blocked_reasons = {
        row["slug"]: row["verified_blocked"]["reason_code"]
        for row in frontier["problems"]
        if row["integrity"] == "domain-valid-blocked"
    }
    if blocked_reasons != {
        "kissing-number-d11": "objective-floor-and-ordinal-ranking",
        "kissing-number-d12": "submission-disabled-http-409",
    }:
        errors.append(f"blocked-lane identities or reasons changed: {blocked_reasons}")
    if expected_snapshot(frontier) not in text:
        errors.append("generated snapshot block is stale")

    lowered = text.lower()
    for phrase in FORBIDDEN:
        if phrase in lowered:
            errors.append(f"forbidden claim appears: {phrase!r}")
    if re.search(r"\b19\b", text):
        errors.append("README landing-page denominator must be 17, not 19")

    for detail in ("176,121", "353,220", "http 409", "solution #1492"):
        if detail in lowered:
            errors.append(f"blocked-lane detail belongs off the landing page: {detail!r}")

    normalized = re.sub(r"\s+", " ", text)
    contract_text = normalized.replace("#&#8203;1", "#1")
    required_strings = (
        "Daybreak Blue",
        "five valid #1 constructions",
        "17 rankable EinsteinArena benchmarks",
        "<strong>1</strong> persistent campaign",
        "“Valid #1” means the construction ranked first in the frozen snapshot",
        "They are not claims that five underlying open problems have been completely solved.",
        "docs/ERDOS_MINIMUM_OVERLAP.md",
        "docs/BLOCKED_LANES.md",
        "docs/COMPUTE.md",
        "<details>",
        "Run details and exact configuration",
    )
    for required in required_strings:
        if required not in contract_text:
            errors.append(f"missing landing-page contract: {required}")

    image_sources = (
        "assets/prolong-memory-codex.webp",
        "assets/codexprolong-system-loop.webp",
    )
    for source in image_sources:
        if text.count(f'src="{source}"') != 1:
            errors.append(f"README must contain exactly one {source}")

    html_images = re.findall(r"<img\b.*?>", text, flags=re.IGNORECASE | re.DOTALL)
    if len(html_images) != 2:
        errors.append(f"README must contain exactly the two approved figures, found {len(html_images)}")
    for tag in html_images:
        if not re.search(r"\balt\s*=\s*['\"][^'\"]+['\"]", tag, flags=re.IGNORECASE):
            errors.append("HTML image is missing nonempty alt text")
        match = re.search(r"\bsrc\s*=\s*['\"]([^'\"]+)['\"]", tag, flags=re.IGNORECASE)
        if not match:
            errors.append("HTML image is missing src")
            continue
        source = ROOT / match.group(1)
        if not source.is_file():
            errors.append(f"README image does not exist: {match.group(1)}")
        elif source.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            if source.stat().st_size > 600_000:
                errors.append(f"README raster exceeds 600 KB: {match.group(1)}")
            if source.suffix.lower() == ".webp" and source.stat().st_size > 250_000:
                errors.append(f"README WebP exceeds 250 KB target: {match.group(1)}")

    markdown_images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", text)
    if markdown_images:
        errors.append("README must not add figures beyond the two approved purple images")

    social = ROOT / "assets/social-preview-1200x630.jpg"
    if not social.is_file():
        errors.append("missing social preview JPEG")
    else:
        if social.stat().st_size >= 1_000_000:
            errors.append("social preview is not below 1 MB")
        try:
            if jpeg_dimensions(social) != (1200, 630):
                errors.append("social preview is not exactly 1200×630")
        except ValueError as error:
            errors.append(f"invalid social preview: {error}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="refresh the generated README snapshot block",
    )
    args = parser.parse_args()
    text = README.read_text(encoding="utf-8")
    if args.write:
        frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
        text = replace_block(text, SNAPSHOT_START, SNAPSHOT_END, expected_snapshot(frontier))
        README.write_text(text, encoding="utf-8")
    errors = validate_readme(text)
    if errors:
        print("README claim check FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("README claim check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
