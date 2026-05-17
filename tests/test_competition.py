import pytest

from slide_skill.competition import (
    COMPETITIONS,
    CompetitionSpec,
    get_competition,
    list_competitions,
    competition_to_markdown,
)


def test_get_competition_valid():
    """All 6 names return correct spec with expected fields."""
    for name in COMPETITIONS:
        spec = get_competition(name)
        assert isinstance(spec, CompetitionSpec)
        assert spec.name == name
        assert spec.name_zh
        assert spec.time_limit_minutes > 0
        assert len(spec.page_range) == 2
        assert len(spec.sections) > 0
        assert spec.tips


def test_get_competition_invalid():
    """Unknown name raises ValueError."""
    with pytest.raises(ValueError):
        get_competition("unknown-competition-name")


def test_list_competitions_returns_six():
    """Returns exactly 6 items."""
    competitions = list_competitions()
    assert len(competitions) == 6


def test_competition_spec_fields():
    """Each spec has non-empty sections, tips, page_range."""
    for spec in list_competitions():
        assert len(spec.sections) > 0
        assert spec.tips.strip() != ""
        assert len(spec.page_range) == 2


def test_competition_to_markdown_contains_heading():
    """Output contains competition name."""
    for spec in list_competitions():
        md = competition_to_markdown(spec)
        assert spec.name_zh in md


def test_competition_to_markdown_contains_time_limit():
    """Output contains time limit."""
    for spec in list_competitions():
        md = competition_to_markdown(spec)
        assert str(spec.time_limit_minutes) in md


def test_competition_to_markdown_contains_section_guidance():
    """Output has guidance comments."""
    for spec in list_competitions():
        md = competition_to_markdown(spec)
        for section in spec.sections:
            assert section.guidance in md


def test_section_min_max_valid():
    """Every section has min_pages >= 1, max_pages >= min_pages."""
    for spec in list_competitions():
        for section in spec.sections:
            assert section.min_pages >= 1
            assert section.max_pages >= section.min_pages


def test_page_range_valid():
    """page_range[0] <= page_range[1], both positive."""
    for spec in list_competitions():
        assert spec.page_range[0] > 0
        assert spec.page_range[1] > 0
        assert spec.page_range[0] <= spec.page_range[1]
