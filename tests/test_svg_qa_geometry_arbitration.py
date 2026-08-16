"""svg_qa.arbitrate_text_geometry — DOM geometry as final arbiter (BENCH-03).

All measurement invocations are mocked; these tests pin the qualification
and re-verdict semantics without needing a real browser.
"""
from __future__ import annotations

import pytest

from slide_skill.svg_qa import (
    SvgIssue,
    arbitrate_text_geometry,
    check_svg_file,
)


def _svg(*texts: str) -> str:
    body = "".join(
        f'<text x="100" y="{140 + i * 120}" font-family="Arial" '
        f'font-size="24" fill="#F1F5F9">{t}</text>'
        for i, t in enumerate(texts)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" '
        'viewBox="0 0 1280 720">'
        '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
        f'<g id="content-body-01">{body}</g></svg>'
    )


def _measured(entries):
    return [
        {
            "index": i,
            "tag": "text",
            "text": text,
            "bbox": {"x": x, "y": y, "width": w, "height": h},
            "textLength": w,
        }
        for i, (text, x, y, w, h) in enumerate(entries)
    ]


def _patch_measure(monkeypatch, result, calls=None):
    import slide_skill.chrome_geometry as chrome_geometry

    def fake_measure(svg_text, **kwargs):
        if calls is not None:
            calls.append(svg_text)
        return result

    monkeypatch.setattr(chrome_geometry, "measure_svg_text_geometry", fake_measure)


_OVERLAP = SvgIssue(
    "warning", "slide_01.svg",
    'Text overlap: "排队统计" (260-284y) overlaps "校园卡" (270-294y)',
)
_OVERFLOW_RIGHT = SvgIssue(
    "warning", "slide_01.svg",
    'Text may overflow right edge: x_right≈1305px > canvas 1280px (text: "很长的标题文本...")',
)
_FIT_BOX = SvgIssue(
    "warning", "slide_01.svg",
    'Text may overflow fit box right edge: x_right≈1305px > box 1200px',
)


class TestQualification:
    def test_no_issues_never_invokes_browser(self, monkeypatch):
        calls: list = []
        _patch_measure(monkeypatch, [], calls)
        issues, info = arbitrate_text_geometry(_svg("标题"), [])
        assert issues == []
        assert info is None
        assert calls == []

    def test_non_geometry_issues_do_not_qualify(self, monkeypatch):
        calls: list = []
        _patch_measure(monkeypatch, [], calls)
        other = SvgIssue("error", "slide_01.svg", "Banned tag: <script>")
        issues, info = arbitrate_text_geometry(_svg("标题"), [other])
        assert issues == [other]
        assert info is None
        assert calls == []

    def test_fit_box_issues_stay_static_only(self, monkeypatch):
        # The fit box is a layout intent the browser cannot see.
        calls: list = []
        _patch_measure(monkeypatch, _measured([]), calls)
        issues, info = arbitrate_text_geometry(_svg("标题"), [_FIT_BOX])
        assert issues == [_FIT_BOX]
        assert info is None
        assert calls == []


class TestReverdict:
    def test_measured_clean_clears_small_text_overlap(self, monkeypatch):
        _patch_measure(monkeypatch, _measured([
            ("排队统计", 100, 260, 96, 24),
            ("校园卡", 100, 480, 72, 24),
        ]))
        issues, info = arbitrate_text_geometry(_svg("排队统计", "校园卡"), [_OVERLAP])
        assert issues == []
        assert info["geometry_verdict"] == "cleared"
        assert info["geometry_cleared"] == 1
        assert info["geometry_confirmed"] == 0

    def test_measured_colliding_keeps_overlap(self, monkeypatch):
        _patch_measure(monkeypatch, _measured([
            ("排队统计", 100, 260, 96, 24),
            ("校园卡", 150, 265, 72, 24),   # inside the first box
        ]))
        issues, info = arbitrate_text_geometry(_svg("排队统计", "校园卡"), [_OVERLAP])
        assert issues == [_OVERLAP]
        assert info["geometry_verdict"] == "confirmed"

    def test_anchor_width_overflow_arbitrated_by_measured_edges(self, monkeypatch):
        # text-anchor="end" at x=1200 estimated past the canvas; the real
        # measured right edge decides, not the estimated width.
        _patch_measure(monkeypatch, _measured([
            ("很长的标题文本", 900, 140, 300, 30),
        ]))
        issues, info = arbitrate_text_geometry(_svg("很长的标题文本"), [_OVERFLOW_RIGHT])
        assert issues == []
        assert info["geometry_verdict"] == "cleared"
        # Same text measured genuinely past the canvas edge -> confirmed.
        _patch_measure(monkeypatch, _measured([
            ("很长的标题文本", 1000, 140, 320, 30),   # right = 1320 > 1280 + margin
        ]))
        issues, info = arbitrate_text_geometry(_svg("很长的标题文本"), [_OVERFLOW_RIGHT])
        assert issues == [_OVERFLOW_RIGHT]
        assert info["geometry_verdict"] == "confirmed"

    def test_unavailable_measurement_keeps_static_verdict(self, monkeypatch):
        _patch_measure(monkeypatch, None)
        issues, info = arbitrate_text_geometry(_svg("排队统计", "校园卡"), [_OVERLAP])
        assert issues == [_OVERLAP]
        assert info == {"geometry_verdict": "unavailable", "geometry_checked": 1}

    def test_unmatched_snippets_keep_static_verdict(self, monkeypatch):
        _patch_measure(monkeypatch, _measured([
            ("别的文本", 100, 260, 96, 24),
        ]))
        issues, info = arbitrate_text_geometry(_svg("排队统计", "校园卡"), [_OVERLAP])
        assert issues == [_OVERLAP]
        # No clear, no confirm -> verdict "unavailable" with all checked.
        assert info["geometry_verdict"] == "unavailable"
        assert info["geometry_checked"] == 1

    def test_mixed_clean_and_confirmed_accounting(self, monkeypatch):
        _patch_measure(monkeypatch, _measured([
            ("排队统计", 100, 260, 96, 24),
            ("校园卡", 100, 480, 72, 24),
            ("很长的标题文本", 1000, 600, 320, 30),
        ]))
        issues, info = arbitrate_text_geometry(
            _svg("排队统计", "校园卡", "很长的标题文本"), [_OVERLAP, _OVERFLOW_RIGHT],
        )
        assert issues == [_OVERFLOW_RIGHT]
        assert info["geometry_verdict"] == "confirmed"
        assert info["geometry_checked"] == 2
        assert info["geometry_cleared"] == 1
        assert info["geometry_confirmed"] == 1


class TestStaticPathUnchanged:
    def test_check_svg_file_signature_accepts_plain_call(self, tmp_path):
        # The default static path stays dependency-free: no browser import
        # or invocation happens for callers that do not opt into geometry.
        svg = tmp_path / "slide_01.svg"
        svg.write_text(_svg("标题", "正文内容"), encoding="utf-8")
        issues = check_svg_file(svg, tmp_path)
        assert isinstance(issues, list)
