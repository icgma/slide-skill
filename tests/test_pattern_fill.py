from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from slide_skill.pattern_fill import (
    collect_patterns,
    resolve_pattern_fill,
    _svg_color_to_rgb,
    _length,
)


SVG_PATTERN = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <pattern id="dots" width="10" height="10" patternUnits="userSpaceOnUse">
      <circle cx="5" cy="5" r="2" fill="#000000"/>
    </pattern>
  </defs>
  <rect x="0" y="0" width="200" height="100" fill="url(#dots)"/>
</svg>
"""

SVG_PATTERN_RECT = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse">
      <line x1="0" y1="0" x2="8" y2="8" stroke="#333333"/>
    </pattern>
  </defs>
  <rect x="0" y="0" width="100" height="100" fill="url(#hatch)"/>
</svg>
"""

SVG_NO_DEFS = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <rect x="10" y="10" width="200" height="100" fill="#FF0000"/>
</svg>
"""

SVG_MULTIPLE = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <pattern id="p1" width="5" height="5">
      <rect x="0" y="0" width="5" height="5" fill="#AABBCC"/>
    </pattern>
    <pattern id="p2" width="20" height="20">
      <circle cx="10" cy="10" r="5" fill="#FF0000"/>
    </pattern>
  </defs>
</svg>
"""


class CollectPatternsTest(unittest.TestCase):
    def test_circle_pattern(self) -> None:
        root = ET.fromstring(SVG_PATTERN)
        patterns = collect_patterns(root)
        self.assertIn("dots", patterns)
        p = patterns["dots"]
        self.assertEqual(p["type"], "pattern")
        self.assertAlmostEqual(p["width"], 10.0)
        self.assertAlmostEqual(p["height"], 10.0)

    def test_line_pattern(self) -> None:
        root = ET.fromstring(SVG_PATTERN_RECT)
        patterns = collect_patterns(root)
        self.assertIn("hatch", patterns)
        p = patterns["hatch"]
        self.assertAlmostEqual(p["width"], 8.0)

    def test_no_defs(self) -> None:
        root = ET.fromstring(SVG_NO_DEFS)
        patterns = collect_patterns(root)
        self.assertEqual(patterns, {})

    def test_multiple_patterns(self) -> None:
        root = ET.fromstring(SVG_MULTIPLE)
        patterns = collect_patterns(root)
        self.assertIn("p1", patterns)
        self.assertIn("p2", patterns)

    def test_pattern_no_id_skipped(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <pattern width="10" height="10">
      <circle cx="5" cy="5" r="2"/>
    </pattern>
  </defs>
</svg>"""
        root = ET.fromstring(svg)
        patterns = collect_patterns(root)
        self.assertEqual(patterns, {})


class ResolvePatternFillTest(unittest.TestCase):
    def test_resolve_existing(self) -> None:
        root = ET.fromstring(SVG_PATTERN)
        patterns = collect_patterns(root)
        result = resolve_pattern_fill("url(#dots)", patterns)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "pattern")

    def test_resolve_missing(self) -> None:
        root = ET.fromstring(SVG_PATTERN)
        patterns = collect_patterns(root)
        result = resolve_pattern_fill("url(#nonexistent)", patterns)
        self.assertIsNone(result)

    def test_resolve_not_url(self) -> None:
        result = resolve_pattern_fill("#FF0000", {})
        self.assertIsNone(result)


class SvgColorTest(unittest.TestCase):
    def test_hex6(self) -> None:
        self.assertEqual(_svg_color_to_rgb("#FF0000"), (255, 0, 0))

    def test_hex3(self) -> None:
        self.assertEqual(_svg_color_to_rgb("#F00"), (255, 0, 0))

    def test_none(self) -> None:
        self.assertIsNone(_svg_color_to_rgb("none"))

    def test_empty(self) -> None:
        self.assertIsNone(_svg_color_to_rgb(""))

    def test_invalid(self) -> None:
        self.assertIsNone(_svg_color_to_rgb("invalid"))


class LengthTest(unittest.TestCase):
    def test_px(self) -> None:
        self.assertAlmostEqual(_length("10px"), 10.0)

    def test_pt(self) -> None:
        self.assertAlmostEqual(_length("10pt"), 13.33, places=1)

    def test_bare(self) -> None:
        self.assertAlmostEqual(_length("10"), 10.0)

    def test_invalid(self) -> None:
        self.assertAlmostEqual(_length("abc"), 0.0)


class RenderPatternImageTest(unittest.TestCase):
    def test_render_produces_file(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow not installed")
        root = ET.fromstring(SVG_PATTERN)
        patterns = collect_patterns(root)
        from slide_skill.pattern_fill import render_pattern_image
        path = render_pattern_image(patterns["dots"])
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())

    def test_render_without_pillow(self) -> None:
        import slide_skill.pattern_fill as pf
        original = None
        try:
            from PIL import Image
        except ImportError:
            pattern = {"width": 10, "height": 10, "x": 0, "y": 0, "children_xml": ""}
            result = pf.render_pattern_image(pattern)
            self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
