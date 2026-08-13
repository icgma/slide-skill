"""Tests for Phase 44: SVG QA design-quality checks.

These tests verify the five new design-quality checkers:
1. Spec drift detection (colors and fonts)
2. Font safety (PPT-safe fallback)
3. Rhythm monotony warning
4. Layout variety warning
5. Image integration info
"""

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from slide_skill.svg_qa import (
    PPT_SAFE_FONTS,
    SvgIssue,
    _check_font_safety,
    _check_image_usage,
    _check_layout_variety,
    _check_rhythm_monotony,
    _check_spec_drift,
    _check_spec_polish,
    _check_text_contrast,
    _count_visual_elements,
    _extract_font_families,
    _extract_hex_colors,
    _extract_layout_signature,
    _parse_font_stack,
    check_project_svg,
    check_svg_file,
    write_svg_report,
)
from slide_skill.svg_pipeline import finalize_svg


def _make_svg(
    fill: str = "#3B82F6",
    font: str = "Arial, sans-serif",
    extra_elements: str = "",
    content_id: str = "content-body-01",
) -> str:
    return (
        '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">\n'
        '  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>\n'
        f'  <g id="chrome-stripe"><rect x="0" y="0" width="6" height="720" fill="{fill}"/></g>\n'
        f'  <g id="{content_id}">\n'
        f'    <text x="100" y="100" font-family="{font}" font-size="44" fill="{fill}">Test</text>\n'
        f"    {extra_elements}\n"
        "  </g>\n"
        '  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#1E293B"/></g>\n'
        "</svg>"
    )


def _parse(svg_str: str) -> ET.Element:
    return ET.fromstring(svg_str)


# ─── Helper tests ────────────────────────────────────────────────────

class TestHelpers:
    def test_extract_hex_colors(self):
        root = _parse(_make_svg(fill="#FF0000"))
        colors = _extract_hex_colors(root)
        assert "#FF0000" in colors
        assert "#0F172A" in colors  # background

    def test_extract_font_families(self):
        root = _parse(_make_svg(font="'Inter', Arial, sans-serif"))
        families = _extract_font_families(root)
        assert "'Inter', Arial, sans-serif" in families

    def test_parse_font_stack(self):
        result = _parse_font_stack("'Inter', Arial, sans-serif")
        assert result == ["inter", "arial", "sans-serif"]

    def test_count_visual_elements(self):
        root = _parse(_make_svg())
        count = _count_visual_elements(root)
        assert count >= 3  # rects + text

    def test_extract_layout_signature(self):
        root = _parse(_make_svg(content_id="content-body-01"))
        sig = _extract_layout_signature(root)
        assert "content-body" in sig


def test_finalize_svg_quality_blocks_design_warnings(tmp_path):
    project = tmp_path / "project"
    svg_dir = project / "svg_output"
    svg_dir.mkdir(parents=True)
    (project / "spec_lock.json").write_text(
        """{
  "palette": {
    "background": "#0F172A",
    "surface": "#1E293B",
    "text": "#F1F5F9",
    "body": "#94A3B8",
    "text_secondary": "#94A3B8",
    "text_tertiary": "#334155",
    "accent": "#3B82F6",
    "muted": "#334155"
  },
  "typography": {
    "title_family": "Arial",
    "body_family": "Arial, sans-serif",
    "emphasis_family": "Arial",
    "code_family": "Consolas, monospace"
  },
  "canvas": {"width": 1280, "height": 720}
}
""",
        encoding="utf-8",
    )
    (svg_dir / "slide_01.svg").write_text(
        '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">\n'
        '  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>\n'
        '  <g id="content-body-01"><text x="100" y="100" font-family="Arial" font-size="44" fill="#0F172A">Invisible title</text></g>\n'
        "</svg>\n",
        encoding="utf-8",
    )

    assert finalize_svg(project, quality=False)
    with pytest.raises(RuntimeError, match="Low text contrast"):
        finalize_svg(project, quality=True)


# ─── Spec drift detection ────────────────────────────────────────────

class TestSpecDrift:
    def _spec_lock(self):
        return {
            "palette": {
                "background": "#0F172A",
                "surface": "#1E293B",
                "text": "#F1F5F9",
                "body": "#94A3B8",
                "text_secondary": "#94A3B8",
                "text_tertiary": "#334155",
                "accent": "#3B82F6",
                "muted": "#334155",
            },
            "design_hints": (
                "Use linearGradient from #1E293B to #0F172A for card panel fills. "
                "Footer bar visible."
            ),
            "typography": {
                "title_family": "Arial",
                "body_family": "Arial, sans-serif",
                "emphasis_family": "Arial",
                "code_family": "Consolas, monospace",
            },
        }

    def test_no_drift_when_palette_matches(self):
        svg = _make_svg(fill="#3B82F6", font="Arial, sans-serif")
        root = _parse(svg)
        issues = _check_spec_drift(
            [(Path("slide_01.svg"), root)], self._spec_lock()
        )
        color_issues = [i for i in issues if "Color" in i.message]
        assert len(color_issues) == 0

    def test_drift_when_color_not_in_palette(self):
        svg = _make_svg(fill="#FF0000")
        root = _parse(svg)
        issues = _check_spec_drift(
            [(Path("slide_01.svg"), root)], self._spec_lock()
        )
        color_issues = [i for i in issues if "#FF0000" in i.message]
        assert len(color_issues) >= 1
        assert color_issues[0].level == "warning"

    def test_rhythm_derived_palette_colors_do_not_drift(self):
        svg = _make_svg(fill="#276EE1")
        root = _parse(svg)
        issues = _check_spec_drift(
            [(Path("slide_01.svg"), root)], self._spec_lock()
        )
        color_issues = [i for i in issues if "#276EE1" in i.message]
        assert color_issues == []

    def test_drift_when_font_not_in_spec(self):
        svg = _make_svg(font="CustomFont, serif")
        root = _parse(svg)
        issues = _check_spec_drift(
            [(Path("slide_01.svg"), root)], self._spec_lock()
        )
        font_issues = [i for i in issues if "Font" in i.message]
        assert len(font_issues) >= 1

    def test_spec_polish_warns_on_flat_content_card_when_gradient_required(self):
        svg = _make_svg(extra_elements='<rect x="100" y="180" width="500" height="260" fill="#1E293B"/>')
        root = _parse(svg)
        issues = _check_spec_polish(
            [(Path("slide_01.svg"), root)], self._spec_lock()
        )

        assert any("flat fill" in issue.message and issue.level == "warning" for issue in issues)

    def test_spec_polish_warns_on_low_contrast_footer_page_number(self):
        svg = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">\n'
            '  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>\n'
            '  <g id="content-body-01"><text x="100" y="100" font-family="Arial" font-size="44" fill="#F1F5F9">Test</text></g>\n'
            '  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#1E293B"/><text x="1240" y="710" font-family="Arial" font-size="12" fill="#334155" text-anchor="end">01 / 01</text></g>\n'
            "</svg>"
        )
        root = _parse(svg)
        issues = _check_spec_polish(
            [(Path("slide_01.svg"), root)], self._spec_lock()
        )

        assert any("footer page number uses low-contrast color" in issue.message for issue in issues)

    def test_spec_polish_warns_when_footer_progress_dots_missing(self):
        svg = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">\n'
            '  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>\n'
            '  <g id="content-body-01"><text x="100" y="100" font-family="Arial" font-size="44" fill="#F1F5F9">Test</text></g>\n'
            '  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#1E293B"/><text x="1240" y="710" font-family="Arial" font-size="12" fill="#94A3B8" text-anchor="end">01 / 01</text></g>\n'
            "</svg>"
        )
        spec = self._spec_lock()
        spec["design_hints"] += " Progress dots in accent color."
        root = _parse(svg)

        issues = _check_spec_polish([(Path("slide_01.svg"), root)], spec)

        assert any("footer is missing accent-colored progress dots" in issue.message for issue in issues)

    def test_spec_polish_accepts_footer_progress_dots(self):
        svg = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">\n'
            '  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>\n'
            '  <g id="content-body-01"><text x="100" y="100" font-family="Arial" font-size="44" fill="#F1F5F9">Test</text></g>\n'
            '  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#1E293B"/><circle cx="32" cy="704" r="4" fill="#3B82F6"/><text x="1240" y="710" font-family="Arial" font-size="12" fill="#94A3B8" text-anchor="end">01 / 01</text></g>\n'
            "</svg>"
        )
        spec = self._spec_lock()
        spec["design_hints"] += " Progress dots in accent color."
        root = _parse(svg)

        issues = _check_spec_polish([(Path("slide_01.svg"), root)], spec)

        assert not [issue for issue in issues if "progress dots" in issue.message]

    def test_spec_polish_warns_when_footer_progress_dots_overlap_page_number_region(self):
        svg = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">\n'
            '  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>\n'
            '  <g id="content-body-01"><text x="100" y="100" font-family="Arial" font-size="44" fill="#F1F5F9">Test</text></g>\n'
            '  <g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#1E293B"/><circle cx="1200" cy="704" r="4" fill="#3B82F6"/><circle cx="1212" cy="704" r="4" fill="#3B82F6"/><text x="1240" y="710" font-family="Arial" font-size="12" fill="#94A3B8" text-anchor="end">01 / 01</text></g>\n'
            "</svg>"
        )
        spec = self._spec_lock()
        spec["design_hints"] += " Progress dots in accent color."
        root = _parse(svg)

        issues = _check_spec_polish([(Path("slide_01.svg"), root)], spec)

        assert any("too close to the right-aligned page number" in issue.message for issue in issues)


# ─── Font safety ─────────────────────────────────────────────────────

class TestFontSafety:
    def test_safe_font_no_warning(self):
        svg = _make_svg(font="Arial, sans-serif")
        root = _parse(svg)
        issues = _check_font_safety([(Path("test.svg"), root)])
        assert len(issues) == 0

    def test_unsafe_font_with_safe_fallback_no_warning(self):
        svg = _make_svg(font="'MyCustomFont', Arial, sans-serif")
        root = _parse(svg)
        issues = _check_font_safety([(Path("test.svg"), root)])
        assert len(issues) == 0

    def test_unsafe_font_no_fallback_warns(self):
        svg = _make_svg(font="'MyCustomFont', 'AnotherCustom'")
        root = _parse(svg)
        issues = _check_font_safety([(Path("test.svg"), root)])
        assert len(issues) >= 1
        assert issues[0].level == "warning"
        assert "MyCustomFont" in issues[0].message.lower() or "mycustomfont" in issues[0].message.lower()


# ─── Rhythm monotony ─────────────────────────────────────────────────

class TestRhythmMonotony:
    def test_similar_density_warns(self):
        """All slides with similar element counts trigger a blocking warning."""
        svgs = []
        for i in range(5):
            svg = _make_svg(content_id=f"content-body-{i:02d}")
            svgs.append((Path(f"slide_{i+1:02d}.svg"), _parse(svg)))
        issues = _check_rhythm_monotony(svgs)
        assert len(issues) == 1
        # Change 2b: rhythm monotony is now warning-level (blocks in strict mode)
        # so flat, cookie-cutter decks cannot ship from the default path.
        assert issues[0].level == "warning"
        assert "density" in issues[0].message.lower()

    def test_varied_density_no_warning(self):
        """Slides with very different element counts should NOT trigger."""
        # Simple slide: few elements
        svg1 = _make_svg()
        # Complex slide: lots of elements
        extras = "\n".join(
            f'    <rect x="{50 + i * 30}" y="{200 + i * 20}" width="20" height="20" fill="#3B82F6"/>'
            for i in range(20)
        )
        svg2 = _make_svg(extra_elements=extras)
        svgs = [
            (Path("slide_01.svg"), _parse(svg1)),
            (Path("slide_02.svg"), _parse(svg2)),
            (Path("slide_03.svg"), _parse(svg1)),
        ]
        issues = _check_rhythm_monotony(svgs)
        assert len(issues) == 0


# ─── Layout variety ──────────────────────────────────────────────────

class TestLayoutVariety:
    def test_identical_layouts_trigger_warning(self):
        svgs = []
        for i in range(4):
            svg = _make_svg(content_id=f"content-body-{i+1:02d}")
            svgs.append((Path(f"slide_{i+1:02d}.svg"), _parse(svg)))
        issues = _check_layout_variety(svgs)
        assert len(issues) >= 1
        # Change 2b: 3+ identical layouts is now warning-level (blocks in strict
        # mode) so repetitive decks fail the default QA gate.
        assert issues[0].level == "warning"
        assert "identical" in issues[0].message.lower()

    def test_varied_layouts_no_info(self):
        svg1 = _make_svg(content_id="content-body-01")
        svg2 = _make_svg(content_id="content-metric-02")
        svg3 = _make_svg(content_id="content-left-03")
        svgs = [
            (Path("slide_01.svg"), _parse(svg1)),
            (Path("slide_02.svg"), _parse(svg2)),
            (Path("slide_03.svg"), _parse(svg3)),
        ]
        issues = _check_layout_variety(svgs)
        assert len(issues) == 0


# ─── Image usage ─────────────────────────────────────────────────────

class TestImageUsage:
    def test_no_images_triggers_info(self):
        svgs = []
        for i in range(5):
            svg = _make_svg(content_id=f"content-body-{i+1:02d}")
            svgs.append((Path(f"slide_{i+1:02d}.svg"), _parse(svg)))
        issues = _check_image_usage(svgs)
        assert len(issues) == 1
        assert issues[0].level == "info"
        assert "imagery" in issues[0].message.lower()

    def test_with_images_no_info(self):
        img = '<image href="photo.jpg" x="0" y="0" width="640" height="360" preserveAspectRatio="xMidYMid slice"/>'
        svgs = []
        for i in range(5):
            svg = _make_svg(content_id=f"content-body-{i+1:02d}", extra_elements=img)
            svgs.append((Path(f"slide_{i+1:02d}.svg"), _parse(svg)))
        issues = _check_image_usage(svgs)
        assert len(issues) == 0


# ─── Text contrast (Change 3a) ──────────────────────────────────────

class TestTextContrast:
    """Verify the general text-contrast checker catches the AI-path equivalent
    of the contrast bug fixed for the deterministic renderer in 43f9bca."""

    def _spec_lock(self):
        return {
            "palette": {
                "background": "#0F172A",
                "surface": "#1E293B",
                "text": "#F1F5F9",
                "body": "#94A3B8",
                "accent": "#3B82F6",
                "muted": "#334155",
            },
        }

    def test_low_contrast_body_text_warns(self):
        # #334155 (dark slate) on #0F172A (darker slate) ≈ 1.7:1 — unreadable.
        svg = _make_svg(fill="#334155")
        # Force a small font size so the body threshold (4.5) applies.
        svg = svg.replace('font-size="44"', 'font-size="20"')
        issues = _check_text_contrast(
            [(Path("slide_01.svg"), _parse(svg))], self._spec_lock()
        )
        contrast_issues = [i for i in issues if "Low text contrast" in i.message]
        assert len(contrast_issues) >= 1
        assert contrast_issues[0].level == "warning"
        assert "#334155" in contrast_issues[0].message

    def test_high_contrast_body_text_passes(self):
        # #94A3B8 (light slate) on #0F172A ≈ 6:1 — readable body color.
        svg = _make_svg(fill="#94A3B8")
        svg = svg.replace('font-size="44"', 'font-size="20"')
        issues = _check_text_contrast(
            [(Path("slide_01.svg"), _parse(svg))], self._spec_lock()
        )
        contrast_issues = [i for i in issues if "Low text contrast" in i.message]
        assert contrast_issues == []

    def test_large_title_uses_lower_threshold(self):
        # #94A3B8 on #0F172A ≈ 6:1 passes both thresholds; instead test that a
        # medium-contrast title (large font) is held to the 3.0 bar, not 4.5.
        # #475569 on #0F172A ≈ 2.4:1 — fails even the large-text threshold.
        svg = _make_svg(fill="#475569")
        # font-size stays at 44 (large) → threshold is 3.0
        issues = _check_text_contrast(
            [(Path("slide_01.svg"), _parse(svg))], self._spec_lock()
        )
        contrast_issues = [i for i in issues if "Low text contrast" in i.message]
        assert len(contrast_issues) >= 1
        assert "large/title" in contrast_issues[0].message

    def test_footer_text_skipped(self):
        # Footer page-number contrast is owned by _footer_contrast_issue; the
        # general checker must not double-report it.
        svg = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            '<g id="chrome-footer"><rect x="0" y="688" width="1280" height="32" fill="#1E293B"/>'
            '<text x="1240" y="710" font-size="12" fill="#334155" text-anchor="end">01 / 01</text></g>'
            "</svg>"
        )
        issues = _check_text_contrast(
            [(Path("slide_01.svg"), _parse(svg))], self._spec_lock()
        )
        contrast_issues = [i for i in issues if "Low text contrast" in i.message]
        assert contrast_issues == []

    def test_text_on_surface_uses_surface_background(self):
        # Body text in a low-contrast color sitting on a surface <rect> should
        # be evaluated against the surface, not the canvas background.
        svg = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            '<g id="content-body-01">'
            '<rect x="80" y="80" width="500" height="300" fill="#1E293B"/>'
            # #1E293B text on #1E293B surface = 1:1, clearly unreadable
            '<text x="100" y="120" font-size="22" fill="#1E293B">Invisible text on card</text>'
            "</g></svg>"
        )
        issues = _check_text_contrast(
            [(Path("slide_01.svg"), _parse(svg))], self._spec_lock()
        )
        contrast_issues = [i for i in issues if "Low text contrast" in i.message]
        assert len(contrast_issues) >= 1

    def test_text_on_opaque_circle_uses_circle_background(self):
        svg = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            '<g id="content-badge-01">'
            '<circle cx="100" cy="100" r="20" fill="#3B82F6"/>'
            '<text x="100" y="105" font-size="20" fill="#0F172A" text-anchor="middle">01</text>'
            "</g></svg>"
        )
        issues = _check_text_contrast(
            [(Path("slide_01.svg"), _parse(svg))], self._spec_lock()
        )
        contrast_issues = [i for i in issues if "Low text contrast" in i.message]
        assert contrast_issues == []


class TestAccentTintContrast:
    """Phase 2: alpha-aware contrast for the ``accent_tint`` derived color.

    ``accent_tint`` is the palette's accent at ~12% opacity, written as an
    8-digit ``#RRGGBBAA`` hex (e.g. ``#3B82F620``). Before this fix the
    checker stripped the alpha byte, so a tint read as the full-strength
    accent — causing two opposite defects:

      * **false positives**: legible text on a pale tint rect was flagged
        as 1.00:1 (accent-on-accent), because the tint background was
        normalized to the opaque accent;
      * **false negatives**: body text painted *with* the tint was judged
        as the vivid accent and silently approved, even though it is
        nearly invisible.

    These tests pin both corrected behaviors.
    """

    def _spec_lock(self):
        # Real-world palette shape (mirrors projects/ai-anthropic-ai).
        return {
            "palette": {
                "background": "#FFFFFF",
                "surface": "#F8FAFC",
                "text": "#1A1A2E",
                "body": "#64748B",
                "accent": "#3B82F6",
                "accent_tint": "#3B82F620",
                "muted": "#E2E8F0",
                "border": "#ECF2FA",
            }
        }

    def test_text_on_tint_rect_not_false_positive(self):
        # Dark text on a pale accent_tint rect is legible: the tint over
        # white reads as ~#E6EFFE, so contrast is high. Before the fix this
        # was wrongly flagged as 1.00:1 (tint bg normalized to full accent).
        svg = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/></g>'
            '<g id="content-body-01">'
            '<rect x="80" y="100" width="400" height="200" fill="#3B82F620"/>'
            '<text x="100" y="150" font-size="20" fill="#1A1A2E">Real body text on tint</text>'
            "</g></svg>"
        )
        issues = _check_text_contrast(
            [(Path("slide_01.svg"), _parse(svg))], self._spec_lock()
        )
        contrast_issues = [i for i in issues if "Low text contrast" in i.message]
        assert contrast_issues == []

    def test_tinted_body_text_is_flagged(self):
        # Body text painted with the tint itself is nearly invisible and
        # must be flagged. Before the fix the alpha was stripped and the
        # text read as the vivid accent, so it was silently approved.
        svg = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/></g>'
            '<g id="content-body-01">'
            '<text x="100" y="150" font-size="20" fill="#3B82F620">Invisible tinted body</text>'
            "</g></svg>"
        )
        issues = _check_text_contrast(
            [(Path("slide_01.svg"), _parse(svg))], self._spec_lock()
        )
        contrast_issues = [i for i in issues if "Low text contrast" in i.message]
        assert len(contrast_issues) == 1
        # The reported color should be the effective composited color, not
        # the raw paint, so the author understands the real problem.
        assert "translucent" in contrast_issues[0].message

    def test_tinted_text_on_tint_rect_still_flagged(self):
        # Tint-on-tint is the genuinely unreadable case and must remain
        # flagged after compositing both sides.
        svg = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/></g>'
            '<g id="content-body-01">'
            '<rect x="80" y="100" width="400" height="200" fill="#3B82F620"/>'
            '<text x="100" y="150" font-size="20" fill="#3B82F620">Tint on tint</text>'
            "</g></svg>"
        )
        issues = _check_text_contrast(
            [(Path("slide_01.svg"), _parse(svg))], self._spec_lock()
        )
        contrast_issues = [i for i in issues if "Low text contrast" in i.message]
        assert len(contrast_issues) >= 1


# ─── Report output ───────────────────────────────────────────────────

class TestReportOutput:
    def test_report_groups_by_severity(self, tmp_path):
        # Create a project with SVGs
        svg_dir = tmp_path / "svg_output"
        svg_dir.mkdir()
        svg = _make_svg(fill="#FF0000")  # Off-palette color
        (svg_dir / "slide_01.svg").write_text(svg, encoding="utf-8")
        (svg_dir / "slide_02.svg").write_text(svg, encoding="utf-8")

        # Create a fake spec_lock.json
        import json
        lock = {
            "palette": {"accent": "#3B82F6", "background": "#0F172A"},
            "typography": {"title_family": "Arial", "body_family": "Arial"},
        }
        (tmp_path / "spec_lock.json").write_text(
            json.dumps(lock), encoding="utf-8"
        )

        report = write_svg_report(tmp_path, quality=True)
        content = report.read_text(encoding="utf-8")
        assert "Warnings" in content or "Info" in content
        assert "Errors" in content or "✅" in content


class TestTextOverflowGate:
    def test_canvas_text_overflow_is_error(self, tmp_path):
        svg = _make_svg(
            extra_elements='<text x="1260" y="120" font-family="Arial" font-size="44">OverflowingText</text>'
        )
        path = tmp_path / "overflow.svg"
        path.write_text(svg, encoding="utf-8")

        issues = check_svg_file(path, tmp_path)
        assert any(i.level == "error" and "right edge" in i.message for i in issues)

    def test_unwrapped_cjk_text_overflow_is_error(self, tmp_path):
        svg = _make_svg(
            extra_elements='<text x="740" y="448" font-family="Arial" font-size="24">动态类型提升入门效率，但需要通过测试减少类型错误</text>'
        )
        path = tmp_path / "cjk-overflow.svg"
        path.write_text(svg, encoding="utf-8")

        issues = check_svg_file(path, tmp_path)
        assert any(i.level == "error" and "right edge" in i.message for i in issues)

    def test_translated_text_overflow_is_error(self, tmp_path):
        svg = _make_svg(
            extra_elements=(
                '<g transform="translate(720, 340)">'
                '<text x="24" y="8" font-family="Arial" font-size="24">动态类型提升入门效率，但需要通过测试减少类型错误</text>'
                '</g>'
            )
        )
        path = tmp_path / "translated-overflow.svg"
        path.write_text(svg, encoding="utf-8")

        issues = check_svg_file(path, tmp_path)
        assert any(i.level == "error" and "right edge" in i.message for i in issues)

    def test_right_aligned_footer_text_uses_anchor(self, tmp_path):
        svg = _make_svg(
            extra_elements='<text x="1200" y="705" font-family="Arial" font-size="14" text-anchor="end">02 / 10</text>'
        )
        path = tmp_path / "anchored-footer.svg"
        path.write_text(svg, encoding="utf-8")

        issues = check_svg_file(path, tmp_path)
        assert not [i for i in issues if i.level == "error"]

    def test_fit_box_text_overflow_is_error(self, tmp_path):
        svg = _make_svg(
            extra_elements=(
                '<text x="200" y="160" font-family="Arial" font-size="42" '
                'data-fit-box="100,100,120,38">This text cannot fit inside the declared box</text>'
            )
        )
        path = tmp_path / "fitbox-overflow.svg"
        path.write_text(svg, encoding="utf-8")

        issues = check_svg_file(path, tmp_path)
        assert any(i.level == "error" and "fit box" in i.message for i in issues)


# ─── tspan dx horizontal flow (QA-01, REDESIGN_v5 F.3) ──────────────

class TestTspanDxFlow:
    """Horizontal <tspan dx> segments inside one <text> are one flowing
    line. The static QA used to collapse them all onto the parent x,
    which reported 11 phantom "text overlap" warnings on a healthy
    timeline slide (REDESIGN_v5 F.3) and pushed it into repair loops."""

    def _check(self, extra_elements: str, tmp_path):
        svg = _make_svg(extra_elements=extra_elements)
        path = tmp_path / "slide.svg"
        path.write_text(svg, encoding="utf-8")
        return check_svg_file(path, tmp_path)

    def test_dx_segments_in_one_text_report_no_overlap(self, tmp_path):
        # Benchmark fixture reproducing the REDESIGN_v5 timeline failure
        # shape: one <text> flowing label + value + unit via dx offsets,
        # plus a second unrelated <text> elsewhere on the slide.
        extra = (
            '<text x="140" y="400" font-family="Arial" font-size="20" fill="#F1F5F9">'
            '<tspan font-weight="700">2019</tspan>'
            '<tspan dx="12">Series A funding closed</tspan>'
            '<tspan dx="12" font-weight="700">$12M</tspan>'
            "</text>"
            '<text x="140" y="560" font-family="Arial" font-size="20" fill="#94A3B8">Unrelated caption line</text>'
        )
        issues = self._check(extra, tmp_path)
        assert [i for i in issues if "Text overlap" in i.message] == []

    def test_two_stacked_texts_still_report_overlap(self, tmp_path):
        # True-positive control: two SEPARATE <text> elements genuinely
        # stacked on nearly the same coordinates must still warn.
        extra = (
            '<text x="300" y="400" font-family="Arial" font-size="24" fill="#F1F5F9">Genuine overlap line one</text>'
            '<text x="308" y="404" font-family="Arial" font-size="24" fill="#F1F5F9">Second text stacked on top</text>'
        )
        issues = self._check(extra, tmp_path)
        assert any("Text overlap" in i.message for i in issues)

    def test_dx_shifted_segment_extends_box_into_real_overlap(self, tmp_path):
        # dx must participate in the emitted box x-range: the second
        # segment is pushed far right by dx, into a slot occupied by an
        # unrelated <text>. Without dx-aware geometry the box would end
        # near x=290 and this genuine collision would be missed.
        extra = (
            '<text x="100" y="300" font-family="Arial" font-size="20" fill="#F1F5F9">'
            "<tspan>Alpha</tspan>"
            '<tspan dx="300">Beta segment text</tspan>'
            "</text>"
            '<text x="480" y="300" font-family="Arial" font-size="20" fill="#F1F5F9">Occupied slot text</text>'
        )
        issues = self._check(extra, tmp_path)
        overlaps = [i for i in issues if "Text overlap" in i.message]
        assert any("Occupied" in i.message for i in overlaps)

    def test_wrapped_tspans_with_x_dy_still_measured_per_row(self, tmp_path):
        # Vertical wrap regression guard: two wrap rows (x + dy) inside
        # one card must keep per-row boxes — the joined-width false
        # positive fixed earlier must not come back with the cursor model.
        extra = (
            '<text x="100" y="300" font-family="Arial" font-size="20" fill="#F1F5F9">'
            '<tspan x="100" dy="0">First wrapped row of text</tspan>'
            '<tspan x="100" dy="28">Second wrapped row here</tspan>'
            "</text>"
            '<text x="480" y="300" font-family="Arial" font-size="20" fill="#94A3B8">Right neighbour card text</text>'
        )
        issues = self._check(extra, tmp_path)
        assert [i for i in issues if "Text overlap" in i.message] == []


# ─── Ghost element detection (QA-04) ────────────────────────────────

def _ghost_errors(issues):
    return [i for i in issues if i.level == "error" and "Ghost element" in i.message]


class TestGhostElementErrors:
    """svg_qa must ERROR on invisible ghost markup: empty text and
    fully-transparent drawables pad structure without pixels."""

    def _check(self, extra_elements: str, tmp_path):
        svg = _make_svg(extra_elements=extra_elements)
        path = tmp_path / "slide.svg"
        path.write_text(svg, encoding="utf-8")
        return check_svg_file(path, tmp_path)

    def test_empty_text_element_is_error(self, tmp_path):
        issues = self._check('<text x="600" y="500" font-size="14"> </text>', tmp_path)
        ghosts = _ghost_errors(issues)
        assert len(ghosts) == 1
        assert "empty <text>" in ghosts[0].message

    def test_empty_tspan_inside_real_text_is_error(self, tmp_path):
        extra = (
            '<text x="600" y="500" font-size="14">Real content'
            '<tspan x="600" dy="20"></tspan></text>'
        )
        ghosts = _ghost_errors(self._check(extra, tmp_path))
        assert len(ghosts) == 1
        assert "empty <tspan>" in ghosts[0].message

    def test_opacity_zero_drawable_is_error(self, tmp_path):
        extra = '<circle cx="200" cy="500" r="4" fill="#3B82F6" opacity="0"/>'
        ghosts = _ghost_errors(self._check(extra, tmp_path))
        assert len(ghosts) == 1
        assert "fully transparent" in ghosts[0].message

    def test_transparent_fill_without_stroke_is_error(self, tmp_path):
        extra = '<rect x="200" y="500" width="120" height="30" rx="15" fill="#3B82F6" fill-opacity="0"/>'
        ghosts = _ghost_errors(self._check(extra, tmp_path))
        assert len(ghosts) == 1
        assert "transparent fill" in ghosts[0].message

    def test_fill_none_without_stroke_is_error(self, tmp_path):
        extra = '<rect x="200" y="500" width="120" height="30" fill="none"/>'
        ghosts = _ghost_errors(self._check(extra, tmp_path))
        assert len(ghosts) == 1
        assert 'fill="none"' in ghosts[0].message

    def test_ancestor_group_opacity_zero_is_error(self, tmp_path):
        extra = '<g opacity="0"><rect x="200" y="500" width="40" height="40" fill="#3B82F6"/></g>'
        ghosts = _ghost_errors(self._check(extra, tmp_path))
        assert len(ghosts) == 1

    def test_fill_none_with_stroke_is_legitimate(self, tmp_path):
        extra = '<rect x="200" y="500" width="120" height="30" fill="none" stroke="#3B82F6" stroke-width="1.5"/>'
        assert _ghost_errors(self._check(extra, tmp_path)) == []

    def test_low_but_nonzero_opacity_is_legitimate(self, tmp_path):
        # Faint decor washes (opacity 0.04) still paint pixels — not ghosts.
        extra = '<rect x="200" y="500" width="120" height="30" fill="#3B82F6" opacity="0.04"/>'
        assert _ghost_errors(self._check(extra, tmp_path)) == []

    def test_defs_and_gradient_stops_are_exempt(self, tmp_path):
        extra = (
            "<defs>"
            '<linearGradient id="fade"><stop offset="0%" stop-color="#3B82F6"/>'
            '<stop offset="100%" stop-color="#3B82F6" stop-opacity="0"/></linearGradient>'
            '<clipPath id="clip"><rect x="0" y="0" width="10" height="10"/></clipPath>'
            "</defs>"
            '<rect x="200" y="500" width="120" height="30" fill="url(#fade)"/>'
        )
        assert _ghost_errors(self._check(extra, tmp_path)) == []

    def test_data_qa_allow_invisible_opts_out(self, tmp_path):
        extra = '<circle cx="200" cy="500" r="4" fill="#3B82F6" opacity="0" data-qa-allow="invisible"/>'
        assert _ghost_errors(self._check(extra, tmp_path)) == []

    def test_data_qa_allow_on_ancestor_opts_out_subtree(self, tmp_path):
        extra = (
            '<g data-qa-allow="invisible">'
            '<rect x="200" y="500" width="40" height="40" fill="#3B82F6" fill-opacity="0"/>'
            '<text x="200" y="560" font-size="12"></text>'
            "</g>"
        )
        assert _ghost_errors(self._check(extra, tmp_path)) == []


class TestPipelineEmitsNoGhosts:
    """The deterministic fast-mode renderer must not emit the ghost
    markup that QA now errors on (invisible bullet circle, empty-label
    transparent chip)."""

    _LOCK = {
        "palette": {
            "background": "#0F172A", "surface": "#1E293B", "text": "#F1F5F9",
            "body": "#94A3B8", "accent": "#3B82F6", "muted": "#64748B",
        },
        "font_family": "Arial, sans-serif",
        "canvas": {"width": 1280, "height": 720},
        "theme": "dark-tech",
    }

    def _assert_no_ghosts(self, svg: str, tmp_path):
        path = tmp_path / "unit.svg"
        path.write_text(svg, encoding="utf-8")
        issues = check_svg_file(path, tmp_path)
        assert _ghost_errors(issues) == []

    def test_render_default_has_no_invisible_bullet_circle(self, tmp_path):
        import re

        from slide_skill.svg_pipeline import _render_default

        body = "- Alpha point text\n- Beta point text"
        svg = _render_default(2, "Heading", body, self._LOCK, 5, 1280, 720)
        # Gradient stop-opacity="0" is a visible fade — only element/fill
        # opacity zero counts as a ghost.
        assert not re.search(r'(?<!stop-)opacity="0"', svg)
        self._assert_no_ghosts(svg, tmp_path)

    def test_render_executive_summary_has_no_empty_chip(self, tmp_path):
        from slide_skill.svg_pipeline import _render_executive_summary

        body = "- First point\n- Second point\n- Third point"
        svg = _render_executive_summary(2, "Heading", body, self._LOCK, 5, 1280, 720)
        assert 'fill-opacity="0"' not in svg
        self._assert_no_ghosts(svg, tmp_path)

    def test_fast_mode_deck_has_zero_ghost_errors(self, tmp_path):
        from slide_skill.project import init_project
        from slide_skill.svg_pipeline import create_spec, generate_svg

        source = tmp_path / "source.md"
        source.write_text(
            "# Deck Title\n\n"
            "# Overview\n\n- Point one detail\n- Point two detail\n- Point three detail\n\n"
            "# Summary\n\n- Wrap up line\n",
            encoding="utf-8",
        )
        project = init_project("GhostCheck", base_dir=tmp_path / "projects")
        create_spec(project, source)
        svg_paths = generate_svg(project, source)
        assert svg_paths
        for svg_path in svg_paths:
            issues = check_svg_file(svg_path, project)
            assert _ghost_errors(issues) == [], f"ghosts in {svg_path.name}"
