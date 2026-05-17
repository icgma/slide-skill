"""Tests for competition-domain SVG renderers."""

import pytest
from slide_skill.content_planner import ContentItem, SlidePlan
from slide_skill.domain_competition import (
    render_competition_slide,
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


class TestCompetitionRenderers:
    def test_team_grid_layout(self, sample_lock):
        plan = SlidePlan(
            index=1,
            layout="team-grid",
            title="Our Team",
            items=[
                ContentItem(type="text", primary="Member 1", meta={"role": "CEO"}),
                ContentItem(type="text", primary="Member 2", meta={"role": "CTO"}),
            ],
        )
        svg = render_competition_slide(plan, sample_lock, total=10)
        assert svg is not None
        assert "Our Team" in svg

    def test_metrics_dashboard_layout(self, sample_lock):
        plan = SlidePlan(
            index=2,
            layout="metrics-dashboard",
            title="Key Metrics",
            items=[
                ContentItem(type="metric", primary="$50B", meta={"label": "TAM"}),
                ContentItem(type="metric", primary="$5B", meta={"label": "SAM"}),
            ],
        )
        svg = render_competition_slide(plan, sample_lock, total=10)
        assert svg is not None
        assert "$50B" in svg or "$5B" in svg

    def test_timeline_layout(self, sample_lock):
        plan = SlidePlan(
            index=3,
            layout="timeline",
            title="Roadmap",
            items=[
                ContentItem(type="step", primary="Phase 1", meta={"quarter": "Q1"}),
                ContentItem(type="step", primary="Phase 2", meta={"quarter": "Q2"}),
            ],
        )
        svg = render_competition_slide(plan, sample_lock, total=10)
        assert svg is not None
        assert "Roadmap" in svg

    def test_comparison_matrix_layout(self, sample_lock):
        plan = SlidePlan(
            index=4,
            layout="comparison-matrix",
            title="Competitive Analysis",
            items=[
                ContentItem(type="text", primary="Feature A"),
                ContentItem(type="text", primary="Feature B"),
            ],
        )
        svg = render_competition_slide(plan, sample_lock, total=10)
        assert svg is not None
        assert "Competitive Analysis" in svg

    def test_has_chrome(self, sample_lock):
        plan = SlidePlan(
            index=1,
            layout="team-grid",
            title="Test",
        )
        svg = render_competition_slide(plan, sample_lock, total=10)
        assert svg is not None
        assert 'id="chrome-stripe"' in svg
        assert 'id="chrome-footer"' in svg

    def test_page_number(self, sample_lock):
        plan = SlidePlan(
            index=3,
            layout="timeline",
            title="Test",
        )
        svg = render_competition_slide(plan, sample_lock, total=12)
        assert svg is not None
        assert "03 / 12" in svg

    def test_unknown_layout_returns_none(self, sample_lock):
        plan = SlidePlan(
            index=1,
            layout="unknown-layout",
            title="Test",
        )
        svg = render_competition_slide(plan, sample_lock, total=10)
        assert svg is None
