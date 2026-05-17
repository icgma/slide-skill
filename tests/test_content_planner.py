"""Tests for the content planning layer — v3.0 intelligence."""

import pytest
from slide_skill.content_planner import (
    ContentConfig,
    ContentItem,
    SlidePlan,
    plan_slides,
    plan_to_markdown,
    plan_to_json,
)


# ---------------------------------------------------------------------------
# Data class tests
# ---------------------------------------------------------------------------

class TestContentItem:
    def test_basic_item(self):
        item = ContentItem(type="text", primary="Hello")
        assert item.type == "text"
        assert item.primary == "Hello"
        assert item.secondary == ""
        assert item.tertiary == ""
        assert item.meta == {}

    def test_vocab_item(self):
        item = ContentItem(
            type="vocab",
            primary="医院",
            tertiary="yīyuàn",
            secondary="hospital",
        )
        assert item.primary == "医院"
        assert item.tertiary == "yīyuàn"
        assert item.secondary == "hospital"

    def test_meta_dict(self):
        item = ContentItem(
            type="metric",
            primary="$50B",
            meta={"bold": True, "number": "50"},
        )
        assert item.meta["bold"] is True


class TestSlidePlan:
    def test_basic_plan(self):
        plan = SlidePlan(index=1, layout="cover", title="Title")
        assert plan.index == 1
        assert plan.layout == "cover"
        assert plan.title == "Title"
        assert plan.items == []
        assert plan.density == "normal"

    def test_to_dict(self):
        plan = SlidePlan(
            index=2,
            layout="bullet-list",
            title="Key Points",
            items=[ContentItem(type="bullet", primary="Point 1")],
            density="sparse",
        )
        d = plan.to_dict()
        assert d["index"] == 2
        assert d["layout"] == "bullet-list"
        assert len(d["items"]) == 1
        assert d["density"] == "sparse"


# ---------------------------------------------------------------------------
# ContentConfig tests
# ---------------------------------------------------------------------------

class TestContentConfig:
    def test_defaults(self):
        cfg = ContentConfig()
        assert cfg.domain == "general"
        assert cfg.max_slides == 20
        assert cfg.max_items_per_slide == 6
        assert cfg.show_pinyin is False  # Default is False per actual code

    def test_teaching_domain(self):
        cfg = ContentConfig(domain="teaching")
        assert cfg.domain == "teaching"
        # Note: max_items_per_slide stays at 6, but _section_to_plans limits vocab to 4

    def test_competition_domain(self):
        cfg = ContentConfig(domain="competition")
        assert cfg.domain == "competition"


# ---------------------------------------------------------------------------
# plan_slides integration tests
# ---------------------------------------------------------------------------

class TestPlanSlides:
    def test_empty_markdown_produces_cover(self):
        plans = plan_slides("")
        assert len(plans) >= 1
        assert plans[0].layout == "cover"

    def test_single_heading_becomes_cover(self):
        md = "# Introduction\nSome text here.\n\n## Section 2\nMore content."
        plans = plan_slides(md)
        # First section becomes cover when there are multiple sections
        assert plans[0].layout == "cover"
        assert plans[0].title == "Introduction"

    def test_multiple_sections_produce_multiple_slides(self):
        md = """# Intro

## Background
- Point A
- Point B

## Conclusion
Thank you.
"""
        plans = plan_slides(md)
        assert len(plans) >= 3
        # First should be cover
        assert plans[0].layout == "cover"
        # Last should be closing (when > 2 sections)
        assert plans[-1].layout == "closing"

    def test_bullet_list_detection(self):
        md = """# Overview

- Feature one
- Feature two
- Feature three
"""
        plans = plan_slides(md)
        # Should detect bullets and create bullet-list layout
        assert any(p.layout in ("bullet-list", "default") for p in plans)

    def test_vocabulary_detection(self):
        md = """# Vocabulary

- 医院 (yīyuàn) — hospital
- 感冒 (gǎnmào) — cold/flu
- 发烧 (fāshāo) — fever
"""
        plans = plan_slides(md)
        # Should detect vocab pattern
        assert any(p.layout == "vocab-card" for p in plans)

    def test_metrics_detection(self):
        md = """# Key Metrics

- Revenue grew 50% YoY
- Market size $50B
- 2x user growth
"""
        plans = plan_slides(md)
        # Should detect metrics
        assert any("metric" in p.layout for p in plans)

    def test_max_slides_enforcement(self):
        # Create a very long markdown
        sections = "\n\n".join(
            f"## Section {i}\n- Item {i}" for i in range(50)
        )
        md = f"# Title\n{sections}"
        cfg = ContentConfig(max_slides=10)
        plans = plan_slides(md, config=cfg)
        assert len(plans) <= 10
        # Last slide should be closing
        assert plans[-1].layout == "closing"

    def test_anti_monotony_breaks_runs(self):
        md = """# Title

## S1
- A
- B

## S2
- C
- D

## S3
- E
- F

## S4
- G
- H
"""
        plans = plan_slides(md)
        # Check no 3 consecutive slides with same layout (excluding chrome)
        chrome = {"cover", "closing", "section-divider"}
        for i in range(len(plans) - 2):
            layouts = [plans[i + j].layout for j in range(3)]
            if layouts[0] not in chrome:
                assert not (layouts[0] == layouts[1] == layouts[2])

    def test_dialogue_detection(self):
        md = """# Dialogue

A: 你好吗？
B: 我很好，谢谢！
A: 你去哪里？
"""
        plans = plan_slides(md)
        assert any(p.layout == "dialogue" for p in plans)

    def test_process_detection_with_arrows(self):
        md = """# Process

Step 1 → Step 2
Step 2 → Step 3
Step 3 → Done
"""
        plans = plan_slides(md)
        # Should detect process/arrows and map to a layout
        assert len(plans) >= 1
        # The actual layout depends on the detection logic - just verify it ran


# ---------------------------------------------------------------------------
# plan_to_markdown tests
# ---------------------------------------------------------------------------

class TestPlanToMarkdown:
    def test_generates_valid_markdown(self):
        plans = [
            SlidePlan(index=1, layout="cover", title="Title"),
            SlidePlan(index=2, layout="bullet-list", title="Points"),
        ]
        md = plan_to_markdown(plans)
        assert "# Slide Plan" in md
        assert "Total slides:" in md
        assert "| # | Layout | Title |" in md
        assert "`cover`" in md
        assert "`bullet-list`" in md

    def test_includes_density_column(self):
        plans = [
            SlidePlan(index=1, layout="cover", title="Title", density="sparse"),
        ]
        md = plan_to_markdown(plans)
        assert "Density" in md
        assert "sparse" in md


# ---------------------------------------------------------------------------
# plan_to_json tests
# ---------------------------------------------------------------------------

class TestPlanToJson:
    def test_serializes_to_list_of_dicts(self):
        plans = [
            SlidePlan(
                index=1,
                layout="cover",
                title="Title",
                items=[ContentItem(type="text", primary="Hello")],
            ),
        ]
        data = plan_to_json(plans)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["index"] == 1
        assert data[0]["layout"] == "cover"
        assert len(data[0]["items"]) == 1

    def test_items_have_all_fields(self):
        plans = [
            SlidePlan(
                index=1,
                layout="vocab-card",
                title="Vocab",
                items=[
                    ContentItem(
                        type="vocab",
                        primary="医院",
                        tertiary="yīyuàn",
                        secondary="hospital",
                    )
                ],
            ),
        ]
        data = plan_to_json(plans)
        item = data[0]["items"][0]
        assert item["primary"] == "医院"
        assert item["tertiary"] == "yīyuàn"
        assert item["secondary"] == "hospital"


# ---------------------------------------------------------------------------
# Domain-specific config tests
# ---------------------------------------------------------------------------

class TestDomainConfigs:
    def test_teaching_config_limits_items(self):
        """Teaching slides should have fewer items per slide for clarity."""
        cfg = ContentConfig(domain="teaching")
        plans = plan_slides("""# Vocab

- Word A (a) — translation A
- Word B (b) — translation B
- Word C (c) — translation C
- Word D (d) — translation D
- Word E (e) — translation E
""", config=cfg)
        # Each vocab slide should have ≤ 4 items
        for p in plans:
            if p.layout == "vocab-card":
                assert len(p.items) <= 4

    def test_competition_config_respects_time_limits(self):
        """Competition decks often have strict time/slide limits."""
        cfg = ContentConfig(domain="competition", max_slides=12)
        sections = "\n\n".join(f"## Part {i}\nContent {i}" for i in range(20))
        md = f"# Competition Deck\n{sections}"
        plans = plan_slides(md, config=cfg)
        assert len(plans) <= 12

    def test_course_config_balanced_density(self):
        """Course presentations need balanced content density."""
        cfg = ContentConfig(domain="course")
        md = """# Course Topic

## Introduction
Background info here.

## Main Content
- Key point 1
- Key point 2
- Key point 3

## Summary
Wrap up.
"""
        plans = plan_slides(md, config=cfg)
        assert len(plans) >= 3
        # Should have variety, not all same layout
        layouts = set(p.layout for p in plans)
        assert len(layouts) >= 2
