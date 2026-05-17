"""Tests for the 80-template registry (slide_skill.templates)."""
from __future__ import annotations

import pytest

from slide_skill.templates import (
    CATEGORIES,
    TEMPLATES,
    TemplateSpec,
    get_template,
    list_categories,
    list_templates,
    template_outline_markdown,
)
from slide_skill.themes import BUILTIN_THEMES


def test_exactly_ten_categories():
    assert len(CATEGORIES) == 10


def test_at_least_eighty_templates():
    assert len(TEMPLATES) >= 80


def test_each_category_has_at_least_eight():
    counts = {slug: 0 for slug in CATEGORIES}
    for t in TEMPLATES.values():
        counts[t.category] += 1
    for slug, n in counts.items():
        assert n >= 8, f"category {slug} only has {n} templates"


def test_all_slugs_unique():
    slugs = [t.slug for t in TEMPLATES.values()]
    assert len(slugs) == len(set(slugs))


def test_every_template_uses_a_known_theme():
    for t in TEMPLATES.values():
        assert t.theme in BUILTIN_THEMES, (
            f"template {t.slug} references unknown theme {t.theme}"
        )


def test_every_template_has_outline_and_layouts():
    for t in TEMPLATES.values():
        assert len(t.outline) >= 5, f"{t.slug} outline too short"
        assert len(t.layouts) >= 4, f"{t.slug} layouts too short"
        assert t.persona, f"{t.slug} missing persona"
        assert t.name_zh and t.name_en, f"{t.slug} missing names"


def test_categories_are_valid():
    for t in TEMPLATES.values():
        assert t.category in CATEGORIES


def test_list_templates_filter():
    biz = list_templates("business")
    assert all(t.category == "business" for t in biz)
    assert len(biz) >= 8


def test_list_templates_unknown_raises():
    with pytest.raises(ValueError):
        list_templates("nonexistent")


def test_list_categories_returns_counts():
    cats = list_categories()
    assert len(cats) == 10
    for slug, label, count in cats:
        assert slug in CATEGORIES
        assert count >= 8


def test_get_template_known():
    spec = get_template("biz-mck-strategy")
    assert isinstance(spec, TemplateSpec)
    assert spec.category == "business"


def test_get_template_unknown_raises():
    with pytest.raises(KeyError):
        get_template("does-not-exist")


def test_template_outline_markdown_renders():
    spec = get_template("biz-mck-strategy")
    md = template_outline_markdown(spec, title="My Custom Title")
    assert md.startswith("# My Custom Title")
    for heading in spec.outline:
        assert heading in md


def test_new_themes_registered():
    """v3.1 added 10 themes absorbed from pptx + ui-ux-pro-max skills."""
    new_names = {
        "midnight-executive", "forest-moss", "coral-energy",
        "terracotta-warm", "ocean-deep", "charcoal-minimal",
        "berry-cream", "sage-calm", "academic-royal", "indigo-saas",
    }
    for name in new_names:
        assert name in BUILTIN_THEMES, f"missing theme {name}"


def test_templates_cover_every_new_theme():
    """Each absorbed theme should be referenced by at least one template."""
    used = {t.theme for t in TEMPLATES.values()}
    for name in (
        "midnight-executive", "forest-moss", "coral-energy",
        "terracotta-warm", "ocean-deep", "charcoal-minimal",
        "berry-cream", "sage-calm", "academic-royal", "indigo-saas",
    ):
        assert name in used, f"new theme {name} unused by any template"
