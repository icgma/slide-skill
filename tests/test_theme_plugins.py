"""Tests for v1.4 Phase 18 — Theme Plugin System."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from slide_skill import themes


SAMPLE_THEME = """\
[theme]
name = "midnight"
font_family = "Inter, sans-serif"
design_hints = "Test theme with very dark background."
layout_rhythm = ["anchor", "breathing"]

[theme.palette]
background = "#000000"
surface = "#111111"
text = "#FFFFFF"
body = "#CCCCCC"
accent = "#FF00FF"
muted = "#222222"

[theme.icons]
stroke = "#FFFFFF"
weight = "2"
"""


class ThemePluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._old = os.environ.get("SLIDE_SKILL_THEMES_DIR")
        os.environ["SLIDE_SKILL_THEMES_DIR"] = self._tmp.name
        themes.THEMES.refresh()

    def tearDown(self) -> None:
        if self._old is None:
            os.environ.pop("SLIDE_SKILL_THEMES_DIR", None)
        else:
            os.environ["SLIDE_SKILL_THEMES_DIR"] = self._old
        themes.THEMES.refresh()

    def test_builtins_present(self) -> None:
        names = {t.name for t in themes.list_themes()}
        for expected in ("dark-tech", "light-corporate", "warm-editorial", "data-forward", "vibrant-startup"):
            self.assertIn(expected, names)

    def test_get_theme_unknown_falls_back(self) -> None:
        spec = themes.get_theme("does-not-exist")
        self.assertEqual(spec.name, "dark-tech")

    def test_install_user_theme(self) -> None:
        src = Path(self._tmp.name) / "mytheme.toml"
        src.write_text(SAMPLE_THEME, encoding="utf-8")
        # Install from a *different* path so it gets copied.
        with TemporaryDirectory() as other:
            staged = Path(other) / "mytheme.toml"
            staged.write_text(SAMPLE_THEME, encoding="utf-8")
            dest = themes.install_user_theme(staged)
            self.assertTrue(dest.is_file())
            self.assertEqual(dest.name, "midnight.toml")

        names = {t.name for t in themes.list_themes()}
        self.assertIn("midnight", names)

        spec = themes.get_theme("midnight")
        self.assertEqual(spec.palette["background"], "#000000")
        self.assertEqual(spec.icons["stroke"], "#FFFFFF")
        self.assertTrue(spec.source.startswith("user:"))

    def test_install_refuses_overwrite_unless_flag(self) -> None:
        with TemporaryDirectory() as other:
            staged = Path(other) / "mytheme.toml"
            staged.write_text(SAMPLE_THEME, encoding="utf-8")
            themes.install_user_theme(staged)
            with self.assertRaises(FileExistsError):
                themes.install_user_theme(staged)
            # overwrite=True succeeds
            dest = themes.install_user_theme(staged, overwrite=True)
            self.assertTrue(dest.is_file())

    def test_remove_user_theme(self) -> None:
        with TemporaryDirectory() as other:
            staged = Path(other) / "mytheme.toml"
            staged.write_text(SAMPLE_THEME, encoding="utf-8")
            themes.install_user_theme(staged)
        themes.remove_user_theme("midnight")
        names = {t.name for t in themes.list_themes()}
        self.assertNotIn("midnight", names)

    def test_remove_builtin_refused(self) -> None:
        with self.assertRaises(ValueError):
            themes.remove_user_theme("dark-tech")

    def test_install_rejects_path_traversal_name(self) -> None:
        evil = SAMPLE_THEME.replace('name = "midnight"', 'name = "../../../../tmp/pwned"')
        with TemporaryDirectory() as other:
            staged = Path(other) / "evil.toml"
            staged.write_text(evil, encoding="utf-8")
            with self.assertRaises(ValueError):
                themes.install_user_theme(staged)

    def test_install_rejects_separator_in_name(self) -> None:
        for bad in ("foo/bar", "foo\\bar", "..", ".hidden", ""):
            evil = SAMPLE_THEME.replace('name = "midnight"', f'name = "{bad}"')
            with TemporaryDirectory() as other:
                staged = Path(other) / "evil.toml"
                staged.write_text(evil, encoding="utf-8")
                with self.assertRaises(ValueError):
                    themes.install_user_theme(staged)

    def test_remove_rejects_path_traversal(self) -> None:
        with self.assertRaises(ValueError):
            themes.remove_user_theme("../../etc/passwd")

    def test_user_theme_overrides_builtin_with_same_name(self) -> None:
        custom = SAMPLE_THEME.replace('name = "midnight"', 'name = "dark-tech"')
        custom = custom.replace('background = "#000000"', 'background = "#ABCDEF"')
        with TemporaryDirectory() as other:
            staged = Path(other) / "dark-tech.toml"
            staged.write_text(custom, encoding="utf-8")
            themes.install_user_theme(staged)
        spec = themes.get_theme("dark-tech")
        self.assertEqual(spec.palette["background"], "#ABCDEF")
        self.assertTrue(spec.source.startswith("user:"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
