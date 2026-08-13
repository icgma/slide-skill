"""Design spec, SVG generation, SVG QA, and finalization — slide-skill v2.0."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .project import load_project
from .svg_shared import (
    chrome_body,
    chrome_defs,
    decor_orbs,
    design_tokens,
    hex_shift,
    is_light,
    shadow_filter_def,
    svg_open,
    title_block,
    title_underline,
)
from .util import ensure_dir, xml_escape

from .text_wrap import _wrap_to_tspans, _estimate_text_bounds, _strip_inline_md, _char_width, _visual_wrap, _token_width, _is_cjk, _tokenize_for_wrap, fitted_tspans
from .theme_profiles import get_theme_profile
from .semantic_scenes import (
    SCENE_CLOSING,
    SCENE_MARKET_OPPORTUNITY,
    SCENE_METRIC_HIGHLIGHT,
    SCENE_PROBLEM,
    SCENE_ROADMAP,
    SCENE_SOLUTION,
    SCENE_TECHNOLOGY,
)
from .svg_qa import check_project_svg, check_svg_file, SvgIssue, write_svg_report
from .spec_builder import create_spec, generate_guide, _load_or_create_lock, _markdown_to_slides
from .layout_router import _select_layout, _distribute_layouts


import logging
from .domain_teaching import render_teaching_slide
from .domain_course import render_course_slide
from .domain_competition import render_competition_slide

# ---------------------------------------------------------------------------
# Local aliases — single source of truth is svg_shared
# ---------------------------------------------------------------------------

_tokens = design_tokens
_hex_shift = hex_shift
_shadow_filter_def = shadow_filter_def
_decor_orbs = decor_orbs
_title_underline = title_underline
_svg_open = svg_open


def _hex_rgb(hexc: str) -> tuple[int, int, int]:
    h_ = hexc.lstrip("#")
    return tuple(int(h_[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _relative_luminance(hexc: str) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (_hex_rgb(hexc))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast_ratio(fg: str, bg: str) -> float:
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _readable_on(fill: str, *, dark: str = "#0F172A", light: str = "#F8FAFC") -> str:
    """Pick a black/white-style text color that is readable on a solid fill."""
    return dark if _contrast_ratio(dark, fill) >= _contrast_ratio(light, fill) else light


def _contrast_safe_accent(color: str, background: str, fallback: str, *, minimum: float = 3.0) -> str:
    return color if _contrast_ratio(color, background) >= minimum else fallback


def _chrome(index: int, total: int, lock: dict, w: int, h: int) -> str:
    """Wrapper combining svg_shared chrome_defs + chrome_body."""
    defs = chrome_defs(index, lock, w, h)
    body = chrome_body(index, total, lock, w, h)
    return f'  <defs>\n{defs}\n  </defs>\n{body}'













# ---------------------------------------------------------------------------
# Tag/attribute rules — v2.0: permissive for visually rich SVG
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# Design spec and spec-lock
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# SVG generation guide (for AI Executor role)
# ---------------------------------------------------------------------------



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

    # Pre-compute intent-aware lock overrides per slide
    _intent_overrides = _compute_intent_overrides(plans, spec_lock)

    # Write design intent back to spec_lock so it persists for QA/export
    _write_intent_to_lock(plans, lock_path, spec_lock)

    for plan in plans:
        # Try domain-specific renderers in priority order
        svg = render_teaching_slide(plan, spec_lock, total)
        if svg is None:
            svg = render_course_slide(plan, spec_lock, total)
        if svg is None:
            svg = render_competition_slide(plan, spec_lock, total)

        if svg is None:
            # Fall back to intent-aware rendering
            svg = _render_with_intent(plan, spec_lock, total, _intent_overrides)

        path = out_dir / f"slide_{plan.index:02d}.svg"
        path.write_text(svg, encoding="utf-8")
        paths.append(path)

    return paths


# ---------------------------------------------------------------------------
# SVG QA — v2.0 permissive rules
# ---------------------------------------------------------------------------





def finalize_svg(project_path: Path | str, *, quality: bool = False) -> list[Path]:
    project = Path(project_path)
    ok, issues = check_project_svg(project, quality=quality)
    blocking = [
        issue for issue in issues
        if issue.level == "error" or (quality and issue.level == "warning")
    ]
    if not ok or blocking:
        details = "\n".join(f"{i.level}: {i.file}: {i.message}" for i in (blocking or issues))
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




# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------





def _strip_markdown(text: str) -> str:
    """Remove markdown formatting from text before SVG rendering."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # **bold** → bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)       # *italic* → italic
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # ## heading
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)    # - bullet
    return text.strip()














# ---------------------------------------------------------------------------
# SVG rendering — programmatic fallback used by generate_svg()
# ---------------------------------------------------------------------------

def _build_plan_for_layout(index: int, heading: str, body: str, layout: str):
    from .content_planner import SlidePlan, lines_to_items
    items, meta = lines_to_items(layout, body)
    plan = SlidePlan(index=index, layout=layout, title=heading, items=items)
    if meta:
        plan.meta = meta
    return plan


def _intent_decor_intensity(lock: dict, fallback: float) -> float:
    """Read per-slide decor intensity from intent overrides, or use fallback."""
    return lock.get("_intent", {}).get("decor_intensity", fallback)


def _write_intent_to_lock(plans: list, lock_path: Path, spec_lock: dict) -> None:
    """Write per-slide design intent back to spec_lock.json for persistence."""
    page_layouts = {}
    page_charts = {}
    for plan in plans:
        idx = plan.index
        page_layouts[str(idx)] = {
            "layout": plan.layout,
            "visual_strategy": getattr(plan, "visual_strategy", "") or "",
            "layout_pattern": getattr(plan, "layout_pattern", "") or "",
            "rhythm": getattr(plan, "rhythm", "") or "",
            "image_hint": getattr(plan, "image_hint", "") or "",
        }
        chart_type = getattr(plan, "chart_type", "") or ""
        if chart_type:
            page_charts[str(idx)] = chart_type
    spec_lock["page_layouts"] = page_layouts
    spec_lock["page_charts"] = page_charts
    lock_path.write_text(json.dumps(spec_lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Intent-aware rendering — bridges content_planner design intent → SVG output
# ---------------------------------------------------------------------------

# Rhythm → visual parameter mapping
_RHYTHM_PARAMS = {
    "anchor": {"decor_intensity": 0.22, "title_scale": 1.1, "spacing_mult": 1.3},
    "breathing": {"decor_intensity": 0.12, "title_scale": 1.0, "spacing_mult": 1.0},
    "dense": {"decor_intensity": 0.06, "title_scale": 0.9, "spacing_mult": 0.8},
}

# Bullet-list visual strategies → alternative render dispatch
_BULLET_VARIANTS = {
    "progressive-reveal": "bullet-list",
    "cards-3-up": "executive-summary",
    "stacked-rows": "bullet-list",
    "compact-grid": "bullet-list",
}


def _compute_intent_overrides(
    plans: list, lock: dict,
) -> dict[int, dict]:
    """Pre-compute per-slide rendering overrides from design intent fields.

    Returns a dict mapping slide index → override parameters that modify
    the lock/render behavior without changing render function signatures.
    """
    overrides: dict[int, dict] = {}
    for plan in plans:
        rhythm = getattr(plan, "rhythm", "") or "breathing"
        strategy = getattr(plan, "visual_strategy", "") or ""
        pattern = getattr(plan, "layout_pattern", "") or ""

        rparams = _RHYTHM_PARAMS.get(rhythm, _RHYTHM_PARAMS["breathing"])

        override = {
            "decor_intensity": rparams["decor_intensity"],
            "title_scale": rparams["title_scale"],
            "spacing_mult": rparams["spacing_mult"],
            "rhythm": rhythm,
            "visual_strategy": strategy,
            "layout_pattern": pattern,
        }

        # Bullet-list variant selection based on layout_pattern
        if plan.layout == "bullet-list" and pattern in _BULLET_VARIANTS:
            override["remap_layout"] = _BULLET_VARIANTS[pattern]

        # Metric-highlight: hero-stat strategy → larger first metric
        if strategy == "hero-stat" and plan.layout == "metric-highlight":
            override["hero_first_metric"] = True

        overrides[plan.index] = override
    return overrides


def _render_with_intent(
    plan, lock: dict, total: int, intent_overrides: dict[int, dict],
) -> str:
    """Render a slide using design-intent overrides from content_planner.

    This is the bridge between the planning layer (which computes visual
    strategy, rhythm, layout patterns) and the rendering layer (which
    generates SVG). It modifies the lock dict per-slide based on intent
    before dispatching to the existing render functions.
    """
    canvas = lock["canvas"]
    w = int(canvas["width"])
    h = int(canvas["height"])
    layout = plan.layout
    idx = plan.index

    # Build body text from plan items
    profiled_scenes = {SCENE_PROBLEM, SCENE_SOLUTION, SCENE_ROADMAP, SCENE_TECHNOLOGY}
    if plan.items and layout in profiled_scenes | {SCENE_MARKET_OPPORTUNITY}:
        body_lines = []
        for item in plan.items:
            primary = re.sub(r"\*\*", "", item.primary or "").strip()
            secondary = re.sub(r"\*\*", "", item.secondary or "").strip()
            body_lines.append(f"{primary}: {secondary}".strip(": "))
        body = "\n".join(body_lines)
    elif plan.items and layout == SCENE_METRIC_HIGHLIGHT:
        body_lines = []
        for item in plan.items:
            primary = re.sub(r"\*\*", "", item.primary or "").strip()
            secondary = re.sub(r"\*\*", "", item.secondary or "").strip()
            if secondary and re.search(r"[$¥€£]?\s*\d|[%％]|[万亿KMB]\b", secondary, re.IGNORECASE):
                body_lines.append(f"{secondary} {primary}".strip())
            else:
                body_lines.append(f"{primary} {secondary}".strip())
        body = "\n".join(body_lines)
    elif layout in {"cover", SCENE_CLOSING, "closing"}:
        body_lines = []
        for item in plan.items:
            line = re.sub(r"\*\*", "", f"{item.primary} {item.secondary}").strip()
            line = re.sub(r"^\s*[-*•]\s+", "", line)
            line = re.sub(r"^\s*>\s*", "", line)
            if line:
                body_lines.append(line)
        body = "\n".join(body_lines)
    else:
        # Default body assembly. Each item becomes one bullet line ("- ").
        # We MUST emit the "- " marker because downstream renderers that
        # this default branch feeds (notably _render_executive_summary via
        # the bullet-list → cards-3-up → executive-summary remap) re-parse
        # the body by looking for lines that start with "- ". Without the
        # marker, every bullet becomes an empty string and the slide
        # renders with placeholder chips ("POINT 01/02/03") and no text.
        # Tolerant renderers (_render_bullet_list, _render_default,
        # _render_process_flow) strip any list marker themselves, so the
        # explicit prefix is safe and idempotent for them.
        body = "\n".join(
            "- " + re.sub(r"\*\*", "", f"{item.primary} {item.secondary}").strip()
            for item in plan.items
        ).strip() if plan.items else ""

    # Get intent overrides for this slide
    ovr = intent_overrides.get(idx, {})

    # Create a per-slide lock copy with rhythm-aware palette adjustments
    intent_lock = dict(lock)
    p = dict(lock["palette"])

    # Rhythm-based accent saturation shift
    rhythm = ovr.get("rhythm", "breathing")
    if rhythm == "anchor":
        # Boost accent for emphasis slides
        p["accent"] = _hex_shift(p["accent"], 10)
    elif rhythm == "dense":
        # Mute accent for dense content slides
        p["accent"] = _hex_shift(p["accent"], -8)

    intent_lock["palette"] = p
    intent_lock["_intent"] = ovr

    # Layout remapping based on visual_strategy / layout_pattern
    remapped = ovr.get("remap_layout")
    if remapped and remapped != layout:
        layout = remapped

    # Dispatch to existing render functions with intent-modified lock
    dispatch = {
        "cover": _render_cover,
        SCENE_CLOSING: _render_closing,
        "section-divider": lambda i, h_, b, l, t, w_, h_p: _render_section_divider(i, h_, l, t, w_, h_p),
        "bullet-list": _render_bullet_list,
        SCENE_PROBLEM: _render_problem_scene,
        SCENE_SOLUTION: _render_solution_scene,
        SCENE_ROADMAP: _render_roadmap_scene,
        SCENE_TECHNOLOGY: _render_technology_scene,
        SCENE_MARKET_OPPORTUNITY: _render_market_opportunity,
        SCENE_METRIC_HIGHLIGHT: _render_metric_highlight,
        "two-column": _render_two_column,
        "comparison": _render_comparison,
        "executive-summary": _render_executive_summary,
        "quote-block": _render_quote_block,
        "process-flow": _render_process_flow,
        "table": _render_table,
        "default": _render_default,
    }
    fn = dispatch.get(layout, _render_default)
    return fn(idx, plan.title, body, intent_lock, total, w, h)


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

    v3_layouts = {
        "vocab-card", "dialogue", "sentence-example", "exercise",
        "learning-objectives", "key-concept", "case-study", "discussion",
        "team-grid", "metrics-dashboard", "timeline", "comparison-matrix"
    }
    if layout in v3_layouts:
        plan = _build_plan_for_layout(index, heading, body, layout)
        svg = render_teaching_slide(plan, lock, total)
        if svg is None:
            svg = render_course_slide(plan, lock, total)
        if svg is None:
            svg = render_competition_slide(plan, lock, total)
        if svg is not None:
            return svg
        logging.getLogger(__name__).warning(
            "v3 layout %r had no domain renderer accept it; falling back to _render_default",
            layout,
        )
        return _render_default(index, heading, body, lock, total, w, h)

    dispatch = {
        "cover": _render_cover,
        SCENE_CLOSING: _render_closing,
        "section-divider": lambda i, h_, b, l, t, w_, h_p: _render_section_divider(i, h_, l, t, w_, h_p),
        "bullet-list": _render_bullet_list,
        SCENE_PROBLEM: _render_problem_scene,
        SCENE_SOLUTION: _render_solution_scene,
        SCENE_ROADMAP: _render_roadmap_scene,
        SCENE_TECHNOLOGY: _render_technology_scene,
        SCENE_MARKET_OPPORTUNITY: _render_market_opportunity,
        SCENE_METRIC_HIGHLIGHT: _render_metric_highlight,
        "two-column": _render_two_column,
        "comparison": _render_comparison,
        "executive-summary": _render_executive_summary,
        "quote-block": _render_quote_block,
        "process-flow": _render_process_flow,
        "table": _render_table,
        "default": _render_default,
    }
    fn = dispatch.get(layout, _render_default)
    return fn(index, heading, body, lock, total, w, h)


def _title_font_size(heading: str) -> int:
    n = len(heading)
    if n <= 12:
        return 64
    if n <= 20:
        return 54
    if n <= 30:
        return 46
    return 38


def _auto_body_font(
    lines: list[str],
    max_width: int,
    avail_height: int,
    *,
    max_size: int = 28,
    floor_size: int = 18,
    line_height: float = 1.45,
    gap: int = 14,
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




def _render_section_divider(index: int, heading: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    title = xml_escape(heading)
    fsize = _title_font_size(heading) + 4
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.20))
    accent = p["accent"]
    accent_lighter = _hex_shift(accent, 40)
    
    cx, cy = w // 2, h // 2
    card_w = int(w * 0.68)
    card_h = 200
    card_x = cx - card_w // 2
    card_y = cy - card_h // 2
    card_rx = t["radius"]["card"] + 4

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="sect-title-grad-{index:02d}" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f'      <stop offset="0%" stop-color="{p["text"]}"/>\n'
        f'      <stop offset="100%" stop-color="{accent}"/>\n'
        f'    </linearGradient>\n'
        f'    <linearGradient id="sect-card-grad-{index:02d}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.85"/>\n'
        f'    </linearGradient>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        # Textured dot pattern
        f'  <g id="sect-grid-{index:02d}">\n'
        f'    <pattern id="sect-dots-{index:02d}" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">\n'
        f'      <circle cx="2" cy="2" r="1.2" fill="{accent}" fill-opacity="0.04"/>\n'
        f'    </pattern>\n'
        f'    <rect x="0" y="0" width="{w}" height="{h}" fill="url(#sect-dots-{index:02d})"/>\n'
        f'  </g>\n'
        # Concentric Orbital Rings behind card
        f'  <g id="decor-section-geom-{index:02d}" opacity="0.65">\n'
        f'    <circle cx="{cx}" cy="{cy}" r="220" stroke="{accent}" stroke-width="1.2" stroke-dasharray="6,6" fill="none" opacity="0.12"/>\n'
        f'    <circle cx="{cx}" cy="{cy}" r="160" stroke="{accent}" stroke-width="1" stroke-dasharray="3,3" fill="none" opacity="0.22"/>\n'
        f'    <circle cx="{cx}" cy="{cy}" r="100" stroke="{accent}" stroke-width="1.5" fill="none" opacity="0.08"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        # Floating Glassmorphic card
        f'  <g id="section-card-{index:02d}" filter="url(#card-shadow-{index:02d})">\n'
        f'    <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{card_rx}" fill="url(#sect-card-grad-{index:02d})" stroke="{accent}" stroke-opacity="0.18" stroke-width="1.5"/>\n'
        f'    <rect x="{card_x + 6}" y="{card_y + 6}" width="{card_w - 12}" height="{card_h - 12}" rx="{card_rx - 4}" fill="none" stroke="{accent}" stroke-opacity="0.10" stroke-width="1"/>\n'
        f'  </g>\n'
        # Glowing Category Badge on top of card
        f'  <g id="section-eyebrow-{index:02d}">\n'
        f'    <rect x="{cx - 70}" y="{card_y + 28}" width="140" height="26" rx="13" fill="{accent}" fill-opacity="0.12" stroke="{accent}" stroke-opacity="0.25" stroke-width="1.2"/>\n'
        f'    <text x="{cx}" y="{card_y + 45}" font-family="{font}" font-size="12" '
        f'font-weight="700" fill="{accent}" text-anchor="middle" letter-spacing="4">'
        f'CHAPTER {index:02d}</text>\n'
        f'  </g>\n'
        # High-contrast chapter title using linear gradient
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{cx}" y="{cy + 36}" font-family="{font}" font-size="{fsize}" '
        f'font-weight="700" fill="url(#sect-title-grad-{index:02d})" text-anchor="middle">{title}</text>\n'
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
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.12))
    light = is_light(lock)

    accent = p["accent"]
    accent_alts = [accent, _hex_shift(accent, -30), _hex_shift(accent, 40)]
    accent_text_fallback = p.get("secondary_accent", _hex_shift(accent, 40))
    card_stroke_opacity = 0.25 if light else 0.15
    card_stroke_width = 1.5 if light else 1

    bullet_parts: list[str] = []
    title_bottom_y = m + 28 + 12  # after title text
    row_y = title_bottom_y + 28  # space for underline + gap
    n = len(lines) if lines else 1
    avail = h - row_y - 60

    clean_lines = [
        (line[2:].strip() if line.startswith("- ") else line) for line in lines
    ]
    # Text starts after the numbered halo region
    halo_region_w = 64
    max_text_w = w - m * 2 - halo_region_w - 40
    body_font, line_dy = _auto_body_font(
        clean_lines, max_text_w, avail,
        max_size=t["type"]["body"], floor_size=t["type"]["caption"], gap=10,
    )

    base_row_h = max(54, min(72, (avail - (n - 1) * 12) // max(n, 1)))
    card_rx = t["radius"]["card"]
    for i, line in enumerate(lines):
        is_bullet = line.startswith("- ")
        text_content = line[2:].strip() if is_bullet else line
        text_x = m + halo_region_w + 24
        cur_max_w = w - m * 2 - halo_region_w - 56
        
        # Clean markdown bold markers and split for keyword extraction
        clean_line = text_content.replace("**", "").replace("__", "")
        sep_match = re.search(r'\s*([—\-\–\—:：]+)\s*', clean_line)
        
        tspans, vis_lines = _wrap_to_tspans(
            clean_line, text_x, body_font, cur_max_w, line_height=line_dy / body_font
        )
        
        ca = accent_alts[i % len(accent_alts)]
        readable_ca = _contrast_safe_accent(ca, p["surface"], accent_text_fallback, minimum=4.5)
        
        if sep_match:
            sep = sep_match.group(0)
            kw_part = clean_line.split(sep, 1)[0]
            if 0 < len(kw_part) < 18:
                first_tspan_pat = re.compile(r"(<tspan[^>]*>)(.*?)(</tspan>)")
                m_tspan = first_tspan_pat.search(tspans)
                if m_tspan:
                    tspan_start, tspan_inner, tspan_end = m_tspan.groups()
                    kw_esc = xml_escape(kw_part)
                    sep_esc = xml_escape(sep)
                    if sep_esc in tspan_inner:
                        kw_seg, rest_seg = tspan_inner.split(sep_esc, 1)
                        styled_inner = (
                            f'<tspan font-weight="700" fill="{readable_ca}">{kw_seg}</tspan>'
                            f'<tspan fill="{p["muted"]}" opacity="0.6">{sep_esc}</tspan>'
                            f'{rest_seg}'
                        )
                        tspans = tspans.replace(tspan_inner, styled_inner, 1)

        row_h = max(base_row_h, vis_lines * line_dy + 24)

        bullet_parts.append(
            f'    <rect x="{m}" y="{row_y}" width="{w - m * 2}" height="{row_h}" rx="{card_rx}" '
            f'fill="url(#row-grad-{index:02d})" stroke="{ca}" stroke-opacity="{card_stroke_opacity}" stroke-width="{card_stroke_width}" filter="url(#card-shadow-{index:02d})"/>'
        )
        # Left accent stripe on card
        bullet_parts.append(
            f'    <rect x="{m}" y="{row_y}" width="4" height="{row_h}" '
            f'rx="2" fill="{ca}" opacity="0.8"/>'
        )

        # Dual-Ring Glowing Badge
        halo_cx = m + 32
        halo_cy = row_y + row_h // 2
        bullet_parts.append(
            f'    <circle cx="{halo_cx}" cy="{halo_cy}" r="22" '
            f'fill="none" stroke="{ca}" stroke-width="1.5" stroke-opacity="0.25"/>'
        )
        bullet_parts.append(
            f'    <circle cx="{halo_cx}" cy="{halo_cy}" r="15" '
            f'fill="{ca}" fill-opacity="0.12"/>'
        )
        bullet_parts.append(
            f'    <text x="{halo_cx}" y="{halo_cy + 5}" font-family="{font}" '
            f'font-size="{t["type"]["overline"]}" font-weight="700" fill="{readable_ca}" '
            f'text-anchor="middle">{i + 1:02d}</text>'
        )

        # Body text position
        text_block_h = vis_lines * line_dy
        text_y = row_y + (row_h - text_block_h) // 2 + body_font - 2
        
        # Tiny bullet marker to satisfy visual tests and represent bullet list shape
        bullet_parts.append(
            f'    <circle cx="{text_x - 14}" cy="{text_y - 6}" r="4" '
            f'fill="{ca}" opacity="0.85"/>'
        )
        
        # Body text
        bullet_parts.append(
            f'    <text x="{text_x}" y="{text_y}" font-family="{font}" '
            f'font-size="{body_font}" fill="{p["text"]}">{tspans}</text>'
        )
        
        # Chevron right-arrow details on card
        chevron_cx = w - m - 20
        chevron_cy = row_y + row_h // 2
        bullet_parts.append(
            f'    <path d="M {chevron_cx - 4} {chevron_cy - 6} L {chevron_cx + 2} {chevron_cy} L {chevron_cx - 4} {chevron_cy + 6}" '
            f'fill="none" stroke="{ca}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.5"/>'
        )
        
        row_y += row_h + 12

    bullets_svg = "\n".join(bullet_parts)
    bar_w = 48
    underline = _title_underline(m, title_bottom_y, accent)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="row-grad-{index:02d}" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.8"/>\n'
        f'    </linearGradient>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'  <g id="decor-bar-{index:02d}">\n'
        f'    <rect x="{w - bar_w}" y="0" width="{bar_w}" height="{h}" fill="{accent}" opacity="0.04"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 28}" font-family="{font}" font-size="{fsize_title}" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'{underline}\n'
        f'  </g>\n'
        f'  <g id="content-body-{index:02d}">\n'
        f'{bullets_svg}\n'
        f'  </g>\n'
        f'</svg>'
    )


def _parse_scene_pairs(body: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ":" in line:
            primary, secondary = [part.strip() for part in line.split(":", 1)]
        else:
            primary, secondary = line, ""
        pairs.append((primary, secondary))
    return pairs


def _render_profiled_list_scene(
    scene: str,
    index: int,
    heading: str,
    body: str,
    lock: dict,
    total: int,
    w: int,
    h: int,
) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    accent = p["accent"]
    profile = get_theme_profile(lock)
    scene_profile = getattr(profile, scene)
    items = _parse_scene_pairs(body)[:4]
    if not items:
        return _render_default(index, heading, body, lock, total, w, h)

    is_hard = scene_profile.card_shape == "hard-block"
    is_editorial = "editorial" in scene_profile.variant or "annotated" in scene_profile.variant
    is_glass = scene_profile.card_shape == "glass-panel"
    card_rx = profile.card_radius if is_hard else t["radius"]["card"]
    stroke_w = profile.stroke_width
    shadow = "" if profile.shadow_style == "none" else f' filter="url(#card-shadow-{index:02d})"'
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.12))
    title = xml_escape(heading)
    title_size = min(_title_font_size(heading), 54)
    underline = _title_underline(m, 76, accent)

    tone = {
        "problem": ("FRICTION", "!", "Risk signal", accent),
        "solution": ("RESPONSE", "✓", "Capability", accent),
        "technology": ("SYSTEM", "◇", "Layer", accent),
    }.get(scene, ("SCENE", "•", "Signal", accent))
    eyebrow, glyph, caption, fallback_color = tone
    small_accent_fallback = p.get("secondary_accent", _hex_shift(accent, 40))
    eyebrow_color = _contrast_safe_accent(accent, p["surface"], small_accent_fallback, minimum=4.5)

    parts: list[str] = []
    if is_editorial:
        y = 146
        parts.append(
            f'    <text x="{m}" y="{y}" font-family="{font}" font-size="14" font-weight="700" fill="{eyebrow_color}" letter-spacing="4">{eyebrow}</text>'
        )
        y += 34
        for i, (primary, secondary) in enumerate(items):
            row_h = 78
            y0 = y + i * (row_h + 14)
            shade = _hex_shift(accent, i * 16 - 16)
            parts.append(
                f'    <line x1="{m}" y1="{y0}" x2="{w - m}" y2="{y0}" stroke="{shade}" stroke-width="{stroke_w}" opacity="0.75"/>'
            )
            parts.append(
                f'    <text x="{m}" y="{y0 + 34}" font-family="{font}" font-size="24" font-weight="700" fill="{p["text"]}">{xml_escape(primary)}</text>'
            )
            if secondary:
                parts.append(
                    f'    <text x="{w - m}" y="{y0 + 34}" font-family="{font}" font-size="18" font-weight="700" fill="{shade}" text-anchor="end">{xml_escape(secondary)}</text>'
                )
            parts.append(
                f'    <text x="{m}" y="{y0 + 60}" font-family="{font}" font-size="14" fill="{p["body"]}" opacity="0.75">{caption} {i + 1:02d}</text>'
            )
    else:
        cols = 2 if len(items) > 2 else len(items)
        rows = (len(items) + cols - 1) // max(cols, 1)
        grid_x = m
        grid_y = 142
        gutter = 26
        card_w = (w - m * 2 - (cols - 1) * gutter) // max(cols, 1)
        card_h = (390 - (rows - 1) * gutter) // max(rows, 1)
        if scene_profile.hero_position == "left" and len(items) >= 3:
            cols = 1
            card_w = int(w * 0.44)
            card_h = 96
            grid_x = int(w * 0.50)
            grid_y = 150
            hero_w = int(w * 0.40)
            hero_h = 340
            hero_x = m
            hero_y = 150
            parts.append(
                f'    <rect x="{hero_x}" y="{hero_y}" width="{hero_w}" height="{hero_h}" rx="{card_rx}" fill="{p["surface"]}" stroke="{accent}" stroke-opacity="{0.7 if is_hard else 0.2}" stroke-width="{stroke_w}"{shadow}/>'
            )
            parts.append(
                f'    <text x="{hero_x + 34}" y="{hero_y + 82}" font-family="{font}" font-size="14" font-weight="700" fill="{eyebrow_color}" letter-spacing="4">{eyebrow}</text>'
            )
            parts.append(
                f'    <text x="{hero_x + 34}" y="{hero_y + 172}" font-family="{font}" font-size="{58 if is_hard else 52}" font-weight="800" fill="{p["text"]}">{xml_escape(heading)}</text>'
            )
            parts.append(
                f'    <text x="{hero_x + 34}" y="{hero_y + hero_h - 44}" font-family="{font}" font-size="18" fill="{p["body"]}" opacity="0.8">{len(items)} mapped signals</text>'
            )

        for i, (primary, secondary) in enumerate(items):
            if scene_profile.hero_position == "left" and len(items) >= 3:
                x = grid_x
                y = grid_y + i * (card_h + 18)
            else:
                col = i % cols
                row = i // cols
                x = grid_x + col * (card_w + gutter)
                y = grid_y + row * (card_h + gutter)
            shade = _hex_shift(fallback_color, i * 18 - 18)
            label_color = _contrast_safe_accent(shade, p["surface"], small_accent_fallback, minimum=4.5)
            parts.append(
                f'    <rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="{card_rx}" fill="{p["surface"]}" fill-opacity="{0.88 if is_glass else 1}" stroke="{shade}" stroke-opacity="{0.72 if is_hard else 0.24}" stroke-width="{stroke_w}"{shadow}/>'
            )
            parts.append(
                f'    <text x="{x + 20}" y="{y + 34}" font-family="{font}" font-size="16" font-weight="800" fill="{label_color}">{glyph} {i + 1:02d}</text>'
            )
            text_w = card_w - 42
            tspans, _, text_font, _ = fitted_tspans(
                primary, x + 20, text_w, card_h - 58,
                max_font_size=22 if is_hard else 20,
                min_font_size=12,
                line_height=1.18,
            )
            parts.append(
                f'    <text x="{x + 20}" y="{y + 72}" font-family="{font}" font-size="{text_font}" font-weight="700" fill="{p["text"]}" data-fit-box="{x + 20},{y + 48},{text_w},{card_h - 58}" data-line-height="1.18">{tspans}</text>'
            )
            if secondary:
                parts.append(
                    f'    <text x="{x + card_w - 20}" y="{y + card_h - 22}" font-family="{font}" font-size="14" font-weight="700" fill="{p["body"]}" text-anchor="end">{xml_escape(secondary)}</text>'
                )

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="64" font-family="{font}" font-size="{title_size}" font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'{underline}\n'
        f'  </g>\n'
        f'  <g id="content-{scene}-{index:02d}" data-theme-profile="{profile.name}" data-scene-variant="{scene_profile.variant}">\n'
        + "\n".join(parts) +
        f'\n  </g>\n'
        f'</svg>'
    )


def _render_problem_scene(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    return _render_profiled_list_scene("problem", index, heading, body, lock, total, w, h)


def _render_solution_scene(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    return _render_profiled_list_scene("solution", index, heading, body, lock, total, w, h)


def _render_technology_scene(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    return _render_profiled_list_scene("technology", index, heading, body, lock, total, w, h)


def _render_roadmap_scene(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    accent = p["accent"]
    profile = get_theme_profile(lock)
    scene_profile = profile.roadmap
    items = _parse_scene_pairs(body)[:5]
    if not items:
        return _render_default(index, heading, body, lock, total, w, h)
    is_hard = scene_profile.card_shape == "hard-block"
    is_editorial = "editorial" in scene_profile.variant
    card_rx = profile.card_radius if is_hard else t["radius"]["card"]
    stroke_w = profile.stroke_width
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.14))
    title = xml_escape(heading)
    title_size = min(_title_font_size(heading), 54)
    underline = _title_underline(m, 76, accent)
    accent_text_fallback = p.get("secondary_accent", _hex_shift(accent, 40))
    parts: list[str] = []

    if is_editorial:
        y = 146
        for i, (date, label) in enumerate(items):
            y0 = y + i * 78
            shade = _hex_shift(accent, i * 15 - 15)
            text_shade = _contrast_safe_accent(shade, p["background"], accent_text_fallback, minimum=4.5)
            parts.append(f'    <line x1="{m}" y1="{y0}" x2="{w - m}" y2="{y0}" stroke="{shade}" stroke-width="{stroke_w}" opacity="0.8"/>')
            parts.append(f'    <text x="{m}" y="{y0 + 34}" font-family="{font}" font-size="24" font-weight="800" fill="{text_shade}">{xml_escape(date)}</text>')
            parts.append(f'    <text x="{m + 180}" y="{y0 + 34}" font-family="{font}" font-size="22" font-weight="700" fill="{p["text"]}">{xml_escape(label)}</text>')
    else:
        rail_y = 330
        card_w = 224
        left = m + card_w // 2
        right = w - m - card_w // 2
        parts.append(f'    <line x1="{left}" y1="{rail_y}" x2="{right}" y2="{rail_y}" stroke="{accent}" stroke-width="{4 if is_hard else 2}" opacity="0.65"/>')
        for i, (date, label) in enumerate(items):
            x = left + int((right - left) * i / max(1, len(items) - 1))
            shade = _hex_shift(accent, i * 16 - 16)
            text_shade = _contrast_safe_accent(shade, p["surface"], accent_text_fallback, minimum=4.5)
            card_h = 118
            y = rail_y - card_h - 44 if i % 2 == 0 else rail_y + 44
            parts.append(f'    <circle cx="{x}" cy="{rail_y}" r="{13 if is_hard else 10}" fill="{shade}" stroke="{p["background"]}" stroke-width="3"/>')
            parts.append(f'    <rect x="{x - card_w // 2}" y="{y}" width="{card_w}" height="{card_h}" rx="{card_rx}" fill="{p["surface"]}" stroke="{shade}" stroke-opacity="{0.75 if is_hard else 0.26}" stroke-width="{stroke_w}"/>')
            parts.append(f'    <text x="{x}" y="{y + 38}" font-family="{font}" font-size="18" font-weight="800" fill="{text_shade}" text-anchor="middle">{xml_escape(date)}</text>')
            tspans, _, label_font, _ = fitted_tspans(label, x, card_w - 28, 50, max_font_size=16, min_font_size=11, line_height=1.16)
            parts.append(f'    <text x="{x}" y="{y + 72}" font-family="{font}" font-size="{label_font}" font-weight="700" fill="{p["text"]}" text-anchor="middle" data-fit-box="{x - (card_w - 28)//2},{y + 54},{card_w - 28},56" data-line-height="1.16">{tspans}</text>')

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="64" font-family="{font}" font-size="{title_size}" font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'{underline}\n'
        f'  </g>\n'
        f'  <g id="content-roadmap-{index:02d}" data-theme-profile="{profile.name}" data-scene-variant="{scene_profile.variant}">\n'
        + "\n".join(parts) +
        f'\n  </g>\n'
        f'</svg>'
    )


def _render_market_opportunity(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    accent = p["accent"]
    profile = get_theme_profile(lock)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.14))
    title = xml_escape(heading)
    fsize_title = min(_title_font_size(heading), 54)

    items: list[tuple[str, str]] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if ":" in line:
            label, value = [part.strip() for part in line.split(":", 1)]
        else:
            m_value = re.search(r"((?:[$¥€£]\s*)?\d[\d,.]*\s*(?:[%％]|[万亿KMB]\b|x\b)?.*)$", line, re.IGNORECASE)
            if m_value:
                label = line[:m_value.start()].strip(" -–—:")
                value = m_value.group(1).strip()
            else:
                label, value = line, ""
        if label or value:
            items.append((label, value))

    if not items:
        return _render_metric_highlight(index, heading, body, lock, total, w, h)

    tam_label, tam_value = items[0]
    segments = items[1:4]
    if not segments:
        return _render_metric_highlight(index, heading, body, lock, total, w, h)

    hero_x = m
    hero_y = 154
    hero_w = int(w * 0.42)
    hero_h = 360
    seg_x = hero_x + hero_w + 48
    seg_y = hero_y + 12
    seg_w = w - seg_x - m
    seg_h = hero_h - 24

    profile = get_theme_profile(lock)
    is_editorial = profile.market.variant == "editorial-tam-strip"
    is_hard = profile.market.card_shape == "hard-block"

    if is_editorial:
        hero_w = w - m * 2
        hero_h = 150
        hero_x = m
        hero_y = 136
        seg_x = m
        seg_y = hero_y + hero_h + 34
        seg_w = w - m * 2
        seg_h = 220
    elif profile.market.variant == "brutalist-block-bars":
        hero_w = int(w * 0.46)
        hero_h = 330
        seg_x = hero_x + hero_w + 34
        seg_w = w - seg_x - m

    card_rx = profile.card_radius if is_hard else t["radius"]["card"]
    stroke_w = profile.stroke_width
    shadow = "" if profile.shadow_style == "none" else f' filter="url(#card-shadow-{index:02d})"'

    value_tspans, _, value_font, _ = fitted_tspans(
        tam_value,
        hero_x + 34,
        hero_w - 68,
        150,
        max_font_size=64,
        min_font_size=30,
        line_height=1.08,
    )
    label_tspans, _, label_font, _ = fitted_tspans(
        tam_label,
        hero_x + 34,
        hero_w - 68,
        64,
        max_font_size=24,
        min_font_size=14,
        line_height=1.2,
    )

    parts = [
        f'    <rect x="{hero_x}" y="{hero_y}" width="{hero_w}" height="{hero_h}" rx="{card_rx}" fill="{p["surface"]}" stroke="{accent}" stroke-opacity="{0.75 if is_hard else 0.22}" stroke-width="{stroke_w}"{shadow}/>',
        f'    <rect x="{hero_x}" y="{hero_y}" width="{hero_w if is_editorial else 8}" height="{5 if is_editorial else hero_h}" fill="{accent}" opacity="0.9"/>',
        f'    <text x="{hero_x + 34}" y="{hero_y + 72}" font-family="{font}" font-size="{label_font}" font-weight="700" fill="{p["body"]}" letter-spacing="1" data-fit-box="{hero_x + 34},{hero_y + 48},{hero_w - 68},64" data-line-height="1.2">{label_tspans}</text>',
        f'    <text x="{hero_x + 34}" y="{hero_y + 164}" font-family="{font}" font-size="{value_font}" font-weight="800" fill="{accent}" data-fit-box="{hero_x + 34},{hero_y + 98},{hero_w - 68},156" data-line-height="1.08">{value_tspans}</text>',
    ]

    if not is_editorial:
        parts.append(
            f'    <text x="{hero_x + 34}" y="{hero_y + hero_h - 42}" font-family="{font}" font-size="18" fill="{p["body"]}" opacity="0.78">Primary demand signal</text>'
        )

    max_pct = 1.0
    parsed_segments: list[tuple[str, str, float]] = []
    for label, value in segments:
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*[%％]", value)
        pct = float(pct_match.group(1)) if pct_match else 0.0
        max_pct = max(max_pct, pct)
        parsed_segments.append((label, value, pct))

    row_gap = 22 if is_editorial else 28
    row_h = (seg_h - row_gap * (len(parsed_segments) - 1)) // max(1, len(parsed_segments))
    for i, (label, value, pct) in enumerate(parsed_segments):
        y = seg_y + i * (row_h + row_gap)
        bar_w = int((seg_w - 170) * (pct / max_pct)) if max_pct else 0
        shade = _hex_shift(accent, i * 20 - 20)
        if is_hard:
            parts.append(
                f'    <rect x="{seg_x}" y="{y}" width="{seg_w}" height="{row_h}" rx="2" fill="{p["background"]}" stroke="{shade}" stroke-width="3"/>'
            )
        else:
            parts.append(
                f'    <rect x="{seg_x}" y="{y}" width="{seg_w}" height="{row_h}" rx="{card_rx}" fill="{p["surface"]}" stroke="{shade}" stroke-opacity="0.18" stroke-width="1.2"{shadow}/>'
            )
        parts.append(
            f'    <text x="{seg_x + 24}" y="{y + row_h // 2 + 8}" font-family="{font}" font-size="{22 if is_hard else 20}" font-weight="700" fill="{p["text"]}">{xml_escape(label)}</text>'
        )
        parts.append(
            f'    <text x="{seg_x + seg_w - 28}" y="{y + row_h // 2 + 9}" font-family="{font}" font-size="{28 if is_hard else 26}" font-weight="800" fill="{shade}" text-anchor="end">{xml_escape(value)}</text>'
        )
        bar_y = y + row_h - 16
        parts.append(
            f'    <rect x="{seg_x + 24}" y="{bar_y}" width="{seg_w - 170}" height="5" rx="2.5" fill="{p["muted"]}" opacity="0.16"/>'
        )
        parts.append(
            f'    <rect x="{seg_x + 24}" y="{bar_y}" width="{bar_w}" height="5" rx="2.5" fill="{shade}" opacity="0.9"/>'
        )

    underline = _title_underline(m, 76, accent)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="64" font-family="{font}" font-size="{fsize_title}" font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'{underline}\n'
        f'  </g>\n'
        f'  <g id="content-market-{index:02d}">\n'
        + "\n".join(parts) +
        f'\n  </g>\n'
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
    light = is_light(lock)

    accent = p["accent"]
    accent_alts = [accent, _hex_shift(accent, -35), _hex_shift(accent, 45), _hex_shift(accent, -15)]
    card_stroke_opacity = 0.20 if light else 0.12

    body = _strip_inline_md(body)
    _metric_line_pat = re.compile(r"^([\$¥€£]?\s*\d[\d,.]*\S*(?:\s+\S+){0,3})\s+(.+)$")
    _label_value_pat = re.compile(r"^(.+?)\s+((?:[\$¥€£]?\s*)?\d[\d,.]*\S*(?:\s+\S+){0,3})$")
    _metric_lines = [re.sub(r"^[-*]\s+", "", ln.strip()) for ln in body.split("\n") if ln.strip()]
    _pairs = []
    for ln in _metric_lines:
        _m = _metric_line_pat.match(ln)
        if _m:
            _pairs.append((_m.group(1), _m.group(2)))
            continue
        _lv = _label_value_pat.match(ln)
        _pairs.append((_lv.group(2), _lv.group(1)) if _lv else (ln, ""))
    metrics = [p[0] for p in _pairs if p[1]][:4]
    labels = [p[1] for p in _pairs if p[1]][:4]

    if not metrics:
        return _render_default(index, heading, body, lock, total, w, h)

    count = min(len(metrics), 4)
    gutter = t["margin"]["tight"]
    profile = get_theme_profile(lock)
    editorial_grid = profile.market.variant == "editorial-tam-strip" and count >= 3
    brutal_stagger = profile.market.variant == "brutalist-block-bars" and count >= 3
    if editorial_grid:
        cols = 2
        card_w = (w - m * 2 - gutter) // cols
        card_h = 156
    else:
        card_w = (w - m * 2 - (count - 1) * gutter) // count
        card_h = int(h * 0.47)
    base_card_y = m + t["type"]["h1"] + t["margin"]["tight"] * 2
    card_rx = t["radius"]["card"]
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.12))

    card_parts: list[str] = []
    defs_parts: list[str] = []
    
    for i in range(count):
        if editorial_grid:
            col = i % 2
            row = i // 2
            cx = m + col * (card_w + gutter)
            card_y = base_card_y + row * (card_h + gutter)
        else:
            cx = m + i * (card_w + gutter)
            card_y = base_card_y + (36 if brutal_stagger and i % 2 else 0)
        mid_x = cx + card_w // 2
        ca = accent_alts[i % len(accent_alts)]
        badge_ca = _contrast_safe_accent(
            ca,
            p["background"],
            p.get("secondary_accent", _hex_shift(accent, 40)),
            minimum=4.5,
        )
        local_rx = profile.card_radius if brutal_stagger else card_rx
        
        # Text gradient for the numeric value
        defs_parts.append(
            f'    <linearGradient id="metric-num-grad-{index:02d}-{i}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["text"]}"/>\n'
            f'      <stop offset="100%" stop-color="{ca}"/>\n'
            f'    </linearGradient>'
        )

        metric_text = metrics[i]
        value_w = card_w - 42
        value_h = 96
        metric_tspans, metric_lines, metric_fsize, metric_dy = fitted_tspans(
            metric_text,
            mid_x,
            value_w,
            value_h,
            max_font_size=52,
            min_font_size=20,
            line_height=1.08,
        )
            
        # Glassmorphic Card panel with subtle stroke border and drop shadow
        card_parts.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{local_rx}" '
            f'fill="url(#metric-grad-{index:02d})" stroke="{ca}" stroke-opacity="{0.75 if brutal_stagger else card_stroke_opacity}" '
            f'stroke-width="{profile.stroke_width if brutal_stagger else 1.5}" filter="url(#card-shadow-{index:02d})"/>'
        )
        # Accent top stripe
        card_parts.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" height="4" rx="2" fill="{ca}" opacity="0.8"/>'
        )
        
        num_y = card_y + t["type"]["caption"] + t["margin"]["tight"]
        # Double ring number badge
        card_parts.append(
            f'    <circle cx="{mid_x}" cy="{num_y - 4}" r="{t["type"]["overline"] + 6}" '
            f'fill="none" stroke="{ca}" stroke-opacity="0.25" stroke-width="1"/>'
        )
        card_parts.append(
            f'    <circle cx="{mid_x}" cy="{num_y - 4}" r="{t["type"]["overline"] + 2}" '
            f'fill="{ca}" opacity="0.1"/>'
        )
        card_parts.append(
            f'    <text x="{mid_x}" y="{num_y}" font-family="{font}" font-size="{t["type"]["overline"] - 1}" '
            f'font-weight="700" fill="{badge_ca}" text-anchor="middle" letter-spacing="1" opacity="0.9">'
            f'{i + 1:02d}</text>'
        )
        
        # Sparkline background decorative graph
        spark_y = card_y + card_h - 28
        card_parts.append(
            f'    <path d="M {cx + 20} {spark_y} Q {cx + card_w // 3} {spark_y - 20} {cx + 2 * card_w // 3} {spark_y - 10} T {cx + card_w - 20} {spark_y - 30}" '
            f'fill="none" stroke="{ca}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.18"/>'
        )
        card_parts.append(
            f'    <circle cx="{cx + card_w - 20}" cy="{spark_y - 30}" r="3" fill="{ca}" opacity="0.7"/>'
        )
        
        # Hero metric value using text gradient fill
        metric_y = card_y + card_h // 2 + 6 - max(0, metric_lines - 1) * metric_dy // 2
        card_parts.append(
            f'    <text x="{mid_x}" y="{metric_y}" font-family="{font}" font-size="{metric_fsize}" '
            f'font-weight="700" fill="url(#metric-num-grad-{index:02d}-{i})" text-anchor="middle" '
            f'data-fit-box="{mid_x - value_w // 2},{metric_y - metric_fsize},{value_w},{value_h}" '
            f'data-line-height="1.08">{metric_tspans}</text>'
        )
        
        raw_label = labels[i] if i < len(labels) else ""
        raw_label = re.sub(r"^[—\-\–\—\~:\s\u2014\u2013]+", "", raw_label).strip()
        if raw_label:
            max_lbl_w = card_w - 40
            label_h = 72
            tspans, lines_count, lbl_font, lbl_dy = fitted_tspans(
                raw_label, mid_x, max_lbl_w, label_h,
                max_font_size=18, min_font_size=12, line_height=1.25,
            )
            lbl_y = card_y + card_h - 28 - (lines_count - 1) * lbl_dy
            card_parts.append(
                f'    <text x="{mid_x}" y="{lbl_y}" font-family="{font}" '
                f'font-size="{lbl_font}" fill="{p["body"]}" text-anchor="middle" opacity="0.9" '
                f'data-fit-box="{mid_x - max_lbl_w // 2},{lbl_y - lbl_font},{max_lbl_w},{label_h}" '
                f'data-line-height="1.25">{tspans}</text>'
            )

    bar_w = t["accent_stripe"] * 6
    underline = _title_underline(m, m + 40, accent)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="metric-grad-{index:02d}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.85"/>\n'
        f'    </linearGradient>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        + "\n".join(defs_parts) + "\n"
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'  <g id="decor-bar-{index:02d}">\n'
        f'    <rect x="{w - bar_w}" y="0" width="{bar_w}" height="{h}" fill="{accent}" opacity="0.04"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 28}" font-family="{font}" font-size="{fsize_title}" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'{underline}\n'
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
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.10))
    accent = p["accent"]

    if "|" in body:
        parts = body.split("|", 1)
    elif re.search(r"\bvs\.?\b", body, re.IGNORECASE):
        parts = re.split(r"\bvs\.?\b", body, maxsplit=1, flags=re.IGNORECASE)
    else:
        mid = len(body) // 2
        parts = [body[:mid], body[mid:]]

    left_text = parts[0].strip()[:300]
    right_text = parts[1].strip()[:300] if len(parts) > 1 else ""
    gutter = t["margin"]["tight"] * 2
    col_w = (w - m * 2 - gutter) // 2
    col_y = m + t["type"]["h1"] + t["margin"]["tight"] * 2
    col_h = h - col_y - t["margin"]["page"]
    right_x = m + col_w + gutter
    body_font = t["type"]["body"]
    line_dy = int(body_font * 1.45)
    inner_w = col_w - 48
    col_rx = t["radius"]["card"]
    
    text_lx = m + 28
    text_rx = right_x + 28
    text_ly = col_y + 76
    text_ry = col_y + 76

    left_tspans, _ = _wrap_to_tspans(left_text, text_lx, body_font, inner_w, line_height=line_dy / body_font)
    right_tspans, _ = _wrap_to_tspans(right_text, text_rx, body_font, inner_w, line_height=line_dy / body_font)

    bar_w = t["accent_stripe"] * 6
    underline = _title_underline(m, m + 40, accent)
    
    # Left column badge details
    l_badge_cx = m + 32
    l_badge_cy = col_y + 32
    
    # Right column badge details
    r_badge_cx = right_x + 32
    r_badge_cy = col_y + 32

    def _hex_to_rgb(hexc: str) -> tuple[int, int, int]:
        h_ = hexc.lstrip("#")
        return tuple(int(h_[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore

    def _shift(hexc: str, delta: int) -> str:
        r, g, b = _hex_to_rgb(hexc)
        r = max(0, min(255, r + delta))
        g = max(0, min(255, g + delta))
        b = max(0, min(255, b + delta))
        return f"#{r:02X}{g:02X}{b:02X}"

    accent_l = accent
    accent_r = _shift(accent, 40)

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="col-grad-{index:02d}-l" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.8"/>\n'
        f'    </linearGradient>\n'
        f'    <linearGradient id="col-grad-{index:02d}-r" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.8"/>\n'
        f'    </linearGradient>\n'
        f'    <clipPath id="col-card-clip-{index:02d}-l">\n'
        f'      <rect x="{m}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}"/>\n'
        f'    </clipPath>\n'
        f'    <clipPath id="col-card-clip-{index:02d}-r">\n'
        f'      <rect x="{right_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}"/>\n'
        f'    </clipPath>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'  <g id="decor-bar-{index:02d}">\n'
        f'    <rect x="{w - bar_w}" y="0" width="{bar_w}" height="{h}" fill="{accent}" opacity="0.04"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 28}" font-family="{font}" font-size="{fsize_title}" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'{underline}\n'
        f'  </g>\n'
        f'  <g id="content-left-{index:02d}">\n'
        f'    <g clip-path="url(#col-card-clip-{index:02d}-l)">\n'
        f'      <rect x="{m}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}" fill="url(#col-grad-{index:02d}-l)"/>\n'
        f'      <rect x="{m}" y="{col_y}" width="4" height="{col_h}" fill="{accent_l}"/>\n'
        f'    </g>\n'
        f'    <rect x="{m}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}" fill="none" stroke="{accent_l}" stroke-opacity="0.18" stroke-width="1.5" filter="url(#card-shadow-{index:02d})"/>\n'
        f'    <rect x="{m + 5}" y="{col_y + 5}" width="{col_w - 10}" height="{col_h - 10}" rx="{col_rx - 4}" fill="none" stroke="{accent_l}" stroke-opacity="0.08" stroke-width="1"/>\n'
        f'    <circle cx="{l_badge_cx}" cy="{l_badge_cy}" r="20" fill="none" stroke="{accent_l}" stroke-width="1.2" stroke-opacity="0.25"/>\n'
        f'    <circle cx="{l_badge_cx}" cy="{l_badge_cy}" r="14" fill="{accent_l}" fill-opacity="0.12"/>\n'
        f'    <text x="{l_badge_cx}" y="{l_badge_cy + 4}" font-family="{font}" font-size="12" font-weight="700" fill="{accent_l}" text-anchor="middle">A</text>\n'
        f'    <text x="{text_lx}" y="{text_ly}" font-family="{font}" font-size="{body_font}" fill="{p["text"]}">{left_tspans}</text>\n'
        f'  </g>\n'
        f'  <g id="content-right-{index:02d}">\n'
        f'    <g clip-path="url(#col-card-clip-{index:02d}-r)">\n'
        f'      <rect x="{right_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}" fill="url(#col-grad-{index:02d}-r)"/>\n'
        f'      <rect x="{right_x}" y="{col_y}" width="4" height="{col_h}" fill="{accent_r}"/>\n'
        f'    </g>\n'
        f'    <rect x="{right_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}" fill="none" stroke="{accent_r}" stroke-opacity="0.18" stroke-width="1.5" filter="url(#card-shadow-{index:02d})"/>\n'
        f'    <rect x="{right_x + 5}" y="{col_y + 5}" width="{col_w - 10}" height="{col_h - 10}" rx="{col_rx - 4}" fill="none" stroke="{accent_r}" stroke-opacity="0.08" stroke-width="1"/>\n'
        f'    <circle cx="{r_badge_cx}" cy="{r_badge_cy}" r="20" fill="none" stroke="{accent_r}" stroke-width="1.2" stroke-opacity="0.25"/>\n'
        f'    <circle cx="{r_badge_cx}" cy="{r_badge_cy}" r="14" fill="{accent_r}" fill-opacity="0.12"/>\n'
        f'    <text x="{r_badge_cx}" y="{r_badge_cy + 4}" font-family="{font}" font-size="12" font-weight="700" fill="{accent_r}" text-anchor="middle">B</text>\n'
        f'    <text x="{text_rx}" y="{text_ry}" font-family="{font}" font-size="{body_font}" fill="{p["text"]}">{right_tspans}</text>\n'
        f'  </g>\n'
        f'</svg>'
    )

def _render_cover_short_impact(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    title = xml_escape(heading)
    body_lines = [line.strip() for line in body.split("\n") if line.strip()]
    subtitle_raw = body_lines[0][:140] if body_lines else ""
    m = t["margin"]["page"]
    accent = p["accent"]

    hero_fsize = t["type"]["hero"] + 24
    title_y = int(h * 0.55)
    max_w = w - m * 2

    title_tspans, title_lines, title_fs, title_dy = fitted_tspans(
        heading, m, max_w, 200,
        max_font_size=hero_fsize, min_font_size=36, line_height=1.15,
    )

    # Only emit the subtitle block when there is real content — an empty
    # <text> is ghost markup that QA now rejects.
    body_group = ""
    if subtitle_raw:
        sub_fs = t["type"]["h2"]
        sub_tspans, sub_lines, sub_actual_fs, sub_dy = fitted_tspans(
            subtitle_raw, m, max_w, 120,
            max_font_size=sub_fs, min_font_size=18, line_height=1.25,
        )
        subtitle_y = title_y + title_lines * title_dy + 16
        body_group = (
            f'  <g id="content-body-{index:02d}">\n'
            f'    <text x="{m}" y="{subtitle_y}" font-family="{font}" font-size="{sub_actual_fs}" '
            f'fill="{p["body"]}" opacity="0.9">{sub_tspans}</text>\n'
            f'  </g>\n'
        )

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'  <g id="decor-geometry-{index:02d}">\n'
        f'    <circle cx="{w}" cy="{h}" r="{int(h*0.8)}" fill="{accent}" opacity="0.04"/>\n'
        f'    <circle cx="{w}" cy="{h}" r="{int(h*0.75)}" stroke="{accent}" stroke-width="2" fill="none" opacity="0.1"/>\n'
        f'  </g>\n'
        f'  <g id="chrome-stripe">\n'
        f'    <rect x="{m}" y="0" width="12" height="{int(h*0.35)}" fill="{accent}" opacity="0.9"/>\n'
        f'  </g>\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{title_y}" font-family="{font}" font-size="{title_fs}" '
        f'font-weight="900" fill="{p["text"]}" letter-spacing="-1">{title_tspans}</text>\n'
        f'  </g>\n'
        f'{body_group}'
        f'  <g id="content-footer-{index:02d}">\n'
        f'    <rect x="{m}" y="{h - m - 12}" width="40" height="4" fill="{accent}"/>\n'
        f'    <text x="{m + 60}" y="{h - m - 4}" font-family="{font}" font-size="{t["type"]["overline"]}" '
        f'fill="{p["body"]}" letter-spacing="2" font-weight="700">01 / PRESENTATION</text>\n'
        f'  </g>\n'
        f'</svg>'
    )

def _render_cover_long_academic(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["page"]
    accent = p["accent"]

    body_lines = [line.strip() for line in body.split("\n") if line.strip()]
    subtitle_raw = body_lines[0][:200] if body_lines else ""

    hero_fsize = t["type"]["h1"] + 8
    max_title_w = w - m * 2
    title_y_start = int(h * 0.35)

    title_tspans, title_lines, title_fs, title_dy = fitted_tspans(
        heading, m, max_title_w, 220,
        max_font_size=hero_fsize, min_font_size=32, line_height=1.3,
    )
    title_svg = (
        f'    <text x="{m}" y="{title_y_start}" font-family="{font}" '
        f'font-size="{title_fs}" font-weight="700" fill="{p["text"]}">{title_tspans}</text>\n'
    )
    y = title_y_start + max(0, title_lines - 1) * title_dy

    # Empty subtitles emit nothing — no ghost <text> markup.
    body_group = ""
    if subtitle_raw:
        sub_tspans, sub_lines, sub_fs, sub_dy = fitted_tspans(
            subtitle_raw, m, max_title_w, 100,
            max_font_size=t["type"]["body"], min_font_size=14, line_height=1.25,
        )
        body_group = (
            f'  <g id="content-body-{index:02d}">\n'
            f'    <text x="{m}" y="{y + 20}" font-family="{font}" font-size="{sub_fs}" fill="{p["body"]}" opacity="0.85">{sub_tspans}</text>\n'
            f'  </g>\n'
        )

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'  <g id="academic-grid-{index:02d}">\n'
        f'    <line x1="{m}" y1="0" x2="{m}" y2="{h}" stroke="{accent}" stroke-width="1" opacity="0.2"/>\n'
        f'    <line x1="0" y1="{int(h*0.22)}" x2="{w}" y2="{int(h*0.22)}" stroke="{p["muted"]}" stroke-width="1" opacity="0.4"/>\n'
        f'    <line x1="0" y1="{h - 80}" x2="{w}" y2="{h - 80}" stroke="{p["muted"]}" stroke-width="1" opacity="0.4"/>\n'
        f'    <rect x="{m}" y="{int(h*0.22)}" width="{w - m * 2}" height="3" fill="{accent}"/>\n'
        f'  </g>\n'
        f'  <g id="content-eyebrow-{index:02d}">\n'
        f'    <text x="{m}" y="{int(h*0.16)}" font-family="{font}" font-size="{t["type"]["caption"]}" fill="{accent}" font-weight="700" letter-spacing="3">RESEARCH REPORT</text>\n'
        f'  </g>\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'{title_svg}'
        f'  </g>\n'
        f'{body_group}'
        f'  <g id="content-footer-{index:02d}">\n'
        f'    <text x="{m}" y="{h - 40}" font-family="{font}" font-size="{t["type"]["caption"]}" fill="{p["body"]}">PAGES: {total:02d} / ACADEMIC OVERVIEW</text>\n'
        f'  </g>\n'
        f'</svg>'
    )

def _render_cover_split_corporate(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    title = xml_escape(heading)
    body_lines = [line.strip() for line in body.split("\n") if line.strip()]
    subtitle_raw = body_lines[0][:140] if body_lines else ""
    m = t["margin"]["page"]
    accent = p["accent"]

    hero_fsize = t["type"]["hero"]
    max_title_w = int((w / 2) - m * 2)

    title_tspans, title_lines, title_fs, title_dy = fitted_tspans(
        heading, m + 20, max_title_w, 320,
        max_font_size=hero_fsize, min_font_size=30, line_height=1.2,
    )
    line_dy = title_dy
    lines = [None] * max(1, title_lines)

    title_y_start = int(h * 0.45)
    title_svg = (
        f'    <text x="{m + 20}" y="{title_y_start}" font-family="{font}" '
        f'font-size="{title_fs}" font-weight="700" fill="{p["text"]}">{title_tspans}</text>\n'
    )
    y = title_y_start + max(0, title_lines - 1) * title_dy

    right_bg = _hex_shift(p["background"], 10) if not is_light(lock) else _hex_shift(p["background"], -10)

    # Empty subtitles emit nothing — no ghost <text> markup.
    body_group = ""
    if subtitle_raw:
        sub_max_w = int((w / 2) - m * 2 - 20)
        sub_tspans, sub_lines, sub_fs, sub_dy = fitted_tspans(
            subtitle_raw, m + 20, sub_max_w, 100,
            max_font_size=t["type"]["body"], min_font_size=14, line_height=1.25,
        )
        subtitle_y = y + 50
        body_group = (
            f'  <g id="content-body-{index:02d}">\n'
            f'    <rect x="{m + 20}" y="{y + 20}" width="40" height="2" fill="{p["muted"]}" opacity="0.5"/>\n'
            f'    <text x="{m + 20}" y="{subtitle_y}" font-family="{font}" font-size="{sub_fs}" fill="{p["body"]}" opacity="0.85">{sub_tspans}</text>\n'
            f'  </g>\n'
        )

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'  <g id="split-bg-{index:02d}">\n'
        f'    <rect x="{w//2}" y="0" width="{w//2}" height="{h}" fill="{right_bg}"/>\n'
        f'    <circle cx="{int(w*0.75)}" cy="{h//2}" r="180" fill="none" stroke="{accent}" stroke-width="2" opacity="0.15" stroke-dasharray="10 10"/>\n'
        f'    <circle cx="{int(w*0.75)}" cy="{h//2}" r="140" fill="{accent}" opacity="0.05"/>\n'
        f'  </g>\n'
        f'  <g id="chrome-stripe">\n'
        f'    <rect x="{m}" y="{title_y_start - hero_fsize}" width="6" height="{len(lines)*line_dy}" fill="{accent}"/>\n'
        f'  </g>\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'{title_svg}'
        f'  </g>\n'
        f'{body_group}'
        f'  <g id="content-right-card-{index:02d}" filter="url(#card-shadow-{index:02d})">\n'
        f'    <rect x="{w//2 + 60}" y="{h//2 - 60}" width="{w//2 - 120}" height="120" rx="12" fill="{p["surface"]}" stroke="{accent}" stroke-opacity="0.2"/>\n'
        f'    <text x="{w//2 + 90}" y="{h//2 - 10}" font-family="{font}" font-size="{t["type"]["caption"]}" fill="{p["body"]}" font-weight="700" letter-spacing="1">PAGES DESIGNED</text>\n'
        f'    <text x="{w//2 + 90}" y="{h//2 + 35}" font-family="{font}" font-size="{t["type"]["h1"]}" font-weight="700" fill="{accent}">{total:02d}</text>\n'
        f'  </g>\n'
        f'</svg>'
    )

def _render_cover(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    """Hero/cover layout — dynamic routing based on title features."""
    title_len = len(heading)
    is_academic = any(c in heading for c in (":", "：", "—", "–")) or title_len > 25
    
    if title_len < 15 and not is_academic:
        return _render_cover_short_impact(index, heading, body, lock, total, w, h)
    elif is_academic:
        return _render_cover_long_academic(index, heading, body, lock, total, w, h)
    else:
        return _render_cover_split_corporate(index, heading, body, lock, total, w, h)


def _render_closing(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    """Thank-you/CTA layout driven by the theme profile's closing scene."""
    profile = get_theme_profile(lock)
    variant = profile.closing.variant
    if variant == "left-editorial-card":
        return _render_closing_editorial(index, heading, body, lock, total, w, h)
    if variant == "wide-hard-banner":
        return _render_closing_brutalist(index, heading, body, lock, total, w, h)
    if variant == "center-glass-card":
        return _render_closing_glass(index, heading, body, lock, total, w, h)
    return _render_closing_technical(index, heading, body, lock, total, w, h)


def _closing_subtitle(body: str) -> str:
    body_lines = []
    for line in body.split("\n"):
        clean = re.sub(r"^\s*[-*•]\s+", "", line.strip())
        clean = re.sub(r"^\s*>\s*", "", clean)
        clean = re.sub(r"`([^`]+)`", r"\1", clean)
        if clean:
            body_lines.append(clean)
    return "\n".join(body_lines[:4])[:360] if body_lines else ""


def _closing_title_text(
    heading: str,
    x: int,
    y: int,
    width: int,
    height: int,
    font: str,
    fill: str,
    *,
    anchor: str = "middle",
    max_font_size: int = 60,
    min_font_size: int = 28,
    weight: str = "700",
    line_height: float = 1.12,
) -> tuple[str, int]:
    tspans, lines, font_size, line_dy = fitted_tspans(
        heading,
        x,
        width,
        height,
        max_font_size=max_font_size,
        min_font_size=min_font_size,
        line_height=line_height,
    )
    y_pos = y + font_size + max(0, (height - (font_size + max(0, lines - 1) * line_dy)) // 2)
    return (
        f'    <text x="{x}" y="{y_pos}" font-family="{font}" font-size="{font_size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" '
        f'data-fit-box="{x - width // 2 if anchor == "middle" else x},{y},{width},{height}" '
        f'data-line-height="{line_height}">{tspans}</text>\n',
        y_pos,
    )


def _closing_body_text(
    subtitle: str,
    x: int,
    y: int,
    width: int,
    height: int,
    font: str,
    fill: str,
    *,
    anchor: str = "middle",
    max_font_size: int = 23,
    min_font_size: int = 13,
) -> str:
    if not subtitle:
        return ""
    tspans, _lines, font_size, _line_dy = fitted_tspans(
        subtitle,
        x,
        width,
        height,
        max_font_size=max_font_size,
        min_font_size=min_font_size,
        line_height=1.25,
    )
    box_x = x - width // 2 if anchor == "middle" else x
    return (
        f'    <text x="{x}" y="{y + font_size}" font-family="{font}" font-size="{font_size}" '
        f'fill="{fill}" text-anchor="{anchor}" data-fit-box="{box_x},{y},{width},{height}" '
        f'data-line-height="1.25">{tspans}</text>\n'
    )


def _render_closing_technical(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    """Default/dark closing: technical terminal card plus footer rail."""
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    subtitle = _closing_subtitle(body)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.20))
    profile = get_theme_profile(lock)

    cx, cy = w // 2, h // 2
    accent = p["accent"]
    accent_lighter = _hex_shift(accent, 40)

    card_w = int(w * 0.84)
    card_h = 360
    card_x = cx - card_w // 2
    card_y = cy - card_h // 2
    card_rx = profile.card_radius
    title_w = card_w - 96
    title_svg, _ = _closing_title_text(
        heading, cx, card_y + 70, title_w, 88, font, p["text"], max_font_size=62
    )
    body_svg = _closing_body_text(
        subtitle, cx, card_y + 178, int(w * 0.70), 132, font, p["body"],
        max_font_size=22, min_font_size=14,
    )

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="close-card-grad-{index:02d}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.9"/>\n'
        f'    </linearGradient>\n'
        f'    <linearGradient id="close-border-{index:02d}" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f'      <stop offset="0%" stop-color="{accent}"/>\n'
        f'      <stop offset="100%" stop-color="{accent_lighter}"/>\n'
        f'    </linearGradient>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'  <g id="decor-closing-geom-{index:02d}" opacity="0.65">\n'
        f'    <circle cx="8%" cy="50%" r="160" stroke="{accent}" stroke-width="1.2" stroke-dasharray="6,6" fill="none" opacity="0.15"/>\n'
        f'    <circle cx="92%" cy="50%" r="160" stroke="{accent}" stroke-width="1.2" stroke-dasharray="6,6" fill="none" opacity="0.15"/>\n'
        f'    <path d="M{card_x + 34} {card_y + card_h - 34} H{card_x + card_w - 34}" stroke="{accent}" stroke-opacity="0.24" stroke-width="1.5"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-closing-{index:02d}" data-theme-profile="{profile.name}" data-scene-variant="{profile.closing.variant}">\n'
        f'  <g id="content-card-{index:02d}" filter="url(#card-shadow-{index:02d})">\n'
        f'    <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{card_rx}" fill="url(#close-card-grad-{index:02d})" stroke="url(#close-border-{index:02d})" stroke-width="2"/>\n'
        f'    <rect x="{card_x + 8}" y="{card_y + 8}" width="{card_w - 16}" height="{card_h - 16}" rx="{card_rx - 4}" fill="none" stroke="{accent}" stroke-opacity="0.18" stroke-width="1.2"/>\n'
        f'  </g>\n'
        f'  <g id="content-eyebrow-{index:02d}">\n'
        f'    <rect x="{cx - 60}" y="{card_y + 32}" width="120" height="24" rx="12" fill="{accent}" fill-opacity="0.10" stroke="{accent}" stroke-opacity="0.25" stroke-width="1"/>\n'
        f'    <text x="{cx}" y="{card_y + 48}" font-family="{font}" font-size="{t["type"]["overline"] - 2}" '
        f'font-weight="700" fill="{accent}" letter-spacing="3" text-anchor="middle">THANK YOU</text>\n'
        f'  </g>\n'
        f'  <g id="content-title-{index:02d}">\n{title_svg}  </g>\n'
        f'  <g id="content-body-{index:02d}">\n'
        f'{body_svg}'
        f'  </g>\n'
        f'  </g>\n'
        f'</svg>\n'
    )


def _render_closing_editorial(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    """Warm editorial closing: left manuscript card and right pull-note."""
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    profile = get_theme_profile(lock)
    subtitle = _closing_subtitle(body)
    chrome = _chrome(index, total, lock, w, h)
    accent = p["accent"]
    m = t["margin"]["content"]
    card_x = m
    card_y = 154
    card_w = int(w * 0.54)
    card_h = 360
    title_svg, _ = _closing_title_text(
        heading, card_x + 42, card_y + 92, card_w - 84, 126, font, p["text"], anchor="start", max_font_size=54
    )
    body_svg = _closing_body_text(
        subtitle, card_x + 42, card_y + 242, card_w - 84, 92, font, p["body"], anchor="start", max_font_size=21
    )
    note_x = card_x + card_w + 78
    note_w = w - note_x - m - 8
    caption_tspans, _ = _wrap_to_tspans(
        "For questions, critique, and next steps.",
        int(note_x + 8),
        int(t["type"]["caption"]),
        int(note_w),
        line_height=1.2,
    )
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>{_shadow_filter_def(index, lock)}</defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'  <g id="decor-editorial-rules-{index:02d}" opacity="0.75">\n'
        f'    <line x1="{m}" y1="96" x2="{w - m}" y2="96" stroke="{accent}" stroke-width="1"/>\n'
        f'    <line x1="{m}" y1="{h - 104}" x2="{w - m}" y2="{h - 104}" stroke="{p["muted"]}" stroke-width="1"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-closing-{index:02d}" data-theme-profile="{profile.name}" data-scene-variant="{profile.closing.variant}">\n'
        f'    <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{profile.card_radius}" fill="{p["surface"]}" '
        f'stroke="{accent}" stroke-width="{profile.stroke_width}" filter="url(#card-shadow-{index:02d})"/>\n'
        f'    <text x="{card_x + 42}" y="{card_y + 54}" font-family="{font}" font-size="{t["type"]["overline"]}" '
        f'font-weight="700" fill="{accent}" letter-spacing="3">CLOSING NOTE</text>\n'
        f'    <g id="content-title-{index:02d}">\n{title_svg}    </g>\n'
        f'    <g id="content-body-{index:02d}">\n{body_svg}    </g>\n'
        f'    <g id="content-pullnote-{index:02d}">\n'
        f'      <text x="{note_x}" y="{card_y + 76}" font-family="{font}" font-size="72" fill="{accent}" opacity="0.20">&quot;</text>\n'
        f'      <text x="{note_x + 8}" y="{card_y + 142}" font-family="{font}" font-size="{t["type"]["h2"]}" fill="{p["text"]}" font-weight="700">Thank you</text>\n'
        f'      <rect x="{note_x + 8}" y="{card_y + 176}" width="{note_w}" height="2" fill="{accent}" opacity="0.55"/>\n'
        f'      <text x="{note_x + 8}" y="{card_y + 226}" font-family="{font}" font-size="{t["type"]["caption"]}" '
        f'fill="{p["body"]}" data-fit-box="{note_x + 8},{card_y + 198},{note_w},64" data-line-height="1.2">{caption_tspans}</text>\n'
        f'    </g>\n'
        f'  </g>\n'
        f'</svg>\n'
    )


def _render_closing_brutalist(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    """Neo-brutalist closing: hard banner, oversized index, no soft card reuse."""
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    profile = get_theme_profile(lock)
    subtitle = _closing_subtitle(body)
    chrome = _chrome(index, total, lock, w, h)
    accent = p["accent"]
    m = t["margin"]["content"]
    banner_x = m
    banner_y = 178
    banner_w = w - 2 * m
    banner_h = 244
    title_svg, _ = _closing_title_text(
        heading, banner_x + 42, banner_y + 60, banner_w - 250, 116, font, p["text"], anchor="start", max_font_size=62
    )
    body_svg = _closing_body_text(
        subtitle, banner_x + 42, banner_y + banner_h + 28, banner_w - 84, 80, font, p["body"], anchor="start", max_font_size=22
    )
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'  <g id="decor-construction-{index:02d}" opacity="0.55">\n'
        f'    <path d="M0 120 H{w} M0 {h - 120} H{w}" stroke="{p["muted"]}" stroke-width="2" stroke-dasharray="18,12"/>\n'
        f'    <path d="M{m - 26} 80 V{h - 80} M{w - m + 26} 80 V{h - 80}" stroke="{accent}" stroke-width="3"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-closing-{index:02d}" data-theme-profile="{profile.name}" data-scene-variant="{profile.closing.variant}">\n'
        f'    <rect x="{banner_x}" y="{banner_y}" width="{banner_w}" height="{banner_h}" rx="0" fill="{p["surface"]}" stroke="{accent}" stroke-width="{profile.stroke_width}"/>\n'
        f'    <rect x="{banner_x + banner_w - 190}" y="{banner_y}" width="190" height="{banner_h}" fill="{accent}"/>\n'
        f'    <text x="{banner_x + banner_w - 95}" y="{banner_y + 150}" font-family="{font}" font-size="92" fill="{p["background"]}" font-weight="900" text-anchor="middle">{index:02d}</text>\n'
        f'    <text x="{banner_x + 42}" y="{banner_y + 42}" font-family="{font}" font-size="{t["type"]["overline"]}" fill="{accent}" font-weight="900" letter-spacing="4">END / NEXT</text>\n'
        f'    <g id="content-title-{index:02d}">\n{title_svg}    </g>\n'
        f'    <g id="content-body-{index:02d}">\n{body_svg}    </g>\n'
        f'  </g>\n'
        f'</svg>\n'
    )


def _render_closing_glass(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    """Celestial glass closing: orbital frame and translucent center panel."""
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    profile = get_theme_profile(lock)
    subtitle = _closing_subtitle(body)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.28))
    accent = p["accent"]
    cx, cy = w // 2, h // 2
    card_w = int(w * 0.64)
    card_h = 258
    card_x = cx - card_w // 2
    card_y = cy - card_h // 2
    title_svg, _ = _closing_title_text(
        heading, cx, card_y + 78, card_w - 104, 102, font, p["text"], max_font_size=56
    )
    body_svg = _closing_body_text(subtitle, cx, card_y + card_h + 26, int(w * 0.58), 76, font, p["body"], max_font_size=22)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <radialGradient id="glass-close-glow-{index:02d}" cx="50%" cy="42%" r="52%">\n'
        f'      <stop offset="0%" stop-color="{accent}" stop-opacity="0.28"/>\n'
        f'      <stop offset="100%" stop-color="{accent}" stop-opacity="0"/>\n'
        f'    </radialGradient>\n'
        f'{_shadow_filter_def(index, lock)}\n{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'  <ellipse cx="{cx}" cy="{cy}" rx="{int(card_w * 0.72)}" ry="{int(card_h * 0.78)}" fill="url(#glass-close-glow-{index:02d})"/>\n'
        f'  <g id="decor-orbital-frame-{index:02d}" opacity="0.75">\n'
        f'    <ellipse cx="{cx}" cy="{cy}" rx="{int(card_w * 0.66)}" ry="{int(card_h * 0.95)}" fill="none" stroke="{accent}" stroke-width="1.3" stroke-opacity="0.36"/>\n'
        f'    <ellipse cx="{cx}" cy="{cy}" rx="{int(card_w * 0.80)}" ry="{int(card_h * 0.52)}" fill="none" stroke="{p["muted"]}" stroke-width="1" stroke-opacity="0.24" transform="rotate(-9 {cx} {cy})"/>\n'
        f'    <circle cx="{card_x + 72}" cy="{card_y + 42}" r="6" fill="{accent}" opacity="0.9"/>\n'
        f'    <circle cx="{card_x + card_w - 86}" cy="{card_y + card_h - 40}" r="4" fill="{accent}" opacity="0.7"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-closing-{index:02d}" data-theme-profile="{profile.name}" data-scene-variant="{profile.closing.variant}">\n'
        f'    <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{profile.card_radius}" fill="{p["surface"]}" fill-opacity="0.78" '
        f'stroke="{accent}" stroke-opacity="0.45" stroke-width="{profile.stroke_width}" filter="url(#card-shadow-{index:02d})"/>\n'
        f'    <text x="{cx}" y="{card_y + 50}" font-family="{font}" font-size="{t["type"]["overline"]}" fill="{accent}" font-weight="700" letter-spacing="4" text-anchor="middle">THANK YOU</text>\n'
        f'    <g id="content-title-{index:02d}">\n{title_svg}    </g>\n'
        f'    <g id="content-body-{index:02d}">\n{body_svg}    </g>\n'
        f'  </g>\n'
        f'</svg>\n'
    )


def _render_closing_body(w: int, h: int, font: str, p: dict, subtitle: str, t: dict | None = None, forced_y: int | None = None) -> str:
    if not subtitle:
        return ""
    t = t or _tokens(w, h)
    max_text_w = int(w * 0.65)
    y_pos = forced_y if forced_y is not None else h // 2 + t["margin"]["tight"] * 2
    bottom_margin = t["margin"]["page"] + t["type"]["caption"] + 18
    max_text_h = max(42, h - y_pos - bottom_margin)
    tspans, line_count, body_font, line_dy = fitted_tspans(
        subtitle,
        w // 2,
        max_text_w,
        max_text_h,
        max_font_size=24,
        min_font_size=13,
        line_height=1.25,
    )
    text_top = y_pos - body_font
    return (
        f'    <text x="{w // 2}" y="{y_pos}" font-family="{font}" font-size="{body_font}" '
        f'fill="{p["body"]}" text-anchor="middle" '
        f'data-fit-box="{w // 2 - max_text_w // 2},{text_top},{max_text_w},{max_text_h}" '
        f'data-line-height="1.25">{tspans}</text>'
    )



def _render_default(index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    title = xml_escape(heading)
    fsize_title = _title_font_size(heading)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.12))
    accent = p["accent"]
    light = is_light(lock)
    card_stroke_opacity = 0.25 if light else 0.12

    body_lines = [line.strip() for line in body.split("\n") if line.strip()][:8]
    body_parts: list[str] = []
    
    card_rx = t["radius"]["card"]
    card_y = m + t["type"]["h1"] + t["margin"]["tight"] * 2
    
    # Calculate body_font based on temporary estimates
    max_text_w = w - m * 2 - t["margin"]["page"] - 20
    # Provide a safe baseline height for auto_body_font estimation
    est_y_start = card_y + t["margin"]["tight"] + t["type"]["body"]
    est_avail_h = h - est_y_start - t["margin"]["page"] - 16
    
    body_font, line_dy = _auto_body_font(
        body_lines, max_text_w, est_avail_h,
        max_size=t["type"]["body"], floor_size=t["type"]["caption"], gap=t["margin"]["tight"] - 4,
    )
    
    # Position bullet lines relative to card_y so they always sit nicely inside!
    y = card_y + t["margin"]["tight"] + body_font - 2
    
    total_visual_lines = 0
    text_x = m + t["margin"]["tight"] * 3
    title_bottom_y = m + 28 + 12
    
    for line in body_lines:
        is_bullet = line.startswith("- ")
        text_content = line[2:].strip() if is_bullet else line
        
        # Clean markdown bold markers and split for keyword extraction
        clean_line = text_content.replace("**", "").replace("__", "")
        sep_match = re.search(r'\s*([—\-\–\—:：]+)\s*', clean_line)
        
        tspans, n = _wrap_to_tspans(clean_line, text_x, body_font, max_text_w, line_height=line_dy / body_font)
        
        if sep_match:
            sep = sep_match.group(0)
            kw_part = clean_line.split(sep, 1)[0]
            if 0 < len(kw_part) < 18:
                first_tspan_pat = re.compile(r"(<tspan[^>]*>)(.*?)(</tspan>)")
                m_tspan = first_tspan_pat.search(tspans)
                if m_tspan:
                    tspan_start, tspan_inner, tspan_end = m_tspan.groups()
                    kw_esc = xml_escape(kw_part)
                    sep_esc = xml_escape(sep)
                    if sep_esc in tspan_inner:
                        kw_seg, rest_seg = tspan_inner.split(sep_esc, 1)
                        styled_inner = (
                            f'<tspan font-weight="700" fill="{accent}">{kw_seg}</tspan>'
                            f'<tspan fill="{p["muted"]}" opacity="0.6">{sep_esc}</tspan>'
                            f'{rest_seg}'
                        )
                        tspans = tspans.replace(tspan_inner, styled_inner, 1)
                        
        # Draw elegant diamond-outline bullet before text
        bullet_cy = y - body_font // 2 - 2
        body_parts.append(
            f'    <polygon points="{text_x - 18},{bullet_cy} {text_x - 14},{bullet_cy - 4} {text_x - 10},{bullet_cy} {text_x - 14},{bullet_cy + 4}" '
            f'fill="{accent}" opacity="0.8"/>'
        )
        body_parts.append(
            f'    <text x="{text_x}" y="{y}" font-family="{font}" font-size="{body_font}" '
            f'fill="{p["body"]}">{tspans}</text>'
        )
        y += line_dy * n + t["margin"]["tight"] - 4
        total_visual_lines += n

    body_svg = "\n".join(body_parts)
    card_h = max(int(h * 0.45), (y - card_y) + t["margin"]["tight"] // 2)
    bar_w = t["accent_stripe"] * 6
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="card-grad-{index:02d}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.85"/>\n'
        f'    </linearGradient>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'  <g id="decor-bar-{index:02d}">\n'
        f'    <rect x="{w - bar_w}" y="0" width="{bar_w}" height="{h}" fill="{accent}" opacity="0.04"/>\n'
        f'  </g>\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 28}" font-family="{font}" font-size="{fsize_title}" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'{_title_underline(m, title_bottom_y, accent)}\n'
        f'  </g>\n'
        f'  <g id="content-body-{index:02d}">\n'
        # Glassmorphic parent panel
        f'    <rect x="{m}" y="{card_y}" width="{w - m * 2}" height="{card_h}" rx="{card_rx}" '
        f'fill="url(#card-grad-{index:02d})" stroke="{accent}" stroke-opacity="{card_stroke_opacity}" stroke-width="1.5" filter="url(#card-shadow-{index:02d})"/>\n'
        f'    <rect x="{m}" y="{card_y}" width="4" height="{card_h}" rx="2" fill="{accent}" opacity="0.8"/>\n'
        f'{body_svg}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# v3.0 layout primitives — drop shadow, executive summary, comparison,
# quote block, process flow. Inspired by ppt-master MBB / consulting decks.
# ---------------------------------------------------------------------------

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
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.10))

    raw = [line.strip() for line in body.split("\n") if line.strip()]
    # Prefer explicit "- " bullets; fall back to any non-empty line so the
    # page never degrades to placeholder chips ("POINT 01/02/03") when the
    # planner hands us already-stripped text. Strip any leading list marker
    # or "N. " numbering defensively.
    bullets = [line[2:].strip() for line in raw if line.startswith("- ")][:3]
    if not any(bullets):
        bullets = [
            re.sub(r"^\s*[-*•]\s+", "", re.sub(r"^\d+[\.\)、]\s*", "", line)).strip()
            for line in raw
        ][:3]
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
    text_accent_fallback = p.get("secondary_accent", _hex_shift(accent, 40))

    gutter = t["margin"]["tight"] * 2
    card_w = (w - m * 2 - 2 * gutter) // 3
    card_h = int(h * 0.53)
    card_y = m + t["type"]["h1"] + t["margin"]["tight"] * 3
    card_rx = t["radius"]["card"]
    parts: list[str] = []
    defs_list: list[str] = []
    inner_w = card_w - t["margin"]["page"]

    card_text_avail = card_h - t["type"]["h1"] * 2 - t["margin"]["tight"]
    body_font, line_dy = _auto_body_font(
        bullets, inner_w, card_text_avail,
        max_size=t["type"]["body"] - 4, floor_size=t["type"]["caption"], gap=t["margin"]["tight"] - 4,
    )

    for i in range(3):
        cx = m + i * (card_w + gutter)
        ca = card_accents[i]
        readable_ca = _contrast_safe_accent(ca, p["surface"], text_accent_fallback)
        
        # Define the glassmorphic linear gradient and clip path for each card to prevent edge bleed
        defs_list.append(
            f'    <linearGradient id="exec-card-grad-{index:02d}-{i}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
            f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.8"/>\n'
            f'    </linearGradient>\n'
            f'    <clipPath id="exec-card-clip-{index:02d}-{i}">\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{card_rx}"/>\n'
            f'    </clipPath>'
        )

        # Card body group with clipped top accent stripe
        parts.append(
            f'    <g clip-path="url(#exec-card-clip-{index:02d}-{i})">\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{card_rx}" fill="url(#exec-card-grad-{index:02d}-{i})"/>\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="6" fill="{ca}"/>\n'
            f'    </g>\n'
            f'    <!-- Outline & shadow container (avoids clipped stroke & shadow) -->\n'
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{card_rx}" fill="none" stroke="{ca}" stroke-opacity="0.18" stroke-width="1.5" filter="url(#card-shadow-{index:02d})"/>\n'
            f'    <!-- Inner border detail -->\n'
            f'    <rect x="{cx + 6}" y="{card_y + 6}" width="{card_w - 12}" height="{card_h - 12}" rx="{card_rx - 4}" fill="none" stroke="{ca}" stroke-opacity="0.08" stroke-width="1"/>'
        )
        
        # Numbered halo (filled circle with the index)
        halo_cx = cx + t["margin"]["page"]
        halo_cy = card_y + t["type"]["h1"] + t["margin"]["tight"] * 2
        parts.append(
            f'    <circle cx="{halo_cx}" cy="{halo_cy}" r="{t["type"]["caption"] + t["margin"]["tight"]}" \n'
            f'      fill="{ca}" fill-opacity="0.14"/>'
        )
        parts.append(
            f'    <text x="{halo_cx}" y="{halo_cy + t["margin"]["tight"]}" font-family="{font}" \n'
            f'      font-size="{t["type"]["h2"]}" font-weight="700" fill="{readable_ca}" \n'
            f'      text-anchor="middle">{i + 1:02d}</text>'
        )
        
        # Body text wrapped
        text = bullets[i] if i < len(bullets) else ""
        if text:
            text_x = cx + t["margin"]["tight"] * 2
            tspans, _vis = _wrap_to_tspans(
                text, text_x, body_font, inner_w,
                line_height=line_dy / body_font,
            )
            parts.append(
                f'    <text x="{text_x}" y="{card_y + t["type"]["h1"] * 2 + t["margin"]["tight"] * 2}" \n'
                f'      font-family="{font}" font-size="{body_font}" \n'
                f'      fill="{p["text"]}">{tspans}</text>'
            )
            
        # No bottom pill chip: the label was always empty, so the old
        # fill-opacity="0" rect + blank <text> pair was pure ghost markup.
        # QA now errors on exactly that pattern (empty text / invisible
        # drawable), so nothing is emitted here.

    cards_svg = "\n".join(parts)
    underline = _title_underline(m, m + t["type"]["caption"] + t["margin"]["tight"] * 2 + 12, p["accent"])
    
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" \n'
        f'  xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        + "\n".join(defs_list) + "\n"
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" \n'
        f'    height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-eyebrow-{index:02d}">\n'
        f'    <text x="{m}" y="{m + t["margin"]["tight"]}" font-family="{font}" font-size="{t["type"]["overline"]}" \n'
        f'      font-weight="700" fill="{p["accent"]}" letter-spacing="4">\n'
        f'      EXECUTIVE SUMMARY</text>\n'
        f'  </g>\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + t["type"]["caption"] + t["margin"]["tight"] * 2}" font-family="{font}" \n'
        f'      font-size="{fsize_title}" font-weight="700" \n'
        f'      fill="{p["text"]}">{title}</text>\n'
        f'{underline}\n'
        f'  </g>\n'
        f'  <g id="content-cards-{index:02d}">\n'
        f'{cards_svg}\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_comparison(
    index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int
) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    title = xml_escape(heading)
    fsize_title = min(_title_font_size(heading), t["type"]["h1"])
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.10))
    accent = p["accent"]

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

    gutter = t["margin"]["page"] * 2
    col_w = (w - m * 2 - gutter) // 2
    col_y = m + t["type"]["h1"] + t["margin"]["tight"] * 2
    col_h = h - col_y - t["margin"]["page"]
    a_x = m
    b_x = a_x + col_w + gutter
    body_font = t["type"]["body"] - 2
    line_dy = int(body_font * 1.45)
    inner_w = col_w - 48
    col_rx = t["radius"]["card"]

    text_lx = a_x + 32
    text_rx = b_x + 32
    text_ly = col_y + 160
    text_ry = col_y + 160

    a_tspans, _ = _wrap_to_tspans(
        a_body or a_label, text_lx, body_font, inner_w,
        line_height=line_dy / body_font,
    )
    b_tspans, _ = _wrap_to_tspans(
        b_body or b_label, text_rx, body_font, inner_w,
        line_height=line_dy / body_font,
    )
    vs_cx = a_x + col_w + gutter // 2
    vs_cy = col_y + col_h // 2
    underline = _title_underline(m, m + 40, accent)

    # Concentric badges details
    l_badge_cx = a_x + 32
    l_badge_cy = col_y + 36
    r_badge_cx = b_x + 32
    r_badge_cy = col_y + 36

    def _hex_to_rgb(hexc: str) -> tuple[int, int, int]:
        h_ = hexc.lstrip("#")
        return tuple(int(h_[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore

    def _shift(hexc: str, delta: int) -> str:
        r, g, b = _hex_to_rgb(hexc)
        r = max(0, min(255, r + delta))
        g = max(0, min(255, g + delta))
        b = max(0, min(255, b + delta))
        return f"#{r:02X}{g:02X}{b:02X}"

    accent_a = accent
    accent_b = _shift(accent, 40)

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="cmp-grad-{index:02d}-a" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.8"/>\n'
        f'    </linearGradient>\n'
        f'    <linearGradient id="cmp-grad-{index:02d}-b" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.8"/>\n'
        f'    </linearGradient>\n'
        f'    <clipPath id="cmp-card-clip-{index:02d}-a">\n'
        f'      <rect x="{a_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}"/>\n'
        f'    </clipPath>\n'
        f'    <clipPath id="cmp-card-clip-{index:02d}-b">\n'
        f'      <rect x="{b_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}"/>\n'
        f'    </clipPath>\n'
        f'{_shadow_filter_def(index, lock)}\n'
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
        f'{underline}\n'
        f'  </g>\n'
        # Side A Card Group with Clip Path
        f'  <g id="content-side-a-{index:02d}">\n'
        f'    <g clip-path="url(#cmp-card-clip-{index:02d}-a)">\n'
        f'      <rect x="{a_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}" fill="url(#cmp-grad-{index:02d}-a)"/>\n'
        f'      <rect x="{a_x}" y="{col_y}" width="4" height="{col_h}" fill="{accent_a}"/>\n'
        f'    </g>\n'
        f'    <rect x="{a_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}" fill="none" stroke="{accent_a}" stroke-opacity="0.18" stroke-width="1.5" filter="url(#card-shadow-{index:02d})"/>\n'
        f'    <rect x="{a_x + 5}" y="{col_y + 5}" width="{col_w - 10}" height="{col_h - 10}" rx="{col_rx - 4}" fill="none" stroke="{accent_a}" stroke-opacity="0.08" stroke-width="1"/>\n'
        # Side A Badge & Heading
        f'    <circle cx="{l_badge_cx}" cy="{l_badge_cy}" r="20" fill="none" stroke="{accent_a}" stroke-width="1.2" stroke-opacity="0.25"/>\n'
        f'    <circle cx="{l_badge_cx}" cy="{l_badge_cy}" r="14" fill="{accent_a}" fill-opacity="0.12"/>\n'
        f'    <text x="{l_badge_cx}" y="{l_badge_cy + 4}" font-family="{font}" font-size="12" font-weight="700" fill="{accent_a}" text-anchor="middle">A</text>\n'
        f'    <text x="{a_x + 32}" y="{col_y + 100}" font-family="{font}" '
        f'font-size="22" font-weight="700" fill="{p["text"]}">'
        f'{xml_escape(a_label[:40])}</text>\n'
        # Side A text
        f'    <text x="{text_lx}" y="{text_ly}" font-family="{font}" '
        f'font-size="{body_font}" fill="{p["body"]}">{a_tspans}</text>\n'
        f'  </g>\n'
        # Central VS Indicator with dynamic concentric rings
        f'  <g id="content-vs-{index:02d}">\n'
        f'    <circle cx="{vs_cx}" cy="{vs_cy}" r="48" fill="none" stroke="{accent}" stroke-width="1.2" stroke-dasharray="4,4" stroke-opacity="0.2"/>\n'
        f'    <circle cx="{vs_cx}" cy="{vs_cy}" r="40" fill="none" stroke="{accent}" stroke-width="1" stroke-opacity="0.15"/>\n'
        f'    <circle cx="{vs_cx}" cy="{vs_cy}" r="32" fill="{accent}" filter="url(#card-shadow-{index:02d})"/>\n'
        f'    <text x="{vs_cx}" y="{vs_cy + 7}" font-family="{font}" '
        f'font-size="20" font-weight="800" fill="{p["background"]}" '
        f'text-anchor="middle">VS</text>\n'
        f'  </g>\n'
        # Side B Card Group with Clip Path
        f'  <g id="content-side-b-{index:02d}">\n'
        f'    <g clip-path="url(#cmp-card-clip-{index:02d}-b)">\n'
        f'      <rect x="{b_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}" fill="url(#cmp-grad-{index:02d}-b)"/>\n'
        f'      <rect x="{b_x}" y="{col_y}" width="4" height="{col_h}" fill="{accent_b}"/>\n'
        f'    </g>\n'
        f'    <rect x="{b_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="{col_rx}" fill="none" stroke="{accent_b}" stroke-opacity="0.18" stroke-width="1.5" filter="url(#card-shadow-{index:02d})"/>\n'
        f'    <rect x="{b_x + 5}" y="{col_y + 5}" width="{col_w - 10}" height="{col_h - 10}" rx="{col_rx - 4}" fill="none" stroke="{accent_b}" stroke-opacity="0.08" stroke-width="1"/>\n'
        # Side B Badge & Heading
        f'    <circle cx="{r_badge_cx}" cy="{r_badge_cy}" r="20" fill="none" stroke="{accent_b}" stroke-width="1.2" stroke-opacity="0.25"/>\n'
        f'    <circle cx="{r_badge_cx}" cy="{r_badge_cy}" r="14" fill="{accent_b}" fill-opacity="0.12"/>\n'
        f'    <text x="{r_badge_cx}" y="{r_badge_cy + 4}" font-family="{font}" font-size="12" font-weight="700" fill="{accent_b}" text-anchor="middle">B</text>\n'
        f'    <text x="{b_x + 32}" y="{col_y + 100}" font-family="{font}" '
        f'font-size="22" font-weight="700" fill="{p["text"]}">'
        f'{xml_escape(b_label[:40])}</text>\n'
        # Side B text
        f'    <text x="{text_rx}" y="{text_ry}" font-family="{font}" '
        f'font-size="{body_font}" fill="{p["body"]}">{b_tspans}</text>\n'
        f'  </g>\n'
        f'</svg>'
    )
def _render_quote_block(
    index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int
) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    title = xml_escape(heading)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.14))
    accent = p["accent"]

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
    body_font = t["type"]["hero"] - 4
    line_dy = int(body_font * 1.45)
    max_w = int(w * 0.62)
    quote_x = w // 2
    tspans, vis = _wrap_to_tspans(
        quote_text, quote_x, body_font, max_w,
        line_height=line_dy / body_font,
    )
    block_h = vis * line_dy
    card_w = int(w * 0.78)
    card_h = max(240, block_h + 130)
    card_x = w // 2 - card_w // 2
    card_y = (h - card_h) // 2 + 10
    card_rx = t["radius"]["card"] + 4
    
    quote_y = card_y + 76

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" '
        f'height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-eyebrow-{index:02d}">\n'
        f'    <text x="{m}" y="{m + t["margin"]["tight"]}" font-family="{font}" '
        f'font-size="{t["type"]["overline"]}" font-weight="700" fill="{accent}" '
        f'letter-spacing="6">{xml_escape(heading[:40].upper())}</text>\n'
        f'  </g>\n'
        # Centered Frosted Glass Quote Card
        f'  <g id="content-quote-card-{index:02d}" filter="url(#card-shadow-{index:02d})">\n'
        f'    <rect x="{card_x}" y="{card_y}" width="{card_w}" height="{card_h}" rx="{card_rx}" fill="{p["surface"]}" fill-opacity="0.8" stroke="{accent}" stroke-opacity="0.15" stroke-width="1.5"/>\n'
        f'    <rect x="{card_x}" y="{card_y}" width="6" height="{card_h}" rx="3" fill="{accent}" opacity="0.8"/>\n'
        f'  </g>\n'
        # Large quotes behind text
        f'  <g id="content-quote-mark-{index:02d}">\n'
        f'    <text x="{card_x + 32}" y="{card_y + 100}" font-family="Georgia, serif" '
        f'font-size="120" font-weight="700" fill="{accent}" fill-opacity="0.14" text-anchor="start">&#x201C;</text>\n'
        f'    <text x="{card_x + card_w - 32}" y="{card_y + card_h - 10}" font-family="Georgia, serif" '
        f'font-size="120" font-weight="700" fill="{accent}" fill-opacity="0.14" text-anchor="end">&#x201D;</text>\n'
        f'  </g>\n'
        # Quote Text centered
        f'  <g id="content-quote-{index:02d}">\n'
        f'    <text x="{quote_x}" y="{quote_y}" '
        f'font-family="{font}" font-size="{body_font}" font-weight="600" '
        f'fill="{p["text"]}" text-anchor="middle" '
        f'font-style="italic">{tspans}</text>\n'
        f'  </g>\n'
        # Attribution and separation line
        f'  <g id="content-attribution-{index:02d}">\n'
        f'    <line x1="{quote_x - 80}" y1="{quote_y + block_h + 20}" x2="{quote_x + 80}" y2="{quote_y + block_h + 20}" stroke="{accent}" stroke-width="1.5" opacity="0.5"/>\n'
        f'    <text x="{quote_x}" y="{quote_y + block_h + 46}" '
        f'font-family="{font}" font-size="{t["type"]["caption"]}" fill="{p["body"]}" '
        f'text-anchor="middle">{xml_escape(attribution[:60])}</text>\n'
        f'  </g>\n'
        f'</svg>'
    )


def _parse_body_table(body: str) -> tuple[list[str], list[list[str]]]:
    """Parse markdown pipe table from body string into (headers, rows)."""
    sep_pat = re.compile(r"^\|[\s\-:]+\|[\s\-:|]*\|$")

    def _split_row(line: str) -> list[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    headers: list[str] = []
    rows: list[list[str]] = []
    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("|") and line.endswith("|"):
            if sep_pat.match(line):
                continue
            cells = _split_row(line)
            if not headers:
                headers = cells
            else:
                rows.append(cells)
        elif "|" in line and not line.startswith("-"):
            # Handle non-standard pipe-delimited lines (e.g., "A|B|C")
            if sep_pat.match("|" + line + "|"):
                continue
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]  # drop empty edge cells
            if not cells:
                continue
            if not headers:
                headers = cells
            else:
                rows.append(cells)
    return headers, rows


def _render_table(
    index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int,
) -> str:
    """Render a structured SVG table from markdown pipe-table body — premium executive report style."""
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    m = t["margin"]["content"]
    title = xml_escape(heading)
    fsize_title = _title_font_size(heading)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.10))
    accent = p["accent"]
    accent_lighter = _hex_shift(accent, 40)

    headers, rows = _parse_body_table(body)
    if not headers or not rows:
        return _render_default(index, heading, body, lock, total, w, h)

    max_cols = 5
    max_rows = 8
    if len(headers) > max_cols:
        headers = headers[:max_cols]
    rows = [r[:max_cols] for r in rows[:max_rows]]

    n_cols = len(headers)
    n_rows = len(rows)

    table_x = m
    table_w = w - m * 2
    col_w = table_w // n_cols

    # Dynamic typography scaling based on column count to prevent congestion
    if n_cols <= 3:
        body_font = 16
        header_font = 18
    else:
        body_font = 13
        header_font = 15

    card_rx = t["radius"]["card"]
    title_area_h = m + t["type"]["h1"] + t["margin"]["tight"] * 3
    table_y = title_area_h

    from .svg_pipeline import _wrap_to_tspans

    # 1. Pre-calculate header height dynamically
    max_header_lines = 1
    header_wrapped = []
    for ci, hdr in enumerate(headers):
        cx = table_x + ci * col_w + col_w // 2
        tspans, lines = _wrap_to_tspans(hdr, cx, header_font, col_w - 20, line_height=1.25)
        header_wrapped.append((tspans, lines))
        max_header_lines = max(max_header_lines, lines)
    header_h = max(46, max_header_lines * int(header_font * 1.25) + 16)

    # 2. Pre-calculate data row heights dynamically
    row_heights = []
    row_data = []
    for ri, row in enumerate(rows):
        cells_wrapped = []
        max_lines = 1
        for ci, cell in enumerate(row):
            cx = table_x + ci * col_w + col_w // 2
            # Clean md markers first
            clean_cell = re.sub(r"\*\*(.+?)\*\*", r"\1", cell)
            clean_cell = re.sub(r"\*(.+?)\*", r"\1", clean_cell).strip()
            # Wrap cell contents
            tspans, lines = _wrap_to_tspans(clean_cell, cx, body_font, col_w - 24, line_height=1.25)
            cells_wrapped.append((tspans, lines))
            max_lines = max(max_lines, lines)
        
        row_h_curr = max(42, max_lines * int(body_font * 1.25) + 16)
        row_heights.append(row_h_curr)
        row_data.append(cells_wrapped)

    parts: list[str] = []

    # Container glassmorphic card
    table_h = header_h + sum(row_heights)
    parts.append(
        f'    <rect x="{table_x}" y="{table_y}" width="{table_w}" '
        f'height="{table_h}" rx="{card_rx}" fill="{p["surface"]}" '
        f'stroke="{accent}" stroke-opacity="0.12" stroke-width="1" filter="url(#card-shadow-{index:02d})" opacity="0.95"/>'
    )

    # Header row gradient background with rounded top edges
    parts.append(
        f'    <rect x="{table_x}" y="{table_y}" width="{table_w}" '
        f'height="{header_h}" rx="{card_rx}" fill="url(#table-hdr-grad-{index:02d})"/>'
    )
    parts.append(
        f'    <rect x="{table_x}" y="{table_y + header_h - 8}" '
        f'width="{table_w}" height="8" fill="{accent}"/>'
    )

    # Header text
    for ci, (hdr_tspans, lines) in enumerate(header_wrapped):
        cx = table_x + ci * col_w + col_w // 2
        hdr_h = lines * int(header_font * 1.25)
        text_padding = (header_h - hdr_h) // 2
        cy = table_y + text_padding + header_font - 1
        parts.append(
            f'    <text x="{cx}" y="{cy}" font-family="{font}" '
            f'font-size="{header_font}" font-weight="700" '
            f'fill="#FFFFFF" text-anchor="middle">{hdr_tspans}</text>'
        )

    # Data rows
    curr_ry = table_y + header_h
    for ri, row in enumerate(rows):
        row_h_curr = row_heights[ri]
        # Alternating row background with very soft accent overlay
        if ri % 2 == 1:
            parts.append(
                f'    <rect x="{table_x}" y="{curr_ry}" width="{table_w}" '
                f'height="{row_h_curr}" fill="{accent}" fill-opacity="0.04"/>'
            )
        else:
            parts.append(
                f'    <rect x="{table_x}" y="{curr_ry}" width="{table_w}" '
                f'height="{row_h_curr}" fill="{p["surface"]}" fill-opacity="0.2"/>'
            )
            
        # Draw cell text
        for ci, cell in enumerate(row):
            cx = table_x + ci * col_w + col_w // 2
            tspans, lines = row_data[ri][ci]
            cell_h = lines * int(body_font * 1.25)
            text_padding = (row_h_curr - cell_h) // 2
            cy = curr_ry + text_padding + body_font - 1
            
            # Make the first column (dimensions) bold and accent-toned
            if ci == 0:
                parts.append(
                    f'    <text x="{cx}" y="{cy}" font-family="{font}" '
                    f'font-size="{body_font}" font-weight="700" fill="{accent}" '
                    f'text-anchor="middle">{tspans}</text>'
                )
            else:
                parts.append(
                    f'    <text x="{cx}" y="{cy}" font-family="{font}" '
                    f'font-size="{body_font}" fill="{p["body"]}" '
                    f'text-anchor="middle">{tspans}</text>'
                )
        
        curr_ry += row_h_curr

    # Column divider lines
    for ci in range(1, n_cols):
        dx = table_x + ci * col_w
        parts.append(
            f'    <line x1="{dx}" y1="{table_y + header_h}" '
            f'x2="{dx}" y2="{table_y + header_h + sum(row_heights)}" '
            f'stroke="{p["muted"]}" stroke-width="1" opacity="0.15"/>'
        )

    # Header/body separator thick gradient line
    parts.append(
        f'    <line x1="{table_x}" y1="{table_y + header_h}" '
        f'x2="{table_x + table_w}" y2="{table_y + header_h}" '
        f'stroke="{accent_lighter}" stroke-width="2.5" opacity="0.8"/>'
    )

    table_svg = "\n".join(parts)

    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'    <linearGradient id="table-hdr-grad-{index:02d}" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f'      <stop offset="0%" stop-color="{accent}"/>\n'
        f'      <stop offset="100%" stop-color="{accent_lighter}"/>\n'
        f'    </linearGradient>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 28}" font-family="{font}" font-size="{fsize_title}" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'{_title_underline(m, m + 40, p["accent"])}\n'
        f'  </g>\n'
        f'  <g id="content-table-{index:02d}">\n'
        f'{table_svg}\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_process_flow(
    index: int, heading: str, body: str, lock: dict, total: int, w: int, h: int
) -> str:
    """Horizontal step boxes connected by chevrons and arrows — premium step process layout."""
    p = lock["palette"]
    font = lock["font_family"]
    title = xml_escape(heading)
    fsize_title = _title_font_size(heading)
    chrome = _chrome(index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(index, lock, w, h, intensity=_intent_decor_intensity(lock, 0.10))
    accent = p["accent"]

    raw = [line.strip() for line in body.split("\n") if line.strip()]
    steps: list[str] = []
    for line in raw:
        clean = re.sub(r"^[-•]\s*", "", line)
        clean = re.sub(r"^\d+[\.、)]\s*", "", clean)
        if re.search(r"[\u4e00-\u9fff]", clean):
            clean = clean.replace("(", "（").replace(")", "）").replace(",", "，")
        steps.append(clean)
    if len(steps) == 1 and ("→" in steps[0] or "->" in steps[0]):
        sep = "→" if "→" in steps[0] else "->"
        steps = [s.strip() for s in steps[0].split(sep) if s.strip()]
    steps = [s for s in steps if s][:5]
    if not steps:
        steps = [body.strip()[:30] or title]

    n = len(steps)
    t = _tokens(w, h)
    m = t["margin"]["content"]
    gutter = t["margin"]["tight"] * 2
    grid_mode = n == 4
    grid_cols = 2 if grid_mode else n
    box_w = (w - m * 2 - (grid_cols - 1) * gutter) // max(grid_cols, 1)
    box_h = 165 if grid_mode else int(h * 0.31)
    box_y = 204 if grid_mode else (h - box_h) // 2 + t["margin"]["tight"] * 2
    body_font = t["type"]["body"] if grid_mode else t["type"]["caption"] + 6
    line_dy = int(body_font * 1.4)
    inner_w = box_w - t["margin"]["page"]
    box_rx = t["radius"]["card"]

    def _hex_to_rgb(hexc: str) -> tuple[int, int, int]:
        h_ = hexc.lstrip("#")
        return tuple(int(h_[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore

    def _shift(hexc: str, delta: int) -> str:
        r, g, b = _hex_to_rgb(hexc)
        r = max(0, min(255, r + delta))
        g = max(0, min(255, g + delta))
        b = max(0, min(255, b + delta))
        return f"#{r:02X}{g:02X}{b:02X}"

    accent_alt1 = _shift(accent, -40)
    accent_alt2 = _shift(accent, +50)
    accent_alt3 = _shift(accent, -20)
    accent_alt4 = _shift(accent, +30)
    step_accents = [accent, accent_alt1, accent_alt2, accent_alt3, accent_alt4]

    parts: list[str] = []
    defs_list: list[str] = []
    for i, step in enumerate(steps):
        col = i % grid_cols
        row = i // grid_cols
        bx = m + col * (box_w + gutter)
        by = box_y + row * (box_h + gutter)
        ca = step_accents[i % len(step_accents)]
        badge_text = _readable_on(ca, dark=p["background"], light=p["text"])
        
        # Define the glassmorphic linear gradient and clip path for each step card to prevent edge bleed
        defs_list.append(
            f'    <linearGradient id="proc-card-grad-{index:02d}-{i}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}"/>\n'
            f'      <stop offset="100%" stop-color="{p["surface"]}" stop-opacity="0.8"/>\n'
            f'    </linearGradient>\n'
            f'    <clipPath id="proc-card-clip-{index:02d}-{i}">\n'
            f'      <rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" rx="{box_rx}"/>\n'
            f'    </clipPath>'
        )

        # Card body group with clipped left accent stripe
        parts.append(
            f'    <g clip-path="url(#proc-card-clip-{index:02d}-{i})">\n'
            f'      <rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" rx="{box_rx}" fill="url(#proc-card-grad-{index:02d}-{i})"/>\n'
            f'      <rect x="{bx}" y="{by}" width="4" height="{box_h}" fill="{ca}"/>\n'
            f'    </g>\n'
            f'    <!-- Outline & shadow container (avoids clipped stroke & shadow) -->\n'
            f'    <rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" rx="{box_rx}" fill="none" stroke="{ca}" stroke-opacity="0.18" stroke-width="1.5" filter="url(#card-shadow-{index:02d})"/>\n'
            f'    <!-- Inner border detail -->\n'
            f'    <rect x="{bx + 5}" y="{by + 5}" width="{box_w - 10}" height="{box_h - 10}" rx="{box_rx - 4}" fill="none" stroke="{ca}" stroke-opacity="0.08" stroke-width="1"/>'
        )
        
        # Step number badge inside glowing concentric rings
        badge_cx = bx + box_w // 2
        badge_cy = by + (40 if grid_mode else t["type"]["h2"] - 4)
        parts.append(
            f'    <circle cx="{badge_cx}" cy="{badge_cy}" r="20" '
            f'fill="none" stroke="{ca}" stroke-opacity="0.25" stroke-width="1.2"/>'
        )
        parts.append(
            f'    <circle cx="{badge_cx}" cy="{badge_cy}" r="14" '
            f'fill="{ca}"/>'
        )
        parts.append(
            f'    <text x="{badge_cx}" y="{badge_cy + 5}" '
            f'font-family="{font}" font-size="{t["type"]["caption"]}" font-weight="700" '
            f'fill="{badge_text}" text-anchor="middle">'
            f'{i + 1:02d}</text>'
        )
        
        # Step text: fit to the card instead of only wrapping by width.
        text_box_y = by + (72 if grid_mode else t["type"]["h1"] + t["margin"]["tight"] * 2)
        text_box_h = by + box_h - text_box_y - t["margin"]["tight"]
        tspans, _v, fitted_font, _fitted_line_dy = fitted_tspans(
            step, bx + box_w // 2, inner_w, text_box_h,
            max_font_size=body_font,
            min_font_size=13,
            line_height=1.18,
        )
        parts.append(
            f'    <text x="{bx + box_w // 2}" y="{text_box_y + fitted_font}" '
            f'font-family="{font}" font-size="{fitted_font}" '
            f'fill="{p["text"]}" text-anchor="middle">{tspans}</text>'
        )
        
        # Connectors between step boxes
        if i < n - 1 and not grid_mode:
            ax = bx + box_w + t["margin"]["tight"] // 2
            ay = by + box_h // 2
            # Glow line connection
            parts.append(
                f'    <line x1="{ax}" y1="{ay}" x2="{ax + gutter - t["margin"]["tight"]}" '
                f'y2="{ay}" stroke="{ca}" stroke-width="2.5" opacity="0.6"/>'
            )
            # Dotted overlay line
            parts.append(
                f'    <line x1="{ax}" y1="{ay}" x2="{ax + gutter - t["margin"]["tight"]}" '
                f'y2="{ay}" stroke="{p["background"]}" stroke-width="1.2" stroke-dasharray="2,3" opacity="0.8"/>'
            )
            # Arrowhead chevron points
            parts.append(
                f'    <polygon points="{ax + gutter - t["margin"]["tight"]},{ay - 5} '
                f'{ax + gutter - 2},{ay} {ax + gutter - t["margin"]["tight"]},{ay + 5}" '
                f'fill="{ca}" opacity="0.8"/>'
            )

    steps_svg = "\n".join(parts)
    return (
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">\n'
        f'  <defs>\n'
        f'{_shadow_filter_def(index, lock)}\n'
        f'{orb_defs}\n'
        + "\n".join(defs_list) + "\n"
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
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
        f'  </g>\n'
        f'  <g id="content-flow-{index:02d}">\n'
        f'{steps_svg}\n'
        f'  </g>\n'
        f'</svg>'
    )
