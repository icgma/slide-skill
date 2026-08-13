"""Phase 39 verification — Executor Reference System."""

import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_reference_files_exist():
    """All 4 reference files exist in the package."""
    from slide_skill.design_guide import _REFERENCES_DIR

    expected = [
        "executor-base.md",
        "executor-general.md",
        "executor-academic.md",
        "shared-standards.md",
    ]
    for name in expected:
        path = _REFERENCES_DIR / name
        assert path.is_file(), f"Missing reference file: {path}"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, f"Reference file too short: {name} ({len(content)} chars)"

    print(f"  PASS: All 4 reference files exist and have content")


def test_reference_line_counts():
    """Reference files meet minimum line count targets."""
    from slide_skill.design_guide import _REFERENCES_DIR

    targets = {
        "executor-base.md": 350,      # target ~400
        "executor-general.md": 80,    # target ~100
        "executor-academic.md": 70,   # target ~80
        "shared-standards.md": 400,   # target ~500
    }
    total = 0
    for name, min_lines in targets.items():
        path = _REFERENCES_DIR / name
        lines = path.read_text(encoding="utf-8").count("\n") + 1
        total += lines
        assert lines >= min_lines, (
            f"{name}: {lines} lines < minimum {min_lines}"
        )
        print(f"    {name}: {lines} lines (min: {min_lines}) OK")

    print(f"  PASS: Total reference lines: {total} (target: 1000+)")
    assert total >= 1000, f"Total lines {total} < 1000"


def test_copy_references():
    """copy_references copies files into project directory."""
    from slide_skill.design_guide import copy_references

    with tempfile.TemporaryDirectory() as tmpdir:
        project = Path(tmpdir) / "test_project"
        project.mkdir()

        dest = copy_references(project)
        assert dest.is_dir(), "references/ dir not created"

        files = list(dest.glob("*.md"))
        assert len(files) >= 4, f"Expected 4+ files, got {len(files)}"

        names = {f.name for f in files}
        assert "executor-base.md" in names
        assert "shared-standards.md" in names

    print("  PASS: copy_references works correctly")


def test_build_design_guide_includes_references():
    """build_design_guide output includes reference section."""
    from slide_skill.design_guide import _REFERENCES_DIR
    from slide_skill.themes import get_theme, ThemeSpec

    # Just test the guide content, not file writing
    theme = get_theme("dark-tech")
    from slide_skill.design_guide import _render_guide
    content = _render_guide(theme)

    assert "Executor Reference Documents" in content
    assert "executor-base.md" in content
    assert "shared-standards.md" in content
    assert "executor-general.md" in content
    assert "executor-academic.md" in content

    print("  PASS: Design guide includes executor reference section")


def test_guide_sections_complete():
    """Design guide has all expected sections."""
    from slide_skill.themes import get_theme
    from slide_skill.design_guide import _render_guide

    theme = get_theme("dark-tech")
    content = _render_guide(theme)

    sections = [
        "1. Design Direction",
        "2. Colour Palette (12 roles)",
        "3. Typography",
        "3.5. Page Rhythm",
        "4. Canvas & Chrome",
        "5. SVG Group Structure",
        "6. Layout Templates",
        "7. Layout Examples",
        "8. Gradients & Filters",
        "9. SVG Authoring Rules",
        "10. Pre-save Checklist",
        "11. Executor Reference Documents",
    ]

    for section in sections:
        assert section in content, f"Missing section: {section}"

    print("  PASS: Design guide has all 12 sections")


def test_guide_line_count():
    """Design guide + references total 1500+ lines."""
    from slide_skill.themes import get_theme
    from slide_skill.design_guide import _render_guide, _REFERENCES_DIR

    theme = get_theme("dark-tech")
    guide_content = _render_guide(theme)
    guide_lines = guide_content.count("\n") + 1

    ref_lines = 0
    for ref_file in _REFERENCES_DIR.glob("*.md"):
        ref_lines += ref_file.read_text(encoding="utf-8").count("\n") + 1

    total = guide_lines + ref_lines
    print(f"    Design guide: {guide_lines} lines")
    print(f"    References: {ref_lines} lines")
    print(f"    Total: {total} lines")
    assert total >= 1500, f"Total {total} < 1500 required"

    print(f"  PASS: Total guidance lines: {total} (requirement: 1500+)")


def run_all():
    tests = [
        test_reference_files_exist,
        test_reference_line_counts,
        test_copy_references,
        test_build_design_guide_includes_references,
        test_guide_sections_complete,
        test_guide_line_count,
    ]

    print(f"\n{'='*60}")
    print(f"Phase 39 Verification — {len(tests)} tests")
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
