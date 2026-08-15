#!/usr/bin/env python3
"""Validate the README's generated facts, claim boundary, links, and images."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, localcontext
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
FRONTIER = ROOT / "data/frontier.json"
RECEIPT = ROOT / "artifacts/receipts/erdos-min-overlap.json"
CERTIFICATE = ROOT / "artifacts/certificates/erdos-min-overlap-continuous.json"
PROGRESS = ROOT / "assets/frontier-progress.svg"
SNAPSHOT_START = "<!-- BEGIN GENERATED:SNAPSHOT -->"
SNAPSHOT_END = "<!-- END GENERATED:SNAPSHOT -->"
ERDOS_START = "<!-- BEGIN GENERATED:ERDOS-SCORE -->"
ERDOS_END = "<!-- END GENERATED:ERDOS-SCORE -->"
FORBIDDEN = (
    "solved a 71-year-old problem",
    "solved a 71 year old problem",
    "fully autonomous",
    "five open problems solved",
    "seven mathematical discoveries",
    "10 problems solved",
    "all 19 solved",
)


def superscript(number: int) -> str:
    table = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    return str(number).translate(table)


def lower_scientific(value: Decimal, digits: int = 2) -> str:
    exponent = value.adjusted()
    quantum = Decimal(1).scaleb(-digits)
    with localcontext() as context:
        context.prec = 60
        coefficient = value.scaleb(-exponent).quantize(quantum, rounding=ROUND_FLOOR)
    return f"{coefficient} × 10{superscript(exponent)}"


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


def progress_svg(frontier: dict[str, object]) -> str:
    counts = frontier_partition(frontier)
    rankable = counts["rankable"]
    leaders = counts["leaders"]
    percent = 100 * leaders / rankable
    start_x = 50.0
    gap = 8.0
    total_width = 1100.0
    segment_width = (total_width - gap * (rankable - 1)) / rankable
    segments = []
    for index in range(rankable):
        x = start_x + index * (segment_width + gap)
        if index < leaders:
            fill = "#8f65ff"
            stroke = "#c8b6ff"
        else:
            fill = "#24213b"
            stroke = "#514b75"
        segments.append(
            f'<rect x="{x:.2f}" y="72" width="{segment_width:.2f}" height="48" '
            f'rx="12" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )
    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 180" role="img" aria-labelledby="title desc">',
            f'<title id="title">{leaders} of {rankable} rankable lanes led</title>',
            f'<desc id="desc">A progress bar with {leaders} filled segments and {counts["live"]} unfilled segments.</desc>',
            '<rect width="1200" height="180" rx="28" fill="#0c0a1a"/>',
            f'<text x="50" y="45" fill="#f5f2ff" font-size="28" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">{leaders} OF {rankable} RANKABLE LANES LED</text>',
            f'<text x="1150" y="45" text-anchor="end" fill="#55d9ff" font-size="28" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">{percent:.1f}%</text>',
            *segments,
            f'<text x="50" y="157" fill="#b692ff" font-size="20" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">{leaders} PLATFORM LEADERS</text>',
            f'<text x="1150" y="157" text-anchor="end" fill="#aaa6c8" font-size="20" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">{counts["live"]} LIVE FRONTIERS REMAIN</text>',
            '</svg>',
            '',
        ]
    )


def expected_snapshot(frontier: dict[str, object]) -> str:
    generated = datetime.fromisoformat(str(frontier["generated_at"]).replace("Z", "+00:00"))
    stamp = generated.strftime("%B %-d, %Y · %H:%M UTC")
    counts = frontier_partition(frontier)
    return f"""{SNAPSHOT_START}
<p align="center">
  <a href="docs/STATUS.md">
    <img
      alt="Platform-leader progress: {counts['leaders']} of {counts['rankable']} rankable EinsteinArena lanes led ({100 * counts['leaders'] / counts['rankable']:.1f}%); {counts['live']} live frontiers remain"
      src="assets/frontier-progress.svg"
      width="88%">
  </a>
  <br>
  <sub>{frontier['domain_valid_first_places']} domain-valid #1s · Frozen {stamp.replace(' · ', ' at ')} · Rankings can change; archived hashes do not</sub>
</p>
{SNAPSHOT_END}"""


def expected_erdos(receipt: dict[str, object], certificate: dict[str, object]) -> str:
    exact = Decimal(str(certificate["rigorous_decimal_upper_bound"]))
    visible_exact = exact.quantize(Decimal("0.0000000001"), rounding=ROUND_CEILING)
    improvement = Decimal(str(certificate["improvement_over_prior_arena_leader"]))
    return f"""{ERDOS_START}
| Frozen comparison | Score |
|---|---:|
| Previous Arena leader | `{receipt['leader_score']:.10f}` |
| CodexProLong exact upper bound | **`{visible_exact}`** |
| Improvement over that frontier | `> {lower_scientific(improvement)}` |
| Direction | **lower is better** |
{ERDOS_END}"""


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
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    certificate = json.loads(CERTIFICATE.read_text(encoding="utf-8"))
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
    if expected_erdos(receipt, certificate) not in text:
        errors.append("generated Erdős score block is stale")
    if not PROGRESS.is_file() or PROGRESS.read_text(encoding="utf-8") != progress_svg(frontier):
        errors.append("frontier progress SVG is stale")

    lowered = text.lower()
    for phrase in FORBIDDEN:
        if phrase in lowered:
            errors.append(f"forbidden claim appears: {phrase!r}")

    for detail in ("176,121", "353,220", "http 409", "solution #1492"):
        if detail in lowered:
            errors.append(f"blocked-lane detail belongs off the landing page: {detail!r}")

    for required in ("docs/BLOCKED_LANES.md", "docs/COMPUTE.md"):
        if required not in text or not (ROOT / required).is_file():
            errors.append(f"missing landing-page deep link: {required}")

    for required in (
        "artifacts/wins/erdos-min-overlap.json",
        "artifacts/verifiers/erdos-min-overlap.json",
        "artifacts/certificates/erdos-min-overlap-continuous.json",
    ):
        if required not in text or not (ROOT / required).is_file():
            errors.append(f"missing Erdős evidence link: {required}")

    for tag in re.findall(r"<img\b.*?>", text, flags=re.IGNORECASE | re.DOTALL):
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

    for alt, source_text in re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", text):
        if not alt.strip():
            errors.append("Markdown image is missing alt text")
        source = ROOT / source_text.split(maxsplit=1)[0].strip("<>")
        if not source.is_file():
            errors.append(f"README image does not exist: {source_text}")

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
        help="refresh the two generated README blocks and progress SVG",
    )
    args = parser.parse_args()
    text = README.read_text(encoding="utf-8")
    if args.write:
        frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        certificate = json.loads(CERTIFICATE.read_text(encoding="utf-8"))
        text = replace_block(text, SNAPSHOT_START, SNAPSHOT_END, expected_snapshot(frontier))
        text = replace_block(text, ERDOS_START, ERDOS_END, expected_erdos(receipt, certificate))
        README.write_text(text, encoding="utf-8")
        PROGRESS.write_text(progress_svg(frontier), encoding="utf-8")
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
