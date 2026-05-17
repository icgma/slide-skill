"""Tests for SVG geometry conversion — all path command types, polygon, polyline."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from slide_skill.exporter import export_project, validate_pptx
from slide_skill.geometry import (
    CubicBezTo,
    Close,
    LineTo,
    MoveTo,
    Pt,
    compute_bbox,
    parse_svg_path,
    parse_svg_points,
    points_to_commands,
)
from slide_skill.project import init_project
from slide_skill.svg_pipeline import check_project_svg, create_spec, finalize_svg, generate_svg


def _make_svg_project(tmp: Path, svg_content: str) -> Path:
    project = init_project("Geometry Test", base_dir=tmp / "projects")
    svg_dir = project / "svg_output"
    svg_dir.mkdir(parents=True, exist_ok=True)
    svg = svg_dir / "slide_01.svg"
    svg.write_text(svg_content, encoding="utf-8")
    return project


class PathParsingTest(unittest.TestCase):
    def test_move_and_line(self) -> None:
        cmds = parse_svg_path("M 10 20 L 100 200")
        self.assertEqual(len(cmds), 2)
        self.assertIsInstance(cmds[0], MoveTo)
        self.assertAlmostEqual(cmds[0].pt.x, 10)
        self.assertAlmostEqual(cmds[0].pt.y, 20)
        self.assertIsInstance(cmds[1], LineTo)

    def test_relative_move_and_line(self) -> None:
        cmds = parse_svg_path("m 10 20 l 50 60")
        self.assertGreaterEqual(len(cmds), 2)
        self.assertIsInstance(cmds[0], MoveTo)
        self.assertAlmostEqual(cmds[0].pt.x, 10)
        self.assertAlmostEqual(cmds[0].pt.y, 20)
        self.assertIsInstance(cmds[1], LineTo)
        self.assertAlmostEqual(cmds[1].pt.x, 60)
        self.assertAlmostEqual(cmds[1].pt.y, 80)

    def test_cubic_bezier_absolute(self) -> None:
        cmds = parse_svg_path("M 0 0 C 30 40 60 80 100 100")
        has_cubic = any(isinstance(c, CubicBezTo) for c in cmds)
        self.assertTrue(has_cubic)

    def test_cubic_bezier_relative(self) -> None:
        cmds = parse_svg_path("M 10 10 c 20 30 40 50 60 70")
        has_cubic = any(isinstance(c, CubicBezTo) for c in cmds)
        self.assertTrue(has_cubic)
        cubic = next(c for c in cmds if isinstance(c, CubicBezTo))
        self.assertAlmostEqual(cubic.pt3.x, 70)
        self.assertAlmostEqual(cubic.pt3.y, 80)

    def test_smooth_curve_s(self) -> None:
        cmds = parse_svg_path("M 0 0 C 10 20 30 40 50 50 S 90 60 100 100")
        cubics = [c for c in cmds if isinstance(c, CubicBezTo)]
        self.assertGreaterEqual(len(cubics), 2)

    def test_smooth_curve_relative_s(self) -> None:
        cmds = parse_svg_path("M 0 0 C 10 20 30 40 50 50 s 40 10 50 50")
        cubics = [c for c in cmds if isinstance(c, CubicBezTo)]
        self.assertGreaterEqual(len(cubics), 2)

    def test_quadratic_bezier_q(self) -> None:
        cmds = parse_svg_path("M 0 0 Q 50 100 100 0")
        has_cubic = any(isinstance(c, CubicBezTo) for c in cmds)
        self.assertTrue(has_cubic, "Quadratic should be converted to cubic")

    def test_quadratic_bezier_relative_q(self) -> None:
        cmds = parse_svg_path("M 10 10 q 40 80 80 0")
        has_cubic = any(isinstance(c, CubicBezTo) for c in cmds)
        self.assertTrue(has_cubic)

    def test_smooth_quadratic_t(self) -> None:
        cmds = parse_svg_path("M 0 0 Q 50 100 100 0 T 200 0")
        cubics = [c for c in cmds if isinstance(c, CubicBezTo)]
        self.assertGreaterEqual(len(cubics), 2)

    def test_smooth_quadratic_relative_t(self) -> None:
        cmds = parse_svg_path("M 0 0 Q 50 100 100 0 t 100 0")
        cubics = [c for c in cmds if isinstance(c, CubicBezTo)]
        self.assertGreaterEqual(len(cubics), 2)

    def test_arc_absolute_a(self) -> None:
        cmds = parse_svg_path("M 10 80 A 45 45 0 0 0 125 125")
        has_cubic = any(isinstance(c, CubicBezTo) for c in cmds)
        self.assertTrue(has_cubic, "Arc should be converted to cubic bezier")

    def test_arc_relative_a(self) -> None:
        cmds = parse_svg_path("M 10 80 a 45 45 0 0 0 115 45")
        has_cubic = any(isinstance(c, CubicBezTo) for c in cmds)
        self.assertTrue(has_cubic)

    def test_close_z(self) -> None:
        cmds = parse_svg_path("M 10 10 L 100 10 L 100 100 Z")
        has_close = any(isinstance(c, Close) for c in cmds)
        self.assertTrue(has_close)

    def test_close_relative_z(self) -> None:
        cmds = parse_svg_path("M 10 10 l 90 0 l 0 90 z")
        has_close = any(isinstance(c, Close) for c in cmds)
        self.assertTrue(has_close)

    def test_empty_path(self) -> None:
        cmds = parse_svg_path("")
        self.assertEqual(len(cmds), 0)

    def test_all_command_types_combined(self) -> None:
        d = "M 10 10 L 100 10 C 130 10 150 30 150 60 S 150 110 120 110 Q 100 130 80 110 T 40 110 A 30 30 0 0 1 10 60 Z"
        cmds = parse_svg_path(d)
        self.assertGreater(len(cmds), 5)
        types = {type(c).__name__ for c in cmds}
        self.assertTrue(types & {"MoveTo", "LineTo", "CubicBezTo", "Close"})


class PolygonParsingTest(unittest.TestCase):
    def test_polygon_points(self) -> None:
        pts = parse_svg_points("10,10 100,10 100,100")
        self.assertEqual(len(pts), 3)
        self.assertAlmostEqual(pts[0].x, 10)

    def test_polygon_points_space_separated(self) -> None:
        pts = parse_svg_points("10 10 100 10 100 100")
        self.assertEqual(len(pts), 3)

    def test_polygon_closed_commands(self) -> None:
        pts = parse_svg_points("10,10 100,10 100,100")
        cmds = points_to_commands(pts, closed=True)
        has_close = any(isinstance(c, Close) for c in cmds)
        self.assertTrue(has_close)

    def test_polyline_open_commands(self) -> None:
        pts = parse_svg_points("10,10 100,10 100,100")
        cmds = points_to_commands(pts, closed=False)
        has_close = any(isinstance(c, Close) for c in cmds)
        self.assertFalse(has_close)

    def test_empty_points(self) -> None:
        pts = parse_svg_points("")
        self.assertEqual(len(pts), 0)


class BBoxTest(unittest.TestCase):
    def test_bbox_from_commands(self) -> None:
        cmds = [MoveTo(Pt(10, 20)), LineTo(Pt(100, 200))]
        min_x, min_y, max_x, max_y = compute_bbox(cmds)
        self.assertAlmostEqual(min_x, 10)
        self.assertAlmostEqual(min_y, 20)
        self.assertAlmostEqual(max_x, 100)
        self.assertAlmostEqual(max_y, 200)

    def test_bbox_with_cubic(self) -> None:
        cmds = [
            MoveTo(Pt(0, 0)),
            CubicBezTo(Pt(50, 0), Pt(50, 100), Pt(100, 100)),
        ]
        min_x, min_y, max_x, max_y = compute_bbox(cmds)
        self.assertAlmostEqual(min_x, 0)
        self.assertAlmostEqual(max_x, 100)
        self.assertAlmostEqual(max_y, 100)


class SVGQAWithGeometryTest(unittest.TestCase):
    def test_qa_allows_path_with_d_attribute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                '<g id="content-main"><path d="M 10 10 L 100 100" fill="none" stroke="#111111"/></g>'
                "</svg>",
            )
            ok, issues = check_project_svg(project)
            self.assertTrue(ok, [f"{i.level}: {i.message}" for i in issues])

    def test_qa_allows_polygon_with_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                '<g id="content-main"><polygon points="10,10 100,10 100,100" fill="#333333"/></g>'
                "</svg>",
            )
            ok, issues = check_project_svg(project)
            self.assertTrue(ok, [f"{i.level}: {i.message}" for i in issues])

    def test_qa_allows_polyline_with_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                '<g id="content-main"><polyline points="10,10 200,50 100,100" fill="none" stroke="#111111"/></g>'
                "</svg>",
            )
            ok, issues = check_project_svg(project)
            self.assertTrue(ok, [f"{i.level}: {i.message}" for i in issues])

    def test_qa_rejects_path_without_d(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                '<g id="content-main"><path fill="#111111"/></g>'
                "</svg>",
            )
            ok, issues = check_project_svg(project)
            self.assertFalse(ok)
            self.assertTrue(any("d attribute" in i.message for i in issues))

    def test_qa_rejects_polygon_without_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                '<g id="content-main"><polygon fill="#111111"/></g>'
                "</svg>",
            )
            ok, issues = check_project_svg(project)
            self.assertFalse(ok)
            self.assertTrue(any("points attribute" in i.message for i in issues))


class ExportGeometryTest(unittest.TestCase):
    def test_export_path_produces_valid_pptx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                '<g id="content-main"><path d="M 100 200 C 200 100 400 100 500 200 S 700 350 800 200" '
                'fill="none" stroke="#2563EB" stroke-width="3"/></g>'
                "</svg>",
            )
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)

    def test_export_polygon_produces_valid_pptx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                '<g id="content-main"><polygon points="640,100 790,300 540,300" fill="#2563EB"/></g>'
                "</svg>",
            )
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)

    def test_export_polyline_produces_valid_pptx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                '<g id="content-main"><polyline points="100,400 300,200 500,400 700,200" '
                'fill="none" stroke="#2563EB" stroke-width="2"/></g>'
                "</svg>",
            )
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)

    def test_export_arc_produces_valid_pptx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                '<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                '<g id="content-main"><path d="M 100 400 A 200 100 0 1 1 600 400" '
                'fill="none" stroke="#2563EB" stroke-width="2"/></g>'
                "</svg>",
            )
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)

    def test_export_all_commands_combined(self) -> None:
        d = "M 100 200 L 300 200 C 350 100 450 100 500 200 S 600 300 700 200 Q 800 100 900 200 T 1100 200 A 50 50 0 0 1 1200 300 Z"
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                f'<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                f'<g id="content-main"><path d="{d}" fill="none" stroke="#111111" stroke-width="2"/></g>'
                f"</svg>",
            )
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)

    def test_export_relative_commands(self) -> None:
        d = "m 100 200 l 200 0 c 50 -100 150 -100 200 0 s 100 100 200 0 q 100 -100 200 0 t 200 0 a 50 50 0 0 1 100 100 z"
        with tempfile.TemporaryDirectory() as tmp:
            project = _make_svg_project(
                Path(tmp),
                f'<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">'
                f'<g id="content-main"><path d="{d}" fill="none" stroke="#111111" stroke-width="2"/></g>'
                f"</svg>",
            )
            deck = export_project(project, stage="output")
            valid, errors = validate_pptx(deck)
            self.assertTrue(valid, errors)

    def test_registry_extensibility(self) -> None:
        from slide_skill.converters import ConverterRegistry, create_default_registry

        reg = create_default_registry()
        self.assertIn("path", reg.supported_tags())
        self.assertIn("polygon", reg.supported_tags())
        self.assertIn("polyline", reg.supported_tags())
        called = []

        def custom_converter(slide, elem, sx, sy, meta, rgb):
            called.append(True)

        reg.register("custom", custom_converter)
        self.assertIn("custom", reg.supported_tags())


if __name__ == "__main__":
    unittest.main()
