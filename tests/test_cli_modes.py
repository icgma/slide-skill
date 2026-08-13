"""Regression tests for no-key CLI usability (phase 48).

Contract under test:
- ``--mode auto`` (default) resolves to ``ai`` only when AI access is
  configured, otherwise to the deterministic ``fast`` renderer.
- Legacy aliases ``quick`` and ``template-smoke`` resolve to ``fast``.
- No CLI path ever calls ``input()``; explicit AI requests without a key
  fail fast with actionable OPENAI_API_KEY guidance.
- Fast-mode output carries no self-deprecation ("not production" / "smoke").
"""

from argparse import Namespace
from pathlib import Path

import pytest

from slide_skill.cli import _require_ai_access, _resolve_generation_mode, main


@pytest.fixture(autouse=True)
def _no_key_and_no_prompt(monkeypatch):
    """Scrub AI env vars and make any input() call fail loudly."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    def _forbidden_input(*args, **kwargs):
        raise AssertionError("input() must not be called")

    monkeypatch.setattr("builtins.input", _forbidden_input)


def test_resolve_mode_aliases():
    assert _resolve_generation_mode(Namespace(mode="quick")) == "fast"
    assert _resolve_generation_mode(Namespace(mode="template-smoke")) == "fast"
    assert _resolve_generation_mode(Namespace(mode="fast")) == "fast"
    assert _resolve_generation_mode(Namespace(mode="ai")) == "ai"


def test_resolve_mode_auto_no_key():
    args = Namespace(mode="auto", ai_api_key=None, ai_base_url=None)
    assert _resolve_generation_mode(args) == "fast"


def test_resolve_mode_auto_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    args = Namespace(mode="auto", ai_api_key=None, ai_base_url=None)
    assert _resolve_generation_mode(args) == "ai"


def _write_source(tmp_path: Path) -> Path:
    source = tmp_path / "source.md"
    source.write_text(
        "# 无钥匙演示\n\n"
        "## 第一部分\n\n- 要点一\n- 要点二\n\n"
        "## 第二部分\n\n- 要点三\n",
        encoding="utf-8",
    )
    return source


def test_quickstart_no_key_end_to_end(tmp_path):
    source = _write_source(tmp_path)
    base = tmp_path / "projects"

    result = main([
        "quickstart",
        str(source),
        "--name",
        "t48",
        "--base",
        str(base),
    ])

    assert result in (0, None)
    exports = list((base / "t48" / "exports").glob("*.pptx"))
    assert exports, "no-key quickstart must produce a .pptx artifact"


def test_quickstart_auto_no_key_prints_degrade_hint(tmp_path, capsys):
    source = _write_source(tmp_path)

    result = main([
        "quickstart",
        str(source),
        "--name",
        "t48-hint",
        "--base",
        str(tmp_path / "projects"),
    ])

    captured = capsys.readouterr()
    assert result in (0, None)
    assert captured.err.count("mode: fast (no API key detected") == 1


def test_quickstart_explicit_ai_without_key(tmp_path, capsys):
    source = _write_source(tmp_path)

    result = main([
        "quickstart",
        str(source),
        "--name",
        "t48-ai",
        "--base",
        str(tmp_path / "projects"),
        "--mode",
        "ai",
    ])

    captured = capsys.readouterr()
    assert result == 1
    assert "OPENAI_API_KEY" in captured.err
    assert "--mode fast" in captured.err


def test_fast_mode_no_self_deprecation(tmp_path, capsys):
    source = _write_source(tmp_path)

    result = main([
        "quickstart",
        str(source),
        "--name",
        "t48-fast",
        "--base",
        str(tmp_path / "projects"),
        "--mode",
        "fast",
    ])

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert result in (0, None)
    assert "not production" not in combined
    assert "smoke" not in combined


def test_ai_only_command_gates_without_key(capsys):
    result = main(["visual-critic", "no-such-project"])

    captured = capsys.readouterr()
    assert result == 1
    assert "OPENAI_API_KEY" in captured.err


def test_require_ai_access_force_reports_guidance(capsys):
    args = Namespace(ai_api_key=None, ai_base_url=None)

    assert _require_ai_access(args, force=True) is False
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.err
    assert "--ai-api-key" in captured.err
