"""Tests for rich-text speaker notes."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from slide_skill.exporter import export_project, pptx_notes, validate_pptx
from slide_skill.project import init_project


def _make_project_with_notes(tmp: Path, svg_content: str, notes_text: str) -> Path:
    project = init_project("Notes Test", base_dir=tmp / "projects")
    svg_dir = project / "svg_output"
    svg_dir.mkdir(parents=True, exist_ok=True)
    (svg_dir / "slide_01.svg").write_text(svg_content, encoding="utf-8")
    notes_dir = project / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / "slide_01.md").write_text(notes_text, encoding="utf-8")
    return project


SVG = (
    '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
    '<g id="content-main"><rect x="10" y="10" width="100" height="100" fill="#111111"/></g>'
    "</svg>"
)


class RichNotesTest(unittest.TestCase):
    def test_bold_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project_with_notes(Path(tmp), SVG, "This is **bold** text")
            deck = export_project(project, stage="output")
            notes = pptx_notes(deck)
            self.assertIn("bold", notes)

    def test_italic_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project_with_notes(Path(tmp), SVG, "This is *italic* text")
            deck = export_project(project, stage="output")
            notes = pptx_notes(deck)
            self.assertIn("italic", notes)

    def test_bullet_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project_with_notes(Path(tmp), SVG, "- First point\n- Second point")
            deck = export_project(project, stage="output")
            notes = pptx_notes(deck)
            self.assertIn("First point", notes)
            self.assertIn("Second point", notes)

    def test_combined_formatting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            notes_text = "Title\n- **Bold bullet**\n- *Italic bullet*\nPlain text"
            project = _make_project_with_notes(Path(tmp), SVG, notes_text)
            deck = export_project(project, stage="output")
            notes = pptx_notes(deck)
            self.assertIn("Bold bullet", notes)
            self.assertIn("Italic bullet", notes)
            self.assertIn("Plain text", notes)

    def test_plain_text_backward_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project_with_notes(Path(tmp), SVG, "Plain text note without formatting")
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)
            notes = pptx_notes(deck)
            self.assertIn("Plain text note without formatting", notes)

    def test_deck_valid_with_rich_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_project_with_notes(Path(tmp), SVG, "**Bold** and *italic* and bullets\n- Item")
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)


class RunParserTest(unittest.TestCase):
    def test_parse_runs(self) -> None:
        from slide_skill.exporter import _parse_runs

        runs = _parse_runs("Hello **world** end")
        self.assertEqual(len(runs), 3)
        self.assertEqual(runs[0], ("Hello ", False, False))
        self.assertEqual(runs[1], ("world", True, False))
        self.assertEqual(runs[2], (" end", False, False))

    def test_parse_italic(self) -> None:
        from slide_skill.exporter import _parse_runs

        runs = _parse_runs("Hello *world* end")
        self.assertEqual(runs[1], ("world", False, True))

    def test_plain_text_single_run(self) -> None:
        from slide_skill.exporter import _parse_runs

        runs = _parse_runs("Just plain text")
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0], ("Just plain text", False, False))


if __name__ == "__main__":
    unittest.main()
