"""Tests for v1.4 Phase 25 — Multi-language Templates + Font Preflight."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from slide_skill import i18n
from slide_skill.themes import ThemeSpec, get_theme


def _latin_only_theme() -> ThemeSpec:
    """Synthetic theme with no CJK / RTL coverage — for preflight tests."""
    return ThemeSpec(
        name="latin-only-test",
        palette={"surface": "#fff", "text": "#000", "accent": "#3B82F6", "body": "#333"},
        font_family="Inter, Arial, sans-serif",
        design_hints="",
    )


class DetectLanguageTests(unittest.TestCase):
    def test_english(self) -> None:
        self.assertEqual(i18n.detect_language("Hello world. This is a test."), "en")

    def test_chinese(self) -> None:
        self.assertEqual(i18n.detect_language("这是一段中文测试文本"), "zh")

    def test_japanese(self) -> None:
        # Mix of kanji + kana -> ja (kana wins).
        self.assertEqual(i18n.detect_language("これは日本語のテストです"), "ja")

    def test_korean(self) -> None:
        self.assertEqual(i18n.detect_language("안녕하세요 한국어 테스트"), "ko")

    def test_arabic_rtl(self) -> None:
        self.assertEqual(i18n.detect_language("مرحبا بالعالم هذا اختبار"), "ar")

    def test_empty_returns_en(self) -> None:
        self.assertEqual(i18n.detect_language(""), "en")


class LanguageProfileTests(unittest.TestCase):
    def test_known_profiles_present(self) -> None:
        for code in ("en", "zh", "ja", "ko", "ar", "he", "es", "fr", "de"):
            self.assertIn(code, i18n.LANGUAGE_PROFILES)

    def test_arabic_is_rtl(self) -> None:
        self.assertEqual(i18n.get_language_profile("ar").direction, "rtl")

    def test_unknown_returns_default(self) -> None:
        self.assertIs(i18n.get_language_profile("xx"), i18n.DEFAULT_PROFILE)


class ApplyProfileTests(unittest.TestCase):
    def test_apply_chinese_swaps_fonts(self) -> None:
        theme = _latin_only_theme()
        new_theme = i18n.apply_language_profile(theme, "zh")
        self.assertIn("Noto Sans SC", new_theme.font_family)
        self.assertIn("line_height=1.6", new_theme.design_hints)
        # Original theme not mutated.
        self.assertNotIn("Noto Sans SC", theme.font_family)

    def test_apply_arabic_sets_direction(self) -> None:
        theme = _latin_only_theme()
        new_theme = i18n.apply_language_profile(theme, "ar")
        self.assertIn("direction=rtl", new_theme.design_hints)
        self.assertEqual(i18n._theme_direction(new_theme), "rtl")


class PreflightTests(unittest.TestCase):
    def test_cjk_warning_when_theme_lacks_cjk_font(self) -> None:
        report = i18n.font_preflight(_latin_only_theme(), ["这是中文内容"])
        self.assertEqual(report.language, "zh")
        codes = [f.code for f in report.findings]
        self.assertIn("font.cjk-coverage", codes)
        self.assertTrue(report.ok)  # warnings only, not errors

    def test_rtl_warning_when_arabic_content(self) -> None:
        report = i18n.font_preflight(_latin_only_theme(), ["مرحبا"])
        codes = [f.code for f in report.findings]
        self.assertIn("rtl.direction", codes)

    def test_no_warnings_after_apply_profile(self) -> None:
        theme = i18n.apply_language_profile(_latin_only_theme(), "zh")
        report = i18n.font_preflight(theme, ["纯中文测试"])
        codes = [f.code for f in report.findings]
        self.assertNotIn("font.cjk-coverage", codes)

    def test_lang_mismatch_info(self) -> None:
        report = i18n.font_preflight(_latin_only_theme(), ["plain english"], lang="zh")
        codes = [f.code for f in report.findings]
        self.assertIn("lang.mismatch", codes)


class PreflightProjectTests(unittest.TestCase):
    def test_reads_md_files_and_notes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "slides").mkdir()
            (root / "slides" / "01.md").write_text("# 標題\n本文中文", encoding="utf-8")
            (root / "notes.md").write_text("演示笔记", encoding="utf-8")
            report = i18n.font_preflight_project(_latin_only_theme(), root)
            self.assertEqual(report.language, "zh")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
