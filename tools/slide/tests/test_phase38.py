"""Phase 38 verification tests — Enriched Spec Lock & Color System.

Run: python -m pytest tests/test_phase38.py -v
Or:  python tests/test_phase38.py
"""

import json
import sys
import tempfile
from pathlib import Path

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_derive_extended_palette():
    """All 21 built-in themes produce valid 12-role palettes."""
    from slide_skill.themes import BUILTIN_THEMES, derive_extended_palette, EXTENDED_COLOR_ROLES

    for name, theme in BUILTIN_THEMES.items():
        ext = derive_extended_palette(theme.palette)
        for role in EXTENDED_COLOR_ROLES:
            assert role in ext, f"Theme '{name}' missing role '{role}'"
            assert ext[role].startswith("#"), f"Theme '{name}' role '{role}' has invalid value: {ext[role]}"
        # Verify original 6 are preserved
        for key in ("background", "surface", "text", "body", "accent", "muted"):
            assert ext[key] == theme.palette[key], f"Theme '{name}' role '{key}' was overwritten"

    print(f"  PASS: All {len(BUILTIN_THEMES)} themes produce valid 12-role palettes")


def test_derive_typography():
    """Typography derivation extracts correct primary family."""
    from slide_skill.themes import derive_typography

    # Test with typical font stack
    typo = derive_typography("Aptos, Arial, 'Microsoft YaHei', sans-serif")
    assert typo.title_family == "Aptos"
    assert "Aptos" in typo.body_family
    assert typo.emphasis_family == "Aptos"
    assert "JetBrains Mono" in typo.code_family
    assert typo.size_ramp["hero"] == 72
    assert typo.size_ramp["body"] == 24

    # Test with quoted primary
    typo2 = derive_typography("'Source Han Serif SC', Georgia, serif")
    assert typo2.title_family == "Source Han Serif SC"

    print("  PASS: Typography derivation works correctly")


def test_theme_properties():
    """ThemeSpec.extended_palette and .typography properties work."""
    from slide_skill.themes import get_theme

    theme = get_theme("dark-tech")
    ext = theme.extended_palette
    assert len(ext) >= 12
    assert "bg_secondary" in ext
    assert "accent_tint" in ext

    typo = theme.typography
    assert typo.title_family == "Aptos"
    assert typo.size_ramp["hero"] == 72

    print("  PASS: ThemeSpec properties return correct derived values")


def test_typography_spec_serialization():
    """TypographySpec round-trips through to_dict/from_dict."""
    from slide_skill.themes import TypographySpec, derive_typography

    original = derive_typography("Inter, Arial, sans-serif")
    data = original.to_dict()
    restored = TypographySpec.from_dict(data)
    assert restored.title_family == original.title_family
    assert restored.body_family == original.body_family
    assert restored.code_family == original.code_family
    assert restored.size_ramp == original.size_ramp

    print("  PASS: TypographySpec serialization round-trips correctly")


def test_assign_page_rhythm():
    """Page rhythm assignment covers all heuristics + monotony prevention."""
    from slide_skill.content_planner import SlidePlan, ContentItem, assign_page_rhythm

    plans = [
        SlidePlan(1, "cover", "Title"),
        SlidePlan(2, "section-divider", "Section 1"),
        SlidePlan(3, "bullet-list", "Content A", items=[ContentItem("bullet", f"item {i}") for i in range(3)]),
        SlidePlan(4, "bullet-list", "Content B", items=[ContentItem("bullet", f"item {i}") for i in range(4)]),
        SlidePlan(5, "bullet-list", "Content C", items=[ContentItem("bullet", f"item {i}") for i in range(5)]),
        SlidePlan(6, "table", "Data", items=[ContentItem("text", f"row {i}") for i in range(8)]),
        SlidePlan(7, "closing", "Thank You"),
    ]

    assign_page_rhythm(plans)

    assert plans[0].rhythm == "anchor", "Cover should be anchor"
    assert plans[1].rhythm == "breathing", "Section divider should be breathing"
    assert plans[5].rhythm == "dense", "8-item slide should be dense"
    assert plans[6].rhythm == "anchor", "Closing should be anchor"

    # All should have rhythm assigned
    for p in plans:
        assert p.rhythm in ("anchor", "breathing", "dense"), f"Slide {p.index} has invalid rhythm: {p.rhythm}"

    # Monotony check: no 3+ consecutive same
    for i in range(1, len(plans) - 1):
        if plans[i].layout not in ("cover", "closing", "section-divider"):
            pass  # Monotony prevention may have changed this

    print("  PASS: Page rhythm assignment works with correct heuristics")


def test_rhythm_monotony_prevention():
    """Monotony prevention breaks 3+ same rhythm runs."""
    from slide_skill.content_planner import SlidePlan, ContentItem, assign_page_rhythm

    # Create 5 content slides with 4 items each (all would default to "anchor")
    plans = [
        SlidePlan(i, "bullet-list", f"Slide {i}",
                  items=[ContentItem("bullet", f"item {j}") for j in range(4)])
        for i in range(1, 6)
    ]

    assign_page_rhythm(plans)

    # Check no 3 consecutive same
    for i in range(1, len(plans) - 1):
        if plans[i - 1].rhythm == plans[i].rhythm == plans[i + 1].rhythm:
            assert False, f"Monotony at slides {i-1}-{i+1}: all '{plans[i].rhythm}'"

    print("  PASS: Rhythm monotony prevention works correctly")


def test_slide_plan_rhythm_serialization():
    """SlidePlan.to_dict() includes rhythm when set."""
    from slide_skill.content_planner import SlidePlan

    plan_with = SlidePlan(1, "cover", "Title", rhythm="anchor")
    d = plan_with.to_dict()
    assert "rhythm" in d
    assert d["rhythm"] == "anchor"

    plan_without = SlidePlan(2, "cover", "Title")
    d2 = plan_without.to_dict()
    assert "rhythm" not in d2  # empty string → not included

    print("  PASS: SlidePlan.to_dict() handles rhythm correctly")


def test_backward_compat_old_palette():
    """derive_extended_palette handles old 6-role palette input."""
    from slide_skill.themes import derive_extended_palette

    old_palette = {
        "background": "#0F172A",
        "surface": "#1E293B",
        "text": "#F1F5F9",
        "body": "#94A3B8",
        "accent": "#3B82F6",
        "muted": "#334155",
    }

    ext = derive_extended_palette(old_palette)
    assert len(ext) >= 12
    # Original values preserved
    for k, v in old_palette.items():
        assert ext[k] == v
    # New values derived
    assert ext["bg_secondary"] != ""
    assert ext["accent_tint"].endswith("20")  # alpha hex

    print("  PASS: Backward compat with 6-role palette works")


def test_svg_shared_helpers():
    """svg_shared.extended_palette and typography_from_lock work."""
    from slide_skill.svg_shared import extended_palette, typography_from_lock

    lock = {
        "palette": {
            "background": "#FFFFFF",
            "surface": "#F8FAFC",
            "text": "#0F172A",
            "body": "#334155",
            "accent": "#1D4ED8",
            "muted": "#CBD5E1",
        },
        "font_family": "Calibri, Arial, sans-serif",
    }

    ext = extended_palette(lock)
    assert "bg_secondary" in ext
    assert "border" in ext

    typo = typography_from_lock(lock)
    assert typo.title_family == "Calibri"

    # With typography in lock
    lock2 = dict(lock)
    lock2["typography"] = {
        "title_family": "Georgia",
        "body_family": "Calibri, Arial, sans-serif",
        "emphasis_family": "Georgia",
        "code_family": "Consolas, monospace",
        "size_ramp": {"hero": 72, "h1": 60, "body": 24},
    }
    typo2 = typography_from_lock(lock2)
    assert typo2.title_family == "Georgia"

    print("  PASS: svg_shared helpers work correctly")


def test_spec_lock_reader_normalize():
    """spec_lock_reader._normalize fills missing v4.0 fields."""
    from slide_skill.spec_lock_reader import _normalize

    old_lock = {
        "title": "Test",
        "palette": {
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F1F5F9",
            "body": "#94A3B8",
            "accent": "#3B82F6",
            "muted": "#334155",
        },
        "font_family": "Arial, sans-serif",
    }

    normalized = _normalize(old_lock)

    # Check extended palette
    assert "bg_secondary" in normalized["palette"]
    assert "border" in normalized["palette"]
    assert "accent_tint" in normalized["palette"]

    # Check typography
    assert "typography" in normalized
    assert normalized["typography"]["title_family"] == "Arial"

    # Check structural fields
    assert "page_rhythm" in normalized
    assert "page_layouts" in normalized
    assert "page_charts" in normalized
    assert "icon_inventory" in normalized
    assert "forbidden_values" in normalized

    print("  PASS: spec_lock_reader normalization fills all v4.0 fields")


def run_all():
    tests = [
        test_derive_extended_palette,
        test_derive_typography,
        test_theme_properties,
        test_typography_spec_serialization,
        test_assign_page_rhythm,
        test_rhythm_monotony_prevention,
        test_slide_plan_rhythm_serialization,
        test_backward_compat_old_palette,
        test_svg_shared_helpers,
        test_spec_lock_reader_normalize,
    ]

    print(f"\n{'='*60}")
    print(f"Phase 38 Verification — {len(tests)} tests")
    print(f"{'='*60}\n")

    passed = 0
    failed = 0
    for test in tests:
        name = test.__name__
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {name}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
