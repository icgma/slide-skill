"""Tests for v1.4 Phase 24 — HTML/Reveal Preview + Presenter View."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from slide_skill import html_preview


def _make_project(tmp: Path, slide_count: int = 3, with_notes: bool = True) -> Path:
    final = tmp / "svg_final"
    final.mkdir(parents=True)
    for n in range(1, slide_count + 1):
        svg = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600">'
            f'<rect width="800" height="600" fill="#222"/><text x="20" y="40" fill="#fff">Slide {n}</text></svg>'
        )
        (final / f"slide_{n:02d}.svg").write_text(svg, encoding="utf-8")
    if with_notes:
        notes = []
        for n in range(1, slide_count + 1):
            notes.append(f"## Slide {n}\nNote text for slide {n}.")
        (tmp / "notes.md").write_text("\n\n".join(notes), encoding="utf-8")
    return tmp


class HtmlPreviewTests(unittest.TestCase):
    def test_missing_final_dir_raises(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                html_preview.render_preview_html(Path(tmp))

    def test_renders_html_with_all_slides(self) -> None:
        with TemporaryDirectory() as tmp:
            project = _make_project(Path(tmp), slide_count=3)
            html = html_preview.render_preview_html(project, title="Demo", lang="en")
            self.assertIn("<title>Demo</title>", html)
            self.assertIn("1 / 3", html)  # initial counter content
            self.assertIn("Slide 1", html)
            self.assertIn("Slide 3", html)
            # JSON-embedded slide array.
            m = re.search(r"const SLIDES = (\[.*?\]);", html, re.DOTALL)
            self.assertIsNotNone(m)
            slides = json.loads(m.group(1))
            self.assertEqual(len(slides), 3)
            # XML decl stripped.
            for s in slides:
                self.assertNotIn("<?xml", s)

    def test_notes_split_per_slide(self) -> None:
        with TemporaryDirectory() as tmp:
            project = _make_project(Path(tmp), slide_count=2, with_notes=True)
            html = html_preview.render_preview_html(project)
            m = re.search(r"const NOTES = (\[.*?\]);", html, re.DOTALL)
            self.assertIsNotNone(m)
            notes = json.loads(m.group(1))
            self.assertEqual(len(notes), 2)
            self.assertIn("Note text for slide 1", notes[0])
            self.assertIn("Note text for slide 2", notes[1])

    def test_notes_default_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            project = _make_project(Path(tmp), slide_count=2, with_notes=False)
            html = html_preview.render_preview_html(project)
            m = re.search(r"const NOTES = (\[.*?\]);", html, re.DOTALL)
            notes = json.loads(m.group(1))
            self.assertEqual(notes, ["", ""])

    def test_write_preview_html_creates_file(self) -> None:
        with TemporaryDirectory() as tmp:
            project = _make_project(Path(tmp), slide_count=1)
            out = Path(tmp) / "preview.html"
            result = html_preview.write_preview_html(project, out, title="X")
            self.assertEqual(result, out)
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 1000)

    def test_html_includes_presenter_hotkeys(self) -> None:
        with TemporaryDirectory() as tmp:
            project = _make_project(Path(tmp), slide_count=1)
            html = html_preview.render_preview_html(project)
            for key in ("ArrowRight", "ArrowLeft", "togglePresenter", "toggleBlack", "toggleWhite"):
                self.assertIn(key, html)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
