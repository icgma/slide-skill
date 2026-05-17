"""Tests for course-domain SVG renderers."""

import pytest
from slide_skill.content_planner import ContentItem, SlidePlan
from slide_skill.domain_course import (
    render_course_slide,
)


@pytest.fixture
def sample_lock():
    """Sample spec lock for rendering."""
    return {
        "palette": {
            "accent": "#3B82F6",
            "text": "#1E293B",
            "surface": "#FFFFFF",
            "muted": "#64748B",
            "background": "#0F172A",
            "body": "#475569",
        },
        "canvas": {"width": 1280, "height": 720},
        "font_family": "Microsoft YaHei",
    }


class TestCourseRenderers:
    def test_learning_objectives_layout(self, sample_lock):
        plan = SlidePlan(
            index=1,
            layout="learning-objectives",
            title="Learning Goals",
            items=[
                ContentItem(type="bullet", primary=f"Objective {i}")
                for i in range(1, 4)
            ],
        )
        svg = render_course_slide(plan, sample_lock, total=5)
        assert svg is not None
        assert "Learning Goals" in svg

    def test_key_concept_layout(self, sample_lock):
        plan = SlidePlan(
            index=2,
            layout="key-concept",
            title="Core Concept",
            items=[
                ContentItem(type="text", primary="Main idea"),
            ],
        )
        svg = render_course_slide(plan, sample_lock, total=5)
        assert svg is not None
        assert "Core Concept" in svg

    def test_case_study_layout(self, sample_lock):
        plan = SlidePlan(
            index=3,
            layout="case-study",
            title="Case Study",
            items=[
                ContentItem(type="text", primary="Background"),
                ContentItem(type="text", primary="Analysis"),
            ],
        )
        svg = render_course_slide(plan, sample_lock, total=5)
        assert svg is not None
        assert "Case Study" in svg

    def test_discussion_layout(self, sample_lock):
        plan = SlidePlan(
            index=4,
            layout="discussion",
            title="Discussion Questions",
            items=[
                ContentItem(type="text", primary="Question 1"),
                ContentItem(type="text", primary="Question 2"),
            ],
        )
        svg = render_course_slide(plan, sample_lock, total=5)
        assert svg is not None
        assert "Discussion Questions" in svg

    def test_has_chrome(self, sample_lock):
        plan = SlidePlan(
            index=1,
            layout="learning-objectives",
            title="Test",
        )
        svg = render_course_slide(plan, sample_lock, total=5)
        assert svg is not None
        assert 'id="chrome-stripe"' in svg
        assert 'id="chrome-footer"' in svg

    def test_page_number(self, sample_lock):
        plan = SlidePlan(
            index=3,
            layout="key-concept",
            title="Test",
        )
        svg = render_course_slide(plan, sample_lock, total=10)
        assert svg is not None
        assert "03 / 10" in svg

    def test_unknown_layout_returns_none(self, sample_lock):
        plan = SlidePlan(
            index=1,
            layout="unknown-layout",
            title="Test",
        )
        svg = render_course_slide(plan, sample_lock, total=5)
        assert svg is None
