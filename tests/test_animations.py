"""Tests for slide transitions and element animations."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from slide_skill.animations import (
    ANIMATION_PRESETS,
    TRANSITION_PRESETS,
    build_timing_xml,
    build_transition_xml,
    inject_transition,
    inject_timing,
)
from slide_skill.exporter import export_project, validate_pptx
from slide_skill.project import init_project


def _make_svg_project(tmp: Path, svg_content: str) -> Path:
    project = init_project("Anim Test", base_dir=tmp / "projects")
    svg_dir = project / "svg_output"
    svg_dir.mkdir(parents=True, exist_ok=True)
    (svg_dir / "slide_01.svg").write_text(svg_content, encoding="utf-8")
    return project


class TransitionXMLTest(unittest.TestCase):
    def test_fade_transition(self) -> None:
        xml = build_transition_xml("fade")
        self.assertIsNotNone(xml)
        self.assertIn("transition", xml.tag)
        self.assertEqual(xml.get("spd"), "med")

    def test_all_transition_types(self) -> None:
        for ttype in TRANSITION_PRESETS:
            xml = build_transition_xml(ttype)
            self.assertIsNotNone(xml, f"Transition '{ttype}' should produce XML")

    def test_unknown_transition_returns_none(self) -> None:
        self.assertIsNone(build_transition_xml("unknown"))

    def test_inject_transition_into_slide(self) -> None:
        from lxml import etree
        P = "http://schemas.openxmlformats.org/presentationml/2006/main"
        slide = etree.Element(f"{{{P}}}sld")
        cSld = etree.SubElement(slide, f"{{{P}}}cSld")
        inject_transition(slide, "fade")
        self.assertEqual(len(list(slide)), 2)


class TimingXMLTest(unittest.TestCase):
    def test_timing_with_one_shape(self) -> None:
        from lxml import etree
        xml = build_timing_xml([{"sp_id": "2", "preset": "fly-in"}])
        self.assertIsNotNone(xml)
        self.assertIn("timing", xml.tag)

    def test_timing_empty_list_returns_none(self) -> None:
        self.assertIsNone(build_timing_xml([]))

    def test_timing_preserves_order(self) -> None:
        from lxml import etree
        shapes = [
            {"sp_id": "2", "preset": "fly-in"},
            {"sp_id": "3", "preset": "fade-in"},
        ]
        xml = build_timing_xml(shapes)
        self.assertIsNotNone(xml)
        xml_bytes = etree.tostring(xml, encoding="unicode")
        self.assertIn('spid="2"', xml_bytes)
        self.assertIn('spid="3"', xml_bytes)

    def test_timing_custom_duration(self) -> None:
        xml = build_timing_xml([{"sp_id": "2", "preset": "fade-in", "duration": 1000}])
        self.assertIsNotNone(xml)


class AnimationIntegrationTest(unittest.TestCase):
    def test_slide_with_transition(self) -> None:
        SVG = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            '<g id="content-main" data-transition="fade">'
            '<rect x="0" y="0" width="1280" height="720" fill="#0F172A"/>'
            '</g>'
            '</svg>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(Path(tmp), SVG)
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)

            with zipfile.ZipFile(deck) as zf:
                slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
                self.assertIn("transition", slide_xml)

    def test_slide_with_animation(self) -> None:
        SVG = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            '<g id="content-bg"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
            '<g id="content-card" data-anim="fade-in" data-anim-duration="800">'
            '<rect x="100" y="100" width="300" height="200" fill="#3B82F6"/>'
            '</g>'
            '</svg>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(Path(tmp), SVG)
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)

            with zipfile.ZipFile(deck) as zf:
                slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
                self.assertIn("timing", slide_xml)

    def test_slide_no_animation_backward_compatible(self) -> None:
        SVG = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            '<g id="content-main"><rect x="0" y="0" width="100" height="100" fill="#111"/></g>'
            '</svg>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(Path(tmp), SVG)
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)

            with zipfile.ZipFile(deck) as zf:
                slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
                self.assertNotIn("timing", slide_xml)
                self.assertNotIn("transition", slide_xml)

    def test_slide_with_transition_and_animation(self) -> None:
        SVG = (
            '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
            '<g id="content-bg" data-transition="wipe">'
            '<rect x="0" y="0" width="1280" height="720" fill="#0F172A"/>'
            '</g>'
            '<g id="content-title" data-anim="fly-in" data-anim-delay="200">'
            '<text x="100" y="100" font-size="44" fill="#FFF">Hello</text>'
            '</g>'
            '</svg>'
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(Path(tmp), SVG)
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)

            with zipfile.ZipFile(deck) as zf:
                slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
                self.assertIn("transition", slide_xml)
                self.assertIn("timing", slide_xml)


if __name__ == "__main__":
    unittest.main()
