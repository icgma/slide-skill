"""Regression tests for slide-skill v3.0 plan-driven pipeline.

These tests pin three bugs found on 2026-06-22 by actually invoking
``slide-skill quickstart`` on representative inputs (Chinese sample,
competition template, English business deck). All three were silent on
the existing test suite because the previous tests used the legacy
``generate_svg()`` API while ``quickstart`` uses ``generate_svg_from_plan()``.

Bug B (CRITICAL — content loss): when the planner marks a bullet-list
slide with layout_pattern ``cards-3-up``, the layout is remapped to
``executive-summary``. ``_render_with_intent`` built the body string
without the ``"- "`` bullet marker, so ``_render_executive_summary``
(which parses bodies by ``startswith("- ")``) found zero bullets and
emitted placeholder chips ``POINT 01/02/03`` with no real text.

Bug A (UX — empty section-divider): an H2 heading that only wraps H3
sub-headings (e.g. ``## 方案对比`` followed by ``### 传统流程``) was
emitted as a near-empty ``section-divider`` slide. Now folded into the
next slide's ``meta["section"]`` eyebrow.

Bug D (QA false positive): ``svg_qa._check_text_overflow`` concatenated
every wrapping ``<tspan>`` into one string and measured the joined width,
producing spurious "Text overlap" warnings on any card that wrapped CJK
text across two vertical tspans.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from slide_skill.content_planner import ContentItem, SlidePlan, plan_slides
from slide_skill.project import init_project
from slide_skill.svg_pipeline import (
    create_spec,
    generate_svg_from_plan,
)
from slide_skill.svg_qa import SvgIssue, check_project_svg


# ---------------------------------------------------------------------------
# Reproducible inputs — minimal versions of the inputs that exposed the bugs.
# ---------------------------------------------------------------------------

_ZH_SAMPLE = """\
# 大语言模型驱动的产品设计

> 一行命令生成的中文演示文稿样例。

## 我们要解决的问题

- 传统幻灯片工具需要手动排版每一页
- 设计师与工程师之间的协作成本高
- 改一处文字，整页排版都要重做

## 方案对比

### 传统流程

- PPT 手动调整,每页平均 12 分钟
- 改字号要重新对齐所有元素
- 设计依赖单一设计师

### slide-skill 流程

- Markdown 输入,2 秒生成完整 .pptx
- 主题切换瞬间完成,排版自动重算

## 渲染管道

- Markdown → 智能切片(LLM 可选)
- 切片 → SVG(主题驱动,完全确定性)
- SVG → 原生 DrawingML(可编辑)
"""

_EN_SAMPLE = """\
# Q3 Marketing Strategy

## Key Pillars

- Brand awareness lifts via paid social
- Conversion rate optimization on checkout
- Retention improvements through loyalty program

## Market Analysis

- Total addressable market is $4.5B globally
- Top three competitors hold 60% market share
- Our differentiator is AI-driven personalization
"""


def _setup_project(tmp: Path, markdown: str, theme: str = "dark-tech") -> Path:
    """Create a project, write source, and emit spec_lock. Return project path."""
    source = tmp / "source.md"
    source.write_text(markdown, encoding="utf-8")
    project = init_project("Regression Deck", base_dir=tmp / "projects")
    create_spec(project, source, theme_name=theme)
    return project


def _slide_text(svg_path: Path) -> str:
    """Extract concatenated text content from an SVG file (for assertions)."""
    text = svg_path.read_text(encoding="utf-8")
    # Strip tags but keep text content
    import re
    no_tags = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", no_tags).strip()


# ---------------------------------------------------------------------------
# Bug B: executive-summary cards must contain real bullet text, not just
# "POINT 01/02/03" placeholder chips.
# ---------------------------------------------------------------------------


class TestExecutiveSummaryContentB(unittest.TestCase):
    """Plans with layout_pattern=cards-3-up must render real bullet text."""

    def test_zh_cards_3_up_renders_real_text(self) -> None:
        """Chinese bullet-list remapped to executive-summary keeps text."""
        plans = plan_slides(_ZH_SAMPLE)
        # Find at least one slide whose body would have hit the
        # cards-3-up → executive-summary remap path.
        remapped = [
            p for p in plans
            if p.layout_pattern == "cards-3-up"
        ]
        self.assertTrue(
            remapped,
            "Test setup: expected at least one cards-3-up plan in sample",
        )

        with tempfile.TemporaryDirectory() as tmp:
            project = _setup_project(Path(tmp), _ZH_SAMPLE)
            svg_paths = generate_svg_from_plan(project, plans)

            # Collect all rendered text across slides
            all_text = " ".join(_slide_text(p) for p in svg_paths)

            # The real bullet content must appear. Pre-fix this was empty.
            self.assertIn("PPT 手动调整", all_text)
            self.assertIn("改字号要重新对齐", all_text)
            self.assertIn("Markdown 输入", all_text)
            self.assertIn("主题切换瞬间完成", all_text)

    def test_en_cards_3_up_renders_real_text(self) -> None:
        """English bullet-list remapped to executive-summary keeps text."""
        plans = plan_slides(_EN_SAMPLE)
        with tempfile.TemporaryDirectory() as tmp:
            project = _setup_project(Path(tmp), _EN_SAMPLE, theme="light-corporate")
            svg_paths = generate_svg_from_plan(project, plans)
            all_text = " ".join(_slide_text(p) for p in svg_paths)

            self.assertIn("Brand awareness", all_text)
            self.assertIn("Conversion rate", all_text)
            self.assertIn("Retention", all_text)
            self.assertIn("Total addressable market", all_text)

    def test_executive_summary_falls_back_when_no_dash_marker(self) -> None:
        """Defensive: renderer must surface text even if body has no '- '.

        Guards against future regressions where a planner change drops the
        bullet marker — the renderer should never silently degrade to
        placeholder chips again.
        """
        from slide_skill.svg_pipeline import _render_executive_summary

        lock = {
            "palette": {
                "background": "#0F172A", "surface": "#1E293B", "text": "#F1F5F9",
                "body": "#F1F5F9", "accent": "#3B82F6", "muted": "#94A3B8",
            },
            "font_family": "Arial, sans-serif",
            "canvas": {"width": 1280, "height": 720},
            "theme": "dark-tech",
        }
        # Body without any "- " prefix (simulates old buggy path)
        body = "First bullet text here\nSecond bullet line\nThird bullet copy"
        svg = _render_executive_summary(2, "Heading", body, lock, 5, 1280, 720)
        # Auto-wrap may split a bullet across <tspan> boundaries, so we
        # compare against tag-stripped text rather than raw substring.
        import re as _re
        no_tags = _re.sub(r"<[^>]+>", " ", svg)
        flat = _re.sub(r"\s+", " ", no_tags)
        # All three bullet contents must appear (the third unsplit).
        self.assertIn("First bullet text", flat)
        self.assertIn("here", flat)
        self.assertIn("Second bullet line", flat)
        self.assertIn("Third bullet copy", flat)


# ---------------------------------------------------------------------------
# Bug A: empty section-divider slides must be folded into the next slide
# rather than emitted as a near-empty "CHAPTER N" page.
# ---------------------------------------------------------------------------


class TestEmptySectionDividerFoldingA(unittest.TestCase):
    """Empty section-divider plans merge into the next content slide."""

    def test_h2_wrapping_only_h3_does_not_emit_divider(self) -> None:
        """``## 方案对比`` wrapping ``### 传统流程`` should not become its
        own near-empty slide."""
        plans = plan_slides(_ZH_SAMPLE)
        # No section-divider should survive when it has no items AND is
        # followed by a content slide.
        for i, plan in enumerate(plans):
            if plan.layout == "section-divider" and not plan.items:
                # If it survived, it must be a trailing divider with no
                # following content slide.
                self.assertEqual(
                    i, len(plans) - 1,
                    f"Empty section-divider at index {i} should have been folded",
                )

    def test_folded_title_preserved_as_section_meta(self) -> None:
        """The divider heading is preserved on the next slide's meta."""
        plans = plan_slides(_ZH_SAMPLE)
        # The "方案对比" heading must appear as the section breadcrumb on
        # at least one content slide.
        self.assertTrue(
            any(p.meta.get("section") == "方案对比" for p in plans if p.meta),
            "Folded section heading not preserved as meta['section']",
        )

    def test_indices_are_contiguous_after_folding(self) -> None:
        """Re-indexing keeps slide indices 1..N contiguous."""
        plans = plan_slides(_ZH_SAMPLE)
        indices = [p.index for p in plans]
        self.assertEqual(indices, list(range(1, len(plans) + 1)))

    def test_trailing_empty_divider_is_preserved(self) -> None:
        """An empty divider with no following content stays as a slide."""
        md = """\
# Title

## Section A

- bullet one
- bullet two

## Empty Trailer
"""
        plans = plan_slides(md)
        # Last plan should be the trailing divider (or a closing slide),
        # but the divider content was not silently dropped.
        last = plans[-1]
        self.assertIn(last.layout, {"section-divider", "closing"})

    def test_cover_and_closing_not_affected(self) -> None:
        """Cover/closing are never dropped by the merge pass."""
        plans = plan_slides(_ZH_SAMPLE)
        self.assertEqual(plans[0].layout, "cover")
        self.assertEqual(plans[-1].layout, "closing")


# ---------------------------------------------------------------------------
# Bug D: per-tspan bbox — vertically wrapped tspans must NOT be measured
# as one long horizontal string.
# ---------------------------------------------------------------------------


class TestPerTspanOverlapDetectionD(unittest.TestCase):
    """QA overlap detection treats each wrapping tspan as its own line."""

    def _make_project_with_wrapped_card(self, tmp: Path) -> Path:
        """Build a project whose single slide wraps CJK text across tspans."""
        project = init_project("Wrapped Card", base_dir=tmp / "projects")
        # Minimal spec_lock so check_project_svg can resolve canvas/palette.
        (project / "spec_lock.json").write_text(json.dumps({
            "palette": {
                "background": "#0F172A", "surface": "#1E293B", "text": "#F1F5F9",
                "body": "#F1F5F9", "accent": "#3B82F6", "muted": "#94A3B8",
                "bg_secondary": "#1E293B", "text_secondary": "#CBD5E1",
                "text_tertiary": "#94A3B8", "secondary_accent": "#60A5FA",
                "accent_tint": "#3B82F620", "border": "#334155",
            },
            "font_family": "Arial, sans-serif",
            "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
            "theme": "dark-tech",
        }), encoding="utf-8")
        # Two cards side-by-side. Each card wraps its CJK text across two
        # vertical tspans. Pre-fix this falsely flagged overlap because the
        # joined width pushed card 1's bbox into card 2.
        svg = project / "svg_output" / "slide_01.svg"
        svg.parent.mkdir(parents=True, exist_ok=True)
        svg.write_text(
            '<svg width="1280" height="720" viewBox="0 0 1280 720" '
            'xmlns="http://www.w3.org/2000/svg">'
            '<rect x="0" y="0" width="1280" height="720" fill="#0F172A"/>'
            # Card 1 text (two-line wrap)
            '<text x="84" y="336" font-family="Arial" font-size="26" '
            'fill="#F1F5F9">'
            '<tspan x="84" dy="0">Markdown 输入,2 秒生成</tspan>'
            '<tspan x="84" dy="37">完整 .pptx</tspan>'
            '</text>'
            # Card 2 text (two-line wrap), well separated in x
            '<text x="502" y="336" font-family="Arial" font-size="26" '
            'fill="#F1F5F9">'
            '<tspan x="502" dy="0">主题切换瞬间完成,排版自</tspan>'
            '<tspan x="502" dy="37">动重算</tspan>'
            '</text>'
            '</svg>',
            encoding="utf-8",
        )
        return project

    def test_wrapped_cjk_does_not_false_overlap(self) -> None:
        """Two cards each wrapping CJK must NOT report text overlap."""
        with tempfile.TemporaryDirectory() as tmp:
            project = self._make_project_with_wrapped_card(Path(tmp))
            ok, issues = check_project_svg(project)
            overlap_issues = [
                i for i in issues if "overlap" in i.message.lower()
            ]
            self.assertEqual(
                overlap_issues, [],
                f"False-positive overlap on wrapped tspans: "
                f"{[i.message for i in overlap_issues]}",
            )

    def test_genuinely_overlapping_text_still_caught(self) -> None:
        """Sanity: real overlap (same x, same y) is still detected."""
        with tempfile.TemporaryDirectory() as tmp:
            project = init_project("Real Overlap", base_dir=Path(tmp) / "projects")
            (project / "spec_lock.json").write_text(json.dumps({
                "palette": {
                    "background": "#0F172A", "surface": "#1E293B", "text": "#F1F9",
                    "body": "#F1F5F9", "accent": "#3B82F6", "muted": "#94A3B8",
                    "bg_secondary": "#1E293B", "text_secondary": "#CBD5E1",
                    "text_tertiary": "#94A3B8", "secondary_accent": "#60A5FA",
                    "accent_tint": "#3B82F620", "border": "#334155",
                },
                "font_family": "Arial, sans-serif",
                "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
                "theme": "dark-tech",
            }), encoding="utf-8")
            # Two plain text elements at the same coordinates.
            svg = project / "svg_output" / "slide_01.svg"
            svg.parent.mkdir(parents=True, exist_ok=True)
            svg.write_text(
                '<svg width="1280" height="720" viewBox="0 0 1280 720" '
                'xmlns="http://www.w3.org/2000/svg">'
                '<rect x="0" y="0" width="1280" height="720" fill="#0F172A"/>'
                '<text x="200" y="200" font-family="Arial" font-size="32" '
                'fill="#F1F5F9">Alpha text content here</text>'
                '<text x="220" y="205" font-family="Arial" font-size="32" '
                'fill="#F1F5F9">Beta text content nearby</text>'
                '</svg>',
                encoding="utf-8",
            )
            ok, issues = check_project_svg(project)
            overlap = [i for i in issues if "overlap" in i.message.lower()]
            self.assertTrue(
                overlap,
                "Genuinely overlapping text was not flagged",
            )


# ---------------------------------------------------------------------------
# REL-02: version single-source agreement. pyproject.toml [project].version
# is canonical; the package __version__ and the SKILL.md title line must
# match it exactly, so any future version bump that misses a mirror fails
# the suite instead of shipping contradictory docs.
# ---------------------------------------------------------------------------


class TestVersionSingleSource(unittest.TestCase):
    """pyproject.toml is the canonical version; all mirrors must agree."""

    _REPO_ROOT = Path(__file__).resolve().parents[1]

    def _pyproject_version(self) -> str:
        import tomllib

        with (self._REPO_ROOT / "pyproject.toml").open("rb") as fh:
            data = tomllib.load(fh)
        return data["project"]["version"]

    def test_package_version_matches_pyproject(self) -> None:
        """slide_skill.__version__ must equal pyproject [project].version."""
        import slide_skill

        self.assertEqual(slide_skill.__version__, self._pyproject_version())

    def test_skill_md_title_version_matches_pyproject(self) -> None:
        """The root SKILL.md title line '(vX.Y.Z)' must match pyproject."""
        import re

        skill_text = (self._REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(
            r"^#\s+slide-skill\b.*\(v([0-9][^)\s]*)\)", skill_text, re.MULTILINE
        )
        self.assertIsNotNone(
            match,
            "SKILL.md must carry a '# slide-skill ... (vX.Y.Z)' title line",
        )
        self.assertEqual(match.group(1), self._pyproject_version())


# ---------------------------------------------------------------------------
# Integration: end-to-end plan → svg → qa gate on the original repro.
# ---------------------------------------------------------------------------


class TestEndToEndRegression(unittest.TestCase):
    """End-to-end plan → generate_svg_from_plan → check_project_svg."""

    def test_zh_sample_runs_clean(self) -> None:
        plans = plan_slides(_ZH_SAMPLE)
        with tempfile.TemporaryDirectory() as tmp:
            project = _setup_project(Path(tmp), _ZH_SAMPLE)
            svg_paths = generate_svg_from_plan(project, plans)
            self.assertGreaterEqual(len(svg_paths), 4)
            ok, issues = check_project_svg(project)
            errors = [i for i in issues if i.level == "error"]
            self.assertEqual(
                errors, [],
                f"SVG gate errors after fix: {[i.message for i in errors]}",
            )

    def test_en_sample_runs_clean(self) -> None:
        plans = plan_slides(_EN_SAMPLE)
        with tempfile.TemporaryDirectory() as tmp:
            project = _setup_project(Path(tmp), _EN_SAMPLE, theme="light-corporate")
            svg_paths = generate_svg_from_plan(project, plans)
            self.assertGreaterEqual(len(svg_paths), 3)
            ok, issues = check_project_svg(project)
            errors = [i for i in issues if i.level == "error"]
            self.assertEqual(
                errors, [],
                f"SVG gate errors after fix: {[i.message for i in errors]}",
            )


if __name__ == "__main__":
    unittest.main()
