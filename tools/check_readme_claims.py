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


def expected_snapshot(frontier: dict[str, object]) -> str:
    generated = datetime.fromisoformat(str(frontier["generated_at"]).replace("Z", "+00:00"))
    stamp = generated.strftime("%B %-d, %Y · %H:%M UTC")
    return f"""{SNAPSHOT_START}
<table align="center">
  <tr>
    <td align="center" width="33%"><strong>{frontier['domain_valid_first_places']}</strong><br><sub>domain-valid #1s</sub></td>
    <td align="center" width="33%"><strong>{frontier['platform_first_places']}</strong><br><sub>platform leaders</sub></td>
    <td align="center" width="33%"><strong>{len(frontier['problems'])}</strong><br><sub>open benchmarks</sub></td>
  </tr>
</table>

<p align="center"><sub>Frozen snapshot: {stamp}. Rankings can change. Archived hashes do not.</sub></p>
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

    if frontier["domain_valid_first_places"] != 5:
        errors.append("frontier domain-valid count is no longer 5")
    if frontier["platform_first_places"] != 7:
        errors.append("frontier platform count is no longer 7")
    if len(frontier["problems"]) != 19:
        errors.append("frontier problem count is no longer 19")
    if expected_snapshot(frontier) not in text:
        errors.append("generated snapshot block is stale")
    if expected_erdos(receipt, certificate) not in text:
        errors.append("generated Erdős score block is stale")

    lowered = text.lower()
    for phrase in FORBIDDEN:
        if phrase in lowered:
            errors.append(f"forbidden claim appears: {phrase!r}")

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
    parser.add_argument("--write", action="store_true", help="refresh only the two generated blocks")
    args = parser.parse_args()
    text = README.read_text(encoding="utf-8")
    if args.write:
        frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        certificate = json.loads(CERTIFICATE.read_text(encoding="utf-8"))
        text = replace_block(text, SNAPSHOT_START, SNAPSHOT_END, expected_snapshot(frontier))
        text = replace_block(text, ERDOS_START, ERDOS_END, expected_erdos(receipt, certificate))
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
