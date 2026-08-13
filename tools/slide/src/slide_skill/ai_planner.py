"""AI Strategist for source-to-slide planning."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from .ai_trace import ai_response_metadata, write_ai_trace
from .content_planner import ContentConfig, ContentItem, SlidePlan
from .provider_response import (
    DEFAULT_ROLE_MAX_TOKENS,
    ProviderResponse,
    escalate_budget,
    parse_provider_response,
)
from .util import ensure_dir

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"
DEFAULT_MAX_TOKENS = DEFAULT_ROLE_MAX_TOKENS["planner"]
DEFAULT_TEMPERATURE = 0.3
DEFAULT_RETRIES = 2
ALLOWED_DENSITIES = {"sparse", "normal", "dense"}
ALLOWED_RHYTHMS = {"anchor", "breathing", "dense", ""}
GENERIC_DESIGN_TEXT = {
    "",
    "none",
    "n/a",
    "na",
    "default",
    "standard",
    "generic",
    "standard-content",
    "specific visual intent",
    "specific arrangement",
    "layout",
    "visual",
}
GENERIC_SOURCE_ANCHORS = {
    "source",
    "topic",
    "content",
    "overview",
    "summary",
    "title",
}
DESIGN_SPECIFIC_TERMS = {
    "accent",
    "arrow",
    "badge",
    "bar",
    "block",
    "border",
    "bullet",
    "callout",
    "card",
    "chart",
    "checkmark",
    "circle",
    "cluster",
    "column",
    "compact",
    "comparison",
    "connector",
    "diagonal",
    "geometry",
    "grid",
    "grouping",
    "hero",
    "hierarchy",
    "icon",
    "image",
    "marker",
    "metric",
    "milestone",
    "node",
    "number",
    "numbered",
    "panel",
    "process",
    "proof",
    "quote",
    "rail",
    "rule",
    "serif",
    "sidebar",
    "stack",
    "stacked",
    "strikethrough",
    "tag",
    "timeline",
    "underline",
    "visual",
    "卡片",
    "标题",
    "要点",
    "强调",
    "层级",
    "色带",
    "图形",
    "列表",
    "项目符号",
    "圆点",
    "圆圈",
    "节点",
    "时间线",
    "时间轴",
    "表格",
    "网格",
    "引用",
    "引号",
    "图标",
    "箭头",
    "流程",
    "编号",
    "序号",
    "关键词",
    "删除线",
    "警示",
    "高亮",
    "对比",
    "矩阵",
    "仪表盘",
    "指标",
    "数字",
    "大字",
    "配图",
    "插图",
    "分隔",
    "分隔线",
    "边框",
    "色块",
    "渐变",
    "annotation",
    "attribution",
    "box",
    "boxes",
    "circles",
    "divider",
    "dividing",
    "footer",
    "header",
    "label",
    "labels",
    "line",
    "lines",
    "section",
    "sections",
    "separated",
    "separator",
    "step",
    "steps",
    "axis",
    "banner",
    "ribbon",
    "table",
    "diagram",
    "loop",
    "cycle",
    "checklist",
    "taxonomy",
    "barrier",
    "metaphor",
    "version",
    "revision",
    "flow",
    "flowchart",
    "funnel",
    "pyramid",
    "venn",
    "gauge",
    "donut",
    "pie",
    "scatter",
    "mindmap",
    "sankey",
    "treemap",
    "waterfall",
    "radar",
    "heatmap",
    "matrix",
    "quadrant",
    "swimlane",
    "kanban",
    "roadmap",
    "spectrum",
    "ladder",
    "stair",
    "orbit",
    "concentric",
    "nested",
    "overlay",
    "tag",
    "tags",
    "label",
    "labels",
    "list",
    "lists",
    "choice",
    "choices",
    "options",
    "test",
    "quiz",
    "question",
    "point",
    "points",
    "scenario",
    "scenarios",
}
LAYOUT_SPECIFIC_TERMS = {
    "above",
    "below",
    "bottom",
    "card",
    "center",
    "centered",
    "vertical",
    "vertically",
    "horizontal",
    "horizontally",
    "column",
    "columns",
    "full-bleed",
    "full-width",
    "grid",
    "left",
    "left-aligned",
    "aligned",
    "lower",
    "upper",
    "panel",
    "rail",
    "right",
    "row",
    "rows",
    "side",
    "spanning",
    "indented",
    "prefix",
    "suffix",
    "connectors",
    "node",
    "nodes",
    "stacked",
    "sidebar",
    "stack",
    "top",
    "左侧",
    "右侧",
    "上方",
    "下方",
    "上下",
    "左右",
    "顶部",
    "底部",
    "中间",
    "居中",
    "居左",
    "居右",
    "标题",
    "卡片",
    "列表",
    "要点",
    "网格",
    "分栏",
    "分列",
    "两列",
    "三列",
    "四列",
    "多列",
    "每行",
    "每列",
    "行",
    "列",
    "对齐",
    "排列",
    "分布",
    "均匀",
    "等距",
    "横向",
    "纵向",
    "垂直",
    "水平",
    "并排",
    "堆叠",
    "环绕",
    "节点",
    "时间轴",
    "表头",
}


def plan_slides_with_ai(
    source_text: str,
    config: ContentConfig | None = None,
    *,
    project_path: Path | str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    top_p: float | None = None,
    retries: int = DEFAULT_RETRIES,
) -> list[SlidePlan]:
    """Ask an OpenAI-compatible model to produce structured slide plans."""
    from openai import OpenAI

    cfg = config or ContentConfig()
    project = Path(project_path) if project_path else None
    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
        base_url=base_url or os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL),
    )
    selected_model = model or os.environ.get("OPENAI_PLANNER_MODEL") or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
    coverage_anchors = _source_coverage_anchors(source_text, cfg)
    source_numeric_tokens = _numeric_tokens(source_text)
    if project:
        _clear_previous_ai_planner_result(project)
        _write_coverage_anchors(project, coverage_anchors)
    feedback = ""
    last_error = ""
    current_max_tokens = max_tokens

    for attempt in range(retries + 1):
        non_blocking: list[str] = []
        prompt = _build_planner_prompt(
            source_text,
            cfg,
            project,
            feedback=feedback,
            coverage_anchors=coverage_anchors,
            source_numeric_tokens=source_numeric_tokens,
        )
        request_payload = _build_planner_request(
            selected_model,
            prompt,
            max_tokens=current_max_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        try:
            provider, response_metadata = _call_planner_once(client, request_payload)
        except Exception as exc:  # noqa: BLE001 - provider SDKs expose many exception classes.
            last_error = _provider_error_message(exc)
            if project:
                _write_planner_attempt(project, attempt, "", error=last_error)
                write_ai_trace(
                    project,
                    stage="planner",
                    model=selected_model,
                    status="failed",
                    prompt=prompt,
                    raw="",
                    request=request_payload,
                    attempt=attempt + 1,
                    metadata={"error": last_error, "feedback": bool(feedback), "provider_error": True},
                )
            if attempt >= retries:
                if project:
                    _write_planner_failure(project, last_error, attempts=attempt + 1)
                raise RuntimeError(f"AI planner provider call failed after {retries + 1} attempts: {last_error}") from exc
            feedback = _planner_feedback(last_error)
            continue
        raw = provider.content
        if provider.blocks_parsing:
            # Completion-status gate: truncated/incomplete output never
            # reaches JSON parsing or repair. Retry with a raised budget
            # instead of feeding the generic validation feedback prompt.
            last_error = (
                f"provider response truncated (finish_reason={provider.finish_reason or 'missing'}) "
                f"at max_tokens={current_max_tokens}; reasoning_chars={provider.reasoning_chars}"
            )
            if project:
                _write_planner_attempt(project, attempt, raw, error=last_error)
                write_ai_trace(
                    project,
                    stage="planner",
                    model=selected_model,
                    status="truncated",
                    prompt=prompt,
                    raw=raw,
                    request=request_payload,
                    attempt=attempt + 1,
                    metadata={"error": last_error, "feedback": bool(feedback), **response_metadata},
                )
            if attempt >= retries:
                if project:
                    _write_planner_failure(project, last_error, attempts=attempt + 1)
                raise ValueError(f"AI planner failed after {retries + 1} attempts: {last_error}")
            escalated = escalate_budget(current_max_tokens)
            if escalated == current_max_tokens:
                cap_error = (
                    f"AI planner response still truncated at the {current_max_tokens}-token budget cap; "
                    "reduce source density or raise the planner max-tokens budget"
                )
                if project:
                    _write_planner_failure(project, cap_error, attempts=attempt + 1)
                raise ValueError(cap_error)
            current_max_tokens = escalated
            continue
        protocol_warnings: list[str] = []
        try:
            payload, protocol_warnings = _parse_json_payload(raw)
            plans, conversion_blocking, conversion_non_blocking = _plans_from_payload(payload, cfg)
            blocking, non_blocking = _validate_plans(
                plans,
                cfg,
                coverage_anchors=coverage_anchors,
                source_numeric_tokens=source_numeric_tokens,
            )
            blocking = conversion_blocking + blocking
            # Soft issues (repeated layouts, rhythm typos) are surfaced to the
            # model as feedback but never fail the attempt — they are
            # self-healed or merely stylistic.
            non_blocking = conversion_non_blocking + non_blocking
            if blocking:
                raise ValueError("; ".join(blocking))
            # Protocol warnings (fences, prose around parsed JSON) are
            # recoverable deviations: recorded and printed, never retried.
            for warning in protocol_warnings:
                print(f"[planner] protocol warning: {warning}", file=sys.stderr)
            # Non-blocking issues (soft rules, item over-count, flagged numbers)
            # are recorded as review warnings even on success.
            review_notes = "; ".join(non_blocking) if non_blocking else ""
            if project:
                _write_planner_artifacts(project, raw, plans, attempt=attempt, error="", warnings=review_notes)
                write_ai_trace(
                    project,
                    stage="planner",
                    model=selected_model,
                    status="passed",
                    prompt=prompt,
                    raw=raw,
                    request=request_payload,
                    attempt=attempt + 1,
                    metadata={
                        "slides": len(plans),
                        "feedback": bool(feedback),
                        "non_blocking_issues": len(non_blocking),
                        **({"protocol_warnings": protocol_warnings} if protocol_warnings else {}),
                        **response_metadata,
                    },
                )
            if non_blocking and attempt < retries:
                # Feed soft issues back so the model can vary layouts next time,
                # but accept this plan as a success either way.
                feedback = _planner_feedback("; ".join(non_blocking))
            return plans
        except ValueError as exc:
            last_error = str(exc)
            if non_blocking:
                recorded_error = "; ".join(non_blocking + [last_error])
            else:
                recorded_error = last_error
            if project:
                _write_planner_attempt(project, attempt, raw, error=recorded_error)
                write_ai_trace(
                    project,
                    stage="planner",
                    model=selected_model,
                    status="failed",
                    prompt=prompt,
                    raw=raw,
                    request=request_payload,
                    attempt=attempt + 1,
                    metadata={
                        "error": recorded_error,
                        "feedback": bool(feedback),
                        **({"protocol_warnings": protocol_warnings} if protocol_warnings else {}),
                        **response_metadata,
                    },
                )
            if attempt >= retries:
                if project:
                    _write_planner_failure(project, last_error, attempts=attempt + 1)
                raise ValueError(f"AI planner failed after {retries + 1} attempts: {last_error}") from exc
            feedback = _planner_feedback(last_error)
            if non_blocking:
                feedback = _planner_feedback("; ".join(non_blocking + [last_error]))

    if project:
        _write_planner_failure(project, last_error, attempts=retries + 1)
    raise ValueError(f"AI planner failed: {last_error}")


def _call_planner_once(
    client,
    request_payload: dict,
) -> tuple[ProviderResponse, dict]:
    response = client.chat.completions.create(**request_payload)
    provider = parse_provider_response(response)
    metadata = ai_response_metadata(response)
    metadata["reasoning_chars"] = provider.reasoning_chars
    return provider, metadata


def _build_planner_request(
    model: str,
    prompt: str,
    *,
    max_tokens: int,
    temperature: float,
    top_p: float | None,
) -> dict:
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are the Strategist for an SVG-first PowerPoint generator. "
                    "Return only JSON that can be converted into editable slide plans."
                ),
            },
            {"role": "user", "content": prompt},
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


def _build_planner_prompt(
    source_text: str,
    cfg: ContentConfig,
    project: Path | None,
    *,
    feedback: str = "",
    coverage_anchors: list[str] | None = None,
    source_numeric_tokens: set[str] | None = None,
) -> str:
    context = _project_context(project) if project else ""
    context_block = f"\n\n## Project Context\n{context}" if context else ""
    feedback_block = f"\n\n## Planner Feedback From Previous Attempt\n{feedback}" if feedback else ""
    coverage_block = _format_coverage_anchor_prompt(coverage_anchors or [])
    numeric_block = _format_numeric_grounding_prompt(source_numeric_tokens or set())
    source_excerpt = source_text[:12000]
    return f"""Create a production slide plan from the source Markdown.

Return JSON only with this shape:
{{
  "slides": [
    {{
      "index": 1,
      "layout": "cover|section-divider|bullet-list|two-column|metric-highlight|quote|timeline|comparison|closing|...",
      "title": "short slide title",
      "density": "sparse|normal|dense",
      "rhythm": "anchor|breathing|dense",
      "visual_strategy": "specific visual intent",
      "layout_pattern": "specific arrangement",
      "chart_type": "none or chart hint",
      "image_hint": "none or image concept",
      "notes": "speaker or design notes",
      "items": [
        {{"type": "text|bullet|metric|quote|step|table-row", "primary": "main text", "secondary": "", "tertiary": "", "meta": {{}}}}
      ]
    }}
  ]
}}

Rules:
- Create no more than {cfg.max_slides} slides.
- Domain: {cfg.domain}; audience: {cfg.audience}; max items per slide: {cfg.max_items_per_slide}.
- Use concise slide titles and preserve the source's meaning.
- Do not invent facts, metrics, names, or citations absent from the source.
- Numeric values in slide titles/items/notes must come from the source. Do not create estimates, rounded values, or illustrative metrics.
- Prefer varied layouts and rhythm; avoid three consecutive slides with the same layout.
- Mark only the strongest pages as rhythm "anchor"; use "dense" only when content truly needs compression.
- Every slide must include executor-ready visual_strategy and layout_pattern.
- visual_strategy must name a concrete visual device or hierarchy, such as accent rail, proof card, metric block, timeline, comparison grid, diagonal geometry, or image panel.
- layout_pattern must describe actual placement/structure, such as title left + proof card right, two-column grid, top metric row + lower bullets, or full-bleed image with bottom caption band.
- Put concrete repairable design intent in visual_strategy/layout_pattern/chart_type/image_hint.
- Do not use generic placeholders like "standard", "default", "specific visual intent", or "specific arrangement".
- Ensure indexes are 1-based and sequential.
- Cover every Required Source Coverage Anchor in slide titles or items. Do not hide source coverage in notes, visual_strategy, layout_pattern, chart_type, or image_hint.
{coverage_block}
{context_block}
{numeric_block}
{feedback_block}

## Source Markdown
```markdown
{source_excerpt}
```
"""


def _project_context(project: Path | None) -> str:
    if project is None:
        return ""
    parts: list[str] = []
    for name in ("spec_lock.md", "spec_lock.json", "design_guide.md"):
        path = project / name
        if path.exists():
            parts.append(f"### {name}\n{path.read_text(encoding='utf-8')[:2200]}")
    return "\n\n".join(parts)


def _parse_json_payload(raw: str) -> tuple[dict, list[str]]:
    """Parse planner output into ``(payload, protocol_warnings)``.

    Issue reporting is split into two channels:

    - ``protocol_warnings`` (returned): recoverable format deviations where
      the JSON itself parsed into a usable payload — markdown fences that
      were stripped successfully, prose around parsed JSON, repairable
      malformed JSON. These are telemetry only and must never trigger a
      retry or fail the attempt.
    - Blocking issues (raised as ``ValueError``): anything that prevents a
      usable payload. These keep the existing retry contract.
    """
    text = raw.strip()
    warnings: list[str] = []
    if text.startswith("```"):
        warnings.append("AI planner output used markdown fences; return raw JSON only.")
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("AI planner did not return JSON")
        prefix = text[:match.start()].strip()
        suffix = text[match.end():].strip()
        if prefix or suffix:
            warnings.append("AI planner output included prose outside JSON; return raw JSON only.")
        candidate = match.group(0)
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            # Last resort: repair malformed JSON (missing/trailing commas,
            # unescaped characters) instead of failing the whole attempt.
            from json_repair import repair_json

            payload = repair_json(candidate, return_objects=True)
            if not isinstance(payload, (dict, list)):
                raise ValueError("AI planner did not return JSON")
            warnings.append("AI planner output required JSON repair; return strictly valid JSON only.")
    if isinstance(payload, list):
        payload = {"slides": payload}
    if not isinstance(payload, dict):
        raise ValueError("AI planner JSON must be an object")
    return payload, warnings


def _plans_from_payload(payload: dict, cfg: ContentConfig) -> tuple[list[SlidePlan], list[str], list[str]]:
    raw_slides = payload.get("slides")
    if not isinstance(raw_slides, list) or not raw_slides:
        raise ValueError("AI planner JSON must include a non-empty slides list")

    plans: list[SlidePlan] = []
    blocking: list[str] = []
    non_blocking: list[str] = []
    if len(raw_slides) > cfg.max_slides:
        blocking.append(
            f"plan returned {len(raw_slides)} slides but max_slides is {cfg.max_slides}; reduce or consolidate slides"
        )
    for position, raw_slide in enumerate(raw_slides[:cfg.max_slides], start=1):
        if not isinstance(raw_slide, dict):
            blocking.append(f"slide entry {position} must be an object")
            continue
        raw_items = raw_slide.get("items", [])
        if not isinstance(raw_items, list):
            blocking.append(f"slide {position} items must be a list")
            raw_items = []
        if len(raw_items) > cfg.max_items_per_slide:
            non_blocking.append(
                f"slide {position} returned {len(raw_items)} items but max_items_per_slide is {cfg.max_items_per_slide}; consolidate items"
            )
        items = []
        for item_index, raw_item in enumerate(raw_items, start=1):
            item = _content_item_from_planner_item(raw_item)
            if item is None:
                blocking.append(f"slide {position} item {item_index} must be an object with primary text")
                continue
            items.append(item)
        density = str(raw_slide.get("density", cfg.default_density)).lower()
        if density not in ALLOWED_DENSITIES:
            non_blocking.append(
                f"slide {position} has invalid density {raw_slide.get('density')!r}; use sparse, normal, or dense"
            )
            density = cfg.default_density
        rhythm = str(raw_slide.get("rhythm", "breathing")).lower()
        if rhythm not in ALLOWED_RHYTHMS:
            non_blocking.append(
                f"slide {position} has invalid rhythm {raw_slide.get('rhythm')!r}; use anchor, breathing, or dense"
            )
            rhythm = "breathing"
        raw_index = raw_slide.get("index", position)
        if _parse_planner_index(raw_index) != position:
            non_blocking.append(
                f"slide {position} returned index {raw_index!r}; indexes must be sequential 1..N"
            )
        plans.append(SlidePlan(
            index=position,
            layout=_slide_text_field(raw_slide, "layout", "slide_layout", "layout_type", "layout_style", "template") or "bullet-list",
            title=_slide_text_field(raw_slide, "title", "slide_title", "heading", "headline", "name") or f"Slide {position}",
            items=items[:cfg.max_items_per_slide],
            notes=_slide_text_field(raw_slide, "notes", "speaker_notes", "speaker_note", "note", "speaker"),
            density=density,
            rhythm=rhythm,
            meta=raw_slide.get("meta") if isinstance(raw_slide.get("meta"), dict) else {},
            visual_strategy=_slide_text_field(
                raw_slide,
                "visual_strategy",
                "visual_intent",
                "visual_design",
                "design_strategy",
                "design_intent",
                "visual",
            ),
            chart_type=_slide_text_field(raw_slide, "chart_type", "chart", "chart_hint", "chart_kind"),
            image_hint=_slide_text_field(raw_slide, "image_hint", "image", "image_concept", "visual_hint", "image_prompt"),
            layout_pattern=_slide_text_field(
                raw_slide,
                "layout_pattern",
                "layout_description",
                "layout_structure",
                "arrangement",
                "placement",
                "layout_intent",
            ),
        ))
    if not plans:
        raise ValueError("AI planner produced no usable slides")
    return plans, blocking, non_blocking


def _parse_planner_index(value) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = re.search(r"\d+", value)
        if match:
            return int(match.group(0))
    return None


def _content_item_from_planner_item(raw_item) -> ContentItem | None:
    if isinstance(raw_item, dict):
        return _content_item_from_payload(raw_item)
    if isinstance(raw_item, str) and raw_item.strip():
        return ContentItem(type="text", primary=raw_item.strip())
    return None


def _slide_text_field(raw_slide: dict, *keys: str) -> str:
    for key in keys:
        value = raw_slide.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _validate_plans(
    plans: list[SlidePlan],
    cfg: ContentConfig,
    *,
    coverage_anchors: list[str] | None = None,
    source_numeric_tokens: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Return ``(blocking, non_blocking)`` validation issues.

    Blocking issues describe content the renderer cannot use (missing
    title, non-actionable design contract, broken indexes, missing source
    anchors, fabricated numbers) and force a planner retry. Non-blocking
    issues are soft stylistic rules (rhythm typos, repeated layouts) that
    are self-healed or merely undesirable; they feed back to the model but
    do not fail the whole deck, since a few bullet-list/two-column slides
    in a row are common and acceptable for content-heavy decks.
    """
    blocking: list[str] = []
    non_blocking: list[str] = []
    if len(plans) > cfg.max_slides:
        blocking.append(f"plan has {len(plans)} slides but max_slides is {cfg.max_slides}")
    expected_indexes = list(range(1, len(plans) + 1))
    actual_indexes = [plan.index for plan in plans]
    if actual_indexes != expected_indexes:
        blocking.append(f"slide indexes must be sequential 1..N, got {actual_indexes}")
    for start in range(0, max(0, len(plans) - 2)):
        layouts = [plans[start + offset].layout for offset in range(3)]
        if layouts[0] == layouts[1] == layouts[2]:
            non_blocking.append(
                f"slides {start + 1}-{start + 3} repeat layout '{layouts[0]}'; vary the executor layout contract"
            )
    for plan in plans:
        if not plan.title.strip():
            blocking.append(f"slide {plan.index} is missing a title")
        if not plan.layout.strip():
            blocking.append(f"slide {plan.index} is missing a layout")
        if not _is_actionable_design_text(plan.visual_strategy, field="visual_strategy"):
            blocking.append(
                f"slide {plan.index} needs a concrete visual_strategy with a specific visual device, hierarchy, or geometry, got {plan.visual_strategy!r}"
            )
        if not _is_actionable_design_text(plan.layout_pattern, field="layout_pattern"):
            blocking.append(
                f"slide {plan.index} needs a concrete layout_pattern with actual placement or structure, got {plan.layout_pattern!r}"
            )
        empty_items = [item for item in plan.items if not item.primary.strip()]
        if empty_items:
            blocking.append(f"slide {plan.index} has {len(empty_items)} empty item(s)")
        if len(plan.items) > cfg.max_items_per_slide:
            non_blocking.append(
                f"slide {plan.index} has {len(plan.items)} items but max_items_per_slide is {cfg.max_items_per_slide}"
            )
    missing_anchors = _missing_source_coverage(plans, coverage_anchors or [])
    for anchor in missing_anchors[:6]:
        blocking.append(f"source coverage missing required anchor: {anchor!r}")
    hallucinated_numbers = _hallucinated_numeric_tokens(plans, source_numeric_tokens or set())
    if hallucinated_numbers:
        preview = ", ".join(sorted(hallucinated_numbers)[:8])
        # Model-added numbers are flagged for review but do not block — failing
        # a whole chapter over one illustrative number is disproportionate, and
        # the model retries without dropping them. The user can spot-check.
        non_blocking.append(f"planner invented numeric value(s) absent from source: {preview}")
    return blocking, non_blocking


def _is_actionable_design_text(value: str, *, field: str) -> bool:
    normalized = " ".join(str(value or "").strip().lower().split())
    if normalized in GENERIC_DESIGN_TEXT:
        return False
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", normalized))
    is_cjk_dominant = cjk_chars >= max(6, len(normalized) * 0.35)
    min_len = 6 if is_cjk_dominant else 18
    if len(normalized) < min_len:
        return False
    if is_cjk_dominant:
        # Chinese design vocabulary is too open-ended for a finite whitelist
        # (e.g. \u4e09\u680f\u6bd4\u8f83/\u6570\u636e\u6d41\u5411/\u8f93\u51fa\u5f62\u6001), so a non-generic CJK description
        # of sufficient length is treated as concrete. Tone/impression-only
        # phrases are rare and short, so the generic + length gates suffice.
        return cjk_chars >= 6
    terms = _design_terms(normalized)
    # A concrete description may use visual nouns ("timeline", "card") or
    # spatial nouns ("left", "below") interchangeably regardless of which
    # field it fills. Matching against the union avoids brittle per-field
    # bucketing where a single mis-categorized term fails validation, while
    # still rejecting tone/emotion-only text (which hits neither set).
    return bool(terms & (DESIGN_SPECIFIC_TERMS | LAYOUT_SPECIFIC_TERMS))


def _design_terms(text: str) -> set[str]:
    normalized = text.lower().replace("-", " ")
    tokens = set(re.findall(r"\w+", normalized))
    # Morphology tolerance: add singular forms so plurals/verb forms match
    # the singular whitelist entries (cards\u2192card, boxes\u2192box, blocks\u2192block).
    terms = set(tokens)
    for tok in tokens:
        if len(tok) > 4 and tok.endswith("es"):
            terms.add(tok[:-2])
        if len(tok) > 3 and tok.endswith("s"):
            terms.add(tok[:-1])
    for term in DESIGN_SPECIFIC_TERMS | LAYOUT_SPECIFIC_TERMS:
        if any("\u4e00" <= ch <= "\u9fff" for ch in term) and term in text:
            terms.add(term)
    return terms


def _planner_feedback(error: str) -> str:
    return (
        "Your previous slide plan could not pass validation. "
        "Return corrected JSON only. Make every slide executor-ready with concrete "
        "visual_strategy and layout_pattern values. Fix this issue: "
        f"{error}"
    )


def _source_coverage_anchors(source_text: str, cfg: ContentConfig, *, max_anchors: int = 10) -> list[str]:
    """Extract source phrases that the AI plan must visibly preserve."""
    anchors: list[str] = []
    in_fence = False
    for raw_line in source_text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue

        heading = re.match(r"^#{1,3}\s+(.+)$", line)
        if heading:
            _append_anchor(anchors, _clean_source_anchor(heading.group(1)), max_anchors=max_anchors)
            continue

        item = re.match(r"^(?:[-*+]\s+|\d+[\.)、]\s+)(.+)$", line)
        if item:
            _append_anchor(anchors, _clean_source_anchor(item.group(1)), max_anchors=max_anchors)
            continue

        if re.search(r"\d+\s*[%％]|\d+\s*[万亿KMB]\b|\d+x\b|\d+\+\b", line, flags=re.IGNORECASE):
            _append_anchor(anchors, _clean_source_anchor(line), max_anchors=max_anchors)

        if len(anchors) >= max_anchors:
            break
    return anchors[:max_anchors]


def _append_anchor(anchors: list[str], anchor: str, *, max_anchors: int) -> None:
    if len(anchors) >= max_anchors:
        return
    if not anchor:
        return
    normalized = _normalize_source_text(anchor)
    if normalized in GENERIC_SOURCE_ANCHORS:
        return
    if len(normalized) < 4:
        return
    if normalized in {_normalize_source_text(existing) for existing in anchors}:
        return
    anchors.append(anchor)


def _clean_source_anchor(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"[*_~]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text[:160].strip(" -:;,.，。；：")


def _format_coverage_anchor_prompt(anchors: list[str]) -> str:
    if not anchors:
        return ""
    lines = [
        "",
        "## Required Source Coverage Anchors",
        "Every anchor below is a hard validation target. Each one must appear in a slide title or in an item primary/secondary/tertiary field.",
        "Short section headings still count as required source content; if slide budget is tight, include the heading as the slide title, subtitle item, or compact context item.",
        "Do not satisfy these anchors only in notes or design fields.",
    ]
    for anchor in anchors:
        lines.append(f"- {anchor}")
    return "\n".join(lines)


def _format_numeric_grounding_prompt(tokens: set[str]) -> str:
    if not tokens:
        return ""
    values = ", ".join(sorted(tokens)[:80])
    return f"\n\n## Allowed Source Numeric Values\n{values}"


def _missing_source_coverage(plans: list[SlidePlan], anchors: list[str]) -> list[str]:
    if not anchors:
        return []
    plan_text = _plan_visible_content_corpus(plans)
    return [anchor for anchor in anchors if not _anchor_covered(anchor, plan_text)]


def _plan_visible_content_corpus(plans: list[SlidePlan]) -> str:
    parts: list[str] = []
    for plan in plans:
        parts.append(plan.title)
        for item in plan.items:
            parts.extend([item.primary, item.secondary, item.tertiary])
    return "\n".join(part for part in parts if part)


def _hallucinated_numeric_tokens(plans: list[SlidePlan], source_tokens: set[str]) -> set[str]:
    if not source_tokens:
        return _numeric_tokens(_plan_visible_content_corpus(plans))
    planned = _numeric_tokens(_plan_visible_content_corpus(plans))
    return {token for token in planned if token not in source_tokens}


def _anchor_covered(anchor: str, plan_text: str) -> bool:
    normalized_anchor = _normalize_source_text(anchor)
    normalized_plan = _normalize_source_text(plan_text)
    if not normalized_anchor:
        return True
    if normalized_anchor in normalized_plan:
        return True

    anchor_cjk = re.findall(r"[一-鿿]", normalized_anchor)
    # CJK anchors have no word boundaries, so token overlap collapses to a
    # single token and degrades to verbatim-only matching. Fall back to
    # character overlap so paraphrased Chinese anchors still count as covered.
    if len(anchor_cjk) >= 4:
        plan_cjk = set(re.findall(r"[一-鿿]", normalized_plan))
        if not plan_cjk:
            return False
        covered = sum(1 for ch in anchor_cjk if ch in plan_cjk)
        return covered / len(anchor_cjk) >= 0.7

    anchor_tokens = normalized_anchor.split()
    if len(anchor_tokens) < 3:
        return False
    plan_tokens = set(normalized_plan.split())
    if not plan_tokens:
        return False
    numeric_tokens = {token for token in anchor_tokens if re.search(r"\d", token)}
    if numeric_tokens and not numeric_tokens.issubset(plan_tokens):
        return False
    covered = sum(1 for token in anchor_tokens if token in plan_tokens)
    return covered / len(anchor_tokens) >= 0.72


def _normalize_source_text(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _numeric_tokens(text: str) -> set[str]:
    """Extract normalized numeric facts for planner anti-hallucination checks."""
    tokens: set[str] = set()
    pattern = re.compile(
        r"(?<![\w.])(?:[$¥€£])?\d+(?:[,.]\d+)*(?:\.\d+)?\s*(?:%|％|万|亿|千|百|k|m|b|x|倍|元|美元|人民币)?",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(str(text or "")):
        token = match.group(0).strip().lower()
        token = token.replace(",", "")
        token = re.sub(r"\s+", "", token)
        if token:
            tokens.add(token)
    return tokens


def _content_item_from_payload(raw_item: dict) -> ContentItem:
    meta = raw_item.get("meta") if isinstance(raw_item.get("meta"), dict) else {}
    primary = _item_text_field(raw_item, "primary", "text", "content", "label", "description")
    secondary = _item_text_field(raw_item, "secondary", "subtitle", "detail", "details", "translation")
    if not secondary and _item_text_field(raw_item, "primary", "text", "content", "label"):
        secondary = _item_text_field(raw_item, "description")
    return ContentItem(
        type=str(raw_item.get("type") or "text"),
        primary=primary,
        secondary=secondary,
        tertiary=_item_text_field(raw_item, "tertiary", "pinyin", "annotation", "note"),
        meta=meta,
    )


def _item_text_field(raw_item: dict, *keys: str) -> str:
    for key in keys:
        value = raw_item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _write_planner_artifacts(
    project: Path, raw: str, plans: list[SlidePlan], *, attempt: int, error: str, warnings: str = ""
) -> None:
    out_dir = ensure_dir(project / "qa" / "ai-planner")
    (out_dir / "raw-response.txt").write_text(raw, encoding="utf-8")
    (out_dir / "plan.json").write_text(
        json.dumps([plan.to_dict() for plan in plans], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "executor-brief.md").write_text(_format_executor_brief(plans), encoding="utf-8")
    _write_planner_attempt(project, attempt, raw, error=error, warnings=warnings)


def _clear_previous_ai_planner_result(project: Path) -> None:
    out_dir = ensure_dir(project / "qa" / "ai-planner")
    for name in ("raw-response.txt", "plan.json", "executor-brief.md", "failure.json"):
        path = out_dir / name
        if path.exists():
            path.unlink()


def _write_planner_failure(project: Path, error: str, *, attempts: int) -> None:
    out_dir = ensure_dir(project / "qa" / "ai-planner")
    payload = {
        "status": "failed",
        "attempts": attempts,
        "error": error,
    }
    (out_dir / "failure.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_coverage_anchors(project: Path, anchors: list[str]) -> None:
    out_dir = ensure_dir(project / "qa" / "ai-planner")
    (out_dir / "coverage-anchors.json").write_text(
        json.dumps({"anchors": anchors}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_planner_attempt(
    project: Path, attempt: int, raw: str, *, error: str, warnings: str = ""
) -> None:
    out_dir = ensure_dir(project / "qa" / "ai-planner")
    payload = {
        "attempt": attempt + 1,
        "raw_chars": len(raw),
        "status": "failed" if error else "passed",
        "error": error,
        "warnings": warnings,
    }
    path = out_dir / f"attempt_{attempt + 1:02d}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _format_executor_brief(plans: list[SlidePlan]) -> str:
    lines = [
        "# AI Executor Brief",
        "",
        "Generated from the validated AI Strategist plan. Use this as the page-by-page design contract.",
        "",
    ]
    for plan in plans:
        lines.append(f"## Slide {plan.index}: {plan.title}")
        lines.append(f"- Layout: {plan.layout}")
        lines.append(f"- Rhythm: {plan.rhythm or 'breathing'}")
        lines.append(f"- Density: {plan.density}")
        lines.append(f"- Visual strategy: {plan.visual_strategy}")
        lines.append(f"- Layout pattern: {plan.layout_pattern}")
        lines.append(f"- Chart type: {plan.chart_type or 'none'}")
        lines.append(f"- Image hint: {plan.image_hint or 'none'}")
        if plan.items:
            lines.append("- Content:")
            for item in plan.items:
                secondary = f" — {item.secondary}" if item.secondary else ""
                tertiary = f" ({item.tertiary})" if item.tertiary else ""
                lines.append(f"  - [{item.type}] {item.primary}{secondary}{tertiary}")
        if plan.notes:
            lines.append(f"- Notes: {plan.notes}")
        lines.append("")
    return "\n".join(lines)
