import base64
import io
import json
import threading
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

from slide_skill.ai_planner import plan_slides_with_ai
from slide_skill.content_planner import ContentConfig, ContentItem, SlidePlan
from slide_skill.ai_executor import generate_svg_with_ai
from slide_skill.visual_critic import generate_visual_feedback


class _FakeOpenAIHandler(BaseHTTPRequestHandler):
    responses = []
    requests = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        payload = json.loads(body.decode("utf-8"))
        self.__class__.requests.append({"path": self.path, "payload": payload})
        content = self.__class__.responses.pop(0)
        if callable(content):
            content(self, payload)
            return
        response = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1,
            "model": payload.get("model", "test-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        }
        encoded = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):  # noqa: A002
        return


class _FakeOpenAIServer:
    def __init__(self, responses):
        _FakeOpenAIHandler.responses = list(responses)
        _FakeOpenAIHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOpenAIHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}/v1", _FakeOpenAIHandler.requests

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def _project(tmp_path):
    project = tmp_path / "http-project"
    for name in ("svg_output", "svg_final", "qa"):
        (project / name).mkdir(parents=True)
    (project / "spec_lock.json").write_text(json.dumps({
        "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
        "theme": "dark-tech",
        "palette": {
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F1F5F9",
            "accent": "#3B82F6",
            "body": "#94A3B8",
            "muted": "#334155",
        },
        "font_family": "Aptos, Arial, sans-serif",
    }), encoding="utf-8")
    return project


def _valid_svg(title="HTTP Slide", body="Body"):
    return f'''<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>
  <g id="decor-01"><rect x="0" y="0" width="6" height="720" fill="#3B82F6"/></g>
  <g id="content-title-01"><text x="96" y="120" font-family="Aptos, Arial, sans-serif" font-size="44" fill="#F1F5F9">{title}</text></g>
  <g id="content-body-01"><text x="96" y="190" font-family="Aptos, Arial, sans-serif" font-size="24" fill="#94A3B8">{body}</text></g>
  <g id="content-proof-01"><text x="720" y="240" font-family="Aptos, Arial, sans-serif" font-size="24" fill="#94A3B8">{body}</text></g>
  <g id="chrome-footer"><text x="1180" y="700" font-family="Aptos, Arial, sans-serif" font-size="12" fill="#94A3B8" text-anchor="end">01 / 01</text></g>
</svg>'''


def test_repair_plan_preserves_ai_planner_contract_and_ignores_footer_text(tmp_path):
    from slide_skill.cli import _extract_svg_text_lines, _repair_plan_from_existing_slide

    project = _project(tmp_path)
    (project / "qa" / "ai-planner").mkdir(parents=True)
    (project / "qa" / "ai-planner" / "plan.json").write_text(json.dumps([
        {
            "index": 1,
            "layout": "two-column",
            "title": "HTTP Deck",
            "items": [
                {"type": "bullet", "primary": "Combined type list", "secondary": "", "tertiary": "", "meta": {}},
                {"type": "text", "primary": "Right-column statement", "secondary": "", "tertiary": "", "meta": {}},
            ],
            "notes": "Keep the two-column layout.",
            "density": "normal",
            "rhythm": "anchor",
            "visual_strategy": "two-column content grid",
            "layout_pattern": "title top-left + two-column cards",
        }
    ]), encoding="utf-8")
    svg = project / "svg_output" / "slide_01.svg"
    svg.write_text(_valid_svg(title="HTTP Deck", body="Body"), encoding="utf-8")

    assert "01 / 01" not in _extract_svg_text_lines(svg)
    plan = _repair_plan_from_existing_slide(project, 1)

    assert plan.layout == "two-column"
    assert plan.title == "HTTP Deck"
    assert [item.primary for item in plan.items] == ["Combined type list", "Right-column statement"]
    assert plan.rhythm == "anchor"
    assert plan.layout_pattern == "title top-left + two-column cards"
    assert "Repair this slide" in plan.notes


def test_release_gates_use_latest_visual_severity_not_historical_max():
    from slide_skill.cli import _ai_release_check_gates

    doctor = [
        SimpleNamespace(status="passed"),
        SimpleNamespace(status="passed"),
        SimpleNamespace(status="passed"),
    ]
    smoke = {
        "status": "passed",
        "deck": "deck.pptx",
        "qa_report": "QA.md",
        "visual_critic": True,
        "metrics": {
            "failed_events": 1,
            "max_visual_severity": "major",
            "executor_brief_missing_events": 0,
        },
        "stage_statuses": [
            {"stage": "visual-critic", "status": "failed", "metadata": {"severity": "major"}},
            {"stage": "visual-critic", "status": "passed", "metadata": {"severity": "ok"}},
        ],
    }

    gates = _ai_release_check_gates(doctor, smoke, None)

    assert gates["visual_severity_ok"] is True
    assert gates["rendered_source_pptx"] is False
    assert gates["trace_has_no_failed_events"] is False
    assert gates["trace_converged_after_retries"] is True
    assert gates["release_ready"] is True


def test_release_gates_distinguish_visual_review_from_applied_repair():
    from slide_skill.cli import _ai_release_check_gates

    doctor = [
        SimpleNamespace(status="passed"),
        SimpleNamespace(status="passed"),
        SimpleNamespace(status="passed"),
    ]
    smoke = {
        "status": "failed",
        "deck": "deck.pptx",
        "qa_report": "QA.md",
        "visual_critic": True,
        "rendered_source": "svg-preview",
        "metrics": {"failed_events": 0, "executor_brief_missing_events": 0},
    }
    reviewed_only = {
        "status": "passed",
        "latest_visual_severity": "ok",
        "latest_rendered_source": "svg-preview",
        "total_metrics": {"failed_events": 0},
        "repair_cycles": [{"round": 1, "repaired": []}],
    }
    repaired = {
        "status": "passed",
        "latest_visual_severity": "ok",
        "latest_rendered_source": "pptx-render",
        "total_metrics": {"failed_events": 0},
        "repair_cycles": [{"round": 1, "repaired": [{"generated": "slide_01.svg"}]}],
    }

    review_gates = _ai_release_check_gates(doctor, smoke, reviewed_only)
    repair_gates = _ai_release_check_gates(doctor, smoke, repaired)

    assert review_gates["visual_iteration_review"] is True
    assert review_gates["visual_repair_applied"] is False
    assert review_gates["rendered_source_pptx"] is False
    assert review_gates["release_ready"] is True
    assert repair_gates["visual_iteration_review"] is True
    assert repair_gates["visual_repair_applied"] is True
    assert repair_gates["rendered_source_pptx"] is True


def test_release_gates_can_require_pptx_rendered_visual_evidence():
    from slide_skill.cli import _ai_release_check_gates

    doctor = [
        SimpleNamespace(status="passed"),
        SimpleNamespace(status="passed"),
        SimpleNamespace(status="passed"),
    ]
    smoke = {
        "status": "passed",
        "deck": "deck.pptx",
        "qa_report": "QA.md",
        "visual_critic": True,
        "require_pptx_render": True,
        "rendered_source": "svg-preview",
        "metrics": {
            "failed_events": 0,
            "executor_brief_missing_events": 0,
            "max_visual_severity": "ok",
        },
    }

    fallback_gates = _ai_release_check_gates(doctor, smoke, None)
    smoke["rendered_source"] = "pptx-render"
    pptx_gates = _ai_release_check_gates(doctor, smoke, None)

    assert fallback_gates["visual_severity_ok"] is True
    assert fallback_gates["rendered_source_pptx"] is False
    assert fallback_gates["release_ready"] is False
    assert pptx_gates["rendered_source_pptx"] is True
    assert pptx_gates["release_ready"] is True


def test_ai_planner_uses_openai_compatible_http_server(tmp_path):
    project = _project(tmp_path)
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Planned",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
                "items": [{"type": "text", "primary": "From server"}],
            }
        ]
    })

    with _FakeOpenAIServer([plan_json]) as (base_url, requests):
        plans = plan_slides_with_ai(
            "# Source",
            ContentConfig(),
            project_path=project,
            base_url=base_url,
            api_key="test-key",
            model="planner-http",
        )

    assert plans[0].title == "HTTP Planned"
    trace = _read_trace(project)
    assert trace[-1]["stage"] == "planner"
    assert trace[-1]["model"] == "planner-http"
    assert requests[0]["path"] == "/v1/chat/completions"
    assert requests[0]["payload"]["model"] == "planner-http"
    assert requests[0]["payload"]["messages"][1]["content"].startswith("Create a production slide plan")


def test_ai_executor_uses_openai_compatible_http_server(tmp_path):
    project = _project(tmp_path)
    plan = SlidePlan(
        index=1,
        layout="cover",
        title="HTTP Slide",
        items=[ContentItem(type="text", primary="Body")],
        rhythm="anchor",
    )

    with _FakeOpenAIServer([_valid_svg()]) as (base_url, requests):
        paths = generate_svg_with_ai(
            project,
            [plan],
            base_url=base_url,
            api_key="test-key",
            model="executor-http",
        )

    assert paths[0].exists()
    assert "HTTP Slide" in paths[0].read_text(encoding="utf-8")
    trace = _read_trace(project)
    assert trace[-1]["stage"] == "executor"
    assert trace[-1]["model"] == "executor-http"
    assert requests[0]["path"] == "/v1/chat/completions"
    assert requests[0]["payload"]["model"] == "executor-http"
    assert "Create SVG page 1 of 1" in requests[0]["payload"]["messages"][1]["content"]


def test_visual_critic_uses_openai_compatible_http_server(tmp_path):
    project = _project(tmp_path)
    rendered = project / "qa" / "rendered"
    rendered.mkdir(parents=True, exist_ok=True)
    (rendered / "slide-1.jpg").write_bytes(b"fake-jpeg")
    response = json.dumps({
        "severity": "major",
        "summary": "Title is clipped",
        "issues": ["Title touches top edge"],
        "actions": ["Move title down"],
        "repair_prompt": "Move the title down and preserve the footer.",
    })

    with _FakeOpenAIServer([response]) as (base_url, requests):
        json_path, md_path = generate_visual_feedback(
            project,
            base_url=base_url,
            api_key="test-key",
            model="vision-http",
        )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["slides"][0]["severity"] == "major"
    assert "Move title down" in md_path.read_text(encoding="utf-8")
    trace = _read_trace(project)
    assert trace[-1]["stage"] == "visual-critic"
    assert trace[-1]["model"] == "vision-http"
    request_sidecar = json.loads((project / "qa" / trace[-1]["request_path"]).read_text(encoding="utf-8"))
    image_url = request_sidecar["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("<image data URL omitted; source=")
    assert "base64" not in image_url
    assert requests[0]["payload"]["model"] == "vision-http"
    content = requests[0]["payload"]["messages"][1]["content"]
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_ai_doctor_embedded_png_is_valid():
    from slide_skill.ai_doctor import _ONE_PIXEL_PNG

    with Image.open(io.BytesIO(base64.b64decode(_ONE_PIXEL_PNG))) as image:
        image.verify()


def test_cli_build_ai_mode_runs_against_openai_compatible_http_server(tmp_path, monkeypatch):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "projects"
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })

    with _FakeOpenAIServer([plan_json, _valid_svg(title="HTTP Deck", body="Point from source")]) as (base_url, requests):
        result = main([
            "build",
            str(source),
            "--name",
            "cli-http",
            "--base",
            str(base),
            "--mode",
            "ai",
            "--planner",
            "ai",
            "--skip-confirm",
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
        ])

    project = base / "cli-http"
    assert result == 0
    assert (project / "qa" / "ai-planner" / "plan.json").exists()
    assert (project / "qa" / "executor" / "slide_01_attempt_01.json").exists()
    trace = _read_trace(project)
    assert [event["stage"] for event in trace] == ["planner", "executor"]
    assert list((project / "exports").glob("*.pptx"))
    assert [request["payload"]["model"] for request in requests] == ["planner-http", "executor-http"]
    assert "Create a production slide plan" in requests[0]["payload"]["messages"][1]["content"]
    assert "Create SVG page 1 of 1" in requests[1]["payload"]["messages"][1]["content"]


def test_cli_ai_smoke_runs_against_openai_compatible_http_server(tmp_path, monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "live"
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })

    with _FakeOpenAIServer([plan_json, _valid_svg(title="HTTP Deck", body="Point from source")]) as (base_url, requests):
        result = main([
            "ai-smoke",
            "--source",
            str(source),
            "--name",
            "cli-ai-smoke",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
        ])

    project = base / "cli-ai-smoke"
    output = capsys.readouterr().out
    trace = _read_trace(project)
    assert result == 0
    assert (project / "qa" / "ai-planner" / "plan.json").exists()
    assert (project / "qa" / "ai-planner" / "executor-brief.md").exists()
    assert (project / "qa" / "executor" / "slide_01_attempt_01.json").exists()
    assert list((project / "exports").glob("*.pptx"))
    smoke = json.loads((project / "qa" / "AI-SMOKE.json").read_text(encoding="utf-8"))
    assert smoke["status"] == "passed"
    assert smoke["visual_critic"] is False
    assert smoke["stages"] == ["planner", "executor"]
    assert smoke["trace_events"] == 2
    assert smoke["metrics"]["failed_events"] == 0
    assert smoke["metrics"]["blocking_count"] == 0
    assert smoke["metrics"]["max_visual_severity"] == ""
    assert smoke["metrics"]["executor_brief_missing_events"] == 0
    assert smoke["metrics"]["prompt_chars"] > 0
    assert smoke["metrics"]["raw_chars"] > 0
    assert smoke["metrics"]["request_chars"] > smoke["metrics"]["prompt_chars"]
    assert smoke["diagnosis"]["focus"] == "all-passed"
    assert smoke["diagnosis"]["trace"] == f"slide-skill ai-trace {project}"
    assert smoke["diagnosis"]["diagnose"] == f"slide-skill ai-trace {project} --diagnose"
    assert [event["stage"] for event in trace] == ["planner", "executor"]
    assert [request["payload"]["model"] for request in requests] == ["planner-http", "executor-http"]
    assert "trace:" in output
    assert "has_executor_brief=True" in output
    assert "prompt=ai-trace-artifacts/" in output


def test_cli_ai_smoke_passes_when_executor_retry_eventually_succeeds(tmp_path, monkeypatch):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "live"
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })
    invalid_svg = _valid_svg(title="HTTP Deck", body="Wrong body")

    with _FakeOpenAIServer([
        plan_json,
        invalid_svg,
        _valid_svg(title="HTTP Deck", body="Point from source"),
    ]) as (base_url, _requests):
        result = main([
            "ai-smoke",
            "--source",
            str(source),
            "--name",
            "cli-ai-smoke-retry",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
        ])

    project = base / "cli-ai-smoke-retry"
    smoke = json.loads((project / "qa" / "AI-SMOKE.json").read_text(encoding="utf-8"))
    assert result == 0
    assert smoke["status"] == "passed"
    assert smoke["metrics"]["failed_events"] == 1
    assert smoke["metrics"]["passed_events"] == 2
    # The wrong-body attempt now trips both fidelity directions (49-02):
    # missing planned content AND unsupported-visible-text "Wrong body".
    assert smoke["metrics"]["blocking_count"] == 2
    assert smoke["metrics"]["failure_hint_counts"] == {"content-fidelity": 1}
    assert smoke["metrics"]["recovered_failure_count"] == 1
    assert smoke["metrics"]["feedback_recovered_failure_count"] == 1
    assert smoke["diagnosis"]["focus"] == "recovered-failure"
    assert smoke["diagnosis"]["event"] == 2
    assert smoke["diagnosis"]["stage"] == "executor"
    assert smoke["diagnosis"]["inspect_raw"] == f"slide-skill ai-trace {project} --event 2 --part raw"
    assert smoke["diagnosis"]["next_detail"][0].startswith("Fix content fidelity before visual polish")
    assert smoke["diagnosis"]["recovered_by_event"] == 3
    assert smoke["diagnosis"]["recovered_by_stage"] == "executor"
    assert smoke["diagnosis"]["recovered_by_attempt"] == 2
    assert smoke["diagnosis"]["recovered_feedback_used"] is True
    assert smoke["stage_statuses"][1]["status"] == "failed"
    assert smoke["stage_statuses"][2]["status"] == "passed"


def test_cli_ai_smoke_repeated_name_resets_previous_trace(tmp_path, monkeypatch):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "live"
    common_args = [
        "ai-smoke",
        "--source",
        str(source),
        "--name",
        "cli-ai-smoke-repeat",
        "--base",
        str(base),
        "--planner-retries",
        "0",
    ]

    with _FakeOpenAIServer(["not json"]) as (base_url, _requests):
        first = main([
            *common_args,
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
        ])
    assert first == 1

    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })
    with _FakeOpenAIServer([plan_json, _valid_svg(title="HTTP Deck", body="Point from source")]) as (base_url, _requests):
        second = main([
            *common_args,
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
        ])

    project = base / "cli-ai-smoke-repeat"
    smoke = json.loads((project / "qa" / "AI-SMOKE.json").read_text(encoding="utf-8"))
    trace = _read_trace(project)
    assert second == 0
    assert smoke["status"] == "passed"
    assert smoke["trace_events"] == 2
    assert smoke["stages"] == ["planner", "executor"]
    assert [event["stage"] for event in trace] == ["planner", "executor"]
    assert all(event["status"] == "passed" for event in trace)


def test_cli_ai_smoke_can_include_visual_critic_http_stage(tmp_path, monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "live"
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })
    critic_response = json.dumps({
        "severity": "ok",
        "summary": "Slide is readable and complete.",
        "issues": [],
        "actions": [],
        "repair_prompt": "",
    })
    rendered = tmp_path / "rendered"
    rendered.mkdir()
    (rendered / "slide-1.jpg").write_bytes(b"fake-jpeg")

    with _FakeOpenAIServer([
        plan_json,
        _valid_svg(title="HTTP Deck", body="Point from source"),
        critic_response,
    ]) as (base_url, requests):
        result = main([
            "ai-smoke",
            "--source",
            str(source),
            "--name",
            "cli-ai-smoke-visual",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--visual-critic",
            "--rendered-dir",
            str(rendered),
        ])

    project = base / "cli-ai-smoke-visual"
    output = capsys.readouterr().out
    trace = _read_trace(project)
    assert result == 0
    assert [event["stage"] for event in trace] == ["planner", "executor", "visual-critic"]
    assert [request["payload"]["model"] for request in requests] == [
        "planner-http",
        "executor-http",
        "vision-http",
    ]
    assert (project / "qa" / "VISUAL-REVIEW.md").exists()
    assert (project / "qa" / "visual-feedback.json").exists()
    smoke = json.loads((project / "qa" / "AI-SMOKE.json").read_text(encoding="utf-8"))
    assert smoke["status"] == "passed"
    assert smoke["visual_critic"] is True
    assert smoke["require_visual_ok"] is False
    assert smoke["rendered_source"] == "external-rendered-dir"
    assert smoke["stages"] == ["planner", "executor", "visual-critic"]
    assert smoke["models"] == {
        "planner": "planner-http",
        "executor": "executor-http",
        "vision": "vision-http",
    }
    assert smoke["metrics"]["attempts"] == 3
    assert smoke["metrics"]["passed_events"] == 3
    assert smoke["metrics"]["failed_events"] == 0
    assert smoke["metrics"]["blocking_count"] == 0
    assert smoke["metrics"]["max_visual_severity"] == "ok"
    assert "visual-critic" in output
    assert "severity=ok" in output
    assert "AI-SMOKE.json" in output


def test_cli_ai_smoke_require_visual_ok_fails_on_minor_feedback(tmp_path, monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "live"
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })
    critic_response = json.dumps({
        "severity": "minor",
        "summary": "Slide is readable but hierarchy could be improved.",
        "issues": ["Title and body hierarchy is slightly weak"],
        "actions": ["Increase title contrast and spacing"],
        "repair_prompt": "Increase the title contrast and add more spacing above the body while preserving all source text.",
    })
    rendered = tmp_path / "rendered"
    rendered.mkdir()
    (rendered / "slide-1.jpg").write_bytes(b"fake-jpeg")

    with _FakeOpenAIServer([
        plan_json,
        _valid_svg(title="HTTP Deck", body="Point from source"),
        critic_response,
    ]) as (base_url, _requests):
        result = main([
            "ai-smoke",
            "--source",
            str(source),
            "--name",
            "cli-ai-smoke-visual-minor-ok-gate",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--visual-critic",
            "--require-visual-ok",
            "--rendered-dir",
            str(rendered),
        ])

    project = base / "cli-ai-smoke-visual-minor-ok-gate"
    stderr = capsys.readouterr().err
    smoke = json.loads((project / "qa" / "AI-SMOKE.json").read_text(encoding="utf-8"))
    assert result == 1
    assert smoke["status"] == "failed"
    assert smoke["visual_critic"] is True
    assert smoke["require_visual_ok"] is True
    assert smoke["metrics"]["failed_events"] == 0
    assert smoke["metrics"]["max_visual_severity"] == "minor"
    assert smoke["diagnosis"]["focus"] == "visual-ok-gate"
    assert smoke["diagnosis"]["event"] == 3
    assert smoke["diagnosis"]["severity"] == "minor"
    assert smoke["diagnosis"]["inspect_raw"] == f"slide-skill ai-trace {project} --event 3 --part raw"
    assert smoke["diagnosis"]["repair_target_count"] == 1
    assert smoke["diagnosis"]["repair_targets"] == [{
        "slide": "1",
        "severity": "minor",
        "summary": "Slide is readable but hierarchy could be improved.",
        "repair": "Increase the title contrast and add more spacing above the body while preserving all source text.",
        "repair_source": "repair_prompt",
    }]
    assert smoke["diagnosis"]["repair_command"] == f"slide-skill repair-feedback {project} --min-severity minor"
    assert "AI smoke visual-ok gate failed" in smoke["error"]
    assert "AI smoke visual-ok gate failed" in stderr

    result = main(["ai-smoke-summary", str(project), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert result == 1
    assert payload[0]["summary_hint"] == "visual-ok:targets=1"


def test_cli_ai_smoke_visual_critic_falls_back_to_svg_preview_rendering(tmp_path, monkeypatch):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "live"
    calls = []

    def fake_render_pptx(deck, rendered_dir, dpi=150):
        calls.append(("pptx", deck, rendered_dir, dpi))
        raise RuntimeError("Render dependencies are not ready. Run `slide-skill render-doctor` for details.")

    def fake_render_svg_previews(project, rendered_dir):
        calls.append(("svg", project, rendered_dir))
        rendered_dir.mkdir(parents=True, exist_ok=True)
        (rendered_dir / "_svg-preview-html").mkdir(parents=True, exist_ok=True)
        image = rendered_dir / "slide-01.png"
        image.write_bytes(b"fake-png")
        return [image]

    monkeypatch.setattr("slide_skill.cli.render_pptx", fake_render_pptx)
    monkeypatch.setattr("slide_skill.cli.render_svg_previews", fake_render_svg_previews)
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })
    critic_response = json.dumps({
        "severity": "ok",
        "summary": "Slide is readable and complete.",
        "issues": [],
        "actions": [],
        "repair_prompt": "",
    })

    with _FakeOpenAIServer([
        plan_json,
        _valid_svg(title="HTTP Deck", body="Point from source"),
        critic_response,
    ]) as (base_url, _requests):
        result = main([
            "ai-smoke",
            "--source",
            str(source),
            "--name",
            "cli-ai-smoke-svg-preview",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--visual-critic",
        ])

    project = base / "cli-ai-smoke-svg-preview"
    smoke = json.loads((project / "qa" / "AI-SMOKE.json").read_text(encoding="utf-8"))
    assert result == 0
    assert [call[0] for call in calls] == ["pptx", "svg"]
    assert smoke["status"] == "passed"
    assert smoke["rendered_source"] == "svg-preview"
    assert smoke["rendered_dir"].endswith("qa\\rendered") or smoke["rendered_dir"].endswith("qa/rendered")
    assert (project / "qa" / "rendered" / "slide-01.png").exists()


def test_cli_ai_smoke_require_pptx_render_rejects_external_rendered_dir(tmp_path, monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    rendered = tmp_path / "rendered"
    rendered.mkdir()
    (rendered / "slide-1.jpg").write_bytes(b"fake-jpeg")

    result = main([
        "ai-smoke",
        "--source",
        str(source),
        "--name",
        "cli-ai-smoke-pptx-render-external",
        "--base",
        str(tmp_path / "live"),
        "--ai-base-url",
        "http://127.0.0.1:9/v1",
        "--planner-model",
        "planner-http",
        "--executor-model",
        "executor-http",
        "--vision-model",
        "vision-http",
        "--visual-critic",
        "--require-pptx-render",
        "--rendered-dir",
        str(rendered),
    ])

    stderr = capsys.readouterr().err
    assert result == 1
    assert "--require-pptx-render cannot be used with --rendered-dir" in stderr


def test_cli_ai_smoke_require_pptx_render_preflights_render_dependencies_before_llm(tmp_path, monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("slide_skill.cli.render_environment", lambda: {
        "ok": False,
        "soffice": None,
        "pdftoppm": "pdftoppm",
        "issues": ["LibreOffice soffice was not found on PATH or common Windows install paths."],
    })
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "live"

    with _FakeOpenAIServer([]) as (base_url, requests):
        result = main([
            "ai-smoke",
            "--source",
            str(source),
            "--name",
            "cli-ai-smoke-pptx-render-preflight",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--visual-critic",
            "--require-pptx-render",
        ])

    project = base / "cli-ai-smoke-pptx-render-preflight"
    stderr = capsys.readouterr().err
    smoke = json.loads((project / "qa" / "AI-SMOKE.json").read_text(encoding="utf-8"))
    assert result == 1
    assert requests == []
    assert smoke["status"] == "failed"
    assert smoke["trace_events"] == 0
    assert smoke["require_pptx_render"] is True
    assert smoke["rendered_source"] == "missing-render-dependencies"
    assert smoke["diagnosis"]["focus"] == "pptx-render-gate"
    assert smoke["diagnosis"]["rendered_source"] == "missing-render-dependencies"
    assert "LibreOffice soffice was not found" in smoke["error"]
    assert "AI smoke PPTX render preflight failed" in stderr


def test_cli_ai_smoke_require_pptx_render_fails_on_svg_preview_fallback(tmp_path, monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("slide_skill.cli.render_environment", lambda: {
        "ok": True,
        "soffice": "soffice",
        "pdftoppm": "pdftoppm",
        "issues": [],
    })
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "live"
    calls = []

    def fake_render_pptx(deck, rendered_dir, dpi=150):
        calls.append(("pptx", deck, rendered_dir, dpi))
        raise RuntimeError("Render dependencies are not ready. Run `slide-skill render-doctor` for details.")

    def fake_render_svg_previews(project, rendered_dir):
        calls.append(("svg", project, rendered_dir))
        rendered_dir.mkdir(parents=True, exist_ok=True)
        image = rendered_dir / "slide-01.png"
        image.write_bytes(b"fake-png")
        return [image]

    monkeypatch.setattr("slide_skill.cli.render_pptx", fake_render_pptx)
    monkeypatch.setattr("slide_skill.cli.render_svg_previews", fake_render_svg_previews)
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })

    with _FakeOpenAIServer([
        plan_json,
        _valid_svg(title="HTTP Deck", body="Point from source"),
    ]) as (base_url, requests):
        result = main([
            "ai-smoke",
            "--source",
            str(source),
            "--name",
            "cli-ai-smoke-pptx-render-fallback",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--visual-critic",
            "--require-pptx-render",
        ])

    project = base / "cli-ai-smoke-pptx-render-fallback"
    stderr = capsys.readouterr().err
    smoke = json.loads((project / "qa" / "AI-SMOKE.json").read_text(encoding="utf-8"))
    trace = _read_trace(project)
    assert result == 1
    assert [call[0] for call in calls] == ["pptx", "svg"]
    assert [event["stage"] for event in trace] == ["planner", "executor"]
    assert smoke["status"] == "failed"
    assert smoke["visual_critic"] is True
    assert smoke["require_pptx_render"] is True
    assert smoke["rendered_source"] == "svg-preview"
    assert smoke["diagnosis"]["focus"] == "pptx-render-gate"
    assert smoke["diagnosis"]["rendered_source"] == "svg-preview"
    assert "render-doctor" in smoke["diagnosis"]["next"]
    assert "AI smoke PPTX render gate failed" in smoke["error"]
    assert "AI smoke PPTX render gate failed" in stderr
    assert (project / "qa" / "rendered" / "slide-01.png").exists()


def test_cli_ai_smoke_fails_on_major_visual_feedback_but_keeps_evidence(tmp_path, monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "live"
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })
    critic_response = json.dumps({
        "severity": "critical",
        "summary": "Slide has severe clipping.",
        "issues": ["Title is clipped at the top edge"],
        "actions": ["Move title down and reduce size"],
        "repair_prompt": "Move the clipped title down, reduce its size, and preserve all visible source text.",
    })
    rendered = tmp_path / "rendered"
    rendered.mkdir()
    (rendered / "slide-1.jpg").write_bytes(b"fake-jpeg")

    with _FakeOpenAIServer([
        plan_json,
        _valid_svg(title="HTTP Deck", body="Point from source"),
        critic_response,
    ]) as (base_url, _requests):
        result = main([
            "ai-smoke",
            "--source",
            str(source),
            "--name",
            "cli-ai-smoke-visual-critical",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--visual-critic",
            "--rendered-dir",
            str(rendered),
        ])

    project = base / "cli-ai-smoke-visual-critical"
    stderr = capsys.readouterr().err
    smoke = json.loads((project / "qa" / "AI-SMOKE.json").read_text(encoding="utf-8"))
    assert result == 1
    assert smoke["status"] == "failed"
    assert smoke["deck"]
    assert smoke["qa_report"]
    assert smoke["visual_critic"] is True
    assert smoke["rendered_source"] == "external-rendered-dir"
    assert smoke["metrics"]["failed_events"] == 0
    assert smoke["metrics"]["max_visual_severity"] == "critical"
    assert smoke["diagnosis"]["focus"] == "active-repair-gate"
    assert smoke["diagnosis"]["event"] == 3
    assert smoke["diagnosis"]["stage"] == "visual-critic"
    assert smoke["diagnosis"]["severity"] == "critical"
    assert smoke["diagnosis"]["inspect_raw"] == f"slide-skill ai-trace {project} --event 3 --part raw"
    assert smoke["diagnosis"]["repair_target_count"] == 1
    assert smoke["diagnosis"]["repair_targets"][0]["severity"] == "critical"
    assert smoke["diagnosis"]["repair_targets"][0]["repair"] == "Move the clipped title down, reduce its size, and preserve all visible source text."
    assert smoke["diagnosis"]["repair_targets"][0]["repair_source"] == "repair_prompt"
    assert smoke["diagnosis"]["repair_command"] == f"slide-skill repair-feedback {project} --min-severity major"
    assert "AI smoke visual QA failed" in smoke["error"]
    assert "AI smoke visual QA failed" in stderr
    assert "last-ai-repair-gate" in stderr
    assert "AI-SMOKE.json" in stderr


def test_cli_ai_smoke_writes_failure_result_when_planner_fails(tmp_path, monkeypatch, capsys):
    from slide_skill.ai_trace import write_ai_trace
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "live"

    def fake_plan(source_text, config, *, project_path=None, **kwargs):
        write_ai_trace(
            project_path,
            stage="planner",
            model=kwargs.get("model") or "planner-http",
            status="failed",
            attempt=1,
            metadata={"error": "provider call failed: AuthenticationError: 401 Forbidden"},
        )
        raise RuntimeError("AI planner provider call failed after 1 attempt")

    monkeypatch.setattr("slide_skill.ai_planner.plan_slides_with_ai", fake_plan)

    result = main([
        "ai-smoke",
        "--source",
        str(source),
        "--name",
        "cli-ai-smoke-failure",
        "--base",
        str(base),
        "--ai-base-url",
        "http://127.0.0.1:11434/v1",
        "--planner-model",
        "planner-http",
    ])

    project = base / "cli-ai-smoke-failure"
    stderr = capsys.readouterr().err
    smoke = json.loads((project / "qa" / "AI-SMOKE.json").read_text(encoding="utf-8"))
    assert result == 1
    assert smoke["status"] == "failed"
    assert smoke["error"] == "AI planner provider call failed after 1 attempt"
    assert smoke["deck"] == ""
    assert smoke["qa_report"] == ""
    assert smoke["stages"] == ["planner"]
    assert smoke["models"]["planner"] == "planner-http"
    assert smoke["metrics"]["failed_events"] == 1
    assert smoke["metrics"]["prompt_chars"] == 0
    assert smoke["metrics"]["blocking_count"] == 0
    assert smoke["metrics"]["max_visual_severity"] == ""
    assert smoke["diagnosis"]["focus"] == "latest-failure"
    assert smoke["diagnosis"]["event"] == 1
    assert smoke["diagnosis"]["stage"] == "planner"
    assert smoke["diagnosis"]["inspect_raw"] == f"slide-skill ai-trace {project} --event 1 --part raw"
    assert smoke["diagnosis"]["provider_role"] == "planner"
    assert smoke["diagnosis"]["provider_model"] == "planner-http"
    assert "OPENAI_PLANNER_MODEL or --planner-model" in smoke["diagnosis"]["next"]
    assert "before running quickstart-ai or ai-smoke" in smoke["diagnosis"]["next"]
    assert "Current model=planner-http" in smoke["diagnosis"]["next"]
    assert smoke["stage_statuses"][0]["status"] == "failed"
    assert "AI-SMOKE.json" in stderr
    assert f"slide-skill ai-trace {project} --diagnose" in stderr


def test_cli_ai_smoke_summary_reports_pass_and_failure(tmp_path, monkeypatch, capsys):
    from slide_skill.cli import main

    passed = tmp_path / "passed"
    failed = tmp_path / "failed"
    (passed / "qa").mkdir(parents=True)
    (failed / "qa").mkdir(parents=True)
    (passed / "qa" / "AI-SMOKE.json").write_text(json.dumps({
        "status": "passed",
        "project": str(passed),
        "visual_critic": True,
        "rendered_source": "svg-preview",
        "trace_events": 3,
        "metrics": {
            "prompt_chars": 100,
            "raw_chars": 20,
            "request_chars": 140,
            "failed_events": 0,
            "blocking_count": 2,
            "max_visual_severity": "minor",
        },
        "stages": ["planner", "executor", "visual-critic"],
        "models": {"planner": "p", "executor": "e", "vision": "v"},
        "diagnosis": {"focus": "all-passed"},
    }), encoding="utf-8")
    (failed / "qa" / "AI-SMOKE.json").write_text(json.dumps({
        "status": "failed",
        "project": str(failed),
        "visual_critic": False,
        "rendered_source": "",
        "trace_events": 1,
        "metrics": {
            "prompt_chars": 10,
            "raw_chars": 0,
            "request_chars": 12,
            "failed_events": 1,
            "blocking_count": 0,
            "max_visual_severity": "",
        },
        "stages": ["planner"],
        "models": {"planner": "p2", "executor": "", "vision": ""},
        "diagnosis": {
            "focus": "latest-failure",
            "provider_role": "planner",
            "provider_model": "p2",
        },
        "error": "401 Forbidden",
    }), encoding="utf-8")

    result = main(["ai-smoke-summary", str(passed), str(failed)])
    output = capsys.readouterr().out

    assert result == 1
    assert "AI smoke summary" in output
    assert "passed | planner,executor,visual-critic | 3 | 0 | 2 | minor | 100 | 20 | 140 | yes | svg-preview | p | e | v" in output
    assert "failed | planner | 1 | 1 | 0 | - | 10 | 0 | 12 | no | - | p2 | - | -" in output
    assert "failed:provider=planner" in output

    result = main(["ai-smoke-summary", str(passed / "qa" / "AI-SMOKE.json"), "--json"])
    raw = capsys.readouterr().out
    payload = json.loads(raw)

    assert result == 0
    assert payload[0]["status"] == "passed"
    assert payload[0]["result_path"].endswith("AI-SMOKE.json")
    assert payload[0]["summary_hint"] == "-"

    result = main(["ai-smoke-summary", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert str(passed) in output
    assert str(failed) in output


def test_cli_ai_smoke_summary_refreshes_stale_diagnosis_from_trace(tmp_path, capsys):
    from slide_skill.ai_trace import write_ai_trace
    from slide_skill.cli import main

    project = tmp_path / "stale-smoke"
    (project / "qa").mkdir(parents=True)
    write_ai_trace(
        project,
        stage="planner",
        model="planner-http",
        status="passed",
        prompt="Plan",
        raw='{"slides":[]}',
        request={"model": "planner-http"},
        attempt=1,
        metadata={"slides": 1, "feedback": False},
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-http",
        status="failed",
        prompt="SVG",
        raw="<svg></svg>",
        request={"model": "executor-http"},
        attempt=1,
        metadata={
            "slide": 1,
            "blocking_count": 1,
            "blocking_issues": [
                "Bullet rendering: bullet body text uses primary title color #F1F5F9; use body/text_secondary color #94A3B8"
            ],
            "has_qa_feedback": False,
        },
    )
    write_ai_trace(
        project,
        stage="executor",
        model="executor-http",
        status="passed",
        prompt="SVG with feedback",
        raw="<svg></svg>",
        request={"model": "executor-http"},
        attempt=2,
        metadata={"slide": 1, "blocking_count": 0, "has_qa_feedback": True},
    )
    (project / "qa" / "AI-SMOKE.json").write_text(json.dumps({
        "status": "passed",
        "project": str(project),
        "visual_critic": False,
        "rendered_source": "",
        "trace_events": 3,
        "metrics": {
            "prompt_chars": 100,
            "raw_chars": 20,
            "request_chars": 140,
            "failed_events": 1,
            "blocking_count": 1,
            "max_visual_severity": "",
        },
        "stages": ["planner", "executor", "executor"],
        "models": {"planner": "planner-http", "executor": "executor-http", "vision": ""},
        "diagnosis": {
            "focus": "recovered-failure",
            "next": "A later retry passed; inspect this event only if the generated artifact still looks wrong.",
        },
    }), encoding="utf-8")

    result = main(["ai-smoke-summary", str(project)])
    output = capsys.readouterr().out

    assert result == 0
    assert "recovered:style-token" in output

    result = main(["ai-smoke-summary", str(project), "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert result == 0
    assert payload[0]["diagnosis_refreshed_from_trace"] is True
    assert payload[0]["summary_hint"].startswith("recovered:style-token")
    assert payload[0]["diagnosis"]["next_detail"][0].startswith("Fix style-token compliance")
    assert payload[0]["diagnosis"]["recovered_by_event"] == 3
    assert payload[0]["diagnosis"]["recovered_feedback_used"] is True
    assert payload[0]["metrics"]["failure_hint_counts"] == {"style-token": 1}
    assert payload[0]["metrics"]["recovered_failure_count"] == 1
    assert payload[0]["metrics"]["feedback_recovered_failure_count"] == 1


def test_cli_ai_release_summary_reports_release_gate_runs(tmp_path, capsys):
    from slide_skill.cli import main

    passed = tmp_path / "passed-release"
    failed = tmp_path / "failed-release"
    (passed / "qa").mkdir(parents=True)
    (failed / "qa").mkdir(parents=True)
    (passed / "qa" / "AI-RELEASE-CHECK.json").write_text(json.dumps({
        "status": "passed",
        "project": str(passed),
        "summary": {
            "decision": "release-ready",
            "release_ready": True,
            "blocking_reasons": [],
            "warnings": ["final visual evidence came from svg-preview, not PPTX render"],
            "final_visual_severity": "ok",
            "smoke_visual_severity": "minor",
            "rendered_source": "svg-preview",
            "visual_iteration_reviewed": True,
            "visual_repair_applied": True,
        },
        "gates": {
            "release_ready": True,
            "rendered_source_pptx": False,
            "visual_iteration_review": True,
            "visual_repair_applied": True,
        },
        "smoke": {"metrics": {"failed_events": 0, "blocking_count": 0}},
        "iteration": {"total_metrics": {"failed_events": 0, "blocking_count": 0}},
    }), encoding="utf-8")
    (failed / "qa" / "AI-RELEASE-CHECK.json").write_text(json.dumps({
        "status": "failed",
        "project": str(failed),
        "summary": {
            "decision": "not-release-ready",
            "release_ready": False,
            "blocking_reasons": [
                "PPTX render preflight failed before provider/model calls because render dependencies are missing"
            ],
            "warnings": [],
            "final_visual_severity": "",
            "smoke_visual_severity": "",
            "rendered_source": "missing-render-dependencies",
        },
        "gates": {
            "release_ready": False,
            "rendered_source_pptx": False,
            "visual_iteration_review": False,
            "visual_repair_applied": False,
        },
        "smoke": {"metrics": {"failed_events": 0, "blocking_count": 0}},
        "iteration": {},
    }), encoding="utf-8")

    result = main(["ai-release-summary", str(passed), str(failed)])
    output = capsys.readouterr().out

    assert result == 1
    assert "AI release summary" in output
    assert "passed | release-ready | yes | ok | minor | svg-preview | no | yes | yes | 0 | 0 | 1 | ready-warning:final visual evidence came from svg-preview" in output
    assert "failed | not-release-ready | no | - | - | missing-render-dependencies | no | no | no | 0 | 0 | 0 | blocked:PPTX render preflight failed" in output

    result = main(["ai-release-summary", str(passed / "qa" / "AI-RELEASE-CHECK.json"), "--json"])
    raw = capsys.readouterr().out
    payload = json.loads(raw)

    assert result == 0
    assert payload[0]["status"] == "passed"
    assert payload[0]["result_path"].endswith("AI-RELEASE-CHECK.json")
    assert payload[0]["summary_hint"].startswith("ready-warning:final visual evidence came from svg-preview")

    result = main(["ai-release-summary", str(failed / "qa" / "AI-RELEASE-CHECK.json"), "--json"])
    raw = capsys.readouterr().out
    payload = json.loads(raw)

    assert result == 1
    assert payload[0]["status"] == "failed"
    assert payload[0]["summary_hint"].startswith("blocked:PPTX render preflight failed")

    result = main(["ai-release-summary", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert str(passed) in output
    assert str(failed) in output


def test_ai_release_summary_propagates_smoke_repair_targets():
    from slide_skill.cli import _ai_release_check_summary, _ai_release_summary_hint

    doctor = [
        SimpleNamespace(role="planner", status="passed", model="planner-http"),
        SimpleNamespace(role="executor", status="passed", model="executor-http"),
        SimpleNamespace(role="vision", status="passed", model="vision-http"),
    ]
    smoke = {
        "status": "failed",
        "require_pptx_render": False,
        "rendered_source": "external-rendered-dir",
        "metrics": {"max_visual_severity": "minor"},
        "stage_statuses": [
            {"stage": "visual-critic", "metadata": {"severity": "minor"}},
        ],
        "diagnosis": {
            "focus": "visual-ok-gate",
            "repair_target_count": 1,
            "repair_targets": [
                {
                    "slide": "1",
                    "severity": "minor",
                    "summary": "Title hierarchy is weak.",
                    "repair": "Increase title contrast and spacing while preserving source text.",
                    "repair_source": "repair_prompt",
                }
            ],
            "repair_command": "slide-skill repair-feedback project --min-severity minor",
        },
    }
    gates = {
        "provider_preflight": True,
        "planner_executor_visual_smoke": True,
        "visual_iteration_review": False,
        "visual_repair_applied": False,
        "visual_severity_ok": False,
        "rendered_source_pptx": False,
        "trace_has_no_failed_events": True,
        "trace_converged_after_retries": False,
        "executor_had_planner_brief": True,
        "release_ready": False,
    }

    summary = _ai_release_check_summary(
        doctor,
        smoke,
        None,
        gates=gates,
        status="failed",
        error="AI smoke visual-ok gate failed: latest visual severity is minor",
    )

    assert summary["decision"] == "not-release-ready"
    assert summary["repair_target_count"] == 1
    assert summary["repair_targets"] == smoke["diagnosis"]["repair_targets"]
    assert summary["repair_command"] == "slide-skill repair-feedback project --min-severity minor"
    assert any("final visual severity is minor" in reason for reason in summary["blocking_reasons"])
    assert any("slide-skill repair-feedback project --min-severity minor" in action for action in summary["next_actions"])
    assert _ai_release_summary_hint({"status": "failed", "summary": summary, "gates": gates}) == "blocked:repair-targets=1"


def test_ai_release_summary_hint_surfaces_provider_failure_roles():
    from slide_skill.cli import _ai_release_summary_hint

    summary = {
        "provider_failures": [
            {"role": "planner", "status": "failed"},
            {"role": "vision", "status": "failed"},
        ],
        "blocking_reasons": ["provider preflight failed for role(s): planner, vision"],
    }
    gates = {"release_ready": False}

    assert _ai_release_summary_hint({"status": "failed", "summary": summary, "gates": gates}) == "blocked:provider=planner,vision"

    summary["repair_target_count"] = 2
    assert _ai_release_summary_hint({"status": "failed", "summary": summary, "gates": gates}) == "blocked:repair-targets=2"


def test_cli_ai_release_check_runs_doctor_and_strict_visual_smoke(tmp_path, monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "release"
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })
    critic_response = json.dumps({
        "severity": "ok",
        "summary": "Slide is readable and complete.",
        "issues": [],
        "actions": [],
        "repair_prompt": "",
    })
    rendered = tmp_path / "rendered"
    rendered.mkdir()
    (rendered / "slide-1.jpg").write_bytes(b"fake-jpeg")
    two_region_svg = _valid_svg(title="HTTP Deck", body="Point from source").replace(
        "</svg>",
        '  <g id="content-proof-01"><text x="720" y="240" font-family="Aptos, Arial, sans-serif" font-size="24" fill="#94A3B8">Point from source</text></g>\n</svg>',
    )

    with _FakeOpenAIServer([
        "ok",
        "ok",
        "ok",
        plan_json,
        two_region_svg,
        critic_response,
    ]) as (base_url, requests):
        result = main([
            "ai-release-check",
            "--source",
            str(source),
            "--name",
            "cli-ai-release",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--rendered-dir",
            str(rendered),
        ])

    project = base / "cli-ai-release"
    output = capsys.readouterr().out
    release = json.loads((project / "qa" / "AI-RELEASE-CHECK.json").read_text(encoding="utf-8"))
    assert result == 0
    assert release["status"] == "passed"
    assert release["error"] == ""
    assert [item["role"] for item in release["doctor"]] == ["planner", "executor", "vision"]
    assert all(item["status"] == "passed" for item in release["doctor"])
    assert release["smoke"]["status"] == "passed"
    assert release["smoke"]["visual_critic"] is True
    assert release["smoke"]["require_visual_ok"] is True
    assert release["smoke"]["metrics"]["max_visual_severity"] == "ok"
    assert release["summary"]["decision"] == "release-ready"
    assert release["summary"]["blocking_reasons"] == []
    assert release["summary"]["final_visual_severity"] == "ok"
    assert release["summary"]["rendered_source"] == "external-rendered-dir"
    assert any("not PPTX render" in warning for warning in release["summary"]["warnings"])
    assert any("--require-pptx-render" in action for action in release["summary"]["next_actions"])
    assert release["gates"] == {
        "provider_preflight": True,
        "planner_executor_visual_smoke": True,
        "visual_iteration_review": False,
        "visual_repair_applied": False,
        "visual_severity_ok": True,
        "rendered_source_pptx": False,
        "trace_has_no_failed_events": True,
        "trace_converged_after_retries": True,
        "executor_had_planner_brief": True,
        "release_ready": True,
    }
    assert [request["payload"]["model"] for request in requests] == [
        "planner-http",
        "executor-http",
        "vision-http",
        "planner-http",
        "executor-http",
        "vision-http",
    ]
    assert "AI-RELEASE-CHECK.json" in output


def test_cli_ai_release_check_require_pptx_render_preflights_before_provider_doctor(tmp_path, monkeypatch, capsys):
    from slide_skill import cli as cli_module
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "render_environment", lambda: {
        "ok": False,
        "soffice": None,
        "pdftoppm": "pdftoppm",
        "issues": ["LibreOffice soffice was not found on PATH or common Windows install paths."],
    })
    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "release"

    with _FakeOpenAIServer([]) as (base_url, requests):
        result = main([
            "ai-release-check",
            "--source",
            str(source),
            "--name",
            "cli-ai-release-pptx-render-preflight",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--require-pptx-render",
        ])

    project = base / "cli-ai-release-pptx-render-preflight"
    stderr = capsys.readouterr().err
    release = json.loads((project / "qa" / "AI-RELEASE-CHECK.json").read_text(encoding="utf-8"))
    assert result == 1
    assert requests == []
    assert release["status"] == "failed"
    assert release["doctor"] == []
    assert release["smoke"]["status"] == "failed"
    assert release["smoke"]["trace_events"] == 0
    assert release["smoke"]["require_pptx_render"] is True
    assert release["smoke"]["rendered_source"] == "missing-render-dependencies"
    assert release["smoke"]["diagnosis"]["focus"] == "pptx-render-gate"
    assert release["gates"]["provider_preflight"] is False
    assert release["gates"]["planner_executor_visual_smoke"] is False
    assert release["gates"]["rendered_source_pptx"] is False
    assert release["gates"]["release_ready"] is False
    assert release["summary"]["decision"] == "not-release-ready"
    assert release["summary"]["rendered_source"] == "missing-render-dependencies"
    assert release["summary"]["blocking_reasons"] == [
        "PPTX render preflight failed before provider/model calls because render dependencies are missing"
    ]
    assert release["summary"]["warnings"] == []
    assert any("render-doctor" in action for action in release["summary"]["next_actions"])
    assert not any("ai-doctor" in action for action in release["summary"]["next_actions"])
    assert "PPTX render preflight failed" in stderr


def test_cli_ai_release_check_repairs_visual_ok_smoke_failure(tmp_path, monkeypatch, capsys):
    from slide_skill import cli as cli_module
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fake_render(_project, _deck, rendered_dir, dpi=150):
        rendered_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 36), color=(12, 20, 36)).save(rendered_dir / "slide-01.png")
        return "svg-preview"

    monkeypatch.setattr(cli_module, "_render_visual_evidence", fake_render)

    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "release"
    rendered = tmp_path / "rendered"
    rendered.mkdir()
    (rendered / "slide-1.jpg").write_bytes(b"fake-jpeg")
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })
    critic_minor = json.dumps({
        "severity": "minor",
        "summary": "Decorative dot near the title creates clutter.",
        "issues": ["Extra blue dot near the title."],
        "actions": ["Remove the title-adjacent dot and keep progress dots in the footer."],
        "repair_prompt": "Remove the isolated blue dot near the title while preserving the footer progress dots and all source-backed text.",
    })
    critic_ok = json.dumps({
        "severity": "ok",
        "summary": "Slide is readable and complete.",
        "issues": [],
        "actions": [],
        "repair_prompt": "",
    })
    two_region_svg = _valid_svg(title="HTTP Deck", body="Point from source").replace(
        "</svg>",
        '  <g id="content-proof-01"><text x="720" y="240" font-family="Aptos, Arial, sans-serif" font-size="24" fill="#94A3B8">Point from source</text></g>\n</svg>',
    )

    with _FakeOpenAIServer([
        "ok",
        "ok",
        "ok",
        plan_json,
        two_region_svg,
        critic_minor,
        critic_minor,
        two_region_svg,
        critic_ok,
    ]) as (base_url, requests):
        result = main([
            "ai-release-check",
            "--source",
            str(source),
            "--name",
            "cli-ai-release-repaired",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--rendered-dir",
            str(rendered),
        ])

    project = base / "cli-ai-release-repaired"
    output = capsys.readouterr().out
    release = json.loads((project / "qa" / "AI-RELEASE-CHECK.json").read_text(encoding="utf-8"))
    assert result == 0
    assert release["status"] == "passed"
    assert release["smoke"]["status"] == "failed"
    assert release["iteration"]["status"] == "passed"
    assert release["iteration"]["latest_visual_severity"] == "ok"
    assert release["gates"]["visual_iteration_review"] is True
    assert release["gates"]["visual_repair_applied"] is True
    assert release["gates"]["visual_severity_ok"] is True
    assert release["gates"]["trace_converged_after_retries"] is True
    assert release["gates"]["release_ready"] is True
    assert release["summary"]["decision"] == "release-ready"
    assert release["summary"]["smoke_visual_severity"] == "minor"
    assert release["summary"]["final_visual_severity"] == "ok"
    assert release["summary"]["visual_iteration_reviewed"] is True
    assert release["summary"]["visual_repair_applied"] is True
    assert any("depends on the repaired visual iteration" in warning for warning in release["summary"]["warnings"])
    assert [request["payload"]["model"] for request in requests] == [
        "planner-http",
        "executor-http",
        "vision-http",
        "planner-http",
        "executor-http",
        "vision-http",
        "vision-http",
        "executor-http",
        "vision-http",
    ]
    assert "AI-RELEASE-CHECK.json" in output


def test_cli_ai_release_check_require_pptx_render_fails_when_iteration_falls_back_to_svg(tmp_path, monkeypatch, capsys):
    from slide_skill import cli as cli_module
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "render_environment", lambda: {
        "ok": True,
        "soffice": "soffice",
        "pdftoppm": "pdftoppm",
        "issues": [],
    })
    rendered_sources = ["pptx-render", "svg-preview", "svg-preview"]

    def fake_render(_project, _deck, rendered_dir, dpi=150):
        rendered_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 36), color=(12, 20, 36)).save(rendered_dir / "slide-01.png")
        return rendered_sources.pop(0) if rendered_sources else "svg-preview"

    monkeypatch.setattr(cli_module, "_render_visual_evidence", fake_render)

    source = tmp_path / "source.md"
    source.write_text("# HTTP Deck\n\n- Point from source\n", encoding="utf-8")
    base = tmp_path / "release"
    plan_json = json.dumps({
        "slides": [
            {
                "layout": "cover",
                "title": "HTTP Deck",
                "items": [{"type": "text", "primary": "Point from source"}],
                "rhythm": "anchor",
                "visual_strategy": "hero title with source-backed supporting point",
                "layout_pattern": "title left with compact proof card right",
            }
        ]
    })
    critic_minor = json.dumps({
        "severity": "minor",
        "summary": "Decorative dot near the title creates clutter.",
        "issues": ["Extra blue dot near the title."],
        "actions": ["Remove the title-adjacent dot and keep progress dots in the footer."],
        "repair_prompt": "Remove the isolated blue dot near the title while preserving the footer progress dots and all source-backed text.",
    })
    critic_ok = json.dumps({
        "severity": "ok",
        "summary": "Slide is readable and complete.",
        "issues": [],
        "actions": [],
        "repair_prompt": "",
    })
    two_region_svg = _valid_svg(title="HTTP Deck", body="Point from source").replace(
        "</svg>",
        '  <g id="content-proof-01"><text x="720" y="240" font-family="Aptos, Arial, sans-serif" font-size="24" fill="#94A3B8">Point from source</text></g>\n</svg>',
    )

    with _FakeOpenAIServer([
        "ok",
        "ok",
        "ok",
        plan_json,
        two_region_svg,
        critic_minor,
        critic_minor,
        two_region_svg,
        critic_ok,
    ]) as (base_url, _requests):
        result = main([
            "ai-release-check",
            "--source",
            str(source),
            "--name",
            "cli-ai-release-strict-render-fallback",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--require-pptx-render",
        ])

    project = base / "cli-ai-release-strict-render-fallback"
    stderr = capsys.readouterr().err
    release = json.loads((project / "qa" / "AI-RELEASE-CHECK.json").read_text(encoding="utf-8"))
    assert result == 1
    assert release["status"] == "failed"
    assert release["error"] == "AI release gates did not reach release_ready."
    assert release["smoke"]["status"] == "failed"
    assert release["smoke"]["require_pptx_render"] is True
    assert release["smoke"]["rendered_source"] == "pptx-render"
    assert release["iteration"]["status"] == "passed"
    assert release["iteration"]["latest_rendered_source"] == "svg-preview"
    assert release["gates"]["visual_iteration_review"] is True
    assert release["gates"]["visual_severity_ok"] is True
    assert release["gates"]["rendered_source_pptx"] is False
    assert release["gates"]["release_ready"] is False
    assert release["summary"]["decision"] == "not-release-ready"
    assert release["summary"]["strict_pptx_render_required"] is True
    assert release["summary"]["rendered_source"] == "svg-preview"
    assert any("strict PPTX render was required" in reason for reason in release["summary"]["blocking_reasons"])
    assert "release check gates failed" in stderr.lower()


def test_ai_iteration_failure_writes_machine_readable_result(tmp_path, monkeypatch):
    from slide_skill import cli as cli_module
    from slide_skill.cli import _run_ai_iteration_loop

    project = _project(tmp_path)
    (project / "svg_final").mkdir(exist_ok=True)
    (project / "exports").mkdir(exist_ok=True)
    deck = project / "exports" / "deck.pptx"
    deck.write_bytes(b"fake")

    def fake_render(_project, _deck, rendered_dir, dpi=150):
        rendered_dir.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 36), color=(12, 20, 36)).save(rendered_dir / "slide-01.png")
        return "svg-preview"

    def fail_visual(*args, **kwargs):
        raise RuntimeError("visual critic failed quality gate for slide 1 after 7 attempt(s)")

    monkeypatch.setattr(cli_module, "_render_visual_evidence", fake_render)
    monkeypatch.setattr("slide_skill.visual_critic.generate_visual_feedback", fail_visual)

    try:
        _run_ai_iteration_loop(
            project,
            rounds=1,
            first_pptx=deck,
            dpi=150,
            min_severity="minor",
            strict_qa=True,
            require_visual_ok=True,
            executor_kwargs={},
            vision_kwargs={},
        )
    except RuntimeError as exc:
        assert "visual critic failed quality gate" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    iteration = json.loads((project / "qa" / "AI-ITERATION.json").read_text(encoding="utf-8"))
    assert iteration["status"] == "failed"
    assert "visual critic failed quality gate" in iteration["error"]
    assert iteration["latest_rendered_source"] == "svg-preview"
    assert (project / "qa" / "FIX-VERIFY.md").exists()


def test_cli_ai_release_check_stops_when_provider_doctor_fails(tmp_path, monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    base = tmp_path / "release"

    def fail_provider(handler, payload):
        encoded = json.dumps({
            "error": {"message": "bad key", "type": "auth_error"},
        }).encode("utf-8")
        handler.send_response(401)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(encoded)))
        handler.end_headers()
        handler.wfile.write(encoded)

    with _FakeOpenAIServer([fail_provider, "ok", "ok"]) as (base_url, requests):
        result = main([
            "ai-release-check",
            "--name",
            "cli-ai-release-fail",
            "--base",
            str(base),
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
        ])

    project = base / "cli-ai-release-fail"
    stderr = capsys.readouterr().err
    release = json.loads((project / "qa" / "AI-RELEASE-CHECK.json").read_text(encoding="utf-8"))
    assert result == 1
    assert len(requests) == 3
    assert release["status"] == "failed"
    assert "provider preflight failed" in stderr.lower()
    assert release["error"] == "AI provider doctor failed; release smoke was not run."
    assert release["doctor"][0]["role"] == "planner"
    assert release["doctor"][0]["status"] == "failed"
    assert release["doctor"][0]["next_action"].startswith("Verify OPENAI_PLANNER_MODEL or --planner-model")
    assert "before running quickstart-ai or ai-smoke" in release["doctor"][0]["next_action"]
    assert release["summary"]["provider_failures"] == [{
        "role": "planner",
        "status": "failed",
        "model": "planner-http",
        "base_url": base_url,
        "error": release["doctor"][0]["error"],
        "next_action": release["doctor"][0]["next_action"],
    }]
    assert release["summary"]["next_actions"][0].startswith(
        "planner provider: Verify OPENAI_PLANNER_MODEL or --planner-model"
    )
    assert "before running quickstart-ai or ai-smoke" in release["summary"]["next_actions"][0]
    assert [request["payload"]["model"] for request in requests] == [
        "planner-http",
        "executor-http",
        "vision-http",
    ]
    assert release["smoke"] == {}
    assert release["iteration"] == {}
    assert release["gates"]["provider_preflight"] is False
    assert release["gates"]["planner_executor_visual_smoke"] is False


def test_cli_ai_iteration_summary_reports_repair_convergence(tmp_path, capsys):
    from slide_skill.cli import main

    passed = tmp_path / "passed"
    failed = tmp_path / "failed"
    (passed / "qa").mkdir(parents=True)
    (failed / "qa").mkdir(parents=True)
    (passed / "qa" / "AI-ITERATION.json").write_text(json.dumps({
        "status": "passed",
        "project": str(passed),
        "strict_qa": True,
        "require_visual_ok": True,
        "latest_visual_severity": "minor",
        "latest_visual_feedback": {
            "slides_reviewed": 2,
            "issue_count": 3,
            "action_count": 2,
            "repair_prompt_count": 1,
            "actionable_repair_count": 1,
            "non_ok_count": 1,
            "summaries": ["slide 1: spacing needs cleanup"],
        },
        "latest_rendered_source": "svg-preview",
        "models": {"executor": "executor-a", "vision": "vision-a"},
        "trace_events": 8,
        "total_trace_events": 20,
        "metrics": {
            "prompt_chars": 1000,
            "raw_chars": 300,
            "request_chars": 1800,
            "failed_events": 1,
            "blocking_count": 2,
            "visual_feedback_used_events": 2,
        },
        "repair_cycles": [
            {"round": 1, "repaired": [{"generated": "a.svg", "final": "a.svg"}]},
            {"round": 2, "repaired": [{"generated": "a.svg", "final": "a.svg"}]},
        ],
    }), encoding="utf-8")
    (failed / "qa" / "AI-ITERATION.json").write_text(json.dumps({
        "status": "failed",
        "project": str(failed),
        "strict_qa": True,
        "require_visual_ok": False,
        "latest_visual_severity": "major",
        "latest_visual_feedback": {
            "slides_reviewed": 1,
            "issue_count": 4,
            "action_count": 3,
            "repair_prompt_count": 1,
            "actionable_repair_count": 1,
            "non_ok_count": 1,
            "summaries": ["slide 1: content is clipped"],
        },
        "repair_target_count": 1,
        "repair_targets": [
            {
                "slide": "1",
                "severity": "major",
                "summary": "content is clipped",
                "repair": "Move content lower.",
                "repair_source": "repair_prompt",
            }
        ],
        "repair_command": f"slide-skill repair-feedback {failed} --min-severity minor",
        "latest_rendered_source": "pptx-render",
        "models": {"executor": "executor-b", "vision": "vision-b"},
        "trace_events": 3,
        "total_trace_events": 9,
        "metrics": {
            "prompt_chars": 500,
            "raw_chars": 120,
            "request_chars": 900,
            "failed_events": 0,
            "blocking_count": 0,
            "visual_feedback_used_events": 1,
        },
        "repair_cycles": [
            {"round": 1, "repaired": [{"generated": "b.svg", "final": "b.svg"}]},
        ],
    }), encoding="utf-8")

    result = main(["ai-iteration-summary", str(passed), str(failed)])
    output = capsys.readouterr().out

    assert result == 1
    assert "AI iteration summary" in output
    assert "hint | project" in output
    assert "passed | yes | yes | 2 | 2 | minor | 3 | 1 | 1 | svg-preview | executor-a | vision-a | 8 | 20 | 1 | 2 | 2 | 1000 | 300 | 1800 | passed-warning:minor,issues=3,non-ok=1,repair-prompts=1,repaired=2" in output
    assert "failed | yes | no | 1 | 1 | major | 4 | 1 | 1 | pptx-render | executor-b | vision-b | 3 | 9 | 0 | 0 | 1 | 500 | 120 | 900 | failed:targets=1,major,issues=4,non-ok=1,repair-prompts=1,repaired=1" in output

    result = main(["ai-iteration-summary", str(passed / "qa" / "AI-ITERATION.json"), "--json"])
    raw = capsys.readouterr().out
    payload = json.loads(raw)

    assert result == 0
    assert payload[0]["status"] == "passed"
    assert payload[0]["latest_visual_feedback"]["issue_count"] == 3
    assert payload[0]["latest_visual_feedback"]["actionable_repair_count"] == 1
    assert payload[0]["result_path"].endswith("AI-ITERATION.json")
    assert payload[0]["summary_hint"] == "passed-warning:minor,issues=3,non-ok=1,repair-prompts=1,repaired=2"

    result = main(["ai-iteration-summary", str(tmp_path)])
    output = capsys.readouterr().out

    assert result == 1
    assert str(passed) in output
    assert str(failed) in output


def test_cli_ai_doctor_checks_role_models_and_vision_http(monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with _FakeOpenAIServer(["ok", "ok", "ok"]) as (base_url, requests):
        result = main([
            "ai-doctor",
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
            "--check-vision",
        ])

    output = capsys.readouterr().out
    assert result == 0
    assert "- planner: passed | model=planner-http" in output
    assert "- executor: passed | model=executor-http" in output
    assert "- vision: passed | model=vision-http" in output
    assert [request["payload"]["model"] for request in requests] == [
        "planner-http",
        "executor-http",
        "vision-http",
    ]
    vision_content = requests[2]["payload"]["messages"][1]["content"]
    assert vision_content[0]["type"] == "text"
    assert vision_content[1]["type"] == "image_url"
    assert vision_content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_cli_ai_doctor_reports_next_actions_for_failures_and_skipped_vision(monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fail_provider(handler, payload):
        encoded = json.dumps({
            "error": {"message": "bad key", "type": "auth_error"},
        }).encode("utf-8")
        handler.send_response(401)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(encoded)))
        handler.end_headers()
        handler.wfile.write(encoded)

    with _FakeOpenAIServer([fail_provider, "ok"]) as (base_url, _requests):
        result = main([
            "ai-doctor",
            "--ai-base-url",
            base_url,
            "--planner-model",
            "planner-http",
            "--executor-model",
            "executor-http",
            "--vision-model",
            "vision-http",
        ])

    output = capsys.readouterr().out
    assert result == 1
    assert "- planner: failed | model=planner-http" in output
    assert "next=Verify OPENAI_PLANNER_MODEL or --planner-model" in output
    assert "before running quickstart-ai or ai-smoke" in output
    assert "- executor: passed | model=executor-http" in output
    assert "- vision: skipped | model=vision-http" in output
    assert "next=Rerun with --check-vision before relying on visual-critic" in output


def test_cli_ai_doctor_requires_provider_access(monkeypatch, capsys):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    result = main(["ai-doctor"])

    stderr = capsys.readouterr().err
    assert result == 1
    assert "AI doctor requires model access" in stderr


def test_visual_feedback_repair_loop_uses_repair_prompt_over_http(tmp_path, monkeypatch):
    from slide_skill.cli import main

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    project = _project(tmp_path)
    existing_svg = _valid_svg(title="Repair Title", body="Repair Body")
    (project / "svg_output" / "slide_01.svg").write_text(existing_svg, encoding="utf-8")
    (project / "svg_final" / "slide_01.svg").write_text(existing_svg, encoding="utf-8")
    rendered = project / "qa" / "rendered"
    rendered.mkdir(parents=True, exist_ok=True)
    (rendered / "slide-1.jpg").write_bytes(b"fake-jpeg")
    critic_response = json.dumps({
        "severity": "major",
        "summary": "Title is clipped near the top edge",
        "issues": ["Title touches the top edge"],
        "actions": ["Move the title block down by 32 px"],
        "repair_prompt": "Rewrite slide 1 with the title block 32 px lower while preserving Repair Title and Repair Body.",
    })

    with _FakeOpenAIServer([
        critic_response,
        _valid_svg(title="Repair Title", body="Repair Body"),
    ]) as (base_url, requests):
        generate_visual_feedback(
            project,
            base_url=base_url,
            api_key="test-key",
            model="vision-http",
        )
        result = main([
            "repair-feedback",
            str(project),
            "--ai-base-url",
            base_url,
            "--executor-model",
            "executor-http",
        ])

    assert result == 0
    assert [request["payload"]["model"] for request in requests] == ["vision-http", "executor-http"]
    repair_request = requests[1]["payload"]["messages"][1]["content"]
    assert "Rendered Visual Repair Contract" in repair_request
    assert "mandatory repair targets" in repair_request
    assert "Prioritize `repair_prompt` items" in repair_request
    assert "repair_prompt" in repair_request
    assert "title block 32 px lower" in repair_request
    assert "Content Fidelity Contract" in repair_request
    assert 'title: "Repair Title"' in repair_request
    assert (project / "svg_final" / "slide_01.svg").exists()


def _read_trace(project):
    return [
        json.loads(line)
        for line in (project / "qa" / "ai-trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
