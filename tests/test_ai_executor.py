"""Tests for AI executor enhancements — Phase 47."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slide_skill.ai_executor import (
    _apply_validated_repair,
    _auto_wrap_overflowing_text,
    _auto_repair_low_contrast,
    _build_page_prompt,
    _build_layout_diversity_hint,
    _check_bullet_markers,
    _check_bullet_text_color,
    _check_content_fidelity,
    _check_layout_intent,
    _build_system_prompt,
    _extract_svg,
    _format_required_text_contract,
    _is_valid_svg,
    _layout_coordinate_guidance,
    _load_design_guide,
    _load_executor_brief,
    _load_visual_feedback,
    _load_reference_materials,
    _read_layout_signature,
    _repair_preserves_visible_text,
    _serialize_svg,
    _validate_svg_attempt,
    generate_svg_with_ai,
)
from slide_skill.content_planner import ContentItem, SlidePlan


def _valid_svg(slide_no: int = 1, total: int = 1, title: str = "Test Slide", body: str = "Hello") -> str:
    return f'''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background">
    <rect x="0" y="0" width="1280" height="720" fill="#0F172A"/>
  </g>
  <g id="content-title-{slide_no:02d}">
    <text x="96" y="120" font-family="Inter, sans-serif" font-size="44" fill="#F8FAFC">{title}</text>
  </g>
  <g id="content-body-{slide_no:02d}">
    <text x="96" y="190" font-family="Inter, sans-serif" font-size="24" fill="#94A3B8">{body}</text>
  </g>
  <g id="chrome-footer">
    <text x="1180" y="700" font-family="Inter, sans-serif" font-size="12" fill="#94A3B8" text-anchor="end">{slide_no:02d} / {total:02d}</text>
  </g>
</svg>'''


def _make_project(tmp_path):
    """Create a minimal project with spec_lock."""
    p = tmp_path / "ai-project"
    p.mkdir()
    for d in ("sources", "svg_output", "svg_final", "images", "notes", "exports", "backup", "qa"):
        (p / d).mkdir()
    (p / "project.json").write_text(json.dumps({
        "name": "ai-project",
        "format": "ppt169",
        "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
    }))
    (p / "spec_lock.json").write_text(json.dumps({
        "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
        "theme": "dark tech",
        "palette": {
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F8FAFC",
            "accent": "#3B82F6",
            # Real dark-tech roles: body is a readable slate (#94A3B8), muted is
            # the dark #334155 used for borders/decoration. The previous fixture
            # swapped these, which put unreadable body text on the dark canvas.
            "body": "#94A3B8",
            "muted": "#334155",
        },
        "font_family": "Inter, sans-serif",
    }))
    return p


def _make_plan(index=1, layout="cover", title="Test Slide"):
    return SlidePlan(
        index=index,
        layout=layout,
        title=title,
        items=[ContentItem(type="text", primary="Hello")],
        rhythm="anchor",
        visual_strategy="hero-statement",
    )


class TestSystemPrompt:

    def test_includes_design_guide(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "design_guide.md").write_text("# Design Guide\nUse bold colors.")
        guide = _load_design_guide(p)
        prompt = _build_system_prompt(
            {"palette": {"background": "#FFF"}, "font_family": "Arial"},
            1280, 720,
            design_guide=guide,
        )
        assert "Design Guide" in prompt
        assert "bold colors" in prompt

    def test_includes_references(self, tmp_path):
        p = _make_project(tmp_path)
        ref_dir = p / "references"
        ref_dir.mkdir()
        (ref_dir / "executor-base.md").write_text("Base rules: use gradients wisely.")
        (ref_dir / "shared-standards.md").write_text("Standards: no scripts.")
        refs = _load_reference_materials(p)
        prompt = _build_system_prompt(
            {"palette": {"background": "#FFF"}, "font_family": "Arial"},
            1280, 720,
            references=refs,
        )
        assert "executor-base.md" in prompt
        assert "shared-standards.md" in prompt
        assert "gradients wisely" in prompt

    def test_no_references_graceful(self, tmp_path):
        p = _make_project(tmp_path)
        refs = _load_reference_materials(p)
        assert refs == ""

    def test_extra_appended(self):
        prompt = _build_system_prompt(
            {"palette": {}, "font_family": "Arial"},
            1280, 720,
            extra="Custom rule: always use rounded corners.",
        )
        assert "rounded corners" in prompt


class TestPagePrompt:

    def test_includes_design_intent(self):
        plan = _make_plan()
        prompt = _build_page_prompt(
            plan, 3,
            {"palette": {"background": "#FFF", "accent": "#3B82F6"}, "font_family": "Arial"},
            "", 1280, 720, [],
        )
        assert "anchor" in prompt
        assert "hero-statement" in prompt
        assert "Test Slide" in prompt
        assert "Footer must show: 01 / 03" in prompt
        assert 'text-anchor="end"' in prompt
        assert "x <= 1240" in prompt

    def test_includes_planner_design_execution_contract(self):
        plan = _make_plan()
        plan.visual_strategy = "hero statement with diagonal accent rail"
        plan.layout_pattern = "large title left with compact proof card right"
        prompt = _build_page_prompt(
            plan, 3,
            {"palette": {"background": "#FFF", "accent": "#3B82F6"}, "font_family": "Arial"},
            "", 1280, 720, [],
        )
        assert "Planner Design Execution Contract" in prompt
        assert "hard layout requirements" in prompt
        assert "not inspiration" in prompt
        assert "Required visual device / hierarchy: hero statement with diagonal accent rail" in prompt
        assert "Required placement / structure: large title left with compact proof card right" in prompt
        assert "Do not replace this contract with a generic centered title or bullet template" in prompt
        assert "Safe-area baseline" in prompt
        assert "left region: x=80..600, y=112..648" in prompt
        assert "right region: x=680..1200, y=112..648" in prompt
        assert "48 px gutter" in prompt

    def test_includes_spec_polish_contract_for_gradient_cards_and_footer(self):
        plan = _make_plan(layout="bullet-list", title="Test Slide")
        spec_lock = {
            "palette": {
                "background": "#0F172A",
                "surface": "#1E293B",
                "text": "#F8FAFC",
                "text_secondary": "#94A3B8",
                "muted": "#334155",
            },
            "font_family": "Aptos, Arial, sans-serif",
            "design_hints": "Use linearGradient from #1E293B to #0F172A for card panel fills. Footer bar visible.",
        }

        prompt = _build_page_prompt(
            plan, 1, spec_lock, "", 1280, 720, [],
            spec_lock_text="Footer bar and card panels must follow locked theme.",
        )

        assert "Spec Polish Contract" in prompt
        assert "define a `<linearGradient>`" in prompt
        assert "do not use a flat `#1E293B` card fill" in prompt
        assert "Footer/page-number text must be readable" in prompt
        assert "`#94A3B8`" in prompt

    def test_includes_spec_polish_contract_for_footer_progress_dots(self):
        plan = _make_plan(layout="bullet-list", title="Test Slide")
        spec_lock = {
            "palette": {
                "background": "#0F172A",
                "surface": "#1E293B",
                "text": "#F8FAFC",
                "accent": "#3B82F6",
                "text_secondary": "#94A3B8",
            },
            "font_family": "Aptos, Arial, sans-serif",
            "design_hints": "Footer bar visible. Progress dots in accent color.",
        }

        prompt = _build_page_prompt(
            plan, 1, spec_lock, "", 1280, 720, [],
            spec_lock_text="Progress dots in accent color.",
        )

        assert "Spec Polish Contract" in prompt
        assert "compact 3-dot progress indicator" in prompt
        assert "cx=24, 40, 56" in prompt
        assert "`#3B82F6`" in prompt
        assert "supplement it, not replace it" in prompt

    def test_includes_bullet_rendering_contract_for_bullet_items(self):
        plan = _make_plan(layout="bullet-list", title="Test Slide")
        plan.items = [
            ContentItem(type="text", primary="Overview"),
            ContentItem(type="bullet", primary="First point"),
            ContentItem(type="bullet", primary="Second point"),
        ]

        prompt = _build_page_prompt(
            plan, 1,
            {"palette": {"background": "#FFF", "accent": "#3B82F6"}, "font_family": "Arial"},
            "", 1280, 720, [],
        )

        assert "Bullet Rendering Contract" in prompt
        assert "This slide has 2 planned `[bullet]` item(s)" in prompt
        assert "Each `[bullet]` item must have a visible marker before the text" in prompt
        assert "separate SVG `<circle>` markers" in prompt
        assert "Bullet body text must use the body/text_secondary color" in prompt
        assert "do not use the primary title color" in prompt
        assert "Do not render planned `[bullet]` items as plain paragraph lines" in prompt

    def test_layout_coordinate_guidance_maps_common_patterns(self):
        assert "two-column cards" in _layout_coordinate_guidance(
            "comparison",
            "comparison grid with four cards",
            1280,
            720,
        )
        assert "top region: x=80..1200, y=96..260" in _layout_coordinate_guidance(
            "bullet-list",
            "top metric row with lower bullets",
            1280,
            720,
        )
        assert "safe content region: x=80..1200, y=96..648" in _layout_coordinate_guidance(
            "quote",
            "single centered statement",
            1280,
            720,
        )

    def test_includes_spec_lock_snapshot_and_feedback(self):
        plan = _make_plan()
        prompt = _build_page_prompt(
            plan, 3,
            {"palette": {"background": "#FFF", "accent": "#3B82F6"}, "font_family": "Arial"},
            "", 1280, 720, [],
            spec_lock_text="LOCKED COLOR #3B82F6",
            feedback="- ERROR slide_01.svg: Missing semantic group",
        )
        assert "Spec Lock Snapshot" in prompt
        assert "LOCKED COLOR #3B82F6" in prompt
        assert "QA Feedback From Previous Attempt" in prompt
        assert "Missing semantic group" in prompt

    def test_includes_visual_feedback(self):
        plan = _make_plan()
        prompt = _build_page_prompt(
            plan, 3,
            {"palette": {"background": "#FFF", "accent": "#3B82F6"}, "font_family": "Arial"},
            "", 1280, 720, [],
            visual_feedback="- repair_prompt: Move the title block down by 32 px and preserve Repair Title.\n- issues: Title is too close to the top edge.",
        )
        assert "Rendered Visual Repair Contract" in prompt
        assert "mandatory repair targets" in prompt
        assert "Prioritize `repair_prompt` items when present" in prompt
        assert "treat `actions` / `action` entries as executor-ready repair instructions" in prompt
        assert "without deleting, hiding, paraphrasing away, or moving off-canvas" in prompt
        assert "Treat any text that visual feedback says to preserve" in prompt
        assert "only mentioned in `repair_prompt`, `actions`, or `action`" in prompt
        assert "Preserve Text From Visual Feedback" in prompt
        assert "preserve Repair Title" in prompt
        assert "保留" in prompt
        assert "If feedback mentions a panel, card, or surface background" in prompt
        assert "moving text alone is not a valid repair" in prompt
        assert "Preserve deck chrome and footer/page number" in prompt
        assert "Move the title block down by 32 px" in prompt
        assert "Title is too close to the top edge" in prompt

    def test_includes_action_only_visual_feedback_as_repair_instruction(self):
        plan = _make_plan()
        prompt = _build_page_prompt(
            plan, 3,
            {"palette": {"background": "#FFF", "accent": "#3B82F6"}, "font_family": "Arial"},
            "", 1280, 720, [],
            visual_feedback="- severity: major\n- actions: Move the title block down by 32 px and preserve Action Title.\n- issues: Title is clipped.",
        )

        assert "Rendered Visual Repair Contract" in prompt
        assert "treat `actions` / `action` entries as executor-ready repair instructions" in prompt
        assert "Move the title block down by 32 px" in prompt
        assert "Preserve Text From Visual Feedback" in prompt
        assert "preserve Action Title" in prompt

    def test_includes_executor_brief(self):
        plan = _make_plan()
        prompt = _build_page_prompt(
            plan, 3,
            {"palette": {"background": "#FFF", "accent": "#3B82F6"}, "font_family": "Arial"},
            "", 1280, 720, [],
            executor_brief="## Slide 1: Test\n- Visual strategy: cinematic title rail",
        )
        assert "AI Strategist Executor Brief" in prompt
        assert "cinematic title rail" in prompt

    def test_includes_content_fidelity_contract(self):
        plan = _make_plan(title="Required Title")
        plan.items = [
            ContentItem(type="text", primary="Required Body", secondary="Supporting context"),
            ContentItem(type="metric", primary="42% improvement", tertiary="YoY"),
        ]
        prompt = _build_page_prompt(
            plan, 3,
            {"palette": {"background": "#FFF", "accent": "#3B82F6"}, "font_family": "Arial"},
            "", 1280, 720, [],
        )
        assert "Content Fidelity Contract" in prompt
        assert 'title: "Required Title"' in prompt
        assert 'item 1: "Required Body"' in prompt
        assert 'item 1 secondary: "Supporting context"' in prompt
        assert 'item 2: "42% improvement"' in prompt
        assert 'item 2 tertiary: "YoY"' in prompt

    def test_required_text_contract_xml_escapes(self):
        plan = _make_plan(title="A & B")
        plan.items = [ContentItem(type="text", primary='Use "quoted" text')]

        contract = _format_required_text_contract(plan)

        assert "A &amp; B" in contract
        assert "&quot;quoted&quot;" in contract


class TestVisualFeedback:

    def test_loads_executor_brief_for_current_slide(self, tmp_path):
        p = _make_project(tmp_path)
        brief_dir = p / "qa" / "ai-planner"
        brief_dir.mkdir(parents=True, exist_ok=True)
        (brief_dir / "executor-brief.md").write_text(
            "# AI Executor Brief\n\n"
            "## Slide 1: First\n"
            "- Visual strategy: diagonal hero rail\n\n"
            "## Slide 2: Second\n"
            "- Visual strategy: dense comparison cards\n",
            encoding="utf-8",
        )

        feedback = _load_executor_brief(p, 1)
        assert "diagonal hero rail" in feedback
        assert "dense comparison cards" not in feedback

    def test_loads_markdown_feedback_for_current_slide(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "qa" / "VISUAL-REVIEW.md").write_text(
            "# Visual Review\n\n"
            "## Slide 1\n"
            "- Title is too close to the top edge.\n\n"
            "## Slide 2\n"
            "- Chart labels overlap.\n",
            encoding="utf-8",
        )

        feedback = _load_visual_feedback(p, 1)
        assert "Title is too close" in feedback
        assert "Chart labels overlap" not in feedback

    def test_skips_non_actionable_ok_markdown_feedback_for_current_slide(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "qa" / "VISUAL-REVIEW.md").write_text(
            "# Visual Review\n\n"
            "## Slide 1\n"
            "- Severity: ok\n"
            "- Summary: Slide looks good.\n\n"
            "## Slide 2\n"
            "- Issue: Footer is missing.\n",
            encoding="utf-8",
        )

        feedback = _load_visual_feedback(p, 1)

        assert feedback == ""

    def test_loads_json_feedback_for_current_slide(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "qa" / "visual-feedback.json").write_text(json.dumps({
            "slides": [
                {
                    "slide": 1,
                    "issues": ["Hero type is too small"],
                    "action": "Increase title scale",
                    "repair_prompt": "Make the hero title 20 px larger and move supporting copy below it.",
                },
                {"slide": 2, "issues": ["Footer is missing"]},
            ]
        }), encoding="utf-8")

        feedback = _load_visual_feedback(p, 1)
        assert feedback.index("repair_prompt") < feedback.index("issues")
        assert "Make the hero title" in feedback
        assert "Hero type is too small" in feedback
        assert "Increase title scale" in feedback
        assert "Footer is missing" not in feedback

    def test_loads_nested_json_actions_as_executor_instructions(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "qa" / "visual-feedback.json").write_text(json.dumps({
            "slides": [
                {
                    "slide": 1,
                    "severity": "major",
                    "summary": "Title and body are crowded.",
                    "issues": [
                        {"area": "title", "description": "Title touches the top safe margin."}
                    ],
                    "actions": [
                        {
                            "target": "title",
                            "instruction": "Move the title block down by 32 px.",
                            "preserve": "Keep the footer page number visible.",
                        },
                        {
                            "target": "body",
                            "repair": "Increase the gap between body rows to at least 24 px.",
                        },
                    ],
                    "repair_prompt": "",
                },
            ]
        }), encoding="utf-8")

        feedback = _load_visual_feedback(p, 1)

        assert "- actions:" in feedback
        assert "Move the title block down by 32 px." in feedback
        assert "Keep the footer page number visible." in feedback
        assert "Increase the gap between body rows to at least 24 px." in feedback
        assert "{'target':" not in feedback
        assert '"target":' not in feedback

    def test_skips_non_actionable_ok_json_feedback_for_current_slide(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "qa" / "visual-feedback.json").write_text(json.dumps({
            "slides": [
                {
                    "slide": 1,
                    "severity": "ok",
                    "summary": "Slide looks good.",
                    "issues": [],
                    "actions": [],
                    "repair_prompt": "",
                },
                {
                    "slide": 2,
                    "severity": "major",
                    "issues": ["Footer is missing"],
                    "repair_prompt": "Add the footer page number to the bottom-right corner.",
                },
            ]
        }), encoding="utf-8")

        feedback = _load_visual_feedback(p, 1)

        assert feedback == ""


class TestExtractSvg:

    def test_plain_svg(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        assert _extract_svg(svg) == svg

    def test_markdown_fence_stripped(self):
        raw = '```xml\n<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>\n```'
        result = _extract_svg(raw)
        assert result.startswith("<svg")
        assert result.endswith("</svg>")

    def test_surrounding_text_stripped(self):
        raw = 'Here is the SVG:\n<svg><rect/></svg>\nEnd.'
        result = _extract_svg(raw)
        assert result.startswith("<svg")
        assert result.endswith("</svg>")


class TestIsValidSvg:

    def test_valid(self):
        assert _is_valid_svg('<svg><rect/></svg>')

    def test_empty(self):
        assert not _is_valid_svg("")

    def test_no_closing(self):
        assert not _is_valid_svg('<svg><rect/>')

    def test_no_opening(self):
        assert not _is_valid_svg('</svg>')


class TestGenerateWithRetry:

    def test_content_fidelity_detects_missing_title_and_item(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Required Title")
        plan.items = [ContentItem(type="text", primary="Required Body", secondary="Required Detail")]
        path = p / "svg_output" / "slide_01.svg"
        svg = _valid_svg(title="Wrong Title", body="Required Body")
        path.write_text(svg, encoding="utf-8")

        issues = _check_content_fidelity(path, svg, plan)

        assert any("missing slide title" in issue.message for issue in issues)
        assert any("missing planned content item" in issue.message for issue in issues)
        assert any("item 1 secondary: Required Detail" in issue.message for issue in issues)

    def test_content_fidelity_ignores_non_visible_title_desc(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Required Title")
        plan.items = [ContentItem(type="text", primary="Required Body")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <title>Required Title</title>
  <desc>Required Body</desc>
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120">Visible Different Title</text></g>
  <g id="content-body-01"><text x="96" y="190">Visible Different Body</text></g>
</svg>'''

        issues = _check_content_fidelity(path, svg, plan)

        assert any("missing slide title" in issue.message for issue in issues)
        assert any("missing planned content item" in issue.message for issue in issues)

    def test_content_fidelity_ignores_hidden_svg_text(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Required Title")
        plan.items = [
            ContentItem(type="text", primary="Required Body", secondary="Required Detail"),
        ]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <text x="96" y="120" display="none">Required Title</text>
  <g opacity="0"><text x="96" y="190">Required Body</text></g>
  <text x="96" y="230" fill-opacity="0">Required Detail</text>
  <g id="content-title-01"><text x="96" y="300">Visible Different Title</text></g>
  <g id="content-body-01"><text x="96" y="340">Visible Different Body</text></g>
</svg>'''

        issues = _check_content_fidelity(path, svg, plan)

        assert any("missing slide title" in issue.message for issue in issues)
        assert any("item 1: Required Body" in issue.message for issue in issues)
        assert any("item 1 secondary: Required Detail" in issue.message for issue in issues)

    def test_content_fidelity_accepts_cjk_line_break_spacing(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Python 入门速览")
        plan.items = [
            ContentItem(type="quote", primary="动态类型提升入门效率，但需要通过测试减少类型错误"),
        ]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120">Python 入门速览</text></g>
  <g id="content-body-01">
    <text x="96" y="190">动态类型提升入门效率，</text>
    <text x="96" y="230">但需要通过测试减少类型错误</text>
  </g>
</svg>'''

        issues = _check_content_fidelity(path, svg, plan)

        assert not any("Content fidelity" in issue.message for issue in issues)

    def test_content_fidelity_accepts_cjk_title_split_by_colon(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Python 入门速览：变量与类型")
        plan.items = [ContentItem(type="text", primary="Python 变量无需提前声明类型")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01">
    <text x="96" y="120">Python 入门速览</text>
    <text x="96" y="170">变量与类型</text>
  </g>
  <g id="content-body-01"><text x="96" y="220">Python 变量无需提前声明类型</text></g>
</svg>'''

        issues = _check_content_fidelity(path, svg, plan)

        assert not any("missing slide title" in issue.message for issue in issues)

    def test_visual_feedback_preserve_text_is_content_fidelity_gate(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Repair Title")
        plan.items = [ContentItem(type="text", primary="Repair Body")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120">Repair Title</text></g>
  <g id="content-body-01"><text x="96" y="220">Repair Body</text></g>
</svg>'''
        path.write_text(svg, encoding="utf-8")

        issues = _validate_svg_attempt(
            p,
            path,
            plan=plan,
            visual_feedback="- repair_prompt: Move content lower and preserve \"Compliance Footnote\".",
            run_qa=False,
            strict_quality=True,
        )

        assert any("visual-feedback preserve 1: Compliance Footnote" in issue.message for issue in issues)

    def test_visual_feedback_generic_preserve_text_does_not_become_content_gate(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Repair Title")
        plan.items = [ContentItem(type="text", primary="Repair Body")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120">Repair Title</text></g>
  <g id="content-body-01"><text x="96" y="220">Repair Body</text></g>
</svg>'''
        path.write_text(svg, encoding="utf-8")

        issues = _validate_svg_attempt(
            p,
            path,
            plan=plan,
            visual_feedback="- repair_prompt: Remove the dot while preserving the footer progress dots and all source-backed text.",
            run_qa=False,
            strict_quality=True,
        )

        assert not any("visual-feedback preserve" in issue.message for issue in issues)

    def test_visual_feedback_accent_stripe_requires_visible_narrow_rect(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Repair Title")
        plan.items = [ContentItem(type="text", primary="Repair Body")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120">Repair Title</text></g>
  <g id="content-body-01"><text x="96" y="220">Repair Body</text></g>
</svg>'''
        path.write_text(svg, encoding="utf-8")

        issues = _validate_svg_attempt(
            p,
            path,
            plan=plan,
            visual_feedback="- repair_prompt: Add a visible accent stripe beside the title.",
            run_qa=False,
            strict_quality=True,
        )

        assert any("requested accent stripe/rail" in issue.message for issue in issues)

    def test_visual_feedback_accent_stripe_accepts_visible_narrow_rect(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Repair Title")
        plan.items = [ContentItem(type="text", primary="Repair Body")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <rect x="64" y="88" width="8" height="240" fill="#3B82F6"/>
  <g id="content-title-01"><text x="96" y="120">Repair Title</text></g>
  <g id="content-body-01"><text x="96" y="220">Repair Body</text></g>
</svg>'''
        path.write_text(svg, encoding="utf-8")

        issues = _validate_svg_attempt(
            p,
            path,
            plan=plan,
            visual_feedback="- repair_prompt: Add a visible accent stripe beside the title.",
            run_qa=False,
            strict_quality=True,
        )

        assert not any("requested accent stripe/rail" in issue.message for issue in issues)

    def test_visual_feedback_panel_requires_visible_content_sized_rect(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Repair Title")
        plan.items = [ContentItem(type="text", primary="Repair Body")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120">Repair Title</text></g>
  <g id="content-body-01"><text x="96" y="220">Repair Body</text></g>
</svg>'''
        path.write_text(svg, encoding="utf-8")

        issues = _validate_svg_attempt(
            p,
            path,
            plan=plan,
            visual_feedback="- repair_prompt: Add a visible panel background behind the body copy.",
            run_qa=False,
            strict_quality=True,
        )

        assert any("requested panel/card/surface background" in issue.message for issue in issues)

    def test_visual_feedback_panel_accepts_content_sized_rect(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Repair Title")
        plan.items = [ContentItem(type="text", primary="Repair Body")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <rect x="80" y="170" width="420" height="150" fill="#1E293B"/>
  <g id="content-title-01"><text x="96" y="120">Repair Title</text></g>
  <g id="content-body-01"><text x="96" y="220">Repair Body</text></g>
</svg>'''
        path.write_text(svg, encoding="utf-8")

        issues = _validate_svg_attempt(
            p,
            path,
            plan=plan,
            visual_feedback="- repair_prompt: Add a visible panel background behind the body copy.",
            run_qa=False,
            strict_quality=True,
        )

        assert not any("requested panel/card/surface background" in issue.message for issue in issues)

    def test_visual_feedback_bullet_marker_requires_visible_marker_or_glyph(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Repair Title")
        plan.items = [ContentItem(type="text", primary="Repair Body")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120">Repair Title</text></g>
  <g id="content-body-01"><text x="96" y="220">Repair Body</text></g>
</svg>'''
        path.write_text(svg, encoding="utf-8")

        issues = _validate_svg_attempt(
            p,
            path,
            plan=plan,
            visual_feedback="- repair_prompt: Add visible accent-color bullet marker dots before each body point.",
            run_qa=False,
            strict_quality=True,
        )

        assert any("requested bullet marker/color" in issue.message for issue in issues)

    def test_visual_feedback_bullet_marker_accepts_visible_circle_marker(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Repair Title")
        plan.items = [ContentItem(type="text", primary="Repair Body")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120">Repair Title</text></g>
  <g id="content-body-01">
    <circle cx="84" cy="220" r="5" fill="#3B82F6"/>
    <text x="96" y="220">Repair Body</text>
  </g>
</svg>'''
        path.write_text(svg, encoding="utf-8")

        issues = _validate_svg_attempt(
            p,
            path,
            plan=plan,
            visual_feedback="- repair_prompt: Add visible accent-color bullet marker dots before each body point.",
            run_qa=False,
            strict_quality=True,
        )

        assert not any("requested bullet marker/color" in issue.message for issue in issues)

    def test_bullet_marker_check_warns_when_bullet_items_have_no_visible_markers(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(layout="bullet-list")
        plan.items = [
            ContentItem(type="text", primary="Variables"),
            ContentItem(type="bullet", primary="Python variables need no declaration."),
            ContentItem(type="bullet", primary="Use tests to reduce type mistakes."),
        ]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120" font-size="44">Test Slide</text></g>
  <g id="content-body-01">
    <text x="96" y="220" font-size="24">Variables</text>
    <text x="96" y="280" font-size="24">Python variables need no declaration.</text>
    <text x="96" y="340" font-size="24">Use tests to reduce type mistakes.</text>
  </g>
</svg>'''

        issues = _check_bullet_markers(path, svg, plan)

        assert len(issues) == 2
        assert all(issue.level == "warning" for issue in issues)
        assert "lacks a visible bullet marker" in issues[0].message

    def test_bullet_marker_check_accepts_circle_markers_before_bullet_text(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(layout="bullet-list")
        plan.items = [
            ContentItem(type="bullet", primary="Python variables need no declaration."),
            ContentItem(type="bullet", primary="Use tests to reduce type mistakes."),
        ]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120" font-size="44">Test Slide</text></g>
  <g id="content-body-01">
    <circle cx="84" cy="280" r="5" fill="#3B82F6"/>
    <text x="112" y="280" font-size="24">Python variables need no declaration.</text>
    <circle cx="84" cy="340" r="5" fill="#3B82F6"/>
    <text x="112" y="340" font-size="24">Use tests to reduce type mistakes.</text>
  </g>
</svg>'''

        assert _check_bullet_markers(path, svg, plan) == []

    def test_bullet_marker_check_accepts_visible_bullet_glyphs(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(layout="bullet-list")
        plan.items = [ContentItem(type="bullet", primary="Python 变量无需提前声明类型。")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120" font-size="44">Test Slide</text></g>
  <g id="content-body-01">
    <text x="96" y="280" font-size="24">• Python 变量无需提前声明类型。</text>
  </g>
</svg>'''

        assert _check_bullet_markers(path, svg, plan) == []

    def test_bullet_text_color_warns_when_body_uses_primary_title_color(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(layout="bullet-list")
        plan.items = [ContentItem(type="bullet", primary="Python variables need no declaration.")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120" font-size="44" fill="#F8FAFC">Test Slide</text></g>
  <g id="content-body-01">
    <circle cx="84" cy="280" r="5" fill="#3B82F6"/>
    <text x="112" y="280" font-size="24" fill="#F8FAFC">Python variables need no declaration.</text>
  </g>
</svg>'''

        issues = _check_bullet_text_color(path, svg, plan, p)

        assert any("bullet body text uses primary title color" in issue.message for issue in issues)
        assert any("#94A3B8" in issue.message for issue in issues)

    def test_bullet_text_color_accepts_body_color(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(layout="bullet-list")
        plan.items = [ContentItem(type="bullet", primary="Python variables need no declaration.")]
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120" font-size="44" fill="#F8FAFC">Test Slide</text></g>
  <g id="content-body-01">
    <circle cx="84" cy="280" r="5" fill="#3B82F6"/>
    <text x="112" y="280" font-size="24" fill="#94A3B8">Python variables need no declaration.</text>
  </g>
</svg>'''

        assert _check_bullet_text_color(path, svg, plan, p) == []

    def test_layout_intent_detects_missing_right_region(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan()
        plan.layout_pattern = "large title left with compact proof card right"
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120">Test Slide</text></g>
  <g id="content-body-01"><text x="96" y="190">Hello</text></g>
</svg>'''

        issues = _check_layout_intent(path, svg, plan)

        assert any("left/right structure" in issue.message for issue in issues)

    def test_layout_intent_does_not_treat_left_accent_as_two_column(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(layout="bullet-list")
        plan.layout_pattern = "title top + 3 bullet points vertically stacked with left-aligned accent stripe"
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="decor-01"><rect x="0" y="0" width="6" height="720" fill="#3B82F6"/></g>
  <g id="content-title-01"><text x="96" y="120">Test Slide</text></g>
  <g id="content-body-01"><text x="112" y="240">Bullet content</text></g>
</svg>'''

        issues = _check_layout_intent(path, svg, plan)

        assert not any("left/right structure" in issue.message for issue in issues)

    def test_layout_intent_accepts_left_right_regions(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan()
        plan.layout_pattern = "large title left with compact proof card right"
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-title-01"><text x="96" y="120">Test Slide</text></g>
  <g id="content-body-01"><text x="720" y="190">Hello</text></g>
</svg>'''

        issues = _check_layout_intent(path, svg, plan)

        assert not issues

    def test_layout_intent_rejects_empty_right_decoration_for_two_column_grid(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(layout="bullet-list")
        plan.layout_pattern = "bullet cards in 2-column grid"
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-left">
    <text x="96" y="120">Test Slide</text>
    <text x="112" y="240">All body text remains in the left column</text>
  </g>
  <g id="decor-right">
    <line x1="720" y1="220" x2="1180" y2="220" stroke="#334155"/>
    <line x1="720" y1="320" x2="1180" y2="320" stroke="#334155"/>
  </g>
</svg>'''

        issues = _check_layout_intent(path, svg, plan)

        assert any("left/right structure" in issue.message for issue in issues)
        assert any("grid/comparison structure" in issue.message for issue in issues)

    def test_layout_intent_detects_flat_grid(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(layout="comparison")
        plan.layout_pattern = "comparison grid with four cards"
        path = p / "svg_output" / "slide_01.svg"
        svg = '''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="content-body-01">
    <rect x="96" y="160" width="200" height="80"/>
    <rect x="360" y="160" width="200" height="80"/>
  </g>
</svg>'''

        issues = _check_layout_intent(path, svg, plan)

        assert any("grid/comparison structure" in issue.message for issue in issues)

    def test_retry_on_invalid(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan()

        call_count = 0
        user_prompts = []

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            user_prompts.append(kwargs["messages"][1]["content"])
            msg = MagicMock()
            if call_count <= 1:
                msg.content = "Not SVG at all"
            else:
                msg.content = _valid_svg()
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            paths = generate_svg_with_ai(p, [plan])
            assert len(paths) == 1
            assert paths[0].exists()
            content = paths[0].read_text(encoding="utf-8")
            assert "<svg" in content
            assert call_count == 2
            assert "QA Feedback From Previous Attempt" in user_prompts[1]

    def test_retry_on_svg_with_surrounding_prose(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan()
        call_count = 0
        user_prompts = []

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            user_prompts.append(kwargs["messages"][1]["content"])
            msg = MagicMock()
            if call_count == 1:
                msg.content = f"Here is the SVG:\n{_valid_svg()}\nDone."
            else:
                msg.content = _valid_svg()
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            paths = generate_svg_with_ai(p, [plan], qa_retries=1)

        assert call_count == 2
        assert paths[0].read_text(encoding="utf-8").startswith("<svg")
        assert "Model output included prose before the SVG" in user_prompts[1]
        first_log = json.loads((p / "qa" / "executor" / "slide_01_attempt_01.json").read_text(encoding="utf-8"))
        assert any("prose before the SVG" in issue["message"] for issue in first_log["issues"])

    def test_failed_generation_does_not_publish_invalid_svg(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan()
        published = p / "svg_output" / "slide_01.svg"
        original_svg = _valid_svg(title="Existing Good", body="Existing Body")
        published.write_text(original_svg, encoding="utf-8")

        def fake_create(**kwargs):
            msg = MagicMock()
            msg.content = "Not SVG at all"
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            try:
                generate_svg_with_ai(p, [plan], clear_output=False, qa_retries=1)
            except RuntimeError as exc:
                assert "failed QA for slide_01.svg after 2 attempts" in str(exc)
            else:
                raise AssertionError("expected RuntimeError")

        assert published.read_text(encoding="utf-8") == original_svg
        attempt_dir = p / "qa" / "executor" / "attempt-svg"
        assert (attempt_dir / "slide_01_attempt_01.svg").read_text(encoding="utf-8") == "Not SVG at all"
        assert (attempt_dir / "slide_01_attempt_02.svg").read_text(encoding="utf-8") == "Not SVG at all"
        log_data = json.loads((p / "qa" / "executor" / "slide_01_attempt_02.json").read_text(encoding="utf-8"))
        assert "attempt-svg" in log_data["path"]
        trace = [
            json.loads(line)
            for line in (p / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert trace[-1]["metadata"]["publish_path"].endswith("slide_01.svg")
        assert trace[-1]["metadata"]["blocking_issues"]
        assert any("not a complete <svg>" in issue for issue in trace[-1]["metadata"]["blocking_issues"])

    def test_provider_error_writes_trace_and_attempt_log(self, tmp_path):
        from slide_skill.ai_trace import read_ai_trace

        p = _make_project(tmp_path)
        plan = _make_plan()
        published = p / "svg_output" / "slide_01.svg"
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("model unavailable")
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            try:
                generate_svg_with_ai(
                    p,
                    [plan],
                    qa_retries=1,
                    model="executor-provider-test",
                )
            except RuntimeError as exc:
                assert "AI executor provider call failed for slide_01.svg after 2 attempts" in str(exc)
            else:
                raise AssertionError("expected RuntimeError")

        trace = read_ai_trace(p)
        log_data = json.loads((p / "qa" / "executor" / "slide_01_attempt_02.json").read_text(encoding="utf-8"))

        assert not published.exists()
        assert len(trace) == 2
        assert trace[-1]["stage"] == "executor"
        assert trace[-1]["status"] == "failed"
        assert trace[-1]["model"] == "executor-provider-test"
        assert trace[-1]["metadata"]["provider_error"] is True
        assert "model unavailable" in trace[-1]["metadata"]["error"]
        assert "model unavailable" in trace[-1]["metadata"]["blocking_issues"][0]
        assert trace[-1]["request_path"].endswith(".request.json")
        assert trace[-1]["prompt_path"].endswith(".prompt.txt")
        assert log_data["blocking_count"] == 1
        assert "model unavailable" in log_data["error"]

    def test_attempt_quality_warnings_block_before_publish(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan()
        call_count = 0
        user_prompts = []

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            user_prompts.append(kwargs["messages"][1]["content"])
            msg = MagicMock()
            if call_count == 1:
                msg.content = _valid_svg().replace("#F8FAFC", "#FF0000")
            else:
                msg.content = _valid_svg()
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            paths = generate_svg_with_ai(p, [plan], qa_retries=1)

        assert call_count == 2
        assert "#FF0000" not in paths[0].read_text(encoding="utf-8")
        assert "#FF0000" in (p / "qa" / "executor" / "attempt-svg" / "slide_01_attempt_01.svg").read_text(encoding="utf-8")
        assert "Color #FF0000 not in spec lock palette" in user_prompts[1]
        first_log = json.loads((p / "qa" / "executor" / "slide_01_attempt_01.json").read_text(encoding="utf-8"))
        assert any("Color #FF0000" in issue["message"] for issue in first_log["issues"])
        assert first_log["blocking_count"] >= 1

    def test_retry_rebuilds_system_prompt_from_updated_spec_lock(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan()
        call_count = 0
        system_prompts = []

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            system_prompts.append(kwargs["messages"][0]["content"])
            msg = MagicMock()
            if call_count == 1:
                lock = json.loads((p / "spec_lock.json").read_text(encoding="utf-8"))
                lock["palette"]["accent"] = "#F97316"
                lock["font_family"] = "Aptos, sans-serif"
                (p / "spec_lock.json").write_text(json.dumps(lock), encoding="utf-8")
                msg.content = "Not SVG at all"
            else:
                msg.content = _valid_svg()
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            generate_svg_with_ai(p, [plan], run_qa=False)

        assert call_count == 2
        assert "#F97316" not in system_prompts[0]
        assert "Aptos, sans-serif" not in system_prompts[0]
        assert "#F97316" in system_prompts[1]
        assert "Aptos, sans-serif" in system_prompts[1]

    def test_retry_on_missing_planned_content(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan(title="Required Title")
        plan.items = [ContentItem(type="text", primary="Required Body")]
        call_count = 0
        user_prompts = []

        def fake_create(**kwargs):
            nonlocal call_count
            call_count += 1
            user_prompts.append(kwargs["messages"][1]["content"])
            msg = MagicMock()
            if call_count == 1:
                msg.content = _valid_svg(title="Wrong Title", body="Wrong Body")
            else:
                msg.content = _valid_svg(title="Required Title", body="Required Body")
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            paths = generate_svg_with_ai(p, [plan])

        assert len(paths) == 1
        assert call_count == 2
        assert "Content Fidelity Contract" in user_prompts[0]
        assert 'title: "Required Title"' in user_prompts[0]
        assert "Content fidelity: missing slide title text" in user_prompts[1]
        assert "Content fidelity: missing planned content item" in user_prompts[1]

    def test_generates_svg_files(self, tmp_path):
        p = _make_project(tmp_path)
        plan = _make_plan()

        def fake_create(**kwargs):
            msg = MagicMock()
            msg.content = _valid_svg()
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            paths = generate_svg_with_ai(p, [plan])
            assert len(paths) == 1
            svg_text = paths[0].read_text(encoding="utf-8")
            assert "1280" in svg_text
            assert "720" in svg_text
            log_path = p / "qa" / "executor" / "slide_01_attempt_01.json"
            assert log_path.exists()
            log_data = json.loads(log_path.read_text(encoding="utf-8"))
            assert log_data["blocking_count"] == 0
            trace = (p / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8")
            assert '"stage": "executor"' in trace

    def test_clear_output_false_preserves_existing_slides(self, tmp_path):
        p = _make_project(tmp_path)
        existing = p / "svg_output" / "slide_99.svg"
        existing.write_text(_valid_svg(slide_no=99, total=99), encoding="utf-8")
        plan = _make_plan()

        def fake_create(**kwargs):
            msg = MagicMock()
            msg.content = _valid_svg()
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            generate_svg_with_ai(p, [plan], clear_output=False)

        assert existing.exists()

    def test_targeted_repair_uses_existing_deck_total(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "svg_output" / "slide_03.svg").write_text(_valid_svg(slide_no=3, total=3), encoding="utf-8")
        plan = _make_plan(index=2)
        user_prompts = []

        def fake_create(**kwargs):
            user_prompts.append(kwargs["messages"][1]["content"])
            msg = MagicMock()
            msg.content = _valid_svg(slide_no=2, total=3)
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            generate_svg_with_ai(p, [plan], clear_output=False)

        assert "Footer must show: 02 / 03" in user_prompts[0]

    def test_injects_visual_feedback_into_generation_prompt(self, tmp_path):
        p = _make_project(tmp_path)
        (p / "qa" / "VISUAL-REVIEW.md").write_text(
            "## Slide 1\n- Move title down; it is clipped in the rendered image.\n",
            encoding="utf-8",
        )
        plan = _make_plan()
        user_prompts = []

        def fake_create(**kwargs):
            user_prompts.append(kwargs["messages"][1]["content"])
            msg = MagicMock()
            msg.content = _valid_svg()
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            generate_svg_with_ai(p, [plan])

        assert "Rendered Visual Repair Contract" in user_prompts[0]
        assert "mandatory repair targets" in user_prompts[0]
        assert "Move title down" in user_prompts[0]
        log_path = p / "qa" / "executor" / "slide_01_attempt_01.json"
        log_data = json.loads(log_path.read_text(encoding="utf-8"))
        assert log_data["has_visual_feedback"] is True
        assert log_data["visual_feedback_chars"] > 0

    def test_injects_executor_brief_into_generation_prompt(self, tmp_path):
        p = _make_project(tmp_path)
        brief_dir = p / "qa" / "ai-planner"
        brief_dir.mkdir(parents=True, exist_ok=True)
        (brief_dir / "executor-brief.md").write_text(
            "## Slide 1: Test Slide\n"
            "- Visual strategy: hero layout with diagonal accent rail\n"
            "- Layout pattern: title left, proof card right\n",
            encoding="utf-8",
        )
        plan = _make_plan()
        user_prompts = []

        def fake_create(**kwargs):
            user_prompts.append(kwargs["messages"][1]["content"])
            msg = MagicMock()
            msg.content = _valid_svg()
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            generate_svg_with_ai(p, [plan])

        assert "AI Strategist Executor Brief" in user_prompts[0]
        assert "Planner Design Execution Contract" in user_prompts[0]
        assert "diagonal accent rail" in user_prompts[0]
        log_path = p / "qa" / "executor" / "slide_01_attempt_01.json"
        log_data = json.loads(log_path.read_text(encoding="utf-8"))
        assert log_data["has_executor_brief"] is True
        assert log_data["executor_brief_chars"] > 0
        trace = [
            json.loads(line)
            for line in (p / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        assert trace[-1]["metadata"]["has_executor_brief"] is True


class TestModeRouting:

    def test_generation_mode_defaults_to_auto(self, monkeypatch):
        from argparse import Namespace
        from slide_skill.cli import _resolve_generation_mode
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        assert _resolve_generation_mode(Namespace(mode=None)) == "fast"
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert _resolve_generation_mode(Namespace(mode=None)) == "ai"

    def test_quick_mode_is_fast_alias(self):
        from argparse import Namespace
        from slide_skill.cli import _resolve_generation_mode
        assert _resolve_generation_mode(Namespace(mode="quick")) == "fast"
        assert _resolve_generation_mode(Namespace(mode="template-smoke")) == "fast"

    def test_ai_access_requires_key_or_local_base(self, monkeypatch):
        from argparse import Namespace
        from slide_skill.cli import _ai_access_configured, _ai_kwargs_from_args
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        assert not _ai_access_configured(Namespace(ai_api_key=None, ai_base_url=None))
        assert _ai_access_configured(Namespace(ai_api_key="sk-test", ai_base_url=None))
        assert _ai_access_configured(Namespace(ai_api_key=None, ai_base_url="http://127.0.0.1:11434/v1"))
        kwargs = _ai_kwargs_from_args(Namespace(
            model=None,
            ai_api_key=None,
            ai_base_url="http://127.0.0.1:11434/v1",
            ai_max_tokens=4096,
            ai_temperature=0.7,
            ai_top_p=None,
        ))
        assert kwargs["api_key"] == "local-openai-compatible"

    def test_ai_kwargs_preserve_env_key_for_custom_base(self, monkeypatch):
        from argparse import Namespace
        from slide_skill.cli import _ai_kwargs_from_args

        monkeypatch.setenv("OPENAI_API_KEY", "sk-env-real")
        kwargs = _ai_kwargs_from_args(Namespace(
            model=None,
            ai_api_key=None,
            ai_base_url="https://token.sensenova.cn/v1",
            ai_max_tokens=4096,
            ai_temperature=0.7,
            ai_top_p=None,
        ))

        assert kwargs["api_key"] == "sk-env-real"

    def test_build_command_has_mode_flag(self):
        from slide_skill.cli import main
        result = main(["build", "nonexistent.md", "--mode", "ai"])
        assert result == 1

    def test_quickstart_command_has_mode_flag(self):
        from slide_skill.cli import main
        result = main(["quickstart", "nonexistent.md", "--mode", "ai"])
        assert result == 1

    def test_quickstart_reports_trace_hint_on_ai_planner_failure(self, tmp_path, monkeypatch, capsys):
        from slide_skill.cli import main
        from slide_skill.ai_trace import write_ai_trace

        source = tmp_path / "source.md"
        source.write_text("# Deck\n\n- Source point\n", encoding="utf-8")
        base = tmp_path / "projects"

        def fake_plan(source_text, config, *, project=None, args=None):
            write_ai_trace(
                project,
                stage="planner",
                model="planner-model",
                status="failed",
                attempt=1,
                metadata={"error": "Missing source coverage anchors: Source point"},
            )
            raise RuntimeError("AI planner failed validation after 1 attempt(s)")

        monkeypatch.setattr("slide_skill.cli._plan_source_slides", fake_plan)

        result = main([
            "quickstart",
            str(source),
            "--name",
            "planner-failure",
            "--base",
            str(base),
            "--mode",
            "ai",
            "--planner",
            "ai",
            "--ai-base-url",
            "http://127.0.0.1:11434/v1",
        ])

        project = base / "planner-failure"
        stderr = capsys.readouterr().err
        assert result == 1
        assert "AI planner failed validation after 1 attempt(s)" in stderr
        assert f"slide-skill ai-trace {project}" in stderr
        assert "--latest-iteration --diagnose" not in stderr
        assert "last-ai-failure: stage=planner | status=failed | attempt=1 | model=planner-model" in stderr

    def test_repair_slide_command_uses_ai_gate(self, monkeypatch):
        from slide_skill.cli import main
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        result = main(["repair-slide", "missing-project", "1"])
        assert result == 1

    def test_build_reports_trace_hint_on_ai_executor_failure(self, tmp_path, monkeypatch, capsys):
        from slide_skill.cli import main
        from slide_skill.ai_trace import write_ai_trace

        source = tmp_path / "source.md"
        source.write_text("# Deck\n\n- Source point\n", encoding="utf-8")
        base = tmp_path / "projects"

        def fake_generate(project, plans, **kwargs):
            write_ai_trace(
                project,
                stage="executor",
                model="executor-model",
                status="failed",
                attempt=2,
                metadata={
                    "slide": 1,
                    "blocking_count": 3,
                    "error": "Content fidelity: missing planned content item",
                },
            )
            raise RuntimeError("failed QA for slide_01.svg after 2 attempts")

        monkeypatch.setattr("slide_skill.ai_executor.generate_svg_with_ai", fake_generate)

        result = main([
            "build",
            str(source),
            "--name",
            "executor-failure",
            "--base",
            str(base),
            "--mode",
            "ai",
            "--planner",
            "deterministic",
            "--skip-confirm",
            "--ai-base-url",
            "http://127.0.0.1:11434/v1",
            "--executor-model",
            "executor-model",
        ])

        project = base / "executor-failure"
        stderr = capsys.readouterr().err
        assert result == 1
        assert "failed QA for slide_01.svg after 2 attempts" in stderr
        assert f"slide-skill ai-trace {project}" in stderr
        assert "last-ai-failure: stage=executor | status=failed | attempt=2 | model=executor-model | slide=1 | blocking_count=3" in stderr

    def test_repair_feedback_repairs_flagged_slides(self, tmp_path):
        from slide_skill.cli import main

        p = _make_project(tmp_path)
        (p / "svg_output" / "slide_01.svg").write_text(_valid_svg(slide_no=1, total=3), encoding="utf-8")
        (p / "svg_output" / "slide_02.svg").write_text(_valid_svg(slide_no=2, total=3), encoding="utf-8")
        (p / "svg_output" / "slide_03.svg").write_text(_valid_svg(slide_no=3, total=3), encoding="utf-8")
        (p / "qa" / "visual-feedback.json").write_text(json.dumps({
            "slides": [
                {"slide": 1, "severity": "ok"},
                {"slide": 2, "severity": "major", "issues": ["Title clipped"], "actions": ["Move title lower"]},
            ]
        }), encoding="utf-8")
        user_prompts = []

        def fake_create(**kwargs):
            user_prompts.append(kwargs["messages"][1]["content"])
            msg = MagicMock()
            msg.content = _valid_svg(slide_no=2, total=3)
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            result = main(["repair-feedback", str(p), "--ai-base-url", "http://127.0.0.1:11434/v1"])

        assert result == 0
        assert len(user_prompts) == 1
        assert "Create SVG page 2" in user_prompts[0]
        assert "Footer must show: 02 / 03" in user_prompts[0]
        assert "Title clipped" in user_prompts[0]

    def test_repair_feedback_skips_summary_only_visual_feedback(self, tmp_path):
        from slide_skill.cli import main

        p = _make_project(tmp_path)
        (p / "svg_output" / "slide_01.svg").write_text(_valid_svg(slide_no=1, total=2), encoding="utf-8")
        (p / "svg_output" / "slide_02.svg").write_text(_valid_svg(slide_no=2, total=2), encoding="utf-8")
        (p / "qa" / "visual-feedback.json").write_text(json.dumps({
            "slides": [
                {"slide": 1, "severity": "major", "summary": "Title hierarchy is weak."},
                {"slide": 2, "severity": "major", "summary": "Footer is missing.", "actions": ["Add the footer page number."]},
            ]
        }), encoding="utf-8")
        user_prompts = []

        def fake_create(**kwargs):
            user_prompts.append(kwargs["messages"][1]["content"])
            msg = MagicMock()
            msg.content = _valid_svg(slide_no=2, total=2)
            choice = MagicMock()
            choice.message = msg
            resp = MagicMock()
            resp.choices = [choice]
            return resp

        mock_client = MagicMock()
        mock_client.chat.completions.create = fake_create
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            result = main(["repair-feedback", str(p), "--ai-base-url", "http://127.0.0.1:11434/v1"])

        assert result == 0
        assert len(user_prompts) == 1
        assert "Create SVG page 2" in user_prompts[0]
        assert "Create SVG page 1" not in user_prompts[0]
        assert "Add the footer page number." in user_prompts[0]

    def test_repair_content_items_strip_svg_bullet_glyphs(self):
        from slide_skill.cli import _content_items_from_body

        items = _content_items_from_body(
            "• Python 变量无需提前声明类型。\n"
            "◦ 常见类型包括 int、float、str 和 bool。\n"
            "▪ 动态类型提升入门效率。\n"
            "‣ 通过测试减少类型错误。\n"
        )

        assert [item.primary for item in items] == [
            "Python 变量无需提前声明类型。",
            "常见类型包括 int、float、str 和 bool。",
            "动态类型提升入门效率。",
            "通过测试减少类型错误。",
        ]
        assert [item.type for item in items] == ["bullet", "bullet", "bullet", "bullet"]

        mixed = _content_items_from_body("变量与类型\n• Python 变量无需提前声明类型。")

        assert [item.type for item in mixed] == ["text", "bullet"]

    def test_iterate_ai_runs_visual_repair_loop(self, tmp_path, monkeypatch):
        from slide_skill.cli import main

        p = _make_project(tmp_path)
        deck = p / "exports" / "deck.pptx"
        deck.parent.mkdir(exist_ok=True)
        deck.write_bytes(b"pptx")
        (p / "svg_output" / "slide_01.svg").write_text(_valid_svg(), encoding="utf-8")
        (p / "svg_final" / "slide_01.svg").write_text(_valid_svg(), encoding="utf-8")
        events = []

        def fake_export(project, output=None, stage="final"):
            events.append(("export", stage))
            return deck

        def fake_render(pptx, output_dir, dpi=150):
            events.append(("render", Path(output_dir).name, dpi))
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            image = Path(output_dir) / "slide-1.jpg"
            image.write_bytes(b"jpg")
            return [image]

        def fake_visual_feedback(project, rendered_dir=None, **kwargs):
            events.append(("critic", Path(rendered_dir).name, kwargs.get("model"), kwargs.get("retries")))
            (Path(project) / "qa" / "visual-feedback.json").write_text(json.dumps({
                "slides": [{
                    "slide": 1,
                    "severity": "major",
                    "issues": ["Text overlap"],
                    "actions": ["Separate the overlapping text blocks by at least 24 px."],
                }]
            }), encoding="utf-8")
            (Path(project) / "qa" / "VISUAL-REVIEW.md").write_text(
                "## Slide 1\n- Text overlap\n",
                encoding="utf-8",
            )
            return Path(project) / "qa" / "visual-feedback.json", Path(project) / "qa" / "VISUAL-REVIEW.md"

        def fake_generate(project, plans, clear_output=False, **kwargs):
            events.append(("repair", [plan.index for plan in plans], clear_output, kwargs.get("model"), kwargs.get("qa_retries")))
            path = Path(project) / "svg_output" / "slide_01.svg"
            path.write_text(_valid_svg(), encoding="utf-8")
            return [path]

        def fake_finalize(project):
            events.append(("finalize", str(project)))
            return [Path(project) / "svg_final" / "slide_01.svg"]

        def fake_run_qa(project, pptx_path=None, require_visual=False, require_fix_verify=False):
            events.append(("qa", require_visual, require_fix_verify))
            report = Path(project) / "qa" / "QA.md"
            report.write_text("status: automated-passed\n", encoding="utf-8")
            return True, report

        monkeypatch.setattr("slide_skill.cli.export_project", fake_export)
        monkeypatch.setattr("slide_skill.cli.render_pptx", fake_render)
        monkeypatch.setattr("slide_skill.cli.finalize_svg", fake_finalize)
        monkeypatch.setattr("slide_skill.cli.run_qa", fake_run_qa)
        monkeypatch.setattr("slide_skill.visual_critic.generate_visual_feedback", fake_visual_feedback)
        monkeypatch.setattr("slide_skill.ai_executor.generate_svg_with_ai", fake_generate)

        result = main([
            "iterate-ai",
            str(p),
            "--ai-base-url",
            "http://127.0.0.1:11434/v1",
            "--model",
            "global-model",
            "--executor-model",
            "executor-model",
            "--vision-model",
            "vision-model",
            "--executor-qa-retries",
            "4",
            "--vision-retries",
            "3",
        ])

        assert result == 0
        assert ("render", "rendered-round-01", 150) in events
        assert ("render", "rendered-final", 150) in events
        assert ("critic", "rendered-round-01", "vision-model", 3) in events
        assert ("critic", "rendered-final", "vision-model", 3) in events
        assert ("repair", [1], False, "executor-model", 4) in events
        assert any(event[0] == "finalize" for event in events)
        assert ("qa", False, False) in events

    def test_iterate_ai_falls_back_to_svg_preview_rendering(self, tmp_path, monkeypatch):
        from slide_skill.cli import main

        p = _make_project(tmp_path)
        deck = p / "exports" / "deck.pptx"
        deck.parent.mkdir(exist_ok=True)
        deck.write_bytes(b"pptx")
        (p / "svg_output" / "slide_01.svg").write_text(_valid_svg(), encoding="utf-8")
        (p / "svg_final" / "slide_01.svg").write_text(_valid_svg(), encoding="utf-8")
        events = []

        def fake_export(project, output=None, stage="final"):
            return deck

        def fake_render_pptx(pptx, output_dir, dpi=150):
            events.append(("pptx-render", Path(output_dir).name))
            raise RuntimeError("Render dependencies are not ready. Run `slide-skill render-doctor` for details.")

        def fake_render_svg_previews(project, output_dir):
            events.append(("svg-preview", Path(output_dir).name))
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            image = Path(output_dir) / "slide-01.png"
            image.write_bytes(b"png")
            return [image]

        def fake_visual_feedback(project, rendered_dir=None, **kwargs):
            events.append(("critic", Path(rendered_dir).name))
            (Path(project) / "qa" / "visual-feedback.json").write_text(json.dumps({
                "slides": [{"slide": 1, "severity": "ok"}]
            }), encoding="utf-8")
            (Path(project) / "qa" / "VISUAL-REVIEW.md").write_text(
                "## Slide 1\n- OK\n",
                encoding="utf-8",
            )
            return Path(project) / "qa" / "visual-feedback.json", Path(project) / "qa" / "VISUAL-REVIEW.md"

        def fake_run_qa(project, pptx_path=None, require_visual=False, require_fix_verify=False):
            report = Path(project) / "qa" / "QA.md"
            report.write_text("status: automated-passed\n", encoding="utf-8")
            return True, report

        monkeypatch.setattr("slide_skill.cli.export_project", fake_export)
        monkeypatch.setattr("slide_skill.cli.render_pptx", fake_render_pptx)
        monkeypatch.setattr("slide_skill.cli.render_svg_previews", fake_render_svg_previews)
        monkeypatch.setattr("slide_skill.cli.run_qa", fake_run_qa)
        monkeypatch.setattr("slide_skill.visual_critic.generate_visual_feedback", fake_visual_feedback)

        result = main([
            "iterate-ai",
            str(p),
            "--ai-base-url",
            "http://127.0.0.1:11434/v1",
            "--vision-model",
            "vision-model",
        ])

        assert result == 0
        assert ("pptx-render", "rendered-round-01") in events
        assert ("svg-preview", "rendered-round-01") in events
        assert ("critic", "rendered-round-01") in events

    def test_iterate_ai_writes_fix_verify_before_strict_qa(self, tmp_path, monkeypatch):
        from slide_skill.cli import main

        p = _make_project(tmp_path)
        deck = p / "exports" / "deck.pptx"
        deck.parent.mkdir(exist_ok=True)
        deck.write_bytes(b"pptx")
        (p / "svg_output" / "slide_01.svg").write_text(_valid_svg(), encoding="utf-8")
        (p / "svg_final" / "slide_01.svg").write_text(_valid_svg(), encoding="utf-8")
        qa_calls = []

        def fake_export(project, output=None, stage="final"):
            return deck

        def fake_render(pptx, output_dir, dpi=150):
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            image = Path(output_dir) / "slide-1.jpg"
            image.write_bytes(b"jpg")
            return [image]

        critic_calls = 0

        def fake_visual_feedback(project, rendered_dir=None, **kwargs):
            nonlocal critic_calls
            critic_calls += 1
            severity = "major" if critic_calls == 1 else "ok"
            (Path(project) / "qa" / "visual-feedback.json").write_text(json.dumps({
                "slides": [{
                    "slide": 1,
                    "severity": severity,
                    "summary": "Final review is clean." if severity == "ok" else "Spacing needs repair.",
                    "issues": [] if severity == "ok" else ["Spacing is too tight."],
                    "actions": [] if severity == "ok" else ["Increase breathing room."],
                    "repair_prompt": "" if severity == "ok" else "Increase spacing around the bullet group.",
                }]
            }), encoding="utf-8")
            (Path(project) / "qa" / "VISUAL-REVIEW.md").write_text(
                f"## Slide 1\n- {severity}\n",
                encoding="utf-8",
            )
            return Path(project) / "qa" / "visual-feedback.json", Path(project) / "qa" / "VISUAL-REVIEW.md"

        def fake_generate(project, plans, clear_output=False, **kwargs):
            path = Path(project) / "svg_output" / "slide_01.svg"
            path.write_text(_valid_svg(), encoding="utf-8")
            return [path]

        def fake_finalize(project):
            return [Path(project) / "svg_final" / "slide_01.svg"]

        def fake_run_qa(project, pptx_path=None, require_visual=False, require_fix_verify=False):
            fix_verify = Path(project) / "qa" / "FIX-VERIFY.md"
            qa_calls.append((require_visual, require_fix_verify, fix_verify.exists()))
            report = Path(project) / "qa" / "QA.md"
            report.write_text("status: passed\n", encoding="utf-8")
            return True, report

        monkeypatch.setattr("slide_skill.cli.export_project", fake_export)
        monkeypatch.setattr("slide_skill.cli.render_pptx", fake_render)
        monkeypatch.setattr("slide_skill.cli.finalize_svg", fake_finalize)
        monkeypatch.setattr("slide_skill.cli.run_qa", fake_run_qa)
        monkeypatch.setattr("slide_skill.visual_critic.generate_visual_feedback", fake_visual_feedback)
        monkeypatch.setattr("slide_skill.ai_executor.generate_svg_with_ai", fake_generate)

        result = main([
            "iterate-ai",
            str(p),
            "--ai-base-url",
            "http://127.0.0.1:11434/v1",
            "--strict-qa",
        ])

        fix_verify = (p / "qa" / "FIX-VERIFY.md").read_text(encoding="utf-8")
        iteration = json.loads((p / "qa" / "AI-ITERATION.json").read_text(encoding="utf-8"))
        assert result == 0
        assert qa_calls == [(True, True, True)]
        assert "Generated by `slide-skill iterate-ai`." in fix_verify
        assert "Latest AI visual feedback max severity: ok" in fix_verify
        assert "Latest AI visual feedback stats: 1 slide(s), 0 issue(s), 0 non-ok slide(s), 0 repair prompt(s), 0 actionable repair(s)" in fix_verify
        assert "slide 1: Final review is clean." in fix_verify
        assert "Repaired `slide_01.svg`" in fix_verify
        assert iteration["status"] == "passed"
        assert iteration["strict_qa"] is True
        assert iteration["latest_visual_severity"] == "ok"
        assert iteration["latest_visual_feedback"]["slides_reviewed"] == 1
        assert iteration["latest_visual_feedback"]["issue_count"] == 0
        assert iteration["latest_visual_feedback"]["repair_prompt_count"] == 0
        assert iteration["latest_visual_feedback"]["actionable_repair_count"] == 0
        assert iteration["latest_rendered_source"] == "pptx-render"
        assert set(iteration["models"]) == {"executor", "vision"}
        assert iteration["trace_events"] <= iteration["total_trace_events"]
        assert "total_metrics" in iteration
        assert iteration["fix_verify"].endswith("FIX-VERIFY.md")
        assert iteration["repair_cycles"][0]["rendered_source"] == "pptx-render"
        assert iteration["repair_cycles"][0]["repaired"][0]["generated"].endswith("slide_01.svg")

    def test_visual_feedback_stats_counts_action_only_repairs(self, tmp_path):
        from slide_skill.cli import _ai_iteration_summary_hint, _visual_feedback_stats

        p = _make_project(tmp_path)
        feedback_path = p / "qa" / "visual-feedback.json"
        feedback_path.write_text(json.dumps({
            "slides": [
                {
                    "slide": 1,
                    "severity": "major",
                    "summary": "Title is clipped.",
                    "issues": ["Title touches top edge"],
                    "actions": ["Move the title block down by at least 32 px."],
                    "repair_prompt": "",
                },
                {
                    "slide": 2,
                    "severity": "ok",
                    "summary": "Slide is clean.",
                    "issues": [],
                    "actions": [],
                    "repair_prompt": "",
                },
            ]
        }), encoding="utf-8")

        stats = _visual_feedback_stats(feedback_path)
        hint = _ai_iteration_summary_hint({
            "status": "failed",
            "latest_visual_severity": "major",
            "latest_visual_feedback": stats,
        })

        assert stats["repair_prompt_count"] == 0
        assert stats["actionable_repair_count"] == 1
        assert hint == "failed:major,issues=1,non-ok=1,actionable=1"

    def test_visual_feedback_stats_counts_scalar_action(self, tmp_path):
        from slide_skill.cli import _visual_feedback_stats

        p = _make_project(tmp_path)
        feedback_path = p / "qa" / "visual-feedback.json"
        feedback_path.write_text(json.dumps({
            "slides": [
                {
                    "slide": 1,
                    "severity": "major",
                    "summary": "Title is clipped.",
                    "issues": ["Title touches top edge"],
                    "action": "Move the title block down by at least 32 px.",
                    "repair_prompt": "",
                },
                {
                    "slide": 2,
                    "severity": "major",
                    "summary": "Body copy overlaps.",
                    "issues": ["Body copy overlaps"],
                    "actions": ["Move the body group lower."],
                    "action": "Do not double count this fallback action.",
                    "repair_prompt": "",
                },
            ]
        }), encoding="utf-8")

        stats = _visual_feedback_stats(feedback_path)

        assert stats["action_count"] == 2
        assert stats["repair_prompt_count"] == 0
        assert stats["actionable_repair_count"] == 2

    def test_iterate_ai_reports_trace_hint_on_critic_failure(self, tmp_path, monkeypatch, capsys):
        from slide_skill.cli import main
        from slide_skill.ai_trace import write_ai_trace

        p = _make_project(tmp_path)
        deck = p / "exports" / "deck.pptx"
        deck.parent.mkdir(exist_ok=True)
        deck.write_bytes(b"pptx")

        def fake_export(project, output=None, stage="final"):
            return deck

        def fake_render(pptx, output_dir, dpi=150):
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            image = Path(output_dir) / "slide-1.jpg"
            image.write_bytes(b"jpg")
            return [image]

        def fake_visual_feedback(project, rendered_dir=None, **kwargs):
            write_ai_trace(
                project,
                stage="visual-critic",
                model=kwargs.get("model") or "vision-model",
                status="failed",
                attempt=1,
                metadata={
                    "slide": 1,
                    "error": "repair_prompt must be specific enough for the SVG executor.",
                },
            )
            raise RuntimeError("failed quality gate for slide 1 after 1 attempt(s)")

        monkeypatch.setattr("slide_skill.cli.export_project", fake_export)
        monkeypatch.setattr("slide_skill.cli.render_pptx", fake_render)
        monkeypatch.setattr("slide_skill.visual_critic.generate_visual_feedback", fake_visual_feedback)

        result = main([
            "iterate-ai",
            str(p),
            "--ai-base-url",
            "http://127.0.0.1:11434/v1",
            "--vision-model",
            "vision-model",
        ])

        stderr = capsys.readouterr().err
        assert result == 1
        assert "failed quality gate for slide 1 after 1 attempt(s)" in stderr
        assert f"slide-skill ai-trace {p}" in stderr
        assert "last-ai-failure: stage=visual-critic | status=failed | attempt=1 | model=vision-model | slide=1" in stderr

    def test_iterate_ai_require_visual_ok_fails_on_minor_feedback(self, tmp_path, monkeypatch, capsys):
        from slide_skill.cli import main
        from slide_skill.ai_trace import write_ai_trace

        p = _make_project(tmp_path)
        deck = p / "exports" / "deck.pptx"
        deck.parent.mkdir(exist_ok=True)
        deck.write_bytes(b"pptx")
        write_ai_trace(
            p,
            stage="executor",
            model="old-model",
            status="failed",
            attempt=1,
            metadata={"slide": 1, "blocking_issues": ["historical failure"]},
        )

        def fake_export(project, output=None, stage="final"):
            return deck

        def fake_render(pptx, output_dir, dpi=150):
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            image = Path(output_dir) / "slide-1.jpg"
            image.write_bytes(b"jpg")
            return [image]

        def fake_visual_feedback(project, rendered_dir=None, **kwargs):
            write_ai_trace(
                project,
                stage="visual-critic",
                model=kwargs.get("model") or "vision-model",
                status="passed",
                attempt=1,
                metadata={"slide": 1, "severity": "minor"},
            )
            (Path(project) / "qa" / "visual-feedback.json").write_text(json.dumps({
                "slides": [{
                    "slide": 1,
                    "severity": "minor",
                    "summary": "Small spacing issue remains.",
                    "issues": ["Bullet spacing is slightly tight."],
                    "actions": ["Add a little breathing room."],
                    "repair_prompt": "Add a little breathing room around the bullet group.",
                }]
            }), encoding="utf-8")
            (Path(project) / "qa" / "VISUAL-REVIEW.md").write_text("## Slide 1\n- minor\n", encoding="utf-8")
            return Path(project) / "qa" / "visual-feedback.json", Path(project) / "qa" / "VISUAL-REVIEW.md"

        def fake_run_qa(project, pptx_path=None, require_visual=False, require_fix_verify=False):
            assert require_visual is True
            assert require_fix_verify is False
            report = Path(project) / "qa" / "QA.md"
            report.write_text("status: passed\n", encoding="utf-8")
            return True, report

        monkeypatch.setattr("slide_skill.cli.export_project", fake_export)
        monkeypatch.setattr("slide_skill.cli.render_pptx", fake_render)
        monkeypatch.setattr("slide_skill.cli.run_qa", fake_run_qa)
        monkeypatch.setattr("slide_skill.visual_critic.generate_visual_feedback", fake_visual_feedback)

        result = main([
            "iterate-ai",
            str(p),
            "--ai-base-url",
            "http://127.0.0.1:11434/v1",
            "--min-severity",
            "major",
            "--require-visual-ok",
        ])

        stderr = capsys.readouterr().err
        iteration = json.loads((p / "qa" / "AI-ITERATION.json").read_text(encoding="utf-8"))
        assert result == 1
        assert "visual-ok gate failed: latest visual severity is minor" in stderr
        assert f"diagnose-latest: slide-skill ai-trace {p} --latest-iteration --diagnose" in stderr
        assert "last-ai-quality-gate: stage=visual-critic | status=passed | attempt=1 | model=vision-model | slide=1" in stderr
        assert "old-model" not in stderr
        assert iteration["status"] == "failed"
        assert iteration["require_visual_ok"] is True
        assert iteration["strict_qa"] is False
        assert iteration["latest_visual_severity"] == "minor"
        assert iteration["latest_visual_feedback"]["issue_count"] == 1
        assert iteration["repair_target_count"] == 1
        assert iteration["repair_targets"] == [{
            "slide": "1",
            "severity": "minor",
            "summary": "Small spacing issue remains.",
            "repair": "Add a little breathing room around the bullet group.",
            "repair_source": "repair_prompt",
        }]
        assert iteration["repair_command"] == f"slide-skill repair-feedback {p} --min-severity minor"

    def test_ai_failure_ignores_stale_iteration_result_for_trace_hint(self, tmp_path, capsys):
        from slide_skill.cli import _report_ai_command_failure
        from slide_skill.ai_trace import write_ai_trace

        p = _make_project(tmp_path)
        write_ai_trace(
            p,
            stage="visual-critic",
            model="old-vision",
            status="passed",
            attempt=1,
            metadata={"slide": 1, "severity": "minor"},
        )
        (p / "qa" / "AI-ITERATION.json").write_text(json.dumps({
            "trace_start": 0,
            "total_trace_events": 1,
            "status": "failed",
        }), encoding="utf-8")
        write_ai_trace(
            p,
            stage="executor",
            model="current-executor",
            status="failed",
            attempt=1,
            metadata={"slide": 1, "blocking_count": 1},
        )

        _report_ai_command_failure(p, RuntimeError("current executor failure"))

        stderr = capsys.readouterr().err
        assert "diagnose-latest:" not in stderr
        assert "last-ai-failure: stage=executor | status=failed | attempt=1 | model=current-executor | slide=1 | blocking_count=1" in stderr
        assert "old-vision" not in stderr

    def test_ai_failure_ignores_current_iteration_result_for_non_iteration_error(self, tmp_path, capsys):
        from slide_skill.cli import _report_ai_command_failure
        from slide_skill.ai_trace import write_ai_trace

        p = _make_project(tmp_path)
        write_ai_trace(
            p,
            stage="visual-critic",
            model="old-vision",
            status="passed",
            attempt=1,
            metadata={"slide": 1, "severity": "minor"},
        )
        write_ai_trace(
            p,
            stage="executor",
            model="current-executor",
            status="failed",
            attempt=1,
            metadata={"slide": 1, "blocking_count": 1},
        )
        (p / "qa" / "AI-ITERATION.json").write_text(json.dumps({
            "trace_start": 0,
            "total_trace_events": 2,
            "status": "failed",
        }), encoding="utf-8")

        _report_ai_command_failure(p, RuntimeError("current executor failure"))

        stderr = capsys.readouterr().err
        assert "diagnose-latest:" not in stderr
        assert "last-ai-failure: stage=executor | status=failed | attempt=1 | model=current-executor | slide=1 | blocking_count=1" in stderr


# ─── Change 1a: reference materials no longer truncated ──────────────

class TestReferenceMaterialsBudget:
    """Verify the executor now reads full reference docs instead of truncating
    each to 2000 chars (which discarded most of the ported ppt-master corpus)."""

    def test_core_references_loaded_in_full(self, tmp_path):
        p = _make_project(tmp_path)
        ref_dir = p / "references"
        ref_dir.mkdir()
        # A core reference well over the old 2000-char truncation point.
        long_body = "Base composition rules. " * 200  # ~4600 chars
        (ref_dir / "executor-base.md").write_text(long_body)
        (ref_dir / "shared-standards.md").write_text("Shared SVG contract. " * 200)

        refs = _load_reference_materials(p)

        # The body must appear complete — not cut off by the old 2000-char limit.
        assert "executor-base.md" in refs
        assert "(truncated)" not in refs
        # The full content survived (the old code would have sliced at 2000).
        assert long_body in refs

    def test_academic_variant_loaded_when_hint_present(self, tmp_path):
        p = _make_project(tmp_path)
        ref_dir = p / "references"
        ref_dir.mkdir()
        (ref_dir / "executor-base.md").write_text("core base")
        (ref_dir / "shared-standards.md").write_text("core standards")
        (ref_dir / "executor-general.md").write_text("general guidance body")
        (ref_dir / "executor-academic.md").write_text("academic citation rules")

        spec_lock = {"design_hints": "Academic thesis deck with formal citations"}
        refs = _load_reference_materials(p, spec_lock)

        assert "academic citation rules" in refs
        # The general variant must NOT also be loaded (they are mutually exclusive).
        assert "general guidance body" not in refs

    def test_general_variant_loaded_by_default(self, tmp_path):
        p = _make_project(tmp_path)
        ref_dir = p / "references"
        ref_dir.mkdir()
        (ref_dir / "executor-base.md").write_text("core base")
        (ref_dir / "shared-standards.md").write_text("core standards")
        (ref_dir / "executor-general.md").write_text("general guidance body")

        # No academic hints → general variant is the fallback.
        refs = _load_reference_materials(p, {"design_hints": "marketing pitch"})
        assert "general guidance body" in refs

    def test_budget_caps_optional_references_not_core(self, tmp_path):
        p = _make_project(tmp_path)
        ref_dir = p / "references"
        ref_dir.mkdir()
        # Core references sized so there is room for an optional reference too.
        (ref_dir / "executor-base.md").write_text("B" * 3000)
        (ref_dir / "shared-standards.md").write_text("S" * 2000)
        (ref_dir / "executor-general.md").write_text("G" * 6000)

        refs = _load_reference_materials(p, {"design_hints": "generic"})
        # Core references always survive intact, even when budget is tight.
        assert "B" * 3000 in refs
        assert "S" * 2000 in refs
        # Optional general reference is present (fits within remaining budget).
        assert "executor-general.md" in refs

    def test_optional_reference_trimmed_when_over_remaining_budget(self, tmp_path):
        p = _make_project(tmp_path)
        ref_dir = p / "references"
        ref_dir.mkdir()
        # Core leaves little room; optional is too big to fit → it gets trimmed.
        (ref_dir / "executor-base.md").write_text("B" * 4000)
        (ref_dir / "shared-standards.md").write_text("S" * 4000)
        (ref_dir / "executor-general.md").write_text("G" * 8000)

        refs = _load_reference_materials(p, {"design_hints": "generic"})
        # Core intact.
        assert "B" * 4000 in refs
        assert "S" * 4000 in refs
        # Optional present but trimmed (core already consumed ~8k of the 12k budget).
        assert "executor-general.md" in refs
        assert "trimmed to fit context budget" in refs

    def test_core_references_always_priority_when_over_budget(self, tmp_path):
        p = _make_project(tmp_path)
        ref_dir = p / "references"
        ref_dir.mkdir()
        # Core alone exceeds the budget → optional must be dropped entirely.
        (ref_dir / "executor-base.md").write_text("B" * 8000)
        (ref_dir / "shared-standards.md").write_text("S" * 5000)
        (ref_dir / "executor-general.md").write_text("G" * 6000)

        refs = _load_reference_materials(p, {"design_hints": "generic"})
        # Core references survive intact; core is never sacrificed.
        assert "B" * 8000 in refs
        assert "S" * 5000 in refs


# ─── Change 1b: design guide budget raised from 3000 to 8000 ─────────

class TestDesignGuideBudget:
    def test_long_design_guide_preserved_up_to_budget(self):
        # ~10k chars: the old 3000 cap would have cut 70% of it.
        guide = "# Design Guide\n" + ("Use the locked palette. " * 400)
        prompt = _build_system_prompt(
            {"palette": {"background": "#FFF"}, "font_family": "Arial"},
            1280, 720,
            design_guide=guide,
        )
        assert "Design Guide" in prompt
        assert "(design guide trimmed to fit context budget)" in prompt
        # The first ~8000 chars of the guide are present.
        assert guide[:7000] in prompt

    def test_short_design_guide_in_full(self):
        guide = "# Design Guide\nShort and sweet."
        prompt = _build_system_prompt(
            {"palette": {"background": "#FFF"}, "font_family": "Arial"},
            1280, 720,
            design_guide=guide,
        )
        assert "Short and sweet." in prompt
        assert "trimmed" not in prompt


# ─── Change 1d: per-page layout diversity hint ───────────────────────

class TestLayoutDiversityHint:
    def _write_slide(self, path: Path, group_ids: list[str]) -> None:
        groups = "".join(f'<g id="{gid}"/>' for gid in group_ids)
        path.write_text(
            f'<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">{groups}</svg>',
            encoding="utf-8",
        )

    def test_signature_extracted_from_generated_slide(self, tmp_path):
        f = tmp_path / "slide_01.svg"
        self._write_slide(f, ["background", "content-title-01", "content-body-01", "chrome-footer"])
        sig = _read_layout_signature(f)
        assert "content-title" in sig
        assert "content-body" in sig
        # Page-number suffixes are stripped so structure, not index, is compared.
        assert "content-title-01" not in sig

    def test_hint_emitted_when_recent_pages_repeat(self, tmp_path):
        f1, f2 = tmp_path / "slide_01.svg", tmp_path / "slide_02.svg"
        self._write_slide(f1, ["background", "content-title", "content-body"])
        self._write_slide(f2, ["background", "content-title", "content-body"])
        hint = _build_layout_diversity_hint([f1, f2])
        assert "Layout Variety Constraint" in hint
        assert "MANDATORY" in hint

    def test_no_hint_when_layouts_differ(self, tmp_path):
        f1, f2 = tmp_path / "slide_01.svg", tmp_path / "slide_02.svg"
        self._write_slide(f1, ["background", "content-title", "content-body"])
        self._write_slide(f2, ["background", "content-metric", "content-right"])
        hint = _build_layout_diversity_hint([f1, f2])
        assert hint == ""

    def test_page_prompt_includes_diversity_hint_after_repeats(self, tmp_path):
        f1, f2 = tmp_path / "slide_01.svg", tmp_path / "slide_02.svg"
        self._write_slide(f1, ["background", "content-title", "content-body"])
        self._write_slide(f2, ["background", "content-title", "content-body"])
        plan = _make_plan(index=3)
        prompt = _build_page_prompt(
            plan, 3,
            {"palette": {"background": "#FFF", "accent": "#3B82F6"}, "font_family": "Arial"},
            "", 1280, 720, [f1, f2],
        )
        assert "Layout Variety Constraint" in prompt

    def test_page_prompt_shows_prior_signatures(self, tmp_path):
        f1 = tmp_path / "slide_01.svg"
        self._write_slide(f1, ["background", "content-title", "content-body"])
        plan = _make_plan(index=2)
        prompt = _build_page_prompt(
            plan, 3,
            {"palette": {"background": "#FFF", "accent": "#3B82F6"}, "font_family": "Arial"},
            "", 1280, 720, [f1],
        )
        assert "layout signature:" in prompt


# ─── Change 3b: auto-wrap repair of overflowing text ─────────────────

class TestAutoWrapRepair:
    """The executor now locally re-wraps overflowing text (mirroring the
    deterministic path's fitted_tspans/kinsoku) instead of spending an LLM
    retry on a problem the model frequently reproduces."""

    def test_no_overflow_messages_returns_none(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"/>'
        result = _auto_wrap_overflowing_text(svg, ["Some other error"], 1280, 720)
        assert result is None

    def test_overflowing_text_rewrapped_into_tspans(self):
        # A single long text run that overshoots the right canvas edge.
        long_text = "This is a very long title that definitely overflows the right edge of the canvas " * 3
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            f'<g id="content-title-01"><text x="80" y="120" font-size="44" fill="#F8FAFC">{long_text}</text></g>'
            "</svg>"
        )
        # The overflow message includes the leading snippet of the offending text.
        msg = f'Text may overflow right edge: x_right≈2000px > canvas 1280px (text: "{long_text[:40]}...")'
        patched = _auto_wrap_overflowing_text(svg, [msg], 1280, 720)
        assert patched is not None
        # The patch must introduce tspan children to wrap the text.
        assert "<tspan" in patched
        # The original long text content survives (just reflowed across tspans).
        assert long_text[:30] in patched

    def test_unparsable_svg_returns_none(self):
        result = _auto_wrap_overflowing_text("not xml at all", ["Text may overflow right edge"], 1280, 720)
        assert result is None

    def test_non_overflow_blocking_issue_not_patched(self):
        # The patcher only acts on overflow messages it can extract a snippet from.
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            '<g id="content-title-01"><text x="80" y="120" font-size="44" fill="#F8FAFC">Short</text></g>'
            "</svg>"
        )
        result = _auto_wrap_overflowing_text(svg, ["Some unrelated blocking issue"], 1280, 720)
        assert result is None


# ─── Change 3a+3b: contrast auto-repair ──────────────────────────────────────

class TestAutoContrastRepair:
    """The executor now locally upgrades low-contrast fills to higher-contrast palette
    roles (mirroring 43f9bca's muted->body fix and _auto_wrap_overflowing_text)
    instead of spending an LLM retry on a problem the model frequently reproduces."""

    SPEC = {
        "palette": {
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F8FAFC",
            "body": "#94A3B8",
            "accent": "#3B82F6",
            "muted": "#334155",
        },
    }

    def _svg(self, body: str, **text_attrs) -> str:
        attrs = "".join(f' {k}="{v}"' for k, v in text_attrs.items())
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            f'<g id="content-body-01"><text x="80" y="120"{attrs}>{body}</text></g>'
            "</svg>"
        )

    def test_no_contrast_messages_returns_none(self):
        svg = self._svg("hello", fill="#F8FAFC")
        # No "Low text contrast" message -> nothing to repair.
        result = _auto_repair_low_contrast(svg, ["Some other error"], self.SPEC)
        assert result is None

    def test_low_contrast_muted_fill_upgraded_to_body(self):
        # #334155 (muted) on #0F172A is ~1.7:1 (unreadable); #94A3B8 (body) is ~6:1.
        svg = self._svg("unreadable body text", fill="#334155", **{"font-size": "20"})
        msg = ("Low text contrast: body text #334155 on #0F172A is 1.72:1 "
                 "(need >=4.5); use a higher-contrast palette role")
        patched = _auto_repair_low_contrast(svg, [msg], self.SPEC)
        assert patched is not None
        # The muted fill was upgraded to body.
        assert "#94A3B8" in patched
        assert "#334155" not in patched
        # Text content is preserved (only fill changed).
        assert "unreadable body text" in patched

    def test_non_palette_fill_returns_none(self):
        # An invented hex is not a known palette role -> cannot safely upgrade, give up.
        svg = self._svg("invented color text", fill="#ABCDEF", **{"font-size": "20"})
        msg = "Low text contrast: body text #ABCDEF on #0F172A is 1.20:1 (need >=4.5)"
        result = _auto_repair_low_contrast(svg, [msg], self.SPEC)
        assert result is None

    def test_translucent_text_skipped(self):
        # fill-opacity < 0.5 signals decorative intent; must not be upgraded.
        svg = self._svg("watermark", fill="#334155", **{"font-size": "20", "fill-opacity": "0.3"})
        msg = "Low text contrast: body text #334155 on #0F172A is 1.72:1 (need >=4.5)"
        result = _auto_repair_low_contrast(svg, [msg], self.SPEC)
        assert result is None

    def test_decorative_font_size_skipped(self):
        # font-size >= 48 is likely a decorative hero numeral; must not be upgraded.
        svg = self._svg("42", fill="#334155", **{"font-size": "48"})
        msg = "Low text contrast: large/title text #334155 on #0F172A is 1.72:1 (need >=3.0)"
        result = _auto_repair_low_contrast(svg, [msg], self.SPEC)
        assert result is None

    def test_multi_element_shared_fill_repaired_once(self):
        # A <g fill="#334155"> wrapping many text nodes: patch the group once.
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            '<g id="content-body-01" fill="#334155" font-size="20">'
            '<text x="80" y="120">first line</text>'
            '<text x="80" y="160">second line</text>'
            '<text x="80" y="200">third line</text>'
            "</g></svg>"
        )
        msg = "Low text contrast: body text #334155 on #0F172A is 1.72:1 (need >=4.5)"
        patched = _auto_repair_low_contrast(svg, [msg], self.SPEC)
        assert patched is not None
        # The group fill was upgraded; no #334155 remains anywhere.
        assert "#94A3B8" in patched
        assert "#334155" not in patched
        # All three text nodes survive.
        assert "first line" in patched
        assert "second line" in patched
        assert "third line" in patched

    def test_non_repairable_background_skipped(self):
        # The checker resolves the text's background to the nearest opaque ancestor
        # rect. When that rect is a custom color not in {background, surface,
        # bg_secondary}, the repair refuses to act (ambiguous canvas) and leaves
        # the slide to the LLM. Here the card rect is an off-palette #64748B.
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            '<g id="content-body-01">'
            '<rect x="80" y="80" width="500" height="200" fill="#64748B"/>'
            '<text x="100" y="120" font-size="20" fill="#334155">on off-palette card</text>'
            "</g></svg>"
        )
        msg = "Low text contrast: body text #334155 on #64748B is 1.72:1 (need >=4.5)"
        result = _auto_repair_low_contrast(svg, [msg], self.SPEC)
        assert result is None

    # ── Phase 2: accent_tint repair path ──────────────────────────────────

    def test_tinted_body_text_repaired_to_readable_role(self):
        # The dominant real-world defect (58% of the contrast baseline):
        # body text painted with accent_tint (#3B82F620, ~12% opacity) is
        # nearly invisible. The alpha-aware checker now flags it; this test
        # confirms the repair then upgrades the tint to a readable role.
        # _resolve_text_fill strips the alpha, so the offending fill resolves
        # to the accent role (#3B82F6), which the ladder upgrades to text.
        spec = {
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
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/></g>'
            '<g id="content-body-01">'
            '<text x="100" y="120" font-size="20" fill="#3B82F620">invisible tinted body</text>'
            "</g></svg>"
        )
        msg = ("Low text contrast: body text #E6EFFE (translucent #3B82F6 reads as #E6EFFE) "
                 "on #FFFFFF is 1.16:1 (need >=4.5); use a higher-contrast palette role")
        patched = _auto_repair_low_contrast(svg, [msg], spec)
        assert patched is not None
        # The tint was upgraded to the high-contrast text role.
        assert "#1A1A2E" in patched
        # The raw tint hex is gone from the text fill.
        assert "#3B82F620" not in patched
        # Content is preserved.
        assert "invisible tinted body" in patched


# ─── 49-02: namespace-safe validated auto-repairs ────────────────────────────

class TestNamespaceSafeValidatedRepair:
    """REDESIGN_v5 1.2F.6-7: repairs used to serialize as <ns0:svg> (black
    render in browsers) and overwrote the attempt file before validation.
    Both repairers now serialize through _serialize_svg and only replace the
    original after the candidate re-passes QA and preserves visible text."""

    SPEC = {
        "palette": {
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F8FAFC",
            "body": "#94A3B8",
            "accent": "#3B82F6",
            "muted": "#334155",
        },
    }

    CONTRAST_MSG = ("Low text contrast: body text #334155 on #0F172A is 1.72:1 "
                    "(need >=4.5); use a higher-contrast palette role")

    def _low_contrast_svg(self) -> str:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            '<g id="content-body-01">'
            '<text x="80" y="120" font-size="20" fill="#334155">unreadable body text</text>'
            "</g></svg>"
        )

    def test_contrast_repair_never_emits_ns0_prefix(self):
        patched = _auto_repair_low_contrast(self._low_contrast_svg(), [self.CONTRAST_MSG], self.SPEC)
        assert patched is not None
        assert patched.lstrip().startswith("<svg")
        assert 'xmlns="http://www.w3.org/2000/svg"' in patched
        assert "ns0:" not in patched

    def test_wrap_repair_never_emits_ns0_prefix(self):
        long_text = "This is a very long title that definitely overflows the right edge of the canvas " * 3
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
            '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            f'<g id="content-title-01"><text x="80" y="120" font-size="44" fill="#F8FAFC">{long_text}</text></g>'
            "</svg>"
        )
        msg = f'Text may overflow right edge: x_right≈2000px > canvas 1280px (text: "{long_text[:40]}...")'
        patched = _auto_wrap_overflowing_text(svg, [msg], 1280, 720)
        assert patched is not None
        assert patched.lstrip().startswith("<svg")
        assert 'xmlns="http://www.w3.org/2000/svg"' in patched
        assert "ns0:" not in patched
        assert "<tspan" in patched

    def test_serialize_svg_registers_default_namespace(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(self._low_contrast_svg())
        serialized = _serialize_svg(root)
        assert serialized.lstrip().startswith("<svg")
        assert "ns0:" not in serialized

    def _attempt_file(self, project, svg: str):
        attempt_dir = project / "qa" / "executor" / "attempt-svg"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        attempt = attempt_dir / "slide_01_attempt_01.svg"
        attempt.write_text(svg, encoding="utf-8")
        return attempt

    def test_accepted_repair_replaces_file_without_ns0(self, tmp_path, monkeypatch):
        p = _make_project(tmp_path)
        original = self._low_contrast_svg()
        attempt = self._attempt_file(p, original)
        monkeypatch.setattr(
            "slide_skill.ai_executor._browser_render_gate",
            lambda path: (True, "mocked"),
        )

        patched = _auto_repair_low_contrast(original, [self.CONTRAST_MSG], self.SPEC)
        assert patched is not None
        accepted, issues = _apply_validated_repair(
            p, attempt, original, patched,
            plan=None,
            visual_feedback="",
            run_qa=False,
            strict_quality=True,
            repair_kind="auto-contrast",
            model="test-model",
            attempt=1,
            slide_index=1,
        )

        assert accepted
        content = attempt.read_text(encoding="utf-8")
        assert content.lstrip().startswith("<svg")
        assert 'xmlns="http://www.w3.org/2000/svg"' in content
        assert "ns0:" not in content
        assert "#94A3B8" in content
        # The candidate temp file was consumed by the atomic replace.
        assert not attempt.with_name(attempt.name + ".patch-candidate").exists()

    def test_rejected_repair_keeps_original_bytes_and_traces(self, tmp_path, monkeypatch):
        from slide_skill.svg_qa import SvgIssue

        p = _make_project(tmp_path)
        original = self._low_contrast_svg()
        attempt = self._attempt_file(p, original)
        original_bytes = attempt.read_bytes()

        def failing_validation(*args, **kwargs):
            return [SvgIssue("error", str(attempt), "forced candidate failure")]

        monkeypatch.setattr(
            "slide_skill.ai_executor._validate_svg_attempt", failing_validation,
        )

        patched = _auto_repair_low_contrast(original, [self.CONTRAST_MSG], self.SPEC)
        assert patched is not None
        accepted, issues = _apply_validated_repair(
            p, attempt, original, patched,
            plan=None,
            visual_feedback="",
            run_qa=False,
            strict_quality=True,
            repair_kind="auto-contrast",
            model="test-model",
            attempt=1,
            slide_index=1,
        )

        assert not accepted
        assert issues == []
        # Original attempt file is byte-identical (failure evidence preserved).
        assert attempt.read_bytes() == original_bytes
        # Candidate temp file was cleaned up.
        assert not attempt.with_name(attempt.name + ".patch-candidate").exists()
        # A repair-rejected trace event records the reason.
        trace_lines = (p / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in trace_lines if line.strip()]
        rejected = [event for event in events if event.get("status") == "repair-rejected"]
        assert rejected
        assert rejected[-1]["metadata"]["repair"] == "auto-contrast"
        assert "forced candidate failure" in rejected[-1]["metadata"]["reason"]

    def test_text_preservation_gate_rejects_content_loss(self, tmp_path, monkeypatch):
        p = _make_project(tmp_path)
        original = self._low_contrast_svg()
        attempt = self._attempt_file(p, original)
        original_bytes = attempt.read_bytes()

        # A "repair" that silently drops the visible text: structural QA still
        # passes, so only the text-preservation gate can catch it.
        dropped = original.replace(
            '<text x="80" y="120" font-size="20" fill="#334155">unreadable body text</text>',
            '<text x="80" y="120" font-size="20" fill="#94A3B8">different text entirely</text>',
        )

        accepted, _ = _apply_validated_repair(
            p, attempt, original, dropped,
            plan=None,
            visual_feedback="",
            run_qa=False,
            strict_quality=True,
            repair_kind="auto-contrast",
            model="test-model",
            attempt=1,
            slide_index=1,
        )

        assert not accepted
        assert attempt.read_bytes() == original_bytes
        trace_lines = (p / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
        events = [json.loads(line) for line in trace_lines if line.strip()]
        rejected = [event for event in events if event.get("status") == "repair-rejected"]
        assert rejected
        assert "visible text" in rejected[-1]["metadata"]["reason"]

    def test_repair_preserves_visible_text_helper(self):
        original = self._low_contrast_svg()
        # Fill-only change preserves the text set.
        recolored = original.replace("#334155", "#94A3B8")
        assert _repair_preserves_visible_text(original, recolored)
        # Re-wrapping into tspans preserves the text set (wrap tolerance).
        wrapped = original.replace(
            ">unreadable body text</text>",
            '><tspan x="80" dy="0">unreadable body</tspan><tspan x="80" dy="28">text</tspan></text>',
        )
        assert _repair_preserves_visible_text(original, wrapped)
        # Dropping a text run fails the gate.
        dropped = original.replace("unreadable body text", "")
        assert not _repair_preserves_visible_text(original, dropped)

