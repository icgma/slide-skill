from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from slide_skill.exporter import export_project, pptx_notes, pptx_text, validate_pptx
from slide_skill.project import init_project, validate_project
from slide_skill.qa import run_qa
from slide_skill.content_planner import plan_slides
from slide_skill.svg_pipeline import (
    check_project_svg,
    create_spec,
    finalize_svg,
    generate_svg,
    generate_svg_from_plan,
    write_svg_report,
)


def _svg_visible_text(svg_path: Path) -> str:
    import re

    text = svg_path.read_text(encoding="utf-8")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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
            report_text = report.read_text(encoding="utf-8")
            self.assertTrue(
                "✅ passed" in report_text or "status: passed" in report_text,
                f"Report should indicate passing: {report_text[:200]}",
            )

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

            (project / "qa" / "visual-feedback.json").write_text(json.dumps({
                "slides": [{
                    "slide": 1,
                    "severity": "major",
                    "issues": ["Title is clipped"],
                    "actions": ["Move title down"],
                    "repair_prompt": "Move the title down and preserve all text.",
                }]
            }), encoding="utf-8")
            strict_ok, strict_report = run_qa(project, deck, require_visual=True, require_fix_verify=True)
            strict_text = strict_report.read_text(encoding="utf-8")
            self.assertFalse(strict_ok)
            self.assertIn("status: failed", strict_text)
            self.assertIn("AI visual feedback max severity: major", strict_text)

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

    def test_plan_rendering_avoids_template_artifacts(self) -> None:
        source_md = """# Demo Deck

> 一份封面副标题。

## 传统流程

- PPT 手动调整,每页平均 12 分钟
- 改字号要重新对齐所有元素
- 设计依赖单一设计师

## 渲染管道

- Markdown → 智能切片(LLM 可选)
- 切片 → SVG(主题驱动,完全确定性)
- SVG → 原生 DrawingML(渐变、形状、文字均可编辑)

## 立即开始

- 安装:`pip install -e tools/slide`
- 快速体验:`slide-skill quickstart examples/sample.zh-CN.md --theme dark-tech`
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            source.write_text(source_md, encoding="utf-8")
            project = init_project("Artifact Regression", base_dir=root / "projects")
            create_spec(project, source)
            paths = generate_svg_from_plan(project, plan_slides(source_md))
            text = " ".join(_svg_visible_text(path) for path in paths)

            self.assertNotIn("POINT 01", text)
            self.assertNotIn("> 一份封面副标题", text)
            self.assertNotIn("- - 安装", text)
            self.assertIn("Markdown", text)
            self.assertIn("智能切片", text)
            self.assertIn("快速体验", text)

    def test_default_demo_samples_generate_10_to_15_slides(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for rel in ("examples/sample.zh-CN.md", "examples/sample.md"):
            with self.subTest(sample=rel):
                source = (root / rel).read_text(encoding="utf-8")
                plans = plan_slides(source)
                self.assertGreaterEqual(len(plans), 10)
                self.assertLessEqual(len(plans), 15)


if __name__ == "__main__":
    unittest.main()
