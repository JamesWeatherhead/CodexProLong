from __future__ import annotations

import json
import unittest

from tools.check_readme_claims import (
    FRONTIER,
    README,
    ROOT,
    frontier_partition,
    jpeg_dimensions,
    validate_readme,
)
from tools.generate_erdos_figure import FIGURE, SOCIAL_SVG, figure_svg, social_svg


class ReadmeClaimsTest(unittest.TestCase):
    def test_current_readme_passes(self) -> None:
        self.assertEqual(validate_readme(README.read_text(encoding="utf-8")), [])

    def test_forbidden_claim_is_rejected(self) -> None:
        text = README.read_text(encoding="utf-8") + "\nCodex solved a 71-year-old problem.\n"
        errors = validate_readme(text)
        self.assertTrue(any("forbidden claim" in error for error in errors))

    def test_model_superlative_is_rejected(self) -> None:
        text = README.read_text(encoding="utf-8") + "\nOpenAI’s best model\n"
        errors = validate_readme(text)
        self.assertTrue(any("forbidden claim" in error for error in errors))

    def test_solved_five_open_problems_is_rejected(self) -> None:
        text = README.read_text(encoding="utf-8") + "\nCodex solved five open problems.\n"
        errors = validate_readme(text)
        self.assertTrue(any("forbidden claim" in error for error in errors))

    def test_nineteen_is_rejected_on_landing_page(self) -> None:
        text = README.read_text(encoding="utf-8") + "\n19 open math benchmarks\n"
        errors = validate_readme(text)
        self.assertTrue(any("denominator must be 17" in error for error in errors))

    def test_frontier_partition_is_7_plus_10_plus_2(self) -> None:
        frontier = json.loads(FRONTIER.read_text(encoding="utf-8"))
        self.assertEqual(
            frontier_partition(frontier),
            {"blocked": 2, "leaders": 7, "live": 10, "rankable": 17, "total": 19},
        )

    def test_blocker_specifics_stay_off_the_landing_page(self) -> None:
        text = README.read_text(encoding="utf-8").lower()
        for detail in ("176,121", "353,220", "http 409", "solution #1492"):
            self.assertNotIn(detail, text)
        self.assertIn("docs/blocked_lanes.md", text)

    def test_missing_alt_text_is_rejected(self) -> None:
        text = README.read_text(encoding="utf-8") + '\n<img src="assets/prolong-memory-codex.webp">\n'
        errors = validate_readme(text)
        self.assertTrue(any("alt text" in error for error in errors))

    def test_removed_erdos_figure_is_rejected(self) -> None:
        text = README.read_text(encoding="utf-8") + "\nassets/erdos-overlap-explainer.svg\n"
        errors = validate_readme(text)
        self.assertTrue(any("forbidden claim" in error for error in errors))

    def test_each_purple_figure_appears_once(self) -> None:
        text = README.read_text(encoding="utf-8")
        duplicated = text + '\n<img alt="duplicate" src="assets/prolong-memory-codex.webp">\n'
        errors = validate_readme(duplicated)
        self.assertTrue(any("exactly one assets/prolong-memory-codex.webp" in error for error in errors))

    def test_run_details_and_valid_definition_are_required(self) -> None:
        text = README.read_text(encoding="utf-8")
        without_details = text.replace("Run details and exact configuration", "Technical appendix")
        without_definition = text.replace(
            "“Valid #&#8203;1” means the construction ranked first in the frozen snapshot",
            "A valid result is documented",
        )
        self.assertTrue(any("Run details" in error for error in validate_readme(without_details)))
        self.assertTrue(any("Valid #1" in error for error in validate_readme(without_definition)))

    def test_generated_visuals_are_current(self) -> None:
        self.assertEqual(FIGURE.read_text(encoding="utf-8"), figure_svg())
        self.assertEqual(SOCIAL_SVG.read_text(encoding="utf-8"), social_svg())
        self.assertLess(FIGURE.stat().st_size, 300_000)

    def test_social_preview_contract(self) -> None:
        preview = ROOT / "assets/social-preview-1200x630.jpg"
        self.assertEqual(jpeg_dimensions(preview), (1200, 630))
        self.assertLess(preview.stat().st_size, 1_000_000)


if __name__ == "__main__":
    unittest.main()
