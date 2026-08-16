"""Five-key concurrency pool tests (CONC-01..04).

Provider is stubbed with a latency-simulating OpenAI fake; the wall-clock
test proves the >=3x speedup mechanism offline (real-provider benchmark
numbers land in the phase evidence once keys are supplied).
"""
from __future__ import annotations

import json
import threading
import time
import types
from pathlib import Path

import pytest

from slide_skill.ai_executor import generate_svg_with_ai
from slide_skill.content_planner import ContentItem, SlidePlan

PAGE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
    '<g id="background"><rect x="0" y="0" width="1280" height="720" fill="#0F172A"/></g>'
    '<g id="content-title-01">'
    '<text x="80" y="120" font-family="Arial" font-size="44" fill="#F8FAFC">{title}</text>'
    "</g>"
    '<g id="content-body-01">'
    '<text x="80" y="220" font-family="Arial" font-size="24" fill="#F1F5F9">{body}</text>'
    "</g></svg>"
)


def _svg_for(title: str, body: str) -> str:
    return PAGE_SVG.replace("{title}", title).replace("{body}", body)


def _make_project(tmp_path: Path) -> Path:
    project = tmp_path / "conc-project"
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
    return project


def _plans(count: int):
    plans = []
    for i in range(1, count + 1):
        plans.append(SlidePlan(
            index=i,
            layout="bullet-list",
            title=f"第{i}页标题",
            items=[ContentItem(type="text", primary=f"第{i}页的内容要点")],
        ))
    return plans


def _install_stub(monkeypatch, *, latency: float = 0.15, fail_index: int | None = None):
    """Stub OpenAI whose completions sleep and return page-shaped SVGs.

    Records per-key in-flight counts to prove the one-request-per-key
    discipline. SlidePlan gained a ``fail_marker`` attribute in the test
    plans (dataclass allows attribute assignment).
    """
    lock = threading.Lock()
    state = {"inflight": {}, "max_inflight": 0, "calls": 0}
    api_keys_seen: list[str] = []

    class _Responses:
        def create(self, **kwargs):
            state["calls"] += 1
            time.sleep(latency)
            user_msg = kwargs["messages"][-1]["content"]
            title = body = ""
            for line in user_msg.splitlines():
                if "Title:" in line:
                    title = line.split("Title:", 1)[1].strip()
                if "第" in line and "页的内容要点" in line:
                    body = line.strip()
            marker = kwargs.get("marker")
            if fail_index is not None and f"第{fail_index}页" in user_msg:
                return types.SimpleNamespace(
                    choices=[types.SimpleNamespace(
                        message=types.SimpleNamespace(content="not an svg at all"),
                        finish_reason="stop",
                    )],
                )
            content = _svg_for(title or "标题", body or "内容")
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(
                    message=types.SimpleNamespace(content=content),
                    finish_reason="stop",
                )],
                usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=10),
            )

    class _Completions:
        def __init__(self, key):
            self._key = key
            self._responses = _Responses()

        def create(self, **kwargs):
            with lock:
                current = state["inflight"].get(self._key, 0) + 1
                state["inflight"][self._key] = current
                state["max_inflight"] = max(state["max_inflight"], current)
            try:
                return self._responses.create(**kwargs)
            finally:
                with lock:
                    state["inflight"][self._key] -= 1

    class _Client:
        def __init__(self, **kwargs):
            self._key = kwargs.get("api_key", "?")
            with lock:
                if self._key not in api_keys_seen:
                    api_keys_seen.append(self._key)
            self.chat = types.SimpleNamespace(
                completions=_Completions(self._key),
            )

    monkeypatch.setattr("openai.OpenAI", _Client)
    return state, api_keys_seen


class TestKeySlotPool:
    def test_concurrent_run_respects_one_inflight_per_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEYS", "k1,k2,k3,k4,k5")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        state, keys = _install_stub(monkeypatch, latency=0.12)
        project = _make_project(tmp_path)
        plans = _plans(10)
        paths = generate_svg_with_ai(
            project, plans,
            model="stub", base_url="http://localhost:9/v1",
            run_qa=False, ai_concurrency=5,
        )
        assert len(paths) == 10
        assert state["max_inflight"] <= 1, "more than one in-flight request on a key"
        assert len(keys) == 5, "pool should use exactly the five env keys"

    def test_deterministic_publish_by_index(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEYS", "k1,k2,k3,k4,k5")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        _install_stub(monkeypatch, latency=0.05)
        project = _make_project(tmp_path)
        paths = generate_svg_with_ai(
            project, _plans(10),
            model="stub", base_url="http://localhost:9/v1",
            run_qa=False, ai_concurrency=5,
        )
        names = [p.name for p in paths]
        assert names == [f"slide_{i:02d}.svg" for i in range(1, 11)]
        for i in range(1, 11):
            assert (project / "svg_output" / f"slide_{i:02d}.svg").exists()

    def test_failed_page_fails_deck_wholesale(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEYS", "k1,k2,k3,k4,k5")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        _install_stub(monkeypatch, latency=0.02, fail_index=4)
        project = _make_project(tmp_path)
        with pytest.raises(RuntimeError, match="deck aborted wholesale"):
            generate_svg_with_ai(
                project, _plans(10),
                model="stub", base_url="http://localhost:9/v1",
                run_qa=False, ai_concurrency=5, qa_retries=0,
            )

    def test_no_key_material_in_trace_or_outputs(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEYS", "SECRET-KEY-AAA,SECRET-KEY-BBB")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        _install_stub(monkeypatch, latency=0.03)
        project = _make_project(tmp_path)
        generate_svg_with_ai(
            project, _plans(4),
            model="stub", base_url="http://localhost:9/v1",
            run_qa=False, ai_concurrency=2,
        )
        trace = (project / "qa" / "ai-trace.jsonl")
        if trace.exists():
            assert "SECRET-KEY" not in trace.read_text(encoding="utf-8")
        for svg in (project / "svg_output").glob("*.svg"):
            assert "SECRET-KEY" not in svg.read_text(encoding="utf-8")

    def test_trace_event_indexes_unique_under_concurrency(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEYS", "k1,k2,k3,k4,k5")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        _install_stub(monkeypatch, latency=0.03)
        project = _make_project(tmp_path)
        generate_svg_with_ai(
            project, _plans(10),
            model="stub", base_url="http://localhost:9/v1",
            run_qa=False, ai_concurrency=5,
        )
        from slide_skill.ai_trace import read_ai_trace
        import re as _re

        events = read_ai_trace(project)
        indexes = []
        for event in events:
            # One event number per event (artifact paths repeat it).
            for value in event.values():
                if isinstance(value, str):
                    match = _re.search(r"event-(\d{4})", value)
                    if match:
                        indexes.append(match.group(1))
                        break
        assert indexes, "trace events must carry artifact event indexes"
        assert len(indexes) == len(set(indexes)), "duplicate trace event indexes"

    def test_concurrency_without_pool_falls_back_serial(self, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("OPENAI_API_KEYS", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "single")
        _install_stub(monkeypatch, latency=0.02)
        project = _make_project(tmp_path)
        paths = generate_svg_with_ai(
            project, _plans(3),
            model="stub", base_url="http://localhost:9/v1",
            run_qa=False, ai_concurrency=5,
        )
        assert len(paths) == 3
        err = capsys.readouterr().err
        assert "no usable key pool" in err


class TestErrorPolicy:
    """CONC-04: auth isolation, Retry-After, transient retry."""

    def _install_error_stub(self, monkeypatch, *, bad_keys=(), rate_limit_key=None,
                            retry_after=None, sleeps=None):
        lock = threading.Lock()
        usage: dict[str, int] = {}

        class _AuthErr(Exception):
            status_code = 401

        class _RateErr(Exception):
            status_code = 429

            def __init__(self):
                super().__init__("rate limited")
                self.response = types.SimpleNamespace(
                    headers={"retry-after": str(retry_after if retry_after is not None else 3)}
                )

        class _Responses:
            def create(self, **kwargs):
                time.sleep(0.01)
                user_msg = kwargs["messages"][-1]["content"]
                title = body = ""
                for line in user_msg.splitlines():
                    if "Title:" in line:
                        title = line.split("Title:", 1)[1].strip()
                    if "页的内容要点" in line:
                        body = line.strip()
                return types.SimpleNamespace(
                    choices=[types.SimpleNamespace(
                        message=types.SimpleNamespace(content=_svg_for(title or "标题", body or "内容")),
                        finish_reason="stop",
                    )],
                    usage=types.SimpleNamespace(prompt_tokens=1, completion_tokens=1),
                )

        class _Completions:
            def __init__(self, key):
                self._key = key

            def create(self, **kwargs):
                with lock:
                    usage[self._key] = usage.get(self._key, 0) + 1
                if self._key in bad_keys:
                    raise _AuthErr("bad key")
                if rate_limit_key is not None and self._key == rate_limit_key:
                    if usage[self._key] <= 1:
                        raise _RateErr()
                return _Responses().create(**kwargs)

        class _Client:
            def __init__(self, **kwargs):
                key = kwargs.get("api_key", "?")
                self.chat = types.SimpleNamespace(completions=_Completions(key))

        monkeypatch.setattr("openai.OpenAI", _Client)
        return usage

    def test_auth_error_isolates_key_and_rotates(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("OPENAI_API_KEYS", "good-1,bad-1,good-2")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        usage = self._install_error_stub(monkeypatch, bad_keys=("bad-1",))
        project = _make_project(tmp_path)
        paths = generate_svg_with_ai(
            project, _plans(6),
            model="stub", base_url="http://localhost:9/v1",
            run_qa=False, ai_concurrency=3,
        )
        assert len(paths) == 6
        assert usage.get("bad-1", 0) == 1, "isolated key must not be reused"
        assert usage.get("good-1", 0) >= 1 and usage.get("good-2", 0) >= 1
        assert "key isolated" in capsys.readouterr().err

    def test_all_keys_auth_fail_fails_wholesale(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEYS", "bad-1,bad-2")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        self._install_error_stub(monkeypatch, bad_keys=("bad-1", "bad-2"))
        project = _make_project(tmp_path)
        with pytest.raises(RuntimeError, match="keys isolated"):
            generate_svg_with_ai(
                project, _plans(4),
                model="stub", base_url="http://localhost:9/v1",
                run_qa=False, ai_concurrency=2,
            )

    def test_rate_limit_honors_retry_after_then_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEYS", "k1,k2")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        sleeps: list[float] = []
        real_sleep = time.sleep
        monkeypatch.setattr(
            "slide_skill.ai_executor.time.sleep", lambda s: sleeps.append(s) or real_sleep(0),
        )
        usage = self._install_error_stub(
            monkeypatch, rate_limit_key="k1", retry_after=7,
        )
        project = _make_project(tmp_path)
        paths = generate_svg_with_ai(
            project, _plans(2),
            model="stub", base_url="http://localhost:9/v1",
            run_qa=False, ai_concurrency=2,
        )
        assert len(paths) == 2
        assert 7.0 in sleeps, "Retry-After must be honored before the retry"

    def test_auth_error_never_leaks_key_material(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEYS", "SECRET-K1,SECRET-K2")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        self._install_error_stub(monkeypatch, bad_keys=("SECRET-K1", "SECRET-K2"))
        project = _make_project(tmp_path)
        with pytest.raises(RuntimeError) as excinfo:
            generate_svg_with_ai(
                project, _plans(2),
                model="stub", base_url="http://localhost:9/v1",
                run_qa=False, ai_concurrency=2,
            )
        assert "SECRET" not in str(excinfo.value)
        trace = project / "qa" / "ai-trace.jsonl"
        if trace.exists():
            assert "SECRET" not in trace.read_text(encoding="utf-8")


class TestWallClock:
    def test_five_keys_ten_pages_at_least_3x_faster(self, tmp_path, monkeypatch):
        """CONC-04 mechanism proof with a latency-simulating provider.

        The stub models a provider with 0.25s per request: serial = 10
        requests on one key; concurrent = 10 requests across 5 keys. The
        >=3x threshold is asserted on the mechanism (scheduling + key
        slots); the real-provider multi-run median + P95 benchmark is
        recorded as phase evidence once production keys are available.
        """
        monkeypatch.setenv("OPENAI_API_KEYS", "k1,k2,k3,k4,k5")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        _install_stub(monkeypatch, latency=0.25)
        serial_project = _make_project(tmp_path / "serial")
        started = time.perf_counter()
        generate_svg_with_ai(
            serial_project, _plans(10),
            model="stub", base_url="http://localhost:9/v1",
            run_qa=False, ai_concurrency=1,
        )
        serial_elapsed = time.perf_counter() - started

        _install_stub(monkeypatch, latency=0.25)
        conc_project = _make_project(tmp_path / "conc")
        started = time.perf_counter()
        generate_svg_with_ai(
            conc_project, _plans(10),
            model="stub", base_url="http://localhost:9/v1",
            run_qa=False, ai_concurrency=5,
        )
        conc_elapsed = time.perf_counter() - started

        speedup = serial_elapsed / conc_elapsed
        assert speedup >= 3.0, f"wall-clock speedup {speedup:.2f}x below 3x threshold"
