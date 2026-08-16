"""Tests for the design_guide module."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from slide_skill.design_guide import build_design_guide
from slide_skill.project import init_project


class DesignGuideTest(unittest.TestCase):

    def _make_project(self, tmp: Path) -> Path:
        return init_project("test-guide", base_dir=tmp / "projects")

    def test_build_design_guide_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            guide_path = build_design_guide(project, "dark-tech")
            self.assertTrue(guide_path.exists(), "design_guide.md should be created")
            self.assertEqual(guide_path.name, "design_guide.md")

    def test_guide_contains_theme_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            guide_path = build_design_guide(project, "light-corporate")
            content = guide_path.read_text(encoding="utf-8")
            self.assertIn("light-corporate", content)

    def test_guide_contains_palette_hex_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            guide_path = build_design_guide(project, "dark-tech")
            content = guide_path.read_text(encoding="utf-8")
            self.assertIn("#0F172A", content, "Background hex should appear in guide")
            self.assertIn("#3B82F6", content, "Accent hex should appear in guide")

    def test_guide_contains_canvas_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            guide_path = build_design_guide(project, "dark-tech")
            content = guide_path.read_text(encoding="utf-8")
            self.assertIn("1280", content)
            self.assertIn("720", content)

    def test_guide_contains_layout_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            guide_path = build_design_guide(project, "dark-tech")
            content = guide_path.read_text(encoding="utf-8")
            for layout in ["cover", "section-divider", "bullet-list", "two-column",
                           "metric-highlight", "quote", "closing"]:
                self.assertIn(layout, content, f"Layout template '{layout}' missing from guide")

    def test_guide_contains_svg_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            guide_path = build_design_guide(project, "dark-tech")
            content = guide_path.read_text(encoding="utf-8")
            self.assertIn("BANNED", content)
            self.assertIn("script", content)
            self.assertIn("foreignObject", content)

    def test_guide_contains_chrome_specs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            guide_path = build_design_guide(project, "dark-tech")
            content = guide_path.read_text(encoding="utf-8")
            # Chrome survives only as an optional deck-level motif (BENCH-01).
            self.assertIn("Optional Deck Motif", content,
                          "Guide must present chrome as an optional deck motif")
            self.assertNotIn("required on EVERY slide", content,
                             "Guide must not require chrome on every slide")
            self.assertNotIn("stripe (required)", content)
            self.assertNotIn("bar (required)", content)
            self.assertIn('width="6"', content,
                          "Stripe snippet stays available inside the optional motif example")
            self.assertIn('y="688"', content,
                          "Footer snippet stays available inside the optional motif example")

    def test_all_themes_produce_valid_guides(self) -> None:
        from slide_skill.themes import list_themes
        with tempfile.TemporaryDirectory() as tmp:
            for theme in list_themes():
                project = init_project(f"test-{theme.name}", base_dir=Path(tmp) / "projects")
                guide_path = build_design_guide(project, theme.name)
                content = guide_path.read_text(encoding="utf-8")
                self.assertGreater(len(content), 500, f"Guide for {theme.name} too short")
                self.assertIn(theme.palette["accent"], content)

    def test_guide_file_is_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project(Path(tmp))
            guide_path = build_design_guide(project, "warm-editorial")
            # Should not raise
            content = guide_path.read_text(encoding="utf-8")
            self.assertIsInstance(content, str)


if __name__ == "__main__":
    unittest.main()
