"""Tests for v1.4 Phase 19 — Icon Library."""

from __future__ import annotations

import re
import unittest
from xml.etree import ElementTree as ET

from slide_skill import icons
from slide_skill.themes import get_theme


class IconLibraryTests(unittest.TestCase):
    def test_inline_set_present(self) -> None:
        names = icons.list_icons("lucide")
        for must_have in ("rocket", "flame", "check", "x", "bar-chart", "code", "users"):
            self.assertIn(must_have, names)

    def test_get_paths_default_pack(self) -> None:
        # Bare name resolves under lucide pack.
        body = icons.get_icon_paths("rocket")
        self.assertIn("path", body)
        self.assertEqual(body, icons.get_icon_paths("lucide:rocket"))

    def test_unknown_icon_raises(self) -> None:
        with self.assertRaises(KeyError):
            icons.get_icon_paths("does-not-exist")

    def test_invalid_spec_raises(self) -> None:
        with self.assertRaises(ValueError):
            icons.get_icon_paths("../etc/passwd")

    def test_render_icon_svg_is_well_formed(self) -> None:
        svg = icons.render_icon_svg("rocket", size=64)
        # Must parse as XML.
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.endswith("svg"))
        self.assertEqual(root.get("width"), "64")
        self.assertEqual(root.get("height"), "64")
        self.assertEqual(root.get("viewBox"), "0 0 24 24")

    def test_render_icon_svg_uses_theme_stroke(self) -> None:
        theme = get_theme("dark-tech")
        svg = icons.render_icon_svg("flame", theme=theme)
        self.assertIn(theme.icons["stroke"], svg)

    def test_render_icon_svg_overrides_stroke_and_weight(self) -> None:
        svg = icons.render_icon_svg("check", stroke="#FF00FF", weight=3)
        self.assertIn('stroke="#FF00FF"', svg)
        self.assertIn('stroke-width="3"', svg)

    def test_render_icon_svg_position(self) -> None:
        svg = icons.render_icon_svg("star", x=100, y=200, size=32)
        self.assertIn('x="100"', svg)
        self.assertIn('y="200"', svg)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
