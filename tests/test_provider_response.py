"""Provider response adapter, completion-status gate, and role budget tests."""
import json
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from slide_skill.ai_planner import plan_slides_with_ai
from slide_skill.content_planner import ContentConfig, ContentItem, SlidePlan
from slide_skill.provider_response import (
    DEFAULT_ROLE_MAX_TOKENS,
    MAX_TOKENS_CAP,
    TruncatedResponseError,
    escalate_budget,
    parse_provider_response,
)


def _fake_response(*, content="", reasoning=None, finish_reason="stop", response_id="resp-1", usage=None):
    message = SimpleNamespace(content=content)
    if reasoning is not None:
        message.reasoning = reasoning
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(id=response_id, choices=[choice], usage=usage)


def _valid_planner_payload(title="Gated Plan"):
    return {
        "slides": [
            {
                "index": 1,
                "layout": "cover",
                "title": title,
                "visual_strategy": "hero title with diagonal accent rail",
                "layout_pattern": "large title left with proof card right",
                "items": [{"type": "text", "primary": "Valid item"}],
            }
        ]
    }


def _make_executor_project(tmp_path):
    project = tmp_path / "gate-project"
    project.mkdir()
    (project / "svg_output").mkdir()
    (project / "qa").mkdir()
    (project / "spec_lock.json").write_text(json.dumps({
        "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
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


def _read_trace_events(project):
    trace_path = project / "qa" / "ai-trace.jsonl"
    return [
        json.loads(line)
        for line in trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestParseProviderResponse:

    def test_stop_response_parses_content_and_records_reasoning_length(self):
        response = _fake_response(
            content="OK",
            reasoning="thinking hard",
            finish_reason="stop",
            usage=SimpleNamespace(
                prompt_tokens=12,
                completion_tokens=5,
                total_tokens=17,
                completion_tokens_details=SimpleNamespace(reasoning_tokens=3),
            ),
        )
        provider = parse_provider_response(response)
        assert provider.content == "OK"
        assert provider.reasoning_chars == len("thinking hard")
        assert provider.finish_reason == "stop"
        assert provider.is_complete
        assert not provider.is_truncated
        assert not provider.blocks_parsing
        assert provider.prompt_tokens == 12
        assert provider.completion_tokens == 5
        assert provider.total_tokens == 17
        assert provider.reasoning_tokens == 3
        metadata = provider.trace_metadata()
        assert metadata["finish_reason"] == "stop"
        assert metadata["reasoning_chars"] == len("thinking hard")

    def test_length_response_with_empty_content_is_truncated(self):
        response = _fake_response(content="", reasoning="r" * 4000, finish_reason="length")
        provider = parse_provider_response(response)
        assert provider.is_truncated
        assert provider.blocks_parsing
        assert not provider.is_complete
        assert provider.content == ""
        assert provider.reasoning_chars == 4000

    def test_missing_finish_reason_gates_only_in_strict_mode(self):
        response = _fake_response(content="OK", finish_reason=None)
        lenient = parse_provider_response(response)
        assert lenient.is_complete
        assert not lenient.blocks_parsing
        strict = parse_provider_response(response, strict_missing_finish=True)
        assert not strict.is_complete
        assert strict.blocks_parsing

    def test_empty_choices_raises_runtime_error(self):
        with pytest.raises(RuntimeError, match="no choices"):
            parse_provider_response(SimpleNamespace(id="resp-1", choices=[], usage=None))


class TestPlannerTruncationGate:

    def test_truncated_planner_attempt_marks_trace_and_escalates_budget(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        payload = _valid_planner_payload()
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _fake_response(content="", reasoning="r" * 2048, finish_reason="length"),
            _fake_response(content=json.dumps(payload), finish_reason="stop"),
        ]
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            plans = plan_slides_with_ai(
                "# Source",
                ContentConfig(),
                project_path=project,
                api_key="sk-test",
                max_tokens=4096,
            )

        assert plans[0].title == "Gated Plan"
        calls = mock_client.chat.completions.create.call_args_list
        assert calls[0].kwargs["max_tokens"] == 4096
        assert calls[1].kwargs["max_tokens"] == 8192
        retry_prompt = calls[1].kwargs["messages"][1]["content"]
        assert "Planner Feedback From Previous Attempt" not in retry_prompt
        events = [event for event in _read_trace_events(project) if event["stage"] == "planner"]
        assert events[0]["status"] == "truncated"
        assert events[0]["metadata"]["finish_reason"] == "length"
        assert events[0]["metadata"]["reasoning_chars"] == 2048
        assert events[-1]["status"] == "passed"

    def test_fenced_valid_json_passes_first_attempt_with_protocol_warning(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        payload = _valid_planner_payload(title="Fenced Plan")
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response(
            content="```json\n" + json.dumps(payload) + "\n```",
            finish_reason="stop",
        )
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            plans = plan_slides_with_ai(
                "# Source",
                ContentConfig(),
                project_path=project,
                api_key="sk-test",
            )

        assert plans[0].title == "Fenced Plan"
        assert mock_client.chat.completions.create.call_count == 1
        events = [event for event in _read_trace_events(project) if event["stage"] == "planner"]
        assert events[-1]["status"] == "passed"
        warnings = events[-1]["metadata"]["protocol_warnings"]
        assert any("markdown fences" in warning for warning in warnings)


class TestExecutorTruncationGate:

    def test_truncated_executor_attempt_never_reaches_svg_extraction(self, tmp_path, monkeypatch):
        import slide_skill.ai_executor as ai_executor_module
        from slide_skill.ai_executor import generate_svg_with_ai

        project = _make_executor_project(tmp_path)
        plan = SlidePlan(
            index=1,
            layout="cover",
            title="Gated Slide",
            items=[ContentItem(type="text", primary="Hello")],
        )

        def _must_not_be_called(response_text):
            raise AssertionError("truncated content must never reach _extract_svg_with_issues")

        monkeypatch.setattr(ai_executor_module, "_extract_svg_with_issues", _must_not_be_called)

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _fake_response(
            content="", reasoning="r" * 100, finish_reason="length",
        )
        mock_openai = MagicMock(return_value=mock_client)

        with patch.dict("sys.modules", {"openai": MagicMock(OpenAI=mock_openai)}):
            with pytest.raises(RuntimeError, match="stayed truncated"):
                generate_svg_with_ai(project, [plan], qa_retries=1, run_qa=False)

        calls = mock_client.chat.completions.create.call_args_list
        assert len(calls) == 2
        assert calls[0].kwargs["max_tokens"] == DEFAULT_ROLE_MAX_TOKENS["executor"]
        assert calls[1].kwargs["max_tokens"] == escalate_budget(DEFAULT_ROLE_MAX_TOKENS["executor"])
        events = [event for event in _read_trace_events(project) if event["stage"] == "executor"]
        assert [event["status"] for event in events] == ["truncated", "truncated"]
        assert events[0]["metadata"]["finish_reason"] == "length"
        assert events[0]["metadata"]["reasoning_chars"] == 100
        assert not (project / "svg_output" / "slide_01.svg").exists()

    def test_truncated_error_carries_provider_response(self):
        response = _fake_response(content="", reasoning="r" * 10, finish_reason="length")
        provider = parse_provider_response(response)
        error = TruncatedResponseError("truncated", provider)
        assert error.response is provider
        assert isinstance(error, ValueError)


class TestBudgetEscalation:

    def test_escalate_budget_doubles_and_caps(self):
        assert escalate_budget(4096) == 8192
        assert escalate_budget(8192) == 16384
        assert escalate_budget(16384) == 32768
        assert escalate_budget(MAX_TOKENS_CAP) == MAX_TOKENS_CAP
        assert escalate_budget(20000) == MAX_TOKENS_CAP
        assert escalate_budget(1000, cap=1500) == 1500


class TestRoleBudgetResolution:

    ROLE_ENV_VARS = (
        "OPENAI_PLANNER_MAX_TOKENS",
        "OPENAI_EXECUTOR_MAX_TOKENS",
        "OPENAI_VISION_MAX_TOKENS",
        "OPENAI_MAX_TOKENS",
    )

    def _clear_env(self, monkeypatch):
        for name in self.ROLE_ENV_VARS:
            monkeypatch.delenv(name, raising=False)

    def test_role_budget_resolution_order(self, monkeypatch):
        from slide_skill.cli import _resolve_role_max_tokens

        self._clear_env(monkeypatch)
        # Role defaults when nothing else is configured.
        assert _resolve_role_max_tokens(Namespace(), "planner") == 4096
        assert _resolve_role_max_tokens(Namespace(), "executor") == 16384
        assert _resolve_role_max_tokens(Namespace(), "vision") == 4096
        # Global env beats the role default.
        monkeypatch.setenv("OPENAI_MAX_TOKENS", "6000")
        assert _resolve_role_max_tokens(Namespace(), "executor") == 6000
        # Global flag beats the global env.
        args_global_flag = Namespace(ai_max_tokens=5000)
        assert _resolve_role_max_tokens(args_global_flag, "executor") == 5000
        # Role env beats the global flag.
        monkeypatch.setenv("OPENAI_EXECUTOR_MAX_TOKENS", "9000")
        assert _resolve_role_max_tokens(args_global_flag, "executor") == 9000
        # Role flag beats everything.
        args_role_flag = Namespace(ai_max_tokens=5000, executor_max_tokens=12000)
        assert _resolve_role_max_tokens(args_role_flag, "executor") == 12000
        # Other roles fall back to the global flag, not the executor override.
        assert _resolve_role_max_tokens(args_role_flag, "planner") == 5000
        # Executor-only overrides leave other roles on their own defaults.
        self._clear_env(monkeypatch)
        assert _resolve_role_max_tokens(Namespace(executor_max_tokens=12000), "planner") == 4096

    def test_executor_kwargs_default_budget_is_16384(self, monkeypatch):
        from slide_skill.cli import _executor_kwargs_from_args

        self._clear_env(monkeypatch)
        kwargs = _executor_kwargs_from_args(Namespace())
        assert kwargs["max_tokens"] == 16384

    def test_role_budget_flags_exist_on_ai_parsers(self):
        from slide_skill.cli import _add_ai_args
        import argparse

        parser = argparse.ArgumentParser()
        _add_ai_args(parser)
        args = parser.parse_args([
            "--planner-max-tokens", "2222",
            "--executor-max-tokens", "3333",
            "--vision-max-tokens", "4444",
        ])
        assert args.planner_max_tokens == 2222
        assert args.executor_max_tokens == 3333
        assert args.vision_max_tokens == 4444
        assert args.ai_max_tokens is None
