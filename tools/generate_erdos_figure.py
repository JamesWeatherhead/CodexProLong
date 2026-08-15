#!/usr/bin/env python3
"""Generate the exact-data Erdős README visual and social-preview source."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from .certify_erdos_continuous import (
        ROOT,
        common_integer_payload,
        exact_overlap_numerators,
    )
except ImportError:  # Direct execution: ``python tools/generate_erdos_figure.py``.
    from certify_erdos_continuous import (
        ROOT,
        common_integer_payload,
        exact_overlap_numerators,
    )


PAYLOAD = ROOT / "artifacts/wins/erdos-min-overlap.json"
CERTIFICATE = ROOT / "artifacts/certificates/erdos-min-overlap-continuous.json"
FIGURE = ROOT / "assets/erdos-overlap-explainer.svg"
SOCIAL_SVG = ROOT / "assets/social-preview-1200x630.svg"


def sampled(values: list[float], count: int, *, maximum: bool = False) -> list[float]:
    result: list[float] = []
    for column in range(count):
        start = column * len(values) // count
        stop = max(start + 1, (column + 1) * len(values) // count)
        bucket = values[start:stop]
        result.append(max(bucket) if maximum else sum(bucket) / len(bucket))
    return result


def line_path(values: list[float | None], x: float, y: float, width: float, height: float) -> str:
    points: list[str] = []
    pen_up = True
    denominator = max(1, len(values) - 1)
    for index, value in enumerate(values):
        if value is None:
            pen_up = True
            continue
        px = x + width * index / denominator
        py = y + height * (1.0 - value)
        points.append(f"{'M' if pen_up else 'L'} {px:.2f} {py:.2f}")
        pen_up = False
    return " ".join(points)


def area_path(values: list[float], x: float, y: float, width: float, height: float) -> str:
    line = line_path(values, x, y, width, height)
    return f"M {x:.2f} {y + height:.2f} {line[1:]} L {x + width:.2f} {y + height:.2f} Z"


def figure_svg() -> str:
    values = json.loads(PAYLOAD.read_text(encoding="utf-8"))["values"]
    certificate = json.loads(CERTIFICATE.read_text(encoding="utf-8"))
    integers, total, _ = common_integer_payload(values)
    mass = len(values) // 2
    normalized = [mass * value / total for value in integers]
    exact_scores = exact_overlap_numerators(integers, total, mass)
    score_values = [numerator / (total * total) for _, numerator in exact_scores]
    best_index = max(range(len(score_values)), key=score_values.__getitem__)
    best_lag = exact_scores[best_index][0]

    density = sampled(normalized, 240)
    shift = best_lag
    shifted: list[float | None] = []
    for index in range(len(normalized)):
        other = index - shift
        shifted.append(1.0 - normalized[other] if 0 <= other < len(normalized) else None)
    density_small = sampled(normalized, 240)
    shifted_small: list[float | None] = []
    for column in range(240):
        start = column * len(shifted) // 240
        stop = max(start + 1, (column + 1) * len(shifted) // 240)
        bucket = [value for value in shifted[start:stop] if value is not None]
        shifted_small.append(sum(bucket) / len(bucket) if bucket else None)
    curve = sampled(score_values, 320, maximum=True)

    score = certificate["rigorous_decimal_upper_bound"]
    score_short = score[:12]
    panel_x = (50, 475, 900)
    panel_y, panel_w, panel_h = 150, 400, 525
    plot_y, plot_h = 285, 210
    plot_w = 332
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 760" role="img" aria-labelledby="title description">',
        '<title id="title">Erdős minimum-overlap construction</title>',
        '<desc id="description">Three panels show the exact candidate density, its shifted complement, and the overlap across every shift. The lowest possible maximum is the objective.</desc>',
        '<defs>',
        '<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#080714"/><stop offset="0.56" stop-color="#11102a"/><stop offset="1" stop-color="#071822"/></linearGradient>',
        '<linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#a87cff" stop-opacity="0.68"/><stop offset="1" stop-color="#6b45ff" stop-opacity="0.05"/></linearGradient>',
        '<filter id="glow"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>',
        '</defs>',
        '<rect width="1400" height="760" rx="34" fill="url(#bg)"/>',
        '<path d="M 30 118 C 330 35, 1070 35, 1370 118" fill="none" stroke="#8f65ff" stroke-opacity="0.35" stroke-width="2"/>',
        '<text x="56" y="63" fill="#f5f2ff" font-size="32" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">ERDŐS MINIMUM OVERLAP</text>',
        '<text x="56" y="104" fill="#aaa6c8" font-size="20" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">An explicit density · every shift checked · exact rational certificate</text>',
    ]
    for x in panel_x:
        parts.append(f'<rect x="{x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="24" fill="#15142f" stroke="#6f58a8" stroke-opacity="0.72"/>')

    labels = (("01", "CHOOSE A DENSITY"), ("02", "SHIFT ITS COMPLEMENT"), ("03", "MINIMIZE THE WORST"))
    for x, (number, label) in zip(panel_x, labels):
        parts.extend([
            f'<text x="{x + 28}" y="{panel_y + 52}" fill="#55d9ff" font-size="22" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">{number}</text>',
            f'<text x="{x + 70}" y="{panel_y + 52}" fill="#f5f2ff" font-size="22" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">{label}</text>',
        ])

    # Panel 1
    x = panel_x[0] + 34
    parts.extend([
        f'<path d="{area_path(density, x, plot_y, plot_w, plot_h)}" fill="url(#fill)"/>',
        f'<path d="{line_path(density, x, plot_y, plot_w, plot_h)}" fill="none" stroke="#b996ff" stroke-width="3"/>',
        f'<line x1="{x}" y1="{plot_y + plot_h}" x2="{x + plot_w}" y2="{plot_y + plot_h}" stroke="#504b75"/>',
        f'<text x="{x}" y="{plot_y + plot_h + 34}" fill="#aaa6c8" font-size="20" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">f(x) on [0, 2]</text>',
        f'<text x="{x}" y="{panel_y + panel_h - 45}" fill="#ddd7f5" font-size="20" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">exact integral = 1</text>',
    ])

    # Panel 2
    x = panel_x[1] + 34
    parts.extend([
        f'<path d="{line_path(density_small, x, plot_y, plot_w, plot_h)}" fill="none" stroke="#b996ff" stroke-width="3"/>',
        f'<path d="{line_path(shifted_small, x, plot_y, plot_w, plot_h)}" fill="none" stroke="#55d9ff" stroke-width="3" stroke-dasharray="8 7"/>',
        f'<line x1="{x}" y1="{plot_y + plot_h}" x2="{x + plot_w}" y2="{plot_y + plot_h}" stroke="#504b75"/>',
        f'<line x1="{x}" y1="{plot_y + plot_h + 30}" x2="{x + 28}" y2="{plot_y + plot_h + 30}" stroke="#b996ff" stroke-width="3"/>',
        f'<text x="{x + 38}" y="{plot_y + plot_h + 36}" fill="#ddd7f5" font-size="19" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">density</text>',
        f'<line x1="{x + 166}" y1="{plot_y + plot_h + 30}" x2="{x + 194}" y2="{plot_y + plot_h + 30}" stroke="#55d9ff" stroke-width="3" stroke-dasharray="8 7"/>',
        f'<text x="{x + 204}" y="{plot_y + plot_h + 36}" fill="#ddd7f5" font-size="19" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">shifted 1−f</text>',
        f'<text x="{x}" y="{panel_y + panel_h - 45}" fill="#aaa6c8" font-size="20" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">representative worst lag: {best_lag}</text>',
    ])

    # Panel 3
    x = panel_x[2] + 34
    curve_min, curve_max = min(curve), max(curve)
    scaled_curve = [(value - curve_min) / (curve_max - curve_min) for value in curve]
    marker_x = x + plot_w * best_index / (len(score_values) - 1)
    parts.extend([
        f'<path d="{area_path(scaled_curve, x, plot_y, plot_w, plot_h)}" fill="url(#fill)"/>',
        f'<path d="{line_path(scaled_curve, x, plot_y, plot_w, plot_h)}" fill="none" stroke="#8c76ff" stroke-width="3"/>',
        f'<line x1="{x}" y1="{plot_y + plot_h}" x2="{x + plot_w}" y2="{plot_y + plot_h}" stroke="#504b75"/>',
        f'<circle cx="{marker_x:.2f}" cy="{plot_y:.2f}" r="8" fill="#56f3bf" filter="url(#glow)"/>',
        f'<text x="{x}" y="{plot_y + plot_h + 34}" fill="#aaa6c8" font-size="20" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">all 7,167 grid shifts</text>',
        f'<text x="{x}" y="{panel_y + panel_h - 76}" fill="#56f3bf" font-size="30" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">≤ {score_short}</text>',
        f'<text x="{x}" y="{panel_y + panel_h - 43}" fill="#f5f2ff" font-size="20" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">LOWER IS BETTER</text>',
    ])
    parts.extend([
        '<text x="700" y="724" text-anchor="middle" fill="#aaa6c8" font-size="19" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">Visualization downsampled for display · certificate uses all 3,584 values</text>',
        '</svg>',
    ])
    return "\n".join(parts) + "\n"


def social_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 630">
<defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#080713"/><stop offset="0.58" stop-color="#171035"/><stop offset="1" stop-color="#062333"/></linearGradient></defs>
<rect width="1200" height="630" rx="34" fill="url(#b)"/>
<path d="M 35 485 C 300 365, 785 560, 1165 362" fill="none" stroke="#8b63ff" stroke-opacity=".5" stroke-width="3"/>
<circle cx="1030" cy="120" r="145" fill="none" stroke="#55d9ff" stroke-opacity=".22" stroke-width="2"/>
<text x="76" y="122" fill="#b692ff" font-size="34" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">CODEXPROLONG</text>
<text x="76" y="245" fill="#f7f3ff" font-size="66" font-weight="800" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">5 VALID #1 CONSTRUCTIONS</text>
<text x="76" y="335" fill="#55d9ff" font-size="38" font-weight="600" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">17 RANKABLE PROBLEMS</text>
<text x="76" y="397" fill="#56f3bf" font-size="38" font-weight="600" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">1 PERSISTENT CAMPAIGN</text>
<text x="76" y="553" fill="#c7c1db" font-size="25" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">DAYBREAK BLUE · CODEX · PROLONG MEMORY</text>
</svg>
"""


def main() -> int:
    FIGURE.write_text(figure_svg(), encoding="utf-8")
    SOCIAL_SVG.write_text(social_svg(), encoding="utf-8")
    print(f"wrote {FIGURE.relative_to(ROOT)}")
    print(f"wrote {SOCIAL_SVG.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
