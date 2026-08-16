"""AI Executor — LLM-driven per-page SVG generation.

Reads spec_lock + design guide + executor references + per-slide design intent,
constructs a prompt for each slide, calls an LLM via OpenAI-compatible API,
and writes the SVG output.  Optionally runs post-generation quality checks.

Defaults to OpenAI-compatible mode (works with OpenAI, DeepSeek, Ollama,
vLLM, LiteLLM, any server exposing /v1/chat/completions).

Usage:
    from .ai_executor import generate_svg_with_ai
    generate_svg_with_ai(project_path, plans)

Environment variables:
    OPENAI_API_KEY   — API key (required for cloud providers)
    OPENAI_BASE_URL  — API base URL (default: https://api.openai.com/v1)
"""

from __future__ import annotations

import json
import html
import os
import re
import shutil
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from .ai_trace import ai_response_metadata, write_ai_trace
from .provider_response import (
    DEFAULT_ROLE_MAX_TOKENS,
    TruncatedResponseError,
    escalate_budget,
    parse_provider_response,
)
from .util import ensure_dir, xml_escape

# Defaults
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o"
_DEFAULT_MAX_TOKENS = DEFAULT_ROLE_MAX_TOKENS["executor"]
_DEFAULT_TEMPERATURE = 0.7
_MAX_RETRIES = 3
_MAX_FEEDBACK_ITEMS = 12
_MAX_VISUAL_FEEDBACK_CHARS = 2400
_VISUAL_FEEDBACK_MD = "VISUAL-REVIEW.md"
_VISUAL_FEEDBACK_JSON = "visual-feedback.json"


class ProviderAuthError(RuntimeError):
    """A provider rejected a key's credentials (CONC-04).

    Raised after key isolation so the pool owner can rotate to a surviving
    key. Never carries key material — only the class signal.
    """


def _classify_provider_error(exc: Exception) -> str:
    """Classify a provider exception for the CONC-04 error policy.

    ``auth``       -> isolate the key, never retry it.
    ``rate_limit`` -> honor Retry-After, then retry the same key.
    ``transient``  -> retry by the normal attempt policy.
    ``fatal``      -> anything else (surfaces through the retry policy).
    """
    name = type(exc).__name__
    status = getattr(exc, "status_code", None)
    if "Authentication" in name or "PermissionDenied" in name or status == 401:
        return "auth"
    if "RateLimit" in name or status == 429:
        return "rate_limit"
    if (
        "Connection" in name
        or "Timeout" in name
        or isinstance(exc, (TimeoutError, OSError))
    ):
        return "transient"
    return "fatal"


def _retry_after_seconds(exc: Exception, *, default: float = 5.0, cap: float = 60.0) -> float:
    """Honor the provider's Retry-After when present (CONC-04)."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return min(max(value, 0.0), cap)


def _concurrency_key_pool() -> list[str]:
    """Usable provider keys for the concurrency pool (CONC-01).

    Keys are read ONLY from the environment: ``OPENAI_API_KEYS`` (comma-
    separated) falling back to ``OPENAI_API_KEY``. Never from CLI args,
    source files, fixtures, or examples — a key must never be able to leak
    through a command line or a committed artifact.
    """
    raw = os.environ.get("OPENAI_API_KEYS", "") or os.environ.get("OPENAI_API_KEY", "")
    seen: dict[str, None] = {}
    for key in raw.split(","):
        key = key.strip()
        if key:
            seen.setdefault(key, None)
    return list(seen)


def generate_svg_with_ai(
    project_path: Path | str,
    plans: list,
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
    temperature: float = _DEFAULT_TEMPERATURE,
    top_p: float | None = None,
    system_prompt_extra: str = "",
    run_qa: bool = True,
    qa_retries: int = _MAX_RETRIES,
    strict_quality: bool = True,
    clear_output: bool = True,
    deck_total: int | None = None,
    ai_concurrency: int = 1,
) -> list[Path]:
    """Generate SVG pages using an LLM via OpenAI-compatible API.

    Args:
        project_path: Path to the project directory.
        plans: List of SlidePlan objects from content_planner.
        model: LLM model ID (default: OPENAI_MODEL env or gpt-4o).
        api_key: API key (default: OPENAI_API_KEY env var).
        base_url: API base URL (default: OPENAI_BASE_URL env or
                  https://api.openai.com/v1).
        max_tokens: Max tokens per completion.
        temperature: Sampling temperature (0.0–2.0).
        top_p: Nucleus sampling parameter (optional).
        system_prompt_extra: Additional text appended to system prompt.
        run_qa: Run post-generation SVG QA on each generated page.
        qa_retries: Number of LLM repair attempts after a page fails QA.
        strict_quality: Treat design-quality warnings as blocking feedback.
        clear_output: Remove existing SVG output before generation.
        deck_total: Total deck slide count for targeted repairs.
        ai_concurrency: Bounded worker count for the key-slot pool
                        (CONC-01). Default 1 = serial. Pool keys come ONLY
                        from the environment (OPENAI_API_KEYS comma-
                        separated, else OPENAI_API_KEY) — never CLI args,
                        source files, or fixtures.

    Returns:
        List of paths to generated SVG files.
    """
    from openai import OpenAI

    project = Path(project_path)
    spec_lock, spec_lock_text = _load_spec_lock(project)
    out_dir = ensure_dir(project / "svg_output")
    if clear_output:
        for old in out_dir.glob("*.svg"):
            old.unlink()
    log_dir = ensure_dir(project / "qa" / "executor")
    attempt_svg_dir = ensure_dir(log_dir / "attempt-svg")

    canvas = spec_lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])

    design_guide = _load_design_guide(project)
    references = _load_reference_materials(project, spec_lock)

    # Resolve parameters with env var fallbacks
    _key = api_key or os.environ.get("OPENAI_API_KEY", "")
    _base = base_url or os.environ.get("OPENAI_BASE_URL", _DEFAULT_BASE_URL)
    _model = model or os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL)

    total = deck_total or _infer_deck_total(project, plans, include_existing=not clear_output)
    paths: list[Path] = []

    def _generate_plan(plan, client, previous_paths, *, attempt_dir=None):
        """Generate one slide through the attempt/repair loop.

        CONC-02: ``previous_paths`` is an immutable snapshot owned by the
        caller - the serial path passes completed pages for the layout
        diversity hint; concurrent workers pass [] so no page depends on
        another page being finished first. ``attempt_dir`` isolates a
        worker attempt directory (CONC-03).
        """
        path = out_dir / f"slide_{plan.index:02d}.svg"
        feedback = ""
        final_issues = []
        current_max_tokens = max_tokens

        for attempt in range(qa_retries + 1):
            attempt_path = (attempt_dir or attempt_svg_dir) / f"slide_{plan.index:02d}_attempt_{attempt + 1:02d}.svg"
            try:
                spec_lock, spec_lock_text = _load_spec_lock(project)
                print(f"[executor] slide {plan.index:02d} attempt {attempt + 1}: spec_lock re-read from disk", file=sys.stderr)
            except (FileNotFoundError, ValueError) as exc:
                raise FileNotFoundError(
                    f"spec_lock became unreadable during slide {plan.index} attempt {attempt + 1}: {exc}"
                ) from exc
            canvas = spec_lock.get("canvas", {})
            prompt_w, prompt_h = int(canvas.get("width", w)), int(canvas.get("height", h))
            system_prompt = _build_system_prompt(
                spec_lock, prompt_w, prompt_h,
                extra=system_prompt_extra,
                design_guide=design_guide,
                references=references,
            )
            executor_brief = _load_executor_brief(project, plan.index)
            visual_feedback = _load_visual_feedback(project, plan.index)
            user_prompt = _build_page_prompt(
                plan, total, spec_lock, design_guide, prompt_w, prompt_h, previous_paths,
                spec_lock_text=spec_lock_text,
                executor_brief=executor_brief,
                feedback=feedback,
                visual_feedback=visual_feedback,
            )

            request_payload = _build_generation_request(
                _model,
                current_max_tokens,
                temperature,
                top_p,
                system_prompt,
                user_prompt,
            )
            try:
                svg_content, raw_content, extraction_issues, response_metadata = _generate_once(client, request_payload)
            except TruncatedResponseError as exc:
                # Completion-status gate: the attempt is truncated, NOT a QA
                # failure. Retry the same prompt with a raised budget and
                # never hand truncated content to SVG extraction or QA.
                provider = exc.response
                error = (
                    f"provider response truncated (finish_reason={provider.finish_reason or 'missing'}) "
                    f"at max_tokens={current_max_tokens}; content never reached SVG extraction"
                )
                write_ai_trace(
                    project,
                    stage="executor",
                    model=_model,
                    status="truncated",
                    prompt=user_prompt,
                    raw=provider.content,
                    request=request_payload,
                    attempt=attempt + 1,
                    metadata={
                        "slide": plan.index,
                        "path": str(attempt_path),
                        "publish_path": str(path),
                        "has_qa_feedback": bool(feedback),
                        "has_executor_brief": bool(executor_brief),
                        "has_visual_feedback": bool(visual_feedback),
                        "error": error,
                        **provider.trace_metadata(),
                    },
                )
                _write_attempt_log(
                    log_dir, plan.index, attempt, attempt_path, provider.content, [],
                    blocking_count=1,
                    executor_brief=executor_brief,
                    visual_feedback=visual_feedback,
                    error=error,
                )
                if attempt >= qa_retries:
                    raise RuntimeError(
                        f"AI executor response stayed truncated for {path.name} after "
                        f"{qa_retries + 1} attempts (last budget {current_max_tokens} tokens); "
                        "reduce slide density or raise the executor max-tokens budget"
                    ) from exc
                escalated = escalate_budget(current_max_tokens)
                if escalated == current_max_tokens:
                    raise RuntimeError(
                        f"AI executor response still truncated at the {current_max_tokens}-token budget cap "
                        f"for {path.name}; reduce slide density or raise the executor max-tokens budget cap"
                    ) from exc
                current_max_tokens = escalated
                continue
            except Exception as exc:  # noqa: BLE001 - provider SDKs expose many exception classes.
                # CONC-04 error policy: auth failures isolate the key
                # (surfaced for pool rotation, never retried in place);
                # rate limits honor Retry-After before the retry proceeds.
                error_kind = _classify_provider_error(exc)
                if error_kind == "auth":
                    raise ProviderAuthError(
                        "provider rejected this key's credentials; "
                        "key isolated from the pool"
                    ) from exc
                if error_kind == "rate_limit":
                    delay = _retry_after_seconds(exc)
                    print(
                        f"[executor] rate limited; honoring Retry-After ({delay:.0f}s)",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                error = _provider_error_message(exc)
                write_ai_trace(
                    project,
                    stage="executor",
                    model=_model,
                    status="failed",
                    prompt=user_prompt,
                    raw="",
                    request=request_payload,
                    attempt=attempt + 1,
                    metadata={
                        "slide": plan.index,
                        "path": str(attempt_path),
                        "publish_path": str(path),
                        "blocking_count": 1,
                        "blocking_issues": [error],
                        "has_qa_feedback": bool(feedback),
                        "has_executor_brief": bool(executor_brief),
                        "has_visual_feedback": bool(visual_feedback),
                        "provider_error": True,
                        "error": error,
                    },
                )
                _write_attempt_log(
                    log_dir, plan.index, attempt, attempt_path, "", [],
                    blocking_count=1,
                    executor_brief=executor_brief,
                    visual_feedback=visual_feedback,
                    error=error,
                )
                if attempt >= qa_retries:
                    raise RuntimeError(
                        f"AI executor provider call failed for {path.name} after "
                        f"{qa_retries + 1} attempts: {error}"
                    ) from exc
                feedback = f"Provider call failed before SVG output: {error}. Retry the same slide request."
                continue
            attempt_path.write_text(svg_content, encoding="utf-8")

            final_issues = _validate_svg_attempt(
                project, attempt_path,
                svg_text=svg_content,
                plan=plan,
                visual_feedback=visual_feedback,
                run_qa=run_qa,
                strict_quality=strict_quality,
                preflight_issues=extraction_issues,
            )
            # QA-02: big-numeral overlap/overflow verdicts are re-checked
            # against real browser bboxes when Chrome exists; measured-clean
            # static issues are dropped before they can block or trigger
            # repair loops. geometry_info lands in the attempt trace.
            final_issues, geometry_info = _arbitrate_static_text_geometry(
                svg_content, final_issues,
            )
            blocking = _blocking_issues(final_issues, strict_quality=strict_quality)
            # GATE-01 (v5.1 phase 57): render-convergence gate at publication.
            # A page whose structural QA is clean but whose render is a black
            # frame must not publish — it loops back into repair instead.
            # Honesty preserved: no browser -> capability gap, never a block.
            # Not tied to run_qa: render convergence is the publish criterion
            # itself, not an optional QA step.
            if not blocking:
                render_ok, render_reason = _browser_render_gate(attempt_path)
                if not render_ok:
                    from .svg_qa import SvgIssue

                    blocking = [SvgIssue("error", str(attempt_path), render_reason)]
            auto_wrap_repaired = False
            auto_contrast_repaired = False

            # Auto-repair: text-overflow. Mirrors the deterministic path's fitted_tspans/kinsoku
            # wrapping (commits 1d78b4d, 23dce0f) but as a post-generation patch on the AI executor's own
            # SVG. Cheaper and more reliable than asking the model to redraw. The patch only
            # replaces the attempt file after candidate validation passes (validate-before-replace).
            if blocking and all("overflow" in issue.message.lower() for issue in blocking):
                canvas_now = spec_lock.get("canvas", {})
                aw = int(canvas_now.get("width", w))
                ah = int(canvas_now.get("height", h))
                patched = _auto_wrap_overflowing_text(
                    svg_content, [issue.message for issue in blocking], aw, ah,
                )
                if patched is not None:
                    accepted, reissue_issues = _apply_validated_repair(
                        project, attempt_path, svg_content, patched,
                        plan=plan,
                        visual_feedback=visual_feedback,
                        run_qa=run_qa,
                        strict_quality=strict_quality,
                        repair_kind="auto-wrap",
                        model=_model,
                        attempt=attempt + 1,
                        slide_index=plan.index,
                    )
                    if accepted:
                        svg_content = patched
                        raw_content = patched
                        final_issues = reissue_issues
                        blocking = []
                        auto_wrap_repaired = True
                    # else: candidate rejected; original attempt SVG untouched, fall through to retry.
            # Auto-repair: low text contrast. Mirrors the deterministic path's muted->body
            # fix (43f9bca) — the largest defect class in the baseline (43%). Upgrades
            # the offending fill to a higher-contrast palette role locally instead of
            # spending an LLM retry (which often reproduces the same low-contrast choice).
            elif blocking and all("Low text contrast" in issue.message for issue in blocking):
                patched = _auto_repair_low_contrast(
                    svg_content, [issue.message for issue in blocking], spec_lock,
                )
                if patched is not None:
                    accepted, reissue_issues = _apply_validated_repair(
                        project, attempt_path, svg_content, patched,
                        plan=plan,
                        visual_feedback=visual_feedback,
                        run_qa=run_qa,
                        strict_quality=strict_quality,
                        repair_kind="auto-contrast",
                        model=_model,
                        attempt=attempt + 1,
                        slide_index=plan.index,
                    )
                    if accepted:
                        svg_content = patched
                        raw_content = patched
                        final_issues = reissue_issues
                        blocking = []
                        auto_contrast_repaired = True
                    # else: candidate rejected; original attempt SVG untouched, fall through to retry.

            _write_attempt_log(
                log_dir, plan.index, attempt, attempt_path, raw_content, final_issues,
                blocking_count=len(blocking),
                executor_brief=executor_brief,
                visual_feedback=visual_feedback,
            )
            write_ai_trace(
                project,
                stage="executor",
                model=_model,
                status=("passed (auto-wrapped)" if auto_wrap_repaired
                        else ("passed (auto-contrast)" if auto_contrast_repaired
                        else ("passed" if not blocking else "failed"))),
                prompt=user_prompt,
                raw=raw_content,
                request=request_payload,
                attempt=attempt + 1,
                metadata={
                    "slide": plan.index,
                    "path": str(attempt_path),
                    "publish_path": str(path),
                    "blocking_count": len(blocking),
                    "blocking_issues": _issue_message_preview(blocking),
                    "auto_wrap_repair": auto_wrap_repaired,
                    "auto_contrast_repair": auto_contrast_repaired,
                    "has_qa_feedback": bool(feedback),
                    "has_executor_brief": bool(executor_brief),
                    "has_visual_feedback": bool(visual_feedback),
                    **(geometry_info or {}),
                    **response_metadata,
                },
            )
            if not blocking:
                shutil.copy2(attempt_path, path)
                break
            if attempt >= qa_retries:
                details = _format_issue_feedback(blocking)
                raise RuntimeError(
                    f"AI SVG generation failed QA for {path.name} after "
                    f"{qa_retries + 1} attempts:\n{details}"
                )
            feedback = _format_issue_feedback(blocking)

        return path

    # -- CONC-01..03 (v5.1 phase 58): bounded key-slot concurrency -----------
    ai_concurrency = max(1, int(ai_concurrency or 1))
    key_pool = _concurrency_key_pool() if ai_concurrency > 1 else []
    max_workers = min(ai_concurrency, len(key_pool), len(plans)) if key_pool else 1
    if ai_concurrency > 1 and max_workers <= 1:
        print(
            "[executor] --ai-concurrency > 1 requested but no usable key pool "
            "(set OPENAI_API_KEYS as a comma-separated list, or OPENAI_API_KEY); "
            "running serial with one key",
            file=sys.stderr,
        )

    if max_workers > 1:
        import queue as _queue
        import threading
        from concurrent.futures import ThreadPoolExecutor

        key_queue: "_queue.Queue[str]" = _queue.Queue()
        for _pool_key in key_pool:
            key_queue.put(_pool_key)
        clients_by_key: dict[str, object] = {}
        alive_lock = threading.Lock()
        alive_keys = [len(key_pool)]

        def _run_plan(plan):
            # Key-slot discipline: at most one in-flight request per key -
            # a worker holds its key for the whole page (attempts + QA).
            # CONC-04: an auth-rejected key is isolated (never returned to
            # the pool) and the page rotates to a surviving key; when no
            # keys remain the deck fails wholesale. The get() is bounded:
            # when every key ends up isolated, blocked getters must wake
            # up and fail instead of waiting for a key that never returns.
            while True:
                try:
                    key = key_queue.get(timeout=30)
                except _queue.Empty:
                    with alive_lock:
                        remaining = alive_keys[0]
                    if remaining <= 0:
                        raise RuntimeError(
                            "all provider keys isolated after auth failures; "
                            "deck aborted wholesale"
                        ) from None
                    continue
                if key is None:
                    # Sentinel pushed when the pool hit zero alive keys.
                    raise RuntimeError(
                        "all provider keys isolated after auth failures; "
                        "deck aborted wholesale"
                    ) from None
                isolated = False
                try:
                    cl = clients_by_key.get(key)
                    if cl is None:
                        cl = OpenAI(api_key=key, base_url=_base)
                        clients_by_key[key] = cl
                    page_attempt_dir = attempt_svg_dir / f"slide_{plan.index:02d}"
                    page_attempt_dir.mkdir(parents=True, exist_ok=True)
                    return _generate_plan(
                        plan, cl, [], attempt_dir=page_attempt_dir,
                    )
                except ProviderAuthError:
                    isolated = True
                    with alive_lock:
                        alive_keys[0] -= 1
                        remaining = alive_keys[0]
                    print(
                        "[executor] provider key isolated after auth failure; "
                        f"{remaining} key(s) remain in the pool",
                        file=sys.stderr,
                    )
                    if remaining <= 0:
                        # Wake every blocked/queued getter so the pool
                        # drains fast (upper bound: one waiter per plan).
                        for _ in range(len(plans)):
                            key_queue.put(None)
                        raise RuntimeError(
                            "all provider keys isolated after auth failures; "
                            "deck aborted wholesale"
                        ) from None
                    continue
                finally:
                    if not isolated:
                        key_queue.put(key)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run_plan, plan): plan for plan in plans}
            errors: list[str] = []
            for future in futures:
                try:
                    paths.append(future.result())
                except Exception as exc:  # noqa: BLE001 - collect every page failure
                    errors.append(f"{exc.__class__.__name__}: {exc}")
            if errors:
                # CONC-04: a failed page fails the deck wholesale - no
                # partial export can proceed from a partial page set.
                raise RuntimeError(
                    "concurrent executor failed for "
                    f"{len(errors)} page(s); deck aborted wholesale:\n"
                    + "\n".join(errors[:5])
                )
        paths.sort(key=lambda p: p.name)
    else:
        client = OpenAI(api_key=_key, base_url=_base)
        for plan in plans:
            paths.append(_generate_plan(plan, client, list(paths)))


    if run_qa:
        _run_quality_check(project, spec_lock, paths, strict_quality=strict_quality)

    return paths


def _load_spec_lock(project: Path) -> tuple[dict, str]:
    """Load structured and prompt-facing spec lock data from disk."""
    json_path = project / "spec_lock.json"
    md_path = project / "spec_lock.md"
    if not json_path.exists():
        raise FileNotFoundError(f"spec_lock.json not found in {project}")
    spec_lock = json.loads(json_path.read_text(encoding="utf-8"))
    if md_path.exists():
        spec_lock_text = md_path.read_text(encoding="utf-8")
    else:
        spec_lock_text = json.dumps(spec_lock, ensure_ascii=False, indent=2)
    return spec_lock, spec_lock_text


def _infer_deck_total(project: Path, plans: list, *, include_existing: bool) -> int:
    """Infer full deck size without collapsing targeted repairs to one page."""
    indexes = [getattr(plan, "index", 0) for plan in plans]
    if include_existing:
        for dirname in ("svg_output", "svg_final"):
            svg_dir = project / dirname
            if not svg_dir.exists():
                continue
            for path in svg_dir.glob("slide_*.svg"):
                match = re.search(r"slide_(\d+)\.svg$", path.name, flags=re.IGNORECASE)
                if match:
                    indexes.append(int(match.group(1)))
    return max(indexes) if indexes else len(plans)


def _generate_once(
    client, request_payload: dict,
) -> tuple[str, str, list[str], dict]:
    """Call the model once and return extracted SVG plus raw model text.

    Raises :class:`TruncatedResponseError` BEFORE SVG extraction when the
    provider reports an exhausted completion budget, so truncated content
    never reaches ``_extract_svg_with_issues`` or QA.
    """
    response = client.chat.completions.create(**request_payload)
    provider = parse_provider_response(response)
    metadata = ai_response_metadata(response)
    metadata["reasoning_chars"] = provider.reasoning_chars
    if provider.blocks_parsing:
        raise TruncatedResponseError(
            f"provider response truncated (finish_reason={provider.finish_reason or 'missing'})",
            provider,
        )
    svg, extraction_issues = _extract_svg_with_issues(provider.content)
    return svg, provider.content, extraction_issues, metadata


def _build_generation_request(
    model: str,
    max_tokens: int,
    temperature: float,
    top_p: float | None,
    system_prompt: str,
    user_prompt: str,
) -> dict:
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if top_p is not None:
        kwargs["top_p"] = top_p
    return kwargs


def _provider_error_message(exc: Exception) -> str:
    text = str(exc).strip()
    if not text:
        text = exc.__class__.__name__
    return f"provider call failed: {exc.__class__.__name__}: {text}"


def _is_valid_svg(text: str) -> bool:
    """Basic SVG validity check."""
    return bool(text) and "<svg" in text and "</svg>" in text


def _load_design_guide(project: Path) -> str:
    """Load design_guide.md from project if it exists."""
    guide_path = project / "design_guide.md"
    if guide_path.exists():
        return guide_path.read_text(encoding="utf-8")
    return ""


# Context budget for reference materials (chars). The old default truncated
# every reference to 2000 chars, which discarded the bulk of ppt-master's
# design corpus before the LLM ever saw it. ~12k keeps executor-base + shared
# standards intact and leaves room for one style/academic variant and the
# image-layout pattern index when the deck calls for them.
_REFERENCE_BUDGET_CHARS = 12000

# Core references are always loaded in full — they encode the shared SVG
# contract and base composition rules that every slide depends on.
_CORE_REFERENCES = ("executor-base.md", "shared-standards.md")

# Optional references are pulled in by topic signals from spec_lock so that
# decks which need them (academic, general prose, image-heavy) actually
# receive the matching guidance instead of a one-size-fits-none excerpt.
_ACADEMIC_HINTS = ("academic", "thesis", "research", "paper", "lecture", "学术", "论文", "研究")
_IMAGE_HINTS = ("image", "photo", "illustration", "图片", "插图", "图示")


def _load_reference_materials(project: Path, spec_lock: dict | None = None) -> str:
    """Load executor reference documents from project references/ dir.

    Core references (executor-base, shared-standards) are always included in
    full. Optional references (executor-general, executor-academic,
    image-layout-patterns) are included when the spec_lock's design_hints or
    theme signals call for them. The combined payload is capped at
    ``_REFERENCE_BUDGET_CHARS`` by trimming optional references first, so the
    shared SVG contract is never sacrificed for a topic supplement.
    """
    ref_dir = project / "references"
    if not ref_dir.is_dir():
        return ""

    hints_blob = " ".join(str(v) for v in (
        (spec_lock or {}).get("design_hints"),
        (spec_lock or {}).get("theme"),
        (spec_lock or {}).get("domain"),
        (spec_lock or {}).get("deck_type"),
    ) if v).lower()

    optional: list[str] = []
    if any(h in hints_blob for h in _ACADEMIC_HINTS):
        optional.append("executor-academic.md")
    else:
        # General-purpose guidance is the default fallback for non-academic decks.
        optional.append("executor-general.md")
    if any(h in hints_blob for h in _IMAGE_HINTS):
        optional.append("image-layout-patterns.md")

    def _read(name: str) -> str:
        path = ref_dir / name
        return path.read_text(encoding="utf-8") if path.exists() else ""

    # Build the payload: core first (never trimmed), then optional until budget.
    parts: list[str] = []
    used = 0
    for name in _CORE_REFERENCES:
        content = _read(name)
        if content:
            parts.append(f"### {name}\n{content}")
            used += len(content) + len(name) + 6

    for name in optional:
        content = _read(name)
        if not content:
            continue
        remaining = _REFERENCE_BUDGET_CHARS - used
        if remaining <= 0:
            break
        if len(content) > remaining:
            # Trim at a paragraph boundary when possible to avoid cutting mid-sentence.
            cut = content.rfind("\n\n", 0, remaining)
            content = (content[:cut] if cut > remaining // 2 else content[:remaining]).rstrip() + "\n... (trimmed to fit context budget)"
        parts.append(f"### {name}\n{content}")
        used += len(content) + len(name) + 6

    return "\n\n".join(parts)


def _load_executor_brief(project: Path, slide_index: int) -> str:
    """Load the validated AI Strategist brief section for one slide."""
    path = project / "qa" / "ai-planner" / "executor-brief.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    heading = re.compile(r"^\s{0,3}##\s+Slide\s+0*(\d+)\b.*$", re.IGNORECASE)
    lines = text.splitlines()
    collected: list[str] = []
    in_slide = False

    for line in lines:
        match = heading.match(line)
        if match:
            if in_slide:
                break
            in_slide = int(match.group(1)) == slide_index
            if in_slide:
                collected.append(line.strip())
            continue
        if in_slide:
            collected.append(line)

    brief = "\n".join(collected).strip()
    if len(brief) > 2200:
        brief = brief[:2200].rstrip() + "\n... (executor brief truncated)"
    return brief


def _load_visual_feedback(project: Path, slide_index: int) -> str:
    """Load rendered/manual visual feedback for a specific slide."""
    qa_dir = project / "qa"
    parts: list[str] = []

    json_feedback = _load_visual_feedback_json(qa_dir / _VISUAL_FEEDBACK_JSON, slide_index)
    if json_feedback:
        parts.append(f"### {_VISUAL_FEEDBACK_JSON}\n{json_feedback}")

    markdown_feedback = _load_visual_feedback_markdown(qa_dir / _VISUAL_FEEDBACK_MD, slide_index)
    if markdown_feedback:
        parts.append(f"### {_VISUAL_FEEDBACK_MD}\n{markdown_feedback}")

    feedback = "\n\n".join(parts).strip()
    if len(feedback) > _MAX_VISUAL_FEEDBACK_CHARS:
        feedback = feedback[:_MAX_VISUAL_FEEDBACK_CHARS].rstrip() + "\n... (visual feedback truncated)"
    return feedback


def _load_visual_feedback_json(path: Path, slide_index: int) -> str:
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""

    entry = _find_visual_feedback_entry(payload, slide_index)
    return _format_visual_feedback_payload(entry)


def _find_visual_feedback_entry(payload, slide_index: int, _depth: int = 0):
    if _depth > 10:
        return None
    keys = _visual_feedback_keys(slide_index)

    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).strip().lower() in keys:
                return value
        for container_key in ("slides", "pages", "feedback", "items"):
            if container_key in payload:
                entry = _find_visual_feedback_entry(payload[container_key], slide_index, _depth + 1)
                if entry:
                    return entry

    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            item_index = item.get("slide") or item.get("slide_index") or item.get("page") or item.get("index")
            if _parse_slide_index(item_index) == slide_index:
                return item

    return None


def _visual_feedback_keys(slide_index: int) -> set[str]:
    return {
        str(slide_index),
        f"{slide_index:02d}",
        f"slide_{slide_index}",
        f"slide_{slide_index:02d}",
        f"slide-{slide_index}",
        f"slide-{slide_index:02d}",
        f"slide {slide_index}",
        f"slide {slide_index:02d}",
        f"page_{slide_index}",
        f"page_{slide_index:02d}",
        f"page {slide_index}",
        f"page {slide_index:02d}",
    }


def _parse_slide_index(value) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return int(match.group(0))
    return None


def _format_visual_feedback_payload(payload) -> str:
    if payload is None or payload == "":
        return ""
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, list):
        lines = []
        for item in payload:
            formatted = _format_visual_feedback_payload(item)
            if formatted:
                lines.append(f"- {formatted}" if "\n" not in formatted else formatted)
        return "\n".join(lines).strip()
    if isinstance(payload, dict):
        if _is_non_actionable_ok_visual_feedback(payload):
            return ""
        action_text = _compact_feedback_action(payload)
        if action_text:
            return action_text
        lines = []
        repair_prompt = payload.get("repair_prompt")
        if repair_prompt:
            formatted_prompt = _format_visual_feedback_payload(repair_prompt)
            if formatted_prompt:
                lines.append(f"- repair_prompt: {formatted_prompt}")
        for key, value in payload.items():
            if key in {"slide", "slide_index", "page", "index", "repair_prompt"}:
                continue
            formatted = _format_visual_feedback_payload(value)
            if formatted:
                lines.append(f"- {key}: {formatted}")
        return "\n".join(lines).strip()
    return str(payload).strip()


def _compact_feedback_action(payload: dict) -> str:
    """Flatten nested action objects into prompt-ready repair text."""
    if any(key in payload for key in ("severity", "summary", "issues", "actions", "repair_prompt", "image")):
        return ""
    preferred_keys = (
        "instruction",
        "repair",
        "action",
        "description",
        "preserve",
        "keep",
    )
    if not any(key in payload for key in preferred_keys):
        return ""
    parts: list[str] = []
    for key in preferred_keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return " ".join(parts).strip()


def _is_non_actionable_ok_visual_feedback(payload: dict) -> bool:
    severity = str(payload.get("severity") or "").strip().lower()
    if severity != "ok":
        return False
    repair_prompt = str(payload.get("repair_prompt") or "").strip()
    issues = payload.get("issues") or payload.get("issue")
    actions = payload.get("actions") or payload.get("action")
    return not repair_prompt and not _has_feedback_content(issues) and not _has_feedback_content(actions)


def _has_feedback_content(value) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, list):
        return any(_has_feedback_content(item) for item in value)
    if isinstance(value, dict):
        return any(_has_feedback_content(item) for item in value.values())
    return bool(str(value).strip())


def _load_visual_feedback_markdown(path: Path, slide_index: int) -> str:
    if not path.exists():
        return ""

    text = path.read_text(encoding="utf-8")
    heading_match = re.compile(r"^\s{0,3}#{1,6}\s*Slide\s+0*(\d+)\b[:\-]?\s*(.*)$", re.IGNORECASE)
    lines = text.splitlines()
    collected: list[str] = []
    in_slide = False

    for line in lines:
        match = heading_match.match(line)
        if match:
            if in_slide:
                break
            in_slide = int(match.group(1)) == slide_index
            if in_slide and match.group(2).strip():
                collected.append(match.group(2).strip())
            continue
        if in_slide:
            collected.append(line)

    markdown = "\n".join(collected).strip()
    if markdown:
        return "" if _is_non_actionable_ok_visual_markdown(markdown) else markdown

    inline_pattern = re.compile(
        rf"^\s*(?:[-*]\s*)?Slide\s+0*{slide_index}\s*[:\-]\s*(.+)$",
        re.IGNORECASE,
    )
    inline = [match.group(1).strip() for line in lines if (match := inline_pattern.match(line))]
    inline_markdown = "\n".join(inline).strip()
    return "" if _is_non_actionable_ok_visual_markdown(inline_markdown) else inline_markdown


def _is_non_actionable_ok_visual_markdown(markdown: str) -> bool:
    lines = [
        re.sub(r"^\s*[-*]\s*", "", line).strip()
        for line in str(markdown or "").splitlines()
    ]
    lines = [line for line in lines if line]
    if not lines:
        return False
    text = " ".join(lines).lower()
    if not re.search(r"\bseverity\s*:\s*ok\b|^ok$|\bok\b", text):
        return False
    actionable_markers = (
        "issue:",
        "issues:",
        "action:",
        "actions:",
        "repair prompt:",
        "repair_prompt:",
        "missing",
        "overlap",
        "clipped",
        "too close",
        "too small",
        "repair",
        "fix",
        "move",
        "add ",
        "increase",
        "reduce",
    )
    if any(marker in text for marker in actionable_markers):
        return False
    all_clear_markers = (
        "ok",
        "looks good",
        "look good",
        "all good",
        "clean",
        "acceptable",
        "passes",
        "no issue",
        "no issues",
        "无问题",
        "通过",
    )
    return any(marker in text for marker in all_clear_markers)


def _run_quality_check(
    project: Path, spec_lock: dict, paths: list[Path], *,
    strict_quality: bool = True,
) -> list[dict]:
    """Run final project-level SVG QA and return serializable issues."""
    del spec_lock
    from .svg_qa import check_project_svg

    ok, issues = check_project_svg(project, stage="output", quality=True)
    target_names = {path.name for path in paths}
    relevant = [issue for issue in issues if not target_names or Path(issue.file).name in target_names]
    blocking = _blocking_issues(relevant, strict_quality=strict_quality)
    if blocking or (not ok and not target_names):
        raise RuntimeError(
            "AI SVG generation completed but project SVG QA still has "
            f"blocking issues:\n{_format_issue_feedback(blocking or relevant)}"
        )
    return [_issue_to_dict(issue) for issue in relevant]


_SVG_NAMESPACE = "http://www.w3.org/2000/svg"
_XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"


def _serialize_svg(root: ET.Element) -> str:
    """Serialize a repaired SVG tree without ever emitting an <ns0:svg> root.

    REDESIGN_v5 1.2F.6: plain ``ET.tostring(root)`` rewrites the root to
    ``<ns0:svg>``, which browsers render as a black frame. The fix registers
    the SVG default namespace (plus xlink) before serializing, on every call —
    ``ET.register_namespace`` is process-global, so it is applied defensively
    each time (idempotent). The ``default_namespace=`` tostring argument is
    not usable here: CPython rejects the unqualified attribute names (width,
    viewBox, ...) every SVG carries.

    Because registering "" for the SVG namespace evicts any other URI holding
    the default prefix (template_ops registers "" for OOXML rels), the global
    registry is snapshotted and restored so this grab stays scoped to this
    serialization.

    Raises ValueError when the result would not start with ``<svg``.
    """
    namespace_map = getattr(ET, "_namespace_map", None)
    snapshot = dict(namespace_map) if namespace_map is not None else None
    ET.register_namespace("", _SVG_NAMESPACE)
    ET.register_namespace("xlink", _XLINK_NAMESPACE)
    try:
        serialized = ET.tostring(root, encoding="unicode")
    finally:
        if namespace_map is not None and snapshot is not None:
            namespace_map.clear()
            namespace_map.update(snapshot)
    if not serialized.lstrip().startswith("<svg"):
        raise ValueError(
            "SVG serialization lost the default namespace "
            f"(root serialized as {serialized.lstrip()[:24]!r})"
        )
    return serialized


def _svg_child_tag(root: ET.Element, local: str) -> str:
    """Tag for a new child element matching the tree's namespace form."""
    if root.tag.startswith("{"):
        namespace = root.tag[1:].split("}", 1)[0]
        return f"{{{namespace}}}{local}"
    return local


# Regex matching the text-overflow error messages emitted by svg_qa. The
# checker reports the offending text snippet inside double quotes, which lets
# the auto-repair find the exact <text>/<tspan> node to re-wrap.
_OVERFLOW_MSG_RE = re.compile(r'Text may overflow[^"]*"([^"]{0,80})', re.IGNORECASE)


def _auto_wrap_overflowing_text(
    svg_text: str,
    blocking_messages: list[str],
    canvas_w: int,
    canvas_h: int,
) -> str | None:
    """Auto-repair text-overflow failures by re-wrapping the offending text.

    Mirrors the deterministic path's ``fitted_tspans``/kinsoku wrapping
    (commits 1d78b4d, 23dce0f) but applied as a post-generation patch on the
    AI executor's own SVG. For each <text> element whose snippet appears in a
    blocking overflow message, re-wrap its content into <tspan> lines that fit
    within the canvas right margin (or its ``data-fit-box`` when present).

    Returns the patched SVG text, or None when no overflow message was found
    or the SVG cannot be patched safely (caller then falls back to LLM retry).
    """
    if not any("overflow" in msg.lower() for msg in blocking_messages):
        return None

    # Collect the offending text snippets from the blocking messages.
    snippets: list[str] = []
    for msg in blocking_messages:
        match = _OVERFLOW_MSG_RE.search(msg)
        if not match:
            continue
        # svg_qa truncates the preview to ~40 chars and appends "..."; strip
        # that trailing ellipsis so the snippet is a true prefix of the text.
        snippet = match.group(1).rstrip().rstrip(".").rstrip()
        if snippet:
            snippets.append(snippet)
    if not snippets:
        return None

    try:
        from .text_wrap import _wrap_to_tspans, _strip_inline_md
    except ImportError:
        return None

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return None

    patched_any = False
    right_margin = max(40, round(canvas_w * 0.04))
    bottom_margin = max(40, round(canvas_h * 0.05))

    for elem in list(root.iter()):
        if _svg_local_name(elem.tag) != "text":
            continue
        # Gather this text element's full visible content.
        own_text = (elem.text or "").strip()
        tspan_texts = []
        for child in elem:
            if _svg_local_name(child.tag) == "tspan" and child.text:
                tspan_texts.append(child.text.strip())
        full = " ".join([t for t in [own_text] + tspan_texts if t])
        if not full:
            continue
        # Match against any offending snippet. The snippet is a prefix of the
        # offending text (svg_qa reports text[:40]); match on a stable leading
        # fragment so whitespace/line-break differences do not defeat it.
        snippet_matches = any(
            snippet and (full.startswith(snippet) or snippet[:20] in full)
            for snippet in snippets
        )
        if not snippet_matches:
            continue

        # Resolve x, font-size, and the available width.
        try:
            x = int(float(elem.attrib.get("x", "0")))
        except (ValueError, TypeError):
            continue
        fs_str = elem.attrib.get("font-size", "")
        try:
            fs = int(float(fs_str)) if fs_str else 24
        except (ValueError, TypeError):
            fs = 24
        try:
            line_height = float(elem.attrib.get("data-line-height", "1.4"))
        except (ValueError, TypeError):
            line_height = 1.4

        # Determine available width: prefer data-fit-box, else canvas right margin.
        fit_box_attr = elem.attrib.get("data-fit-box", "")
        max_width = None
        box_y = None
        box_h = None
        if fit_box_attr:
            try:
                bx, by, bw, bh = [int(float(v)) for v in re.findall(r"-?\d+", fit_box_attr)]
                max_width = max(1, bw - 4)
                box_y, box_h = by, bh
            except (ValueError, TypeError):
                pass
        if not max_width:
            max_width = max(1, canvas_w - x - right_margin)

        # Re-wrap the original (un-stripped) full text so wording is preserved.
        # Signature: _wrap_to_tspans(text, x, font_size, max_width_px, line_height).
        tspans, line_count = _wrap_to_tspans(full, x, fs, max_width, line_height=line_height)
        if not tspans or line_count <= 1:
            # Wrapping did not help (single line still too wide, or empty). Skip.
            continue

        # Guard against the wrap itself overflowing the bottom of the canvas/box.
        try:
            y = int(float(elem.attrib.get("y", "0")))
        except (ValueError, TypeError):
            y = 0
        dy = int(fs * line_height)
        wrap_bottom = y + (line_count - 1) * dy
        bottom_limit = (box_y + box_h) if (box_y is not None and box_h is not None) else (canvas_h - bottom_margin)
        if wrap_bottom > bottom_limit:
            continue

        # Apply: clear existing text/tspan children, set new tspans.
        elem.text = None
        for child in list(elem):
            if _svg_local_name(child.tag) == "tspan":
                elem.remove(child)
        # Insert tspans as raw XML by serializing and re-parsing the element subtree.
        # ElementTree lacks a clean raw-children API, so we replace via string surgery
        # on the serialized element is fragile; instead append tspan Elements directly.
        for i, line in enumerate(_tspan_lines_from_wrap(full, x, max_width, fs, line_height)):
            tspan = ET.Element(_svg_child_tag(root, "tspan"))
            tspan.set("x", str(x))
            tspan.set("dy", "0" if i == 0 else str(dy))
            tspan.text = line
            elem.append(tspan)
        patched_any = True

    if not patched_any:
        return None

    try:
        return _serialize_svg(root)
    except ValueError:
        return None  # never hand a namespace-broken patch to the caller


# Proven-safe upgrade ladder. Only roles whose substitution 43f9bca or the theme
# semantics justify are listed; other fill sources are left to the LLM to redraw.
_TEXT_UPGRADE_LADDER: dict[str, tuple[str, ...]] = {
    "muted": ("body", "text"),
    "text_tertiary": ("body", "text"),
    "body": ("text",),
    "text_secondary": ("text",),
    "secondary_accent": ("accent", "text"),
    "accent": ("text",),  # body-size accent often below 4.5; large-size is usually fine
}

# Backgrounds we are willing to repair against. Gradients/patterns/8-digit-hex
# chips are left to the LLM because their effective background is ambiguous.
_REPAIRABLE_BACKGROUND_ROLES = ("background", "surface", "bg_secondary")

# Skip elements that are likely decorative (intent differs from readable text).
_REPAIR_DECORATIVE_FONT_SIZE = 48


def _auto_repair_low_contrast(
    svg_text: str,
    blocking_messages: list[str],
    spec_lock: dict,
) -> str | None:
    """Auto-repair low-contrast text by upgrading the offending fill to a
    higher-contrast palette role.

    Mirrors the deterministic path's muted->body fix (43f9bca) and the
    _auto_wrap_overflowing_text scaffolding. When the only blocking issues are
    low-contrast warnings, walk the SVG, resolve each offending text element's
    fill and background, and if the fill maps to a palette role that has a
    higher-contrast candidate (per _TEXT_UPGRADE_LADDER), swap the fill-owning
    ancestor to the candidate hex. Returns the patched SVG text, or None when
    no message applies or the SVG cannot be safely patched (caller falls back
    to LLM retry).
    """
    if not any("Low text contrast" in msg for msg in blocking_messages):
        return None

    from .svg_qa import (
        _contrast_ratio,
        _is_in_footer_group,
        _local_name,
        _normalize_hex,
        _resolve_text_background,
        _resolve_text_fill,
        _get_parent,
        _TEXT_CONTRAST_BODY_MIN,
        _TEXT_CONTRAST_LARGE_MIN,
        _LARGE_TEXT_FONT_SIZE,
        _DECORATIVE_FONT_SIZE,
    )

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return None

    palette = spec_lock.get("palette", {}) if isinstance(spec_lock.get("palette"), dict) else {}
    # Build a reverse map: normalized hex -> palette role name, for the roles we
    # know how to upgrade. Only exact palette-role matches are repairable;
    # invented hexes are left to the LLM.
    hex_to_role: dict[str, str] = {}
    for role in _TEXT_UPGRADE_LADDER.keys():
        hex_val = _normalize_hex(palette.get(role))
        if hex_val:
            hex_to_role[hex_val] = role

    # Resolve the set of repairable opaque canvas backgrounds.
    repairable_bgs: set[str] = set()
    for role in _REPAIRABLE_BACKGROUND_ROLES:
        hex_val = _normalize_hex(palette.get(role))
        if hex_val:
            repairable_bgs.add(hex_val)

    canvas_bg = _normalize_hex(palette.get("background"))
    surface = _normalize_hex(palette.get("surface"))

    # Phase 1 (collect): resolve each offending text element's target fill WITHOUT
    # mutating yet, so a group upgraded once is not re-upgraded by the next
    # sibling that shares its (now-changed) fill. Record (owning_node -> new_hex)
    # keyed on the fill-owning element so each node is decided exactly once.
    targets: dict[int, str] = {}  # id(ET.Element) -> new fill hex
    decided_fills: set[str] = set()  # offending fills already assigned a target

    for elem in list(root.iter()):
        if _local_name(elem.tag) != "text":
            continue
        # Skip empty text.
        if not "".join(elem.itertext()).strip():
            continue
        if _is_in_footer_group(elem, root):
            continue
        fill = _resolve_text_fill(elem, root)
        if not fill:
            continue
        # Only repair fills that are exact palette roles we know how to upgrade.
        offending_role = hex_to_role.get(fill)
        if not offending_role:
            continue
        # If we already decided a target for this offending fill, do not re-decide
        # (prevents cascade re-upgrade across sibling text sharing the fill).
        if fill in decided_fills:
            continue
        # Resolve font-size for threshold selection.
        fs_str = elem.attrib.get("font-size", "")
        try:
            fs = int(float(fs_str)) if fs_str else 20
        except (ValueError, TypeError):
            fs = 20
        if fs < _DECORATIVE_FONT_SIZE:
            continue
        # Skip likely-decorative hero numerals / watermarks.
        if fs >= _REPAIR_DECORATIVE_FONT_SIZE:
            continue
        # Skip translucent text (decorative intent).
        opacity = elem.attrib.get("opacity", "")
        try:
            if opacity and float(opacity) < 0.5:
                continue
        except (ValueError, TypeError):
            pass
        fill_opacity = elem.attrib.get("fill-opacity", "")
        try:
            if fill_opacity and float(fill_opacity) < 0.5:
                continue
        except (ValueError, TypeError):
            pass

        background = _resolve_text_background(elem, root, canvas_bg) or surface
        if not background or background not in repairable_bgs:
            continue

        threshold = _TEXT_CONTRAST_LARGE_MIN if fs >= _LARGE_TEXT_FONT_SIZE else _TEXT_CONTRAST_BODY_MIN
        candidate_roles = _TEXT_UPGRADE_LADDER.get(offending_role, ())
        new_hex = None
        for cand_role in candidate_roles:
            cand_hex = _normalize_hex(palette.get(cand_role))
            if not cand_hex or cand_hex == fill:
                continue
            if _contrast_ratio(cand_hex, background) >= threshold:
                new_hex = cand_hex
                break
        if not new_hex:
            continue

        # Find the nearest ancestor that owns this fill (the mutation target),
        # so all text sharing the fill is fixed in one pass (mirrors the
        # checker's seen_pairs dedup).
        target = elem
        node = elem
        while node is not None:
            node_fill = _normalize_hex(node.attrib.get("fill"))
            if node_fill == fill:
                target = node
                break
            node = _get_parent(root, node)
        targets[id(target)] = new_hex
        decided_fills.add(fill)

    # Phase 2 (apply): mutate each owning node exactly once.
    patched_any = False
    for elem in list(root.iter()):
        if id(elem) in targets:
            elem.set("fill", targets[id(elem)])
            patched_any = True

    if not patched_any:
        return None

    try:
        return _serialize_svg(root)
    except ValueError:
        return None  # never hand a namespace-broken patch to the caller


def _tspan_lines_from_wrap(text: str, x: int, max_width: int, fs: int, line_height: float) -> list[str]:
    """Return the visual line strings for a text run (paired with _wrap_to_tspans)."""
    from .text_wrap import _visual_wrap, _strip_inline_md
    clean = _strip_inline_md(text).strip()
    if not clean:
        return []
    return _visual_wrap(clean, max_width, fs)


def _repair_preserves_visible_text(original_text: str, patched_text: str) -> bool:
    """Repairs may only restyle/reflow; the visible text set must survive.

    Compares the whitespace-free normalized full text of every rendered
    <text> element (wrap-split tolerant), so re-wrapping into tspans passes
    while any dropped or altered content rejects the patch.
    """
    def element_texts(svg_text: str) -> list[str]:
        texts = [
            _fidelity_compact(" ".join(chunks))
            for chunks in _visible_svg_text_line_runs(svg_text)
        ]
        return sorted(text for text in texts if text)

    return element_texts(original_text) == element_texts(patched_text)


# ── Browser geometry arbitration (QA-02 -> BENCH-03) ─────────────────────
#
# svg_qa's character-width model is a cheap pre-screen; the browser's
# getBBox() measurements are the final arbiter for every text-geometry
# verdict class. The mechanism lives in svg_qa.arbitrate_text_geometry()
# so the benchmark runner, publish gate, and executor share one arbiter.
# Since v5.1 BENCH-03 all text sizes qualify (big numerals AND ordinary
# tspan-dx / text-anchor width / small-text collisions).


def _arbitrate_static_text_geometry(svg_text: str, issues: list) -> tuple[list, dict | None]:
    """Browser-arbitrate static text-geometry verdicts (delegates to svg_qa)."""
    from .svg_qa import arbitrate_text_geometry

    return arbitrate_text_geometry(svg_text, issues)



# QA-03: capability-gap marker recorded when a repair is accepted without a
# browser re-render check (no local Chrome). Strict release paths surface it.
_NO_BROWSER_RENDER_GAP = "no-browser-render-check"


def _browser_render_gate(candidate_path: Path) -> tuple[bool, str]:
    """Post-repair re-render gate — mandatory whenever a browser exists (QA-03).

    Reuses the repo's headless-browser screenshot path (render.py). When
    ``find_chrome()`` locates a browser the check MUST run: a candidate whose
    render is positively detected as a black frame is rejected (the ns0
    black-screen class shipped with green source QA). When no browser exists
    the gate cannot run — it passes but reports the capability gap so the
    caller records it in the trace instead of silently passing.
    """
    from .chrome_geometry import find_chrome

    browser = find_chrome()
    if not browser:
        return True, f"capability-gap: {_NO_BROWSER_RENDER_GAP}"
    try:
        from .render import (
            CHROME_TIMEOUT_SECONDS,
            _run_with_timeout,
            _write_svg_screenshot_html,
        )
    except ImportError:
        return True, f"capability-gap: {_NO_BROWSER_RENDER_GAP}"
    import tempfile
    try:
        with tempfile.TemporaryDirectory(prefix="repair-render-") as tmp:
            html_path = Path(tmp) / "candidate.html"
            png_path = Path(tmp) / "candidate.png"
            _write_svg_screenshot_html(candidate_path, html_path)
            _run_with_timeout(
                [
                    browser,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    f"--screenshot={png_path.resolve()}",
                    "--window-size=1280,720",
                    html_path.resolve().as_uri(),
                ],
                timeout=CHROME_TIMEOUT_SECONDS,
                label="repair candidate screenshot",
            )
            if not png_path.exists() or png_path.stat().st_size == 0:
                return True, "screenshot not produced; gate skipped"
            try:
                from PIL import Image
            except ImportError:
                return True, "Pillow unavailable; gate skipped"
            with Image.open(png_path) as img:
                sampled = img.convert("RGB").resize((64, 36))
                brightest = max(max(pixel) for pixel in sampled.getdata())
            if brightest <= 8:
                return False, "candidate renders as a black frame"
    except Exception as exc:  # noqa: BLE001 - environmental render failures must not block
        return True, f"render gate skipped ({exc.__class__.__name__})"
    return True, "render ok"


def _apply_validated_repair(
    project: Path,
    attempt_path: Path,
    original_text: str,
    patched_text: str,
    *,
    plan,
    visual_feedback: str,
    run_qa: bool,
    strict_quality: bool,
    repair_kind: str,
    model: str,
    attempt: int,
    slide_index: int,
) -> tuple[bool, list]:
    """Validate a repair candidate before it may replace the attempt SVG.

    REDESIGN_v5 1.2F.7: the old flow overwrote the attempt file before any
    validation, polluting failure evidence. This writes the patch to a
    sibling ``.patch-candidate`` file, re-runs per-file QA on the candidate,
    verifies the visible text set is preserved, re-renders it whenever a
    local browser exists (QA-03: black frames reject; no browser records a
    capability-gap trace note instead of silently passing), and only then
    atomically replaces the original (``os.replace``). On any failure the
    original attempt file stays byte-identical, the candidate is deleted,
    and a ``repair-rejected`` trace event records the reason.

    Returns ``(accepted, revalidated_issues)``.
    """
    candidate_path = attempt_path.with_name(attempt_path.name + ".patch-candidate")
    candidate_path.write_text(patched_text, encoding="utf-8")
    rejection = ""
    reissue_issues: list = []
    capability_gap = ""
    candidate_geometry: dict | None = None
    try:
        reissue_issues = _validate_svg_attempt(
            project, candidate_path,
            svg_text=patched_text,
            plan=plan,
            visual_feedback=visual_feedback,
            run_qa=run_qa,
            strict_quality=strict_quality,
            preflight_issues=None,
        )
        # Same arbiter as the attempt loop: a phantom big-text verdict must
        # not reject an otherwise valid repair candidate (QA-02).
        reissue_issues, candidate_geometry = _arbitrate_static_text_geometry(
            patched_text, reissue_issues,
        )
        reblocking = _blocking_issues(reissue_issues, strict_quality=strict_quality)
        if reblocking:
            rejection = "candidate QA still blocking: " + "; ".join(
                _issue_message_preview(reblocking)
            )
        elif not _repair_preserves_visible_text(original_text, patched_text):
            rejection = "candidate dropped or altered visible text"
        else:
            render_ok, render_reason = _browser_render_gate(candidate_path)
            if not render_ok:
                rejection = f"browser render check failed: {render_reason}"
            elif render_reason.startswith("capability-gap:"):
                capability_gap = render_reason.split(":", 1)[1].strip()
    except Exception as exc:  # noqa: BLE001 - a repair must never crash generation
        rejection = f"candidate validation raised {exc.__class__.__name__}: {exc}"

    if rejection:
        candidate_path.unlink(missing_ok=True)
        write_ai_trace(
            project,
            stage="executor",
            model=model,
            status="repair-rejected",
            attempt=attempt,
            metadata={
                "slide": slide_index,
                "repair": repair_kind,
                "reason": rejection,
                "path": str(attempt_path),
                **(candidate_geometry or {}),
            },
        )
        return False, []

    os.replace(candidate_path, attempt_path)
    if capability_gap:
        # QA-03: never silently accept a repair without a re-render check.
        # The gap is trace-recorded here and listed by ai-release-check.
        write_ai_trace(
            project,
            stage="executor",
            model=model,
            status="repair-accepted",
            attempt=attempt,
            metadata={
                "slide": slide_index,
                "repair": repair_kind,
                "path": str(attempt_path),
                "capability_gap": capability_gap,
                "note": f"capability-gap: {capability_gap}",
            },
        )
    return True, reissue_issues


def _validate_svg_attempt(
    project: Path, svg_path: Path, *,
    svg_text: str | None = None,
    plan=None,
    visual_feedback: str = "",
    run_qa: bool,
    strict_quality: bool,
    preflight_issues: list[str] | None = None,
):
    """Validate one generated page with structural and optional quality QA."""
    from .svg_qa import SvgIssue

    issues = [
        SvgIssue(
            "warning" if "markdown fences" in issue else "error",
            str(svg_path),
            issue,
        )
        for issue in (preflight_issues or [])
    ]
    svg_text = svg_text or svg_path.read_text(encoding="utf-8")
    if not _is_valid_svg(svg_text):
        issues.append(SvgIssue("error", str(svg_path), "Model output is not a complete <svg>...</svg> document"))
        return issues

    from .svg_qa import check_project_svg, check_svg_file

    issues.extend(check_svg_file(svg_path, project))
    if run_qa:
        issues.extend(_check_svg_attempt_quality(svg_path, project, svg_text=svg_text))
    if plan is not None:
        issues.extend(_check_content_fidelity(
            svg_path,
            svg_text,
            plan,
            extra_required=_visual_feedback_preserve_required_strings(visual_feedback),
        ))
        issues.extend(_check_bullet_markers(svg_path, svg_text, plan))
        issues.extend(_check_bullet_text_color(svg_path, svg_text, plan, project))
        issues.extend(_check_layout_intent(svg_path, svg_text, plan))
    issues.extend(_check_visual_feedback_geometry(svg_path, svg_text, visual_feedback))
    if run_qa:
        _, project_issues = check_project_svg(project, stage="output", quality=True)
        for issue in project_issues:
            if Path(issue.file).name == svg_path.name:
                issues.append(issue)

    return _dedupe_issues(issues)


def _check_svg_attempt_quality(svg_path: Path, project: Path, *, svg_text: str | None = None):
    """Run file-level design-quality checks for an unpublished executor attempt."""
    from .svg_qa import (
        SvgIssue,
        _check_font_safety,
        _check_spec_polish,
        _check_spec_drift,
        _check_text_contrast,
    )

    try:
        root = ET.fromstring(svg_text or svg_path.read_text(encoding="utf-8"))
    except ET.ParseError:
        return []

    issues = []
    try:
        from .spec_lock_reader import load_spec_lock
        spec_lock = load_spec_lock(project)
    except (FileNotFoundError, Exception):
        spec_lock = None

    parsed = [(svg_path, root)]
    if spec_lock:
        issues.extend(_check_spec_drift(parsed, spec_lock))
        issues.extend(_check_spec_polish(parsed, spec_lock))
        issues.extend(_check_text_contrast(parsed, spec_lock))
    issues.extend(_check_font_safety(parsed))
    return [
        SvgIssue(issue.level, str(svg_path), issue.message)
        for issue in issues
    ]


def _check_content_fidelity(svg_path: Path, svg_text: str, plan, *, extra_required: list[tuple[str, str]] | None = None) -> list:
    """Ensure the model did not produce a valid-looking SVG with missing content."""
    from .svg_qa import SvgIssue

    visible_text = _svg_visible_text(svg_text)
    issues = []
    required = _required_visible_strings(plan) + list(extra_required or [])
    title = next((text for label, text in required if label == "title"), "")
    if title and not _contains_content_fragment(visible_text, title):
        issues.append(SvgIssue(
            "warning",
            str(svg_path),
            f"Content fidelity: missing slide title text {title!r}",
        ))

    missing_items: list[str] = []
    for label, text in required:
        if label == "title":
            continue
        if text and not _contains_content_fragment(visible_text, text):
            missing_items.append(f"{label}: {text}")

    if missing_items:
        preview = "; ".join(repr(item) for item in missing_items[:3])
        remaining = len(missing_items) - 3
        suffix = f"; ... {remaining} more" if remaining > 0 else ""
        issues.append(SvgIssue(
            "warning",
            str(svg_path),
            f"Content fidelity: missing planned content item(s): {preview}{suffix}",
        ))
    issues.extend(_check_unsupported_content(
        svg_path, svg_text, plan, extra_allowed=extra_required,
    ))
    return issues


# ── Closed-world fidelity: visible → planned direction (REDESIGN_v5 1.2C) ────
#
# The missing-content direction above catches pages that omit planned text.
# This direction catches the opposite, more dangerous class: the model
# inventing plausible-but-unsourced claims and numbers (sample 1 added nine
# judgments never present in the plan). Every visible text run must trace to
# the plan corpus or be an approved derived label (page numbers, enumeration
# markers, decorative glyphs).

# Punctuation stripped from run/allowed boundaries after NFKC normalization.
# NFKC already folds full-width forms (：→:, ，→,, ％→%), so this set only
# needs ASCII plus the CJK marks NFKC leaves untouched (。、《》等).
_FIDELITY_TRAILING_PUNCT = "：:。.，,；;、！!？?·•…~～"

# A run counts as content only if it contains letters, digits, or CJK;
# pure punctuation/symbol runs (bullets, arrows, dividers) are decorative.
_FIDELITY_WORD_RE = re.compile(
    r"[0-9a-z\u00c0-\u024f\u0370-\u03ff\u0400-\u04ff\u3040-\u30ff\u31f0-\u31ff"
    r"\u4e00-\u9fff\uac00-\ud7af]"
)

# Footer page label forms the pipeline itself emits ("03 / 14", "3/14").
_FIDELITY_PAGE_LABEL_RE = re.compile(r"^\d{1,3} ?/ ?\d{1,3}$")

# Roman-numeral enumeration labels up to XII (normalized/casefolded).
_FIDELITY_ROMAN_LABELS = frozenset(
    {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"}
)

# Digit-sequence tokens that require a source: >= 2 digits or any percentage.
_FIDELITY_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*\s*%?")

# Subtrees whose text never renders (plus non-rendered metadata elements).
_FIDELITY_SKIP_TAGS = frozenset(
    {"defs", "symbol", "clippath", "mask", "pattern", "marker",
     "script", "style", "title", "desc", "metadata"}
)

_FIDELITY_ISSUE_PREVIEW = 8


def _fidelity_normalize(text: str) -> str:
    """One normalization for both sides of the closed-world comparison."""
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip().casefold()
    return normalized.rstrip(_FIDELITY_TRAILING_PUNCT + " ")


def _fidelity_compact(text: str) -> str:
    """Whitespace-free normalized form (tolerates CJK wrap splits)."""
    return re.sub(r"\s+", "", _fidelity_normalize(text))


def _fidelity_allowed_strings(plan) -> list[str]:
    """Closed-world corpus: every string the plan object provides."""
    allowed: list[str] = []

    def add(value) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text:
                allowed.append(text)
        elif isinstance(value, dict):
            for child in value.values():
                add(child)
        elif isinstance(value, (list, tuple, set)):
            for child in value:
                add(child)

    for field in ("title", "notes", "layout", "visual_strategy",
                  "chart_type", "image_hint", "layout_pattern"):
        add(getattr(plan, field, ""))
    add(getattr(plan, "meta", None))
    for item in list(getattr(plan, "items", []) or []):
        for field in ("type", "primary", "secondary", "tertiary"):
            add(getattr(item, field, ""))
        add(getattr(item, "meta", None))
    return allowed


def _is_auto_allowed_visible_label(normalized: str) -> bool:
    """Derived labels a page may show without plan entries."""
    if not normalized:
        return True
    if not _FIDELITY_WORD_RE.search(normalized):
        return True  # decorative glyph run (bullets, arrows, rules)
    if _FIDELITY_PAGE_LABEL_RE.match(normalized):
        return True  # footer page label "NN / TT"
    if len(normalized) == 1 and (normalized.isdigit() or normalized.isalpha()):
        return True  # single-digit/letter enumeration marker
    if normalized.isdigit() and len(normalized) <= 2:
        return True  # "01".."99" enumeration / page numerals
    if normalized in _FIDELITY_ROMAN_LABELS:
        return True
    return False


def _visible_svg_text_line_runs(svg_text: str) -> list[list[str]]:
    """Per rendered <text> element, its visible chunk strings in order.

    Skips <defs>-style subtrees and hidden elements. Shared by the
    closed-world fidelity check and repair text-preservation validation.
    """
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return []

    lines: list[list[str]] = []

    def collect_chunks(node: ET.Element, chunks: list[str]) -> None:
        if node.text and node.text.strip():
            chunks.append(node.text.strip())
        for child in list(node):
            if (not _svg_element_hidden(child)
                    and _svg_local_name(child.tag) not in _FIDELITY_SKIP_TAGS):
                collect_chunks(child, chunks)
            if child.tail and child.tail.strip():
                chunks.append(child.tail.strip())

    def walk(elem: ET.Element) -> None:
        local = _svg_local_name(elem.tag)
        if local in _FIDELITY_SKIP_TAGS or _svg_element_hidden(elem):
            return
        if local == "text":
            chunks: list[str] = []
            collect_chunks(elem, chunks)
            if chunks:
                lines.append(chunks)
            return
        for child in list(elem):
            walk(child)

    walk(root)
    return lines


def _fidelity_run_supported(
    run: str,
    allowed_pairs: list[tuple[str, str]],
) -> bool:
    """A visible run is supported when it is a substring of an allowed string
    or an allowed string is a substring of it (handles wrapping splits)."""
    normalized = _fidelity_normalize(run)
    if _is_auto_allowed_visible_label(normalized):
        return True
    compact = re.sub(r"\s+", "", normalized)
    for norm, comp in allowed_pairs:
        if normalized in norm or (compact and compact in comp):
            return True
        # Reverse direction: require length >= 2 so degenerate one-character
        # allowed strings cannot whitelist arbitrary runs.
        if len(norm) >= 2 and (norm in normalized or comp in compact):
            return True
    return False


def _fidelity_number_tokens(normalized_line: str) -> list[str]:
    """Digit-sequence tokens that require plan/source backing."""
    tokens: list[str] = []
    for match in _FIDELITY_NUMBER_RE.finditer(normalized_line):
        token = re.sub(r"\s+", "", match.group(0))
        digit_count = sum(ch.isdigit() for ch in token)
        if "%" in token or digit_count >= 2:
            tokens.append(token)
    return tokens


def _check_unsupported_content(
    svg_path: Path, svg_text: str, plan, *,
    extra_allowed: list[tuple[str, str]] | None = None,
) -> list:
    """Closed-world direction: block visible text/numbers absent from the plan."""
    from .svg_qa import SvgIssue

    allowed_source = _fidelity_allowed_strings(plan)
    allowed_source += [text for _, text in (extra_allowed or [])]
    allowed_pairs: list[tuple[str, str]] = []
    for text in allowed_source:
        norm = _fidelity_normalize(text)
        if norm:
            allowed_pairs.append((norm, re.sub(r"\s+", "", norm)))
    number_corpus = "\n".join(comp for _, comp in allowed_pairs)

    unsupported: list[str] = []
    unsourced: list[str] = []
    for chunks in _visible_svg_text_line_runs(svg_text):
        line = " ".join(chunks)
        line_norm = _fidelity_normalize(line)
        # Wrapping-split tolerance: when the whole element's concatenated text
        # is supported, its individual (wrapped) chunks never false-positive.
        line_supported = _fidelity_run_supported(line, allowed_pairs)
        if not line_supported:
            for chunk in chunks:
                if not _fidelity_run_supported(chunk, allowed_pairs):
                    unsupported.append(chunk)
        if _is_auto_allowed_visible_label(line_norm):
            continue  # enumeration markers / page labels need no number source
        for token in _fidelity_number_tokens(line_norm):
            if token not in number_corpus:
                unsourced.append(token)

    issues = []
    for text in list(dict.fromkeys(unsupported))[:_FIDELITY_ISSUE_PREVIEW]:
        issues.append(SvgIssue(
            "error",
            str(svg_path),
            f"Content fidelity: unsupported-visible-text {text!r} is not part of "
            "the slide plan or an approved derived label; remove it or add it to the plan",
        ))
    hidden_unsupported = len(dict.fromkeys(unsupported)) - _FIDELITY_ISSUE_PREVIEW
    if hidden_unsupported > 0:
        issues.append(SvgIssue(
            "error",
            str(svg_path),
            f"Content fidelity: unsupported-visible-text ... {hidden_unsupported} more run(s) not in the plan",
        ))
    for token in list(dict.fromkeys(unsourced))[:_FIDELITY_ISSUE_PREVIEW]:
        issues.append(SvgIssue(
            "error",
            str(svg_path),
            f"Content fidelity: unsourced-number {token!r} does not appear in the "
            "plan/source corpus; remove it or trace it to the source",
        ))
    return issues


def _visual_feedback_preserve_required_strings(visual_feedback: str) -> list[tuple[str, str]]:
    required: list[tuple[str, str]] = []
    for line in _visual_feedback_preserve_lines(visual_feedback):
        extracted = _extract_preserved_text_from_feedback_line(line)
        if not extracted:
            continue
        required.append((f"visual-feedback preserve {len(required) + 1}", extracted))
    return required


def _visual_feedback_preserve_lines(visual_feedback: str) -> list[str]:
    lines = []
    markers = ("preserve", "keep", "retain", "maintain", "保留")
    for raw_line in str(visual_feedback or "").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" -\t")
        if not line:
            continue
        lowered = line.lower()
        if not any(marker in lowered or marker in line for marker in markers):
            continue
        if len(line) > 180:
            line = line[:177].rstrip() + "..."
        if line not in lines:
            lines.append(line)
        if len(lines) >= 5:
            break
    return lines


def _extract_preserved_text_from_feedback_line(line: str) -> str:
    text = re.sub(r"^(?:repair_prompt|issues?|actions?|summary)\s*:\s*", "", str(line).strip(), flags=re.IGNORECASE)
    quoted = re.findall(r"[\"'“”‘’`「『](.*?)[\"'“”‘’`」』]", text)
    if quoted:
        return max((item.strip() for item in quoted), key=len, default="")
    patterns = (
        r"(?:preserve|keep|retain|maintain)\s+(?:the\s+)?(?:visible\s+)?(?:text\s+)?(.+?)(?:\s+(?:while|and|but|when|unless)|[.;,。；，]|$)",
        r"保留(?:可见)?(?:文本|文字|内容)?[:：]?\s*(.+?)(?:[。；;，,]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _concrete_preserved_text_candidate(match.group(1))
    return _concrete_preserved_text_candidate(text)


def _concrete_preserved_text_candidate(candidate: str) -> str:
    candidate = str(candidate or "").strip(" .。；;,，:：")[:120]
    if not candidate:
        return ""
    clean = candidate.lower()
    generic_markers = (
        "footer",
        "page number",
        "progress dot",
        "deck chrome",
        "source-backed text",
        "source backed text",
        "all source",
        "all visible",
        "all required",
        "all text",
    )
    if any(marker in clean for marker in generic_markers):
        return ""
    if len(candidate.split()) > 8 and not _contains_cjk(candidate):
        return ""
    return candidate


def _check_visual_feedback_geometry(svg_path: Path, svg_text: str, visual_feedback: str) -> list:
    """Verify concrete rendered-feedback geometry requests that are cheap to prove."""
    from .svg_qa import SvgIssue

    feedback = str(visual_feedback or "").lower()
    if not feedback:
        return []
    issues = []
    if "accent" in feedback and any(term in feedback for term in ("stripe", "rail")):
        if not _has_visible_accent_stripe_rect(svg_text):
            issues.append(SvgIssue(
                "warning",
                str(svg_path),
                "Visual feedback geometry: requested accent stripe/rail but no visible narrow rect was found",
            ))
    if _visual_feedback_requests_surface_rect(feedback):
        if not _has_visible_surface_rect(svg_text):
            issues.append(SvgIssue(
                "warning",
                str(svg_path),
                "Visual feedback geometry: requested panel/card/surface background but no visible content-sized rect was found",
            ))
    if _visual_feedback_requests_bullet_marker(feedback):
        if not _has_visible_bullet_marker_or_glyph(svg_text):
            issues.append(SvgIssue(
                "warning",
                str(svg_path),
                "Visual feedback geometry: requested bullet marker/color but no visible bullet marker or glyph was found",
            ))
    return issues


def _visual_feedback_requests_surface_rect(feedback: str) -> bool:
    if not any(term in feedback for term in ("panel", "card", "surface", "background")):
        return False
    return any(term in feedback for term in ("add", "create", "draw", "visible", "behind", "background", "surface", "panel", "card"))


def _visual_feedback_requests_bullet_marker(feedback: str) -> bool:
    if "bullet" not in feedback:
        return False
    return any(term in feedback for term in ("marker", "color", "colour", "glyph", "dot", "circle"))


def _has_visible_accent_stripe_rect(svg_text: str) -> bool:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return False
    rects: list[tuple[float, float]] = []
    _collect_visible_rect_sizes(root, rects, hidden=False)
    for width, height in rects:
        if width <= 0 or height <= 0:
            continue
        if width <= 24 and height >= 120:
            return True
        if height <= 24 and width >= 120:
            return True
    return False


def _has_visible_bullet_marker_or_glyph(svg_text: str) -> bool:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return False
    text_runs: list[dict] = []
    markers: list[tuple[float, float]] = []
    _collect_bullet_marker_evidence(root, text_runs, markers, hidden=False, inherited=(0.0, 0.0))
    if markers:
        return True
    return any(re.search(r"[•●◦▪‣]", str(run.get("raw", ""))) for run in text_runs)


def _has_visible_surface_rect(svg_text: str) -> bool:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return False
    rects: list[tuple[float, float]] = []
    _collect_visible_rect_sizes(root, rects, hidden=False)
    for width, height in rects:
        if width <= 0 or height <= 0:
            continue
        if width >= 1200 and height >= 650:
            continue
        if width >= 120 and height >= 60 and (width * height) >= 12000:
            return True
    return False


def _collect_visible_rect_sizes(elem: ET.Element, rects: list[tuple[float, float]], *, hidden: bool) -> None:
    local = _svg_local_name(elem.tag)
    current_hidden = hidden or _svg_element_hidden(elem)
    if current_hidden or local in {"script", "style", "title", "desc", "defs", "lineargradient", "radialgradient", "stop", "filter", "clippath", "mask"}:
        return
    if local == "rect":
        width = _float_attr(elem.attrib.get("width")) or 0.0
        height = _float_attr(elem.attrib.get("height")) or 0.0
        rects.append((width, height))
    for child in list(elem):
        _collect_visible_rect_sizes(child, rects, hidden=current_hidden)


def _check_bullet_markers(svg_path: Path, svg_text: str, plan) -> list:
    """Ensure planned bullet items have a visible marker, not just plain text."""
    from .svg_qa import SvgIssue

    bullet_items = [
        item for item in list(getattr(plan, "items", []) or [])
        if str(getattr(item, "type", "") or "").strip().lower() == "bullet"
        and str(getattr(item, "primary", "") or "").strip()
    ]
    if not bullet_items:
        return []

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return []

    text_runs: list[dict] = []
    markers: list[tuple[float, float]] = []
    _collect_bullet_marker_evidence(root, text_runs, markers, hidden=False, inherited=(0.0, 0.0))

    issues = []
    for item in bullet_items:
        expected = str(getattr(item, "primary", "") or "")
        run = _find_text_run_for_content(text_runs, expected)
        if run is None:
            continue
        if _text_run_has_bullet_glyph(run, expected):
            continue
        if _has_marker_for_text_run(markers, run):
            continue
        preview = _content_match_fragment(expected)
        issues.append(SvgIssue(
            "warning",
            str(svg_path),
            f"Bullet rendering: planned bullet item lacks a visible bullet marker before the text: {preview!r}",
        ))
    return issues


def _check_bullet_text_color(svg_path: Path, svg_text: str, plan, project: Path) -> list:
    """Ensure bullet body text uses body color, not title color."""
    from .svg_qa import SvgIssue

    bullet_items = [
        item for item in list(getattr(plan, "items", []) or [])
        if str(getattr(item, "type", "") or "").strip().lower() == "bullet"
        and str(getattr(item, "primary", "") or "").strip()
    ]
    if not bullet_items:
        return []

    try:
        spec_lock, _ = _load_spec_lock(project)
    except (FileNotFoundError, Exception):
        return []
    palette = spec_lock.get("palette", {}) if isinstance(spec_lock.get("palette"), dict) else {}
    primary = _normalize_svg_hex(palette.get("text"))
    body = _normalize_svg_hex(palette.get("text_secondary") or palette.get("body"))
    if not primary or not body or primary == body:
        return []

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return []

    text_runs: list[dict] = []
    markers: list[tuple[float, float]] = []
    _collect_bullet_marker_evidence(root, text_runs, markers, hidden=False, inherited=(0.0, 0.0))

    issues = []
    for item in bullet_items:
        run = _find_text_run_for_content(text_runs, str(getattr(item, "primary", "") or ""))
        if run is None:
            continue
        fill = _normalize_svg_hex(run.get("fill"))
        if fill == primary:
            preview = _content_match_fragment(str(getattr(item, "primary", "") or ""))
            issues.append(SvgIssue(
                "warning",
                str(svg_path),
                f"Bullet rendering: bullet body text uses primary title color {primary}; use body/text_secondary color {body}: {preview!r}",
            ))
    return issues


def _check_layout_intent(svg_path: Path, svg_text: str, plan) -> list:
    """Catch generic layouts that ignore explicit planner placement contracts."""
    from .svg_qa import SvgIssue

    pattern = f"{getattr(plan, 'layout', '')} {getattr(plan, 'layout_pattern', '')}".lower()
    if not any(term in pattern for term in (
        "left", "right", "two-column", "two column", "2-column", "proof card",
        "grid", "comparison", "top", "lower", "bottom", "row",
    )):
        return []
    positions = _visible_svg_positions(svg_text)
    text_positions = _visible_svg_text_positions(svg_text)
    content_positions = [(x, y) for x, y, _text in text_positions] or positions
    if not content_positions:
        return [SvgIssue("warning", str(svg_path), "Layout intent: no visible positioned SVG elements found to verify planner layout")]

    has_left = any(x <= 620 for x, _ in content_positions)
    has_right = any(x >= 660 for x, _ in content_positions)
    has_top = any(80 <= y <= 280 for _, y in content_positions)
    has_lower = any(300 <= y <= 660 for _, y in content_positions)

    issues = []
    if _requires_left_right_layout(pattern):
        if not (has_left and has_right):
            issues.append(SvgIssue(
                "warning",
                str(svg_path),
                "Layout intent: planner requested left/right structure but visible elements do not occupy both left and right regions",
            ))
    if any(term in pattern for term in ("top", "lower", "bottom", "row")):
        if not (has_top and has_lower):
            issues.append(SvgIssue(
                "warning",
                str(svg_path),
                "Layout intent: planner requested top/lower structure but visible elements do not occupy both vertical regions",
            ))
    if _requires_grid_layout(pattern):
        quadrants = {
            ("left" if x < 640 else "right", "top" if y < 360 else "bottom")
            for x, y in content_positions
            if 60 <= x <= 1220 and 80 <= y <= 670
        }
        if len(quadrants) < 3:
            issues.append(SvgIssue(
                "warning",
                str(svg_path),
                "Layout intent: planner requested grid/comparison structure but visible elements do not span at least three grid quadrants",
            ))
    return issues


def _collect_bullet_marker_evidence(
    elem: ET.Element,
    text_runs: list[dict],
    markers: list[tuple[float, float]],
    *,
    hidden: bool,
    inherited: tuple[float, float],
) -> None:
    local = _svg_local_name(elem.tag)
    current_hidden = hidden or _svg_element_hidden(elem)
    if current_hidden or local in {"script", "style", "title", "desc", "defs", "lineargradient", "radialgradient", "stop", "filter", "clippath", "mask"}:
        return

    tx, ty = _svg_translate(elem.attrib.get("transform", ""))
    origin = (inherited[0] + tx, inherited[1] + ty)
    if local == "text":
        text = _element_visible_text(elem)
        x = _float_attr(elem.attrib.get("x"))
        y = _float_attr(elem.attrib.get("y"))
        if text and x is not None and y is not None:
            text_runs.append({
                "text": _normalize_content_text(html.unescape(text)),
                "raw": html.unescape(text),
                "x": origin[0] + x,
                "y": origin[1] + y,
                "fill": elem.attrib.get("fill", ""),
            })
    marker = _bullet_marker_position(elem, origin)
    if marker is not None:
        markers.append(marker)

    for child in list(elem):
        _collect_bullet_marker_evidence(child, text_runs, markers, hidden=current_hidden, inherited=origin)


def _element_visible_text(elem: ET.Element) -> str:
    parts: list[str] = []
    _collect_visible_svg_text(elem, parts, hidden=False, in_text=False)
    return "".join(parts)


def _bullet_marker_position(elem: ET.Element, inherited: tuple[float, float]) -> tuple[float, float] | None:
    local = _svg_local_name(elem.tag)
    attrs = elem.attrib
    if local in {"circle", "ellipse"}:
        cx = _float_attr(attrs.get("cx"))
        cy = _float_attr(attrs.get("cy"))
        if cx is not None and cy is not None:
            return inherited[0] + cx, inherited[1] + cy
    if local == "rect":
        x = _float_attr(attrs.get("x"))
        y = _float_attr(attrs.get("y"))
        width = _float_attr(attrs.get("width")) or 0.0
        height = _float_attr(attrs.get("height")) or 0.0
        if x is not None and y is not None and width <= 24 and height <= 24:
            return inherited[0] + x + (width / 2), inherited[1] + y + (height / 2)
    if local in {"polygon", "polyline"}:
        point = _first_svg_point(attrs.get("points", ""))
        if point is not None:
            return inherited[0] + point[0], inherited[1] + point[1]
    return None


def _find_text_run_for_content(text_runs: list[dict], expected: str) -> dict | None:
    fragment = _content_match_fragment(expected)
    if not fragment:
        return None
    for run in text_runs:
        text = str(run.get("text", ""))
        if fragment in text:
            return run
        if _contains_cjk(fragment):
            compact_text = _compact_cjk_text(text)
            if _compact_cjk_text(fragment) in compact_text or _cjk_parts_covered(fragment, compact_text):
                return run
    return None


def _text_run_has_bullet_glyph(run: dict, expected: str) -> bool:
    raw = str(run.get("raw", ""))
    fragment = str(expected or "").strip()
    if not raw or not fragment:
        return False
    compact_raw = raw.strip()
    raw_index = compact_raw.find(fragment)
    if raw_index < 0 and _contains_cjk(fragment):
        raw_index = _compact_cjk_text(compact_raw).find(_compact_cjk_text(fragment))
    prefix = compact_raw[:raw_index] if raw_index >= 0 else compact_raw[:4]
    return bool(re.search(r"[•●◦▪‣]\s*$", prefix) or re.search(r"^\s*[-*]\s+$", prefix))


def _has_marker_for_text_run(markers: list[tuple[float, float]], run: dict) -> bool:
    x = float(run.get("x", 0.0))
    y = float(run.get("y", 0.0))
    for marker_x, marker_y in markers:
        if 6 <= (x - marker_x) <= 80 and abs(y - marker_y) <= 22:
            return True
    return False


def _normalize_svg_hex(value: object) -> str | None:
    text = str(value or "").strip()
    match = re.match(r"^#[0-9a-fA-F]{6}$", text)
    if not match:
        return None
    return text.upper()


def _visible_svg_positions(svg_text: str) -> list[tuple[float, float]]:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return []
    positions: list[tuple[float, float]] = []
    _collect_visible_svg_positions(root, positions, hidden=False, inherited=(0.0, 0.0))
    return positions


def _requires_left_right_layout(pattern: str) -> bool:
    text = str(pattern or "").lower()
    explicit_two_col = any(term in text for term in ("two-column", "two column", "2-column", "2 column", "split", "side-by-side"))
    explicit_right = any(term in text for term in (" right ", "right-", "right:", "right column", "right card", "right panel", "proof card"))
    explicit_left = any(term in text for term in (" left ", "left-", "left:", "left column", "left card", "left panel"))
    return explicit_two_col or "proof card" in text or (explicit_left and explicit_right)


def _requires_grid_layout(pattern: str) -> bool:
    text = str(pattern or "").lower()
    return any(term in text for term in ("grid", "comparison", "matrix", "cards-"))


def _visible_svg_text_positions(svg_text: str) -> list[tuple[float, float, str]]:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return []
    positions: list[tuple[float, float, str]] = []
    _collect_visible_svg_text_positions(root, positions, hidden=False, inherited=(0.0, 0.0))
    return positions


def _collect_visible_svg_text_positions(
    elem: ET.Element,
    positions: list[tuple[float, float, str]],
    *,
    hidden: bool,
    inherited: tuple[float, float],
) -> None:
    local = _svg_local_name(elem.tag)
    current_hidden = hidden or _svg_element_hidden(elem)
    if current_hidden or local in {"script", "style", "title", "desc", "defs", "lineargradient", "radialgradient", "stop", "filter", "clippath", "mask"}:
        return

    tx, ty = _svg_translate(elem.attrib.get("transform", ""))
    origin = (inherited[0] + tx, inherited[1] + ty)
    if local == "text":
        x = _float_attr(elem.attrib.get("x"))
        y = _float_attr(elem.attrib.get("y"))
        text = _normalize_content_text(html.unescape(_element_visible_text(elem)))
        if x is not None and y is not None and text and not re.fullmatch(r"\d{1,2}\s*/\s*\d{1,2}", text):
            positions.append((origin[0] + x, origin[1] + y, text))
    for child in list(elem):
        _collect_visible_svg_text_positions(child, positions, hidden=current_hidden, inherited=origin)


def _collect_visible_svg_positions(
    elem: ET.Element,
    positions: list[tuple[float, float]],
    *,
    hidden: bool,
    inherited: tuple[float, float],
) -> None:
    local = _svg_local_name(elem.tag)
    current_hidden = hidden or _svg_element_hidden(elem)
    if current_hidden or local in {"script", "style", "title", "desc", "defs", "lineargradient", "radialgradient", "stop", "filter", "clippath", "mask"}:
        return

    tx, ty = _svg_translate(elem.attrib.get("transform", ""))
    origin = (inherited[0] + tx, inherited[1] + ty)
    point = _svg_element_position(elem, origin)
    if point is not None:
        positions.append(point)
    for child in list(elem):
        _collect_visible_svg_positions(child, positions, hidden=current_hidden, inherited=origin)


def _svg_element_position(elem: ET.Element, inherited: tuple[float, float]) -> tuple[float, float] | None:
    local = _svg_local_name(elem.tag)
    attrs = elem.attrib
    if local in {"text", "tspan", "rect", "image", "use"}:
        x = _float_attr(attrs.get("x"))
        y = _float_attr(attrs.get("y"))
        if x is not None and y is not None:
            return inherited[0] + x, inherited[1] + y
    if local in {"circle", "ellipse"}:
        cx = _float_attr(attrs.get("cx"))
        cy = _float_attr(attrs.get("cy"))
        if cx is not None and cy is not None:
            return inherited[0] + cx, inherited[1] + cy
    if local == "line":
        x = _float_attr(attrs.get("x1"))
        y = _float_attr(attrs.get("y1"))
        if x is not None and y is not None:
            return inherited[0] + x, inherited[1] + y
    if local in {"polygon", "polyline"}:
        point = _first_svg_point(attrs.get("points", ""))
        if point is not None:
            return inherited[0] + point[0], inherited[1] + point[1]
    return None


def _svg_translate(transform: str) -> tuple[float, float]:
    match = re.search(r"translate\(\s*(-?\d+(?:\.\d+)?)(?:[\s,]+(-?\d+(?:\.\d+)?))?", str(transform or ""), flags=re.IGNORECASE)
    if not match:
        return 0.0, 0.0
    return float(match.group(1)), float(match.group(2) or 0)


def _first_svg_point(points: str) -> tuple[float, float] | None:
    nums = re.findall(r"-?\d+(?:\.\d+)?", str(points or ""))
    if len(nums) < 2:
        return None
    return float(nums[0]), float(nums[1])


def _float_attr(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(value))
    if not match:
        return None
    return float(match.group(1))


def _svg_visible_text(svg_text: str) -> str:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return _svg_visible_text_fallback(svg_text)

    parts: list[str] = []
    _collect_visible_svg_text(root, parts, hidden=False, in_text=False)
    return _normalize_content_text(html.unescape(" ".join(parts)))


def _svg_visible_text_fallback(svg_text: str) -> str:
    text = re.sub(
        r"<(?:script|style|title|desc)\b.*?</(?:script|style|title|desc)>",
        " ",
        svg_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    return _normalize_content_text(html.unescape(text))


def _collect_visible_svg_text(elem: ET.Element, parts: list[str], *, hidden: bool, in_text: bool) -> None:
    local = _svg_local_name(elem.tag)
    current_hidden = hidden or _svg_element_hidden(elem)
    if current_hidden or local in {"script", "style", "title", "desc"}:
        return

    current_in_text = in_text or local in {"text", "tspan"}
    if current_in_text and elem.text:
        parts.append(elem.text)
    for child in list(elem):
        child_hidden = current_hidden or _svg_element_hidden(child)
        _collect_visible_svg_text(child, parts, hidden=child_hidden, in_text=current_in_text)
        if current_in_text and not child_hidden and child.tail:
            parts.append(child.tail)


def _svg_element_hidden(elem: ET.Element) -> bool:
    attrs = {str(key).lower(): str(value).strip().lower() for key, value in elem.attrib.items()}
    style = _parse_svg_style(attrs.get("style", ""))
    merged = {**style, **attrs}
    if merged.get("display") == "none":
        return True
    if merged.get("visibility") in {"hidden", "collapse"}:
        return True
    if _svg_numeric_attr_is_zero(merged.get("opacity")):
        return True
    if _svg_numeric_attr_is_zero(merged.get("fill-opacity")):
        return True
    if merged.get("fill") == "none" and not merged.get("stroke"):
        return True
    if _svg_numeric_attr_is_zero(merged.get("font-size")):
        return True
    return False


def _parse_svg_style(style: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in str(style or "").split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        parsed[key.strip().lower()] = value.strip().lower()
    return parsed


def _svg_numeric_attr_is_zero(value: str | None) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    if not text:
        return False
    if text.endswith("%"):
        text = text[:-1].strip()
        scale = 100.0
    else:
        scale = 1.0
    try:
        return float(text) / scale <= 0
    except ValueError:
        return False


def _svg_local_name(tag: str) -> str:
    return str(tag).rsplit("}", 1)[-1].lower()


def _contains_content_fragment(visible_text: str, expected: str) -> bool:
    fragment = _content_match_fragment(expected)
    if not fragment:
        return True
    if fragment in visible_text:
        return True
    if _contains_cjk(fragment):
        compact_visible = _compact_cjk_text(visible_text)
        if _compact_cjk_text(fragment) in compact_visible:
            return True
        return _cjk_parts_covered(fragment, compact_visible)
    return False


def _content_match_fragment(text: str) -> str:
    normalized = _normalize_content_text(text)
    if len(normalized) <= 80:
        return normalized
    words = normalized.split()
    if len(words) >= 8:
        return " ".join(words[:8])
    return normalized[:80]


def _normalize_content_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))


def _compact_cjk_text(text: str) -> str:
    return re.sub(r"\s+", "", _normalize_content_text(text))


def _cjk_parts_covered(expected: str, compact_visible: str) -> bool:
    parts = [
        _compact_cjk_text(part)
        for part in re.split(r"[:：,，;；、|/\\\-—]+", str(expected or ""))
        if _compact_cjk_text(part)
    ]
    meaningful = [part for part in parts if len(part) >= 2]
    if len(meaningful) < 2:
        return False
    return all(part in compact_visible for part in meaningful)


def _blocking_issues(issues, *, strict_quality: bool):
    blocking_levels = {"error", "warning"} if strict_quality else {"error"}
    return [issue for issue in issues if issue.level in blocking_levels]


def _dedupe_issues(issues):
    seen = set()
    deduped = []
    for issue in issues:
        key = (issue.level, Path(issue.file).name, issue.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def _issue_to_dict(issue) -> dict:
    return {
        "level": issue.level,
        "file": str(issue.file),
        "message": issue.message,
    }


def _format_issue_feedback(issues) -> str:
    if not issues:
        return "No blocking issues."
    lines = []
    for issue in issues[:_MAX_FEEDBACK_ITEMS]:
        lines.append(f"- {issue.level.upper()} {Path(issue.file).name}: {issue.message}")
    remaining = len(issues) - len(lines)
    if remaining > 0:
        lines.append(f"- ... {remaining} more issues omitted; fix the same class of problems globally.")
    return "\n".join(lines)


def _issue_message_preview(issues, *, limit: int = 3) -> list[str]:
    return [issue.message for issue in list(issues or [])[:limit]]


def _write_attempt_log(
    log_dir: Path, slide_index: int, attempt: int, path: Path,
    raw_content: str, issues, *, blocking_count: int, executor_brief: str = "", visual_feedback: str = "",
    error: str = "",
) -> None:
    payload = {
        "slide": slide_index,
        "attempt": attempt + 1,
        "path": str(path),
        "raw_chars": len(raw_content),
        "issues": [_issue_to_dict(issue) for issue in issues],
        "blocking_count": blocking_count,
        "has_executor_brief": bool(executor_brief),
        "executor_brief_chars": len(executor_brief),
        "has_visual_feedback": bool(visual_feedback),
        "visual_feedback_chars": len(visual_feedback),
    }
    if error:
        payload["error"] = error
    log_path = log_dir / f"slide_{slide_index:02d}_attempt_{attempt + 1:02d}.json"
    log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_system_prompt(
    spec_lock: dict, w: int, h: int, *,
    extra: str = "",
    design_guide: str = "",
    references: str = "",
) -> str:
    """Build the system prompt with global design specifications."""
    p = spec_lock.get("palette")
    if not isinstance(p, dict):
        raise ValueError("spec_lock.json missing required 'palette' object")
    font = spec_lock.get("font_family")
    if not font:
        raise ValueError("spec_lock.json missing required 'font_family'")

    base = f"""You are an expert SVG slide designer. You create individual SVG pages for a presentation deck.

## Global Specifications
- Canvas: {w}×{h} pixels, viewBox="0 0 {w} {h}"
- Background: {p.get('background', '#FFFFFF')}
- Surface: {p.get('surface', '#F8FAFC')}
- Accent: {p.get('accent', '#3B82F6')}
- Text primary: {p.get('text', '#111827')}
- Text body: {p.get('body', '#334155')}
- Text muted: {p.get('muted', '#94A3B8')}
- Font family: {font}

## SVG Rules
- MUST use xmlns="http://www.w3.org/2000/svg"
- MUST use semantic group IDs: id="background", id="content-title-NN", id="content-body-NN", etc.
- MUST include page number in footer area
- Allowed: rect, circle, ellipse, line, text, tspan, path, polygon, polyline, g, defs, linearGradient, radialGradient, stop, filter, clipPath, pattern, use, image
- BANNED: script, foreignObject, iframe, animate, animateTransform, set, animateMotion, onclick, onload, on* attributes
- Use SVG presentation attributes, not CSS style/class attributes
- Never introduce colors or primary fonts that are absent from the spec lock
- Do not use generic red/yellow/green UI dots or syntax-highlight colors unless those exact colors appear in the spec lock; map decorative/status colors to accent, secondary_accent, muted, text, or surface values from the palette
- All text must be XML-escaped
- Use stable, semantic IDs for all groups

## Design Principles
- Compose like an editorial/poster designer, not a form-filler: use the FULL canvas as a deliberate composition, never a default top-left stack with wasted space.
- Establish ONE clear focal point per page with strong scale contrast — make the hero element (key title, number, or word) dramatically larger than supporting text so the eye lands somewhere first.
- Embrace asymmetry and intentional negative space as design tools; let emptiness frame the focal point rather than reading as unused canvas.
- Vary the composition's entry point and alignment across pages (left, centered, offset, or anchored to a strong element) — do NOT default every element to a left x=80 column.
- Use the accent color decisively for a single focal moment, not scattered evenly across the page; reserve muted tones for secondary content.
- Match visual density to content importance, and vary decoration per page so consecutive pages do not look the same.
- Ensure readable contrast ratios and keep generous margins so text never crowds the canvas edge.
- If QA feedback is provided, fix every listed issue in the next attempt; do not preserve invalid SVG choices"""

    if design_guide:
        # The design guide carries the palette table, typography ramp, concrete
        # layout templates, and the pre-save checklist. Truncating at 3000 cut
        # most of that before the LLM saw it. 8000 keeps the layout examples
        # and checklist intact for typical themes.
        guide_budget = 8000
        guide_excerpt = design_guide[:guide_budget] if len(design_guide) > guide_budget else design_guide
        if len(design_guide) > guide_budget:
            guide_excerpt = guide_excerpt.rstrip() + "\n... (design guide trimmed to fit context budget)"
        base += f"\n\n## Design Guide\n{guide_excerpt}"

    if references:
        base += f"\n\n## Reference Materials\n{references}"

    if extra:
        base += f"\n\n{extra}"
    return base


def _build_page_prompt(
    plan,
    total: int,
    spec_lock: dict,
    design_guide: str,
    w: int,
    h: int,
    previous_paths: list[Path],
    *,
    spec_lock_text: str = "",
    executor_brief: str = "",
    feedback: str = "",
    visual_feedback: str = "",
) -> str:
    """Build the per-page user prompt with specific design intent."""
    idx = plan.index
    p = spec_lock["palette"]
    font = spec_lock["font_family"]

    rhythm = getattr(plan, "rhythm", "breathing") or "breathing"
    strategy = getattr(plan, "visual_strategy", "standard-content") or "standard-content"
    pattern = getattr(plan, "layout_pattern", "") or ""
    chart_type = getattr(plan, "chart_type", "") or ""
    image_hint = getattr(plan, "image_hint", "") or ""
    coordinate_guidance = _layout_coordinate_guidance(plan.layout, pattern, w, h)
    spec_polish_contract = _format_spec_polish_contract(spec_lock, spec_lock_text)
    bullet_rendering_contract = _format_bullet_rendering_contract(plan, spec_lock)

    rhythm_desc = {
        "anchor": "HIGH emphasis — use bold decoration, large typography, strong visual hierarchy. This page should command attention.",
        "breathing": "MODERATE emphasis — clean layout with subtle decoration. Balance content clarity with visual appeal.",
        "dense": "LOW emphasis — minimal decoration, compact layout. Focus on fitting information clearly.",
    }

    items_text = ""
    for i, item in enumerate(plan.items):
        items_text += f"  {i+1}. [{item.type}] {item.primary}"
        if item.secondary:
            items_text += f" — {item.secondary}"
        if item.tertiary:
            items_text += f" ({item.tertiary})"
        items_text += "\n"
    required_text_contract = _format_required_text_contract(plan)

    context_note = ""
    if previous_paths:
        diversity_hint = _build_layout_diversity_hint(previous_paths)
        last_two = previous_paths[-2:]
        context_note = f"\n## Context (previous pages for design continuity)\n"
        for pp in last_two:
            ctx_line = f"- {pp.name} already generated"
            sig = _read_layout_signature(pp)
            if sig:
                ctx_line += f" (layout signature: {sig})"
            ctx_line += " — avoid repeating its exact decoration layout, focal placement, and entry alignment"
            context_note += ctx_line + "\n"
        if diversity_hint:
            context_note += diversity_hint

    feedback_block = ""
    if feedback:
        feedback_block = f"""
## QA Feedback From Previous Attempt
Your previous SVG for this page failed the production gate. Rewrite the page and fix all issues below:
{feedback}
"""

    visual_feedback_block = ""
    if visual_feedback:
        preserve_block = _format_visual_feedback_preserve_contract(visual_feedback)
        visual_feedback_block = f"""
## Rendered Visual Repair Contract
These observations come from rendered slide review and are mandatory repair targets for this rewrite. Prioritize `repair_prompt` items when present; otherwise treat `actions` / `action` entries as executor-ready repair instructions, then use issues and summaries for context. Fix the visible defects without deleting, hiding, paraphrasing away, or moving off-canvas any required title/body text from the Content Fidelity Contract:
{visual_feedback}
{preserve_block}

Repair geometry rules:
- Treat any text that visual feedback says to preserve, keep, retain, maintain, or 保留 as required visible content too, even if it is only mentioned in `repair_prompt`, `actions`, or `action`.
- If feedback mentions a panel, card, or surface background, create a visible `<rect>` behind the related text; moving text alone is not a valid repair.
- If feedback mentions a left/right panel, implement that side-specific placement with concrete x/width coordinates instead of a full-width generic content block.
- Preserve the planner's layout_pattern during repairs. If the pattern requires two-column, grid, comparison, left/right, or proof-card structure, place actual visible title/body content in the required regions; decorative lines, empty cards, or background shapes alone do not satisfy the layout.
- If feedback mentions an accent stripe or rail, create a visible narrow `<rect>` using the locked accent color.
- If feedback mentions bullet marker color, render separate visible markers (for example circles) or visible bullet glyphs in the locked accent color.
- Preserve deck chrome and footer/page number unless the feedback explicitly asks to change them.
"""

    spec_block = ""
    if spec_lock_text:
        spec_block = f"""
## Spec Lock Snapshot
This is the authoritative lock re-read for this page attempt. Copy exact palette and typography values from here.
```text
{spec_lock_text[:6000]}
```
"""

    brief_block = ""
    if executor_brief:
        brief_block = f"""
## AI Strategist Executor Brief
This is the validated planner-to-executor design contract for this specific slide. Follow it unless QA or visual feedback below requires a repair.
{executor_brief}
"""

    design_contract_block = f"""
## Planner Design Execution Contract
Implement the plan's visual_strategy and layout_pattern as hard layout requirements, not inspiration. The SVG must contain visible geometry that expresses the named visual device or hierarchy, and the arrangement must follow the stated placement/structure. If the executor brief below conflicts with the compact fields here, prefer the executor brief. Do not replace this contract with a generic centered title or bullet template. Do not satisfy a two-column/grid/comparison contract with empty decorative shapes: put required visible content in the named regions.
- Required visual device / hierarchy: {strategy}
- Required placement / structure: {pattern or plan.layout}
- Layout family: {plan.layout}
{coordinate_guidance}
"""

    prompt = f"""Create SVG page {idx} of {total}.
{feedback_block}
{visual_feedback_block}
{spec_block}
{brief_block}
{design_contract_block}
{spec_polish_contract}
{bullet_rendering_contract}

## Page Design Intent
- Layout: {plan.layout}
- Visual strategy: {strategy}
- Layout pattern: {pattern}
- Rhythm: **{rhythm}** — {rhythm_desc.get(rhythm, "Standard visual emphasis.")}
- Chart type: {chart_type or "none"}
- Image hint: {image_hint or "none"}
{"- Design density: " + plan.density if plan.density else ""}

## Content
Title: {plan.title}
Items:
{items_text if items_text else "  (no body items — use full-bleed hero typography)"}
{"Notes: " + plan.notes if plan.notes else ""}
{required_text_contract}

## Requirements
1. Output ONLY the SVG code, no markdown fences
2. Start with: <svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">
3. End with: </svg>
4. Use palette: bg={p.get('background')}, accent={p.get('accent')}, text={p.get('text')}
5. Font: {font}
6. Footer must show: {idx:02d} / {total:02d}; render it as right-aligned text inside the footer with `text-anchor="end"` and x <= {w - 40}
7. Include semantic group IDs: id="background", id="decor-{idx:02d}", id="content-title-{idx:02d}", id="content-body-{idx:02d}"
8. Use direct SVG attributes only: fill, stroke, font-family, font-size, opacity. Do not use class or style.
9. Keep text inside the canvas. data-fit-box is optional: omit it unless the box fully contains the rendered text; an undersized data-fit-box fails QA.
{"Additional density instruction: this is a DENSE page — use minimal decoration, compact spacing." if rhythm == "dense" else ""}
{"Additional density instruction: this is an ANCHOR page — use bold decoration, hero typography, strong visual impact." if rhythm == "anchor" else ""}
{context_note}
"""
    return prompt


def _format_required_text_contract(plan) -> str:
    required = _required_visible_strings(plan)
    if not required:
        return ""

    lines = [
        "",
        "## Content Fidelity Contract",
        "The following strings must appear as visible SVG text in <text> or <tspan> elements. Do not place them only in <title>, <desc>, comments, IDs, or metadata. Keep wording exact except for safe line breaks.",
    ]
    for label, text in required:
        lines.append(f'- {label}: "{xml_escape(text)}"')
    return "\n".join(lines)


def _format_visual_feedback_preserve_contract(visual_feedback: str) -> str:
    lines = _visual_feedback_preserve_lines(visual_feedback)
    if not lines:
        return ""
    rendered = ["", "Preserve Text From Visual Feedback:"]
    rendered.extend(f"- {xml_escape(line)}" for line in lines)
    return "\n".join(rendered)


def _format_spec_polish_contract(spec_lock: dict, spec_lock_text: str = "") -> str:
    palette = spec_lock.get("palette", {}) if isinstance(spec_lock.get("palette"), dict) else {}
    hints = f"{spec_lock.get('design_hints', '')}\n{spec_lock_text}".lower()
    lines = []
    if "lineargradient" in hints and any(term in hints for term in ("card", "panel", "surface")):
        surface = palette.get("surface", "#1E293B")
        background = palette.get("background", "#0F172A")
        lines.append(
            "If you draw a content card, panel, proof card, or surface background, define a `<linearGradient>` in `<defs>` "
            f"and use `fill=\"url(#...)\"` on that rect; do not use a flat `{surface}` card fill when the spec asks for gradient depth. "
            f"Use stops from `{surface}` toward `{background}` unless the spec gives a more specific gradient."
        )
    if "footer" in hints:
        text_secondary = palette.get("text_secondary") or palette.get("body") or palette.get("text")
        muted = palette.get("muted") or palette.get("text_tertiary")
        if text_secondary:
            lines.append(
                f"Footer/page-number text must be readable on the footer bar: use `{text_secondary}` or another approved readable text color, "
                f"not the low-contrast muted value `{muted}`."
            )
    if "progress dots" in hints:
        accent = palette.get("accent", "#3B82F6")
        lines.append(
            f"Render a compact 3-dot progress indicator inside the footer bar using the locked accent color `{accent}`. "
            "Place the dots near the left edge of the footer (for example cx=24, 40, 56 and cy=704 on a 1280x720 canvas). "
            "Keep the required page number visible and right-aligned; progress dots supplement it, not replace it."
        )
    if not lines:
        return ""
    return "\n## Spec Polish Contract\n" + "\n".join(f"- {line}" for line in lines) + "\n"


def _format_bullet_rendering_contract(plan, spec_lock: dict) -> str:
    bullet_count = sum(
        1 for item in list(getattr(plan, "items", []) or [])
        if str(getattr(item, "type", "") or "").strip().lower() == "bullet"
    )
    if bullet_count <= 0:
        return ""

    palette = spec_lock.get("palette", {}) if isinstance(spec_lock.get("palette"), dict) else {}
    accent = palette.get("accent", "#3B82F6")
    body = palette.get("text_secondary") or palette.get("body") or palette.get("text")
    text = palette.get("text")
    return (
        "\n## Bullet Rendering Contract\n"
        f"- This slide has {bullet_count} planned `[bullet]` item(s). Each `[bullet]` item must have a visible marker before the text.\n"
        f"- Prefer separate SVG `<circle>` markers in the locked accent color `{accent}`; bullet glyphs are acceptable only if visibly rendered before the text.\n"
        f"- Bullet body text must use the body/text_secondary color `{body}`; do not use the primary title color `{text}` for bullet body copy. Code terms may use the locked code font and an approved accent color.\n"
        "- Do not render planned `[bullet]` items as plain paragraph lines with no marker.\n"
        "- Keep the marker and its bullet text on the same baseline, with consistent indentation.\n"
    )


def _read_layout_signature(svg_path: Path) -> str:
    """Extract the structural layout signature of a generated SVG page.

    Mirrors ``svg_qa._extract_layout_signature``: the sorted set of normalized
    top-level group IDs. Two pages with the same signature share the same
    structural skeleton, which is the cheapest predictor of visual monotony.
    Returns an empty string when the file cannot be parsed.
    """
    try:
        root = ET.fromstring(svg_path.read_text(encoding="utf-8"))
    except (ET.ParseError, OSError):
        return ""
    ids = []
    for child in list(root):
        tag = _svg_local_name(child.tag)
        if tag == "g":
            gid = child.attrib.get("id", "")
            if gid:
                normalized = re.sub(r"-\d+$", "", gid)
                ids.append(normalized)
    return "|".join(sorted(ids))


def _build_layout_diversity_hint(previous_paths: list[Path]) -> str:
    """Warn the executor when recent pages share an identical layout signature.

    Returns a prompt fragment that explicitly asks for a different composition
    when the last 2 pages (or 2 of the last 3) share the same structural
    skeleton. This is the per-page counterpart of svg_qa's project-level
    ``_check_layout_variety``: it steers the LLM *before* a third identical page
    is produced, instead of flagging it after the fact.
    """
    recent = previous_paths[-3:]
    if len(recent) < 2:
        return ""
    sigs = [_read_layout_signature(p) for p in recent]
    # Count how many of the most recent pages share the immediately-prior signature.
    last_sig = sigs[-1]
    if not last_sig:
        return ""
    run = 0
    for s in reversed(sigs[:-1]):
        if s == last_sig:
            run += 1
        else:
            break
    if run < 1:
        return ""
    n = run + 1
    return (
        f"\n## Layout Variety Constraint (MANDATORY)\n"
        f"The previous {n} generated page(s) share the same structural layout "
        f"signature ({last_sig}). This page MUST use a visibly different "
        f"composition: change the focal placement (left/center/right/diagonal), "
        f"the entry alignment, the primary container shape (full-width band vs "
        f"cards vs hero), or the negative-space ratio. Producing a third near-"
        f"identical page fails the deck's visual-variety gate.\n"
    )


def _layout_coordinate_guidance(layout: str, pattern: str, w: int, h: int) -> str:
    """Translate common planner layout words into concrete SVG regions."""
    normalized = f"{layout} {pattern}".lower()
    safe_bottom = min(h - 72, 648)
    lines = ["- Safe-area baseline (a starting point you MAY deviate from for stronger composition, as long as all text stays within safe margins: x >= 64, x <= w-64, and above the footer band):"]
    if _requires_left_right_layout(normalized):
        lines.extend([
            "  - left region: x=80..600, y=112..648",
            "  - right region: x=680..1200, y=112..648",
            "  - keep at least 48 px gutter between left and right regions",
        ])
    elif _requires_grid_layout(normalized):
        lines.extend([
            "  - grid region: x=80..1200, y=132..648",
            "  - two-column cards: left x=80..600, right x=680..1200",
            "  - two-row cards: top y=132..360, bottom y=400..648",
        ])
    elif any(term in normalized for term in ("top", "lower", "bottom", "row")):
        lines.extend([
            "  - top region: x=80..1200, y=96..260",
            f"  - lower region: x=80..1200, y=300..{safe_bottom}",
            "  - reserve y=688..720 for footer only",
        ])
    elif any(term in normalized for term in ("metric", "proof", "card")):
        lines.extend([
            "  - metric/proof card region: x=80..460, y=148..628",
            "  - supporting text region: x=520..1200, y=148..628",
        ])
    elif any(term in normalized for term in ("full-bleed", "image", "hero")):
        lines.extend([
            f"  - hero/title region: x=96..760, y=120..{min(h - 180, 540)}",
            "  - decorative/image region: x=780..1200, y=96..648",
        ])
    else:
        lines.extend([
            "  - safe content region: x=80..1200, y=96..648",
            "  - title band: x=96..1184, y=80..150",
            "  - body region: x=96..1184, y=170..648",
        ])
    lines.append(
        "- Treat these regions as a flexible baseline, not slots to fill: deviate freely for a more striking layout — shift the focal element, lean into asymmetry, or anchor content off the default left column."
    )
    lines.append(
        "- Any deviation is fine provided all required text stays fully inside the canvas (x >= 64, x <= w-64) and clear of the footer band."
    )
    return "\n".join(lines)


def _required_visible_strings(plan) -> list[tuple[str, str]]:
    """Return source-backed strings that must survive as visible SVG text."""
    required: list[tuple[str, str]] = []
    title = str(getattr(plan, "title", "") or "").strip()
    if title:
        required.append(("title", title))
    for index, item in enumerate(list(getattr(plan, "items", []) or [])[:6], start=1):
        for field in ("primary", "secondary", "tertiary"):
            text = str(getattr(item, field, "") or "").strip()
            if text:
                label = f"item {index}" if field == "primary" else f"item {index} {field}"
                required.append((label, text))
    return required


def _extract_svg(response_text: str) -> str:
    """Extract SVG content from LLM response, stripping markdown fences."""
    svg, _ = _extract_svg_with_issues(response_text)
    return svg


def _extract_svg_with_issues(response_text: str) -> tuple[str, list[str]]:
    """Extract SVG content and report protocol violations for LLM retry."""
    text = response_text.strip()
    issues: list[str] = []

    if text.startswith("```"):
        issues.append("Model output used markdown fences; output ONLY raw SVG code.")
        text = re.sub(r"^```(?:xml|svg)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

    svg_starts = list(re.finditer(r"<svg[\s>]", text))
    svg_ends = list(re.finditer(r"</svg>", text))
    if len(svg_starts) > 1 or len(svg_ends) > 1:
        issues.append("Model output contained multiple SVG documents; output exactly one complete <svg> element.")

    if not text.startswith("<svg"):
        if svg_starts:
            prefix = text[:svg_starts[0].start()].strip()
            if prefix:
                issues.append("Model output included prose before the SVG; output ONLY the SVG element.")
            text = text[svg_starts[0].start():]
        elif text:
            issues.append("Model output did not start with <svg>; output ONLY a complete <svg>...</svg> document.")

    if "</svg>" in text:
        end = text.rfind("</svg>") + len("</svg>")
        suffix = text[end:].strip()
        if suffix:
            issues.append("Model output included extra text after the SVG; output ONLY the SVG element.")
        text = text[:end]

    return text.strip(), issues
