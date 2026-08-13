"""Tests for Phase 45: Content Planning v2 (design-aware planning).

These tests verify the v4.0 design-intent enhancements:
1. SlidePlan extended fields
2. Chart auto-selection
3. Image hint inference
4. Layout pattern suggestion
5. Enhanced keyword-aware rhythm assignment
6. Eight Confirmations design gate
7. Updated plan_to_markdown / plan_to_json output
"""

import json

import pytest

from slide_skill.content_planner import (
    ContentConfig,
    ContentItem,
    SlidePlan,
    _enrich_design_intent,
    _suggest_chart_type,
    _suggest_image,
    _suggest_layout_pattern,
    _suggest_visual_strategy,
    assign_page_rhythm,
    confirmations_to_markdown,
    generate_design_confirmations,
    plan_slides,
    plan_to_json,
    plan_to_markdown,
)


# ─── SlidePlan extended fields ───────────────────────────────────────

class TestSlidePlanFields:
    def test_new_fields_default_empty(self):
        plan = SlidePlan(index=1, layout="bullet-list", title="Test")
        assert plan.visual_strategy == ""
        assert plan.chart_type == ""
        assert plan.image_hint == ""
        assert plan.layout_pattern == ""

    def test_to_dict_includes_new_fields(self):
        plan = SlidePlan(
            index=1, layout="bullet-list", title="Test",
            visual_strategy="progressive-reveal",
            chart_type="kpi_cards",
            image_hint="technology",
            layout_pattern="cards-3-up",
        )
        d = plan.to_dict()
        assert d["visual_strategy"] == "progressive-reveal"
        assert d["chart_type"] == "kpi_cards"
        assert d["image_hint"] == "technology"
        assert d["layout_pattern"] == "cards-3-up"

    def test_to_dict_omits_empty_fields(self):
        plan = SlidePlan(index=1, layout="bullet-list", title="Test")
        d = plan.to_dict()
        assert "visual_strategy" not in d
        assert "chart_type" not in d
        assert "image_hint" not in d
        assert "layout_pattern" not in d


# ─── Chart auto-selection ────────────────────────────────────────────

class TestChartAutoSelection:
    def test_metric_highlight_kpi(self):
        plan = SlidePlan(
            index=1, layout="metric-highlight", title="KPIs",
            items=[ContentItem(type="metric", primary="85%")],
        )
        assert _suggest_chart_type(plan) == "kpi_cards"

    def test_metric_many_items_bar(self):
        plan = SlidePlan(
            index=1, layout="metric-highlight", title="Scores",
            items=[ContentItem(type="metric", primary=f"{i}%") for i in range(5)],
        )
        assert _suggest_chart_type(plan) == "bar_vertical"

    def test_timeline_horizontal(self):
        plan = SlidePlan(index=1, layout="timeline", title="Timeline")
        assert _suggest_chart_type(plan) == "timeline_horizontal"

    def test_comparison_table(self):
        plan = SlidePlan(index=1, layout="comparison", title="Compare")
        assert _suggest_chart_type(plan) == "comparison_table"

    def test_percentages_near_100_donut(self):
        plan = SlidePlan(
            index=1, layout="bullet-list", title="Distribution",
            items=[
                ContentItem(type="metric", primary="60% Sales"),
                ContentItem(type="metric", primary="25% Marketing"),
                ContentItem(type="metric", primary="15% Engineering"),
            ],
        )
        assert _suggest_chart_type(plan) == "donut_chart"

    def test_no_chart_for_bullet_list(self):
        plan = SlidePlan(
            index=1, layout="bullet-list", title="Points",
            items=[ContentItem(type="text", primary="Point 1")],
        )
        assert _suggest_chart_type(plan) == ""


# ─── Image hint inference ────────────────────────────────────────────

class TestImageHint:
    def test_technology_title_gets_hint(self):
        plan = SlidePlan(
            index=1, layout="bullet-list", title="Technology Overview",
            items=[ContentItem(type="text", primary="AI tools")],
            rhythm="anchor",
        )
        result = _suggest_image(plan)
        assert "technology" in result.lower()

    def test_chinese_keyword_gets_hint(self):
        plan = SlidePlan(
            index=1, layout="bullet-list", title="创新方案",
            items=[ContentItem(type="text", primary="新方法")],
            rhythm="anchor",
        )
        result = _suggest_image(plan)
        assert "innovation" in result.lower()

    def test_dense_slide_no_hint(self):
        plan = SlidePlan(
            index=1, layout="bullet-list", title="Technology",
            items=[ContentItem(type="text", primary=f"Item {i}") for i in range(5)],
            rhythm="dense",
        )
        assert _suggest_image(plan) == ""

    def test_cover_slide_no_hint(self):
        plan = SlidePlan(index=1, layout="cover", title="Technology", rhythm="anchor")
        assert _suggest_image(plan) == ""


# ─── Layout pattern suggestion ───────────────────────────────────────

class TestLayoutPattern:
    def test_bullet_list_3_items_cards(self):
        plan = SlidePlan(
            index=1, layout="bullet-list", title="Points",
            items=[ContentItem(type="text", primary=f"Item {i}") for i in range(3)],
        )
        assert _suggest_layout_pattern(plan) == "cards-3-up"

    def test_bullet_list_5_items_stacked(self):
        plan = SlidePlan(
            index=1, layout="bullet-list", title="Points",
            items=[ContentItem(type="text", primary=f"Item {i}") for i in range(5)],
        )
        assert _suggest_layout_pattern(plan) == "stacked-rows"

    def test_metric_2_items_split(self):
        plan = SlidePlan(
            index=1, layout="metric-highlight", title="KPIs",
            items=[ContentItem(type="metric", primary=f"{i}%") for i in range(2)],
        )
        assert _suggest_layout_pattern(plan) == "split-50-50"

    def test_cover_full_bleed(self):
        plan = SlidePlan(index=1, layout="cover", title="Title")
        assert _suggest_layout_pattern(plan) == "full-bleed-hero"


# ─── Visual strategy ────────────────────────────────────────────────

class TestVisualStrategy:
    def test_cover_hero_statement(self):
        plan = SlidePlan(index=1, layout="cover", title="Title")
        assert _suggest_visual_strategy(plan) == "hero-statement"

    def test_bullet_progressive_reveal(self):
        plan = SlidePlan(index=1, layout="bullet-list", title="Points")
        assert _suggest_visual_strategy(plan) == "progressive-reveal"

    def test_unknown_layout_standard(self):
        plan = SlidePlan(index=1, layout="unknown-layout", title="Test")
        assert _suggest_visual_strategy(plan) == "standard-content"


# ─── Enhanced rhythm assignment ──────────────────────────────────────

class TestEnhancedRhythm:
    def test_conclusion_title_anchor(self):
        plans = [
            SlidePlan(index=1, layout="cover", title="Cover"),
            SlidePlan(
                index=2, layout="section-divider", title="Background",
            ),
            SlidePlan(
                index=3, layout="bullet-list", title="结论与展望",
                items=[ContentItem(type="text", primary="Finding 1")],
            ),
            SlidePlan(index=4, layout="closing", title="Thanks"),
        ]
        assign_page_rhythm(plans)
        assert plans[2].rhythm == "anchor"

    def test_overview_title_breathing(self):
        plans = [
            SlidePlan(index=1, layout="cover", title="Cover"),
            SlidePlan(
                index=2, layout="bullet-list", title="研究概述",
                items=[ContentItem(type="text", primary="Point 1")],
            ),
            SlidePlan(index=3, layout="closing", title="Thanks"),
        ]
        assign_page_rhythm(plans)
        assert plans[1].rhythm == "breathing"

    def test_table_layout_dense(self):
        plans = [
            SlidePlan(index=1, layout="cover", title="Cover"),
            SlidePlan(index=2, layout="table", title="Data Table",
                     items=[ContentItem(type="text", primary="Row 1")]),
            SlidePlan(index=3, layout="closing", title="Thanks"),
        ]
        assign_page_rhythm(plans)
        assert plans[1].rhythm == "dense"


# ─── Design intent enrichment ────────────────────────────────────────

class TestEnrichDesignIntent:
    def test_enrichment_populates_all_fields(self):
        plans = [
            SlidePlan(
                index=1, layout="bullet-list", title="Technology Overview",
                items=[ContentItem(type="text", primary=f"Item {i}") for i in range(3)],
                rhythm="anchor",
            ),
        ]
        _enrich_design_intent(plans)
        assert plans[0].visual_strategy == "progressive-reveal"
        assert plans[0].layout_pattern == "cards-3-up"

    def test_enrichment_does_not_overwrite(self):
        plans = [
            SlidePlan(
                index=1, layout="bullet-list", title="Test",
                visual_strategy="custom-strategy",
            ),
        ]
        _enrich_design_intent(plans)
        assert plans[0].visual_strategy == "custom-strategy"


# ─── Eight Confirmations ─────────────────────────────────────────────

class TestEightConfirmations:
    def test_generates_all_8_keys(self):
        plans = [
            SlidePlan(index=1, layout="cover", title="Title", rhythm="anchor"),
            SlidePlan(
                index=2, layout="bullet-list", title="Points", rhythm="breathing",
                items=[ContentItem(type="text", primary="P1")],
            ),
            SlidePlan(index=3, layout="closing", title="Thanks", rhythm="anchor"),
        ]
        confirmations = generate_design_confirmations(plans)
        assert "format" in confirmations
        assert "page_count" in confirmations
        assert "style" in confirmations
        assert "color_scheme" in confirmations
        assert "typography" in confirmations
        assert "image_style" in confirmations
        assert "rhythm_pattern" in confirmations
        assert "outline" in confirmations
        assert confirmations["page_count"] == 3

    def test_rhythm_pattern_counts(self):
        plans = [
            SlidePlan(index=1, layout="cover", title="T", rhythm="anchor"),
            SlidePlan(index=2, layout="bullet-list", title="T", rhythm="breathing"),
            SlidePlan(index=3, layout="table", title="T", rhythm="dense"),
        ]
        confirmations = generate_design_confirmations(plans)
        assert "anchor=1" in confirmations["rhythm_pattern"]
        assert "breathing=1" in confirmations["rhythm_pattern"]
        assert "dense=1" in confirmations["rhythm_pattern"]

    def test_confirmations_to_markdown(self):
        confirmations = {
            "format": "16:9",
            "page_count": 5,
            "style": "dark-tech",
            "color_scheme": "test",
            "typography": "test",
            "image_style": "2/5",
            "rhythm_pattern": "anchor=2, breathing=2, dense=1",
            "outline": ["1. [cover] Title", "2. [bullet-list] Points"],
        }
        md = confirmations_to_markdown(confirmations)
        assert "Eight Confirmations" in md
        assert "dark-tech" in md
        assert "Slide Outline" in md


# ─── Updated plan output ─────────────────────────────────────────────

class TestUpdatedPlanOutput:
    def _sample_plans(self):
        return [
            SlidePlan(
                index=1, layout="cover", title="Title",
                visual_strategy="hero-statement",
                layout_pattern="full-bleed-hero",
                rhythm="anchor",
            ),
            SlidePlan(
                index=2, layout="metric-highlight", title="KPIs",
                items=[ContentItem(type="metric", primary="85%")],
                visual_strategy="hero-stat",
                chart_type="kpi_cards",
                layout_pattern="cards-3-up",
                rhythm="anchor",
            ),
        ]

    def test_markdown_includes_new_columns(self):
        md = plan_to_markdown(self._sample_plans())
        assert "Strategy" in md
        assert "Chart" in md
        assert "Pattern" in md
        assert "hero-statement" in md
        assert "kpi_cards" in md

    def test_json_includes_new_fields(self):
        data = plan_to_json(self._sample_plans())
        assert data[0]["visual_strategy"] == "hero-statement"
        assert data[1]["chart_type"] == "kpi_cards"
        assert data[1]["layout_pattern"] == "cards-3-up"


# ─── Integration: plan_slides produces enriched plans ────────────────

class TestIntegration:
    def test_plan_slides_enriches_design_intent(self):
        md = """# Test Presentation

## Technology Overview

- AI is transforming education
- Deep learning is the key
- Natural language processing

## 结论

Key findings and takeaways.
"""
        plans = plan_slides(md)
        assert len(plans) >= 3
        # All plans should have visual_strategy populated
        for p in plans:
            assert p.visual_strategy != "", f"Slide {p.index} missing visual_strategy"
            assert p.rhythm != "", f"Slide {p.index} missing rhythm"
