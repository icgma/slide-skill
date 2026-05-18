from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from slide_skill.clip_path import (
    collect_clip_paths,
    resolve_clip_path,
    _circle_to_commands,
    _ellipse_to_commands,
)


SVG_CLIPPATH_RECT = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <clipPath id="clip1">
      <rect x="10" y="10" width="200" height="100"/>
    </clipPath>
  </defs>
  <rect x="0" y="0" width="300" height="200" fill="#FF0000" clip-path="url(#clip1)"/>
</svg>
"""

SVG_CLIPPATH_PATH = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <clipPath id="clip2">
      <path d="M10 10 L200 10 L200 100 L10 100 Z"/>
    </clipPath>
  </defs>
  <circle cx="100" cy="50" r="80" fill="#00FF00" clip-path="url(#clip2)"/>
</svg>
"""

SVG_MASK = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <mask id="mask1">
      <rect x="0" y="0" width="100" height="100" fill="white"/>
    </mask>
  </defs>
  <rect x="0" y="0" width="200" height="200" fill="#0000FF" mask="url(#mask1)"/>
</svg>
"""

SVG_NO_DEFS = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <rect x="10" y="10" width="200" height="100" fill="#FF0000"/>
</svg>
"""

SVG_CLIPPATH_CIRCLE = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <clipPath id="circClip">
      <circle cx="100" cy="100" r="50"/>
    </clipPath>
  </defs>
</svg>
"""


class CollectClipPathsTest(unittest.TestCase):
    def test_rect_clip_path(self) -> None:
        root = ET.fromstring(SVG_CLIPPATH_RECT)
        clips = collect_clip_paths(root)
        self.assertIn("clip1", clips)
        self.assertEqual(clips["clip1"]["type"], "clipPath")
        self.assertGreater(len(clips["clip1"]["commands"]), 0)

    def test_path_clip_path(self) -> None:
        root = ET.fromstring(SVG_CLIPPATH_PATH)
        clips = collect_clip_paths(root)
        self.assertIn("clip2", clips)
        self.assertEqual(clips["clip2"]["type"], "clipPath")
        self.assertGreater(len(clips["clip2"]["commands"]), 0)

    def test_mask(self) -> None:
        root = ET.fromstring(SVG_MASK)
        clips = collect_clip_paths(root)
        self.assertIn("mask1", clips)
        self.assertEqual(clips["mask1"]["type"], "mask")

    def test_no_defs(self) -> None:
        root = ET.fromstring(SVG_NO_DEFS)
        clips = collect_clip_paths(root)
        self.assertEqual(clips, {})

    def test_circle_clip_path(self) -> None:
        root = ET.fromstring(SVG_CLIPPATH_CIRCLE)
        clips = collect_clip_paths(root)
        self.assertIn("circClip", clips)
        cmds = clips["circClip"]["commands"]
        self.assertGreater(len(cmds), 2)

    def test_empty_clip_path(self) -> None:
        svg = """\
<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540">
  <defs>
    <clipPath id="emptyClip"></clipPath>
  </defs>
</svg>"""
        root = ET.fromstring(svg)
        clips = collect_clip_paths(root)
        self.assertIn("emptyClip", clips)
        self.assertEqual(clips["emptyClip"]["commands"], [])


class ResolveClipPathTest(unittest.TestCase):
    def test_resolve_existing(self) -> None:
        root = ET.fromstring(SVG_CLIPPATH_RECT)
        clips = collect_clip_paths(root)
        result = resolve_clip_path("url(#clip1)", clips)
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "clipPath")

    def test_resolve_missing(self) -> None:
        root = ET.fromstring(SVG_CLIPPATH_RECT)
        clips = collect_clip_paths(root)
        result = resolve_clip_path("url(#nonexistent)", clips)
        self.assertIsNone(result)

    def test_resolve_not_url(self) -> None:
        result = resolve_clip_path("something", {})
        self.assertIsNone(result)


class CircleCommandsTest(unittest.TestCase):
    def test_circle_commands_count(self) -> None:
        cmds = _circle_to_commands(100, 100, 50)
        self.assertEqual(len(cmds), 25)
        self.assertEqual(cmds[0][0], "M")
        self.assertEqual(cmds[-1][0], "Z")


class EllipseCommandsTest(unittest.TestCase):
    def test_ellipse_commands_count(self) -> None:
        cmds = _ellipse_to_commands(100, 100, 50, 30)
        self.assertEqual(len(cmds), 25)
        self.assertEqual(cmds[0][0], "M")
        self.assertEqual(cmds[-1][0], "Z")


class SvgQaClipPathTest(unittest.TestCase):
    def test_clip_path_attr_allowed(self) -> None:
        from slide_skill.svg_pipeline import check_svg_file
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            project.mkdir()
            svg_file = project / "test.svg"
            svg_file.write_text(SVG_CLIPPATH_RECT, encoding="utf-8")
            issues = check_svg_file(svg_file, project)
            clip_issues = [i for i in issues if "clip-path" in i.message.lower()]
            self.assertEqual(len(clip_issues), 0, f"clip-path should be allowed, got: {clip_issues}")

    def test_mask_attr_allowed(self) -> None:
        from slide_skill.svg_pipeline import check_svg_file
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            project.mkdir()
            svg_file = project / "test.svg"
            svg_file.write_text(SVG_MASK, encoding="utf-8")
            issues = check_svg_file(svg_file, project)
            mask_issues = [i for i in issues if "mask" in i.message.lower() and "banned" in i.message.lower()]
            self.assertEqual(len(mask_issues), 0, f"mask attribute should be allowed, got: {mask_issues}")


if __name__ == "__main__":
    unittest.main()
