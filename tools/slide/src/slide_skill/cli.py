"""Command line interface for Slide Skill v2.0."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

from .exporter import export_project, pptx_notes, pptx_text, validate_pptx
from .intake import convert_file, url_to_markdown
from .project import import_sources, init_project, validate_project
from .provider_response import DEFAULT_ROLE_MAX_TOKENS
from .qa import run_qa
from .render import render_environment, render_environment_report, render_pptx, render_svg_previews
from .svg_pipeline import create_spec, finalize_svg, generate_guide, generate_svg, generate_svg_from_plan, write_svg_report
from .template_ops import (
    delete_slides,
    duplicate_slide,
    inspect_template,
    reorder_slides,
    replace_text,
    replacements_from_json,
)

_DEFAULT_AI_BASE_URL = "https://api.openai.com/v1"
_LOCAL_AI_DUMMY_KEY = "local-openai-compatible"


def _validate_project_name(name: str) -> str:
    if ".." in Path(name).parts or Path(name).is_absolute():
        print(f"error: project name must not contain '..' or be absolute: {name}", file=sys.stderr)
        sys.exit(1)
    return name

_AI_SMOKE_SOURCE = """# Python 入门速览

## 变量与类型
- Python 变量无需提前声明类型。
- 常见类型包括 int、float、str 和 bool。
- 动态类型提升入门效率，但需要通过测试减少类型错误。
"""


def _add_ai_args(parser) -> None:
    """Add AI-related arguments to a subcommand parser."""
    parser.add_argument("--model", default=None,
                        help="Default LLM model ID for all AI roles unless a role-specific model is set")
    parser.add_argument("--planner-model", default=None,
                        help="AI Strategist model ID (default: OPENAI_PLANNER_MODEL or --model)")
    parser.add_argument("--executor-model", default=None,
                        help="AI Executor SVG model ID (default: --model or OPENAI_MODEL)")
    parser.add_argument("--vision-model", default=None,
                        help="AI visual critic model ID (default: OPENAI_VISION_MODEL or --model)")
    parser.add_argument("--planner-retries", type=int, default=None,
                        help="AI Strategist validation retry count (default: planner module default)")
    parser.add_argument("--executor-qa-retries", type=int, default=None,
                        help="AI Executor rewrite attempts after SVG/content QA failures (default: executor module default)")
    parser.add_argument("--vision-retries", type=int, default=None,
                        help="AI visual critic retry count for weak/invalid feedback (default: visual critic module default)")
    parser.add_argument("--ai-base-url", default=None,
                        help="OpenAI-compatible API base URL (default: OPENAI_BASE_URL env or https://api.openai.com/v1)")
    parser.add_argument("--ai-api-key", default=None,
                        help="API key (default: OPENAI_API_KEY env)")
    parser.add_argument("--ai-concurrency", type=int, default=1,
                        help="Bounded key-slot concurrency for the executor (default 1 = serial). "
                             "max_workers = min(N, usable keys, slide count); pool keys come only "
                             "from OPENAI_API_KEYS / OPENAI_API_KEY env")
    parser.add_argument("--ai-temperature", type=float, default=0.7,
                        help="Sampling temperature 0.0-2.0 (default: 0.7)")
    parser.add_argument("--ai-max-tokens", type=int, default=None,
                        help="Completion budget for all AI roles unless a role budget is set "
                             "(default: role-specific — planner 4096, executor 16384, vision 4096)")
    parser.add_argument("--planner-max-tokens", type=int, default=None,
                        help="AI Strategist completion budget (default: OPENAI_PLANNER_MAX_TOKENS, "
                             "then --ai-max-tokens/OPENAI_MAX_TOKENS, then 4096)")
    parser.add_argument("--executor-max-tokens", type=int, default=None,
                        help="AI Executor completion budget (default: OPENAI_EXECUTOR_MAX_TOKENS, "
                             "then --ai-max-tokens/OPENAI_MAX_TOKENS, then 16384)")
    parser.add_argument("--vision-max-tokens", type=int, default=None,
                        help="AI visual critic completion budget (default: OPENAI_VISION_MAX_TOKENS, "
                             "then --ai-max-tokens/OPENAI_MAX_TOKENS, then 4096)")
    parser.add_argument("--ai-top-p", type=float, default=None,
                        help="Nucleus sampling parameter (optional)")


def _ai_kwargs_from_args(args) -> dict:
    """Extract default AI kwargs from parsed CLI args."""
    api_key = getattr(args, "ai_api_key", None) or os.environ.get("OPENAI_API_KEY")
    base_url = getattr(args, "ai_base_url", None)
    if not api_key and _uses_custom_ai_base(base_url):
        api_key = _LOCAL_AI_DUMMY_KEY
    return {
        "model": getattr(args, "model", None),
        "api_key": api_key,
        "base_url": base_url,
        "max_tokens": getattr(args, "ai_max_tokens", None),
        "temperature": getattr(args, "ai_temperature", 0.7),
        "top_p": getattr(args, "ai_top_p", None),
    }


def _role_ai_kwargs_from_args(args, role: str) -> dict:
    """Extract kwargs for a specific AI role while preserving global defaults."""
    kwargs = _ai_kwargs_from_args(args)
    role_model = getattr(args, f"{role}_model", None)
    if role_model:
        kwargs["model"] = role_model
    kwargs["max_tokens"] = _resolve_role_max_tokens(args, role)
    return kwargs


def _resolve_role_max_tokens(args, role: str) -> int:
    """Resolve one role's completion budget.

    Order: role flag > role env (OPENAI_{ROLE}_MAX_TOKENS) >
    --ai-max-tokens / OPENAI_MAX_TOKENS > role default.
    """
    role_flag = getattr(args, f"{role}_max_tokens", None)
    if role_flag is not None:
        return int(role_flag)
    role_env = _env_max_tokens(f"OPENAI_{role.upper()}_MAX_TOKENS")
    if role_env is not None:
        return role_env
    global_flag = getattr(args, "ai_max_tokens", None)
    if global_flag is not None:
        return int(global_flag)
    global_env = _env_max_tokens("OPENAI_MAX_TOKENS")
    if global_env is not None:
        return global_env
    return DEFAULT_ROLE_MAX_TOKENS[role]


def _env_max_tokens(name: str) -> int | None:
    """Parse a positive integer budget from the environment, else None."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _planner_kwargs_from_args(args) -> dict:
    kwargs = _role_ai_kwargs_from_args(args, "planner")
    retries = getattr(args, "planner_retries", None)
    if retries is not None:
        kwargs["retries"] = retries
    return kwargs


def _executor_kwargs_from_args(args) -> dict:
    kwargs = _role_ai_kwargs_from_args(args, "executor")
    retries = getattr(args, "executor_qa_retries", None)
    if retries is not None:
        kwargs["qa_retries"] = retries
    concurrency = getattr(args, "ai_concurrency", None)
    if concurrency is not None:
        kwargs["ai_concurrency"] = max(1, int(concurrency))
    return kwargs


def _vision_kwargs_from_args(args) -> dict:
    kwargs = _role_ai_kwargs_from_args(args, "vision")
    retries = getattr(args, "vision_retries", None)
    if retries is not None:
        kwargs["retries"] = retries
    return kwargs


def _release_vision_kwargs_from_args(args) -> dict:
    kwargs = _vision_kwargs_from_args(args)
    kwargs["retries"] = max(int(kwargs.get("retries") or 0), 6)
    return kwargs


def _resolve_generation_mode(args) -> str:
    """Return canonical generation mode: ``ai`` or ``fast``.

    ``fast`` is the deterministic template renderer (``template-smoke`` and
    ``quick`` are kept as backward-compatible aliases). The default ``auto``
    resolves to ``ai`` when AI access is configured, otherwise ``fast``.
    """
    mode = getattr(args, "mode", None) or "auto"
    if mode in ("quick", "template-smoke", "fast"):
        return "fast"
    if mode == "auto":
        return "ai" if _ai_access_configured(args) else "fast"
    return mode


def _resolve_planner_mode(args) -> str:
    """Resolve planner mode, defaulting production AI generation to AI planning."""
    planner = getattr(args, "planner", "deterministic") or "deterministic"
    if planner != "auto":
        return planner
    return "ai" if _resolve_generation_mode(args) == "ai" else "deterministic"


def _ai_access_configured(args) -> bool:
    """True when AI mode has either a key or an explicit non-default local base."""
    key = getattr(args, "ai_api_key", None) or os.environ.get("OPENAI_API_KEY", "")
    if key:
        return True
    base = getattr(args, "ai_base_url", None) or os.environ.get("OPENAI_BASE_URL", "")
    if base:
        return True
    return False


def _uses_custom_ai_base(base_url: str | None) -> bool:
    """True when requests are routed to a non-default OpenAI-compatible endpoint."""
    base = base_url or os.environ.get("OPENAI_BASE_URL", "")
    return bool(base and base.rstrip("/") != _DEFAULT_AI_BASE_URL.rstrip("/"))


def _require_ai_access(args, force: bool = False) -> bool:
    """Non-interactive gate for AI-dependent commands.

    Returns True when the invocation can proceed. Never prompts and never
    mutates ``args``. With ``force=True`` (AI-only commands) configured access
    is required unconditionally; otherwise the requirement is derived from the
    resolved generation/planner modes.
    """
    if not force:
        needs_generation_ai = _resolve_generation_mode(args) == "ai"
        needs_planner_ai = _resolve_planner_mode(args) == "ai"
        if not (needs_generation_ai or needs_planner_ai):
            return True
    if _ai_access_configured(args):
        return True
    print("error: AI mode requires an API key.", file=sys.stderr)
    print("  set OPENAI_API_KEY (and optionally OPENAI_BASE_URL), or pass --ai-api-key / --ai-base-url", file=sys.stderr)
    print("  or use --mode fast for deterministic no-key generation", file=sys.stderr)
    return False


_AI_COMMAND_ERRORS = (RuntimeError, FileNotFoundError, ValueError)


def _report_ai_command_failure(project: Path | str, exc: Exception) -> None:
    """Print actionable diagnostics for AI command failures."""
    project_path = Path(project)
    print(f"error: {exc}", file=sys.stderr)
    print(f"inspect: slide-skill ai-trace {project_path}", file=sys.stderr)
    print(f"diagnose: slide-skill ai-trace {project_path} --diagnose", file=sys.stderr)
    use_latest_iteration = _is_ai_iteration_result_failure(exc) and _has_current_ai_iteration_result(project_path)
    if use_latest_iteration:
        print(f"diagnose-latest: slide-skill ai-trace {project_path} --latest-iteration --diagnose", file=sys.stderr)
    try:
        from .ai_trace import latest_iteration_trace_scope, read_ai_trace
        events = read_ai_trace(project_path)
    except Exception:
        return
    if not events:
        print("last-ai-failure: no trace events found; failure occurred before a model call", file=sys.stderr)
        return
    selected_events = events
    try:
        if use_latest_iteration:
            scoped_events, _start_index, _label, _iteration = latest_iteration_trace_scope(project_path)
            if scoped_events:
                selected_events = scoped_events
    except Exception:
        selected_events = events
    failed = [event for event in selected_events if event.get("status") not in {"passed", "ok", "success"}]
    repair_gate = [
        event
        for event in selected_events
        if event.get("stage") == "visual-critic"
        and isinstance(event.get("metadata"), dict)
        and str(event["metadata"].get("severity", "")).lower() in {"major", "critical"}
    ]
    if "visual QA failed" in str(exc) and repair_gate:
        event = repair_gate[-1]
    else:
        event = failed[-1] if failed else selected_events[-1]
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    parts = [
        f"stage={event.get('stage', 'unknown')}",
        f"status={event.get('status', 'unknown')}",
        f"attempt={event.get('attempt', '-')}",
        f"model={event.get('model', '-')}",
    ]
    if "slide" in metadata:
        parts.append(f"slide={metadata['slide']}")
    if "blocking_count" in metadata:
        parts.append(f"blocking_count={metadata['blocking_count']}")
    severity = str(metadata.get("severity", "")).lower()
    label = "last-ai-failure" if failed else "last-ai-event"
    if event.get("stage") == "visual-critic" and severity in {"major", "critical"}:
        label = "last-ai-repair-gate"
    elif "visual-ok gate failed" in str(exc) and event.get("stage") == "visual-critic" and severity in {"minor", "major", "critical"}:
        label = "last-ai-quality-gate"
    print(f"{label}: {' | '.join(parts)}", file=sys.stderr)
    if metadata.get("error"):
        print(f"last-ai-error: {metadata['error']}", file=sys.stderr)


def _has_current_ai_iteration_result(project_path: Path) -> bool:
    """True when AI-ITERATION.json belongs to the current trace length."""
    iteration_path = project_path / "qa" / "AI-ITERATION.json"
    trace_path = project_path / "qa" / "ai-trace.jsonl"
    if not iteration_path.exists() or not trace_path.exists():
        return False
    try:
        payload = json.loads(iteration_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or "total_trace_events" not in payload:
        return False
    try:
        expected = int(payload.get("total_trace_events"))
    except (TypeError, ValueError):
        return False
    actual = sum(1 for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip())
    return expected == actual


def _is_ai_iteration_result_failure(exc: Exception) -> bool:
    """True for failures raised after iterate-ai has written AI-ITERATION.json."""
    message = str(exc)
    return "strict QA failed:" in message or "visual-ok gate failed:" in message


def main(argv: list[str] | None = None) -> int:
    _configure_stdio_for_model_text()
    parser = argparse.ArgumentParser(prog="slide-skill")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a deck project workspace")
    p_init.add_argument("name")
    p_init.add_argument("--format", default="ppt169")
    p_init.add_argument("--base", default="projects")
    p_init.add_argument("--overwrite", action="store_true")
    p_init.add_argument("--theme", default="dark-tech", help="Visual theme (dark-tech, light-corporate, warm-editorial, data-forward, vibrant-startup)")
    p_init.add_argument("--competition", default=None, help="Competition template (internet-plus, challenge-cup, math-modeling, innovation-training, thesis-defense, course-presentation)")
    p_init.add_argument("--from-example", action="store_true",
                        help="Start from the finished example pack for --competition: copies its source.md and speaker notes into the project")

    p_import = sub.add_parser("import-sources", help="Copy or move source files into a project")
    p_import.add_argument("project")
    p_import.add_argument("sources", nargs="+")
    p_import.add_argument("--move", action="store_true")

    p_validate = sub.add_parser("validate", help="Validate a project workspace")
    p_validate.add_argument("project")

    p_source = sub.add_parser("source-to-md", help="Convert source material to Markdown")
    p_source.add_argument("source")
    p_source.add_argument("-o", "--output")
    p_source.add_argument("--url", action="store_true")

    p_spec = sub.add_parser("spec", help="Create design_spec.md and spec_lock.json")
    p_spec.add_argument("project")
    p_spec.add_argument("--source")
    p_spec.add_argument("--title")
    p_spec.add_argument("--theme", default="dark-tech", help="Visual theme name")

    p_guide = sub.add_parser("generate-guide", help="Generate per-slide SVG authoring prompt for the AI Executor role")
    p_guide.add_argument("project")
    p_guide.add_argument("--source", required=True, help="Source Markdown file")
    p_guide.add_argument("--theme", default=None, help="Visual theme name (overrides spec_lock.json)")
    p_guide.add_argument("--max-slides", type=int, default=12)

    p_svg = sub.add_parser("svg", help="Generate SVG pages from Markdown (programmatic fallback)")
    p_svg.add_argument("project")
    p_svg.add_argument("--source", required=True)
    p_svg.add_argument("--max-slides", type=int, default=12)

    p_confirm = sub.add_parser("confirm", help="Run interactive Eight Confirmations dialogue")
    p_confirm.add_argument("project", help="Project directory path")
    p_confirm.add_argument("--auto", action="store_true", help="Auto-derive values without interaction")

    p_check = sub.add_parser("check-svg", help="Run SVG quality gate")
    p_check.add_argument("project")
    p_check.add_argument("--stage", default="output", choices=["output", "final"])
    p_check.add_argument("--quality", action="store_true", help="Enable design-quality checks (spec drift, font safety, rhythm, layout, imagery)")

    p_finalize = sub.add_parser("finalize-svg", help="Finalize SVG pages for export")
    p_finalize.add_argument("project")
    p_finalize.add_argument("--quality", action="store_true",
                            help="Treat design-quality warnings as blocking during finalization")

    p_export = sub.add_parser("export", help="Export finalized SVG pages to PPTX")
    p_export.add_argument("project")
    p_export.add_argument("-o", "--output")
    p_export.add_argument("--stage", default="final", choices=["output", "final"])
    p_export.add_argument("--com-smoke", dest="com_smoke", action="store_true", default=None,
                          help="Run the optional PowerPoint COM final smoke render after export")
    p_export.add_argument("--no-com-smoke", dest="com_smoke", action="store_false",
                          help="Skip the PowerPoint COM smoke render (auto-on on Windows)")

    p_qa = sub.add_parser("qa", help="Run QA checks")
    p_qa.add_argument("project")
    p_qa.add_argument("--pptx")
    p_qa.add_argument("--strict", action="store_true", help="Require visual QA and fix-and-verify evidence")
    p_qa.add_argument("--require-visual", action="store_true", help="Require rendered images and VISUAL-REVIEW.md")
    p_qa.add_argument("--require-fix-verify", action="store_true", help="Require FIX-VERIFY.md evidence")

    p_render = sub.add_parser("render", help="Render PPTX to per-slide JPEG images for visual QA")
    p_render.add_argument("pptx")
    p_render.add_argument("-o", "--output-dir", required=True)
    p_render.add_argument("--dpi", type=int, default=150)

    p_visual_critic = sub.add_parser("visual-critic", help="Analyze rendered slide images with AI and write repair feedback")
    p_visual_critic.add_argument("project", help="Project directory containing qa/rendered images")
    p_visual_critic.add_argument("--rendered-dir", default=None, help="Override rendered image directory (default: <project>/qa/rendered)")
    p_visual_critic.add_argument("--slides", default=None, help="Comma-separated slide numbers to analyze")
    _add_ai_args(p_visual_critic)

    p_pdf = sub.add_parser("pdf", help="Export a project or PPTX to PDF")
    p_pdf.add_argument("input", help="Project directory or .pptx file")
    p_pdf.add_argument("-o", "--output", required=True, help="Output .pdf path")
    p_pdf.add_argument("--backend", default="soffice", choices=["soffice", "cairo"],
                       help="Conversion backend (cairo skips LibreOffice; needs cairosvg + pypdf)")
    p_pdf.add_argument("--quality", default="standard", choices=["draft", "standard", "print"],
                       help="Embedded raster DPI tier (cairo backend only)")

    sub.add_parser("render-doctor", help="Check LibreOffice/Poppler render dependencies")

    p_text = sub.add_parser("pptx-text", help="Extract text from a PPTX")
    p_text.add_argument("pptx")

    p_notes = sub.add_parser("pptx-notes", help="Extract embedded speaker notes from a PPTX")
    p_notes.add_argument("pptx")

    p_pptx_validate = sub.add_parser("validate-pptx", help="Validate PPTX package/native editability")
    p_pptx_validate.add_argument("pptx")

    p_inspect = sub.add_parser("template-inspect", help="Inspect a PPTX template")
    p_inspect.add_argument("pptx")

    p_replace = sub.add_parser("template-replace", help="Replace template text using a JSON mapping")
    p_replace.add_argument("input")
    p_replace.add_argument("output")
    p_replace.add_argument("--map", required=True)

    p_delete = sub.add_parser("template-delete", help="Delete slides from a PPTX")
    p_delete.add_argument("input")
    p_delete.add_argument("output")
    p_delete.add_argument("--slides", required=True, help="Comma-separated slide numbers")

    p_reorder = sub.add_parser("template-reorder", help="Reorder slides in a PPTX")
    p_reorder.add_argument("input")
    p_reorder.add_argument("output")
    p_reorder.add_argument("--order", required=True, help="Comma-separated full slide order")

    p_duplicate = sub.add_parser("template-duplicate", help="Duplicate one slide")
    p_duplicate.add_argument("input")
    p_duplicate.add_argument("output")
    p_duplicate.add_argument("--slide", type=int, required=True)

    p_fill = sub.add_parser(
        "template-fill",
        help="Fill a mandated PPTX template from Markdown without redesigning it",
    )
    p_fill.add_argument("template", help="School/organization .pptx template")
    p_fill.add_argument("--content", required=True, help="Thesis/content Markdown file")
    p_fill.add_argument("-o", "--output", default=None,
                        help="Output PPTX path (default: <template-stem>-filled.pptx in cwd)")
    p_fill.add_argument("--map", default=None,
                        help='JSON per-slide replacement overrides: {"3": {"old": "new"}}')

    p_plan = sub.add_parser("plan", help="Generate a structured slide plan from Markdown (review before generating)")
    p_plan.add_argument("source", help="Source Markdown file")
    p_plan.add_argument("--domain", default="general", choices=["teaching", "course", "competition", "general"],
                        help="Content domain for layout/density decisions")
    p_plan.add_argument("--max-items", type=int, default=6, help="Max content items per slide")
    p_plan.add_argument("--pinyin", action="store_true", help="Show pinyin annotations (teaching domain)")
    p_plan.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON instead of markdown table")
    p_plan.add_argument("--max-slides", type=int, default=20, help="Maximum number of slides")
    p_plan.add_argument("--planner", default="deterministic", choices=["auto", "deterministic", "ai"],
                        help="Planning engine: deterministic heuristics or AI strategist. auto picks AI only when a key is configured.")
    _add_ai_args(p_plan)

    p_quick = sub.add_parser("quickstart", help="Run source-to-PPTX pipeline end-to-end")
    p_quick.add_argument("source")
    p_quick.add_argument("--name")
    p_quick.add_argument("--format", default="ppt169")
    p_quick.add_argument("--base", default="projects")
    p_quick.add_argument("--theme", default="dark-tech", help="Visual theme name")
    p_quick.add_argument("--competition", default=None, help="Competition template")
    p_quick.add_argument("--mode", default="auto", choices=["auto", "ai", "fast", "template-smoke", "quick"],
                         help="auto (default): AI generation when an API key is configured, deterministic fast templates otherwise. "
                              "ai: per-page LLM authoring (requires OPENAI_API_KEY or --ai-api-key). "
                              "fast: deterministic theme templates, ~2s, no API key. "
                              "template-smoke/quick: legacy aliases for fast.")
    p_quick.add_argument("--planner", default="auto", choices=["auto", "deterministic", "ai"],
                         help="Planning engine: auto uses AI planner in AI mode and deterministic planner in fast mode.")
    p_quick.add_argument("--lenient-quality", action="store_true",
                         help="Allow design-quality warnings in AI quickstart. Not recommended for deliverable decks.")
    _add_ai_args(p_quick)

    p_build = sub.add_parser("build", help="Plan-driven source-to-PPTX (v3 pipeline with domain awareness)")
    p_build.add_argument("source")
    p_build.add_argument("--name", default=None)
    p_build.add_argument("--format", default="ppt169")
    p_build.add_argument("--base", default="projects")
    p_build.add_argument("--theme", default="dark-tech", help="Visual theme name")
    p_build.add_argument("--domain", default="general", choices=["teaching", "course", "competition", "general"],
                         help="Content domain for layout/density decisions")
    p_build.add_argument("--max-items", type=int, default=6, help="Max content items per slide")
    p_build.add_argument("--pinyin", action="store_true", help="Show pinyin annotations (teaching domain)")
    p_build.add_argument("--max-slides", type=int, default=20, help="Maximum number of slides")
    p_build.add_argument("--mode", default="auto", choices=["auto", "ai", "fast", "template-smoke", "quick"],
                         help="auto (default): AI generation when an API key is configured, deterministic fast templates otherwise. "
                              "ai: per-page LLM authoring (requires OPENAI_API_KEY or --ai-api-key). "
                              "fast: deterministic theme templates, ~2s, no API key. "
                              "template-smoke/quick: legacy aliases for fast.")
    p_build.add_argument("--planner", default="auto", choices=["auto", "deterministic", "ai"],
                         help="Planning engine: auto uses AI planner in AI mode and deterministic planner in fast mode.")
    p_build.add_argument("--skip-confirm", action="store_true", help="Skip confirmation gate check")
    _add_ai_args(p_build)

    p_preview = sub.add_parser("preview", help="Build deck with plan + open instant HTML preview in browser")
    p_preview.add_argument("source")
    p_preview.add_argument("--name", default=None)
    p_preview.add_argument("--format", default="ppt169")
    p_preview.add_argument("--base", default="projects")
    p_preview.add_argument("--theme", default="dark-tech", help="Visual theme name")
    p_preview.add_argument("--domain", default="general", choices=["teaching", "course", "competition", "general"],
                           help="Content domain for layout/density decisions")
    p_preview.add_argument("--max-items", type=int, default=6, help="Max content items per slide")
    p_preview.add_argument("--pinyin", action="store_true", help="Show pinyin annotations (teaching domain)")
    p_preview.add_argument("--max-slides", type=int, default=20, help="Maximum number of slides")
    p_preview.add_argument("--no-open", action="store_true", help="Don't auto-open browser")

    p_adjust = sub.add_parser("adjust", help="Regenerate a specific slide in an existing project")
    p_adjust.add_argument("project", help="Path to existing project directory")
    p_adjust.add_argument("slide", type=int, help="Slide number to regenerate (1-based)")
    p_adjust.add_argument("--title", default=None, help="New title for the slide")
    p_adjust.add_argument("--body", default=None, help="New body content for the slide (Markdown)")
    p_adjust.add_argument("--layout", default=None, help="Force a specific layout (e.g. vocab-card, dialogue, bullet-list)")
    p_adjust.add_argument("--body-file", default=None, help="Read body content from a file instead of --body")

    p_repair = sub.add_parser("repair-slide", help="Regenerate one slide with AI using QA and visual feedback")
    p_repair.add_argument("project", help="Path to existing project directory")
    p_repair.add_argument("slide", type=int, help="Slide number to regenerate (1-based)")
    p_repair.add_argument("--title", default=None, help="Replacement title; defaults to existing SVG text")
    p_repair.add_argument("--body", default=None, help="Replacement body content; defaults to existing SVG text")
    p_repair.add_argument("--body-file", default=None, help="Read replacement body content from a file")
    p_repair.add_argument("--layout", default=None, help="Layout hint for the repaired slide")
    _add_ai_args(p_repair)

    p_repair_feedback = sub.add_parser("repair-feedback", help="Repair all slides flagged by qa/visual-feedback.json")
    p_repair_feedback.add_argument("project", help="Path to existing project directory")
    p_repair_feedback.add_argument("--slides", default=None, help="Comma-separated slide numbers to repair; defaults to non-ok visual feedback")
    p_repair_feedback.add_argument("--min-severity", default="minor", choices=["minor", "major", "critical"],
                                   help="Minimum visual feedback severity to repair (default: minor)")
    p_repair_feedback.add_argument("--layout", default=None, help="Layout hint for repaired slides")
    _add_ai_args(p_repair_feedback)

    p_iterate_ai = sub.add_parser("iterate-ai", help="Run export/render/visual-critic/repair loop")
    p_iterate_ai.add_argument("project", help="Path to existing project directory")
    p_iterate_ai.add_argument("--rounds", type=int, default=1, help="Number of visual repair rounds (default: 1)")
    p_iterate_ai.add_argument("--pptx", default=None, help="Optional existing PPTX for the first render")
    p_iterate_ai.add_argument("--dpi", type=int, default=150, help="Render DPI (default: 150)")
    p_iterate_ai.add_argument("--min-severity", default="minor", choices=["minor", "major", "critical"],
                              help="Minimum visual feedback severity to repair (default: minor)")
    p_iterate_ai.add_argument("--strict-qa", action="store_true", help="Run strict QA after the final export")
    p_iterate_ai.add_argument("--require-visual-ok", action="store_true",
                              help="Fail unless the final AI visual feedback severity is ok")
    _add_ai_args(p_iterate_ai)

    p_ai_trace = sub.add_parser("ai-trace", help="Show a readable summary of planner/executor/visual-critic interactions")
    p_ai_trace.add_argument("project", help="Project directory containing qa/ai-trace.jsonl")
    p_ai_trace.add_argument("--json", action="store_true", dest="as_json", help="Print raw trace events as formatted JSON")
    p_ai_trace.add_argument("--diagnose", action="store_true", help="Print actionable diagnosis for failed or incomplete AI interactions")
    p_ai_trace.add_argument("--latest-iteration", action="store_true",
                            help="Scope summary/diagnosis/json to qa/AI-ITERATION.json trace_start")
    p_ai_trace.add_argument("--event", type=int, default=None, help="Show a full sidecar for one 1-based trace event")
    p_ai_trace.add_argument("--part", default="prompt", choices=["prompt", "raw", "request"],
                            help="Sidecar to show with --event: prompt, raw, or request (default: prompt)")
    p_ai_trace.add_argument("--bundle", default=None,
                            help="Write a zip bundle with trace sidecars and AI QA reports")

    p_ai_smoke = sub.add_parser("ai-smoke", help="Run a persistent one-slide live LLM planner/executor smoke test")
    p_ai_smoke.add_argument("--source", default=None, help="Optional Markdown source; defaults to a built-in one-slide sample")
    p_ai_smoke.add_argument("--name", default="ai-smoke", help="Project name (default: ai-smoke)")
    p_ai_smoke.add_argument("--base", default="test-output/live-llm", help="Project base directory")
    p_ai_smoke.add_argument("--format", default="ppt169")
    p_ai_smoke.add_argument("--theme", default="dark-tech", help="Visual theme name")
    p_ai_smoke.add_argument("--max-slides", type=int, default=1, help="Maximum slides for the smoke run")
    p_ai_smoke.add_argument("--max-items", type=int, default=4, help="Maximum items per slide")
    p_ai_smoke.add_argument("--visual-critic", action="store_true",
                            help="Also render the smoke deck and run the AI visual critic")
    p_ai_smoke.add_argument("--require-visual-ok", action="store_true",
                            help="With --visual-critic, fail unless the AI visual feedback severity is ok")
    p_ai_smoke.add_argument("--rendered-dir", default=None,
                            help="Use existing rendered images for --visual-critic instead of rendering the PPTX")
    p_ai_smoke.add_argument("--require-pptx-render", action="store_true",
                            help="With --visual-critic, fail unless evidence is rendered from the exported PPTX")
    p_ai_smoke.add_argument("--dpi", type=int, default=150, help="Render DPI when --visual-critic is used (default: 150)")
    _add_ai_args(p_ai_smoke)

    p_ai_release = sub.add_parser("ai-release-check", help="Run provider preflight plus strict live LLM visual smoke for release gating")
    p_ai_release.add_argument("--source", default=None, help="Optional Markdown source; defaults to the built-in one-slide release sample")
    p_ai_release.add_argument("--name", default="ai-release-check", help="Project name (default: ai-release-check)")
    p_ai_release.add_argument("--base", default="test-output/live-llm", help="Project base directory")
    p_ai_release.add_argument("--format", default="ppt169")
    p_ai_release.add_argument("--theme", default="dark-tech", help="Visual theme name")
    p_ai_release.add_argument("--max-slides", type=int, default=1, help="Maximum slides for the release smoke run")
    p_ai_release.add_argument("--max-items", type=int, default=4, help="Maximum items per slide")
    p_ai_release.add_argument("--rendered-dir", default=None,
                              help="Use existing rendered images instead of rendering the PPTX")
    p_ai_release.add_argument("--require-pptx-render", action="store_true",
                              help="Fail unless visual evidence is rendered from the exported PPTX")
    p_ai_release.add_argument("--dpi", type=int, default=150, help="Render DPI (default: 150)")
    p_ai_release.add_argument("--repair-rounds", type=int, default=2,
                              help="Visual repair rounds to run when strict smoke is repairable (default: 2)")
    _add_ai_args(p_ai_release)

    p_ai_smoke_summary = sub.add_parser("ai-smoke-summary", help="Summarize one or more qa/AI-SMOKE.json results")
    p_ai_smoke_summary.add_argument("projects", nargs="+", help="Project directories or AI-SMOKE.json files")
    p_ai_smoke_summary.add_argument("--json", action="store_true", dest="as_json", help="Print normalized smoke results as JSON")

    p_ai_iteration_summary = sub.add_parser("ai-iteration-summary", help="Summarize one or more qa/AI-ITERATION.json results")
    p_ai_iteration_summary.add_argument("projects", nargs="+", help="Project directories or AI-ITERATION.json files")
    p_ai_iteration_summary.add_argument("--json", action="store_true", dest="as_json", help="Print normalized iteration results as JSON")

    p_ai_release_summary = sub.add_parser("ai-release-summary", help="Summarize one or more qa/AI-RELEASE-CHECK.json results")
    p_ai_release_summary.add_argument("projects", nargs="+", help="Project directories or AI-RELEASE-CHECK.json files")
    p_ai_release_summary.add_argument("--json", action="store_true", dest="as_json", help="Print normalized release-check results as JSON")

    p_ai_doctor = sub.add_parser("ai-doctor", help="Preflight OpenAI-compatible planner/executor/vision provider access")
    p_ai_doctor.add_argument("--check-vision", action="store_true", help="Also send a tiny image-input request to the vision model")
    _add_ai_args(p_ai_doctor)

    p_narrate = sub.add_parser("narrate", help="Generate TTS audio from speaker notes")
    p_narrate.add_argument("project")
    p_narrate.add_argument("--voice", default=None, help="Voice name (engine-specific)")
    p_narrate.add_argument("--engine", default="edge-tts", choices=["edge-tts", "mimo"], help="TTS engine")
    p_narrate.add_argument("--style", default="", help="MiMo: natural language style instruction")
    p_narrate.add_argument("--voice-clone", default=None, help="MiMo: path to mp3/wav sample for voice cloning")
    p_narrate.add_argument("--voice-design", default=None, help="MiMo: text description for voice design")

    p_voices = sub.add_parser("voices", help="List available TTS voices")
    p_voices.add_argument("--locale", default="")
    p_voices.add_argument("--engine", default="edge-tts", choices=["edge-tts", "mimo"], help="TTS engine")

    sub.add_parser("formats", help="List available canvas format presets")
    sub.add_parser("themes", help="List available visual design themes")
    sub.add_parser("competitions", help="List available competition templates")

    p_templates = sub.add_parser(
        "templates",
        help="List 80 named slide templates across 10 categories (business / pitch / "
             "product / report / education / academic / marketing / government / tech / training)",
    )
    p_templates.add_argument(
        "--category", default=None,
        help="Filter to one category slug (e.g. business, pitch, product, ...). "
             "Omit to list every template grouped by category.",
    )
    p_templates.add_argument(
        "--show", default=None,
        help="Show full details (theme, layouts, sample outline) for one template slug.",
    )

    p_tquick = sub.add_parser(
        "template-quickstart",
        help="Scaffold a deck from a named template — creates project + sample outline.",
    )
    p_tquick.add_argument("slug", help="Template slug, e.g. biz-mck-strategy")
    p_tquick.add_argument("--name", default=None, help="Project name (defaults to template slug)")
    p_tquick.add_argument("--title", default=None, help="Deck title (defaults to template name)")
    p_tquick.add_argument("--format", default="ppt169")
    p_tquick.add_argument("--base", default="projects")
    p_tquick.add_argument("--overwrite", action="store_true")

    p_theme = sub.add_parser("theme", help="Manage user-installed theme plugins")
    theme_sub = p_theme.add_subparsers(dest="theme_command", required=True)
    p_theme_add = theme_sub.add_parser("add", help="Install a TOML theme file into ~/.config/slide-skill/themes/")
    p_theme_add.add_argument("path", help="Path to a TOML theme file")
    p_theme_add.add_argument("--overwrite", action="store_true")
    p_theme_remove = theme_sub.add_parser("remove", help="Delete a user-installed theme")
    p_theme_remove.add_argument("name")
    theme_sub.add_parser("list", help="List all available themes with their source")

    p_rehearse = sub.add_parser("rehearse", help="Estimate presentation timing from speaker notes")
    p_rehearse.add_argument("project")
    p_rehearse.add_argument("--time-limit", type=float, default=None, help="Time limit in minutes")

    p_draft = sub.add_parser("draft-notes", help="Generate speaker note drafts from slide content")
    p_draft.add_argument("project")
    p_draft.add_argument("--overwrite", action="store_true", help="Overwrite existing notes")

    p_html = sub.add_parser("html-preview", help="Render a self-contained HTML presenter from svg_final/")
    p_html.add_argument("project")
    p_html.add_argument("-o", "--output", default=None, help="Output .html path (default: <project>/exports/preview.html)")
    p_html.add_argument("--title", default="Slide Preview")
    p_html.add_argument("--lang", default=None, help="ISO language code; defaults to spec_lock.json lang or 'en'")

    p_pf = sub.add_parser("font-preflight", help="Scan deck text for missing-glyph / RTL handling issues")
    p_pf.add_argument("project")
    p_pf.add_argument("--theme", default=None, help="Theme name; defaults to spec_lock.json theme")
    p_pf.add_argument("--lang", default=None, help="Force language code (else autodetected)")

    p_bench = sub.add_parser(
        "benchmark-briefs",
        help="Run the six-family composition benchmark (dry-run by default; --yes gates the provider run)",
    )
    p_bench.add_argument("--briefs-dir", default="benchmarks/briefs",
                         help="Directory with the six family brief files (default: benchmarks/briefs)")
    p_bench.add_argument("--out", default="benchmarks",
                         help="Output directory for manifest + evidence (default: benchmarks)")
    p_bench.add_argument("--theme", default="dark-tech",
                         help="Single theme across all six briefs (default: dark-tech)")
    p_bench.add_argument("--yes", action="store_true",
                         help="Gated provider run: 6 briefs, serial, one provider key; "
                              "atomically replaces benchmarks/six-family-manifest.json")
    p_bench.add_argument("--dry-run", action="store_true",
                         help="Explicit dry-run alias (validate briefs + classifier self-test, no provider call)")
    p_bench.add_argument("--base", default=None,
                         help="Scratch base directory for benchmark projects (default: temp dir)")

    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init":
        if getattr(args, "from_example", False) and not args.competition:
            print("error: --from-example requires --competition <slug>. Run 'slide-skill competitions' for slugs.", file=sys.stderr)
            return 1
        project = init_project(args.name, args.format, args.base, args.overwrite, competition=args.competition)
        print(project)
        if getattr(args, "from_example", False):
            from .competition import scaffold_from_example
            info = scaffold_from_example(project, args.competition)
            print(f"source:  {info['source']}  (示例内容，改成你自己的)")
            if info["notes"]:
                print(f"notes:   {info['notes']}  (演讲备注，导出时自动嵌入 PPTX)")
            print("next:    1. 编辑 source.md，替换为你的内容")
            print(f"         2. slide-skill quickstart {info['source']} --theme {info['theme']} --name {args.name} --mode fast")
    elif args.command == "import-sources":
        paths = import_sources(args.project, [Path(item) for item in args.sources], move=args.move)
        print("\n".join(str(path) for path in paths))
    elif args.command == "validate":
        ok, errors = validate_project(args.project)
        print("valid" if ok else "invalid")
        for error in errors:
            print(f"- {error}")
        return 0 if ok else 1
    elif args.command == "source-to-md":
        markdown = url_to_markdown(args.source, args.output) if args.url else convert_file(args.source, args.output)
        if not args.output:
            print(markdown)
    elif args.command == "spec":
        theme = getattr(args, "theme", "dark-tech") or "dark-tech"
        spec, lock = create_spec(args.project, args.source, args.title, theme_name=theme)
        print(spec)
        print(lock)
    elif args.command == "generate-guide":
        theme = getattr(args, "theme", None)
        prompt = generate_guide(args.project, args.source, theme_name=theme or "dark-tech", max_slides=args.max_slides)
        print(prompt)
    elif args.command == "svg":
        for path in generate_svg(args.project, args.source, args.max_slides):
            print(path)
    elif args.command == "confirm":
        from .confirm_dialogue import run_auto_derive, run_interactive
        project = Path(args.project)
        if not project.is_dir():
            print(f"error: {project} is not a directory", file=sys.stderr)
            return 1
        if args.auto:
            result = run_auto_derive(project)
            print("Auto-derived confirmations:")
        else:
            result = run_interactive(project)
            print("\nConfirmations saved.")
        for key, val in result.items():
            print(f"  {key}: {val}")
    elif args.command == "check-svg":
        report = write_svg_report(args.project, args.stage, quality=args.quality)
        print(report)
        txt = report.read_text(encoding="utf-8")
        return 0 if "✅ passed" in txt or "status: passed" in txt else 1
    elif args.command == "finalize-svg":
        for path in finalize_svg(args.project, quality=args.quality):
            print(path)
    elif args.command == "export":
        print(export_project(args.project, args.output, args.stage, com_smoke=args.com_smoke))
    elif args.command == "qa":
        ok, report = run_qa(
            args.project,
            args.pptx,
            require_visual=args.strict or args.require_visual,
            require_fix_verify=args.strict or args.require_fix_verify,
            strict_svg_quality=args.strict,
        )
        print(report)
        return 0 if ok else 1
    elif args.command == "render":
        for path in render_pptx(args.pptx, args.output_dir, args.dpi):
            print(path)
    elif args.command == "visual-critic":
        if not _require_ai_access(args, force=True):
            return 1
        from .visual_critic import generate_visual_feedback
        slides = _numbers(args.slides) if args.slides else None
        project = Path(args.project)
        try:
            json_path, md_path = generate_visual_feedback(
                project,
                rendered_dir=args.rendered_dir,
                slides=slides,
                **_vision_kwargs_from_args(args),
            )
        except _AI_COMMAND_ERRORS as exc:
            _report_ai_command_failure(project, exc)
            return 1
        print(f"visual-feedback: {json_path}")
        print(f"visual-review: {md_path}")
    elif args.command == "pdf":
        from .pdf_export import export_pdf
        out = export_pdf(args.input, args.output, backend=args.backend, quality=args.quality)
        print(out)
    elif args.command == "render-doctor":
        print(render_environment_report(), end="")
    elif args.command == "pptx-text":
        print(pptx_text(args.pptx))
    elif args.command == "pptx-notes":
        print(pptx_notes(args.pptx))
    elif args.command == "validate-pptx":
        ok, errors = validate_pptx(args.pptx)
        print("valid" if ok else "invalid")
        for error in errors:
            print(f"- {error}")
        return 0 if ok else 1
    elif args.command == "template-inspect":
        import json
        print(json.dumps(inspect_template(args.pptx), ensure_ascii=False, indent=2))
    elif args.command == "template-replace":
        print(replace_text(args.input, args.output, replacements_from_json(args.map)))
    elif args.command == "template-delete":
        print(delete_slides(args.input, args.output, _numbers(args.slides)))
    elif args.command == "template-reorder":
        print(reorder_slides(args.input, args.output, _numbers(args.order)))
    elif args.command == "template-duplicate":
        print(duplicate_slide(args.input, args.output, args.slide))
    elif args.command == "template-fill":
        from .template_fill import fill_template

        template = Path(args.template)
        output = Path(args.output) if args.output else Path.cwd() / f"{template.stem}-filled.pptx"
        try:
            result = fill_template(template, args.content, output, mapping_json=args.map)
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(result.output)
        print(result.report_path)
        print(f"verdict: {result.verdict}")
    elif args.command == "plan":
        import json as _json
        from .content_planner import ContentConfig, plan_to_json, plan_to_markdown
        if _resolve_planner_mode(args) == "ai" and not _require_ai_access(args):
            return 1
        source_text = Path(args.source).read_text(encoding="utf-8")
        cfg = ContentConfig(
            domain=args.domain,
            max_items_per_slide=args.max_items,
            show_pinyin=args.pinyin,
            max_slides=args.max_slides,
        )
        plans = _plan_source_slides(source_text, cfg, args=args)
        if args.as_json:
            print(_json.dumps(plan_to_json(plans), ensure_ascii=False, indent=2))
        else:
            print(plan_to_markdown(plans))
    elif args.command == "quickstart":
        from .content_planner import ContentConfig
        if not _require_ai_access(args):
            return 1
        name = args.name or Path(args.source).stem
        theme = getattr(args, "theme", "dark-tech") or "dark-tech"
        mode = _resolve_generation_mode(args)
        if getattr(args, "mode", None) in (None, "auto") and mode == "fast":
            print("mode: fast (no API key detected; set OPENAI_API_KEY for AI-authored slides)", file=sys.stderr)
        project = init_project(name, args.format, args.base, overwrite=True, competition=args.competition)
        source_md = project / "sources" / (Path(args.source).stem + ".md")
        convert_file(args.source, source_md)
        original = Path(args.source)
        if original.resolve() != source_md.resolve():
            dest_original = project / "sources" / original.name
            if not dest_original.exists():
                shutil.copy2(original, dest_original)
        create_spec(project, source_md, theme_name=theme)
        source_text = source_md.read_text(encoding="utf-8")
        comp = getattr(args, "competition", None)
        cfg = ContentConfig(
            domain="competition" if comp else "general",
            competition_name=comp,
        )
        try:
            plans = _plan_source_slides(source_text, cfg, project=project, args=args)
        except _AI_COMMAND_ERRORS as exc:
            _report_ai_command_failure(project, exc)
            return 1

        if mode == "ai":
            from .ai_executor import generate_svg_with_ai
            try:
                generate_svg_with_ai(
                    project,
                    plans,
                    strict_quality=not args.lenient_quality,
                    **_executor_kwargs_from_args(args),
                )
            except _AI_COMMAND_ERRORS as exc:
                _report_ai_command_failure(project, exc)
                return 1
        else:
            generate_svg_from_plan(project, plans)

        write_svg_report(project, quality=(mode == "ai"))
        finalize_svg(project, quality=(mode == "ai" and not args.lenient_quality))
        deck = export_project(project)
        ok, report = run_qa(project, deck, strict_svg_quality=(mode == "ai" and not args.lenient_quality))
        print(f"project: {project}")
        print(f"deck: {deck}")
        print(f"qa: {report}")
        return 0 if ok else 1
    elif args.command == "build":
        from .content_planner import ContentConfig, plan_to_markdown
        if not _require_ai_access(args):
            return 1
        mode = _resolve_generation_mode(args)
        if getattr(args, "mode", None) in (None, "auto") and mode == "fast":
            print("mode: fast (no API key detected; set OPENAI_API_KEY for AI-authored slides)", file=sys.stderr)
        name = args.name or Path(args.source).stem
        theme = getattr(args, "theme", "dark-tech") or "dark-tech"
        project = init_project(name, args.format, args.base, overwrite=True)
        # Read and convert source
        source_md = project / "sources" / (Path(args.source).stem + ".md")
        convert_file(args.source, source_md)
        original = Path(args.source)
        if original.resolve() != source_md.resolve():
            dest_original = project / "sources" / original.name
            if not dest_original.exists():
                shutil.copy2(original, dest_original)
        create_spec(project, source_md, theme_name=theme)
        # Plan slides with domain awareness
        source_text = source_md.read_text(encoding="utf-8")
        cfg = ContentConfig(
            domain=args.domain,
            max_items_per_slide=args.max_items,
            show_pinyin=args.pinyin,
            max_slides=args.max_slides,
        )
        try:
            plans = _plan_source_slides(source_text, cfg, project=project, args=args)
        except _AI_COMMAND_ERRORS as exc:
            _report_ai_command_failure(project, exc)
            return 1
        # Show plan summary
        print(plan_to_markdown(plans))
        print()
        # Confirmation gate
        if not getattr(args, "skip_confirm", False):
            from .confirmations import check_confirmations
            complete, missing = check_confirmations(project)
            if not complete:
                print(f"Confirmations incomplete. Missing: {', '.join(missing)}", file=sys.stderr)
                print("Run 'slide confirm <project>' first, or use --skip-confirm.", file=sys.stderr)
                return 1
        # Render from plan: ai (LLM per-page) or fast (deterministic templates).
        if mode == "ai":
            from .ai_executor import generate_svg_with_ai
            try:
                generate_svg_with_ai(project, plans, **_executor_kwargs_from_args(args))
            except _AI_COMMAND_ERRORS as exc:
                _report_ai_command_failure(project, exc)
                return 1
        else:
            generate_svg_from_plan(project, plans)
        write_svg_report(project, quality=(mode == "ai"))
        finalize_svg(project, quality=(mode == "ai"))
        deck = export_project(project)
        ok, report = run_qa(project, deck, strict_svg_quality=(mode == "ai"))
        print(f"project: {project}")
        print(f"deck: {deck}")
        print(f"qa: {report}")
        return 0 if ok else 1
    elif args.command == "preview":
        import webbrowser
        from .content_planner import ContentConfig, plan_slides, plan_to_markdown

        from .html_preview import write_preview_html
        name = args.name or Path(args.source).stem
        theme = getattr(args, "theme", "dark-tech") or "dark-tech"
        project = init_project(name, args.format, args.base, overwrite=True)
        source_md = project / "sources" / (Path(args.source).stem + ".md")
        convert_file(args.source, source_md)
        original = Path(args.source)
        if original.resolve() != source_md.resolve():
            dest_original = project / "sources" / original.name
            if not dest_original.exists():
                shutil.copy2(original, dest_original)
        create_spec(project, source_md, theme_name=theme)
        source_text = source_md.read_text(encoding="utf-8")
        cfg = ContentConfig(
            domain=args.domain,
            max_items_per_slide=args.max_items,
            show_pinyin=args.pinyin,
            max_slides=args.max_slides,
        )
        plans = plan_slides(source_text, cfg)
        print(plan_to_markdown(plans))
        print()
        generate_svg_from_plan(project, plans)
        write_svg_report(project)
        finalize_svg(project)
        # Generate HTML preview
        lock_path = project / "spec_lock.json"
        lang = "en"
        preview_title = name
        if lock_path.exists():
            import json as _json
            lock = _json.loads(lock_path.read_text(encoding="utf-8"))
            lang = lock.get("lang", "en")
            preview_title = lock.get("title", name)
        html_out = project / "exports" / "preview.html"
        write_preview_html(project, html_out, title=preview_title, lang=lang)
        print(f"project: {project}")
        print(f"preview: {html_out}")
        if not args.no_open:
            webbrowser.open(html_out.as_uri())
        return 0
    elif args.command == "adjust":
        import json as _json
        from .svg_pipeline import _render_slide_svg
        project = Path(args.project)
        if not project.exists():
            print(f"error: project not found: {project}", file=sys.stderr)
            return 1
        lock_path = project / "spec_lock.json"
        if not lock_path.exists():
            print(f"error: no spec_lock.json in {project}", file=sys.stderr)
            return 1
        spec_lock = _json.loads(lock_path.read_text(encoding="utf-8"))
        slide_idx = args.slide
        svg_dir = project / "svg_output"
        svg_file = svg_dir / f"slide_{slide_idx:02d}.svg"
        if not svg_file.exists():
            print(f"error: slide {slide_idx} not found ({svg_file})", file=sys.stderr)
            return 1
        # Count total slides
        total = len(list(svg_dir.glob("*.svg")))
        # Get body content
        body = ""
        if args.body_file:
            body = Path(args.body_file).read_text(encoding="utf-8")
        elif args.body:
            body = args.body
        # Get title
        title = args.title or f"Slide {slide_idx}"
        layout = args.layout
        # Regenerate
        svg = _render_slide_svg(
            slide_idx, title, body, spec_lock, total,
            layout=layout,
        )
        svg_file.write_text(svg, encoding="utf-8")
        # Also update svg_final
        final_file = project / "svg_final" / f"slide_{slide_idx:02d}.svg"
        if final_file.parent.exists():
            final_file.write_text(svg, encoding="utf-8")
        print(f"adjusted: {svg_file}")
        print(f"Re-run `slide-skill html-preview {project}` to refresh the preview.")
        return 0
    elif args.command == "repair-slide":
        if not _require_ai_access(args, force=True):
            return 1
        from .content_planner import ContentItem, SlidePlan
        from .ai_executor import generate_svg_with_ai

        project = Path(args.project)
        if not project.exists():
            print(f"error: project not found: {project}", file=sys.stderr)
            return 1
        if not (project / "spec_lock.json").exists():
            print(f"error: no spec_lock.json in {project}", file=sys.stderr)
            return 1

        plan = _repair_plan_from_existing_slide(project, args.slide, layout=args.layout)
        if args.title or args.body or args.body_file:
            current_svg = _existing_slide_svg(project, args.slide)
            existing_lines = _extract_svg_text_lines(current_svg) if current_svg else []
            title = args.title or (existing_lines[0] if existing_lines else f"Slide {args.slide}")
            body = _repair_body_from_args(args)
            if body is None:
                body = "\n".join(existing_lines[1:]).strip()
            items = _content_items_from_body(body)
            if not items:
                items = [ContentItem(type="text", primary="Preserve the current slide content while fixing visual feedback.")]
            plan = SlidePlan(
                index=args.slide,
                layout=args.layout or plan.layout or "bullet-list",
                title=title,
                items=items,
                rhythm=plan.rhythm or "breathing",
                visual_strategy=plan.visual_strategy or "visual-repair",
                layout_pattern=plan.layout_pattern,
                notes="Repair this slide using QA feedback and rendered visual review observations.",
            )
        try:
            paths = generate_svg_with_ai(project, [plan], clear_output=False, **_executor_kwargs_from_args(args))
        except _AI_COMMAND_ERRORS as exc:
            _report_ai_command_failure(project, exc)
            return 1
        generated = paths[0]
        final_file = project / "svg_final" / generated.name
        if final_file.parent.exists():
            shutil.copy2(generated, final_file)
        print(f"repaired: {generated}")
        if final_file.exists():
            print(f"updated-final: {final_file}")
        print(f"feedback sources: {project / 'qa' / 'VISUAL-REVIEW.md'} ; {project / 'qa' / 'visual-feedback.json'}")
        return 0
    elif args.command == "repair-feedback":
        if not _require_ai_access(args, force=True):
            return 1
        project = Path(args.project)
        if not project.exists():
            print(f"error: project not found: {project}", file=sys.stderr)
            return 1
        if not (project / "spec_lock.json").exists():
            print(f"error: no spec_lock.json in {project}", file=sys.stderr)
            return 1

        requested = _numbers(args.slides) if args.slides else None
        try:
            repaired = _repair_feedback_project(
                project,
                ai_kwargs=_executor_kwargs_from_args(args),
                slide_indexes=requested,
                min_severity=args.min_severity,
                layout=args.layout,
            )
        except _AI_COMMAND_ERRORS as exc:
            _report_ai_command_failure(project, exc)
            return 1
        if not repaired:
            print("No slides require repair from visual feedback.")
            return 0
        for generated, final_file in repaired:
            print(f"repaired: {generated}")
            if final_file.exists():
                print(f"updated-final: {final_file}")
        return 0
    elif args.command == "iterate-ai":
        if not _require_ai_access(args, force=True):
            return 1
        project = Path(args.project)
        if not project.exists():
            print(f"error: project not found: {project}", file=sys.stderr)
            return 1
        try:
            deck, report = _run_ai_iteration_loop(
                project,
                rounds=args.rounds,
                first_pptx=Path(args.pptx) if args.pptx else None,
                dpi=args.dpi,
                min_severity=args.min_severity,
                strict_qa=args.strict_qa,
                require_visual_ok=args.require_visual_ok,
                executor_kwargs=_executor_kwargs_from_args(args),
                vision_kwargs=_vision_kwargs_from_args(args),
            )
        except _AI_COMMAND_ERRORS as exc:
            _report_ai_command_failure(project, exc)
            return 1
        print(f"deck: {deck}")
        print(f"qa: {report}")
        return 0
    elif args.command == "ai-trace":
        from .ai_trace import (
            diagnose_ai_trace,
            latest_iteration_trace_scope,
            read_ai_trace,
            read_ai_trace_part,
            summarize_ai_trace,
            write_ai_trace_bundle,
        )
        project = Path(args.project)
        if not project.exists():
            print(f"error: project not found: {project}", file=sys.stderr)
            return 1
        try:
            if args.bundle:
                if args.latest_iteration:
                    events, start_index, label, _iteration_result = latest_iteration_trace_scope(project)
                    bundle_path = write_ai_trace_bundle(project, args.bundle, events, start_index=start_index, scope_label=label)
                else:
                    bundle_path = write_ai_trace_bundle(project, args.bundle)
                print(bundle_path)
            elif args.event is not None:
                print(read_ai_trace_part(project, args.event, args.part), end="")
            elif args.diagnose:
                if args.latest_iteration:
                    events, start_index, label, iteration_result = latest_iteration_trace_scope(project)
                    print(diagnose_ai_trace(
                        project,
                        events,
                        start_index=start_index,
                        scope_label=label,
                        iteration_result=iteration_result,
                    ))
                else:
                    print(diagnose_ai_trace(project))
            elif args.as_json:
                import json as _json
                events = latest_iteration_trace_scope(project)[0] if args.latest_iteration else read_ai_trace(project)
                print(_json.dumps(events, ensure_ascii=False, indent=2))
            else:
                if args.latest_iteration:
                    events, start_index, label, _iteration_result = latest_iteration_trace_scope(project)
                    print(summarize_ai_trace(project, events, start_index=start_index, scope_label=label))
                else:
                    print(summarize_ai_trace(project))
        except (FileNotFoundError, ValueError, IndexError, OSError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0
    elif args.command == "ai-smoke":
        if not _require_ai_access(args, force=True):
            return 1
        project = Path(args.base) / _validate_project_name(args.name)
        try:
            project, deck, report = _run_ai_smoke(args)
        except _AI_COMMAND_ERRORS as exc:
            try:
                smoke_path = project / "qa" / "AI-SMOKE.json"
                if not smoke_path.exists():
                    smoke_path = _write_ai_smoke_result(project, None, None, args, status="failed", error=str(exc))
                print(f"smoke: {smoke_path}", file=sys.stderr)
            except Exception:  # noqa: BLE001 - failure reporting must not hide the original AI error.
                pass
            _report_ai_command_failure(project, exc)
            return 1
        from .ai_trace import summarize_ai_trace
        print(f"project: {project}")
        print(f"deck: {deck}")
        print(f"qa: {report}")
        print(f"smoke: {project / 'qa' / 'AI-SMOKE.json'}")
        print("trace:")
        print(summarize_ai_trace(project))
        return 0
    elif args.command == "ai-release-check":
        if not _ai_access_configured(args):
            print(
                "error: AI release check requires model access. Set OPENAI_API_KEY, "
                "pass --ai-api-key, or pass --ai-base-url for a local OpenAI-compatible server.",
                file=sys.stderr,
            )
            return 1
        project = Path(args.base) / _validate_project_name(args.name)
        try:
            result_path = _run_ai_release_check(args)
        except _AI_COMMAND_ERRORS as exc:
            _report_ai_command_failure(project, exc)
            return 1
        print(f"release-check: {result_path}")
        print((result_path.read_text(encoding="utf-8")).rstrip())
        return 0
    elif args.command == "ai-smoke-summary":
        rows = [row for item in args.projects for row in _read_ai_smoke_results(Path(item))]
        if args.as_json:
            import json as _json
            print(_json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            print(_format_ai_smoke_summary(rows))
        return 0 if all(row.get("status") == "passed" for row in rows) else 1
    elif args.command == "ai-iteration-summary":
        rows = [row for item in args.projects for row in _read_ai_iteration_results(Path(item))]
        if args.as_json:
            import json as _json
            print(_json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            print(_format_ai_iteration_summary(rows))
        return 0 if all(row.get("status") == "passed" for row in rows) else 1
    elif args.command == "ai-release-summary":
        rows = [row for item in args.projects for row in _read_ai_release_results(Path(item))]
        if args.as_json:
            import json as _json
            print(_json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            print(_format_ai_release_summary(rows))
        return 0 if all(_ai_release_row_ready(row) for row in rows) else 1
    elif args.command == "ai-doctor":
        if not _ai_access_configured(args):
            print(
                "error: AI doctor requires model access. Set OPENAI_API_KEY, "
                "pass --ai-api-key, or pass --ai-base-url for a local OpenAI-compatible server.",
                file=sys.stderr,
            )
            return 1
        from .ai_doctor import check_ai_provider, format_ai_doctor_results
        results = check_ai_provider(
            planner_kwargs=_planner_kwargs_from_args(args),
            executor_kwargs=_executor_kwargs_from_args(args),
            vision_kwargs=_vision_kwargs_from_args(args),
            check_vision=args.check_vision,
        )
        print(format_ai_doctor_results(results))
        return 0 if all(result.status in {"passed", "skipped"} for result in results) else 1
    elif args.command == "narrate":
        from .narrate import narrate_project
        voice = args.voice or ("冰糖" if args.engine == "mimo" else "zh-CN-XiaoxiaoNeural")
        paths = narrate_project(
            args.project,
            voice,
            engine=args.engine,
            style=args.style,
            voice_clone_sample=Path(args.voice_clone) if args.voice_clone else None,
            voice_design_prompt=args.voice_design,
        )
        for path in paths:
            print(path)
        if not paths:
            print("No speaker notes found — nothing to narrate.")
    elif args.command == "voices":
        from .narrate import list_available_voices
        voices = list_available_voices(args.locale, engine=args.engine)
        for v in voices:
            print(v)
    elif args.command == "formats":
        from .formats import CANVAS_FORMATS
        print(f"{'Name':<12} {'Ratio':<8} {'Size':<15} {'Use Case'}")
        print("-" * 65)
        for fmt in CANVAS_FORMATS.values():
            print(f"{fmt.name:<12} {fmt.ratio:<8} {fmt.width}x{fmt.height:<10} {fmt.use_case}")
    elif args.command == "themes":
        from .themes import list_themes
        themes = list_themes()
        print(f"{'Name':<22} {'Font':<30} {'Direction'}")
        print("-" * 90)
        for t in themes:
            direction = t.design_hints[:55].rstrip() + "…"
            font_short = t.font_family.split(",")[0].strip()
            print(f"{t.name:<22} {font_short:<30} {direction}")
    elif args.command == "theme":
        from .themes import install_user_theme, list_themes, remove_user_theme, user_themes_dir
        if args.theme_command == "add":
            dest = install_user_theme(args.path, overwrite=args.overwrite)
            print(f"installed: {dest}")
        elif args.theme_command == "remove":
            dest = remove_user_theme(args.name)
            print(f"removed: {dest}")
        elif args.theme_command == "list":
            print(f"User themes dir: {user_themes_dir()}")
            print(f"{'Name':<22} {'Source':<40} {'Font'}")
            print("-" * 100)
            for t in list_themes():
                font_short = t.font_family.split(",")[0].strip()
                print(f"{t.name:<22} {t.source:<40} {font_short}")
    elif args.command == "templates":
        from .templates import (
            CATEGORIES, get_template, list_categories, list_templates,
        )
        if args.show:
            spec = get_template(args.show)
            print(f"Slug:     {spec.slug}")
            print(f"分类:     {spec.category_label}")
            print(f"中文名:   {spec.name_zh}")
            print(f"英文名:   {spec.name_en}")
            print(f"主题:     {spec.theme}")
            print(f"布局:     {' → '.join(spec.layouts)}")
            print(f"用途:     {spec.persona}")
            print(f"示例提纲:")
            for i, h in enumerate(spec.outline, 1):
                print(f"  {i}. {h}")
            print()
            print(f"快速生成:  slide-skill template-quickstart {spec.slug} --title <你的标题>")
            return 0
        if args.category:
            templates = list_templates(args.category)
            print(f"## {CATEGORIES[args.category]} ({len(templates)} 个模板)")
            print(f"{'Slug':<26} {'中文名':<22} {'主题':<22} {'用途'}")
            print("-" * 110)
            for t in templates:
                print(f"{t.slug:<26} {t.name_zh:<22} {t.theme:<22} {t.persona}")
            return 0
        cats = list_categories()
        total = sum(c[2] for c in cats)
        print(f"# {total} templates across {len(cats)} categories")
        print(f"# Use `--category <slug>` to drill in, `--show <slug>` for details.\n")
        for slug, label, count in cats:
            print(f"  {slug:<12} {count:>2} 个   {label}")
        return 0
    elif args.command == "template-quickstart":
        from .templates import get_template, template_outline_markdown
        spec = get_template(args.slug)
        name = args.name or spec.slug
        project = init_project(name, args.format, args.base, overwrite=args.overwrite)
        source_md = project / "sources" / f"{spec.slug}.md"
        source_md.write_text(template_outline_markdown(spec, args.title), encoding="utf-8")
        create_spec(project, source_md, title=args.title or spec.name_zh, theme_name=spec.theme)
        print(f"project:    {project}")
        print(f"template:   {spec.slug}  ({spec.category_label})")
        print(f"theme:      {spec.theme}")
        print(f"source:     {source_md}  (填入正文后再运行下面命令)")
        print(f"next:       slide-skill svg {project} --source {source_md}")
        print(f"            slide-skill finalize-svg {project} && slide-skill export {project}")
        return 0
    elif args.command == "competitions":
        from .competition import EXAMPLE_PACK_THEMES, list_competitions
        comps = list_competitions()
        print(f"{'ID':<22} {'名称':<24} {'时限':<8} {'页数':<10} {'章节数':<8} {'示例包主题'}")
        print("-" * 100)
        for c in comps:
            pages = f"{c.page_range[0]}-{c.page_range[1]}"
            theme = EXAMPLE_PACK_THEMES.get(c.name, "-")
            print(f"{c.name:<22} {c.name_zh:<24} {c.time_limit_minutes}min{' ':<4} {pages:<10} {len(c.sections):<8} {theme}")
        print()
        print("每个竞赛都有成品示例包（source + 演讲备注 + SVG + deck.pptx + QA）：examples/competitions/<ID>/")
        print("一条命令从示例包起步：slide-skill init <名称> --competition <ID> --from-example")
    elif args.command == "rehearse":
        from .rehearse import format_rehearsal_report, rehearse_project
        report = rehearse_project(args.project, time_limit_minutes=args.time_limit)
        print(format_rehearsal_report(report))
        return 1 if report.over_limit else 0
    elif args.command == "html-preview":
        import json as _json
        from .html_preview import write_preview_html
        project = Path(args.project)
        lang = args.lang
        if lang is None:
            lock = project / "spec_lock.json"
            if lock.exists():
                try:
                    lang = _json.loads(lock.read_text(encoding="utf-8")).get("lang", "en")
                except Exception:  # noqa: BLE001
                    lang = "en"
            else:
                lang = "en"
        out = Path(args.output) if args.output else project / "exports" / "preview.html"
        path = write_preview_html(project, out, title=args.title, lang=lang or "en")
        print(path)
    elif args.command == "font-preflight":
        import json as _json
        from .i18n import font_preflight_project
        from .themes import get_theme
        project = Path(args.project)
        theme_name = args.theme
        if theme_name is None and (project / "spec_lock.json").exists():
            try:
                theme_name = _json.loads((project / "spec_lock.json").read_text(encoding="utf-8")).get("theme")
            except Exception:  # noqa: BLE001
                theme_name = None
        theme = get_theme(theme_name or "dark-tech")
        report = font_preflight_project(theme, project, lang=args.lang)
        print(f"language: {report.language}")
        if not report.findings:
            print("- ok: no issues found.")
        for f in report.findings:
            print(f"- {f.severity} {f.code}: {f.message}")
        return 0 if not any(f.severity in {"error", "warn"} for f in report.findings) else 1
    elif args.command == "benchmark-briefs":
        from .benchmark import run_benchmark
        manifest, code = run_benchmark(
            args.briefs_dir,
            args.out,
            theme=args.theme,
            yes=args.yes and not args.dry_run,
            base_dir=args.base,
        )
        return code
    elif args.command == "draft-notes":
        from .draft_notes import draft_notes
        created = draft_notes(args.project, overwrite=args.overwrite)
        for path in created:
            print(path)
        if not created:
            print("All slides already have notes. Use --overwrite to regenerate.")
    return 0


def _numbers(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def _run_ai_smoke(args) -> tuple[Path, Path, Path]:
    """Run a persistent one-slide live LLM smoke project."""
    from .ai_executor import generate_svg_with_ai
    from .ai_planner import plan_slides_with_ai
    from .content_planner import ContentConfig

    if getattr(args, "require_visual_ok", False) and not getattr(args, "visual_critic", False):
        raise ValueError("--require-visual-ok requires --visual-critic")
    if getattr(args, "require_pptx_render", False) and not getattr(args, "visual_critic", False):
        raise ValueError("--require-pptx-render requires --visual-critic")
    if getattr(args, "require_pptx_render", False) and getattr(args, "rendered_dir", None):
        raise ValueError("--require-pptx-render cannot be used with --rendered-dir")

    project = init_project(args.name, args.format, args.base, overwrite=True)
    _reset_ai_smoke_outputs(project)
    if getattr(args, "require_pptx_render", False):
        render_error = _pptx_render_environment_error()
        if render_error:
            setattr(args, "_rendered_source_override", "missing-render-dependencies")
            message = f"AI smoke PPTX render preflight failed: {render_error}"
            _write_ai_smoke_result(project, None, None, args, status="failed", error=message)
            raise RuntimeError(message)
    if args.source:
        original = Path(args.source)
        source_md = project / "sources" / (original.stem + ".md")
        convert_file(original, source_md)
        if original.resolve() != source_md.resolve():
            dest_original = project / "sources" / original.name
            if not dest_original.exists():
                shutil.copy2(original, dest_original)
    else:
        source_md = project / "sources" / "ai-smoke.md"
        source_md.write_text(_AI_SMOKE_SOURCE, encoding="utf-8")

    create_spec(project, source_md, theme_name=args.theme)
    source_text = source_md.read_text(encoding="utf-8")
    config = ContentConfig(
        domain="general",
        max_items_per_slide=args.max_items,
        max_slides=args.max_slides,
        audience="live LLM smoke test",
    )
    plans = plan_slides_with_ai(
        source_text,
        config,
        project_path=project,
        **_planner_kwargs_from_args(args),
    )
    generate_svg_with_ai(project, plans, **_executor_kwargs_from_args(args))
    write_svg_report(project, quality=True)
    finalize_svg(project)
    deck = export_project(project)
    ok, report = run_qa(project, deck)
    if not ok:
        message = f"AI smoke QA failed: {report}"
        _write_ai_smoke_result(project, deck, report, args, status="failed", error=message)
        raise RuntimeError(message)
    if getattr(args, "visual_critic", False):
        from .visual_critic import generate_visual_feedback

        rendered_dir = project / "qa" / "rendered"
        if getattr(args, "rendered_dir", None):
            _copy_rendered_images(Path(args.rendered_dir), rendered_dir)
            rendered_source = "external-rendered-dir"
        else:
            rendered_source = _render_visual_evidence(project, deck, rendered_dir, dpi=getattr(args, "dpi", 150))
        setattr(args, "_rendered_source_override", rendered_source)
        if getattr(args, "require_pptx_render", False) and rendered_source != "pptx-render":
            message = f"AI smoke PPTX render gate failed: rendered_source is {rendered_source or 'unknown'}"
            _write_ai_smoke_result(project, deck, report, args, status="failed", error=message)
            raise RuntimeError(message)
        generate_visual_feedback(project, rendered_dir=rendered_dir, **_vision_kwargs_from_args(args))
        ok, report = run_qa(project, deck, require_visual=True)
        if not ok:
            message = f"AI smoke visual QA failed: {report}"
            _write_ai_smoke_result(project, deck, report, args, status="failed", error=message)
            raise RuntimeError(message)
        latest_visual_severity = _visual_feedback_max_severity(project / "qa" / "visual-feedback.json")
        if getattr(args, "require_visual_ok", False) and latest_visual_severity != "ok":
            message = f"AI smoke visual-ok gate failed: latest visual severity is {latest_visual_severity or 'unknown'}"
            _write_ai_smoke_result(project, deck, report, args, status="failed", error=message)
            raise RuntimeError(message)
    _write_ai_smoke_result(project, deck, report, args)
    return project, deck, report


def _reset_ai_smoke_outputs(project: Path) -> None:
    """Clear generated smoke evidence so repeated runs are comparable."""
    for dirname in ("qa", "svg_output", "svg_final", "exports"):
        target = project / dirname
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)


def _run_ai_release_check(args) -> Path:
    """Run the production AI release gate and write machine-readable evidence."""
    from argparse import Namespace
    from .ai_doctor import check_ai_provider

    project = Path(args.base) / _validate_project_name(args.name)
    if getattr(args, "require_pptx_render", False):
        render_error = _pptx_render_environment_error()
        if render_error:
            smoke_result = _ai_release_render_preflight_smoke_result(project, args, render_error)
            result_path = _write_ai_release_check_result(
                project,
                doctor_results=[],
                smoke_result=smoke_result,
                iteration_result=None,
                status="failed",
                error=str(smoke_result.get("error") or "AI release PPTX render preflight failed."),
            )
            raise RuntimeError(f"AI release check PPTX render preflight failed: {result_path}")

    doctor_results = check_ai_provider(
        planner_kwargs=_planner_kwargs_from_args(args),
        executor_kwargs=_executor_kwargs_from_args(args),
        vision_kwargs=_vision_kwargs_from_args(args),
        check_vision=True,
    )
    if any(result.status != "passed" for result in doctor_results):
        result_path = _write_ai_release_check_result(
            project,
            doctor_results=doctor_results,
            smoke_result=None,
            iteration_result=None,
            status="failed",
            error="AI provider doctor failed; release smoke was not run.",
        )
        raise RuntimeError(f"AI release check provider preflight failed: {result_path}")

    smoke_args = Namespace(**vars(args))
    smoke_args.visual_critic = True
    smoke_args.require_visual_ok = True
    try:
        project, deck, report = _run_ai_smoke(smoke_args)
    except _AI_COMMAND_ERRORS as exc:
        smoke_path = project / "qa" / "AI-SMOKE.json"
        smoke_result = _read_ai_smoke_result_file(smoke_path) if smoke_path.exists() else None
        if _release_smoke_can_retry_with_iteration(smoke_result):
            try:
                deck_path = Path(str(smoke_result.get("deck") or ""))
                iteration_deck = deck_path if deck_path.exists() else None
                _run_ai_iteration_loop(
                    project,
                    rounds=max(1, int(getattr(args, "repair_rounds", 2) or 2)),
                    first_pptx=iteration_deck,
                    dpi=getattr(args, "dpi", 150),
                    min_severity="minor",
                    strict_qa=True,
                    require_visual_ok=True,
                    executor_kwargs=_executor_kwargs_from_args(args),
                    vision_kwargs=_release_vision_kwargs_from_args(args),
                )
            except _AI_COMMAND_ERRORS as iteration_exc:
                iteration_path = project / "qa" / "AI-ITERATION.json"
                iteration_result = _read_ai_iteration_result_file(iteration_path) if iteration_path.exists() else None
                result_path = _write_ai_release_check_result(
                    project,
                    doctor_results=doctor_results,
                    smoke_result=smoke_result,
                    iteration_result=iteration_result,
                    status="failed",
                    error=f"{exc}; visual iteration failed: {iteration_exc}",
                )
                raise RuntimeError(f"AI release check visual iteration failed: {result_path}") from iteration_exc
            iteration_path = project / "qa" / "AI-ITERATION.json"
            iteration_result = _read_ai_iteration_result_file(iteration_path) if iteration_path.exists() else None
            if not iteration_result:
                raise RuntimeError("AI visual iteration did not write qa/AI-ITERATION.json")
            status = "passed" if iteration_result.get("status") == "passed" else "failed"
            error = "" if status == "passed" else str(iteration_result.get("error") or "AI visual iteration failed")
            result_path = _write_ai_release_check_result(
                project,
                doctor_results=doctor_results,
                smoke_result=smoke_result,
                iteration_result=iteration_result,
                status=status,
                error=error,
            )
            if _ai_release_check_result_ready(result_path):
                return result_path
            raise RuntimeError(f"AI release check gates failed: {result_path}") from exc
        result_path = _write_ai_release_check_result(
            project,
            doctor_results=doctor_results,
            smoke_result=smoke_result,
            iteration_result=None,
            status="failed",
            error=str(exc),
        )
        raise RuntimeError(f"AI release check smoke failed: {result_path}") from exc
    smoke_result = _read_ai_smoke_result_file(project / "qa" / "AI-SMOKE.json")
    status = "passed" if smoke_result.get("status") == "passed" else "failed"
    error = "" if status == "passed" else str(smoke_result.get("error") or "AI smoke failed")
    result_path = _write_ai_release_check_result(
        project,
        doctor_results=doctor_results,
        smoke_result=smoke_result,
        iteration_result=None,
        status=status,
        error=error,
    )
    if not _ai_release_check_result_ready(result_path):
        raise RuntimeError(f"AI release check failed: {result_path}")
    del deck, report
    return result_path


def _ai_release_render_preflight_smoke_result(project: Path, args, render_error: str) -> dict:
    """Return smoke-shaped evidence for release failures before any model call."""
    message = f"AI release PPTX render preflight failed: {render_error}"
    return {
        "status": "failed",
        "error": message,
        "project": str(project),
        "deck": "",
        "qa_report": "",
        "visual_critic": True,
        "require_visual_ok": True,
        "require_pptx_render": bool(getattr(args, "require_pptx_render", False)),
        "rendered_dir": str(project / "qa" / "rendered"),
        "rendered_source": "missing-render-dependencies",
        "trace_events": 0,
        "stages": [],
        "models": {
            "planner": _planner_kwargs_from_args(args).get("model") or "",
            "executor": _executor_kwargs_from_args(args).get("model") or "",
            "vision": _vision_kwargs_from_args(args).get("model") or "",
        },
        "metrics": _ai_smoke_metrics([]),
        "diagnosis": _ai_smoke_diagnosis(
            project,
            [],
            require_visual_ok=True,
            require_pptx_render=True,
            rendered_source="missing-render-dependencies",
        ),
        "stage_statuses": [],
    }


def _write_ai_release_check_result(
    project: Path,
    *,
    doctor_results,
    smoke_result: dict | None,
    iteration_result: dict | None,
    status: str,
    error: str = "",
) -> Path:
    from .util import ensure_dir

    gates = _ai_release_check_gates(doctor_results, smoke_result, iteration_result)
    final_status = status
    final_error = error
    if status == "passed" and not gates.get("release_ready"):
        final_status = "failed"
        final_error = error or "AI release gates did not reach release_ready."
    summary = _ai_release_check_summary(
        doctor_results,
        smoke_result,
        iteration_result,
        gates=gates,
        status=final_status,
        error=final_error,
        capability_gaps=_ai_trace_capability_gaps(project),
    )
    payload = {
        "status": final_status,
        "error": final_error,
        "project": str(project),
        "summary": summary,
        "doctor": [
            {
                "role": result.role,
                "model": result.model,
                "base_url": result.base_url,
                "status": result.status,
                "error": result.error,
                "next_action": result.next_action,
            }
            for result in doctor_results
        ],
        "smoke": smoke_result or {},
        "iteration": iteration_result or {},
        "gates": gates,
    }
    path = ensure_dir(project / "qa") / "AI-RELEASE-CHECK.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _ai_release_check_result_ready(result_path: Path) -> bool:
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    gates = payload.get("gates") if isinstance(payload, dict) and isinstance(payload.get("gates"), dict) else {}
    return payload.get("status") == "passed" and gates.get("release_ready") is True


def _ai_trace_capability_gaps(project: Path) -> list[str]:
    """Distinct capability-gap markers recorded in the project's AI trace.

    QA-03: a repair accepted without a browser re-render check writes
    ``metadata.capability_gap`` into its trace event. The release gate must
    list these explicitly instead of letting them pass silently.
    """
    from .ai_trace import read_ai_trace

    gaps: list[str] = []
    for event in read_ai_trace(project):
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        gap = str(metadata.get("capability_gap") or "").strip()
        if gap:
            gaps.append(gap)
    return sorted(set(gaps))


def _ai_release_check_summary(
    doctor_results,
    smoke_result: dict | None,
    iteration_result: dict | None,
    *,
    gates: dict,
    status: str,
    error: str = "",
    capability_gaps: list[str] | None = None,
) -> dict:
    """Return a CI- and human-readable release decision summary."""
    final_visual_severity = _final_release_visual_severity(smoke_result, iteration_result)
    smoke_visual_severity = _latest_smoke_visual_severity(smoke_result)
    rendered_source = _final_release_rendered_source(smoke_result, iteration_result)
    blocking_reasons = _ai_release_blocking_reasons(
        doctor_results,
        smoke_result,
        iteration_result,
        gates=gates,
        rendered_source=rendered_source,
        final_visual_severity=final_visual_severity,
        error=error,
    )
    warnings = _ai_release_warnings(
        smoke_result,
        iteration_result,
        gates=gates,
        smoke_visual_severity=smoke_visual_severity,
        final_visual_severity=final_visual_severity,
        rendered_source=rendered_source,
        capability_gaps=capability_gaps,
    )
    repair_guidance = _ai_release_repair_guidance(smoke_result, gates=gates)
    provider_failures = _ai_release_provider_failures(doctor_results)
    return {
        "decision": "release-ready" if gates.get("release_ready") else "not-release-ready",
        "status": status,
        "release_ready": bool(gates.get("release_ready")),
        "blocking_reasons": blocking_reasons,
        "warnings": warnings,
        "next_actions": _ai_release_next_actions(
            blocking_reasons,
            warnings,
            repair_guidance=repair_guidance,
            provider_failures=provider_failures,
        ),
        "final_visual_severity": final_visual_severity or "",
        "smoke_visual_severity": smoke_visual_severity or "",
        "rendered_source": rendered_source or "",
        "capability_gaps": list(capability_gaps or []),
        **repair_guidance,
        "provider_failures": provider_failures,
        "strict_pptx_render_required": bool(isinstance(smoke_result, dict) and smoke_result.get("require_pptx_render")),
        "visual_iteration_reviewed": bool(gates.get("visual_iteration_review")),
        "visual_repair_applied": bool(gates.get("visual_repair_applied")),
        "doctor_roles": [
            {
                "role": getattr(result, "role", ""),
                "status": getattr(result, "status", ""),
                "model": getattr(result, "model", ""),
            }
            for result in doctor_results
        ],
    }


def _ai_release_provider_failures(doctor_results) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for result in doctor_results:
        if getattr(result, "status", "") == "passed":
            continue
        failure = {
            "role": str(getattr(result, "role", "") or "unknown"),
            "status": str(getattr(result, "status", "") or "unknown"),
            "model": str(getattr(result, "model", "") or ""),
            "base_url": str(getattr(result, "base_url", "") or ""),
        }
        error = str(getattr(result, "error", "") or "")
        if error:
            failure["error"] = error
        next_action = str(getattr(result, "next_action", "") or "")
        if next_action:
            failure["next_action"] = next_action
        failures.append(failure)
    return failures


def _ai_release_repair_guidance(smoke_result: dict | None, *, gates: dict) -> dict:
    if gates.get("release_ready") or gates.get("visual_repair_applied"):
        return {}
    diagnosis = smoke_result.get("diagnosis") if isinstance(smoke_result, dict) and isinstance(smoke_result.get("diagnosis"), dict) else {}
    targets = diagnosis.get("repair_targets") if isinstance(diagnosis.get("repair_targets"), list) else []
    if not targets:
        return {}
    result = {
        "repair_targets": targets[:3],
        "repair_target_count": int(diagnosis.get("repair_target_count") or len(targets)),
    }
    if diagnosis.get("repair_targets_more"):
        result["repair_targets_more"] = diagnosis.get("repair_targets_more")
    if diagnosis.get("repair_command"):
        result["repair_command"] = str(diagnosis.get("repair_command"))
    return result


def _ai_release_blocking_reasons(
    doctor_results,
    smoke_result: dict | None,
    iteration_result: dict | None,
    *,
    gates: dict,
    rendered_source: str,
    final_visual_severity: str,
    error: str = "",
) -> list[str]:
    reasons: list[str] = []
    strict_pptx = bool(isinstance(smoke_result, dict) and smoke_result.get("require_pptx_render"))
    if strict_pptx and rendered_source == "missing-render-dependencies":
        return ["PPTX render preflight failed before provider/model calls because render dependencies are missing"]
    if not gates.get("provider_preflight"):
        failed_roles = [
            str(getattr(result, "role", "") or "unknown")
            for result in doctor_results
            if getattr(result, "status", "") != "passed"
        ]
        if failed_roles:
            reasons.append(f"provider preflight failed for role(s): {', '.join(failed_roles)}")
        else:
            reasons.append("provider preflight did not run or produced no passing role checks")
    if not gates.get("planner_executor_visual_smoke"):
        reasons.append("planner/executor/visual smoke did not complete with deck and QA evidence")
    final_result = iteration_result if isinstance(iteration_result, dict) else smoke_result
    if not (isinstance(final_result, dict) and final_result.get("status") == "passed"):
        reasons.append("final smoke or visual iteration status is not passed")
    if not gates.get("visual_severity_ok"):
        reasons.append(f"final visual severity is {final_visual_severity or 'unknown'}, not ok")
    if not gates.get("executor_had_planner_brief"):
        reasons.append("executor trace is missing the validated planner brief handoff")
    if strict_pptx and not gates.get("rendered_source_pptx"):
        reasons.append(f"strict PPTX render was required but final rendered_source is {rendered_source or 'unknown'}")
    if error and not reasons:
        reasons.append(str(error))
    return _dedupe_strings(reasons)


def _ai_release_warnings(
    smoke_result: dict | None,
    iteration_result: dict | None,
    *,
    gates: dict,
    smoke_visual_severity: str,
    final_visual_severity: str,
    rendered_source: str,
    capability_gaps: list[str] | None = None,
) -> list[str]:
    warnings: list[str] = []
    for gap in capability_gaps or []:
        warnings.append(
            f"capability-gap: {gap} — at least one auto-repair was accepted "
            "without a browser re-render check (no local Chrome/Edge)"
        )
    strict_pptx = bool(isinstance(smoke_result, dict) and smoke_result.get("require_pptx_render"))
    if strict_pptx and rendered_source == "missing-render-dependencies":
        return warnings
    if gates.get("trace_has_no_failed_events") is False and gates.get("trace_converged_after_retries"):
        warnings.append("one or more model attempts failed before a later retry converged")
    if gates.get("visual_iteration_review") and smoke_visual_severity and smoke_visual_severity != "ok":
        if gates.get("visual_repair_applied"):
            warnings.append(
                f"initial visual smoke was {smoke_visual_severity}; release readiness depends on the repaired visual iteration"
            )
        else:
            warnings.append(
                f"initial visual smoke was {smoke_visual_severity}; later review passed without an SVG rewrite"
            )
    if rendered_source and rendered_source != "pptx-render":
        warnings.append(f"final visual evidence came from {rendered_source}, not PPTX render")
    if final_visual_severity == "ok" and gates.get("release_ready") and gates.get("visual_iteration_review"):
        warnings.append("release passed after visual iteration; keep AI-ITERATION.json with the release evidence")
    return _dedupe_strings(warnings)


def _ai_release_next_actions(
    blocking_reasons: list[str],
    warnings: list[str],
    *,
    repair_guidance: dict | None = None,
    provider_failures: list[dict[str, str]] | None = None,
) -> list[str]:
    if not blocking_reasons:
        actions = ["Archive qa/AI-RELEASE-CHECK.json, qa/AI-SMOKE.json, qa/ai-trace.jsonl, and rendered evidence with the release."]
        if any("not PPTX render" in warning for warning in warnings):
            actions.append("For production acceptance, rerun with --require-pptx-render on a LibreOffice+Poppler machine.")
        if any("without an SVG rewrite" in warning for warning in warnings):
            actions.append("Manually inspect the rendered image if policy requires deterministic repair after non-ok first-pass feedback.")
        return actions

    actions: list[str] = []
    joined = " ".join(blocking_reasons).lower()
    if "provider preflight" in joined:
        for failure in provider_failures or []:
            role = str(failure.get("role") or "unknown")
            next_action = str(failure.get("next_action") or "")
            if next_action:
                actions.append(f"{role} provider: {next_action}")
        actions.append("Run slide-skill ai-doctor --check-vision and fix API key, base URL, model, or account access.")
    if "pptx render" in joined or "rendered_source" in joined:
        actions.append("Run slide-skill render-doctor, install/repair LibreOffice and Poppler, then rerun with --require-pptx-render.")
    if "visual severity" in joined:
        repair_command = str((repair_guidance or {}).get("repair_command") or "")
        if repair_command:
            actions.append(f"Run {repair_command}, then rerun iterate-ai until latest visual severity is ok.")
        else:
            actions.append("Inspect qa/VISUAL-REVIEW.md, run iterate-ai, and keep rerunning until latest visual severity is ok.")
    if "planner/executor/visual smoke" in joined or "planner brief" in joined:
        actions.append("Inspect slide-skill ai-trace <project> --diagnose before changing prompts or models.")
    if not actions:
        actions.append("Inspect qa/AI-RELEASE-CHECK.json, qa/AI-SMOKE.json, and qa/ai-trace.jsonl to identify the failed gate.")
    return _dedupe_strings(actions)


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
    return result


def _release_smoke_can_retry_with_iteration(smoke_result: dict | None) -> bool:
    """Only visual-ok smoke failures have enough deck evidence for automatic repair."""
    if not isinstance(smoke_result, dict):
        return False
    diagnosis = smoke_result.get("diagnosis") if isinstance(smoke_result.get("diagnosis"), dict) else {}
    if diagnosis.get("focus") != "visual-ok-gate":
        return False
    deck = Path(str(smoke_result.get("deck") or ""))
    return deck.exists() and bool(smoke_result.get("qa_report"))


def _ai_release_check_gates(doctor_results, smoke_result: dict | None, iteration_result: dict | None) -> dict:
    provider_preflight = bool(doctor_results) and all(result.status == "passed" for result in doctor_results)
    smoke_metrics = smoke_result.get("metrics") if isinstance(smoke_result, dict) and isinstance(smoke_result.get("metrics"), dict) else {}
    final_result = iteration_result if isinstance(iteration_result, dict) else smoke_result
    final_status_passed = isinstance(final_result, dict) and final_result.get("status") == "passed"
    visual_iteration_review = isinstance(iteration_result, dict)
    visual_repair_applied = _ai_iteration_repaired_slide_count(iteration_result) > 0
    smoke_completed = (
        isinstance(smoke_result, dict)
        and bool(smoke_result.get("deck"))
        and bool(smoke_result.get("qa_report"))
        and bool(smoke_result.get("visual_critic"))
    )
    if isinstance(iteration_result, dict):
        final_visual_severity = str(iteration_result.get("latest_visual_severity") or "").lower()
        total_metrics = iteration_result.get("total_metrics") if isinstance(iteration_result.get("total_metrics"), dict) else {}
        failed_events = int(total_metrics.get("failed_events") or 0)
    else:
        final_visual_severity = _latest_smoke_visual_severity(smoke_result)
        failed_events = int(smoke_metrics.get("failed_events") or 0)
    executor_brief_missing = int(smoke_metrics.get("executor_brief_missing_events") or 0)
    rendered_source = _final_release_rendered_source(smoke_result, iteration_result)
    requires_pptx_render = bool(
        isinstance(smoke_result, dict)
        and smoke_result.get("require_pptx_render")
    )
    release_ready = (
        provider_preflight
        and smoke_completed
        and final_status_passed
        and final_visual_severity == "ok"
        and executor_brief_missing == 0
        and (not requires_pptx_render or rendered_source == "pptx-render")
    )
    return {
        "provider_preflight": provider_preflight,
        "planner_executor_visual_smoke": smoke_completed,
        "visual_iteration_review": visual_iteration_review,
        "visual_repair_applied": visual_repair_applied,
        "visual_severity_ok": final_visual_severity == "ok",
        "rendered_source_pptx": rendered_source == "pptx-render",
        "trace_has_no_failed_events": failed_events == 0,
        "trace_converged_after_retries": final_status_passed,
        "executor_had_planner_brief": executor_brief_missing == 0,
        "release_ready": release_ready,
    }


def _final_release_rendered_source(smoke_result: dict | None, iteration_result: dict | None) -> str:
    if isinstance(iteration_result, dict) and str(iteration_result.get("latest_rendered_source") or ""):
        return str(iteration_result.get("latest_rendered_source") or "")
    if isinstance(smoke_result, dict):
        return str(smoke_result.get("rendered_source") or "")
    return ""


def _ai_iteration_repaired_slide_count(iteration_result: dict | None) -> int:
    if not isinstance(iteration_result, dict):
        return 0
    cycles = iteration_result.get("repair_cycles") if isinstance(iteration_result.get("repair_cycles"), list) else []
    count = 0
    for cycle in cycles:
        if not isinstance(cycle, dict):
            continue
        repaired = cycle.get("repaired") if isinstance(cycle.get("repaired"), list) else []
        count += len(repaired)
    return count


def _latest_smoke_visual_severity(smoke_result: dict | None) -> str:
    if not isinstance(smoke_result, dict):
        return ""
    stage_statuses = smoke_result.get("stage_statuses") if isinstance(smoke_result.get("stage_statuses"), list) else []
    for event in reversed(stage_statuses):
        if not isinstance(event, dict) or event.get("stage") != "visual-critic":
            continue
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        severity = str(metadata.get("severity") or "").lower()
        if severity:
            return severity
    metrics = smoke_result.get("metrics") if isinstance(smoke_result.get("metrics"), dict) else {}
    return str(metrics.get("max_visual_severity") or "").lower()


def _final_release_visual_severity(smoke_result: dict | None, iteration_result: dict | None) -> str:
    if isinstance(iteration_result, dict):
        return str(iteration_result.get("latest_visual_severity") or "").lower()
    return _latest_smoke_visual_severity(smoke_result)


def _write_ai_smoke_result(
    project: Path,
    deck: Path | None,
    report: Path | None,
    args,
    *,
    status: str | None = None,
    error: str = "",
) -> Path:
    """Write machine-readable evidence for the persistent AI smoke run."""
    from .ai_trace import read_ai_trace
    from .util import ensure_dir

    events = read_ai_trace(project)
    stages = [str(event.get("stage", "unknown")) for event in events]
    completed = bool(events) and bool(deck) and bool(report) and Path(deck).exists() and Path(report).exists()
    result = {
        "status": status or ("passed" if completed else "failed"),
        "error": error,
        "project": str(project),
        "deck": str(deck or ""),
        "qa_report": str(report or ""),
        "visual_critic": bool(getattr(args, "visual_critic", False)),
        "require_visual_ok": bool(getattr(args, "require_visual_ok", False)),
        "require_pptx_render": bool(getattr(args, "require_pptx_render", False)),
        "rendered_dir": str(project / "qa" / "rendered") if getattr(args, "visual_critic", False) else "",
        "rendered_source": _ai_smoke_rendered_source(project, args),
        "trace_events": len(events),
        "stages": stages,
        "models": _ai_smoke_role_models(args, events),
        "metrics": _ai_smoke_metrics(events),
        "diagnosis": _ai_smoke_diagnosis(
            project,
            events,
            require_visual_ok=bool(getattr(args, "require_visual_ok", False)),
            require_pptx_render=bool(getattr(args, "require_pptx_render", False)),
            rendered_source=_ai_smoke_rendered_source(project, args),
        ),
        "stage_statuses": [
            {
                "stage": event.get("stage", "unknown"),
                "status": event.get("status", "unknown"),
                "attempt": event.get("attempt"),
                "model": event.get("model", ""),
                "metadata": event.get("metadata", {}),
            }
            for event in events
        ],
    }
    path = ensure_dir(project / "qa") / "AI-SMOKE.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _ai_smoke_diagnosis(
    project: Path,
    events: list[dict],
    *,
    require_visual_ok: bool = False,
    require_pptx_render: bool = False,
    rendered_source: str = "",
) -> dict:
    """Return the most useful next inspection target for an AI smoke run."""
    from .ai_trace import format_ai_trace_command, issue_specific_next_steps

    diagnosis: dict = {
        "focus": "no-trace",
        "trace": format_ai_trace_command(project),
        "diagnose": format_ai_trace_command(project, diagnose=True),
    }
    if not events:
        if require_pptx_render and rendered_source != "pptx-render":
            diagnosis["focus"] = "pptx-render-gate"
            diagnosis["rendered_source"] = rendered_source or "unknown"
            diagnosis["next"] = (
                "Install or repair LibreOffice and Poppler, run slide-skill render-doctor, "
                "then rerun the smoke with --require-pptx-render."
            )
            return diagnosis
        diagnosis["next"] = "No model interaction was recorded; check AI access/configuration before prompt tuning."
        return diagnosis

    repair_gate = _latest_smoke_visual_repair_gate(events, require_visual_ok=require_visual_ok)
    failed = [event for event in events if event.get("status") not in {"passed", "ok", "success"}]
    target = None
    focus = "all-passed"
    if repair_gate:
        target = repair_gate
        metadata = repair_gate.get("metadata") if isinstance(repair_gate.get("metadata"), dict) else {}
        severity = str(metadata.get("severity") or "").lower()
        focus = "visual-ok-gate" if require_visual_ok and severity in {"minor", "major", "critical"} else "active-repair-gate"
    elif failed:
        target = failed[-1]
        focus = "recovered-failure" if events.index(target) < len(events) - 1 else "latest-failure"

    diagnosis["focus"] = focus
    if target is None and require_pptx_render and rendered_source != "pptx-render":
        diagnosis["focus"] = "pptx-render-gate"
        diagnosis["rendered_source"] = rendered_source or "unknown"
        diagnosis["next"] = (
            "Install or repair LibreOffice and Poppler, run slide-skill render-doctor, "
            "then rerun the smoke with --require-pptx-render."
        )
        return diagnosis
    if target is None:
        diagnosis["next"] = "All recorded model events passed their current gates."
        return diagnosis

    metadata = target.get("metadata") if isinstance(target.get("metadata"), dict) else {}
    event_index = events.index(target) + 1
    diagnosis.update({
        "event": event_index,
        "stage": target.get("stage", "unknown"),
        "status": target.get("status", "unknown"),
        "attempt": target.get("attempt"),
        "model": target.get("model", ""),
        "inspect_raw": format_ai_trace_command(project, event_index=event_index, part="raw"),
    })
    for key in ("slide", "severity", "error", "blocking_issues", "blocking_count"):
        if key in metadata:
            diagnosis[key] = metadata[key]
    next_detail = issue_specific_next_steps(target, metadata)
    if next_detail:
        diagnosis["next_detail"] = next_detail
    if focus == "recovered-failure":
        recovered_by = _first_later_passed_event(events, target)
        if recovered_by:
            recovered_metadata = recovered_by.get("metadata") if isinstance(recovered_by.get("metadata"), dict) else {}
            diagnosis["recovered_by_event"] = events.index(recovered_by) + 1
            diagnosis["recovered_by_stage"] = recovered_by.get("stage", "unknown")
            diagnosis["recovered_by_attempt"] = recovered_by.get("attempt")
            diagnosis["recovered_feedback_used"] = bool(
                recovered_metadata.get("feedback")
                or recovered_metadata.get("has_qa_feedback")
                or recovered_metadata.get("has_visual_feedback")
            )
    if focus == "active-repair-gate":
        _append_ai_smoke_repair_targets(diagnosis, project, min_severity="major")
        diagnosis["next"] = "Run repair-feedback or iterate-ai; the latest visual critic feedback is repair-worthy."
    elif focus == "visual-ok-gate":
        _append_ai_smoke_repair_targets(diagnosis, project, min_severity="minor")
        diagnosis["next"] = "Review the latest visual feedback and run iterate-ai; this smoke requires severity ok."
    elif _looks_like_ai_provider_access_error(str(metadata.get("error") or "")):
        provider_role = _ai_smoke_provider_role(str(target.get("stage") or ""))
        diagnosis["provider_role"] = provider_role
        diagnosis["provider_model"] = str(target.get("model") or "")
        diagnosis["next"] = _ai_smoke_provider_next_action(provider_role, diagnosis["provider_model"])
    elif focus == "recovered-failure":
        diagnosis["next"] = "A later retry passed; inspect this event only if the generated artifact still looks wrong."
    else:
        diagnosis["next"] = "Inspect the failing raw response and prompt before changing generation rules."
    return diagnosis


def _ai_smoke_provider_role(stage: str) -> str:
    clean = str(stage or "").strip().lower()
    if clean == "visual-critic":
        return "vision"
    if clean in {"planner", "executor", "vision"}:
        return clean
    return "unknown"


def _ai_smoke_provider_next_action(role: str, model: str) -> str:
    current = f" Current model={model}." if model else ""
    if role == "planner":
        return (
            "Verify OPENAI_PLANNER_MODEL or --planner-model, API key, base URL, "
            f"and planner account access before running quickstart-ai or ai-smoke.{current}"
        )
    if role == "executor":
        return (
            "Verify OPENAI_EXECUTOR_MODEL or --executor-model, API key, base URL, "
            f"and executor account access before SVG generation or repair-feedback.{current}"
        )
    if role == "vision":
        return (
            "Use a vision-capable OPENAI_VISION_MODEL or --vision-model with image input support "
            f"before visual-critic, ai-smoke --visual-critic, or release gates.{current}"
        )
    return f"Verify API key, base URL, model access, and provider account status.{current}"


def _append_ai_smoke_repair_targets(diagnosis: dict, project: Path, *, min_severity: str) -> None:
    from .ai_trace import format_cli_path, visual_repair_targets

    targets = visual_repair_targets(project, min_severity=min_severity)
    if not targets:
        return
    diagnosis["repair_targets"] = targets[:3]
    diagnosis["repair_target_count"] = len(targets)
    if len(targets) > 3:
        diagnosis["repair_targets_more"] = len(targets) - 3
    diagnosis["repair_command"] = f"slide-skill repair-feedback {format_cli_path(project)} --min-severity {min_severity}"


def _first_later_passed_event(events: list[dict], target: dict) -> dict | None:
    target_index = events.index(target)
    target_stage = target.get("stage")
    target_slide = None
    target_metadata = target.get("metadata") if isinstance(target.get("metadata"), dict) else {}
    if "slide" in target_metadata:
        target_slide = target_metadata.get("slide")
    for event in events[target_index + 1:]:
        if event.get("stage") != target_stage:
            continue
        if event.get("status") not in {"passed", "ok", "success"}:
            continue
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if target_slide is not None and metadata.get("slide") != target_slide:
            continue
        return event
    return None


def _ai_smoke_metrics(events: list[dict]) -> dict:
    failed_events = [event for event in events if event.get("status") not in {"passed", "ok", "success"}]
    recovered_events = [
        recovered
        for event in failed_events
        if (recovered := _first_later_passed_event(events, event)) is not None
    ]
    return {
        "prompt_chars": sum(int(event.get("prompt_chars") or 0) for event in events),
        "raw_chars": sum(int(event.get("raw_chars") or 0) for event in events),
        "request_chars": sum(int(event.get("request_chars") or 0) for event in events),
        "attempts": sum(1 for event in events if event.get("attempt") is not None),
        "failed_events": len(failed_events),
        "passed_events": sum(1 for event in events if event.get("status") in {"passed", "ok", "success"}),
        "failure_hint_counts": _ai_failure_hint_counts(failed_events),
        "recovered_failure_count": len(recovered_events),
        "feedback_recovered_failure_count": sum(1 for event in recovered_events if _event_used_ai_feedback(event)),
        "blocking_count": sum(_event_blocking_count(event) for event in events),
        "max_visual_severity": _max_visual_severity(events),
        "executor_brief_missing_events": sum(
            1
            for event in events
            if event.get("stage") == "executor"
            and isinstance(event.get("metadata"), dict)
            and event["metadata"].get("has_executor_brief") is False
        ),
        "visual_feedback_used_events": sum(
            1
            for event in events
            if event.get("stage") == "executor"
            and isinstance(event.get("metadata"), dict)
            and event["metadata"].get("has_visual_feedback") is True
        ),
    }


def _ai_failure_hint_counts(events: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        alias = _ai_failure_hint_alias(event)
        counts[alias] = counts.get(alias, 0) + 1
    return counts


def _ai_failure_hint_alias(event: dict) -> str:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    try:
        from .ai_trace import failure_hint_alias

        return failure_hint_alias(event, metadata)
    except Exception:  # noqa: BLE001 - metrics should not break summary output.
        pass
    if _looks_like_ai_provider_access_error(str(metadata.get("error") or "")):
        return "provider-access"
    return "unclassified"


def _event_used_ai_feedback(event: dict) -> bool:
    metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
    return bool(
        metadata.get("feedback")
        or metadata.get("has_qa_feedback")
        or metadata.get("has_visual_feedback")
    )


def _pptx_render_environment_error() -> str:
    env = render_environment()
    if env.get("ok"):
        return ""
    issues = env.get("issues") if isinstance(env.get("issues"), list) else []
    return "; ".join(str(issue) for issue in issues) or "Render dependencies are not ready. Run `slide-skill render-doctor` for details."


def _ai_smoke_rendered_source(project: Path, args) -> str:
    if not getattr(args, "visual_critic", False):
        return ""
    override = str(getattr(args, "_rendered_source_override", "") or "")
    if override:
        return override
    if getattr(args, "rendered_dir", None):
        return "external-rendered-dir"
    if (project / "qa" / "rendered" / "_svg-preview-html").exists():
        return "svg-preview"
    if (project / "qa" / "rendered").exists():
        return "pptx-render"
    return ""


def _event_blocking_count(event: dict) -> int:
    metadata = event.get("metadata")
    if not isinstance(metadata, dict):
        return 0
    try:
        return int(metadata.get("blocking_count") or 0)
    except (TypeError, ValueError):
        return 0


def _latest_smoke_visual_repair_gate(events: list[dict], *, require_visual_ok: bool = False) -> dict | None:
    latest_by_slide: dict[object, dict] = {}
    for event in events:
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        if event.get("stage") == "visual-critic":
            latest_by_slide[metadata.get("slide", "unknown")] = event
    for event in reversed(list(latest_by_slide.values())):
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        gated = {"minor", "major", "critical"} if require_visual_ok else {"major", "critical"}
        if str(metadata.get("severity") or "").lower() in gated:
            return event
    return None


def _max_visual_severity(events: list[dict]) -> str:
    order = {"ok": 0, "minor": 1, "major": 2, "critical": 3}
    highest = ""
    highest_rank = -1
    for event in events:
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            continue
        severity = str(metadata.get("severity") or "").lower()
        rank = order.get(severity)
        if rank is not None and rank > highest_rank:
            highest = severity
            highest_rank = rank
    return highest


def _looks_like_ai_provider_access_error(error: str) -> bool:
    clean = error.lower()
    return any(marker in clean for marker in (
        "401",
        "403",
        "authenticationerror",
        "permission",
        "forbidden",
        "unauthorized",
        "unsupported image",
        "image input",
        "vision model",
        "vision-capable",
    ))


def _ai_smoke_role_models(args, events: list[dict]) -> dict:
    trace_models: dict[str, str] = {}
    for event in events:
        stage = str(event.get("stage", ""))
        model = str(event.get("model", "") or "")
        if stage and model:
            trace_models[stage] = model
    return {
        "planner": _planner_kwargs_from_args(args).get("model") or trace_models.get("planner", ""),
        "executor": _executor_kwargs_from_args(args).get("model") or trace_models.get("executor", ""),
        "vision": _vision_kwargs_from_args(args).get("model") or trace_models.get("visual-critic", ""),
    }


def _read_ai_smoke_results(path: Path) -> list[dict]:
    smoke_path = path if path.name == "AI-SMOKE.json" else path / "qa" / "AI-SMOKE.json"
    if smoke_path.exists():
        return [_read_ai_smoke_result_file(smoke_path)]
    if path.is_dir():
        child_results = sorted(path.glob("*/qa/AI-SMOKE.json"))
        if child_results:
            return [_read_ai_smoke_result_file(child) for child in child_results]
    raise FileNotFoundError(f"AI smoke result not found: {smoke_path}")


def _read_ai_smoke_result_file(smoke_path: Path) -> dict:
    if not smoke_path.exists():
        raise FileNotFoundError(f"AI smoke result not found: {smoke_path}")
    payload = json.loads(smoke_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"AI smoke result must be a JSON object: {smoke_path}")
    payload = dict(payload)
    payload["result_path"] = str(smoke_path)
    _refresh_ai_smoke_diagnosis_from_trace(payload, smoke_path)
    payload["summary_hint"] = _ai_smoke_summary_hint(payload)
    return payload


def _refresh_ai_smoke_diagnosis_from_trace(payload: dict, smoke_path: Path) -> None:
    project = _ai_smoke_project_path(payload, smoke_path)
    trace_path = project / "qa" / "ai-trace.jsonl"
    if not trace_path.exists():
        return
    try:
        from .ai_trace import read_ai_trace

        events = read_ai_trace(project)
    except Exception:  # noqa: BLE001 - summary must still work with a stale/corrupt trace.
        return
    if not events:
        return
    payload["diagnosis"] = _ai_smoke_diagnosis(
        project,
        events,
        require_visual_ok=bool(payload.get("require_visual_ok")),
        require_pptx_render=bool(payload.get("require_pptx_render")),
        rendered_source=str(payload.get("rendered_source") or ""),
    )
    payload["metrics"] = {
        **(payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}),
        **_ai_smoke_metrics(events),
    }
    payload["trace_events"] = len(events)
    payload["stages"] = [str(event.get("stage", "unknown")) for event in events]
    payload["diagnosis_refreshed_from_trace"] = True


def _ai_smoke_project_path(payload: dict, smoke_path: Path) -> Path:
    project = str(payload.get("project") or "").strip()
    if project:
        return Path(project)
    return smoke_path.parent.parent


def _format_ai_smoke_summary(rows: list[dict]) -> str:
    lines = [
        "AI smoke summary",
        "status | stages | trace | failed | block | sev | prompt | raw | request | visual | render | planner | executor | vision | hint | project",
        "-------|--------|-------|--------|-------|-----|--------|-----|---------|--------|--------|---------|----------|--------|------|--------",
    ]
    for row in rows:
        models = row.get("models") if isinstance(row.get("models"), dict) else {}
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        stages = ",".join(str(item) for item in row.get("stages", []))
        lines.append(
            " | ".join([
                str(row.get("status", "unknown")),
                stages or "-",
                str(row.get("trace_events", 0)),
                str(metrics.get("failed_events", "-")),
                str(metrics.get("blocking_count", "-")),
                str(metrics.get("max_visual_severity", "") or "-"),
                str(metrics.get("prompt_chars", "-")),
                str(metrics.get("raw_chars", "-")),
                str(metrics.get("request_chars", "-")),
                "yes" if row.get("visual_critic") else "no",
                str(row.get("rendered_source", "") or "-"),
                str(models.get("planner", "") or "-"),
                str(models.get("executor", "") or "-"),
                str(models.get("vision", "") or "-"),
                str(row.get("summary_hint") or _ai_smoke_summary_hint(row)),
                str(row.get("project", "") or row.get("result_path", "")),
            ])
        )
    return "\n".join(lines)


def _ai_smoke_summary_hint(row: dict) -> str:
    diagnosis = row.get("diagnosis") if isinstance(row.get("diagnosis"), dict) else {}
    focus = str(diagnosis.get("focus") or "")
    details = diagnosis.get("next_detail") if isinstance(diagnosis.get("next_detail"), list) else []
    prefix = {
        "recovered-failure": "recovered",
        "latest-failure": "failed",
        "active-repair-gate": "repair",
        "visual-ok-gate": "visual-ok",
        "pptx-render-gate": "pptx-render",
    }.get(focus, "")
    if details:
        return _compact_ai_hint(f"{prefix}:{details[0]}" if prefix else str(details[0]))
    if prefix:
        repair_target_count = diagnosis.get("repair_target_count")
        if focus in {"active-repair-gate", "visual-ok-gate"} and repair_target_count:
            return f"{prefix}:targets={repair_target_count}"
        if focus == "recovered-failure" and diagnosis.get("recovered_feedback_used") is True:
            return "recovered:feedback"
        provider_role = str(diagnosis.get("provider_role") or "").strip().lower()
        if focus in {"latest-failure", "recovered-failure"} and provider_role:
            return f"{prefix}:provider={provider_role}"
        return prefix
    return "-"


def _compact_ai_hint(text: str, *, limit: int = 44) -> str:
    clean = " ".join(str(text).replace("|", "/").split())
    alias = _ai_hint_alias(clean)
    if alias:
        clean = _replace_ai_hint_marker(clean, alias)
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _ai_hint_alias(text: str) -> str:
    clean = str(text)
    aliases = (
        ("Fix content fidelity before visual polish", "content-fidelity"),
        ("Fix planner-to-executor layout handoff", "layout-handoff"),
        ("Fix style-token compliance", "style-token"),
        ("Fix output protocol first", "output-protocol"),
        ("Fix visual-critic protocol before repair", "critic-protocol"),
        ("Fix planner coverage before SVG generation", "planner-coverage"),
        ("Fix numeric grounding", "numeric-grounding"),
        ("Reduce source/slide density or increase max tokens", "token-density"),
        ("Fix planner protocol first", "planner-protocol"),
    )
    for marker, alias in aliases:
        if marker in clean:
            return alias
    return ""


def _replace_ai_hint_marker(text: str, alias: str) -> str:
    markers = (
        "Fix content fidelity before visual polish",
        "Fix planner-to-executor layout handoff",
        "Fix style-token compliance",
        "Fix output protocol first",
        "Fix visual-critic protocol before repair",
        "Fix planner coverage before SVG generation",
        "Fix numeric grounding",
        "Reduce source/slide density or increase max tokens",
        "Fix planner protocol first",
    )
    for marker in markers:
        if marker in text:
            return text.replace(marker, alias)
    return text


def _read_ai_iteration_results(path: Path) -> list[dict]:
    result_path = path if path.name == "AI-ITERATION.json" else path / "qa" / "AI-ITERATION.json"
    if result_path.exists():
        return [_read_ai_iteration_result_file(result_path)]
    if path.is_dir():
        child_results = sorted(path.glob("*/qa/AI-ITERATION.json"))
        if child_results:
            return [_read_ai_iteration_result_file(child) for child in child_results]
    raise FileNotFoundError(f"AI iteration result not found: {result_path}")


def _read_ai_iteration_result_file(result_path: Path) -> dict:
    if not result_path.exists():
        raise FileNotFoundError(f"AI iteration result not found: {result_path}")
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"AI iteration result must be a JSON object: {result_path}")
    payload = dict(payload)
    payload["result_path"] = str(result_path)
    payload["summary_hint"] = _ai_iteration_summary_hint(payload)
    return payload


def _format_ai_iteration_summary(rows: list[dict]) -> str:
    lines = [
        "AI iteration summary",
        "status | strict | ok-gate | cycles | repaired | latest-sev | issues | non-ok | repairs | render | executor | vision | run-trace | total-trace | failed | block | visual-used | prompt | raw | request | hint | project",
        "-------|--------|---------|--------|----------|------------|--------|--------|---------|--------|----------|--------|-----------|-------------|--------|-------|-------------|--------|-----|---------|------|--------",
    ]
    for row in rows:
        metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        models = row.get("models") if isinstance(row.get("models"), dict) else {}
        feedback = row.get("latest_visual_feedback") if isinstance(row.get("latest_visual_feedback"), dict) else {}
        cycles = row.get("repair_cycles") if isinstance(row.get("repair_cycles"), list) else []
        repaired_count = _ai_iteration_repaired_count(row)
        lines.append(
            " | ".join([
                str(row.get("status", "unknown")),
                "yes" if row.get("strict_qa") else "no",
                "yes" if row.get("require_visual_ok") else "no",
                str(len(cycles)),
                str(repaired_count),
                str(row.get("latest_visual_severity", "") or "-"),
                str(feedback.get("issue_count", "-")),
                str(feedback.get("non_ok_count", "-")),
                str(feedback.get("repair_prompt_count", "-")),
                str(row.get("latest_rendered_source", "") or "-"),
                str(models.get("executor", "") or "-"),
                str(models.get("vision", "") or "-"),
                str(row.get("trace_events", 0)),
                str(row.get("total_trace_events", row.get("trace_events", 0))),
                str(metrics.get("failed_events", "-")),
                str(metrics.get("blocking_count", "-")),
                str(metrics.get("visual_feedback_used_events", "-")),
                str(metrics.get("prompt_chars", "-")),
                str(metrics.get("raw_chars", "-")),
                str(metrics.get("request_chars", "-")),
                str(row.get("summary_hint") or _ai_iteration_summary_hint(row)),
                str(row.get("project", "") or row.get("result_path", "")),
            ])
        )
    return "\n".join(lines)


def _ai_iteration_repaired_count(row: dict) -> int:
    cycles = row.get("repair_cycles") if isinstance(row.get("repair_cycles"), list) else []
    return sum(
        len(cycle.get("repaired") or [])
        for cycle in cycles
        if isinstance(cycle, dict)
    )


def _ai_iteration_feedback_count(feedback: dict, key: str) -> int | None:
    value = feedback.get(key)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        text = str(value).strip()
        return int(text) if text else None
    except (TypeError, ValueError):
        return None


def _ai_iteration_summary_hint(row: dict) -> str:
    feedback = row.get("latest_visual_feedback") if isinstance(row.get("latest_visual_feedback"), dict) else {}
    status = str(row.get("status") or "unknown").strip().lower()
    severity = str(row.get("latest_visual_severity") or "").strip().lower()
    issues = _ai_iteration_feedback_count(feedback, "issue_count")
    non_ok = _ai_iteration_feedback_count(feedback, "non_ok_count")
    repair_prompts = _ai_iteration_feedback_count(feedback, "repair_prompt_count")
    actionable_repairs = _ai_iteration_feedback_count(feedback, "actionable_repair_count")
    repaired_count = _ai_iteration_repaired_count(row)
    repair_target_count = row.get("repair_target_count")

    parts: list[str] = []
    if repair_target_count:
        parts.append(f"targets={repair_target_count}")
    if severity and severity != "ok":
        parts.append(severity)
    for label, value in (
        ("issues", issues),
        ("non-ok", non_ok),
        ("repair-prompts", repair_prompts),
        ("actionable", actionable_repairs if actionable_repairs != repair_prompts else None),
        ("repaired", repaired_count if repaired_count else None),
    ):
        if value:
            parts.append(f"{label}={value}")
    detail = ",".join(parts)

    if status != "passed":
        if detail:
            return f"failed:{detail}"
        error = " ".join(str(row.get("error") or "").split())
        if error:
            return f"failed:{error[:120]}{'...' if len(error) > 120 else ''}"
        return "failed"
    if severity and severity != "ok":
        return f"passed-warning:{detail or severity}"
    if issues or non_ok or repair_prompts or actionable_repairs:
        return f"passed-warning:{detail or 'visual-feedback'}"
    if repaired_count:
        return f"repaired:{repaired_count}"
    return "passed"


def _read_ai_release_results(path: Path) -> list[dict]:
    result_path = path if path.name == "AI-RELEASE-CHECK.json" else path / "qa" / "AI-RELEASE-CHECK.json"
    if result_path.exists():
        return [_read_ai_release_result_file(result_path)]
    if path.is_dir():
        child_results = sorted(path.glob("*/qa/AI-RELEASE-CHECK.json"))
        if child_results:
            return [_read_ai_release_result_file(child) for child in child_results]
    raise FileNotFoundError(f"AI release result not found: {result_path}")


def _read_ai_release_result_file(result_path: Path) -> dict:
    if not result_path.exists():
        raise FileNotFoundError(f"AI release result not found: {result_path}")
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"AI release result must be a JSON object: {result_path}")
    payload = dict(payload)
    payload["result_path"] = str(result_path)
    payload["summary_hint"] = _ai_release_summary_hint(payload)
    return payload


def _ai_release_row_ready(row: dict) -> bool:
    gates = row.get("gates") if isinstance(row.get("gates"), dict) else {}
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    return (
        row.get("status") == "passed"
        and gates.get("release_ready") is True
        and summary.get("release_ready", True) is True
    )


def _format_ai_release_summary(rows: list[dict]) -> str:
    lines = [
        "AI release summary",
        "status | decision | ready | visual | smoke-sev | render | pptx | iter | repair | failed | block | warnings | hint | project",
        "-------|----------|-------|--------|-----------|--------|------|------|--------|--------|-------|----------|----------|--------",
    ]
    for row in rows:
        summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
        gates = row.get("gates") if isinstance(row.get("gates"), dict) else {}
        metrics = _ai_release_summary_metrics(row)
        lines.append(
            " | ".join([
                str(row.get("status", "unknown")),
                str(summary.get("decision") or ("release-ready" if gates.get("release_ready") else "not-release-ready")),
                "yes" if gates.get("release_ready") else "no",
                str(summary.get("final_visual_severity") or _ai_release_final_visual_severity_from_row(row) or "-"),
                str(summary.get("smoke_visual_severity") or _ai_release_smoke_visual_severity_from_row(row) or "-"),
                str(summary.get("rendered_source") or _ai_release_render_source_from_row(row) or "-"),
                "yes" if gates.get("rendered_source_pptx") else "no",
                "yes" if gates.get("visual_iteration_review") else "no",
                "yes" if gates.get("visual_repair_applied") else "no",
                str(metrics.get("failed_events", "-")),
                str(metrics.get("blocking_count", "-")),
                str(len(summary.get("warnings") if isinstance(summary.get("warnings"), list) else [])),
                str(row.get("summary_hint") or _ai_release_summary_hint(row)),
                str(row.get("project", "") or row.get("result_path", "")),
            ])
        )
    return "\n".join(lines)


def _ai_release_summary_metrics(row: dict) -> dict:
    iteration = row.get("iteration") if isinstance(row.get("iteration"), dict) else {}
    smoke = row.get("smoke") if isinstance(row.get("smoke"), dict) else {}
    metrics = iteration.get("total_metrics") if isinstance(iteration.get("total_metrics"), dict) else None
    if metrics is None:
        metrics = iteration.get("metrics") if isinstance(iteration.get("metrics"), dict) else None
    if metrics is None:
        metrics = smoke.get("metrics") if isinstance(smoke.get("metrics"), dict) else {}
    return metrics


def _ai_release_final_visual_severity_from_row(row: dict) -> str:
    iteration = row.get("iteration") if isinstance(row.get("iteration"), dict) else {}
    if str(iteration.get("latest_visual_severity") or ""):
        return str(iteration.get("latest_visual_severity") or "")
    smoke = row.get("smoke") if isinstance(row.get("smoke"), dict) else {}
    return _latest_smoke_visual_severity(smoke)


def _ai_release_smoke_visual_severity_from_row(row: dict) -> str:
    smoke = row.get("smoke") if isinstance(row.get("smoke"), dict) else {}
    return _latest_smoke_visual_severity(smoke)


def _ai_release_render_source_from_row(row: dict) -> str:
    iteration = row.get("iteration") if isinstance(row.get("iteration"), dict) else {}
    if str(iteration.get("latest_rendered_source") or ""):
        return str(iteration.get("latest_rendered_source") or "")
    smoke = row.get("smoke") if isinstance(row.get("smoke"), dict) else {}
    return str(smoke.get("rendered_source") or "")


def _compact_release_blockers(summary: dict) -> str:
    reasons = summary.get("blocking_reasons") if isinstance(summary.get("blocking_reasons"), list) else []
    if not reasons:
        return "-"
    text = "; ".join(str(reason).strip() for reason in reasons if str(reason).strip())
    text = " ".join(text.split())
    return text[:160] + ("..." if len(text) > 160 else "")


def _ai_release_summary_hint(row: dict) -> str:
    summary = row.get("summary") if isinstance(row.get("summary"), dict) else {}
    if not _ai_release_row_ready(row):
        repair_target_count = summary.get("repair_target_count")
        if repair_target_count:
            return f"blocked:repair-targets={repair_target_count}"
        provider_roles = _ai_release_provider_failure_roles(summary)
        if provider_roles:
            return f"blocked:provider={provider_roles}"
        blockers = _compact_release_blockers(summary)
        return f"blocked:{blockers}" if blockers != "-" else "blocked"
    warnings = summary.get("warnings") if isinstance(summary.get("warnings"), list) else []
    warning_text = "; ".join(str(item).strip() for item in warnings if str(item).strip())
    warning_text = " ".join(warning_text.split())
    if warning_text:
        warning_text = warning_text[:120] + ("..." if len(warning_text) > 120 else "")
        return f"ready-warning:{warning_text}"
    return "ready"


def _ai_release_provider_failure_roles(summary: dict) -> str:
    failures = summary.get("provider_failures") if isinstance(summary.get("provider_failures"), list) else []
    roles: list[str] = []
    seen: set[str] = set()
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        role = str(failure.get("role") or "").strip().lower()
        if not role or role in seen:
            continue
        roles.append(role)
        seen.add(role)
    return ",".join(roles)


def _copy_rendered_images(source_dir: Path, target_dir: Path) -> list[Path]:
    """Copy externally rendered slide images into the project QA evidence dir."""
    if not source_dir.exists():
        raise FileNotFoundError(f"rendered image directory not found: {source_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for path in sorted(source_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        dest = target_dir / path.name
        shutil.copy2(path, dest)
        copied.append(dest)
    if not copied:
        raise FileNotFoundError(f"no rendered slide images found in {source_dir}")
    return copied


def _render_visual_evidence(project: Path, deck: Path, rendered_dir: Path, *, dpi: int) -> str:
    """Render visual evidence for AI review, falling back to SVG previews if PPTX rendering is unavailable."""
    try:
        render_pptx(deck, rendered_dir, dpi=dpi)
        return "pptx-render"
    except RuntimeError as exc:
        if "Render dependencies are not ready" not in str(exc):
            raise
        render_svg_previews(project, rendered_dir)
        return "svg-preview"


def _existing_slide_svg(project: Path, slide: int) -> Path | None:
    for dirname in ("svg_output", "svg_final"):
        path = project / dirname / f"slide_{slide:02d}.svg"
        if path.exists():
            return path
    return None


def _extract_svg_text_lines(path: Path | None) -> list[str]:
    if path is None:
        return []
    text = path.read_text(encoding="utf-8")
    raw_parts = re.findall(r"<(?:text|tspan)\b[^>]*>(.*?)</(?:text|tspan)>", text, flags=re.IGNORECASE | re.DOTALL)
    lines: list[str] = []
    for part in raw_parts:
        cleaned = re.sub(r"<[^>]+>", "", part)
        cleaned = html.unescape(cleaned).strip()
        if re.fullmatch(r"\d{1,2}\s*/\s*\d{1,2}", cleaned):
            continue
        if cleaned:
            lines.append(cleaned)
    return lines


def _repair_body_from_args(args) -> str | None:
    if getattr(args, "body_file", None):
        return Path(args.body_file).read_text(encoding="utf-8")
    if getattr(args, "body", None) is not None:
        return args.body
    return None


def _content_items_from_body(body: str) -> list:
    from .content_planner import ContentItem

    bullet_re = re.compile(r"^\s*(?:[-*+]|\u2022|\u25e6|\u25aa|\u2023)\s+")
    items = []
    for line in body.splitlines():
        if not line.strip():
            continue
        is_bullet = bool(bullet_re.match(line))
        text = bullet_re.sub("", line).strip()
        if text:
            items.append(ContentItem(type="bullet" if is_bullet else "text", primary=text))
    return items


def _plan_source_slides(source_text: str, config, *, project: Path | None = None, args=None):
    planner = _resolve_planner_mode(args) if args is not None else "deterministic"
    if planner == "ai":
        from .ai_planner import plan_slides_with_ai
        return plan_slides_with_ai(
            source_text,
            config,
            project_path=project,
            **_planner_kwargs_from_args(args),
        )

    from .content_planner import plan_slides
    return plan_slides(source_text, config, project_path=str(project) if project else None)


def _repair_feedback_project(
    project: Path,
    *,
    ai_kwargs: dict,
    slide_indexes: list[int] | None = None,
    min_severity: str = "minor",
    layout: str | None = None,
) -> list[tuple[Path, Path]]:
    from .ai_executor import generate_svg_with_ai

    targets = slide_indexes or _slides_from_visual_feedback(project, min_severity=min_severity)
    if not targets:
        return []
    plans = [_repair_plan_from_existing_slide(project, slide, layout=layout) for slide in targets]
    paths = generate_svg_with_ai(project, plans, clear_output=False, **ai_kwargs)
    repaired: list[tuple[Path, Path]] = []
    for generated in paths:
        final_file = project / "svg_final" / generated.name
        if final_file.parent.exists():
            shutil.copy2(generated, final_file)
        repaired.append((generated, final_file))
    return repaired


def _run_ai_iteration_loop(
    project: Path,
    *,
    rounds: int,
    first_pptx: Path | None,
    dpi: int,
    min_severity: str,
    strict_qa: bool,
    require_visual_ok: bool,
    executor_kwargs: dict,
    vision_kwargs: dict,
) -> tuple[Path, Path]:
    if rounds < 1:
        raise ValueError("--rounds must be at least 1")
    if not (project / "spec_lock.json").exists():
        raise FileNotFoundError(f"no spec_lock.json in {project}")

    from .visual_critic import generate_visual_feedback
    from .ai_trace import read_ai_trace

    trace_start = len(read_ai_trace(project))
    deck = first_pptx or export_project(project)
    report: Path | None = None
    repaired_after_latest_review = False
    repair_cycles: list[dict] = []
    latest_rendered_dir: Path | None = None
    latest_rendered_source = ""
    try:
        for round_index in range(1, rounds + 1):
            rendered_dir = project / "qa" / f"rendered-round-{round_index:02d}"
            rendered_source = _render_visual_evidence(project, deck, rendered_dir, dpi=dpi)
            latest_rendered_dir = rendered_dir
            latest_rendered_source = rendered_source
            generate_visual_feedback(project, rendered_dir=rendered_dir, **vision_kwargs)
            repaired = _repair_feedback_project(
                project,
                ai_kwargs=executor_kwargs,
                min_severity=min_severity,
            )
            repair_cycles.append({
                "round": round_index,
                "rendered_dir": rendered_dir,
                "rendered_source": rendered_source,
                "repaired": repaired,
            })
            if not repaired:
                repaired_after_latest_review = False
                break
            repaired_after_latest_review = True
            finalize_svg(project)
            deck = export_project(project)

        if repaired_after_latest_review:
            rendered_dir = project / "qa" / "rendered-final"
            latest_rendered_source = _render_visual_evidence(project, deck, rendered_dir, dpi=dpi)
            latest_rendered_dir = rendered_dir
            generate_visual_feedback(project, rendered_dir=rendered_dir, **vision_kwargs)
    except _AI_COMMAND_ERRORS as exc:
        _write_ai_fix_verify(project, deck, repair_cycles, latest_rendered_dir)
        _write_ai_iteration_result(
            project,
            deck,
            report or (project / "qa" / "QA.md"),
            strict_qa=strict_qa,
            require_visual_ok=require_visual_ok,
            repair_cycles=repair_cycles,
            latest_rendered_dir=latest_rendered_dir,
            latest_rendered_source=latest_rendered_source,
            trace_start=trace_start,
            status="failed",
            error=str(exc),
        )
        raise

    _write_ai_fix_verify(project, deck, repair_cycles, latest_rendered_dir)
    ok, report = run_qa(
        project,
        deck,
        require_visual=strict_qa or require_visual_ok,
        require_fix_verify=strict_qa,
    )
    if strict_qa and not ok:
        _write_ai_iteration_result(
            project,
            deck,
            report,
            strict_qa=strict_qa,
            require_visual_ok=require_visual_ok,
            repair_cycles=repair_cycles,
            latest_rendered_dir=latest_rendered_dir,
            latest_rendered_source=latest_rendered_source,
            trace_start=trace_start,
            status="failed",
            error=f"strict QA failed: {report}",
        )
        raise RuntimeError(f"strict QA failed: {report}")
    latest_visual_severity = _visual_feedback_max_severity(project / "qa" / "visual-feedback.json")
    if require_visual_ok and latest_visual_severity != "ok":
        error = f"visual-ok gate failed: latest visual severity is {latest_visual_severity or 'unknown'}"
        _write_ai_iteration_result(
            project,
            deck,
            report,
            strict_qa=strict_qa,
            require_visual_ok=require_visual_ok,
            repair_cycles=repair_cycles,
            latest_rendered_dir=latest_rendered_dir,
            latest_rendered_source=latest_rendered_source,
            trace_start=trace_start,
            status="failed",
            error=error,
        )
        raise RuntimeError(error)
    _write_ai_iteration_result(
        project,
        deck,
        report,
        strict_qa=strict_qa,
        require_visual_ok=require_visual_ok,
        repair_cycles=repair_cycles,
        latest_rendered_dir=latest_rendered_dir,
        latest_rendered_source=latest_rendered_source,
        trace_start=trace_start,
    )
    return deck, report


def _write_ai_iteration_result(
    project: Path,
    deck: Path,
    report: Path,
    *,
    strict_qa: bool,
    require_visual_ok: bool,
    repair_cycles: list[dict],
    latest_rendered_dir: Path | None,
    latest_rendered_source: str,
    trace_start: int,
    status: str | None = None,
    error: str = "",
) -> Path:
    """Write machine-readable evidence for an AI visual iteration run."""
    from .ai_trace import read_ai_trace
    from .util import ensure_dir

    events = read_ai_trace(project)
    run_events = events[trace_start:]
    latest_visual_severity = _visual_feedback_max_severity(project / "qa" / "visual-feedback.json")
    result = {
        "status": status or "passed",
        "error": error,
        "project": str(project),
        "deck": str(deck),
        "qa_report": str(report),
        "strict_qa": strict_qa,
        "require_visual_ok": require_visual_ok,
        "fix_verify": str(project / "qa" / "FIX-VERIFY.md"),
        "latest_rendered_dir": str(latest_rendered_dir or ""),
        "latest_rendered_source": latest_rendered_source,
        "latest_visual_severity": latest_visual_severity,
        "latest_visual_feedback": _visual_feedback_stats(project / "qa" / "visual-feedback.json"),
        "models": _ai_iteration_role_models(run_events),
        "trace_events": len(run_events),
        "total_trace_events": len(events),
        "trace_start": trace_start,
        "metrics": _ai_smoke_metrics(run_events),
        "total_metrics": _ai_smoke_metrics(events),
        "repair_cycles": [
            {
                "round": cycle.get("round"),
                "rendered_dir": str(cycle.get("rendered_dir") or ""),
                "rendered_source": str(cycle.get("rendered_source") or ""),
                "repaired": [
                    {"generated": str(generated), "final": str(final_file)}
                    for generated, final_file in (cycle.get("repaired") or [])
                ],
            }
            for cycle in repair_cycles
        ],
    }
    _append_ai_iteration_repair_targets(result, project, latest_visual_severity=latest_visual_severity)
    path = ensure_dir(project / "qa") / "AI-ITERATION.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _append_ai_iteration_repair_targets(result: dict, project: Path, *, latest_visual_severity: str) -> None:
    severity = str(latest_visual_severity or "").lower()
    if severity in {"", "ok", "invalid"}:
        return
    from .ai_trace import format_cli_path, visual_repair_targets

    targets = visual_repair_targets(project, min_severity="minor")
    if not targets:
        return
    result["repair_targets"] = targets[:3]
    result["repair_target_count"] = len(targets)
    if len(targets) > 3:
        result["repair_targets_more"] = len(targets) - 3
    result["repair_command"] = f"slide-skill repair-feedback {format_cli_path(project)} --min-severity minor"


def _ai_iteration_role_models(events: list[dict]) -> dict:
    models: dict[str, str] = {"executor": "", "vision": ""}
    for event in events:
        stage = str(event.get("stage") or "")
        model = str(event.get("model") or "")
        if not model:
            continue
        if stage == "executor":
            models["executor"] = model
        elif stage == "visual-critic":
            models["vision"] = model
    return models


def _write_ai_fix_verify(project: Path, deck: Path, repair_cycles: list[dict], latest_rendered_dir: Path | None) -> Path:
    """Write fix-and-verify evidence for the AI visual iteration loop."""
    qa_dir = project / "qa"
    feedback_path = qa_dir / "visual-feedback.json"
    max_severity = _visual_feedback_max_severity(feedback_path)
    feedback_stats = _visual_feedback_stats(feedback_path)
    lines = [
        "# Fix And Verify",
        "",
        "Generated by `slide-skill iterate-ai`.",
        "",
        f"- Deck: `{deck}`",
        f"- Latest rendered evidence: `{latest_rendered_dir}`" if latest_rendered_dir else "- Latest rendered evidence: not recorded",
        f"- Latest AI visual feedback max severity: {max_severity or 'unknown'}",
        (
            "- Latest AI visual feedback stats: "
            f"{feedback_stats['slides_reviewed']} slide(s), "
            f"{feedback_stats['issue_count']} issue(s), "
            f"{feedback_stats['non_ok_count']} non-ok slide(s), "
            f"{feedback_stats['repair_prompt_count']} repair prompt(s), "
            f"{feedback_stats['actionable_repair_count']} actionable repair(s)"
        ),
        "",
    ]
    summaries = feedback_stats.get("summaries") if isinstance(feedback_stats.get("summaries"), list) else []
    if summaries:
        lines.append("## Latest Visual Feedback Summary")
        for summary in summaries:
            lines.append(f"- {summary}")
        lines.append("")
    lines.append("## Repair Cycles")
    if not repair_cycles:
        lines.append("- No visual review cycles were recorded.")
    for cycle in repair_cycles:
        repaired = cycle.get("repaired") or []
        lines.append(f"### Round {cycle.get('round', '-')}")
        lines.append(f"- Rendered evidence: `{cycle.get('rendered_dir')}`")
        if repaired:
            for generated, final_file in repaired:
                lines.append(f"- Repaired `{generated.name}`; updated final: `{final_file}`")
        else:
            lines.append("- No slides met the configured repair severity threshold.")
        lines.append("")
    path = qa_dir / "FIX-VERIFY.md"
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _visual_feedback_stats(feedback_path: Path) -> dict:
    """Summarize the latest persisted visual feedback without duplicating review text."""
    empty = {
        "status": "missing",
        "slides_reviewed": 0,
        "issue_count": 0,
        "action_count": 0,
        "repair_prompt_count": 0,
        "actionable_repair_count": 0,
        "non_ok_count": 0,
        "summaries": [],
    }
    if not feedback_path.exists():
        return empty
    try:
        payload = json.loads(feedback_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        result = dict(empty)
        result["status"] = "invalid"
        return result

    slides = payload.get("slides", []) if isinstance(payload, dict) else []
    if not isinstance(slides, list):
        result = dict(empty)
        result["status"] = "invalid"
        return result

    order = {"ok", "minor", "major", "critical"}
    summaries: list[str] = []
    issue_count = 0
    action_count = 0
    repair_prompt_count = 0
    actionable_repair_count = 0
    non_ok_count = 0
    slides_reviewed = 0
    for item in slides:
        if not isinstance(item, dict):
            continue
        slides_reviewed += 1
        severity = str(item.get("severity", "")).lower()
        if severity in order and severity != "ok":
            non_ok_count += 1
        issues = item.get("issues") if isinstance(item.get("issues"), list) else []
        actions = item.get("actions") if isinstance(item.get("actions"), list) else []
        issue_count += len(issues)
        action_count += len(actions) or int(_has_visual_feedback_content(item.get("action")))
        if str(item.get("repair_prompt") or "").strip():
            repair_prompt_count += 1
        if severity in order and severity != "ok" and _has_actionable_visual_repair(item):
            actionable_repair_count += 1
        summary = str(item.get("summary") or "").strip()
        slide = item.get("slide") or item.get("slide_index") or item.get("page") or item.get("index")
        if summary and len(summaries) < 3:
            prefix = f"slide {slide}: " if slide is not None else ""
            summaries.append((prefix + summary)[:240])

    return {
        "status": "ok",
        "slides_reviewed": slides_reviewed,
        "issue_count": issue_count,
        "action_count": action_count,
        "repair_prompt_count": repair_prompt_count,
        "actionable_repair_count": actionable_repair_count,
        "non_ok_count": non_ok_count,
        "summaries": summaries,
    }


def _has_actionable_visual_repair(item: dict) -> bool:
    if str(item.get("repair_prompt") or "").strip():
        return True
    return _has_visual_feedback_content(item.get("actions")) or _has_visual_feedback_content(item.get("action"))


def _has_visual_feedback_content(value) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, list):
        return any(_has_visual_feedback_content(item) for item in value)
    if isinstance(value, dict):
        return any(_has_visual_feedback_content(item) for item in value.values())
    return bool(str(value).strip())


def _visual_feedback_max_severity(feedback_path: Path) -> str:
    if not feedback_path.exists():
        return ""
    try:
        payload = json.loads(feedback_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "invalid"
    order = {"ok": 0, "minor": 1, "major": 2, "critical": 3}
    highest = ""
    highest_rank = -1
    for item in payload.get("slides", []):
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity", "")).lower()
        rank = order.get(severity)
        if rank is not None and rank > highest_rank:
            highest = severity
            highest_rank = rank
    return highest


def _repair_plan_from_existing_slide(project: Path, slide: int, *, layout: str | None = None):
    from dataclasses import replace

    from .content_planner import ContentItem, SlidePlan

    planned = _planned_slide_from_ai_plan(project, slide)
    if planned:
        repair_note = "Repair this slide using QA feedback and rendered visual review observations."
        updates = {}
        if layout:
            updates["layout"] = layout
        updates["notes"] = f"{planned.notes}\n\n{repair_note}".strip() if planned.notes else repair_note
        return replace(planned, **updates)

    current_svg = _existing_slide_svg(project, slide)
    existing_lines = _extract_svg_text_lines(current_svg) if current_svg else []
    title = existing_lines[0] if existing_lines else f"Slide {slide}"
    body = "\n".join(existing_lines[1:]).strip()
    items = _content_items_from_body(body)
    if not items:
        items = [ContentItem(type="text", primary="Preserve the current slide content while fixing visual feedback.")]
    return SlidePlan(
        index=slide,
        layout=layout or "bullet-list",
        title=title,
        items=items,
        rhythm="breathing",
        visual_strategy="visual-repair",
        notes="Repair this slide using QA feedback and rendered visual review observations.",
    )


def _planned_slide_from_ai_plan(project: Path, slide: int):
    from .content_planner import ContentItem, SlidePlan

    plan_path = project / "qa" / "ai-planner" / "plan.json"
    if not plan_path.exists():
        return None
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return None
    for entry in payload:
        if not isinstance(entry, dict) or int(entry.get("index") or 0) != slide:
            continue
        raw_items = entry.get("items") if isinstance(entry.get("items"), list) else []
        items = [
            ContentItem(
                type=str(item.get("type") or "text"),
                primary=str(item.get("primary") or ""),
                secondary=str(item.get("secondary") or ""),
                tertiary=str(item.get("tertiary") or ""),
                meta=item.get("meta") if isinstance(item.get("meta"), dict) else {},
            )
            for item in raw_items
            if isinstance(item, dict) and str(item.get("primary") or "").strip()
        ]
        return SlidePlan(
            index=slide,
            layout=str(entry.get("layout") or "bullet-list"),
            title=str(entry.get("title") or f"Slide {slide}"),
            items=items,
            notes=str(entry.get("notes") or ""),
            density=str(entry.get("density") or "normal"),
            rhythm=str(entry.get("rhythm") or ""),
            meta=entry.get("meta") if isinstance(entry.get("meta"), dict) else {},
            visual_strategy=str(entry.get("visual_strategy") or ""),
            chart_type=str(entry.get("chart_type") or ""),
            image_hint=str(entry.get("image_hint") or ""),
            layout_pattern=str(entry.get("layout_pattern") or ""),
        )
    return None


def _slides_from_visual_feedback(project: Path, *, min_severity: str = "minor") -> list[int]:
    feedback_path = project / "qa" / "visual-feedback.json"
    if not feedback_path.exists():
        raise FileNotFoundError(f"visual feedback not found: {feedback_path}")
    from .ai_trace import visual_repair_targets

    slides = []
    for target in visual_repair_targets(project, min_severity=min_severity):
        try:
            slides.append(int(target["slide"]))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(set(slides))

def _configure_stdio_for_model_text() -> None:
    """Avoid Windows console encoding crashes when model output contains Unicode."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
