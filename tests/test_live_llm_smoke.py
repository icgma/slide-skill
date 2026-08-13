import json
import os
from pathlib import Path

import pytest

from slide_skill.ai_executor import generate_svg_with_ai
from slide_skill.ai_planner import plan_slides_with_ai
from slide_skill.ai_trace import read_ai_trace, summarize_ai_trace
from slide_skill.content_planner import ContentConfig


def test_live_llm_planner_executor_smoke(tmp_path):
    """Opt-in smoke test for real OpenAI-compatible model interaction."""
    api_key, base_url, planner_model, executor_model = _live_llm_config()
    project = _live_project(tmp_path)
    source = """# Python 入门速览

## 变量与类型
- Python 变量无需提前声明类型。
- 常见类型包括 int、float、str 和 bool。
- 动态类型提升入门效率，但需要通过测试减少类型错误。
"""
    config = ContentConfig(max_slides=1, max_items_per_slide=3, audience="beginner programmers")

    plans = plan_slides_with_ai(
        source,
        config,
        project_path=project,
        api_key=api_key,
        base_url=base_url,
        model=planner_model,
        max_tokens=2500,
        temperature=0.2,
        retries=1,
    )
    paths = generate_svg_with_ai(
        project,
        plans,
        api_key=api_key,
        base_url=base_url,
        model=executor_model,
        max_tokens=4096,
        temperature=0.2,
        qa_retries=1,
        strict_quality=True,
    )

    assert len(plans) == 1
    assert plans[0].visual_strategy
    assert plans[0].layout_pattern
    assert len(paths) == 1
    assert paths[0].exists()
    assert paths[0].read_text(encoding="utf-8").lstrip().startswith("<svg")
    assert (project / "qa" / "ai-planner" / "plan.json").exists()
    assert (project / "qa" / "ai-planner" / "executor-brief.md").exists()
    assert (project / "qa" / "executor" / "slide_01_attempt_01.json").exists()

    events = read_ai_trace(project)
    summary = summarize_ai_trace(project)
    assert any(event["stage"] == "planner" and event["status"] == "passed" for event in events)
    assert any(event["stage"] == "executor" and event["status"] == "passed" for event in events)
    assert "has_executor_brief=True" in summary
    assert "prompt=ai-trace-artifacts/" in summary
    assert "raw=ai-trace-artifacts/" in summary


def _live_llm_config() -> tuple[str, str | None, str, str]:
    if os.environ.get("SLIDE_SKILL_RUN_LIVE_LLM") != "1":
        pytest.skip("set SLIDE_SKILL_RUN_LIVE_LLM=1 to run real LLM smoke tests")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        pytest.skip("OPENAI_API_KEY is required for real LLM smoke tests")
    base_url = os.environ.get("OPENAI_BASE_URL") or None
    default_model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    planner_model = os.environ.get("OPENAI_PLANNER_MODEL", default_model)
    executor_model = os.environ.get("OPENAI_EXECUTOR_MODEL", default_model)
    return api_key, base_url, planner_model, executor_model


def _live_project(tmp_path: Path) -> Path:
    project = tmp_path / "live-llm-smoke"
    for dirname in ("svg_output", "svg_final", "qa"):
        (project / dirname).mkdir(parents=True, exist_ok=True)
    spec_lock = {
        "canvas": {"width": 1280, "height": 720, "ratio": "16:9"},
        "title": "Python 入门速览",
        "theme": "dark-tech",
        "palette": {
            "background": "#0F172A",
            "surface": "#1E293B",
            "text": "#F8FAFC",
            "accent": "#38BDF8",
            "body": "#CBD5E1",
            "muted": "#334155",
        },
        "font_family": "Aptos, Arial, sans-serif",
    }
    (project / "spec_lock.json").write_text(json.dumps(spec_lock, ensure_ascii=False, indent=2), encoding="utf-8")
    (project / "spec_lock.md").write_text(
        """# Spec Lock

- Canvas: 1280x720
- Theme: dark-tech
- Palette: background #0F172A, surface #1E293B, text #F8FAFC, accent #38BDF8, body #CBD5E1, muted #334155
- Font: Aptos, Arial, sans-serif
""",
        encoding="utf-8",
    )
    return project
