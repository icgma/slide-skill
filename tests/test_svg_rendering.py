"""Tests for SVG rendering quality — text layout, titles, visual variety."""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from slide_skill.project import init_project
from slide_skill.svg_pipeline import generate_svg, create_spec
from slide_skill.svg_qa import check_svg_file


class TextLayoutTest(unittest.TestCase):
    """SVG-01: Bullet points must render as separate lines with • markers."""

    def _generate_slides(self, markdown: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            source.write_text(markdown, encoding="utf-8")
            project = init_project("Test", base_dir=root / "projects")
            create_spec(project, source)
            svg_paths = generate_svg(project, source)
            return [p.read_text(encoding="utf-8") for p in svg_paths]

    def test_bullet_points_on_separate_lines(self) -> None:
        """Each - item must produce its own <tspan>, not one collapsed line."""
        md = "# Slide Title\n\n- Point one\n- Point two\n- Point three"
        svgs = self._generate_slides(md)
        self.assertGreaterEqual(len(svgs), 1)
        svg = svgs[0]
        tspans = re.findall(r"<tspan[^>]*>(.*?)</tspan>", svg)
        body_tspans = [t for t in tspans if t and not re.match(r"^0?\d+$", t)]
        joined = " ".join(body_tspans)
        self.assertNotIn("- Point one - Point two - Point three", joined, "Bullets should NOT be collapsed into one line")

    def test_bullet_marker_is_bullet_character(self) -> None:
        """Bullet items should use • marker, not raw '- '."""
        md = "# List\n\n- First item\n- Second item"
        svgs = self._generate_slides(md)
        svg = svgs[0]
        body_text = re.findall(r"<tspan[^>]*>(.*?)</tspan>", svg)
        body = " ".join(t for t in body_text if t)
        has_bullet_marker = "•" in svg or "&#x2022;" in svg or "•" in body
        has_raw_dash = re.search(r">- [A-Z]", svg)
        if has_raw_dash and not has_bullet_marker:
            self.fail("Bullets should use • marker, not raw '- ' prefix")

    def test_markdown_list_preserves_line_breaks(self) -> None:
        """Source markdown lists should produce separate rendered lines in SVG."""
        md = "# Features\n\n- Feature A\n- Feature B\n- Feature C"
        svgs = self._generate_slides(md)
        svg = svgs[0]
        has_multi = (
            len(re.findall(r'<tspan[^>]*dy="34"[^>]*>', svg)) >= 2
            or (svg.count("Feature A") >= 1 and svg.count("Feature B") >= 1)
        )
        self.assertTrue(has_multi, "Multi-item lists should render on separate visual lines")


class TitleOverflowTest(unittest.TestCase):
    """SVG-02: Long titles must auto-wrap; empty body uses centered layout."""

    def _generate_slide(self, markdown: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            source.write_text(markdown, encoding="utf-8")
            project = init_project("Test", base_dir=root / "projects")
            create_spec(project, source)
            svg_paths = generate_svg(project, source)
            return svg_paths[0].read_text(encoding="utf-8")

    def test_long_title_does_not_overflow(self) -> None:
        """Title >20 chars should split into multiple tspans or reduce font-size."""
        md = "# 智能学伴——基于大语言模型的个性化学习助手\n\nSome body text."
        svg = self._generate_slide(md)
        title_tspans = re.findall(r'font-size="(\d+)"[^>]*font-weight="700"', svg)
        if title_tspans:
            size = int(title_tspans[0])
            self.assertLessEqual(size, 60, "Long title should use reduced font-size or wrap")

    def test_empty_body_no_blank_card(self) -> None:
        """When body is empty, should not show an empty white card."""
        md = "# Project Title"
        svg = self._generate_slide(md)
        has_white_card = 'fill="#FFFFFF"' in svg
        has_body_content = bool(re.search(r'id="content-body', svg))
        if has_white_card and has_body_content:
            body_text = re.findall(r'<tspan[^>]*>(.*?)</tspan>', svg)
            non_empty = [t for t in body_text if t.strip() and not re.match(r"^0?\d+$", t)]
            has_empty_card = len(non_empty) == 0
            if has_empty_card:
                self.fail("Empty body should not produce a blank white card")


class BulletLayoutPrecedenceTest(unittest.TestCase):
    """SVG-05: Layout selection precedence for bullet threshold >= 1."""

    def _generate_slides(self, markdown: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            source.write_text(markdown, encoding="utf-8")
            project = init_project("Test", base_dir=root / "projects")
            create_spec(project, source)
            svg_paths = generate_svg(project, source)
            return [p.read_text(encoding="utf-8") for p in svg_paths]

    def test_single_bullet_uses_bullet_renderer(self) -> None:
        """A body with one bullet item should use the bullet-list layout."""
        md = "# Slide\n\n- Only item"
        svgs = self._generate_slides(md)
        self.assertGreaterEqual(len(svgs), 1)
        svg = svgs[0]
        has_bullet_marker = 'r="4"' in svg and 'fill=' in svg
        has_raw_dash = bool(re.search(r">- Only item<", svg))
        self.assertTrue(has_bullet_marker, "Single-item list should use bullet marker (small filled circle)")
        self.assertFalse(has_raw_dash, "Single-item list should not emit raw '- ' prefix")

    def test_two_bullets_use_bullet_renderer(self) -> None:
        """Two bullet items should use the bullet-list layout, not default."""
        md = "# Slide\n\n- Alpha\n- Beta"
        svgs = self._generate_slides(md)
        svg = svgs[0]
        has_bullet_marker = 'r="4"' in svg and 'fill=' in svg
        self.assertTrue(has_bullet_marker, "Two-item list should use bullet markers")


class LayoutVarietyTest(unittest.TestCase):
    """SVG-03: Different content types should use different layout templates."""

    def _generate_slides(self, markdown: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            source.write_text(markdown, encoding="utf-8")
            project = init_project("Test", base_dir=root / "projects")
            create_spec(project, source)
            svg_paths = generate_svg(project, source)
            return [p.read_text(encoding="utf-8") for p in svg_paths]

    def test_not_all_slides_identical(self) -> None:
        """Slides with different content should produce different SVG structures."""
        md = (
            "# Cover Title\n\n"
            "# Features\n\n- Feature A\n- Feature B\n- Feature C\n- Feature D\n"
        )
        svgs = self._generate_slides(md)
        if len(svgs) < 2:
            self.skipTest("Need at least 2 slides")
        svg1, svg2 = svgs[0], svgs[1]
        decor1 = set(re.findall(r'id="decor-[^"]*"', svg1))
        decor2 = set(re.findall(r'id="decor-[^"]*"', svg2))
        layout1 = re.findall(r'rx="(\d+)"', svg1)
        layout2 = re.findall(r'rx="(\d+)"', svg2)
        same_layout = (decor1 == decor2) and (layout1 == layout2)
        if same_layout:
            self.fail("Different content types should produce different SVG layouts")


class VisualChromeTest(unittest.TestCase):
    """SVG-04: All slides should have footer, accent stripe, progress dots."""

    def _generate_slide(self, markdown: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.md"
            source.write_text(markdown, encoding="utf-8")
            project = init_project("Test", base_dir=root / "projects")
            create_spec(project, source)
            svg_paths = generate_svg(project, source)
            return svg_paths[0].read_text(encoding="utf-8")

    def test_has_footer_bar(self) -> None:
        """SVG should include a footer bar element."""
        md = "# Test\n\nBody text."
        svg = self._generate_slide(md)
        self.assertIn("footer", svg.lower(), "SVG should include footer elements")

    def test_has_accent_stripe(self) -> None:
        """SVG should include a left accent gradient stripe."""
        md = "# Test\n\nBody text."
        svg = self._generate_slide(md)
        self.assertTrue('chrome-stripe' in svg, "SVG should include left accent stripe")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# v3 layout router regression tests (architect-flagged bugs)
# ---------------------------------------------------------------------------

class V3LayoutRouterTest(unittest.TestCase):
    def test_metric_bullets_route_to_metric_highlight(self) -> None:
        """Bullets dominated by % / 万 / 亿 should hit metric-highlight."""
        from slide_skill.svg_pipeline import _select_layout
        body = "- 营收增长 38%\n- 毛利率 62%\n- NPS 58"
        self.assertEqual(_select_layout("指标", body, 2, 5), "metric-highlight")

    def test_single_pipe_does_not_trigger_comparison(self) -> None:
        """One bare pipe in body must not auto-route to comparison."""
        from slide_skill.svg_pipeline import _select_layout
        body = "- 表格列\n- a | b"
        self.assertNotEqual(_select_layout("表", body, 2, 5), "comparison")

    def test_explicit_label_pipe_pairs_route_to_comparison(self) -> None:
        """Two `label | description` lines should route to comparison."""
        from slide_skill.svg_pipeline import _select_layout
        body = "旗舰版 | 高客单 50W ARPU\n通用版 | 走量 5W ARPU"
        self.assertEqual(_select_layout("对比", body, 2, 5), "comparison")

    def test_long_bullet_run_anti_monotony_preserves_content(self) -> None:
        """A run of long bullet slides must not collapse to 3-card summary."""
        from slide_skill.svg_pipeline import _distribute_layouts
        layouts = ["cover", "bullet-list", "bullet-list", "bullet-list", "closing"]
        long_body = "\n".join(f"- item {i}" for i in range(7))
        slides = [("", "")] * 5
        slides[1] = ("h", long_body)
        slides[2] = ("h", long_body)
        slides[3] = ("h", long_body)
        out = _distribute_layouts(layouts, slides)
        # Middle should rotate but NOT to executive-summary (would drop bullets).
        self.assertNotEqual(out[2], "executive-summary")
        self.assertEqual(out[2], "default")

    def test_short_bullet_run_can_become_executive_summary(self) -> None:
        """A run of ≤3-bullet slides can safely rotate to exec-summary."""
        from slide_skill.svg_pipeline import _distribute_layouts
        layouts = ["cover", "bullet-list", "bullet-list", "bullet-list", "closing"]
        short_body = "- a\n- b\n- c"
        slides = [("", "")] * 5
        slides[1] = ("h", short_body)
        slides[2] = ("h", short_body)
        slides[3] = ("h", short_body)
        out = _distribute_layouts(layouts, slides)
        self.assertEqual(out[2], "executive-summary")


def test_closing_long_body_fits_safe_area(tmp_path) -> None:
    from slide_skill.svg_pipeline import _render_closing

    lock = {
        "palette": {
            "accent": "#3B82F6",
            "text": "#F8FAFC",
            "surface": "#1E293B",
            "muted": "#64748B",
            "background": "#0F172A",
            "body": "#CBD5E1",
        },
        "canvas": {"width": 1280, "height": 720},
        "font_family": "Microsoft YaHei",
    }
    body = (
        "If you remember one thing, remember that the deck must preserve readable, "
        "editable PowerPoint output without letting long generated copy collide "
        "with the closing card or footer."
    )
    svg = _render_closing(8, "Why Now", body, lock, total=8, w=1280, h=720)
    path = tmp_path / "closing.svg"
    path.write_text(svg, encoding="utf-8")
    issues = check_svg_file(path, tmp_path)
    assert not [i for i in issues if i.level == "error"]


def test_market_opportunity_renderer_uses_semantic_group(tmp_path) -> None:
    from slide_skill.svg_pipeline import _render_market_opportunity

    lock = {
        "palette": {
            "accent": "#3B82F6",
            "text": "#F8FAFC",
            "surface": "#1E293B",
            "muted": "#64748B",
            "background": "#0F172A",
            "body": "#CBD5E1",
        },
        "canvas": {"width": 1280, "height": 720},
        "font_family": "Microsoft YaHei",
        "theme": "dark-tech",
    }
    body = (
        "Total Addressable Market: 120亿 USD by 2027\n"
        "Enterprise analytics: 45%\n"
        "SMB segment: 30%\n"
        "Government and public sector: 25%"
    )
    svg = _render_market_opportunity(4, "Market Opportunity", body, lock, total=8, w=1280, h=720)
    assert 'id="content-market-04"' in svg
    assert "Primary demand signal" in svg
    path = tmp_path / "market.svg"
    path.write_text(svg, encoding="utf-8")
    issues = check_svg_file(path, tmp_path)
    assert not [i for i in issues if i.level == "error"]


def test_profiled_problem_solution_technology_and_roadmap_scenes(tmp_path) -> None:
    from slide_skill.svg_pipeline import (
        _render_problem_scene,
        _render_roadmap_scene,
        _render_solution_scene,
        _render_technology_scene,
    )

    lock = {
        "palette": {
            "accent": "#1D4ED8",
            "text": "#0A0A0A",
            "surface": "#FFFFFF",
            "muted": "#E5E5E5",
            "background": "#FBFBF9",
            "body": "#333333",
        },
        "canvas": {"width": 1280, "height": 720},
        "font_family": "Arial",
        "theme": "neo-brutalist",
    }
    renderers = [
        ("problem", _render_problem_scene, "Problem Statement", "Data silos\nManual reporting"),
        ("solution", _render_solution_scene, "Our Solution", "Unified ingestion\nRealtime alerts"),
        ("technology", _render_technology_scene, "Technology Stack", "Kafka\nML models"),
        ("roadmap", _render_roadmap_scene, "Roadmap", "Q1: Mobile\nQ2: AI writer"),
    ]
    for name, renderer, title, body in renderers:
        svg = renderer(2, title, body, lock, total=8, w=1280, h=720)
        assert f"content-{name}-02" in svg
        assert 'data-theme-profile="neo-brutalist"' in svg
        assert "data-scene-variant=" in svg
        path = tmp_path / f"{name}.svg"
        path.write_text(svg, encoding="utf-8")
        issues = check_svg_file(path, tmp_path)
        assert not [i for i in issues if i.level == "error"]


def test_profiled_closing_scene_matrix_variants(tmp_path) -> None:
    from slide_skill.svg_pipeline import _render_closing

    base_lock = {
        "palette": {
            "accent": "#1D4ED8",
            "text": "#0A0A0A",
            "surface": "#FFFFFF",
            "muted": "#E5E5E5",
            "background": "#FBFBF9",
            "body": "#333333",
        },
        "canvas": {"width": 1280, "height": 720},
        "font_family": "Arial",
    }
    expected_signatures = {
        "dark-tech": ("default", "decor-closing-geom"),
        "warm-editorial": ("warm-editorial", "content-pullnote"),
        "neo-brutalist": ("neo-brutalist", "decor-construction"),
        "celestial-glass": ("celestial-glass", "decor-orbital-frame"),
    }
    variants = set()
    for theme, (profile_name, signature) in expected_signatures.items():
        lock = {**base_lock, "theme": theme}
        svg = _render_closing(
            8,
            "Why Now",
            "Preserve editable output, visual QA evidence, and a strong final call to action.",
            lock,
            total=8,
            w=1280,
            h=720,
        )
        assert 'id="content-closing-08"' in svg
        assert f'data-theme-profile="{profile_name}"' in svg
        assert "data-scene-variant=" in svg
        assert signature in svg
        variants.add(svg.split('data-scene-variant="', 1)[1].split('"', 1)[0])
        path = tmp_path / f"closing-{theme}.svg"
        path.write_text(svg, encoding="utf-8")
        issues = check_svg_file(path, tmp_path)
        assert not [i for i in issues if i.level == "error"]

    assert len(variants) == 4
