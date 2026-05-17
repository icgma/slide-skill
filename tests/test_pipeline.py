from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from slide_skill.exporter import export_project, pptx_notes, pptx_text, validate_pptx
from slide_skill.project import init_project, validate_project
from slide_skill.qa import run_qa
from slide_skill.svg_pipeline import check_project_svg, create_spec, finalize_svg, generate_svg, write_svg_report


class PipelineTest(unittest.TestCase):
    def test_markdown_to_editable_pptx_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            source.write_text("# Demo\n\n## First Slide\n\nEditable native output.\n", encoding="utf-8")
            project = init_project("Demo Deck", base_dir=root / "projects")
            ok, errors = validate_project(project)
            self.assertTrue(ok, errors)

            create_spec(project, source)
            svg_paths = generate_svg(project, source)
            self.assertGreaterEqual(len(svg_paths), 1)
            report = write_svg_report(project)
            self.assertIn("status: passed", report.read_text(encoding="utf-8"))

            final_paths = finalize_svg(project)
            self.assertEqual(len(svg_paths), len(final_paths))

            (project / "notes" / "total.md").write_text(
                "## Slide 1\nOpening note.\n\n## Slide 2\nDetail note.\n",
                encoding="utf-8",
            )
            deck = export_project(project)
            valid, pptx_errors = validate_pptx(deck)
            self.assertTrue(valid, pptx_errors)
            self.assertIn("Demo", pptx_text(deck))
            notes = pptx_notes(deck)
            self.assertIn("Opening note.", notes)
            self.assertIn("Detail note.", notes)
            self.assertTrue(deck.with_name(deck.stem + "_notes.md").exists())

            qa_ok, qa_report = run_qa(project, deck)
            self.assertTrue(qa_ok, qa_report.read_text(encoding="utf-8"))
            self.assertIn("status: automated-passed", qa_report.read_text(encoding="utf-8"))

            strict_ok, strict_report = run_qa(project, deck, require_visual=True, require_fix_verify=True)
            self.assertFalse(strict_ok)
            self.assertIn("status: failed", strict_report.read_text(encoding="utf-8"))

            rendered = project / "qa" / "rendered"
            rendered.mkdir(parents=True, exist_ok=True)
            (rendered / "slide-1.jpg").write_bytes(b"fake-render")
            (project / "qa" / "VISUAL-REVIEW.md").write_text("# Visual Review\n\nPassed.\n", encoding="utf-8")
            (project / "qa" / "FIX-VERIFY.md").write_text("# Fix And Verify\n\nChecked.\n", encoding="utf-8")

            strict_ok, strict_report = run_qa(project, deck, require_visual=True, require_fix_verify=True)
            self.assertTrue(strict_ok, strict_report.read_text(encoding="utf-8"))
            self.assertIn("status: passed", strict_report.read_text(encoding="utf-8"))

    def test_svg_gate_rejects_banned_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = init_project("Bad Svg", base_dir=root / "projects")
            svg = project / "svg_output" / "slide_01.svg"

            # v2.0: animation tags are banned hard errors
            svg.write_text(
                """<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="content-main">
    <rect x="10" y="10" width="100" height="100" fill="#111111"/>
    <animate attributeName="opacity" from="0" to="1" dur="1s"/>
  </g>
</svg>
""",
                encoding="utf-8",
            )

            ok, issues = check_project_svg(project)
            self.assertFalse(ok)
            self.assertTrue(any("Banned SVG tag" in issue.message for issue in issues))

            # v2.0: DOM event-handler attributes are banned hard errors
            svg.write_text(
                """<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="content-main">
    <rect x="10" y="10" width="100" height="100" fill="#111111" onclick="alert(1)"/>
  </g>
</svg>
""",
                encoding="utf-8",
            )

            ok, issues = check_project_svg(project)
            self.assertFalse(ok)
            self.assertTrue(any("Banned event-handler attribute" in issue.message for issue in issues))
            with self.assertRaises(RuntimeError):
                finalize_svg(project)


if __name__ == "__main__":
    unittest.main()
