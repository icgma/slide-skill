"""AI visual critic for rendered slide images."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from pathlib import Path

from .ai_trace import ai_response_metadata, write_ai_trace
from .provider_response import DEFAULT_ROLE_MAX_TOKENS, ProviderResponse, parse_provider_response
from .util import ensure_dir

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_VISION_MODEL = "gpt-4o"
DEFAULT_MAX_TOKENS = DEFAULT_ROLE_MAX_TOKENS["vision"]
DEFAULT_TEMPERATURE = 0.1
DEFAULT_RETRIES = 1
VISUAL_FEEDBACK_JSON = "visual-feedback.json"
VISUAL_REVIEW_MD = "VISUAL-REVIEW.md"


def generate_visual_feedback(
    project_path: Path | str,
    *,
    rendered_dir: Path | str | None = None,
    slides: list[int] | None = None,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    top_p: float | None = None,
    retries: int = DEFAULT_RETRIES,
) -> tuple[Path, Path]:
    """Analyze rendered slide images and write feedback artifacts.

    Returns:
        ``(visual-feedback.json, VISUAL-REVIEW.md)`` paths.
    """
    from openai import OpenAI

    project = Path(project_path)
    if not project.is_dir():
        raise FileNotFoundError(f"Project directory not found: {project}")
    qa_dir = ensure_dir(project / "qa")
    image_dir = Path(rendered_dir) if rendered_dir else qa_dir / "rendered"
    images = _rendered_slide_images(image_dir, slides=slides)
    if not images:
        raise FileNotFoundError(f"No rendered slide images found in {image_dir}")
    _clear_previous_ai_visual_feedback(qa_dir)

    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
        base_url=base_url or os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL),
    )
    selected_model = model or os.environ.get("OPENAI_VISION_MODEL") or os.environ.get("OPENAI_MODEL", DEFAULT_VISION_MODEL)
    spec_excerpt = _project_context(project)

    slide_feedback = []
    for slide_index, image_path in images:
        feedback = ""
        normalized = {}
        quality_issue = ""
        expected_context = _slide_expected_context(project, slide_index)
        for attempt in range(retries + 1):
            prompt = _build_visual_prompt(
                slide_index,
                spec_excerpt,
                expected_context=expected_context,
                feedback=feedback,
            )
            request_payload = _build_visual_request(
                selected_model,
                image_path,
                slide_index,
                spec_excerpt,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
            )
            try:
                provider, response_metadata = _call_visual_model(client, request_payload)
            except Exception as exc:  # noqa: BLE001 - provider SDKs expose many exception classes.
                quality_issue = _provider_error_message(exc)
                write_ai_trace(
                    project,
                    stage="visual-critic",
                    model=selected_model,
                    status="failed",
                    prompt=prompt,
                    raw="",
                    request=_redact_visual_request(request_payload, image_path),
                    attempt=attempt + 1,
                    metadata={
                        "slide": slide_index,
                        "image": str(image_path),
                        "severity": "unknown",
                        "feedback": bool(feedback),
                        "has_expected_context": bool(expected_context),
                        "provider_error": True,
                        "error": quality_issue,
                    },
                )
                if attempt >= retries:
                    raise RuntimeError(
                        "AI visual critic provider call failed for "
                        f"slide {slide_index} after {retries + 1} attempt(s): {quality_issue}"
                    ) from exc
                feedback = _visual_retry_feedback(quality_issue)
                continue
            raw = provider.content
            if provider.blocks_parsing:
                # Completion-status gate: truncated critic output is invalid
                # feedback and is never parsed as JSON.
                quality_issue = (
                    f"provider response truncated (finish_reason={provider.finish_reason or 'missing'}); "
                    "visual feedback was not parsed"
                )
                write_ai_trace(
                    project,
                    stage="visual-critic",
                    model=selected_model,
                    status="truncated",
                    prompt=prompt,
                    raw=raw,
                    request=_redact_visual_request(request_payload, image_path),
                    attempt=attempt + 1,
                    metadata={
                        "slide": slide_index,
                        "image": str(image_path),
                        "severity": "unknown",
                        "feedback": bool(feedback),
                        "has_expected_context": bool(expected_context),
                        "error": quality_issue,
                        **response_metadata,
                    },
                )
                if attempt >= retries:
                    break
                feedback = _visual_retry_feedback(quality_issue)
                continue
            normalized = _normalize_slide_feedback(slide_index, image_path, raw)
            normalized = _apply_structural_feedback_sanity(project, slide_index, normalized)
            quality_issue = _visual_feedback_quality_issue(normalized)
            status = "passed" if not quality_issue else "failed"
            write_ai_trace(
                project,
                stage="visual-critic",
                model=selected_model,
                status=status,
                prompt=prompt,
                raw=raw,
                request=_redact_visual_request(request_payload, image_path),
                attempt=attempt + 1,
                metadata={
                    "slide": slide_index,
                    "image": str(image_path),
                    "severity": normalized["severity"],
                    "feedback": bool(feedback),
                    "has_expected_context": bool(expected_context),
                    **response_metadata,
                    **({"error": quality_issue} if quality_issue else {}),
                },
            )
            if not quality_issue or attempt >= retries:
                break
            feedback = _visual_retry_feedback(quality_issue)
        if quality_issue:
            raise RuntimeError(
                "AI visual critic failed quality gate for "
                f"slide {slide_index} after {retries + 1} attempt(s): {quality_issue}"
            )
        clean = {k: v for k, v in normalized.items() if not k.startswith("_")}
        slide_feedback.append(clean)

    json_path = qa_dir / VISUAL_FEEDBACK_JSON
    md_path = qa_dir / VISUAL_REVIEW_MD
    payload = {
        "source": "ai-visual-critic",
        "rendered_dir": str(image_dir),
        "slides": slide_feedback,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_format_visual_review_markdown(slide_feedback), encoding="utf-8")
    return json_path, md_path


def _clear_previous_ai_visual_feedback(qa_dir: Path) -> None:
    json_path = qa_dir / VISUAL_FEEDBACK_JSON
    if _is_ai_visual_feedback_json(json_path):
        json_path.unlink()

    md_path = qa_dir / VISUAL_REVIEW_MD
    if _is_ai_visual_review_markdown(md_path):
        md_path.unlink()


def _is_ai_visual_feedback_json(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and payload.get("source") == "ai-visual-critic"


def _is_ai_visual_review_markdown(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return "Generated by AI visual critic." in text[:400]


def _rendered_slide_images(image_dir: Path, *, slides: list[int] | None = None) -> list[tuple[int, Path]]:
    selected = set(slides or [])
    result: list[tuple[int, Path]] = []
    if not image_dir.exists():
        return result
    for path in sorted(image_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        slide_index = _slide_index_from_name(path.name)
        if slide_index is None:
            continue
        if selected and slide_index not in selected:
            continue
        result.append((slide_index, path))
    return result


def _slide_index_from_name(name: str) -> int | None:
    match = re.search(r"(?:slide|snapshot)[-_ ]?0*(\d+)", name, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def _project_context(project: Path) -> str:
    parts: list[str] = []
    for name in ("spec_lock.md", "design_guide.md"):
        path = project / name
        if path.exists():
            parts.append(f"## {name}\n{path.read_text(encoding='utf-8')[:1800]}")
    json_path = project / "spec_lock.json"
    if not parts and json_path.exists():
        parts.append(f"## spec_lock.json\n{json_path.read_text(encoding='utf-8')[:1800]}")
    return "\n\n".join(parts)


def _slide_expected_context(project: Path, slide_index: int) -> str:
    """Return the planner's expected content/design contract for one slide."""
    path = project / "qa" / "ai-planner" / "executor-brief.md"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^##\s+Slide\s+0*{slide_index}\b.*$", flags=re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    next_match = re.search(r"^##\s+Slide\s+\d+\b.*$", text[match.end():], flags=re.IGNORECASE | re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(text)
    return text[match.start():end].strip()[:2200]


def _call_visual_model(
    client,
    request_payload: dict,
) -> tuple[ProviderResponse, dict]:
    response = client.chat.completions.create(**request_payload)
    # parse_provider_response raises RuntimeError on empty choices
    # (possible content filter), preserving the previous guard.
    provider = parse_provider_response(response)
    metadata = ai_response_metadata(response)
    metadata["reasoning_chars"] = provider.reasoning_chars
    return provider, metadata


def _build_visual_request(
    model: str,
    image_path: Path,
    slide_index: int,
    spec_excerpt: str,
    *,
    prompt: str | None = None,
    max_tokens: int,
    temperature: float,
    top_p: float | None,
) -> dict:
    prompt = prompt or _build_visual_prompt(slide_index, spec_excerpt)
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict presentation visual QA reviewer. "
                    "Return only compact JSON with visible issues and concrete repair actions."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": _image_data_url(image_path)},
                    },
                ],
            },
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


def _redact_visual_request(kwargs: dict, image_path: Path) -> dict:
    payload = json.loads(json.dumps(kwargs, ensure_ascii=False))
    content = payload.get("messages", [{}])[-1].get("content", [])
    for item in content:
        if isinstance(item, dict) and item.get("type") == "image_url":
            item["image_url"] = {"url": f"<image data URL omitted; source={image_path}>"}
    return payload


def _build_visual_prompt(
    slide_index: int,
    spec_excerpt: str,
    *,
    expected_context: str = "",
    feedback: str = "",
) -> str:
    spec_block = f"\n\nProject design context:\n{spec_excerpt}" if spec_excerpt else ""
    expected_block = f"\n\nExpected slide content and design contract:\n{expected_context}" if expected_context else ""
    feedback_block = f"\n\n## Critic Feedback From Previous Attempt\n{feedback}" if feedback else ""
    return f"""Analyze rendered slide {slide_index}.

Return JSON only. The first character of your answer must be `{{` and the last character must be `}}`. Do not wrap the JSON in markdown fences, prose, labels, or comments. Match this schema:
{{
  "severity": "ok|minor|major|critical",
  "summary": "one sentence visual verdict",
  "issues": ["visible issue 1", "visible issue 2"],
  "actions": ["specific SVG repair action 1", "specific SVG repair action 2"],
  "repair_prompt": "preferred concise instruction paragraph for the SVG executor; may be empty only when actions are concrete enough to paste into a rewrite prompt"
}}

Focus on visual defects that an SVG generator can fix: clipped text, overlap, weak hierarchy, bad contrast, off-canvas elements, excessive density, inconsistent alignment, missing footer/page number, missing expected title/body content, and design drift from the project spec. Compare the rendered image against the expected slide content when provided; if expected text is missing, obscured, or materially changed, report it as a visible issue. Footer page numbering is required deck chrome; do not ask to remove it or replace it with progress dots. Progress dots may be added only if the page number remains visible and readable; do not flag optional progress-dot alignment unless it creates a clear visible defect such as overlap, clipping, or broken rhythm. If the slide is acceptable, use severity "ok", empty issues/actions, and an empty repair_prompt. If repair is needed, prefer a specific repair_prompt that can be pasted directly into a slide rewrite prompt; if repair_prompt is empty, actions must be equally concrete executor-ready repair instructions.{spec_block}{expected_block}{feedback_block}
"""


def _image_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _normalize_slide_feedback(slide_index: int, image_path: Path, raw: str) -> dict:
    parsed = _parse_json_object(raw)
    parse_failed = not isinstance(parsed, dict)
    if parse_failed:
        parsed = {
            "severity": "major",
            "summary": "Visual critic returned non-JSON feedback.",
            "issues": [raw.strip() or "No readable feedback returned."],
            "actions": ["Review the rendered slide manually and repair visible defects."],
        }

    severity = str(parsed.get("severity", "minor")).lower()
    if severity not in {"ok", "minor", "major", "critical"}:
        severity = "minor"
    return {
        "slide": slide_index,
        "image": str(image_path),
        "severity": severity,
        "summary": str(parsed.get("summary", "")).strip(),
        "issues": _string_list(parsed.get("issues")),
        "actions": _normalized_actions(parsed),
        "repair_prompt": str(parsed.get("repair_prompt", "")).strip(),
        "_parse_failed": parse_failed,
    }


def _normalized_actions(parsed: dict) -> list[str]:
    actions = _string_list(parsed.get("actions"))
    return actions or _string_list(parsed.get("action"))


def _visual_feedback_quality_issue(normalized: dict) -> str:
    if normalized.get("_parse_failed"):
        return "Visual critic did not return valid JSON."
    severity = normalized.get("severity", "minor")
    if severity == "ok":
        if normalized.get("issues") or normalized.get("actions") or str(normalized.get("repair_prompt", "")).strip():
            return "Severity ok must have empty issues, actions, and repair_prompt; use minor/major/critical when repair is needed."
    else:
        if not normalized.get("issues") and not normalized.get("actions"):
            return "Non-ok visual feedback must include at least one visible issue or repair action."
        chrome_issue = _required_chrome_quality_issue(normalized)
        if chrome_issue:
            return chrome_issue
        repair_issue = _repair_prompt_quality_issue(normalized)
        if repair_issue:
            return repair_issue
    return ""


def _apply_structural_feedback_sanity(project: Path, slide_index: int, normalized: dict) -> dict:
    """Remove visual feedback contradicted by the generated SVG structure."""
    svg_text = _slide_svg_text(project, slide_index)
    if not svg_text:
        return normalized

    removed_terms: list[str] = []
    issues = _filter_structurally_false_items(normalized.get("issues", []), svg_text, removed_terms)
    actions = _filter_structurally_false_items(normalized.get("actions", []), svg_text, removed_terms)
    if len(issues) == len(normalized.get("issues", [])) and len(actions) == len(normalized.get("actions", [])):
        return normalized

    adjusted = dict(normalized)
    adjusted["issues"] = issues
    adjusted["actions"] = actions
    if not issues and not actions:
        adjusted["severity"] = "ok"
        adjusted["summary"] = "Slide passes after filtering visual feedback contradicted by SVG structure."
        adjusted["repair_prompt"] = ""
    elif _repair_prompt_only_references_removed_feedback(str(adjusted.get("repair_prompt", "")), removed_terms):
        adjusted["repair_prompt"] = ""
    elif _repair_prompt_misses_remaining_feedback(str(adjusted.get("repair_prompt", "")), issues, actions):
        adjusted["repair_prompt"] = ""
    return adjusted


def _slide_svg_text(project: Path, slide_index: int) -> str:
    name = f"slide_{slide_index:02d}.svg"
    for dirname in ("svg_output", "svg_final"):
        path = project / dirname / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return ""
    return ""


def _filter_structurally_false_items(items: list[str], svg_text: str, removed_terms: list[str]) -> list[str]:
    kept: list[str] = []
    for item in items:
        text = str(item)
        if _is_gradient_false_positive(text, svg_text):
            removed_terms.append("gradient")
            continue
        if _is_footer_height_false_positive(text, svg_text):
            removed_terms.append("footer")
            continue
        if _is_accent_stripe_width_false_positive(text, svg_text):
            removed_terms.append("stripe")
            continue
        if _is_accent_stripe_style_false_positive(text, svg_text):
            removed_terms.append("stripe")
            continue
        if _is_bullet_color_false_positive(text, svg_text):
            removed_terms.append("bulletcolor")
            continue
        if _is_optional_progress_dot_alignment(text):
            removed_terms.append("progress")
            continue
        kept.append(text)
    return kept


def _is_gradient_false_positive(feedback_text: str, svg_text: str) -> bool:
    text = str(feedback_text or "").lower()
    if "gradient" not in text and "solid" not in text:
        return False
    if not any(term in text for term in ("missing", "lack", "lacks", "solid", "instead of", "replace", "apply")):
        return False
    return _svg_has_gradient_filled_panel(svg_text)


def _svg_has_gradient_filled_panel(svg_text: str) -> bool:
    if not re.search(r"<linearGradient\b", svg_text, flags=re.IGNORECASE):
        return False
    return bool(re.search(r"<rect\b[^>]*\bfill\s*=\s*['\"]url\(#", svg_text, flags=re.IGNORECASE))


def _is_footer_height_false_positive(feedback_text: str, svg_text: str) -> bool:
    text = str(feedback_text or "").lower()
    if "footer" not in text or ("height" not in text and "32px" not in text and "32 px" not in text):
        return False
    if not any(term in text for term in ("larger", "exceed", "reduce", "exactly 32", "32px spec", "32px tall")):
        return False
    return _svg_has_exact_footer_bar(svg_text)


def _svg_has_exact_footer_bar(svg_text: str) -> bool:
    try:
        root = ET_fromstring(svg_text)
    except Exception:
        return False
    for elem in root.iter():
        if str(elem.tag).rsplit("}", 1)[-1].lower() != "rect":
            continue
        y = _numeric_attr(elem.attrib.get("y"))
        width = _numeric_attr(elem.attrib.get("width"))
        height = _numeric_attr(elem.attrib.get("height"))
        if y == 688 and height == 32 and (width is None or width >= 1200):
            return True
    return False


def _is_accent_stripe_width_false_positive(feedback_text: str, svg_text: str) -> bool:
    text = str(feedback_text or "").lower()
    if "accent stripe" not in text and "accent rail" not in text and "left stripe" not in text:
        return False
    if "width" not in text and "6px" not in text and "6 px" not in text:
        return False
    if not any(term in text for term in ("exceed", "reduce", "narrow", "too wide", "wider", "exactly 6", "6px specification", "6px width")):
        return False
    return _svg_has_exact_left_accent_stripe(svg_text)


def _is_accent_stripe_style_false_positive(feedback_text: str, svg_text: str) -> bool:
    text = str(feedback_text or "").lower()
    if "accent stripe" not in text and "accent rail" not in text and "left stripe" not in text and "stripe" not in text:
        return False
    if "#3b82f6" not in text and "no stroke" not in text:
        return False
    return _svg_has_compliant_left_accent_stripe(svg_text)


def _svg_has_exact_left_accent_stripe(svg_text: str) -> bool:
    try:
        root = ET_fromstring(svg_text)
    except Exception:
        return bool(re.search(
            r"<rect\b[^>]*\bx\s*=\s*['\"]0['\"][^>]*\bwidth\s*=\s*['\"]6(?:\.0)?['\"][^>]*\bheight\s*=\s*['\"]720(?:\.0)?['\"]",
            svg_text,
            flags=re.IGNORECASE,
        ))
    for elem in root.iter():
        if str(elem.tag).rsplit("}", 1)[-1].lower() != "rect":
            continue
        x = _numeric_attr(elem.attrib.get("x"))
        width = _numeric_attr(elem.attrib.get("width"))
        height = _numeric_attr(elem.attrib.get("height"))
        if x == 0 and width == 6 and (height is None or height >= 680):
            return True
    return False


def _svg_has_compliant_left_accent_stripe(svg_text: str) -> bool:
    try:
        root = ET_fromstring(svg_text)
    except Exception:
        return False
    for elem in root.iter():
        if str(elem.tag).rsplit("}", 1)[-1].lower() != "rect":
            continue
        x = _numeric_attr(elem.attrib.get("x"))
        width = _numeric_attr(elem.attrib.get("width"))
        height = _numeric_attr(elem.attrib.get("height"))
        fill = str(elem.attrib.get("fill", "")).strip().lower()
        stroke = str(elem.attrib.get("stroke", "")).strip().lower()
        if x == 0 and width == 6 and (height is None or height >= 680) and fill == "#3b82f6" and not stroke:
            return True
    return False


def _is_bullet_color_false_positive(feedback_text: str, svg_text: str) -> bool:
    text = str(feedback_text or "").lower()
    if "bullet" not in text or "color" not in text:
        return False
    if "#94a3b8" not in text and "body color" not in text and "brighter" not in text:
        return False
    return _svg_has_body_colored_bullet_text(svg_text)


def _svg_has_body_colored_bullet_text(svg_text: str) -> bool:
    try:
        root = ET_fromstring(svg_text)
    except Exception:
        return False
    count = 0
    for elem in root.iter():
        if str(elem.tag).rsplit("}", 1)[-1].lower() != "text":
            continue
        fill = str(elem.attrib.get("fill", "")).strip().lower()
        if fill != "#94a3b8":
            continue
        text = "".join(elem.itertext()).strip()
        if len(text) >= 8:
            count += 1
    return count >= 2


def ET_fromstring(svg_text: str):
    from xml.etree import ElementTree as ET

    return ET.fromstring(svg_text)


def _numeric_attr(value: object) -> float | None:
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(value or ""))
    if not match:
        return None
    return float(match.group(1))


def _is_optional_progress_dot_alignment(feedback_text: str) -> bool:
    text = str(feedback_text or "").lower()
    dot_terms = ("progress dot", "progress-dot", "chrome dot", "accent dot")
    if not any(term in text for term in dot_terms):
        return False
    if "align" not in text and "alignment" not in text:
        return False
    hard_defect_terms = ("overlap", "clipped", "off-canvas", "unreadable", "hidden")
    return not any(term in text for term in hard_defect_terms)


def _repair_prompt_only_references_removed_feedback(prompt: str, removed_terms: list[str]) -> bool:
    text = str(prompt or "").lower()
    if not text or not removed_terms:
        return False
    meaningful_terms = {
        term for term in removed_terms
        if term in {"gradient", "progress", "stripe", "footer", "bulletcolor"}
    }
    if not meaningful_terms:
        return False
    prompt_terms = re.findall(r"gradient|progress|stripe|rail|footer|bullet|color|typography|body", text)
    normalized_terms = {
        "bulletcolor" if term in {"bullet", "color", "typography", "body"} else term
        for term in prompt_terms
    }
    return all(term in meaningful_terms for term in normalized_terms)


def _repair_prompt_misses_remaining_feedback(prompt: str, issues: list[str], actions: list[str]) -> bool:
    if not str(prompt or "").strip():
        return False
    context = " ".join(str(value) for value in [*issues, *actions])
    context_terms = _repair_prompt_terms(context)
    if not context_terms:
        return False
    return not (_repair_prompt_terms(prompt) & context_terms)


def _required_chrome_quality_issue(normalized: dict) -> str:
    text = " ".join(
        str(value)
        for key in ("issues", "actions", "repair_prompt")
        for value in (
            normalized.get(key, [])
            if isinstance(normalized.get(key), list)
            else [normalized.get(key, "")]
        )
    ).lower()
    page_number_terms = ("page number", "page numbering", "01 / 01", "01/01", "页码")
    progress_terms = ("progress dot", "progress dots", "进度点")
    replace_terms = ("replace", "remove", "instead of", "替换", "移除")
    if (
        any(term in text for term in page_number_terms)
        and any(term in text for term in progress_terms)
        and any(term in text for term in replace_terms)
    ):
        return "Footer page number is required deck chrome; do not ask to replace it with progress dots."
    return ""


def _repair_prompt_quality_issue(normalized: dict) -> str:
    repair_text = _visual_repair_text(normalized)
    if not repair_text:
        return "Non-ok visual feedback must include repair_prompt or a concrete action written for the SVG executor."
    normalized_prompt = " ".join(repair_text.lower().split())
    generic_prompts = {
        "fix it",
        "fix this",
        "fix the slide",
        "improve the slide",
        "make it better",
        "repair the slide",
        "adjust the slide",
    }
    if normalized_prompt in generic_prompts or len(normalized_prompt) < 24:
        return "repair_prompt must be specific enough for the SVG executor, or provide a concrete action; not a generic instruction."

    context = " ".join(
        str(value)
        for key in ("issues", "actions")
        for value in normalized.get(key, [])
    )
    prompt_terms = _repair_prompt_terms(repair_text)
    context_terms = _repair_prompt_terms(context)
    if context_terms and not (prompt_terms & context_terms):
        return "repair_prompt must reference the visible issue, or provide an action that references the visible issue."
    return ""


def _visual_repair_text(normalized: dict) -> str:
    repair_prompt = str(normalized.get("repair_prompt") or "").strip()
    if repair_prompt:
        return repair_prompt
    actions = normalized.get("actions")
    if isinstance(actions, list):
        return "; ".join(str(action).strip() for action in actions if str(action).strip())
    return str(actions or "").strip()


def _repair_prompt_terms(text: str) -> set[str]:
    source = str(text or "").lower()
    terms = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", source, flags=re.UNICODE)
    stopwords = {
        "the", "and", "or", "to", "a", "an", "of", "in", "on", "for", "with",
        "by", "at", "is", "are", "be", "this", "that", "it", "slide", "svg",
        "repair", "fix", "issue", "action", "visible",
    }
    result = {term for term in terms if len(term) >= 3 and term not in stopwords}
    for cjk in re.findall(r"[\u4e00-\u9fff]+", source):
        for size in (2, 3):
            if len(cjk) >= size:
                result.update(cjk[index:index + size] for index in range(0, len(cjk) - size + 1))
    return result


def _visual_retry_feedback(issue: str) -> str:
    return (
        "Your previous visual review was not executor-ready. Return corrected JSON only. "
        "The first character must be `{` and the last character must be `}`; no markdown, prose, labels, or comments. "
        f"Fix this issue: {issue}"
    )


def _parse_json_object(text: str):
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        candidate = _first_balanced_json_object(stripped)
        if not candidate:
            return None
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None


def _first_balanced_json_object(text: str) -> str:
    """Extract the first balanced JSON object without greedily swallowing prose."""
    start = text.find("{")
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return ""


def _string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        result = []
        for item in value:
            text = str(item).strip()
            if text:
                result.append(text)
        return result
    return [str(value).strip()]


def _format_visual_review_markdown(slides: list[dict]) -> str:
    lines = ["# Visual Review", "", "Generated by AI visual critic.", ""]
    for slide in sorted(slides, key=lambda item: item["slide"]):
        lines.append(f"## Slide {slide['slide']}")
        lines.append(f"- Severity: {slide['severity']}")
        if slide.get("summary"):
            lines.append(f"- Summary: {slide['summary']}")
        for issue in slide.get("issues", []):
            lines.append(f"- Issue: {issue}")
        for action in slide.get("actions", []):
            lines.append(f"- Action: {action}")
        if slide.get("repair_prompt"):
            lines.append(f"- Repair prompt: {slide['repair_prompt']}")
        lines.append("")
    return "\n".join(lines)
