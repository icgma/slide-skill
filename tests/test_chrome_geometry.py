"""Tests for chrome_geometry — browser DOM geometry measurement (QA-02/QA-03).

Offline by default: harness construction and DOM parsing are pure, and the
measurement path is exercised with a mocked subprocess. One integration test
runs against a real local Chrome/Edge when present (this Windows box has
one) and skips cleanly elsewhere.
"""
import html
import json
import subprocess
from types import SimpleNamespace

import pytest

from slide_skill.chrome_geometry import (
    build_measurement_harness,
    find_chrome,
    measure_svg_text_geometry,
    parse_measurement_dom,
)


def _two_text_svg() -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
        '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
        '<g id="content-body-01">'
        '<text x="100" y="300" font-family="Arial, sans-serif" font-size="120" fill="#F8FAFC">97%</text>'
        '<text x="100" y="420" font-family="Arial, sans-serif" font-size="24" fill="#94A3B8">uptime last quarter</text>'
        "</g></svg>"
    )


class TestHarnessConstruction:

    def test_harness_waits_for_fonts_and_serializes_into_title(self):
        harness = build_measurement_harness(_two_text_svg())
        assert "document.fonts.ready" in harness
        assert "document.title = JSON.stringify(results)" in harness
        assert "getBBox" in harness
        assert "getComputedTextLength" in harness

    def test_harness_embeds_svg_as_json_string_not_raw_concatenation(self):
        # A hostile-but-legal text payload: quotes plus a literal </script>.
        svg = _two_text_svg().replace(
            "uptime last quarter", 'say "hi" then </script> survives'
        )
        harness = build_measurement_harness(svg)
        # The SVG markup must not appear raw in the page (innerHTML assignment
        # from a JS string, not concatenated markup).
        assert "<text x=" not in harness.split("<script>")[0]
        # Exactly one real closing script tag: the harness's own.
        assert harness.count("</script>") == 1
        # The embedded payload carries the JS-escaped form instead.
        assert "<\\/script>" in harness
        assert "<\\/text>" in harness

    def test_harness_embeds_svg_at_natural_canvas_size(self):
        harness = build_measurement_harness(_two_text_svg())
        assert "width:1280px" in harness
        assert "height:720px" in harness


class TestParseMeasurementDom:

    def _dom_with_payload(self, payload: str) -> str:
        return (
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(payload)}</title></head>"
            "<body><div id=\"stage\"><svg><text>97%</text></svg></div></body></html>"
        )

    def test_parses_bboxes_from_escaped_title(self):
        payload = json.dumps([
            {
                "index": 0,
                "tag": "text",
                "text": "97%",
                "bbox": {"x": 100.5, "y": 212.25, "width": 216.0, "height": 96.5},
                "textLength": 214.9,
            },
        ])
        parsed = parse_measurement_dom(self._dom_with_payload(payload))
        assert parsed is not None
        assert len(parsed) == 1
        entry = parsed[0]
        assert entry["tag"] == "text"
        assert entry["text"] == "97%"
        assert entry["bbox"] == {"x": 100.5, "y": 212.25, "width": 216.0, "height": 96.5}
        assert entry["textLength"] == pytest.approx(214.9)

    def test_svg_own_title_element_does_not_confuse_parsing(self):
        payload = json.dumps([{"index": 0, "tag": "text", "text": "a",
                               "bbox": {"x": 1, "y": 2, "width": 3, "height": 4},
                               "textLength": 3}])
        dom = (
            "<html><head><title>" + html.escape(payload) + "</title></head>"
            "<body><svg><title>decorative svg title</title><text>a</text></svg></body></html>"
        )
        parsed = parse_measurement_dom(dom)
        assert parsed is not None
        assert parsed[0]["bbox"]["width"] == 3.0

    def test_unparseable_or_missing_payload_returns_none(self):
        assert parse_measurement_dom("<html><head></head><body></body></html>") is None
        assert parse_measurement_dom("<html><title>not json</title></html>") is None
        assert parse_measurement_dom("") is None


class TestMeasureWithMockedChrome:

    def _fake_run(self, dom_text: str, calls: list | None = None):
        def run(cmd, **kwargs):
            if calls is not None:
                calls.append(cmd)
            return SimpleNamespace(returncode=0, stdout=dom_text, stderr="")
        return run

    def test_measurement_parses_mocked_dump_dom(self, monkeypatch):
        payload = json.dumps([
            {"index": 0, "tag": "text", "text": "97%",
             "bbox": {"x": 100, "y": 210, "width": 216, "height": 96}, "textLength": 214},
            {"index": 1, "tag": "text", "text": "uptime last quarter",
             "bbox": {"x": 100, "y": 402, "width": 220, "height": 24}, "textLength": 219},
        ])
        dom = f"<html><head><title>{html.escape(payload)}</title></head><body></body></html>"
        calls: list = []
        monkeypatch.setattr(subprocess, "run", self._fake_run(dom, calls))

        measured = measure_svg_text_geometry(_two_text_svg(), chrome_path="C:/fake/chrome.exe")

        assert measured is not None
        assert [entry["text"] for entry in measured] == ["97%", "uptime last quarter"]
        assert measured[0]["bbox"]["width"] == 216.0
        # The invocation mirrors the screenshot path's sandbox posture and
        # uses --dump-dom with a virtual time budget.
        cmd = calls[0]
        assert cmd[0] == "C:/fake/chrome.exe"
        assert "--headless=new" in cmd
        assert "--dump-dom" in cmd
        assert "--virtual-time-budget=5000" in cmd
        assert "--no-first-run" in cmd
        assert "--disable-gpu" in cmd
        assert "--no-sandbox" in cmd

    def test_missing_chrome_returns_none_without_exception(self, monkeypatch):
        import slide_skill.chrome_geometry as chrome_geometry
        monkeypatch.setattr(chrome_geometry, "find_chrome", lambda: None)
        assert measure_svg_text_geometry(_two_text_svg()) is None

    def test_failed_invocation_returns_none(self, monkeypatch):
        def raising_run(cmd, **kwargs):
            raise OSError("binary vanished")
        monkeypatch.setattr(subprocess, "run", raising_run)
        assert measure_svg_text_geometry(_two_text_svg(), chrome_path="C:/fake/chrome.exe") is None

    def test_timeout_returns_none(self, monkeypatch):
        def timing_out_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 20.0))
        monkeypatch.setattr(subprocess, "run", timing_out_run)
        assert measure_svg_text_geometry(
            _two_text_svg(), chrome_path="C:/fake/chrome.exe", timeout=0.1
        ) is None

    def test_garbage_dom_returns_none(self, monkeypatch):
        monkeypatch.setattr(subprocess, "run", self._fake_run("chrome crashed early"))
        assert measure_svg_text_geometry(_two_text_svg(), chrome_path="C:/fake/chrome.exe") is None


@pytest.mark.skipif(find_chrome() is None, reason="no local Chrome/Edge installed")
class TestRealChromeIntegration:

    def test_real_browser_measures_two_text_svg(self):
        measured = measure_svg_text_geometry(_two_text_svg())

        assert measured is not None
        texts = [entry for entry in measured if entry["tag"] == "text"]
        assert len(texts) == 2
        by_text = {entry["text"]: entry for entry in texts}
        assert "97%" in by_text
        assert "uptime last quarter" in by_text
        for entry in texts:
            assert entry["bbox"]["width"] > 0
            assert entry["bbox"]["height"] > 0
            assert entry["textLength"] > 0
        # Sanity: the 120px numeral is much taller and starts near x=100.
        numeral = by_text["97%"]
        caption = by_text["uptime last quarter"]
        assert numeral["bbox"]["height"] > caption["bbox"]["height"] * 2
        assert numeral["bbox"]["x"] == pytest.approx(100, abs=15)


# ═════════════════════════════════════════════════════════════════════
# QA-02: browser geometry arbitration of big-text static verdicts
# ═════════════════════════════════════════════════════════════════════

from slide_skill.ai_executor import (  # noqa: E402 - grouped with their tests
    _apply_validated_repair,
    _arbitrate_static_text_geometry,
    generate_svg_with_ai,
)
from slide_skill.svg_qa import SvgIssue  # noqa: E402


def _big_numeral_svg(caption_y: int = 420) -> str:
    """Metric-slide shape: 44px title, 120px display numeral, 24px caption."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
        '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
        '<g id="content-title-01">'
        '<text x="96" y="120" font-family="Inter, sans-serif" font-size="44" fill="#F8FAFC">Big Metric</text>'
        "</g>"
        '<g id="content-body-01">'
        '<text x="100" y="300" font-family="Inter, sans-serif" font-size="120" fill="#F8FAFC">97%</text>'
        f'<text x="110" y="{caption_y}" font-family="Inter, sans-serif" font-size="24" fill="#94A3B8">uptime</text>'
        "</g>"
        '<g id="chrome-footer">'
        '<text x="1180" y="700" font-family="Inter, sans-serif" font-size="12" fill="#94A3B8" text-anchor="end">01 / 01</text>'
        "</g></svg>"
    )


_OVERLAP_ISSUE = SvgIssue(
    "warning", "slide_01.svg",
    'Text overlap: "97%" (210-330y) overlaps "uptime" (292-316y)',
)


def _measured(entries):
    """Build a measurement list in the chrome_geometry payload shape."""
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


class TestGeometryArbitration:

    def _patch_measure(self, monkeypatch, result, calls=None):
        import slide_skill.chrome_geometry as chrome_geometry

        def fake_measure(svg_text, **kwargs):
            if calls is not None:
                calls.append(svg_text)
            return result
        monkeypatch.setattr(chrome_geometry, "measure_svg_text_geometry", fake_measure)

    def test_clean_measurement_clears_big_numeral_overlap(self, monkeypatch):
        # Browser says the numeral and caption do not intersect.
        self._patch_measure(monkeypatch, _measured([
            ("Big Metric", 96, 86, 240, 44),
            ("97%", 100, 212, 216, 96),
            ("uptime", 110, 396, 80, 24),
        ]))
        issues, info = _arbitrate_static_text_geometry(
            _big_numeral_svg(), [_OVERLAP_ISSUE],
        )
        assert issues == []
        assert info is not None
        assert info["geometry_verdict"] == "cleared"
        assert info["geometry_checked"] == 1
        assert info["geometry_cleared"] == 1

    def test_colliding_measurement_keeps_issue(self, monkeypatch):
        # Browser confirms the caption really sits inside the numeral's box.
        self._patch_measure(monkeypatch, _measured([
            ("Big Metric", 96, 86, 240, 44),
            ("97%", 100, 212, 216, 96),
            ("uptime", 110, 280, 80, 24),
        ]))
        issues, info = _arbitrate_static_text_geometry(
            _big_numeral_svg(caption_y=310), [_OVERLAP_ISSUE],
        )
        assert issues == [_OVERLAP_ISSUE]
        assert info is not None
        assert info["geometry_verdict"] == "confirmed"
        assert info["geometry_confirmed"] == 1
        assert info["geometry_cleared"] == 0

    def test_unavailable_measurement_keeps_static_verdict(self, monkeypatch):
        self._patch_measure(monkeypatch, None)
        issues, info = _arbitrate_static_text_geometry(
            _big_numeral_svg(), [_OVERLAP_ISSUE],
        )
        assert issues == [_OVERLAP_ISSUE]
        assert info is not None
        assert info["geometry_verdict"] == "unavailable"

    def test_small_text_issues_never_invoke_the_browser(self, monkeypatch):
        calls: list = []
        self._patch_measure(monkeypatch, [], calls)
        small_svg = _big_numeral_svg().replace('font-size="120"', 'font-size="24"').replace(
            'font-size="44"', 'font-size="20"'
        )
        small_issue = SvgIssue(
            "warning", "slide_01.svg",
            'Text overlap: "97%" (282-306y) overlaps "uptime" (292-316y)',
        )
        issues, info = _arbitrate_static_text_geometry(small_svg, [small_issue])
        assert issues == [small_issue]
        assert info is None
        assert calls == []

    def test_overflow_verdicts_follow_measured_canvas_edges(self, monkeypatch):
        overflow = SvgIssue(
            "error", "slide_01.svg",
            'Text may overflow right edge: x_right≈1320px > canvas 1280px (text: "97%...")',
        )
        # Measured well inside the canvas -> cleared.
        self._patch_measure(monkeypatch, _measured([("97%", 100, 212, 216, 96)]))
        issues, info = _arbitrate_static_text_geometry(_big_numeral_svg(), [overflow])
        assert issues == []
        assert info["geometry_verdict"] == "cleared"
        # Measured genuinely past the edge (x2 = 1100 + 220 > 1280 + margin) -> confirmed.
        self._patch_measure(monkeypatch, _measured([("97%", 1100, 212, 220, 96)]))
        issues, info = _arbitrate_static_text_geometry(_big_numeral_svg(), [overflow])
        assert issues and issues[0].message.startswith("Text may overflow right edge")
        assert info["geometry_verdict"] == "confirmed"

    def test_unmatched_snippets_keep_static_verdict(self, monkeypatch):
        # Measurement succeeded but no node matches the quoted text.
        self._patch_measure(monkeypatch, _measured([("something else", 0, 0, 10, 10)]))
        issues, info = _arbitrate_static_text_geometry(
            _big_numeral_svg(), [_OVERLAP_ISSUE],
        )
        assert issues == [_OVERLAP_ISSUE]
        assert info["geometry_verdict"] == "unavailable"


# ═════════════════════════════════════════════════════════════════════
# QA-03: mandatory post-repair re-render when a browser exists
# ═════════════════════════════════════════════════════════════════════

def _make_repair_project(tmp_path):
    project = tmp_path / "repair-project"
    for name in ("svg_output", "svg_final", "qa"):
        (project / name).mkdir(parents=True)
    (project / "spec_lock.json").write_text(json.dumps({
        "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
        "theme": "dark tech",
        "palette": {
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F8FAFC",
            "accent": "#3B82F6",
            "body": "#94A3B8",
            "muted": "#334155",
        },
        "font_family": "Inter, sans-serif",
    }), encoding="utf-8")
    return project


def _attempt_file(project, svg: str):
    attempt_dir = project / "qa" / "executor" / "attempt-svg"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    attempt = attempt_dir / "slide_01_attempt_01.svg"
    attempt.write_text(svg, encoding="utf-8")
    return attempt


def _trace_events(project):
    trace = project / "qa" / "ai-trace.jsonl"
    if not trace.exists():
        return []
    return [
        json.loads(line)
        for line in trace.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestMandatoryPostRepairRender:

    def test_black_render_rejects_candidate_even_with_clean_structural_qa(
        self, tmp_path, monkeypatch,
    ):
        from PIL import Image
        import slide_skill.chrome_geometry as chrome_geometry
        import slide_skill.render as render

        project = _make_repair_project(tmp_path)
        original = _big_numeral_svg()
        attempt = _attempt_file(project, original)
        original_bytes = attempt.read_bytes()
        patched = original.replace("#94A3B8", "#CBD5E1")  # text-preserving restyle

        monkeypatch.setattr(
            "slide_skill.ai_executor._validate_svg_attempt", lambda *a, **k: [],
        )
        monkeypatch.setattr(chrome_geometry, "find_chrome", lambda: "C:/fake/chrome.exe")

        def fake_screenshot(cmd, *, timeout, label):
            target = next(
                arg.split("=", 1)[1] for arg in cmd if arg.startswith("--screenshot=")
            )
            Image.new("RGB", (1280, 720), (0, 0, 0)).save(target)
        monkeypatch.setattr(render, "_run_with_timeout", fake_screenshot)

        accepted, issues = _apply_validated_repair(
            project, attempt, original, patched,
            plan=None,
            visual_feedback="",
            run_qa=False,
            strict_quality=True,
            repair_kind="auto-contrast",
            model="test-model",
            attempt=1,
            slide_index=1,
        )

        assert not accepted
        assert issues == []
        assert attempt.read_bytes() == original_bytes
        assert not attempt.with_name(attempt.name + ".patch-candidate").exists()
        rejected = [e for e in _trace_events(project) if e.get("status") == "repair-rejected"]
        assert rejected
        assert "black frame" in rejected[-1]["metadata"]["reason"]

    def test_no_browser_acceptance_records_capability_gap(self, tmp_path, monkeypatch):
        import slide_skill.chrome_geometry as chrome_geometry

        project = _make_repair_project(tmp_path)
        original = _big_numeral_svg()
        attempt = _attempt_file(project, original)
        patched = original.replace("#94A3B8", "#CBD5E1")

        monkeypatch.setattr(
            "slide_skill.ai_executor._validate_svg_attempt", lambda *a, **k: [],
        )
        monkeypatch.setattr(chrome_geometry, "find_chrome", lambda: None)

        accepted, _ = _apply_validated_repair(
            project, attempt, original, patched,
            plan=None,
            visual_feedback="",
            run_qa=False,
            strict_quality=True,
            repair_kind="auto-contrast",
            model="test-model",
            attempt=1,
            slide_index=1,
        )

        assert accepted
        assert attempt.read_text(encoding="utf-8") == patched
        events = [e for e in _trace_events(project) if e.get("status") == "repair-accepted"]
        assert events
        metadata = events[-1]["metadata"]
        assert metadata["capability_gap"] == "no-browser-render-check"
        assert metadata["note"] == "capability-gap: no-browser-render-check"
        assert metadata["repair"] == "auto-contrast"

    def test_healthy_render_accepts_candidate(self, tmp_path, monkeypatch):
        from PIL import Image
        import slide_skill.chrome_geometry as chrome_geometry
        import slide_skill.render as render

        project = _make_repair_project(tmp_path)
        original = _big_numeral_svg()
        attempt = _attempt_file(project, original)
        patched = original.replace("#94A3B8", "#CBD5E1")

        monkeypatch.setattr(
            "slide_skill.ai_executor._validate_svg_attempt", lambda *a, **k: [],
        )
        monkeypatch.setattr(chrome_geometry, "find_chrome", lambda: "C:/fake/chrome.exe")

        def fake_screenshot(cmd, *, timeout, label):
            target = next(
                arg.split("=", 1)[1] for arg in cmd if arg.startswith("--screenshot=")
            )
            image = Image.new("RGB", (1280, 720), (15, 23, 42))
            image.paste((248, 250, 252), (100, 200, 400, 330))
            image.save(target)
        monkeypatch.setattr(render, "_run_with_timeout", fake_screenshot)

        accepted, _ = _apply_validated_repair(
            project, attempt, original, patched,
            plan=None,
            visual_feedback="",
            run_qa=False,
            strict_quality=True,
            repair_kind="auto-contrast",
            model="test-model",
            attempt=1,
            slide_index=1,
        )

        assert accepted
        assert attempt.read_text(encoding="utf-8") == patched
        # A render that ran and passed leaves no capability-gap event behind.
        assert not [e for e in _trace_events(project) if e.get("status") == "repair-accepted"]


class TestReleaseCheckSurfacesCapabilityGap:

    def test_trace_capability_gaps_are_read_and_listed(self, tmp_path):
        from slide_skill.ai_trace import write_ai_trace
        from slide_skill.cli import _ai_release_check_summary, _ai_trace_capability_gaps

        project = _make_repair_project(tmp_path)
        write_ai_trace(
            project,
            stage="executor",
            model="test-model",
            status="repair-accepted",
            attempt=1,
            metadata={
                "slide": 1,
                "repair": "auto-wrap",
                "capability_gap": "no-browser-render-check",
                "note": "capability-gap: no-browser-render-check",
            },
        )

        gaps = _ai_trace_capability_gaps(project)
        assert gaps == ["no-browser-render-check"]

        doctor = [
            SimpleNamespace(role="planner", status="passed", model="m"),
            SimpleNamespace(role="executor", status="passed", model="m"),
            SimpleNamespace(role="vision", status="passed", model="m"),
        ]
        smoke = {
            "status": "passed",
            "deck": "deck.pptx",
            "qa_report": "QA.md",
            "visual_critic": True,
            "metrics": {"failed_events": 0, "executor_brief_missing_events": 0},
        }
        gates = {
            "provider_preflight": True,
            "planner_executor_visual_smoke": True,
            "visual_iteration_review": False,
            "visual_repair_applied": False,
            "visual_severity_ok": True,
            "rendered_source_pptx": True,
            "trace_has_no_failed_events": True,
            "trace_converged_after_retries": False,
            "executor_had_planner_brief": True,
            "release_ready": True,
        }
        summary = _ai_release_check_summary(
            doctor, smoke, None,
            gates=gates, status="passed", error="",
            capability_gaps=gaps,
        )
        assert summary["capability_gaps"] == ["no-browser-render-check"]
        assert any("capability-gap: no-browser-render-check" in warning
                   for warning in summary["warnings"])

    def test_no_gap_events_produce_no_gap_warnings(self, tmp_path):
        from slide_skill.cli import _ai_trace_capability_gaps

        project = _make_repair_project(tmp_path)
        assert _ai_trace_capability_gaps(project) == []


# ═════════════════════════════════════════════════════════════════════
# End-to-end wiring: the executor attempt loop consults the arbiter and
# records geometry_verdict in the attempt trace event.
# ═════════════════════════════════════════════════════════════════════

class _StubCompletions:
    def __init__(self, content: str):
        self._content = content

    def create(self, **kwargs):
        return SimpleNamespace(
            id="chatcmpl-stub",
            choices=[SimpleNamespace(
                index=0,
                message=SimpleNamespace(role="assistant", content=self._content),
                finish_reason="stop",
            )],
        )


class _StubOpenAI:
    content = ""

    def __init__(self, *args, **kwargs):
        self.chat = SimpleNamespace(completions=_StubCompletions(self.__class__.content))


class TestExecutorLoopWiring:

    def test_attempt_loop_clears_phantom_overlap_and_traces_verdict(
        self, tmp_path, monkeypatch,
    ):
        from slide_skill.content_planner import ContentItem, SlidePlan
        import slide_skill.chrome_geometry as chrome_geometry

        project = _make_repair_project(tmp_path)
        # caption_y=310 puts the 24px caption inside the 120px numeral's
        # static box: svg_qa reports a Text overlap warning, which blocks
        # under strict quality. The mocked browser measurement contradicts
        # the estimate, so the arbiter must clear it and publish the page.
        svg = _big_numeral_svg(caption_y=310)
        _StubOpenAI.content = svg
        monkeypatch.setattr("openai.OpenAI", _StubOpenAI)

        measure_calls: list = []

        def fake_measure(svg_text, **kwargs):
            measure_calls.append(svg_text)
            return _measured([
                ("Big Metric", 96, 86, 240, 44),
                ("97%", 100, 212, 216, 96),
                ("uptime", 110, 396, 80, 24),
            ])
        monkeypatch.setattr(chrome_geometry, "measure_svg_text_geometry", fake_measure)

        plan = SlidePlan(
            index=1,
            layout="metric",
            title="Big Metric",
            items=[ContentItem(type="metric", primary="97%", secondary="uptime")],
            rhythm="anchor",
            visual_strategy="hero-statement",
        )

        paths = generate_svg_with_ai(
            project, [plan],
            model="stub-model",
            api_key="test-key",
            base_url="http://localhost:9/v1",
            run_qa=False,
            qa_retries=0,
            strict_quality=True,
        )

        assert len(paths) == 1
        assert paths[0].exists()
        assert measure_calls, "the arbiter must have consulted the browser measurement"

        executor_events = [
            e for e in _trace_events(project)
            if e.get("stage") == "executor" and "geometry_verdict" in (e.get("metadata") or {})
        ]
        assert executor_events
        metadata = executor_events[-1]["metadata"]
        assert metadata["geometry_verdict"] == "cleared"
        assert metadata["geometry_cleared"] == 1
        assert executor_events[-1]["status"] == "passed"
        assert metadata["blocking_count"] == 0
