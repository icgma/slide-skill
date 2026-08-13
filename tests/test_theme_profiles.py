"""Tests for structural theme profiles."""

from slide_skill.theme_profiles import get_theme_profile


def test_core_theme_profiles_have_distinct_market_variants():
    themes = ["dark-tech", "warm-editorial", "neo-brutalist", "celestial-glass"]
    variants = {
        get_theme_profile({"theme": theme}).market.variant
        for theme in themes
    }
    assert len(variants) >= 3


def test_core_theme_profiles_have_distinct_closing_variants():
    themes = ["dark-tech", "warm-editorial", "neo-brutalist", "celestial-glass"]
    variants = {
        get_theme_profile({"theme": theme}).closing.variant
        for theme in themes
    }
    assert len(variants) >= 3


def test_core_theme_profiles_have_distinct_semantic_scene_variants():
    themes = ["dark-tech", "warm-editorial", "neo-brutalist", "celestial-glass"]
    for scene in ("problem", "solution", "roadmap", "technology"):
        variants = {
            getattr(get_theme_profile({"theme": theme}), scene).variant
            for theme in themes
        }
        assert len(variants) >= 3
