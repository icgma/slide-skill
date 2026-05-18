"""Tests for v1.4 Phase 21 — Native Charts."""

from __future__ import annotations

import unittest
from xml.etree import ElementTree as ET

from slide_skill import charts
from slide_skill.themes import get_theme


SAMPLE = {
    "kind": "bar",
    "title": "Q3 Revenue",
    "categories": ["North", "South", "East", "West"],
    "series": [
        {"name": "2024", "values": [120, 90, 150, 80]},
        {"name": "2025", "values": [140, 110, 170, 100]},
    ],
}


class ChartSpecTests(unittest.TestCase):
    def test_from_dict_normalizes(self) -> None:
        spec = charts.ChartSpec.from_dict(SAMPLE)
        self.assertEqual(spec.kind, "bar")
        self.assertEqual(spec.title, "Q3 Revenue")
        self.assertEqual(spec.categories, ["North", "South", "East", "West"])
        self.assertEqual(len(spec.series), 2)
        self.assertEqual(spec.series[0]["values"], [120, 90, 150, 80])

    def test_unsupported_kind_raises(self) -> None:
        with self.assertRaises(ValueError):
            charts.ChartSpec.from_dict({"kind": "treemap-3d"})

    def test_kind_lowercased(self) -> None:
        spec = charts.ChartSpec.from_dict({"kind": "PIE", "categories": ["a"], "series": [{"name": "s", "values": [1]}]})
        self.assertEqual(spec.kind, "pie")


class ChartSvgTests(unittest.TestCase):
    def test_renders_svg_fragment(self) -> None:
        spec = charts.ChartSpec.from_dict(SAMPLE)
        out = charts.chart_to_svg(spec, theme=get_theme("dark-tech"), width=600, height=400, x=100, y=50)
        wrapped = f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">{out}</svg>'
        root = ET.fromstring(wrapped)
        # Must contain at least one <g> with translate.
        ns = "{http://www.w3.org/2000/svg}"
        gs = root.findall(f".//{ns}g")
        self.assertGreaterEqual(len(gs), 1)
        self.assertIn('translate(100,50)', out)

    def test_pie_renders(self) -> None:
        spec = charts.ChartSpec.from_dict({
            "kind": "pie",
            "categories": ["A", "B", "C"],
            "series": [{"name": "S1", "values": [30, 50, 20]}],
        })
        out = charts.chart_to_svg(spec, theme=get_theme("light-corporate"))
        self.assertIn("<g", out)


class LightenTests(unittest.TestCase):
    def test_lighten_changes_color(self) -> None:
        result = charts._lighten("#000000", 0.5)
        self.assertEqual(result, "#7F7F7F")

    def test_lighten_invalid_input_passthrough(self) -> None:
        self.assertEqual(charts._lighten("not-hex", 0.5), "not-hex")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
