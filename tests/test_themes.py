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


if __name__ == "__main__":
    unittest.main()
