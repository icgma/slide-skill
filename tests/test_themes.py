"""Tests for the themes module."""

from __future__ import annotations

import unittest

from slide_skill.themes import THEMES, ThemeSpec, get_theme, list_themes


class ThemeSpecTest(unittest.TestCase):

    def test_all_builtin_themes_exist(self) -> None:
        expected = {
            "dark-tech",
            "light-corporate",
            "warm-editorial",
            "data-forward",
            "vibrant-startup",
            "mckinsey-consulting",
            "anthropic-ai",
            "google-brand",
            "pixel-retro",
            "psychology-warm",
            "medical-clean",
            "gov-red",
            # v5.0 Premium Frontend-Design themes
            "academic-noir",
            "neo-brutalist",
            "industrial-blueprint",
            "organic-clay",
            "art-deco-archive",
            "japandi-zen",
            "high-fashion",
            "retro-terminal",
            "botanical-herbarium",
            "celestial-glass",
            # Phase 52 — Chinese academic defense theme
            "academic-defense",
        }
        self.assertTrue(expected.issubset(set(THEMES.keys())))

    def test_each_theme_has_required_palette_keys(self) -> None:
        required = {"background", "surface", "text", "body", "accent", "muted"}
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                self.assertEqual(set(theme.palette.keys()), required, f"{name} palette missing keys")

    def test_each_theme_palette_values_are_hex(self) -> None:
        import re
        hex_pattern = re.compile(r"^#[0-9A-Fa-f]{6}$")
        for name, theme in THEMES.items():
            for role, color in theme.palette.items():
                with self.subTest(theme=name, role=role):
                    self.assertRegex(color, hex_pattern, f"{name}.{role} is not a valid hex colour")

    def test_each_theme_has_font_family(self) -> None:
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                self.assertTrue(theme.font_family, f"{name} missing font_family")

    def test_each_theme_has_design_hints(self) -> None:
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                self.assertGreater(len(theme.design_hints), 20, f"{name} design_hints too short")

    def test_each_theme_has_layout_rhythm(self) -> None:
        for name, theme in THEMES.items():
            with self.subTest(theme=name):
                self.assertIsInstance(theme.layout_rhythm, list)
                self.assertGreater(len(theme.layout_rhythm), 0)

    def test_get_theme_returns_correct_theme(self) -> None:
        for name in THEMES:
            theme = get_theme(name)
            self.assertEqual(theme.name, name)

    def test_get_theme_falls_back_to_dark_tech(self) -> None:
        theme = get_theme("nonexistent-theme")
        self.assertEqual(theme.name, "dark-tech")

    def test_list_themes_returns_all(self) -> None:
        themes = list_themes()
        self.assertEqual(len(themes), len(THEMES))
        names = {t.name for t in themes}
        self.assertEqual(names, set(THEMES.keys()))

    def test_dark_tech_palette(self) -> None:
        t = get_theme("dark-tech")
        self.assertEqual(t.palette["background"], "#0F172A")
        self.assertEqual(t.palette["accent"], "#3B82F6")

    def test_light_corporate_palette(self) -> None:
        t = get_theme("light-corporate")
        self.assertEqual(t.palette["background"], "#FFFFFF")
        self.assertEqual(t.palette["accent"], "#1D4ED8")

    def test_warm_editorial_palette(self) -> None:
        t = get_theme("warm-editorial")
        self.assertEqual(t.palette["background"], "#FDF6EE")
        self.assertEqual(t.palette["accent"], "#EA580C")

    def test_data_forward_palette(self) -> None:
        t = get_theme("data-forward")
        self.assertEqual(t.palette["background"], "#F1F5F9")
        self.assertEqual(t.palette["accent"], "#0284C7")

    def test_vibrant_startup_palette(self) -> None:
        t = get_theme("vibrant-startup")
        self.assertEqual(t.palette["background"], "#FFFFFF")
        self.assertEqual(t.palette["accent"], "#7C3AED")

    def test_theme_spec_is_dataclass(self) -> None:
        t = get_theme("dark-tech")
        self.assertIsInstance(t, ThemeSpec)
        self.assertEqual(t.name, "dark-tech")


class AcademicDefenseThemeTest(unittest.TestCase):
    """Phase 52 — academic-defense theme contract (ACAD-01)."""

    def test_registered(self) -> None:
        self.assertIn("academic-defense", THEMES)
        t = get_theme("academic-defense")
        self.assertEqual(t.name, "academic-defense")
        self.assertEqual(t.source, "builtin")

    def test_palette_exact_navy_values(self) -> None:
        t = get_theme("academic-defense")
        self.assertEqual(t.palette["background"], "#FFFFFF")
        self.assertEqual(t.palette["surface"], "#F4F6FA")
        self.assertEqual(t.palette["text"], "#1B2A4A")
        self.assertEqual(t.palette["body"], "#44506B")
        self.assertEqual(t.palette["accent"], "#2D4A7A")
        self.assertEqual(t.palette["muted"], "#C9D2E3")

    def test_font_stack_is_yahei_first(self) -> None:
        t = get_theme("academic-defense")
        self.assertTrue(
            t.font_family.startswith("'Microsoft YaHei'"),
            f"font stack must lead with Microsoft YaHei: {t.font_family}",
        )
        typo = t.typography
        self.assertEqual(typo.title_family, "Microsoft YaHei")
        self.assertEqual(typo.body_family, t.font_family)

    def test_extended_palette_derives_all_roles(self) -> None:
        from slide_skill.themes import EXTENDED_COLOR_ROLES
        t = get_theme("academic-defense")
        extended = t.extended_palette
        for role in EXTENDED_COLOR_ROLES:
            with self.subTest(role=role):
                self.assertIn(role, extended)
                self.assertTrue(extended[role].startswith("#"))

    def test_design_hints_encode_academic_conventions(self) -> None:
        t = get_theme("academic-defense")
        self.assertIn("#B03A2E", t.design_hints)  # dark red for key data only
        self.assertIn("总-分-总", t.design_hints)
        self.assertEqual(t.icons, {"stroke": "#1B2A4A", "weight": "1.5"})
        self.assertEqual(t.layout_rhythm, ["anchor", "breathing", "dense"])

    def test_cli_themes_lists_academic_defense(self) -> None:
        import contextlib
        import io

        from slide_skill.cli import main

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = main(["themes"])
        self.assertIn(result, (0, None))
        self.assertIn("academic-defense", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
