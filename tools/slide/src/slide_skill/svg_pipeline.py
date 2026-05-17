"""Design spec, SVG generation, SVG QA, and finalization — slide-skill v2.0."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from .project import load_project
from .util import ensure_dir, xml_escape


def _char_width(ch: str, font_size: int) -> float:
    """Approximate advance width of a single character."""
    return font_size * (1.0 if ord(ch) >= 0x2E80 else 0.55)


def _token_width(token: str, font_size: int) -> float:
    """Sum of character widths for a token."""
    return sum(_char_width(c, font_size) for c in token)


def _is_cjk(ch: str) -> bool:
    """Return True if ch is a CJK/wide character."""
    return ord(ch) >= 0x2E80


def _tokenize_for_wrap(text: str) -> list[str]:
    """Split text into wrap-friendly tokens.

    CJK characters become individual tokens (can break between any two).
    Latin/digit runs stay together as one token (never break mid-word).
    Whitespace is attached to the preceding token where possible.
    """
    tokens: list[str] = []
    buf = ""
    for ch in text:
        if _is_cjk(ch):
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        elif ch in (" ", "\t"):
            buf += ch
        else:
            if buf.endswith((" ", "\t")) and any(not c.isspace() for c in buf):
                # Whitespace after a completed Latin word → flush word+space
                tokens.append(buf)
                buf = str(ch)
            elif buf and buf.rstrip() == "" and tokens:
                # Pure whitespace buffer after CJK → attach to prev token
                tokens[-1] += buf
                buf = str(ch)
            else:
                buf += ch
    if buf:
        tokens.append(buf)
    return tokens


def _visual_wrap(text: str, max_width_px: int, font_size: int) -> list[str]:
    """Wrap a string into visual lines that fit within max_width_px.

    Wraps at word boundaries for Latin text and at character boundaries
    for CJK text.  Never breaks an English word in the middle unless
    the word alone is wider than the available width.
    """
    if not text:
        return []

    # Handle explicit newlines first
    raw_lines = text.split("\n")
    result: list[str] = []

    for raw_line in raw_lines:
        tokens = _tokenize_for_wrap(raw_line)
        if not tokens:
            result.append("")
            continue

        cur_line = ""
        cur_w = 0.0

        for token in tokens:
            tw = _token_width(token, font_size)

            if cur_w + tw <= max_width_px or not cur_line:
                # Fits, or first token on line (must accept even if too wide)
                cur_line += token
                cur_w += tw
            else:
                # Doesn't fit → wrap: emit current line, start new line
                result.append(cur_line.rstrip())
                # Keep the full token (with trailing space) so the next
                # token concatenates with proper word separation.
                cur_line = token
                cur_w = tw

        if cur_line:
            result.append(cur_line.rstrip())

    return result


def _wrap_to_tspans(
    text: str, x: int, font_size: int, max_width_px: int,
    line_height: float = 1.4,
) -> tuple[str, int]:
    """Return (joined `<tspan>` xml, total visual line count) for a text run."""
    lines = _visual_wrap(text, max_width_px, font_size) or [""]
    dy = int(font_size * line_height)
    parts = []
    for i, line in enumerate(lines):
        d = "0" if i == 0 else str(dy)
        parts.append(
            f'<tspan x="{x}" dy="{d}">{xml_escape(line)}</tspan>'
        )
    return "".join(parts), len(lines)

# ---------------------------------------------------------------------------
# Tag/attribute rules — v2.0: permissive for visually rich SVG
# ---------------------------------------------------------------------------

SUPPORTED_DRAWABLE_TAGS = {
    "rect", "circle", "ellipse", "line", "text", "tspan", "image",
    "path", "polygon", "polyline", "g",
    "defs", "linearGradient", "radialGradient", "stop",
    "filter", "feGaussianBlur", "feDropShadow", "feOffset", "feFlood", "feComposite",
    "feMerge", "feMergeNode", "clipPath", "mask", "pattern", "use",
    "title", "desc",
}

# Only ban security-dangerous and animation tags
BANNED_TAGS = {
    "script", "foreignObject", "iframe",
    "animate", "animateTransform", "set", "animateMotion",
}

# Only ban DOM event-handler attributes
BANNED_ATTRS = {
    "onclick", "onload", "onmouseover", "onmouseout",
    "onmousedown", "onmouseup", "onfocus", "onblur",
    "onchange", "onerror", "onsubmit",
}


@dataclass
class SvgIssue:
    level: str
    file: str
    message: str


# ---------------------------------------------------------------------------
# Design spec and spec-lock
# ---------------------------------------------------------------------------

def create_spec(
    project_path: Path | str,
    source_markdown: Path | str | None = None,
    title: str | None = None,
    theme_name: str = "dark-tech",
) -> tuple[Path, Path]:
    """Create design_spec.md, spec_lock.json, and design_guide.md."""
    from .themes import get_theme
    from .design_guide import build_design_guide

    project = Path(project_path)
    meta = load_project(project)
    source_text = Path(source_markdown).read_text(encoding="utf-8") if source_markdown else ""
    inferred_title = title or _first_heading(source_text) or meta.get("title", meta["name"])
    theme = get_theme(theme_name)
    p = theme.palette

    spec = (
        f"# Design Specification: {inferred_title}\n\n"
        f"## Canvas\n\n"
        f"- Format: {meta['format']}\n"
        f"- Size: {meta['canvas']['width']} x {meta['canvas']['height']} px\n"
        f"- Ratio: {meta['canvas']['ratio']}\n\n"
        f"## Theme\n\n"
        f"- Name: {theme.name}\n"
        f"- Direction: {theme.design_hints}\n\n"
        f"## Visual Direction\n\n"
        f"- Background: {p['background']}\n"
        f"- Surface: {p['surface']}\n"
        f"- Accent: {p['accent']}\n"
        f"- Typography: {theme.font_family}\n\n"
        f"## Content Plan\n\n"
        f"Use source headings as slide boundaries. Each SVG page must follow the\n"
        f"spec lock and design guide. Read design_guide.md before writing SVG files.\n"
    )
    spec_path = project / "design_spec.md"
    spec_path.write_text(spec, encoding="utf-8")

    from .i18n import detect_language
    detected_lang = detect_language(source_text) if source_text else "en"

    spec_lock = {
        "title": inferred_title,
        "theme": theme_name,
        "lang": detected_lang,
        "format": meta["format"],
        "canvas": meta["canvas"],
        "palette": {
            "background": p["background"],
            "surface": p["surface"],
            "muted": p["muted"],
            "text": p["text"],
            "body": p["body"],
            "accent": p["accent"],
        },
        "font_family": theme.font_family,
        "page_rhythm": theme.layout_rhythm,
        "design_hints": theme.design_hints,
        "svg_rules": {
            "semantic_groups_required": True,
            "supported_drawable_tags": sorted(SUPPORTED_DRAWABLE_TAGS),
            "banned_tags": sorted(BANNED_TAGS),
            "banned_attrs": sorted(BANNED_ATTRS),
            "note": (
                "v2.0: gradients, opacity, filters, transform, paths fully allowed. "
                "Only script/foreignObject/animation tags and on* event handlers are banned."
            ),
        },
    }
    lock_path = project / "spec_lock.json"
    lock_path.write_text(json.dumps(spec_lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Write design guide for the AI Executor role
    build_design_guide(project, theme_name, source_text)

    return spec_path, lock_path


# ---------------------------------------------------------------------------
# SVG generation guide (for AI Executor role)
# ---------------------------------------------------------------------------

def generate_guide(
    project_path: Path | str,
    source_markdown: Path | str,
    theme_name: str = "dark-tech",
    max_slides: int = 12,
) -> Path:
    """Generate svg_generation_prompt.md — the AI agent's per-slide authoring guide.

    Does NOT generate SVGs itself. Creates a Markdown prompt telling the
    Executor role what to write for each slide: content, layout, coordinates.

    Returns the path to the generated prompt file.
    """
    from .themes import get_theme
    from .design_guide import build_design_guide

    project = Path(project_path)
    meta = load_project(project)
    source_text = Path(source_markdown).read_text(encoding="utf-8")
    slides = _markdown_to_slides(source_text)[:max_slides]
    spec_lock = _load_or_create_lock(project, source_markdown, theme_name)
    theme = get_theme(spec_lock.get("theme", theme_name))
    p = theme.palette
    font = theme.font_family
    w = int(meta["canvas"]["width"])
    h = int(meta["canvas"]["height"])

    # Ensure design_guide.md exists
    build_design_guide(project, spec_lock.get("theme", theme_name), source_text)

    lines = [
        "# SVG Generation Prompt",
        "",
        f"Project: `{meta['name']}`  |  Theme: `{theme.name}`  |  Slides: {len(slides)}",
        "",
        "## Instructions",
        "",
        "1. Read `design_guide.md` in this project directory BEFORE writing any SVG.",
        "2. Write each slide as a separate `.svg` file in `svg_output/`.",
        f"3. Canvas: **{w} x {h} px**. Always set width, height, viewBox on root `<svg>`.",
        "4. Every slide MUST include the left accent stripe and footer bar.",
        "5. Every top-level `<g>` MUST have an `id` attribute.",
        "6. Choose the appropriate layout template from design_guide.md for each slide.",
        "7. Use ONLY palette colours from the spec lock below.",
        "8. Gradients, opacity, filters are allowed — use them for visual richness.",
        "",
        "## Palette Reference",
        "",
        "| Role | Hex |",
        "|------|-----|",
        f"| background | `{p['background']}` |",
        f"| surface | `{p['surface']}` |",
        f"| text | `{p['text']}` |",
        f"| body | `{p['body']}` |",
        f"| accent | `{p['accent']}` |",
        f"| muted | `{p['muted']}` |",
        "",
        f"Font: `{font}`",
        "",
        "---",
        "",
        "## Slide Plan",
        "",
        f"Total slides: **{len(slides)}**",
        "",
    ]

    for i, (heading, body) in enumerate(slides, start=1):
        layout = _select_layout(heading, body, i, len(slides))
        lines.append(f"### Slide {i:02d} of {len(slides):02d} — Layout: {layout}")
        lines.append(f"**File:** `svg_output/slide_{i:02d}.svg`")
        lines.append("")
        lines.append(f"**Title:** {heading}")
        if body.strip():
            lines.append("**Body content:**")
            lines.append("```")
            lines.append(body.strip())
            lines.append("```")
        else:
            lines.append("*(No body text — use section-divider layout)*")
        lines.append("")

    prompt_path = project / "svg_generation_prompt.md"
    prompt_path.write_text("\n".join(lines), encoding="utf-8")
    return prompt_path


# ---------------------------------------------------------------------------
# SVG generation (backward-compatible programmatic path)
# ---------------------------------------------------------------------------

def generate_svg(
    project_path: Path | str,
    source_markdown: Path | str,
    max_slides: int = 12,
) -> list[Path]:
    """Generate SVG pages programmatically from Markdown source.

    Backward-compatible entry point. For production AI-authored decks,
    use generate_guide() to produce a prompt for the Executor role instead.
    """
    project = Path(project_path)
    meta = load_project(project)
    spec_lock = _load_or_create_lock(project, source_markdown)
    source_text = Path(source_markdown).read_text(encoding="utf-8")
    slides = _markdown_to_slides(source_text)[:max_slides]
    if not slides:
        slides = [(spec_lock["title"], "No source content was provided.")]
    out_dir = ensure_dir(project / "svg_output")
    for old in out_dir.glob("*.svg"):
        old.unlink()
    paths: list[Path] = []
    total_slides = len(slides)
    has_competition = "competition" in meta
    project_title = spec_lock["title"]

    # Pre-compute layout per slide, then run anti-monotony pass so a deck
    # never falls into "every slide is bullet-list" rut.
    raw_layouts: list[str] = []
    for i, (heading, body) in enumerate(slides, start=1):
        if i == 1 and total_slides > 1:
            raw_layouts.append("cover")
        elif i == total_slides and total_slides > 1:
            raw_layouts.append("closing")
        else:
            raw_layouts.append(_select_layout(heading, body, i, total_slides))
    layouts = _distribute_layouts(raw_layouts, slides)

    for index, ((heading, body), layout) in enumerate(zip(slides, layouts), start=1):
        svg = _render_slide_svg(
            index, heading, body, spec_lock, total_slides, has_competition,
            project_title, layout=layout,
        )
        path = out_dir / f"slide_{index:02d}.svg"
        path.write_text(svg, encoding="utf-8")
        paths.append(path)
    return paths


def generate_svg_from_plan(
    project_path: Path | str,
    plans: list,  # list[SlidePlan] — avoid circular import by using list
) -> list[Path]:
    """Generate SVG pages from a structured slide plan.

    This is the v3.0 entry point that replaces the old generate_svg() for
    plan-driven workflows. Teaching-domain layouts (vocab-card, dialogue, etc.)
    are rendered by domain_teaching; everything else falls back to the
    existing render functions.

    Args:
        project_path: Path to the project directory.
        plans: List of SlidePlan objects from content_planner.plan_slides().

    Returns:
        List of paths to generated SVG files.
    """
    from .domain_teaching import render_teaching_slide
    from .domain_course import render_course_slide
    from .domain_competition import render_competition_slide

    project = Path(project_path)
    lock_path = project / "spec_lock.json"
    if not lock_path.exists():
        raise FileNotFoundError(
            f"spec_lock.json not found in {project}. Run create_spec() first."
        )
    spec_lock = json.loads(lock_path.read_text(encoding="utf-8"))
    out_dir = ensure_dir(project / "svg_output")
    for old in out_dir.glob("*.svg"):
        old.unlink()

    paths: list[Path] = []
    total = len(plans)

    for plan in plans:
        # Try domain-specific renderers in priority order
        svg = render_teaching_slide(plan, spec_lock, total)
        if svg is None:
            svg = render_course_slide(plan, spec_lock, total)
        if svg is None:
            svg = render_competition_slide(plan, spec_lock, total)

        if svg is None:
            # Fall back to existing layout renderers
            body = "\n".join(
                item.primary for item in plan.items
            ) if plan.items else ""
            svg = _render_slide_svg(
                plan.index, plan.title, body, spec_lock, total,
                layout=plan.layout,
            )

        path = out_dir / f"slide_{plan.index:02d}.svg"
        path.write_text(svg, encoding="utf-8")
        paths.append(path)

    return paths


# ---------------------------------------------------------------------------
# SVG QA — v2.0 permissive rules
# ---------------------------------------------------------------------------

def check_project_svg(project_path: Path | str, stage: str = "output") -> tuple[bool, list[SvgIssue]]:
    project = Path(project_path)
    svg_dir = project / ("svg_final" if stage == "final" else "svg_output")
    issues: list[SvgIssue] = []
    for svg_file in sorted(svg_dir.glob("*.svg")):
        issues.extend(check_svg_file(svg_file, project))
    if not list(svg_dir.glob("*.svg")):
        issues.append(SvgIssue("error", str(svg_dir), "No SVG files found"))
    return not any(issue.level == "error" for issue in issues), issues


def check_svg_file(svg_file: Path, project_path: Path) -> list[SvgIssue]:
    issues: list[SvgIssue] = []
    try:
        root = ET.fromstring(svg_file.read_text(encoding="utf-8"))
    except ET.ParseError as exc:
        return [SvgIssue("error", str(svg_file), f"Invalid XML: {exc}")]

    if not root.tag.endswith("svg"):
        issues.append(SvgIssue("error", str(svg_file), "Root element is not <svg>"))

    width = root.attrib.get("width")
    height = root.attrib.get("height")
    viewbox = root.attrib.get("viewBox")
    if not (width and height and viewbox):
        issues.append(SvgIssue("error", str(svg_file), "SVG must declare width, height, and viewBox"))
    elif viewbox.strip() != f"0 0 {width} {height}":
        issues.append(SvgIssue("error", str(svg_file), "viewBox must match width and height"))

    for elem in root.iter():
        tag = _local_name(elem.tag)

        # Banned tags — hard error
        if tag in BANNED_TAGS or tag.startswith("animate"):
            issues.append(SvgIssue("error", str(svg_file), f"Banned SVG tag: <{tag}>"))

        # Path must have non-empty d
        if tag == "path" and not elem.attrib.get("d", "").strip():
            issues.append(SvgIssue("error", str(svg_file), "SVG <path> requires a non-empty d attribute"))

        # Polygon/polyline must have points
        if tag in {"polygon", "polyline"} and not elem.attrib.get("points", "").strip():
            issues.append(SvgIssue("error", str(svg_file), f"SVG <{tag}> requires a non-empty points attribute"))

        # Only ban event-handler attributes
        for attr in elem.attrib:
            if attr in BANNED_ATTRS or attr.startswith("on"):
                issues.append(SvgIssue("error", str(svg_file), f"Banned event-handler attribute: {attr}"))

        # Warn (not error) for external href in <use>
        if tag == "use":
            href = elem.attrib.get("href", "") or elem.attrib.get(
                "{http://www.w3.org/1999/xlink}href", ""
            )
            if href and not href.startswith("#"):
                issues.append(
                    SvgIssue("warning", str(svg_file), f"External href in <use>: {href} (prefer local #id)")
                )

    # Require at least one semantic top-level content group
    content_groups = [
        child for child in list(root)
        if _local_name(child.tag) == "g" and not _is_chrome_group(child.attrib.get("id", ""))
    ]
    if not content_groups:
        issues.append(SvgIssue("error", str(svg_file), "No semantic top-level content groups found"))

    for group in content_groups:
        if not group.attrib.get("id"):
            issues.append(SvgIssue("error", str(svg_file), "Top-level content group missing id attribute"))

    # ── Text overflow detection ──────────────────────────────────────
    # Estimate text bounding boxes and flag any that extend beyond canvas.
    canvas_w = int(width) if width and width.isdigit() else 0
    canvas_h = int(height) if height and height.isdigit() else 0
    if canvas_w and canvas_h:
        for elem in root.iter():
            tag = _local_name(elem.tag)
            if tag != "text":
                continue
            # Get position
            try:
                tx = int(float(elem.attrib.get("x", "0")))
                ty = int(float(elem.attrib.get("y", "0")))
            except (ValueError, TypeError):
                continue
            # Get font-size
            fs_str = elem.attrib.get("font-size", "")
            try:
                fs = int(float(fs_str)) if fs_str else 20
            except (ValueError, TypeError):
                fs = 20
            # Collect text content (including tspans)
            texts = []
            if elem.text and elem.text.strip():
                texts.append(elem.text.strip())
            for child in elem:
                if _local_name(child.tag) == "tspan" and child.text:
                    texts.append(child.text.strip())
            full_text = " ".join(texts)
            if not full_text:
                continue
            # Estimate bounds
            _, y_top, x_right, y_bottom = _estimate_text_bounds(
                full_text, fs, tx, ty, max_width=canvas_w - tx - 20,
            )
            # Check overflow
            margin = 10  # allow small margin
            if x_right > canvas_w + margin:
                issues.append(SvgIssue(
                    "warning", str(svg_file),
                    f"Text may overflow right edge: x_right≈{x_right}px > canvas {canvas_w}px "
                    f"(text: \"{full_text[:40]}...\")"
                ))
            if y_bottom > canvas_h + margin:
                issues.append(SvgIssue(
                    "warning", str(svg_file),
                    f"Text may overflow bottom edge: y_bottom≈{y_bottom}px > canvas {canvas_h}px "
                    f"(text: \"{full_text[:40]}...\")"
                ))

    return issues


def finalize_svg(project_path: Path | str) -> list[Path]:
    project = Path(project_path)
    ok, issues = check_project_svg(project)
    if not ok:
        details = "\n".join(f"{i.level}: {i.file}: {i.message}" for i in issues)
        raise RuntimeError(f"SVG quality gate failed:\n{details}")
    source_dir = project / "svg_output"
    final_dir = ensure_dir(project / "svg_final")
    for old in final_dir.glob("*.svg"):
        old.unlink()

    # Resolve theme + language profile once so chart/code/icon placeholders
    # render with the right palette and CJK fallbacks.
    from .enhancements import expand_enhancements_in_file
    from .themes import get_theme
    theme = None
    lock_path = project / "spec_lock.json"
    if lock_path.exists():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            theme = get_theme(lock.get("theme", "dark-tech"))
            lang = lock.get("lang")
            if lang:
                from .i18n import apply_language_profile
                theme = apply_language_profile(theme, lang)
        except Exception:  # noqa: BLE001 — fall back to default theme silently
            theme = None

    paths: list[Path] = []
    for src in sorted(source_dir.glob("*.svg")):
        dst = final_dir / src.name
        shutil.copy2(src, dst)
        expand_enhancements_in_file(dst, theme=theme)
        paths.append(dst)
    return paths


def write_svg_report(project_path: Path | str, stage: str = "output") -> Path:
    project = Path(project_path)
    ok, issues = check_project_svg(project, stage=stage)
    report = project / "qa" / "SVG-QA.md"
    ensure_dir(report.parent)
    lines = ["# SVG QA", "", f"status: {'passed' if ok else 'failed'}", ""]
    if issues:
        for issue in issues:
            lines.append(f"- **{issue.level}** `{issue.file}`: {issue.message}")
    else:
        lines.append("- No issues found.")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_or_create_lock(
    project: Path,
    source_markdown: Path | str,
    theme_name: str = "dark-tech",
) -> dict:
    lock = project / "spec_lock.json"
    if not lock.exists():
        create_spec(project, source_markdown, theme_name=theme_name)
    return json.loads(lock.read_text(encoding="utf-8"))


def _first_heading(markdown: str) -> str | None:
    for line in markdown.splitlines():
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def _markdown_to_slides(markdown: str) -> list[tuple[str, str]]:
    slides: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_body: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("#"):
            if current_title:
                slides.append((current_title, current_body))
            current_title = line.lstrip("#").strip()
            current_body = []
        else:
            current_body.append(line.strip())
    if current_title:
        slides.append((current_title, current_body))
    if not slides and markdown.strip():
        slides.append(("Overview", markdown.strip().splitlines()))
    return [(title, "\n".join(body)) for title, body in slides]


def _select_layout(heading: str, body: str, index: int, total: int) -> str:
    """Content-driven layout router. Returns a layout name string.

    Order matters — earlier checks win. Designed so common patterns map to
    the richest applicable layout (executive_summary, process_flow, etc.)
    instead of falling through to plain bullet-list every time.
    """
    if not body.strip():
        return "section-divider"
    raw_lines = [line for line in body.split("\n") if line.strip()]
    lines = [line.strip() for line in raw_lines]
    bullet_lines = [line[2:].strip() for line in lines if line.startswith("- ")]

    # Quote / takeaway: body starts with "> " or wrapped in fancy quotes.
    first = lines[0]
    if first.startswith("> ") or first.startswith("\u201c") or first.startswith('"'):
        return "quote-block"

    # Process flow: bullets separated by "→" arrows OR numbered step prefixes.
    has_arrows = any("→" in line or "->" in line for line in lines)
    numbered = sum(1 for line in lines if re.match(r"^\d+[\.、)]\s", line))
    if has_arrows or numbered >= 3:
        return "process-flow"

    # Comparison: explicit "vs" OR at least one line shaped as
    # "label | description" with both sides non-empty. A bare pipe
    # anywhere in the body is too broad and matches markdown tables.
    pipe_pairs = [
        line for line in lines
        if "|" in line
        and line.split("|", 1)[0].strip()
        and line.split("|", 1)[1].strip()
    ]
    if re.search(r"\bvs\.?\b", body, re.IGNORECASE) or len(pipe_pairs) >= 2:
        return "comparison"

    # Metric-highlight: bullet items dominated by numeric/percentage data
    # (e.g. "- 32% YoY growth"). Must beat the generic bullet fallback.
    if bullet_lines:
        metric_bullets = sum(
            1 for b in bullet_lines if re.search(r"\d+\s*[%％]|\d+\s*[万亿KMB]", b)
        )
        if metric_bullets >= max(2, len(bullet_lines) // 2):
            return "metric-highlight"

    # Executive summary: 3-6 short bullet items (avg < 50 chars), title-like.
    if 3 <= len(bullet_lines) <= 6:
        avg_len = sum(len(b) for b in bullet_lines) / len(bullet_lines)
        if avg_len < 50:
            return "executive-summary"

    if bullet_lines:
        return "bullet-list"
    if re.search(r"\d+%|\d+[万亿]", body):
        return "metric-highlight"
    return "default"


def _distribute_layouts(
    layouts: list[str],
    slides: list[tuple[str, str]] | None = None,
) -> list[str]:
    """Anti-monotony pass: break up runs of 3+ identical content layouts.

    Keeps cover / section-divider / closing untouched. For a run of the
    same content layout, rotates the middle slide to a contrasting layout
    — but only to a layout that can fit all of that slide's content
    (so we never silently truncate bullets, etc.).
    """
    chrome = {"cover", "section-divider", "closing"}
    result = list(layouts)

    def _bullet_count(idx: int) -> int:
        if not slides or idx >= len(slides):
            return 99
        body = slides[idx][1]
        return sum(
            1 for line in body.split("\n")
            if line.strip().startswith(("- ", "* ", "• "))
        )

    def _safe_rotation(cur: str, idx: int) -> str | None:
        # Pick a contrasting layout that preserves this slide's content.
        if cur == "bullet-list":
            # Only collapse to 3-card summary if it really has ≤3 bullets.
            if _bullet_count(idx) <= 3:
                return "executive-summary"
            # Otherwise keep all content but use the default chrome.
            return "default"
        if cur == "executive-summary":
            # bullet-list always preserves all bullets.
            return "bullet-list"
        if cur == "default":
            return "bullet-list" if _bullet_count(idx) > 0 else None
        if cur == "metric-highlight":
            return "default"
        return None

    i = 1
    while i < len(result) - 1:
        prev, cur, nxt = result[i - 1], result[i], result[i + 1]
        if cur in chrome:
            i += 1
            continue
        if prev == cur == nxt:
            alt = _safe_rotation(cur, i)
            if alt and alt != cur:
                result[i] = alt
        i += 1
    return result


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _is_chrome_group(gid: str) -> bool:
    return gid.startswith("chrome-") or gid == "background"


# ---------------------------------------------------------------------------
# SVG rendering — programmatic fallback used by generate_svg()
# ---------------------------------------------------------------------------

def _render_slide_svg(
    index: int,
    heading: str,
    body: str,
    lock: dict,
    total: int = 1,
    has_competition: bool = False,
    project_title: str = "",
    layout: str | None = None,
) -> str:
    canvas = lock["canvas"]
    w = int(canvas["width"])
    h = int(canvas["height"])
    if layout is None:
        if index == 1:
            layout = "cover"
        elif index == total and total > 1:
            layout = "closing"
        else:
            layout = _select_layout(heading, body, index, total)

    dispatch = {
        "cover": _render_cover,
        "closing": _render_closing,
        "section-divider": lambda i, h_, b, l, t, w_, h_p: _render_section_divider(i, h_, l, t, w_, h_p),
        "bullet-list": _render_bullet_list,
        "metric-highlight": _render_metric_highlight,
        "two-column": _render_two_column,
        "comparison": _render_comparison,
        "executive-summary": _render_executive_summary,
        "quote-block": _render_quote_block,
        "process-flow": _render_process_flow,
        "default": _render_default,
    }
    fn = dispatch.get(layout, _render_default)
    return fn(index, heading, body, lock, total, w, h)


def _tokens(w: int, h: int) -> dict:
    """Unified design token system for consistent spacing, type, and surface."""
    unit = min(w, h) // 72
    return {
        "margin": {"page": unit * 5, "content": unit * 4, "tight": unit * 2},
        "type": {
            "hero": unit * 6,
            "h1": unit * 5,
            "h2": unit * 4,
            "body": unit * 2 + 2,
            "caption": unit * 2,
            "overline": int(unit * 1.4),
        },
        "radius": {"card": unit * 2, "pill": unit * 3, "sm": unit},
        "shadow": {
            "sm": (0, 1, 3, 0.06),
            "md": (0, 2, 6, 0.08),
            "lg": (0, 4, 12, 0.10),
        },
        "accent_stripe": unit // 2,
    }


def _chrome(index: int, total: int, lock: dict, w: int, h: int) -> str:
    """Render subtle left gradient accent line and lightweight page number."""
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    sw = t["accent_stripe"]
    return (
        f'  <defs>\n'
        f'    <linearGradient id="accent-fade-{index:02d}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0.4"/>\n'
        f'      <stop offset="50%" stop-color="{p["accent"]}" stop-opacity="0.9"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0.4"/>\n'
        f'    </linearGradient>\n'
        f'  </defs>\n'
        f'  <g id="chrome-stripe">\n'
        f'    <rect x="0" y="0" width="{sw}" height="{h}" fill="url(#accent-fade-{index:02d})" />\n'
        f'  </g>\n'
        f'  <g id="chrome-footer">\n'
        f'    <text x="{w - t['margin']['tight'] * 3}" y="{h - t['margin']['tight'] * 2}" '
        f'font-family="{font}" font-size="{t['type']['overline']}" '
        f'fill="{p["muted"]}" text-anchor="end" opacity="0.6">'
        f'{index:02d} / {total:02d}</text>\n'
        f'  </g>'
    )


def _decor_orbs(index: int, lock: dict, w: int, h: int, intensity: float = 0.18) -> tuple[str, str]:
    """Ambient gradient blobs for visual depth. Returns (defs_fragment, body_fragment)."""
    p = lock["palette"]
    eff_intensity = min(intensity * 0.75, 0.15)
    defs = (
        f'    <radialGradient id="orb-{index:02d}" cx="50%" cy="50%" r="50%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="{eff_intensity}"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'    </radialGradient>\n'
        f'    <radialGradient id="orb2-{index:02d}" cx="50%" cy="50%" r="50%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="{eff_intensity * 0.6}"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'    </radialGradient>'
    )
    body = (
        f'  <g id="decor-{index:02d}">\n'
        f'    <ellipse cx="{w - 80}" cy="40" rx="300" ry="220" fill="url(#orb-{index:02d})"/>\n'
        f'    <ellipse cx="80" cy="{h - 40}" rx="200" ry="140" fill="url(#orb2-{index:02d})"/>\n'
        f'  </g>'
    )
    return defs, body


def _title_font_size(heading: str) -> int:
    n = len(heading)
    if n <= 15:
        return 56
    if n <= 25:
        return 44
    if n <= 35:
        return 38
    return 32


def _auto_body_font(
    lines: list[str],
    max_width: int,
    avail_height: int,
    *,
    max_size: int = 24,
    floor_size: int = 14,
    line_height: float = 1.45,
    gap: int = 12,
) -> tuple[int, int]:
    """Calculate the best body font size so all text fits the available area.

    Starts from max_size and steps down until total visual height fits.
    Returns (font_size, line_dy) tuple.

    Args:
        lines: Text lines to render.
        max_width: Available text width in pixels.
        avail_height: Available vertical space in pixels.
        max_size: Largest font size to attempt.
        floor_size: Smallest font size allowed (readability floor).
        line_height: Line-height multiplier (relative to font size).
        gap: Pixel gap between logical items.
    """
    if not lines:
        return max_size, int(max_size * line_height)

    for size in range(max_size, floor_size - 1, -1):
        dy = int(size * line_height)
        total_h = 0
        for text in lines:
            wrapped = _visual_wrap(text, max_width, size)
            vis_lines = max(len(wrapped), 1)
            total_h += vis_lines * dy + gap
        total_h -= gap  # no trailing gap

        if total_h <= avail_height:
            return size, dy

    # Even floor_size overflows — return floor anyway
    return floor_size, int(floor_size * line_height)


def _estimate_text_bounds(
    text: str,
    font_size: int,
    x: int,
    y: int,
    max_width: int | None = None,
) -> tuple[int, int, int, int]:
    """Estimate pixel bounding box (x, y_top, x_right, y_bottom) for a text run.

    Uses the same character-width model as _visual_wrap.
    If max_width is given, accounts for wrapping.
    """
    if not text:
        return (x, y, x, y)

    if max_width:
        wrapped = _visual_wrap(text, max_width, font_size)
    else:
        wrapped = [text]

    line_dy = int(font_size * 1.45)
    max_line_w = max(
        (_token_width(line, font_size) for line in wrapped),
        default=0,
    )
    y_top = y - font_size  # approximate ascent
    y_bottom = y + (len(wrapped) - 1) * line_dy
    return (x, int(y_top), int(x + max_line_w), int(y_bottom))


def _render_section_divider(index: int, heading: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    title = xml_escape(heading)
    band_y = h // 2 - 80
    fsize = _title_font_size(heading)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=0.20)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="band-grad-{index:02d}" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" />\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0.55" />\n'
        f'    </linearGradient>\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="section-eyebrow-{index:02d}">\n'
        f'    <text x="{w // 2}" y="{band_y - 32}" font-family="{font}" font-size="14" '
        f'font-weight="600" fill="{p["accent"]}" text-anchor="middle" letter-spacing="4">'
        f'CHAPTER {index:02d}</text>\n'
        f'  </g>\n'
        f'  <g id="section-band-{index:02d}">\n'
        f'    <rect x="0" y="{band_y}" width="{w}" height="160" fill="url(#band-grad-{index:02d})"/>\n'
        f'  </g>\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{w // 2}" y="{band_y + 96}" font-family="{font}" font-size="{fsize}" '
        f'font-weight="700" fill="{p["text"]}" text-anchor="middle">{title}</text>\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_bullet_list(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    lines = [line.strip() for line in body.split("\n") if line.strip()][:7]
    title = xml_escape(heading)
    fsize_title = _title_font_size(heading)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=0.12)

    bullet_parts: list[str] = []
    row_y = 160
    n = len(lines) if lines else 1
    avail = h - row_y - 60

    clean_lines = [
        (line[2:].strip() if line.startswith("- ") else line) for line in lines
    ]
    max_text_w = w - m * 4 - 160
    body_font, line_dy = _auto_body_font(
        clean_lines, max_text_w, avail,
        max_size=t["type"]["body"], floor_size=t["type"]["caption"], gap=10,
    )

    base_row_h = max(54, min(72, (avail - (n - 1) * 12) // max(n, 1)))
    card_rx = t["radius"]["card"]
    for i, line in enumerate(lines):
        is_bullet = line.startswith("- ")
        text_content = line[2:].strip() if is_bullet else line
        text_x = m * 2 + 40 if is_bullet else m * 2
        max_text_w = w - m * 2 - text_x - 32
        tspans, vis_lines = _wrap_to_tspans(
            text_content, text_x, body_font, max_text_w, line_height=line_dy / body_font
        )
        row_h = max(base_row_h, vis_lines * line_dy + 24)
        bullet_parts.append(
            f'    <rect x="{m}" y="{row_y}" width="{w - m * 2}" height="{row_h}" rx="{card_rx}" '
            f'fill="url(#row-grad-{index:02d})" filter="url(#card-shadow-{index:02d})"/>'
        )
        text_block_h = vis_lines * line_dy
        text_y = row_y + (row_h - text_block_h) // 2 + body_font
        if is_bullet:
            cy = row_y + row_h // 2
            bullet_parts.append(
                f'    <circle cx="{m + 36}" cy="{cy}" r="14" fill="{p["accent"]}" opacity="0.12"/>'
            )
            bullet_parts.append(
                f'    <circle cx="{m + 36}" cy="{cy}" r="4" fill="{p["accent"]}"/>'
            )
            bullet_parts.append(
                f'    <text x="{text_x}" y="{text_y}" font-family="{font}" font-size="{body_font}" '
                f'fill="{p["text"]}">{tspans}</text>'
            )
        else:
            bullet_parts.append(
                f'    <text x="{text_x}" y="{text_y}" font-family="{font}" '
                f'font-size="{body_font}" fill="{p["text"]}">{tspans}</text>'
            )
        row_y += row_h + 12

    bullets_svg = "\n".join(bullet_parts)
    bar_w = 48
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="row-grad-{index:02d}" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.7"/>\n'
        f'    </linearGradient>\n'
        f'    <filter id="card-shadow-{index:02d}" x="-2%" y="-2%" width="104%" height="108%">\n'
        f'      <feDropShadow dx="0" dy="1" stdDeviation="3" flood-color="{p["muted"]}" flood-opacity="0.25"/>\n'
        f'    </filter>\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'  <g id="decor-bar-{index:02d}">\n'
        f'    <rect x="{w - bar_w}" y="0" width="{bar_w}" height="{h}" fill="{p["accent"]}" opacity="0.04"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 28}" font-family="{font}" font-size="{fsize_title}" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="{m}" y="{m + 40}" width="48" height="3" rx="1.5" fill="{p["accent"]}" opacity="0.7"/>\n'
        f'  </g>\n'
        f'  <g id="content-body-{index:02d}">\n'
        f'{bullets_svg}\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_metric_highlight(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    title = xml_escape(heading)
    fsize_title = _title_font_size(heading)
    chrome = _chrome(index, total, lock, w, h)

    metrics = re.findall(r"(\d+(?:\.\d+)?%|\d+[万亿]\S*|\d+x|\d+\+)", body)
    labels_raw = re.split(r"\d+(?:\.\d+)?%|\d+[万亿]\S*|\d+x|\d+\+", body)
    labels = [s.strip().strip("-•:，。").strip() for s in labels_raw if s.strip()]

    if not metrics:
        return _render_default(index, heading, body, lock, total, w, h)

    count = min(len(metrics), 4)
    gutter = t["margin"]["tight"]
    card_w = (w - m * 2 - (count - 1) * gutter) // count
    card_h = int(h * 0.47)
    card_y = m + t["type"]["h1"] + t["margin"]["tight"] * 2
    card_rx = t["radius"]["card"]
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=0.12)

    card_parts: list[str] = []
    for i in range(count):
        cx = m + i * (card_w + gutter)
        mid_x = cx + card_w // 2
        metric_text = xml_escape(metrics[i])
        metric_len = len(metric_text)
        if metric_len <= 6:
            metric_fsize = t["type"]["hero"]
        elif metric_len <= 10:
            metric_fsize = t["type"]["h1"]
        elif metric_len <= 16:
            metric_fsize = t["type"]["h2"]
        else:
            metric_fsize = t["type"]["body"]
        card_parts.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{card_rx}" '
            f'fill="url(#metric-grad-{index:02d})" filter="url(#metric-shadow-{index:02d})"/>'
        )
        card_parts.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" height="4" rx="2" fill="{p["accent"]}" opacity="0.8"/>'
        )
        num_y = card_y + t["type"]["caption"] + t["margin"]["tight"]
        card_parts.append(
            f'    <text x="{mid_x}" y="{num_y}" font-family="{font}" font-size="{t["type"]["overline"]}" '
            f'font-weight="500" fill="{p["accent"]}" text-anchor="middle" letter-spacing="2" opacity="0.8">'
            f'{i + 1:02d}</text>'
        )
        card_parts.append(
            f'    <text x="{mid_x}" y="{card_y + card_h // 2 + 2}" font-family="{font}" font-size="{metric_fsize}" '
            f'font-weight="700" fill="{p["text"]}" text-anchor="middle">{metric_text}</text>'
        )
        label = xml_escape(labels[i][:40]) if i < len(labels) else ""
        if label:
            lbl_y = card_y + card_h - t["type"]["caption"] * 2
            card_parts.append(
                f'    <text x="{mid_x}" y="{lbl_y}" font-family="{font}" '
                f'font-size="{t["type"]["caption"]}" fill="{p["body"]}" text-anchor="middle" opacity="0.9">{label}</text>'
            )

    bar_w = t["accent_stripe"] * 6
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="metric-grad-{index:02d}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.85"/>\n'
        f'    </linearGradient>\n'
        f'    <filter id="metric-shadow-{index:02d}" x="-3%" y="-2%" width="106%" height="110%">\n'
        f'      <feDropShadow dx="0" dy="2" stdDeviation="6" flood-color="{p["muted"]}" flood-opacity="0.2"/>\n'
        f'    </filter>\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'  <g id="decor-bar-{index:02d}">\n'
        f'    <rect x="{w - bar_w}" y="0" width="{bar_w}" height="{h}" fill="{p["accent"]}" opacity="0.04"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 28}" font-family="{font}" font-size="{fsize_title}" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="{m}" y="{m + 40}" width="48" height="3" rx="1.5" fill="{p["accent"]}" opacity="0.7"/>\n'
        f'  </g>\n'
        f'  <g id="content-metric-{index:02d}">\n'
        + "\n".join(card_parts) +
        f'\n  </g>\n'
        f'</svg>'
    )


def _render_two_column(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    title = xml_escape(heading)
    fsize_title = min(_title_font_size(heading), t["type"]["h1"])
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=0.10)

    if "|" in body:
        parts = body.split("|", 1)
    elif re.search(r"\bvs\.?\b", body, re.IGNORECASE):
        parts = re.split(r"\bvs\.?\b", body, maxsplit=1, flags=re.IGNORECASE)
    else:
        mid = len(body) // 2
        parts = [body[:mid], body[mid:]]

    left_text = parts[0].strip()[:300]
    right_text = parts[1].strip()[:300] if len(parts) > 1 else ""
    gutter = t["margin"]["tight"]
    col_w = (w - m * 2 - gutter) // 2
    col_y = m + t["type"]["h1"] + t["margin"]["tight"] * 2
    col_h = h - col_y - t["margin"]["page"]
    right_x = m + col_w + gutter
    body_font = t["type"]["body"]
    line_dy = int(body_font * 1.4)
    inner_w = col_w - t["margin"]["page"]
    col_rx = t["radius"]["card"]
    left_tspans, _ = _wrap_to_tspans(left_text, m + t["margin"]["tight"] * 2, body_font, inner_w, line_height=line_dy / body_font)
    right_tspans, _ = _wrap_to_tspans(right_text, right_x + t["margin"]["tight"], body_font, inner_w, line_height=line_dy / body_font)

    bar_w = t["accent_stripe"] * 6
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="col-grad-{index:02d}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["muted"]}" stop-opacity="1"/>\n'
        f'    </linearGradient>\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'  <g id="decor-bar-{index:02d}">\n'
        f'    <rect x="{w - bar_w}" y="0" width="{bar_w}" height="{h}" fill="{p["accent"]}" opacity="0.04"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 28}" font-family="{font}" font-size="{fsize_title}" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="{m}" y="{m + 40}" width="48" height="3" rx="1.5" fill="{p["accent"]}" opacity="0.7"/>\n'
        f'  </g>\n'
        f'  <g id="content-left-{index:02d}">\n'
        f'    <rect x="{m}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}" '
        f'fill="url(#col-grad-{index:02d})"/>\n'
        f'    <rect x="{m}" y="{col_y}" width="{col_w}" height="6" rx="3" fill="{p["accent"]}"/>\n'
        f'    <text x="{m + t["margin"]["tight"] * 2}" y="{col_y + t["type"]["caption"] + t["margin"]["tight"]}" font-family="{font}" font-size="{t["type"]["overline"]}" '
        f'font-weight="600" fill="{p["accent"]}" letter-spacing="3">A</text>\n'
        f'    <text x="{m + t["margin"]["tight"] * 2}" y="{col_y + t["type"]["h2"] + t["margin"]["tight"] * 2}" font-family="{font}" font-size="{body_font}" '
        f'fill="{p["text"]}">{left_tspans}</text>\n'
        f'  </g>\n'
        f'  <g id="content-right-{index:02d}">\n'
        f'    <rect x="{right_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}" '
        f'fill="url(#col-grad-{index:02d})"/>\n'
        f'    <rect x="{right_x}" y="{col_y}" width="{col_w}" height="6" rx="3" fill="{p["accent"]}"/>\n'
        f'    <text x="{right_x + t["margin"]["tight"]}" y="{col_y + t["type"]["caption"] + t["margin"]["tight"]}" font-family="{font}" font-size="{t["type"]["overline"]}" '
        f'font-weight="600" fill="{p["accent"]}" letter-spacing="3">B</text>\n'
        f'    <text x="{right_x + t["margin"]["tight"]}" y="{col_y + t["type"]["h2"] + t["margin"]["tight"] * 2}" font-family="{font}" font-size="{body_font}" '
        f'fill="{p["text"]}">{right_tspans}</text>\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_cover(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    """Hero/cover layout — centered title with strong visual presence."""
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    title = xml_escape(heading)
    body_lines = [line.strip() for line in body.split("\n") if line.strip()]
    subtitle = xml_escape(body_lines[0][:140]) if body_lines else ""
    cx = w // 2
    cy = h // 2
    m = t["margin"]["page"]
    hero_fsize = t["type"]["hero"]
    max_title_w = w - m * 4
    est_title_w = len(heading) * hero_fsize * 0.55
    if est_title_w > max_title_w:
        hero_fsize = max(int(hero_fsize * max_title_w / est_title_w), t["type"]["h2"])
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <radialGradient id="hero-orb-{index:02d}" cx="50%" cy="50%" r="60%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0.25"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'    </radialGradient>\n'
        f'    <linearGradient id="hero-bar-{index:02d}" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'      <stop offset="30%" stop-color="{p["accent"]}" stop-opacity="0.9"/>\n'
        f'      <stop offset="70%" stop-color="{p["accent"]}" stop-opacity="0.9"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'    </linearGradient>\n'
        f'    <linearGradient id="bottom-accent-{index:02d}" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'      <stop offset="20%" stop-color="{p["accent"]}" stop-opacity="0.7"/>\n'
        f'      <stop offset="80%" stop-color="{p["accent"]}" stop-opacity="0.7"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'    </linearGradient>\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'  <g id="decor-{index:02d}">\n'
        f'    <ellipse cx="{cx}" cy="{cy - m}" rx="{w // 3}" ry="{h // 3}" fill="url(#hero-orb-{index:02d})"/>\n'
        f'  </g>\n'
        f'  <g id="chrome-bottom">\n'
        f'    <rect x="0" y="{h - m // 2}" width="{w}" height="{m // 2}" fill="url(#bottom-accent-{index:02d})"/>\n'
        f'  </g>\n'
        f'  <g id="content-eyebrow-{index:02d}">\n'
        f'    <text x="{cx}" y="{cy - m * 2}" font-family="{font}" font-size="{t['type']['overline']}" '
        f'font-weight="600" fill="{p["accent"]}" text-anchor="middle" letter-spacing="4" opacity="0.9">PRESENTATION</text>\n'
        f'  </g>\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{cx}" y="{cy}" font-family="{font}" font-size="{hero_fsize}" '
        f'font-weight="700" fill="{p["text"]}" text-anchor="middle">{title}</text>\n'
        f'  </g>\n'
        f'  <g id="content-divider-{index:02d}">\n'
        f'    <rect x="{cx - m * 2}" y="{cy + m}" width="{m * 4}" height="3" rx="1.5" fill="url(#hero-bar-{index:02d})"/>\n'
        f'  </g>\n'
        f'  <g id="content-body-{index:02d}">\n'
        f'    <text x="{cx}" y="{cy + m * 3}" font-family="{font}" font-size="{t['type']['body']}" fill="{p["body"]}" '
        f'text-anchor="middle" opacity="0.85">{subtitle}</text>\n'
        f'  </g>\n'
        f'  <g id="content-footer-{index:02d}">\n'
        f'    <text x="{cx}" y="{h - m // 2 - 6}" font-family="{font}" font-size="{t['type']['overline']}" '
        f'fill="{p["accent"]}" text-anchor="middle" letter-spacing="3" opacity="0.7">{total:02d} SLIDES</text>\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_closing(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    """Thank-you/CTA layout — used for the last slide of a deck."""
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    title = xml_escape(heading)
    body_lines = [line.strip() for line in body.split("\n") if line.strip()]
    subtitle = xml_escape(body_lines[0][:160]) if body_lines else ""
    base = _title_font_size(heading)
    fsize_title = base + t["margin"]["tight"] if base >= t["type"]["h1"] else base
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=0.10)
    cx, cy = w // 2, h // 2
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-eyebrow-{index:02d}">\n'
        f'    <line x1="{cx - t["margin"]["tight"] * 2}" y1="{cy - t["type"]["h1"] - t["margin"]["tight"]}" x2="{cx + t["margin"]["tight"] * 2}" y2="{cy - t["type"]["h1"] - t["margin"]["tight"]}" '
        f'stroke="{p["accent"]}" stroke-width="2"/>\n'
        f'  </g>\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{cx}" y="{cy - t["margin"]["tight"] * 2}" font-family="{font}" font-size="{fsize_title}" '
        f'font-weight="700" fill="{p["text"]}" text-anchor="middle">{title}</text>\n'
        f'  </g>\n'
        f'  <g id="content-body-{index:02d}">\n'
        f'{_render_closing_body(w, h, font, p, subtitle, t)}\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_closing_body(w: int, h: int, font: str, p: dict, subtitle: str, t: dict | None = None) -> str:
    if not subtitle:
        return ""
    t = t or _tokens(w, h)
    body_font = t["type"]["body"]
    line_dy = int(body_font * 1.5)
    max_text_w = int(w * 0.65)
    tspans, _ = _wrap_to_tspans(subtitle, w // 2, body_font, max_text_w, line_height=line_dy / body_font)
    return (
        f'    <text x="{w // 2}" y="{h // 2 + t["margin"]["tight"] * 2}" font-family="{font}" font-size="{body_font}" '
        f'fill="{p["body"]}" text-anchor="middle">{tspans}</text>'
    )


def _render_default(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    title = xml_escape(heading)
    fsize_title = _title_font_size(heading)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=0.12)

    body_lines = [line.strip() for line in body.split("\n") if line.strip()][:8]
    body_parts: list[str] = []
    y = m + t["type"]["h1"] + t["margin"]["tight"] * 4
    max_text_w = w - m * 2 - t["margin"]["page"]
    avail_h = h - y - t["margin"]["page"]
    body_font, line_dy = _auto_body_font(
        body_lines, max_text_w, avail_h,
        max_size=t["type"]["body"], floor_size=t["type"]["caption"], gap=t["margin"]["tight"] - 4,
    )
    total_visual_lines = 0
    text_x = m + t["margin"]["tight"] * 2
    for line in body_lines:
        tspans, n = _wrap_to_tspans(line, text_x, body_font, max_text_w, line_height=line_dy / body_font)
        body_parts.append(
            f'    <text x="{text_x}" y="{y}" font-family="{font}" font-size="{body_font}" '
            f'fill="{p["body"]}">{tspans}</text>'
        )
        y += line_dy * n + t["margin"]["tight"] - 4
        total_visual_lines += n

    body_svg = "\n".join(body_parts)
    card_h = max(t["margin"]["page"], total_visual_lines * line_dy + len(body_lines) * (t["margin"]["tight"] - 4) + t["margin"]["tight"] * 2)
    card_rx = t["radius"]["card"]
    card_y = m + t["type"]["h1"] + t["margin"]["tight"] * 2
    bar_w = t["accent_stripe"] * 6
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="card-grad-{index:02d}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}" />\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.85" />\n'
        f'    </linearGradient>\n'
        f'    <filter id="card-shadow-{index:02d}" x="-2%" y="-2%" width="104%" height="108%">\n'
        f'      <feDropShadow dx="0" dy="1" stdDeviation="4" flood-color="{p["muted"]}" flood-opacity="0.2"/>\n'
        f'    </filter>\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'  <g id="decor-bar-{index:02d}">\n'
        f'    <rect x="{w - bar_w}" y="0" width="{bar_w}" height="{h}" fill="{p["accent"]}" opacity="0.04"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 28}" font-family="{font}" font-size="{fsize_title}" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="{m}" y="{m + 40}" width="48" height="3" rx="1.5" fill="{p["accent"]}" opacity="0.7"/>\n'
        f'  </g>\n'
        f'  <g id="content-body-{index:02d}">\n'
        f'    <rect x="{m}" y="{card_y}" width="{w - m * 2}" height="{card_h}" rx="{card_rx}" '
        f'fill="url(#card-grad-{index:02d})" filter="url(#card-shadow-{index:02d})"/>\n'
        f'{body_svg}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# v3.0 layout primitives — drop shadow, executive summary, comparison,
# quote block, process flow. Inspired by ppt-master MBB / consulting decks.
# ---------------------------------------------------------------------------

def _shadow_filter_def(index: int) -> str:
    """Reusable card drop-shadow filter (matches ppt-master cardShadow)."""
    return (
        f'    <filter id="card-shadow-{index:02d}" x="-20%" y="-20%" '
        f'width="140%" height="150%">\n'
        f'      <feGaussianBlur in="SourceAlpha" stdDeviation="6" result="blur"/>\n'
        f'      <feOffset in="blur" dx="0" dy="3" result="offsetBlur"/>\n'
        f'      <feFlood flood-color="#000000" flood-opacity="0.16" '
        f'result="shadowColor"/>\n'
        f'      <feComposite in="shadowColor" in2="offsetBlur" '
        f'operator="in" result="shadow"/>\n'
        f'      <feMerge>\n'
        f'        <feMergeNode in="shadow"/>\n'
        f'        <feMergeNode in="SourceGraphic"/>\n'
        f'      </feMerge>\n'
        f'    </filter>'
    )


def _soft_edge_filter_def(index: int, std: float = 3) -> str:
    """Soft-edge feathering filter (feGaussianBlur on SourceAlpha only)."""
    return (
        f'    <filter id="soft-edge-{index:02d}" x="-20%" y="-20%" '
        f'width="140%" height="150%">\n'
        f'      <feGaussianBlur in="SourceAlpha" stdDeviation="{std}"/>\n'
        f'    </filter>'
    )


def _glow_filter_def(
    index: int, color: str = "", opacity: float = 0.5, std: float = 4,
) -> str:
    """Glow filter: blur(SourceAlpha) + flood + composite + merge."""
    flood_color = color or "#000000"
    return (
        f'    <filter id="glow-{index:02d}" x="-20%" y="-20%" '
        f'width="140%" height="150%">\n'
        f'      <feGaussianBlur in="SourceAlpha" stdDeviation="{std}" result="blur"/>\n'
        f'      <feFlood flood-color="{flood_color}" flood-opacity="{opacity}" '
        f'result="glowColor"/>\n'
        f'      <feComposite in="glowColor" in2="blur" '
        f'operator="in" result="glow"/>\n'
        f'      <feMerge>\n'
        f'        <feMergeNode in="glow"/>\n'
        f'        <feMergeNode in="SourceGraphic"/>\n'
        f'      </feMerge>\n'
        f'    </filter>'
    )


def _render_executive_summary(
    index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int
) -> str:
    """3-card grid with colored top stripe + numbered halo + body + chip.

    Used when the body is 3-6 short bullet items — turns a generic bullet
    list into a McKinsey-style executive-summary page.
    """
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    title = xml_escape(heading)
    fsize_title = _title_font_size(heading)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=0.10)

    raw = [line.strip() for line in body.split("\n") if line.strip()]
    bullets = [line[2:].strip() for line in raw if line.startswith("- ")][:3]
    while len(bullets) < 3:
        bullets.append("")

    # Per-card accent rotation: pick three palette swatches so the deck
    # doesn't look like a solid wall of accent color.
    def _hex_to_rgb(hexc: str) -> tuple[int, int, int]:
        h_ = hexc.lstrip("#")
        return tuple(int(h_[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore

    def _shift(hexc: str, delta: int) -> str:
        r, g, b = _hex_to_rgb(hexc)
        r = max(0, min(255, r + delta))
        g = max(0, min(255, g + delta))
        b = max(0, min(255, b + delta))
        return f"#{r:02X}{g:02X}{b:02X}"

    accent = p["accent"]
    accent_alt1 = _shift(accent, -40)
    accent_alt2 = _shift(accent, +50)
    card_accents = [accent, accent_alt1, accent_alt2]

    gutter = t["margin"]["tight"] * 2
    card_w = (w - m * 2 - 2 * gutter) // 3
    card_h = int(h * 0.53)
    card_y = m + t["type"]["h1"] + t["margin"]["tight"] * 3
    card_rx = t["radius"]["card"]
    parts: list[str] = []
    inner_w = card_w - t["margin"]["page"]

    card_text_avail = card_h - t["type"]["h1"] * 2 - t["margin"]["tight"] * 2
    body_font, line_dy = _auto_body_font(
        bullets, inner_w, card_text_avail,
        max_size=t["type"]["body"] - 4, floor_size=t["type"]["caption"], gap=t["margin"]["tight"] - 4,
    )

    for i in range(3):
        cx = m + i * (card_w + gutter)
        ca = card_accents[i]
        # Card body with shadow
        parts.append(
            f'    <g filter="url(#card-shadow-{index:02d})">\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" '
            f'height="{card_h}" rx="{card_rx}" fill="{p["surface"]}"/>\n'
            f'    </g>'
        )
        # Top accent stripe
        parts.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" '
            f'height="6" fill="{ca}"/>'
        )
        # Numbered halo (filled circle with the index)
        halo_cx = cx + t["margin"]["page"]
        halo_cy = card_y + t["type"]["h1"] + t["margin"]["tight"] * 2
        parts.append(
            f'    <circle cx="{halo_cx}" cy="{halo_cy}" r="{t["type"]["caption"] + t["margin"]["tight"]}" '
            f'fill="{ca}" fill-opacity="0.14"/>'
        )
        parts.append(
            f'    <text x="{halo_cx}" y="{halo_cy + t["margin"]["tight"]}" font-family="{font}" '
            f'font-size="{t["type"]["h2"]}" font-weight="700" fill="{ca}" '
            f'text-anchor="middle">{i + 1:02d}</text>'
        )
        # Body text wrapped
        text = bullets[i] if i < len(bullets) else ""
        if text:
            tspans, _vis = _wrap_to_tspans(
                text, cx + 24, body_font, inner_w,
                line_height=line_dy / body_font,
            )
            parts.append(
                f'    <text x="{cx + t["margin"]["tight"] * 2}" y="{card_y + t["type"]["h1"] * 2 + t["margin"]["tight"] * 2}" '
                f'font-family="{font}" font-size="{body_font}" '
                f'fill="{p["text"]}">{tspans}</text>'
            )
        # Pill chip at the bottom
        chip_label = f"POINT {i + 1:02d}"
        chip_w = t["margin"]["page"] * 3
        chip_x = cx + (card_w - chip_w) // 2
        chip_y = card_y + card_h - t["margin"]["tight"] * 3
        parts.append(
            f'    <rect x="{chip_x}" y="{chip_y}" width="{chip_w}" '
            f'height="{t["margin"]["tight"] + 4}" rx="{t["radius"]["pill"]}" fill="{ca}" fill-opacity="0.14"/>'
        )
        parts.append(
            f'    <text x="{chip_x + chip_w // 2}" y="{chip_y + t["margin"]["tight"]}" '
            f'font-family="{font}" font-size="{t["type"]["overline"]}" font-weight="700" '
            f'fill="{ca}" text-anchor="middle" letter-spacing="2">'
            f'{chip_label}</text>'
        )

    cards_svg = "\n".join(parts)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" '
        f'height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-eyebrow-{index:02d}">\n'
        f'    <text x="{m}" y="{m + t["margin"]["tight"]}" font-family="{font}" font-size="{t["type"]["overline"]}" '
        f'font-weight="700" fill="{p["accent"]}" letter-spacing="4">'
        f'EXECUTIVE SUMMARY</text>\n'
        f'  </g>\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + t["type"]["caption"] + t["margin"]["tight"] * 2}" font-family="{font}" '
        f'font-size="{fsize_title}" font-weight="700" '
        f'fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="{m}" y="{m + t["type"]["caption"] + t["margin"]["tight"] * 3}" width="48" height="3" rx="1.5" '
        f'fill="{p["accent"]}" opacity="0.7"/>\n'
        f'  </g>\n'
        f'  <g id="content-cards-{index:02d}">\n'
        f'{cards_svg}\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_comparison(
    index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int
) -> str:
    """Two-card vs comparison with central VS divider."""
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    title = xml_escape(heading)
    fsize_title = min(_title_font_size(heading), t["type"]["h1"])
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=0.10)

    # Per-line `label | description` is the canonical comparison format.
    # Each non-empty line containing `|` becomes one side; we take the
    # first two such lines. Fallback: split body in half.
    pair_lines = [
        line.strip() for line in body.split("\n")
        if line.strip() and "|" in line
    ]

    def _clean(text: str) -> str:
        return re.sub(r"^[-•]\s*", "", text).strip()

    if len(pair_lines) >= 2:
        a_label, a_body = [_clean(s) for s in pair_lines[0].split("|", 1)]
        b_label, b_body = [_clean(s) for s in pair_lines[1].split("|", 1)]
    elif len(pair_lines) == 1 and re.search(r"\bvs\.?\b", body, re.IGNORECASE):
        a_part, b_part = re.split(r"\bvs\.?\b", body, maxsplit=1, flags=re.IGNORECASE)
        a_label, a_body = _clean(a_part), ""
        b_label, b_body = _clean(b_part), ""
    elif "|" in body:
        a_part, b_part = body.split("|", 1)
        a_label, a_body = _clean(a_part), ""
        b_label, b_body = _clean(b_part), ""
    else:
        mid = len(body) // 2
        a_label, a_body = _clean(body[:mid]), ""
        b_label, b_body = _clean(body[mid:]), ""
    if not a_label:
        a_label = "Option A"
    if not b_label:
        b_label = "Option B"

    gutter = t["margin"]["page"]
    col_w = (w - m * 2 - gutter) // 2
    col_y = m + t["type"]["h1"] + t["margin"]["tight"] * 2
    col_h = h - col_y - t["margin"]["page"]
    a_x = m
    b_x = a_x + col_w + gutter
    body_font = t["type"]["body"] - 4
    line_dy = int(body_font * 1.45)
    inner_w = col_w - t["margin"]["page"]
    col_rx = t["radius"]["card"]

    a_tspans, _ = _wrap_to_tspans(
        a_body or a_label, a_x + t["margin"]["tight"], body_font, inner_w,
        line_height=line_dy / body_font,
    )
    b_tspans, _ = _wrap_to_tspans(
        b_body or b_label, b_x + t["margin"]["tight"], body_font, inner_w,
        line_height=line_dy / body_font,
    )
    vs_cx = a_x + col_w + gutter // 2
    vs_cy = col_y + col_h // 2

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index)}\n'
        f'    <linearGradient id="cmp-grad-{index:02d}" x1="0%" y1="0%" '
        f'x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["muted"]}" '
        f'stop-opacity="0.7"/>\n'
        f'    </linearGradient>\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" '
        f'height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 28}" font-family="{font}" '
        f'font-size="{fsize_title}" font-weight="700" '
        f'fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="{m}" y="{m + 40}" width="48" height="3" rx="1.5" '
        f'fill="{p["accent"]}" opacity="0.7"/>\n'
        f'  </g>\n'
        f'  <g id="content-side-a-{index:02d}">\n'
        f'    <g filter="url(#card-shadow-{index:02d})">\n'
        f'      <rect x="{a_x}" y="{col_y}" width="{col_w}" '
        f'height="{col_h}" rx="{col_rx}" fill="url(#cmp-grad-{index:02d})"/>\n'
        f'    </g>\n'
        f'    <rect x="{a_x}" y="{col_y}" width="{col_w}" height="6" '
        f'fill="{p["accent"]}"/>\n'
        f'    <text x="{a_x + 32}" y="{col_y + 60}" font-family="{font}" '
        f'font-size="14" font-weight="700" fill="{p["accent"]}" '
        f'letter-spacing="3">A</text>\n'
        f'    <text x="{a_x + 32}" y="{col_y + 100}" font-family="{font}" '
        f'font-size="22" font-weight="700" fill="{p["text"]}">'
        f'{xml_escape(a_label[:40])}</text>\n'
        f'    <text x="{a_x + 32}" y="{col_y + 160}" font-family="{font}" '
        f'font-size="{body_font}" fill="{p["body"]}">{a_tspans}</text>\n'
        f'  </g>\n'
        f'  <g id="content-vs-{index:02d}">\n'
        f'    <circle cx="{vs_cx}" cy="{vs_cy}" r="36" '
        f'fill="{p["accent"]}"/>\n'
        f'    <text x="{vs_cx}" y="{vs_cy + 8}" font-family="{font}" '
        f'font-size="22" font-weight="700" fill="{p["background"]}" '
        f'text-anchor="middle">VS</text>\n'
        f'  </g>\n'
        f'  <g id="content-side-b-{index:02d}">\n'
        f'    <g filter="url(#card-shadow-{index:02d})">\n'
        f'      <rect x="{b_x}" y="{col_y}" width="{col_w}" '
        f'height="{col_h}" rx="{col_rx}" fill="url(#cmp-grad-{index:02d})"/>\n'
        f'    </g>\n'
        f'    <rect x="{b_x}" y="{col_y}" width="{col_w}" height="6" '
        f'fill="{p["accent"]}"/>\n'
        f'    <text x="{b_x + 32}" y="{col_y + 60}" font-family="{font}" '
        f'font-size="14" font-weight="700" fill="{p["accent"]}" '
        f'letter-spacing="3">B</text>\n'
        f'    <text x="{b_x + 32}" y="{col_y + 100}" font-family="{font}" '
        f'font-size="22" font-weight="700" fill="{p["text"]}">'
        f'{xml_escape(b_label[:40])}</text>\n'
        f'    <text x="{b_x + 32}" y="{col_y + 160}" font-family="{font}" '
        f'font-size="{body_font}" fill="{p["body"]}">{b_tspans}</text>\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_quote_block(
    index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int
) -> str:
    """Big centered pull quote with attribution."""
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    title = xml_escape(heading)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=0.14)

    raw = [line.strip() for line in body.split("\n") if line.strip()]
    quote_text = ""
    attribution = ""
    for line in raw:
        if line.startswith("> "):
            quote_text += (" " if quote_text else "") + line[2:].strip()
        elif line.startswith(("— ", "-- ", "— ")):
            attribution = line.lstrip("-—— ").strip()
        elif not quote_text:
            quote_text = line.strip("\u201c\u201d\"'")
        else:
            attribution = attribution or line

    quote_text = quote_text or body.strip() or title
    body_font = t["type"]["hero"]
    line_dy = int(body_font * 1.5)
    max_w = int(w * 0.72)
    quote_x = w // 2
    tspans, vis = _wrap_to_tspans(
        quote_text, quote_x, body_font, max_w,
        line_height=line_dy / body_font,
    )
    block_h = vis * line_dy
    quote_y = (h - block_h) // 2 - 20

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" '
        f'height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-eyebrow-{index:02d}">\n'
        f'    <text x="{m}" y="{m + t["margin"]["tight"]}" font-family="{font}" '
        f'font-size="{t["type"]["overline"]}" font-weight="700" fill="{p["accent"]}" '
        f'letter-spacing="6">{xml_escape(heading[:40].upper())}</text>\n'
        f'  </g>\n'
        f'  <g id="content-quote-mark-{index:02d}">\n'
        f'    <text x="{quote_x}" y="{quote_y + 10}" font-family="Georgia, serif" '
        f'font-size="{t["type"]["hero"] * 3}" font-weight="700" fill="{p["accent"]}" '
        f'fill-opacity="0.18" text-anchor="middle">&#x201C;</text>\n'
        f'  </g>\n'
        f'  <g id="content-quote-{index:02d}">\n'
        f'    <text x="{quote_x}" y="{quote_y + body_font}" '
        f'font-family="{font}" font-size="{body_font}" font-weight="600" '
        f'fill="{p["text"]}" text-anchor="middle" '
        f'font-style="italic">{tspans}</text>\n'
        f'  </g>\n'
        f'  <g id="content-attribution-{index:02d}">\n'
        f'    <line x1="{quote_x - t["margin"]["tight"] * 2}" y1="{quote_y + block_h + t["margin"]["page"]}" '
        f'x2="{quote_x + t["margin"]["tight"] * 2}" y2="{quote_y + block_h + t["margin"]["page"]}" '
        f'stroke="{p["accent"]}" stroke-width="2"/>\n'
        f'    <text x="{quote_x}" y="{quote_y + block_h + t["margin"]["page"] + t["type"]["caption"] * 2}" '
        f'font-family="{font}" font-size="{t["type"]["caption"]}" fill="{p["body"]}" '
        f'text-anchor="middle">{xml_escape(attribution[:60])}</text>\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_process_flow(
    index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int
) -> str:
    """Horizontal step boxes connected by arrows. Up to 5 steps."""
    p = lock["palette"]
    font = lock["font_family"]
    title = xml_escape(heading)
    fsize_title = _title_font_size(heading)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=0.10)

    raw = [line.strip() for line in body.split("\n") if line.strip()]
    steps: list[str] = []
    for line in raw:
        # Unwrap bullets / numbered prefixes
        clean = re.sub(r"^[-•]\s*", "", line)
        clean = re.sub(r"^\d+[\.、)]\s*", "", clean)
        if "→" in clean:
            steps.extend(s.strip() for s in clean.split("→") if s.strip())
        elif "->" in clean:
            steps.extend(s.strip() for s in clean.split("->") if s.strip())
        else:
            steps.append(clean)
    steps = [s for s in steps if s][:5]
    if not steps:
        steps = [body.strip()[:30] or title]

    n = len(steps)
    t = _tokens(w, h)
    m = t["margin"]["content"]
    gutter = t["margin"]["tight"] * 2
    box_w = (w - m * 2 - (n - 1) * gutter) // n
    box_h = int(h * 0.31)
    box_y = (h - box_h) // 2 + t["margin"]["tight"] * 2
    body_font = t["type"]["caption"] + 6
    line_dy = int(body_font * 1.4)
    inner_w = box_w - t["margin"]["page"]
    box_rx = t["radius"]["card"]

    parts: list[str] = []
    for i, step in enumerate(steps):
        bx = m + i * (box_w + gutter)
        # Box
        parts.append(
            f'    <g filter="url(#card-shadow-{index:02d})">\n'
            f'      <rect x="{bx}" y="{box_y}" width="{box_w}" '
            f'height="{box_h}" rx="{box_rx}" fill="{p["surface"]}"/>\n'
            f'    </g>'
        )
        parts.append(
            f'    <rect x="{bx}" y="{box_y}" width="{box_w}" height="6" '
            f'fill="{p["accent"]}"/>'
        )
        # Step number badge
        parts.append(
            f'    <circle cx="{bx + box_w // 2}" cy="{box_y + t["type"]["h2"]}" r="{t["type"]["caption"] + t["margin"]["tight"]}" '
            f'fill="{p["accent"]}"/>'
        )
        parts.append(
            f'    <text x="{bx + box_w // 2}" y="{box_y + t["type"]["h2"] + t["margin"]["tight"]}" '
            f'font-family="{font}" font-size="{t["type"]["caption"] + t["margin"]["tight"]}" font-weight="700" '
            f'fill="{p["background"]}" text-anchor="middle">'
            f'{i + 1:02d}</text>'
        )
        # Step text
        tspans, _v = _wrap_to_tspans(
            step, bx + box_w // 2, body_font, inner_w,
            line_height=line_dy / body_font,
        )
        parts.append(
            f'    <text x="{bx + box_w // 2}" y="{box_y + t["type"]["h1"] + t["margin"]["tight"] * 2}" '
            f'font-family="{font}" font-size="{body_font}" '
            f'fill="{p["text"]}" text-anchor="middle">{tspans}</text>'
        )
        # Arrow to next step
        if i < n - 1:
            ax = bx + box_w + t["margin"]["tight"] // 2
            ay = box_y + box_h // 2
            parts.append(
                f'    <line x1="{ax}" y1="{ay}" x2="{ax + gutter - t["margin"]["tight"]}" '
                f'y2="{ay}" stroke="{p["accent"]}" stroke-width="3"/>'
            )
            parts.append(
                f'    <polygon points="{ax + gutter - t["margin"]["tight"]},{ay - 6} '
                f'{ax + gutter - 2},{ay} {ax + gutter - t["margin"]["tight"]},{ay + 6}" '
                f'fill="{p["accent"]}"/>'
            )

    steps_svg = "\n".join(parts)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" '
        f'height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-eyebrow-{index:02d}">\n'
        f'    <text x="{m}" y="{m + t["margin"]["tight"]}" font-family="{font}" font-size="{t["type"]["overline"]}" '
        f'font-weight="700" fill="{p["accent"]}" letter-spacing="4">'
        f'PROCESS &#x2192; {n} STEPS</text>\n'
        f'  </g>\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + t["type"]["caption"] + t["margin"]["tight"] * 2}" font-family="{font}" '
        f'font-size="{fsize_title}" font-weight="700" '
        f'fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="{m}" y="{m + t["type"]["caption"] + t["margin"]["tight"] * 3}" width="48" height="3" rx="1.5" '
        f'fill="{p["accent"]}" opacity="0.7"/>\n'
        f'  </g>\n'
        f'  <g id="content-flow-{index:02d}">\n'
        f'{steps_svg}\n'
        f'  </g>\n'
        f'</svg>'
    )
