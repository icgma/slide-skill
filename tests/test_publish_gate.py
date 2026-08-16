"""Render-convergence publish gate tests (GATE-01..04).

Render smoke + geometry measurement are mocked; COM smoke is faked via a
stub module. These pin the gate's blocking semantics and the no-partial-PPTX
export contract.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from slide_skill.exporter import export_project
from slide_skill.publish_gate import (
    DeckGateResult,
    PageGateResult,
    com_smoke_render,
    gate_deck,
    gate_page,
    write_gate_report,
)


GOOD_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
    '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
    '<g id="content-title-01">'
    '<text x="80" y="120" font-family="Arial" font-size="44" fill="#F8FAFC">标题</text>'
    "</g>"
    '<g id="content-body-01">'
    '<text x="80" y="220" font-family="Arial" font-size="24" fill="#F1F5F9">正文内容一行</text>'
    "</g></svg>"
)

OVERLAP_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
    '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
    '<g id="content-body-01">'
    '<text x="100" y="300" font-family="Arial" font-size="24" fill="#F1F5F9">排队统计</text>'
    '<text x="150" y="305" font-family="Arial" font-size="24" fill="#F1F5F9">校园卡</text>'
    "</g></svg>"
)


def _make_project(tmp_path: Path, svgs: dict[str, str], *, stage: str = "final") -> Path:
    from tests.test_design_guide import DesignGuideTest  # noqa: F401 — ensure import path
    project = tmp_path / "proj"
    (project / ("svg_final" if stage == "final" else "svg_output")).mkdir(parents=True)
    (project / "qa").mkdir()
    for name, svg in svgs.items():
        (project / ("svg_final" if stage == "final" else "svg_output") / name).write_text(
            svg, encoding="utf-8"
        )
    return project


def _patch_render(monkeypatch, defects_by_stem: dict[str, list[str]] | None = None,
                  default: list[str] | None = None):
    import slide_skill.measurement_contracts as mc

    def fake_smoke(svg_path, png_path, **kwargs):
        if defects_by_stem is not None and svg_path.stem in defects_by_stem:
            return defects_by_stem[svg_path.stem]
        return default or []

    # gate_page imports render_svg_smoke from the module at call time, so
    # patching the source module is effective.
    monkeypatch.setattr(mc, "render_svg_smoke", fake_smoke)


def _patch_measure(monkeypatch, result):
    import slide_skill.chrome_geometry as chrome_geometry

    monkeypatch.setattr(
        chrome_geometry, "measure_svg_text_geometry", lambda svg, **kw: result
    )


class TestGatePage:
    def test_clean_page_passes(self, tmp_path, monkeypatch):
        _patch_render(monkeypatch)
        _patch_measure(monkeypatch, None)
        svg = tmp_path / "slide_01.svg"
        svg.write_text(GOOD_SVG, encoding="utf-8")
        result = gate_page(svg, tmp_path)
        assert result.passed
        assert result.render_status == "rendered"
        assert result.blockers == []

    def test_black_render_blocks_despite_clean_qa(self, tmp_path, monkeypatch):
        _patch_render(monkeypatch, {"slide_01": ["Chrome render is a uniform image (blank/black-screen candidate)"]})
        _patch_measure(monkeypatch, None)
        svg = tmp_path / "slide_01.svg"
        svg.write_text(GOOD_SVG, encoding="utf-8")
        result = gate_page(svg, tmp_path)
        assert not result.passed
        assert any("uniform image" in b for b in result.blockers)

    def test_no_browser_records_gap_not_block(self, tmp_path, monkeypatch):
        _patch_render(monkeypatch, default=["no Chrome/Edge browser found for render smoke"])
        _patch_measure(monkeypatch, None)
        svg = tmp_path / "slide_01.svg"
        svg.write_text(GOOD_SVG, encoding="utf-8")
        result = gate_page(svg, tmp_path)
        assert result.passed  # static verdict retained
        assert result.render_status == "not-executed"

    def test_geometry_confirmed_overlap_blocks(self, tmp_path, monkeypatch):
        _patch_render(monkeypatch)
        # Static QA reports the overlap; measured boxes confirm it.
        _patch_measure(monkeypatch, [
            {"index": 0, "tag": "text", "text": "排队统计",
             "bbox": {"x": 100, "y": 276, "width": 96, "height": 24}, "textLength": 96},
            {"index": 1, "tag": "text", "text": "校园卡",
             "bbox": {"x": 150, "y": 281, "width": 72, "height": 24}, "textLength": 72},
        ])
        svg = tmp_path / "slide_01.svg"
        svg.write_text(OVERLAP_SVG, encoding="utf-8")
        result = gate_page(svg, tmp_path)
        assert not result.passed
        assert result.geometry_verdict == "confirmed"

    def test_geometry_cleared_phantom_overlap_passes(self, tmp_path, monkeypatch):
        _patch_render(monkeypatch)
        _patch_measure(monkeypatch, [
            {"index": 0, "tag": "text", "text": "排队统计",
             "bbox": {"x": 100, "y": 276, "width": 96, "height": 24}, "textLength": 96},
            {"index": 1, "tag": "text", "text": "校园卡",
             "bbox": {"x": 100, "y": 476, "width": 72, "height": 24}, "textLength": 72},
        ])
        svg = tmp_path / "slide_01.svg"
        svg.write_text(OVERLAP_SVG, encoding="utf-8")
        result = gate_page(svg, tmp_path)
        assert result.passed
        assert result.geometry_verdict == "cleared"


class TestGateDeck:
    def test_deck_with_one_bad_page_fails(self, tmp_path, monkeypatch):
        _patch_render(monkeypatch, {"slide_02": ["Chrome render is a uniform image (blank/black-screen candidate)"]})
        _patch_measure(monkeypatch, None)
        project = _make_project(tmp_path, {
            "slide_01.svg": GOOD_SVG,
            "slide_02.svg": GOOD_SVG,
        })
        deck = gate_deck(project, stage="final")
        assert not deck.passed
        assert len(deck.pages) == 2
        assert deck.pages[0].passed and not deck.pages[1].passed

    def test_report_persists_machine_readable_verdicts(self, tmp_path, monkeypatch):
        _patch_render(monkeypatch)
        _patch_measure(monkeypatch, None)
        project = _make_project(tmp_path, {"slide_01.svg": GOOD_SVG})
        deck = gate_deck(project, stage="final")
        deck.com_smoke = {"status": "not-executed", "detail": "pywin32 unavailable"}
        deck.capability_gaps.append("com-smoke: pywin32 unavailable")
        report = write_gate_report(project, deck)
        data = json.loads(report.read_text(encoding="utf-8"))
        assert data["passed"] is True
        assert data["com_smoke"]["status"] == "not-executed"
        assert data["capability_gaps"]


class TestExportGate:
    def _full_project(self, tmp_path: Path) -> Path:
        """A minimal project that can actually be exported."""
        from tests.test_design_guide import DesignGuideTest  # noqa: F401
        project = tmp_path / "e2e"
        (project / "svg_final").mkdir(parents=True)
        (project / "svg_output").mkdir()
        (project / "qa").mkdir()
        (project / "project.json").write_text(
            json.dumps({
                "name": "e2e",
                "title": "e2e",
                "format": "ppt169",
                "canvas": {
                    "width": 1280, "height": 720, "ratio": "16:9",
                    "pptx_width_in": 13.333, "pptx_height_in": 7.5,
                },
            }),
            encoding="utf-8",
        )
        (project / "svg_final" / "slide_01.svg").write_text(GOOD_SVG, encoding="utf-8")
        return project

    def test_clean_deck_exports_with_report(self, tmp_path, monkeypatch):
        _patch_render(monkeypatch)
        _patch_measure(monkeypatch, None)
        project = self._full_project(tmp_path)
        out = export_project(project, com_smoke=False)
        assert out.exists()
        report = json.loads((project / "qa" / "PUBLISH-GATE.json").read_text(encoding="utf-8"))
        assert report["passed"] is True

    def test_blocked_deck_refuses_export_no_partial_pptx(self, tmp_path, monkeypatch):
        _patch_render(monkeypatch, {"slide_01": ["Chrome render is a uniform image (blank/black-screen candidate)"]})
        _patch_measure(monkeypatch, None)
        project = self._full_project(tmp_path)
        out_path = tmp_path / "out" / "deck.pptx"
        with pytest.raises(RuntimeError, match="publish gate failed"):
            export_project(project, out_path, com_smoke=False)
        assert not out_path.exists()
        # Evidence is still persisted for the failed run.
        report = json.loads((project / "qa" / "PUBLISH-GATE.json").read_text(encoding="utf-8"))
        assert report["passed"] is False


class TestExecutorPublishGate:
    """GATE-01: a clean-QA page whose render fails must not publish."""

    def _run(self, tmp_path, monkeypatch, gate_results):
        import slide_skill.ai_executor as ai_executor
        from slide_skill.content_planner import ContentItem, SlidePlan

        project = tmp_path / "gate-project"
        for name in ("svg_output", "svg_final", "qa"):
            (project / name).mkdir(parents=True)
        (project / "spec_lock.json").write_text(json.dumps({
            "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
            "theme": "dark tech",
            "palette": {
                "background": "#0F172A", "surface": "#1E293B",
                "text": "#F8FAFC", "accent": "#3B82F6",
                "body": "#94A3B8", "muted": "#334155",
            },
            "font_family": "Inter, sans-serif",
        }), encoding="utf-8")

        calls: list = []

        def fake_gate(candidate_path):
            calls.append(candidate_path)
            return gate_results[min(len(calls) - 1, len(gate_results) - 1)]

        monkeypatch.setattr(ai_executor, "_browser_render_gate", fake_gate)

        class _StubResponses:
            def create(self, **kwargs):
                return types.SimpleNamespace(
                    choices=[types.SimpleNamespace(
                        message=types.SimpleNamespace(content=GOOD_SVG),
                        finish_reason="stop",
                    )],
                    usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=10),
                )

        class _StubClient:
            def __init__(self, **kwargs):
                self.chat = types.SimpleNamespace(completions=_StubResponses())

        monkeypatch.setattr("openai.OpenAI", lambda **kwargs: _StubClient())

        plan = SlidePlan(
            index=1, layout="bullet-list", title="标题",
            items=[ContentItem(type="text", primary="正文内容一行")],
        )
        return ai_executor.generate_svg_with_ai(
            project, [plan],
            model="stub", api_key="k", base_url="http://localhost:9/v1",
            run_qa=False, qa_retries=1,
        ), calls

    def test_black_render_blocks_publication(self, tmp_path, monkeypatch):
        with pytest.raises(RuntimeError, match="failed QA"):
            self._run(
                tmp_path, monkeypatch,
                gate_results=[(False, "render gate: black frame detected")],
            )
        assert not (tmp_path / "gate-project" / "svg_output" / "slide_01.svg").exists()

    def test_render_recovery_publishes(self, tmp_path, monkeypatch):
        paths, calls = self._run(
            tmp_path, monkeypatch,
            gate_results=[(False, "black"), (True, "ok")],
        )
        assert calls, "render gate must run at the publish decision point"
        assert (tmp_path / "gate-project" / "svg_output" / "slide_01.svg").exists()


class TestComSmoke:
    def test_missing_pywin32_is_a_recorded_gap(self, monkeypatch):
        import slide_skill.publish_gate as pg

        real_import = __import__

        def no_win32(name, *args, **kwargs):
            if name in {"pythoncom", "win32com", "win32com.client"}:
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", no_win32)
        status, detail = pg.com_smoke_render(Path("whatever.pptx"))
        assert status == "not-executed"
        assert "pywin32 unavailable" in detail

    def test_successful_com_export_passes(self, tmp_path, monkeypatch):
        fake_win32 = types.ModuleType("win32com")
        fake_client = types.ModuleType("win32com.client")

        class FakePresentation:
            def __init__(self, *a, **k):
                pass

            def Export(self, out_dir, fmt):
                for i in range(3):
                    Path(out_dir, f"幻灯片{i}.PNG").write_bytes(b"png")

            def Close(self):
                pass

        class FakeApp:
            Presentations = types.SimpleNamespace(Open=lambda *a, **k: FakePresentation())

        fake_client.Dispatch = lambda name: FakeApp()
        fake_win32.client = fake_client
        fake_pythoncom = types.ModuleType("pythoncom")
        fake_pythoncom.CoInitialize = lambda: None
        fake_pythoncom.CoUninitialize = lambda: None
        monkeypatch.setitem(sys.modules, "win32com", fake_win32)
        monkeypatch.setitem(sys.modules, "win32com.client", fake_client)
        monkeypatch.setitem(sys.modules, "pythoncom", fake_pythoncom)

        pptx = tmp_path / "deck.pptx"
        pptx.write_bytes(b"fake")
        status, detail = com_smoke_render(pptx)
        assert status == "passed"
        assert "3 slide image" in detail

    def test_com_error_is_gap_not_failure(self, tmp_path, monkeypatch):
        fake_win32 = types.ModuleType("win32com")
        fake_client = types.ModuleType("win32com.client")
        fake_client.Dispatch = lambda name: (_ for _ in ()).throw(RuntimeError("no PowerPoint"))
        fake_win32.client = fake_client
        fake_pythoncom = types.ModuleType("pythoncom")
        fake_pythoncom.CoInitialize = lambda: None
        fake_pythoncom.CoUninitialize = lambda: None
        monkeypatch.setitem(sys.modules, "win32com", fake_win32)
        monkeypatch.setitem(sys.modules, "win32com.client", fake_client)
        monkeypatch.setitem(sys.modules, "pythoncom", fake_pythoncom)
        pptx = tmp_path / "deck.pptx"
        pptx.write_bytes(b"fake")
        status, detail = com_smoke_render(pptx)
        assert status == "not-executed"
