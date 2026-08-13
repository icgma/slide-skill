"""Phase 40-43 verification tests — v4.0 AI-Authored Visual Excellence."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_image_layout_patterns_exist():
    """Phase 40: image-layout-patterns.md exists with 72+ patterns."""
    ref = Path(__file__).resolve().parent.parent / "src" / "slide_skill" / "references" / "image-layout-patterns.md"
    assert ref.exists(), f"Missing: {ref}"
    text = ref.read_text(encoding="utf-8")
    # Count pattern rows in tables (lines starting with | # |)
    pattern_lines = [l for l in text.splitlines() if l.strip().startswith("| ") and not l.strip().startswith("| #") and not l.strip().startswith("|---") and not l.strip().startswith("| Pattern")]
    assert len(pattern_lines) >= 72, f"Expected 72+ patterns, found {len(pattern_lines)}"


def test_image_layout_spec_exist():
    """Phase 40: image-layout-spec.md dimension calculator exists."""
    ref = Path(__file__).resolve().parent.parent / "src" / "slide_skill" / "references" / "image-layout-spec.md"
    assert ref.exists(), f"Missing: {ref}"
    text = ref.read_text(encoding="utf-8")
    assert "CANVAS_W = 1280" in text
    assert "full-bleed" in text
    assert "grid-2x2" in text


def test_chart_templates_count():
    """Phase 41: at least 15 chart SVG templates exist."""
    charts_dir = Path(__file__).resolve().parent.parent / "src" / "slide_skill" / "templates" / "charts"
    assert charts_dir.is_dir(), f"Missing charts dir: {charts_dir}"
    svgs = list(charts_dir.glob("*.svg"))
    assert len(svgs) >= 15, f"Expected 15+ chart SVGs, found {len(svgs)}: {[s.name for s in svgs]}"


def test_chart_index_valid():
    """Phase 41: charts_index.json is valid and lists all templates."""
    index_path = Path(__file__).resolve().parent.parent / "src" / "slide_skill" / "templates" / "charts" / "charts_index.json"
    assert index_path.exists(), f"Missing: {index_path}"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert "templates" in data
    assert len(data["templates"]) >= 15
    # Verify all files exist
    charts_dir = index_path.parent
    for entry in data["templates"]:
        svg_path = charts_dir / entry["file"]
        assert svg_path.exists(), f"Index references missing file: {entry['file']}"


def test_chart_style_guide_exists():
    """Phase 41: CHART_STYLE_GUIDE.md exists."""
    guide = Path(__file__).resolve().parent.parent / "src" / "slide_skill" / "templates" / "charts" / "CHART_STYLE_GUIDE.md"
    assert guide.exists()
    text = guide.read_text(encoding="utf-8")
    assert "plot-area" in text  # Plot area convention
    assert "Card Container" in text


def test_layout_templates_3_styles():
    """Phase 42: layout templates exist in 3 styles with 8 each."""
    layouts_dir = Path(__file__).resolve().parent.parent / "src" / "slide_skill" / "templates" / "layouts"
    assert layouts_dir.is_dir()
    for style in ["general", "academic", "creative"]:
        style_dir = layouts_dir / style
        assert style_dir.is_dir(), f"Missing style directory: {style}"
        svgs = list(style_dir.glob("*.svg"))
        assert len(svgs) >= 8, f"Expected 8+ SVGs in {style}, found {len(svgs)}"


def test_layouts_index_valid():
    """Phase 42: layouts_index.json is valid and lists all templates."""
    index_path = Path(__file__).resolve().parent.parent / "src" / "slide_skill" / "templates" / "layouts" / "layouts_index.json"
    assert index_path.exists()
    data = json.loads(index_path.read_text(encoding="utf-8"))
    assert "styles" in data
    assert len(data["styles"]) >= 3
    total = sum(len(v) for v in data["styles"].values())
    assert total >= 24, f"Expected 24+ layout templates total, found {total}"


def test_image_base_reference():
    """Phase 43: image-base.md exists with prompt templates."""
    ref = Path(__file__).resolve().parent.parent / "src" / "slide_skill" / "references" / "image-base.md"
    assert ref.exists()
    text = ref.read_text(encoding="utf-8")
    assert "Prompt Template" in text
    assert "Rendering Styles" in text


def test_image_palettes_count():
    """Phase 43: at least 14 palette guides exist."""
    palettes_dir = Path(__file__).resolve().parent.parent / "src" / "slide_skill" / "references" / "image-palettes"
    assert palettes_dir.is_dir()
    mds = list(palettes_dir.glob("*.md"))
    assert len(mds) >= 14, f"Expected 14+ palette guides, found {len(mds)}"


def test_image_renderings_count():
    """Phase 43: at least 12 rendering style guides exist."""
    renders_dir = Path(__file__).resolve().parent.parent / "src" / "slide_skill" / "references" / "image-renderings"
    assert renders_dir.is_dir()
    mds = list(renders_dir.glob("*.md"))
    assert len(mds) >= 12, f"Expected 12+ rendering guides, found {len(mds)}"


def test_image_generate_enhanced():
    """Phase 43: image_generate module has palette/rendering support."""
    from slide_skill.image_generate import (
        list_palettes,
        list_rendering_styles,
        enhance_prompt,
        build_image_manifest,
    )
    palettes = list_palettes()
    assert len(palettes) >= 14, f"Expected 14+ palettes, found {len(palettes)}"

    styles = list_rendering_styles()
    assert len(styles) >= 12, f"Expected 12+ styles, found {len(styles)}"

    # Test prompt enhancement
    enhanced = enhance_prompt("a dashboard", palette="tech-midnight", rendering="flat")
    assert "flat" in enhanced.lower()
    assert "No text" in enhanced


def test_design_guide_references_new_docs():
    """All phases: design guide references new materials."""
    from slide_skill.design_guide import _render_guide
    from slide_skill.themes import get_theme
    theme = get_theme("dark-tech")
    guide_text = _render_guide(theme)
    assert "image-layout-patterns.md" in guide_text
    assert "image-base.md" in guide_text
    assert "templates/charts/" in guide_text
    assert "templates/layouts/" in guide_text


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed}/{passed + failed} tests passed")
    sys.exit(1 if failed else 0)
