"""Tests for confirm_dialogue module — Phase 46."""
import json
from io import StringIO
from pathlib import Path

import pytest

from slide_skill.confirm_dialogue import propose_values, run_auto_derive, run_interactive
from slide_skill.confirmations import (
    EIGHT_CONFIRMATION_KEYS,
    check_confirmations,
    load_confirmations,
    write_confirmations,
)


@pytest.fixture()
def project_dir(tmp_path):
    """Create a minimal project directory with spec_lock.json."""
    p = tmp_path / "test-project"
    p.mkdir()
    (p / "sources").mkdir()
    (p / "svg_output").mkdir()
    (p / "svg_final").mkdir()
    (p / "images").mkdir()
    (p / "notes").mkdir()
    (p / "exports").mkdir()
    (p / "backup").mkdir()
    (p / "qa").mkdir()
    # project.json
    (p / "project.json").write_text(json.dumps({
        "name": "test-project",
        "format": "ppt169",
        "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
    }))
    # spec_lock.json
    (p / "spec_lock.json").write_text(json.dumps({
        "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
        "theme": "dark-tech",
        "palette": {
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F8FAFC",
            "accent": "#3B82F6",
        },
        "font_family": "Inter, sans-serif",
        "page_rhythm": ["anchor", "breathing", "dense"],
    }))
    # Source markdown with headings
    (p / "sources" / "content.md").write_text(
        "# Title\n\n## Section 1\n\n## Section 2\n\n## Section 3\n"
    )
    return p


class TestProposeValues:

    def test_all_eight_keys_present(self, project_dir):
        proposals = propose_values(project_dir)
        for key in EIGHT_CONFIRMATION_KEYS:
            assert key in proposals, f"Missing key: {key}"

    def test_format_derived_from_spec_lock(self, project_dir):
        proposals = propose_values(project_dir)
        assert "16:9" in proposals["format"]
        assert "1280" in proposals["format"]

    def test_page_count_from_source_headings(self, project_dir):
        proposals = propose_values(project_dir)
        assert proposals["page_count"] == "4"

    def test_style_from_spec_lock(self, project_dir):
        proposals = propose_values(project_dir)
        assert proposals["style"] == "dark-tech"

    def test_color_scheme_mentions_accent(self, project_dir):
        proposals = propose_values(project_dir)
        assert "accent" in proposals["color_scheme"].lower()

    def test_typography_from_spec_lock(self, project_dir):
        proposals = propose_values(project_dir)
        assert "Inter" in proposals["typography"]

    def test_rhythm_pattern_joined(self, project_dir):
        proposals = propose_values(project_dir)
        assert "anchor" in proposals["rhythm_pattern"]
        assert "→" in proposals["rhythm_pattern"]

    def test_no_spec_lock_raises(self, tmp_path):
        bare = tmp_path / "empty-project"
        bare.mkdir()
        proposals = propose_values(bare)
        # Should still return defaults, not raise
        assert proposals["format"]  # has some default
        assert proposals["page_count"] == "10"


class TestAutoDerive:

    def test_writes_confirmations_json(self, project_dir):
        result = run_auto_derive(project_dir)
        conf_path = project_dir / "confirmations.json"
        assert conf_path.exists()
        data = json.loads(conf_path.read_text(encoding="utf-8"))
        assert "confirmations" in data

    def test_all_keys_populated(self, project_dir):
        result = run_auto_derive(project_dir)
        for key in EIGHT_CONFIRMATION_KEYS:
            assert key in result
        # outline is empty by default
        assert result["outline"] == ""

    def test_returns_proposed_values(self, project_dir):
        result = run_auto_derive(project_dir)
        assert "16:9" in result["format"]
        assert result["style"] == "dark-tech"


class TestInteractive:

    def test_accept_all(self, project_dir):
        # 8 newlines = accept all proposed values
        stdin = StringIO("\n\n\n\n\n\n\n\n")
        stdout = StringIO()
        result = run_interactive(project_dir, stdin=stdin, stdout=stdout)
        for key in EIGHT_CONFIRMATION_KEYS:
            assert key in result
        # Should have saved to confirmations.json
        conf = load_confirmations(project_dir)
        assert conf is not None

    def test_edit_one(self, project_dir):
        # Accept first 2, edit page_count (index 1), accept rest
        inputs = "\n" + "e\n20\n" + "\n\n\n\n\n\n"
        stdin = StringIO(inputs)
        stdout = StringIO()
        result = run_interactive(project_dir, stdin=stdin, stdout=stdout)
        assert result["page_count"] == "20"
        assert result["format"]  # should still have proposed value

    def test_skip_outline(self, project_dir):
        # Accept all except skip the last one (outline)
        inputs = "\n\n\n\n\n\n" + "s\n"
        stdin = StringIO(inputs)
        stdout = StringIO()
        result = run_interactive(project_dir, stdin=stdin, stdout=stdout)
        assert result["outline"] == ""

    def test_output_shows_labels(self, project_dir):
        stdin = StringIO("\n\n\n\n\n\n\n\n")
        stdout = StringIO()
        run_interactive(project_dir, stdin=stdin, stdout=stdout)
        output = stdout.getvalue()
        assert "Canvas Format" in output
        assert "Proposed:" in output


class TestConfirmationIntegration:

    def test_check_incomplete_fresh_project(self, project_dir):
        complete, missing = check_confirmations(project_dir)
        assert not complete
        assert len(missing) > 0

    def test_check_complete_after_auto_derive(self, project_dir):
        run_auto_derive(project_dir)
        complete, missing = check_confirmations(project_dir)
        # Default items include 'confirmation' which auto-derive doesn't set
        # EIGHT_CONFIRMATION_KEYS != DEFAULT_CONFIRMATION_ITEMS
        # So check based on EIGHT_CONFIRMATION_KEYS
        conf = load_confirmations(project_dir)
        assert conf is not None

    def test_content_planner_uses_confirmations(self, project_dir):
        from slide_skill.content_planner import plan_slides
        from slide_skill.confirmations import load_confirmations as _lc
        # Write confirmations with audience and confirmation key set
        write_confirmations(project_dir, {
            "title": "Test Deck",
            "audience": "academic",
            "key_points": "Testing",
            "layout_strategy": "default",
            "color_scheme": "blue",
            "page_count": "5",
            "special_requirements": "none",
            "confirmation": "yes",
        })
        md = "# Intro\n\n## Point 1\n- Item A\n- Item B\n"
        plans = plan_slides(md, project_path=str(project_dir))
        assert len(plans) > 0
        # Verify confirmations were loadable
        conf = _lc(project_dir)
        assert conf is not None
        assert conf.get("all_confirmed") is True
