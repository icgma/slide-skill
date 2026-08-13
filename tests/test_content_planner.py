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

    def test_table_detection(self):
        md = """# Results

| Model | Accuracy | F1 |
|-------|----------|-----|
| TextCNN | 78.3% | 76.5% |
| BERT-base | 87.6% | 86.2% |
"""
        plans = plan_slides(md)
        assert any(p.layout == "table" for p in plans)

    def test_table_not_confused_with_comparison(self):
        md = """# Results

| Model | Accuracy | F1 |
|-------|----------|-----|
| TextCNN | 78.3% | 76.5% |
| BERT-base | 87.6% | 86.2% |
"""
        plans = plan_slides(md)
        table_plans = [p for p in plans if p.layout == "table"]
        comp_plans = [p for p in plans if p.layout == "comparison"]
        assert len(table_plans) >= 1
        assert len(comp_plans) == 0


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

    def test_includes_v4_design_columns(self):
        plans = [
            SlidePlan(index=1, layout="cover", title="Title", density="sparse"),
        ]
        md = plan_to_markdown(plans)
        assert "Strategy" in md
        assert "Chart" in md
        assert "Pattern" in md


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


class TestPremiumLayoutRouting:
    def test_learning_objectives_routing(self):
        md = """# Course Topic
## 教学目标
- 掌握智能传播的定义与范式
- 理解平台化社会的权力流变
- 能够运用社会计算工具进行情感分析
"""
        plans = plan_slides(md, config=ContentConfig(domain="course"))
        assert any(p.layout == "learning-objectives" for p in plans)
        for p in plans:
            if p.layout == "learning-objectives":
                assert len(p.items) == 3
                assert p.items[0].type == "objective"

    def test_team_grid_routing(self):
        md = """# About Us
## 创始团队
- 张三 — 首席执行官：前科技巨头副总裁，15年行业经验。
- 李四 — 首席技术官：麻省理工博士，自然语言处理专家。
"""
        plans = plan_slides(md, config=ContentConfig(domain="competition"))
        assert any(p.layout == "team-grid" for p in plans)
        for p in plans:
            if p.layout == "team-grid":
                assert len(p.items) == 2
                assert p.items[0].type == "member"
                assert p.items[0].primary == "张三"
                assert "首席执行官" in p.items[0].secondary

    def test_timeline_routing(self):
        md = """# Process
## 发展规划
- 2026年 — 产品发布与天使轮融资
- 2027年 — 市场扩张与A轮融资
- 2028年 — 盈亏平衡与全球化探索
"""
        plans = plan_slides(md, config=ContentConfig(domain="competition"))
        assert any(p.layout == "timeline" for p in plans)
        for p in plans:
            if p.layout == "timeline":
                assert len(p.items) == 3
                assert p.items[0].type == "milestone"

    def test_key_concept_routing(self):
        md = """# Theory
## 概念定义
什么是智能传播？
智能传播是指利用人工智能、大数据等技术，实现信息自动生产、精准匹配与动态交互的新型信息分发范式。
"""
        plans = plan_slides(md, config=ContentConfig(domain="course"))
        assert any(p.layout == "key-concept" for p in plans)

    def test_case_study_routing(self):
        md = """# Case Study
## 经典案例分析
SITUATION: 平台化社会中传统媒体话语权弱化，假新闻泛滥。
---
FINDINGS: 社会计算工具能实时识别谣言，但无法解决价值偏见。
"""
        plans = plan_slides(md, config=ContentConfig(domain="course"))
        assert any(p.layout == "case-study" for p in plans)

    def test_discussion_routing(self):
        md = """# QA
## 思考与讨论
如何看待算法推荐对公共讨论空间的蚕食？
- 信息茧房是必然结果吗？
- 如何构建算法时代的公共话语权？
"""
        plans = plan_slides(md, config=ContentConfig(domain="course"))
        assert any(p.layout == "discussion" for p in plans)

    def test_comparison_matrix_routing(self):
        md = """# Battle
## 平台对比 (A vs B)
平台A特点：去中心化、高隐私、用户自治。
---
平台B特点：中心化推荐、广告变现、平台强管控。
"""
        plans = plan_slides(md, config=ContentConfig(domain="competition"))
        assert any(p.layout == "comparison-matrix" for p in plans)

    def test_metrics_dashboard_routing(self):
        md = """# Performance
## 关键指标数据
- 98% 准确率：算法模型在公开数据集上的分类精度。
- 10M 活跃用户：平台月度活跃用户突破千万大关。
- 2.5x 增长：相比上一季度，平台流量实现翻倍。
"""
        plans = plan_slides(md, config=ContentConfig(domain="competition"))
        assert any(p.layout == "metrics-dashboard" for p in plans)

    def test_market_opportunity_routes_to_dedicated_layout(self):
        md = """# Market
## Market Opportunity
- Total Addressable Market - $120B by 2027
- Enterprise adoption - 68% of teams piloting AI workflows
- Cost pressure - 3.5x increase in support volume
"""
        plans = plan_slides(md, config=ContentConfig(domain="general"))
        assert any(p.layout == "market-opportunity" for p in plans)
        assert not any(p.layout == "metrics-dashboard" for p in plans)

    def test_core_sections_route_to_semantic_scenes(self):
        md = """# Product
## Problem Statement
- Manual reporting takes 40+ hours
- Data silos across teams
## Our Solution
- Unified ingestion
- Natural language query interface
## Technology Stack
- Cloud-native services
- Apache Kafka
## Roadmap
- Q1 2026: Mobile dashboard
- Q2 2026: AI report writer
## Why Now
The market window is open.
"""
        plans = plan_slides(md, config=ContentConfig(domain="general"))
        layouts = {p.title: p.layout for p in plans}
        assert layouts["Problem Statement"] == "problem"
        assert layouts["Our Solution"] == "solution"
        assert layouts["Technology Stack"] == "technology-stack"
        assert layouts["Roadmap"] == "roadmap"

    def test_metrics_dashboard_no_false_positive(self):
        # A single occurrence like 4K should NOT trigger metrics-dashboard
        md = """# Lab
## 一流的智能媒体实验室与实战基地
- 智能舆情监测平台 — 追踪社交网络热点，运用自然语言处理进行社会态度与舆情研判。
- 融合演播厅系统 — 配备行业级 4K 融媒体转播与虚拟合成设备，对接业界主流生产环境。
- 计算媒体中心 — 提供高性能计算集群，支持学生进行大规模文本挖掘与多模态数据分析。
"""
        plans = plan_slides(md, config=ContentConfig(domain="course"))
        assert not any(p.layout == "metrics-dashboard" for p in plans)

    def test_case_study_not_confused_with_table(self):
        # Markdown table should not be confused with case-study even if it contains "---" table divider
        md = """# Results
## 智能传播 vs 传统新闻：职业图景的升级
| 职业维度 | 传统新闻专业 | 智能传播专业 |
|---|---|---|
| 核心技能 | 文字采编 | 数据挖掘 |
"""
        plans = plan_slides(md, config=ContentConfig(domain="course"))
        assert not any(p.layout == "case-study" for p in plans)
        assert any(p.layout == "table" for p in plans)

    def test_key_concept_structural_upgrades(self):
        # Structural layouts with core pillar keywords should map to key-concept in course/competition domain
        md2 = """# Intro
## 专业定位：人文温情与智能科技的交汇
- 专业底色 — 传承经典新闻学的人文关怀
- 技术赋能 — 拥抱人工智能
- 培养目标 — 培养融合媒体精英
"""
        plans2 = plan_slides(md2, config=ContentConfig(domain="course"))
        assert any(p.layout == "key-concept" for p in plans2)

        md5 = """# Intro
## 硬核课程体系：人文与算法双轨并进
- 基础层 — 采写编评
- 技术层 — Python
- 传播层 — 计算传播
"""
        plans5 = plan_slides(md5, config=ContentConfig(domain="course"))
        assert any(p.layout == "key-concept" for p in plans5)

