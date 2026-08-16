from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import pytest

from slide_skill.measurement_contracts import (
    audit_closed_world_text,
    audit_executor_trace,
    audit_svg_contract,
    render_svg_smoke,
)

# The render-smoke scenarios exercise the host's real Chrome (the committed
# render evidence); they opt out of the hermetic no-browser default.
pytestmark = pytest.mark.real_browser

SOURCE = [
    "三种提示词策略对比",
    "零样本",
    "Zero-shot",
    "直接提问，不给示例，适合简单任务",
    "少样本",
    "Few-shot",
    "给出2-5个示例，显著提升格式一致性",
    "思维链",
    "CoT",
    "要求模型逐步推理，适合数学与逻辑题",
]
CARD_PAIRS = [
    ("零样本", "直接提问，不给示例，适合简单任务"),
    ("少样本", "给出2-5个示例，显著提升格式一致性"),
    ("思维链", "要求模型逐步推理，适合数学与逻辑题"),
]
PALETTE = {"#0F172A", "#1E293B", "#F1F5F9", "#94A3B8", "#3B82F6", "#29374B"}

VALID_SVG = """<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
<g id="card-1"><rect x="80" y="160" width="340" height="360" fill="#1E293B" stroke="#29374B"/>
<text x="104" y="210" fill="#F1F5F9">零样本</text><text x="104" y="260" fill="#94A3B8">Zero-shot</text>
<text x="104" y="320" fill="#F1F5F9">直接提问，不给示例，适合简单任务</text></g>
<g id="card-2"><rect x="470" y="160" width="340" height="360" fill="#1E293B" stroke="#29374B"/>
<text x="494" y="210" fill="#F1F5F9">少样本</text><text x="494" y="260" fill="#94A3B8">Few-shot</text>
<text x="494" y="320" fill="#F1F5F9">给出2-5个示例，显著提升格式一致性</text></g>
<g id="card-3"><rect x="860" y="160" width="340" height="360" fill="#1E293B" stroke="#29374B"/>
<text x="884" y="210" fill="#F1F5F9">思维链</text><text x="884" y="260" fill="#94A3B8">CoT</text>
<text x="884" y="320" fill="#F1F5F9">要求模型逐步推理，适合数学与逻辑题</text></g>
<g id="title"><text x="80" y="100" fill="#F1F5F9">三种提示词策略对比</text></g>
</svg>"""


def audit(svg: str) -> list[str]:
    defects, _ = audit_svg_contract(
        svg,
        required_text=SOURCE,
        allowed_text=SOURCE,
        allowed_colors=PALETTE,
        card_pairs=CARD_PAIRS,
        allowed_text_groups=[
            ["三种提示词策略对比"],
            ["零样本", "Zero-shot", "直接提问，不给示例，适合简单任务"],
            ["少样本", "Few-shot", "给出2-5个示例，显著提升格式一致性"],
            ["思维链", "CoT", "要求模型逐步推理，适合数学与逻辑题"],
        ],
        derived_text_patterns=[r"(?:策略)?0?[1-3]"],
    )
    return defects


class SvgContractTests(unittest.TestCase):
    def test_complete_visible_three_card_svg_passes(self):
        self.assertEqual(audit(VALID_SVG), [])

    def test_missing_descriptions_fail(self):
        svg = VALID_SVG
        for _, description in CARD_PAIRS:
            svg = svg.replace(f'<text x="104" y="320" fill="#F1F5F9">{description}</text>', "")
            svg = svg.replace(f'<text x="494" y="320" fill="#F1F5F9">{description}</text>', "")
            svg = svg.replace(f'<text x="884" y="320" fill="#F1F5F9">{description}</text>', "")
        self.assertTrue(any("missing required visible text" in issue for issue in audit(svg)))

    def test_inherited_opacity_makes_text_invisible(self):
        svg = VALID_SVG.replace('<g id="card-1">', '<g id="card-1" opacity="0">')
        defects = audit(svg)
        self.assertTrue(any("invisible text" in issue for issue in defects))
        self.assertTrue(any("missing required visible text" in issue for issue in defects))

    def test_tspan_position_is_checked_after_transform(self):
        old = '<text x="80" y="100" fill="#F1F5F9">三种提示词策略对比</text>'
        new = ('<text x="80" y="100" fill="#F1F5F9" transform="translate(10 5)">'
               '<tspan x="5000" y="5000">三种提示词策略对比</tspan></text>')
        self.assertTrue(any("outside safe area" in issue for issue in audit(VALID_SVG.replace(old, new))))

    def test_root_dimensions_and_non_palette_paint_are_rejected(self):
        svg = VALID_SVG.replace('width="1280" height="720"', 'width="1920" height="1080"')
        svg = svg.replace('fill="#1E293B"', 'fill="rgb(30,41,59)"', 1)
        defects = audit(svg)
        self.assertTrue(any("root geometry" in issue for issue in defects))
        self.assertTrue(any("prohibited paint" in issue for issue in defects))

    def test_local_gradient_is_allowed_but_external_paint_is_rejected(self):
        gradient = ('<defs><linearGradient id="surface"><stop offset="0" stop-color="#1E293B"/>'
                    '<stop offset="1" stop-color="#0F172A"/></linearGradient></defs>')
        local = VALID_SVG.replace(
            '<g id="background">',
            gradient + '<g id="background">',
        ).replace('fill="#1E293B"', 'fill="url(#surface)"', 1)
        self.assertEqual(audit(local), [])
        quoted = local.replace('url(#surface)', 'url( &quot;#surface&quot; )')
        self.assertEqual(audit(quoted), [])
        external = local.replace('url(#surface)', 'url(https://example.invalid/paint.svg#surface)')
        self.assertTrue(any("prohibited paint" in issue for issue in audit(external)))

    def test_active_content_and_external_references_are_rejected_before_render(self):
        variants = [
            VALID_SVG.replace(
                '<g id="background">',
                '<g id="background"><script>document.body.textContent="executed"</script>',
            ),
            VALID_SVG.replace('<svg width=', '<svg onload="document.body.textContent=\'executed\'" width='),
            VALID_SVG.replace(
                '<g id="background">',
                '<g id="background"><image href="https://example.invalid/pixel.png"/>',
            ),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for index, svg in enumerate(variants):
                with self.subTest(index=index):
                    self.assertTrue(any("unsafe SVG" in issue for issue in audit(svg)))
                    path = root / f"unsafe-{index}.svg"
                    path.write_text(svg, encoding="utf-8")
                    self.assertTrue(any(
                        "unsafe SVG" in issue
                        for issue in render_svg_smoke(path, root / f"unsafe-{index}.png")
                    ))

    def test_nearly_transparent_text_fails_visibility_gate(self):
        svg = VALID_SVG.replace('<text ', '<text opacity="0.01" ')
        self.assertTrue(any("invisible text" in issue for issue in audit(svg)))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "near-transparent.svg"
            path.write_text(svg, encoding="utf-8")
            self.assertTrue(any(
                "not visibly painted" in issue
                for issue in render_svg_smoke(path, root / "near-transparent.png")
            ))

    def test_implicit_black_paint_is_rejected(self):
        svg = VALID_SVG.replace(
            '<g id="title">',
            '<g id="implicit-paint"><circle cx="640" cy="600" r="20"/></g><g id="title">',
        )
        self.assertTrue(any("implicit paint" in issue for issue in audit(svg)))

    def test_stroke_only_shape_still_has_prohibited_implicit_fill(self):
        svg = VALID_SVG.replace(
            '<g id="title">',
            '<g id="stroke-only"><circle cx="640" cy="600" r="30" stroke="#F1F5F9"/></g><g id="title">',
        )
        self.assertTrue(any("implicit paint" in issue for issue in audit(svg)))

    def test_gradient_stop_requires_explicit_palette_color(self):
        gradient = '<defs><linearGradient id="bad"><stop offset="0"/></linearGradient></defs>'
        svg = VALID_SVG.replace('<g id="background">', gradient + '<g id="background">')
        self.assertTrue(any("implicit paint" in issue for issue in audit(svg)))

    def test_fill_none_inherited_from_parent_hides_text_without_override(self):
        svg = VALID_SVG.replace('<g id="card-1">', '<g id="card-1" fill="none">')
        svg = svg.replace('<text x="104" y="210" fill="#F1F5F9">零样本</text>', '<text x="104" y="210">零样本</text>')
        defects = audit(svg)
        self.assertTrue(any("invisible text" in issue for issue in defects))
        self.assertTrue(any("missing required visible text" in issue for issue in defects))

    def test_descendant_can_restore_inherited_visibility(self):
        svg = VALID_SVG.replace('<g id="card-1">', '<g id="card-1" visibility="hidden">')
        svg = svg.replace('<rect x="80"', '<rect visibility="visible" x="80"', 1)
        svg = svg.replace('<text x="104"', '<text visibility="visible" x="104"')
        self.assertEqual(audit(svg), [])

    def test_visibility_inherit_uses_visible_parent_value(self):
        svg = VALID_SVG.replace('<text x="104"', '<text visibility="inherit" x="104"')
        self.assertEqual(audit(svg), [])

    def test_missing_card_geometry_fails(self):
        svg = VALID_SVG.replace('<rect x="80" y="160" width="340" height="360" fill="#1E293B" stroke="#29374B"/>', "")
        self.assertTrue(any("card geometry" in issue for issue in audit(svg)))

    def test_tiny_decorative_rectangles_do_not_count_as_cards(self):
        svg = VALID_SVG.replace('width="340" height="360"', 'width="1" height="1"')
        self.assertTrue(any("card geometry" in issue for issue in audit(svg)))

    def test_decorative_rect_before_real_card_does_not_false_fail(self):
        decoration = '<rect x="80" y="150" width="1" height="1" fill="#3B82F6"/>'
        svg = VALID_SVG.replace('<g id="card-1">', '<g id="card-1">' + decoration)
        self.assertEqual(audit(svg), [])

    def test_invisible_oversized_rect_does_not_spoof_card_containment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            invisible = ('<rect x="80" y="160" width="380" height="360" '
                         'fill="#1E293B" opacity="0"/>')
            svg = VALID_SVG.replace('<g id="card-1">', '<g id="card-1">' + invisible)
            svg = svg.replace('<text x="104" y="210"', '<text x="410" y="210"')
            path = root / "invisible-card.svg"
            path.write_text(svg, encoding="utf-8")
            defects = render_svg_smoke(path, root / "invisible-card.png", card_pairs=CARD_PAIRS)
            self.assertTrue(any("card geometry" in issue for issue in defects))

    def test_nested_transform_card_overlap_fails_browser_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = ('<g id="card-2"><rect x="470" y="160" width="340" height="360" fill="#1E293B" stroke="#29374B"/>\n'
                   '<text x="494" y="210" fill="#F1F5F9">少样本</text><text x="494" y="260" fill="#94A3B8">Few-shot</text>\n'
                   '<text x="494" y="320" fill="#F1F5F9">给出2-5个示例，显著提升格式一致性</text></g>')
            new = '<g id="card-2"><g transform="translate(-390 0)">' + old.removeprefix('<g id="card-2">').removesuffix('</g>') + '</g></g>'
            svg = VALID_SVG.replace(old, new)
            path = root / "overlap.svg"
            path.write_text(svg, encoding="utf-8")
            defects = render_svg_smoke(path, root / "overlap.png", card_pairs=CARD_PAIRS)
            self.assertTrue(any("card geometry overlaps" in issue for issue in defects))

    def test_card_text_must_be_contained_by_card_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg = VALID_SVG.replace(
                '<text x="104" y="320" fill="#F1F5F9">直接提问，不给示例，适合简单任务</text>',
                '<text x="430" y="530" fill="#F1F5F9">直接提问，不给示例，适合简单任务</text>',
            )
            path = root / "card-overflow.svg"
            path.write_text(svg, encoding="utf-8")
            defects = render_svg_smoke(
                path,
                root / "card-overflow.png",
                text_bounds=(80, 80, 1200, 680),
                card_pairs=CARD_PAIRS,
            )
            self.assertTrue(any("card geometry" in issue for issue in defects))

    def test_style_element_is_always_rejected(self):
        variants = [
            VALID_SVG.replace(
                '<g id="background">',
                '<g id="background"><style>@import url("https://example.invalid/theme.css");</style>'
            ),
            VALID_SVG.replace(
                '<g id="background">',
                '<g id="background"><style>@IMPORT "https://example.invalid/theme.css";</style>'
            ),
            VALID_SVG.replace(
                '<g id="background">',
                '<g id="background"><style>@font-face{src:URL(https://example.invalid/f.woff2)}</style>'
            ),
            VALID_SVG.replace(
                '<g id="background">',
                '<g id="background"><style>#title text{fill:#FF0000}</style>'
            ),
        ]
        for index, svg in enumerate(variants):
            with self.subTest(index=index):
                self.assertTrue(any("unsafe SVG" in issue for issue in audit(svg)))

    def test_mixed_case_active_elements_are_rejected(self):
        tags = ["SCRIPT", "Script", "FOREIGNOBJECT", "ANIMATE", "AnimateTransform", "SET"]
        for tag in tags:
            with self.subTest(tag=tag):
                svg = VALID_SVG.replace(
                    '<g id="background">',
                    f'<g id="background"><{tag}>document.documentElement.setAttribute("data-ran","yes")</{tag}>'
                )
                self.assertTrue(any("unsafe SVG" in issue for issue in audit(svg)))

    def test_smil_animation_is_rejected_as_active_content(self):
        animated = VALID_SVG.replace(
            '<text x="104" y="210" fill="#F1F5F9">零样本</text>',
            '<text x="104" y="210" fill="#F1F5F9">零样本<animate attributeName="opacity" from="1" to="0" dur="0.1s"/></text>'
        )
        self.assertTrue(any("unsafe SVG" in issue for issue in audit(animated)))

    def test_render_rows_does_not_use_no_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "safe.svg"
            path.write_text(VALID_SVG, encoding="utf-8")
            original_run = __import__('subprocess').run
            calls = []
            def spy_run(args, **kwargs):
                calls.append(args)
                return original_run(args, **kwargs)
            __import__('subprocess').run = spy_run
            try:
                result = render_svg_smoke(path, root / "safe.png", card_pairs=CARD_PAIRS)
            finally:
                __import__('subprocess').run = original_run
            self.assertEqual(result, [])
            chrome_calls = [c for c in calls if any('chrome' in str(arg).lower() for arg in c)]
            for args in chrome_calls:
                self.assertNotIn('--no-sandbox', args, f"Chrome called with --no-sandbox: {args}")

    def test_cross_source_fragments_fail_closed_world(self):
        invented = (
            '<g id="invented"><text x="80" y="650" fill="#F1F5F9">'
            '<tspan>直接提问</tspan><tspan dx="12">显著提升</tspan>'
            '<tspan dx="12">数学与逻辑题</tspan></text></g>'
        )
        svg = VALID_SVG.replace('</svg>', invented + '</svg>')
        self.assertTrue(any("unexpected visible text" in issue for issue in audit(svg)))

    def test_full_source_strings_from_different_items_cannot_be_merged(self):
        invented = (
            '<g id="merged-items"><text x="80" y="650" fill="#F1F5F9">'
            '<tspan>零样本</tspan><tspan dx="12">少样本</tspan></text></g>'
        )
        svg = VALID_SVG.replace('</svg>', invented + '</svg>')
        self.assertTrue(any("unexpected visible text" in issue for issue in audit(svg)))

    def test_tspan_tail_invention_fails_closed_world(self):
        invented = (
            '<g id="tail-invented"><text x="80" y="650" fill="#F1F5F9">'
            '<tspan>零样本</tspan>未经计划的尾部判断</text></g>'
        )
        svg = VALID_SVG.replace('</svg>', invented + '</svg>')
        self.assertTrue(any("unexpected visible text" in issue for issue in audit(svg)))

    def test_chrome_render_rejects_uniform_black_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            visible = root / "visible.svg"
            visible.write_text(VALID_SVG, encoding="utf-8")
            self.assertEqual(render_svg_smoke(visible, root / "visible.png"), [])

            black = root / "black.svg"
            black.write_text(
                '<svg width="1280" height="720" viewBox="0 0 1280 720" '
                'xmlns="http://www.w3.org/2000/svg"><rect width="1280" height="720" fill="#000"/></svg>',
                encoding="utf-8",
            )
            self.assertTrue(any("uniform image" in issue for issue in render_svg_smoke(black, root / "black.png")))

    def test_chrome_geometry_rejects_text_whose_right_edge_exits_safe_area(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg = VALID_SVG.replace(
                '<text x="80" y="100" fill="#F1F5F9">三种提示词策略对比</text>',
                '<text x="1180" y="100" font-size="48" fill="#F1F5F9">三种提示词策略对比</text>',
            )
            path = root / "overflow.svg"
            path.write_text(svg, encoding="utf-8")
            defects = render_svg_smoke(
                path,
                root / "overflow.png",
                text_bounds=(80, 80, 1200, 680),
                card_pairs=CARD_PAIRS,
            )
            self.assertTrue(any("clipped" in issue or "text bounds" in issue for issue in defects))

    def test_hidden_and_clipped_text_fail_browser_visibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hidden = root / "hidden.svg"
            hidden.write_text(VALID_SVG.replace('<text ', '<text visibility="hidden" '), encoding="utf-8")
            self.assertTrue(any("not visibly painted" in issue for issue in render_svg_smoke(hidden, root / "hidden.png")))

            clip = ('<defs><clipPath id="tiny"><rect x="0" y="0" width="1" height="1"/>'
                    '</clipPath></defs>')
            clipped_svg = VALID_SVG.replace('<g id="background">', clip + '<g id="background">')
            clipped_svg = clipped_svg.replace('<text ', '<text clip-path="url(#tiny)" ')
            clipped = root / "clipped.svg"
            clipped.write_text(clipped_svg, encoding="utf-8")
            self.assertTrue(any("not visibly painted" in issue for issue in render_svg_smoke(clipped, root / "clipped.png")))

    def test_non_clipping_local_clip_path_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = ('<defs><clipPath id="whole"><rect x="0" y="0" width="1280" height="720"/>'
                    '</clipPath></defs>')
            svg = VALID_SVG.replace('<g id="background">', clip + '<g id="background">')
            svg = svg.replace('<text ', '<text clip-path="url(#whole)" ')
            path = root / "whole-clip.svg"
            path.write_text(svg, encoding="utf-8")
            self.assertEqual(render_svg_smoke(path, root / "whole-clip.png", card_pairs=CARD_PAIRS), [])

    def test_partial_clip_that_removes_most_glyphs_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            clip = ('<defs><clipPath id="sliver" clipPathUnits="objectBoundingBox">'
                    '<rect x="0" y="0" width="0.08" height="1"/>'
                    '</clipPath></defs>')
            svg = VALID_SVG.replace('<g id="background">', clip + '<g id="background">')
            svg = svg.replace('<text ', '<text clip-path="url(#sliver)" ')
            path = root / "partial-clip.svg"
            path.write_text(svg, encoding="utf-8")
            defects = render_svg_smoke(path, root / "partial-clip.png", card_pairs=CARD_PAIRS)
            self.assertTrue(any("mostly clipped" in issue for issue in defects))

    def test_nearly_black_one_pixel_noise_fails_coverage_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg = VALID_SVG
            for color in ("#1E293B", "#F1F5F9", "#94A3B8", "#29374B"):
                svg = svg.replace(color, "#0F172A")
            svg = svg.replace('<text ', '<text visibility="hidden" ')
            svg = svg.replace('</svg>', '<g id="noise"><rect x="0" y="0" width="1" height="1" fill="#3B82F6"/></g></svg>')
            path = root / "near-black.svg"
            path.write_text(svg, encoding="utf-8")
            self.assertTrue(any("foreground coverage" in issue for issue in render_svg_smoke(path, root / "near-black.png")))

    def test_text_same_color_as_background_fails_pixel_visibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg = VALID_SVG.replace('fill="#F1F5F9"', 'fill="#0F172A"')
            svg = svg.replace('fill="#94A3B8"', 'fill="#0F172A"')
            path = root / "same-color.svg"
            path.write_text(svg, encoding="utf-8")
            defects = render_svg_smoke(path, root / "same-color.png", card_pairs=CARD_PAIRS)
            self.assertTrue(any("text has no rendered pixel effect" in issue for issue in defects))


class ExecutorProbeTests(unittest.TestCase):
    def test_fresh_pass_event_requires_stop(self):
        event = {"stage": "executor", "status": "passed", "metadata": {"slide": 1, "finish_reason": "length"}}
        self.assertTrue(any("finish_reason" in issue for issue in audit_executor_trace([event], 1)))

    def test_fresh_stop_pass_event_is_accepted(self):
        event = {"stage": "executor", "status": "passed", "metadata": {"slide": 1, "finish_reason": "stop"}}
        self.assertEqual(audit_executor_trace([event], 1), [])

    def test_truncated_failure_then_complete_retry_is_accepted(self):
        events = [
            {"stage": "executor", "status": "failed", "metadata": {"slide": 1, "finish_reason": "length"}},
            {"stage": "executor", "status": "passed", "metadata": {"slide": 1, "finish_reason": "stop"}},
        ]
        self.assertEqual(audit_executor_trace(events, 1), [])

    def test_trace_pass_must_match_returned_publish_path(self):
        events = [
            {"stage": "executor", "status": "passed", "metadata": {
                "slide": 1, "finish_reason": "length", "publish_path": "current.svg"}},
            {"stage": "executor", "status": "passed", "metadata": {
                "slide": 1, "finish_reason": "stop", "publish_path": "unrelated.svg"}},
        ]
        defects = audit_executor_trace(events, 1, publish_path=Path("current.svg"))
        self.assertTrue(any("publish path" in issue or "finish_reason" in issue for issue in defects))

    def test_invented_visible_copy_fails_closed_world(self):
        svg = """<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
        <g id="content"><text x="80" y="100">质量门禁必须前置</text>
        <text x="80" y="180">必须在导出前被拦截</text><text x="80" y="240">未经计划的结论</text></g></svg>"""
        defects = audit_closed_world_text(
            svg,
            required_text=["质量门禁必须前置", "必须在导出前被拦截"],
            allowed_text=["质量门禁必须前置", "必须在导出前被拦截"],
        )
        self.assertTrue(any("unexpected visible text" in issue for issue in defects))


class HonestDegradationTests(unittest.TestCase):
    def test_render_smoke_reports_missing_browser_explicitly(self):
        # The scratch-probe CLI selector test was superseded: pre-run input
        # validation now lives in the committed benchmark runner (56-03).
        # The honesty contract it shared — never silently pass on missing
        # capability — is preserved here for the render path.
        from slide_skill import measurement_contracts as mc

        original = mc._find_browser
        mc._find_browser = lambda: None
        try:
            defects = render_svg_smoke(
                Path("does-not-matter.svg"), Path(tempfile.gettempdir()) / "x.png"
            )
        finally:
            mc._find_browser = original
        self.assertEqual(defects, ["no Chrome/Edge browser found for render smoke"])


if __name__ == "__main__":
    unittest.main()
