"""Course-presentation SVG renderers for slide-skill v3.0.

Provides specialized layouts for academic/course presentations:
  - learning-objectives:  Numbered objectives with checkmark icons
  - key-concept:          Large concept heading + explanation + example
  - case-study:           Two-panel case layout (situation + analysis)
  - discussion:           Open question card with prompt

All renderers share the same signature and chrome/decor helpers
from domain_teaching so they blend seamlessly with existing themes.
"""

from __future__ import annotations

from .content_planner import SlidePlan
from .util import xml_escape


# ---------------------------------------------------------------------------
# Shared helpers (same as domain_teaching)
# ---------------------------------------------------------------------------

def _chrome(index: int, total: int, lock: dict, w: int, h: int) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    return (
        f'  <g id="chrome-stripe">\n'
        f'    <rect x="0" y="0" width="6" height="{h}" fill="{p["accent"]}" />\n'
        f'  </g>\n'
        f'  <g id="chrome-footer">\n'
        f'    <rect x="0" y="{h - 32}" width="{w}" height="32" fill="{p["surface"]}" />\n'
        f'    <text x="{w - 96}" y="{h - 10}" font-family="{font}" font-size="12" '
        f'fill="{p["muted"]}" text-anchor="end">{index:02d} / {total:02d}</text>\n'
        f'  </g>'
    )


def _decor_orbs(index: int, lock: dict, w: int, h: int, intensity: float = 0.08) -> tuple[str, str]:
    p = lock["palette"]
    defs = (
        f'    <radialGradient id="course-orb-{index:02d}" cx="50%" cy="50%" r="50%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="{intensity}"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'    </radialGradient>'
    )
    body = (
        f'  <g id="decor-{index:02d}">\n'
        f'    <circle cx="{w - 100}" cy="80" r="250" fill="url(#course-orb-{index:02d})"/>\n'
        f'  </g>'
    )
    return defs, body


def _svg_open(w: int, h: int) -> str:
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'


def _title_block(index: int, title: str, lock: dict) -> str:
    p = lock["palette"]
    font = lock["font_family"]
    return (
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="96" y="108" font-family="{font}" font-size="36" '
        f'font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="96" y="120" width="60" height="4" fill="{p["accent"]}"/>\n'
        f'  </g>'
    )


# ---------------------------------------------------------------------------
# Learning Objectives Layout
# ---------------------------------------------------------------------------

def render_learning_objectives(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a learning objectives slide.

    Layout: Numbered objectives with checkmark-style icons and
    a subtle badge reading "LEARNING OBJECTIVES" at the top.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items
    parts: list[str] = []

    # Badge
    parts.append(
        f'    <rect x="80" y="150" width="200" height="28" rx="14" fill="{p["accent"]}"/>'
    )
    parts.append(
        f'    <text x="180" y="170" font-family="{font}" font-size="12" '
        f'font-weight="600" fill="{p["background"]}" text-anchor="middle">'
        f'LEARNING OBJECTIVES</text>'
    )

    y = 210
    obj_h = 65
    gap = 12
    card_w = w - 200

    for idx, item in enumerate(items[:6]):
        text = xml_escape(item.primary[:120])

        # Card background
        parts.append(
            f'    <rect x="100" y="{y}" width="{card_w}" height="{obj_h}" '
            f'rx="10" fill="{p["surface"]}"/>'
        )
        # Number circle
        parts.append(
            f'    <circle cx="140" cy="{y + obj_h // 2}" r="18" '
            f'fill="{p["accent"]}" opacity="0.15"/>'
        )
        parts.append(
            f'    <text x="140" y="{y + obj_h // 2 + 6}" font-family="{font}" '
            f'font-size="16" font-weight="700" fill="{p["accent"]}" '
            f'text-anchor="middle">{idx + 1}</text>'
        )
        # Objective text
        parts.append(
            f'    <text x="176" y="{y + obj_h // 2 + 7}" font-family="{font}" '
            f'font-size="20" fill="{p["text"]}">{text}</text>'
        )

        y += obj_h + gap

    content = "\n".join(parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n{orb_defs}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock)}\n'
        f'  <g id="content-objectives-{plan.index:02d}">\n'
        f'{content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Key Concept Layout
# ---------------------------------------------------------------------------

def render_key_concept(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a key concept slide.

    Layout: Large concept term centered, with explanation below
    and an optional example in a muted box at the bottom.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h, intensity=0.12)
    title = xml_escape(plan.title)

    # First item is the concept term, rest are explanations
    concept = xml_escape(plan.items[0].primary) if plan.items else title
    explanation_items = plan.items[1:4] if len(plan.items) > 1 else []

    parts: list[str] = []

    # Large concept term
    concept_len = len(concept)
    if concept_len <= 6:
        concept_font = 72
    elif concept_len <= 12:
        concept_font = 56
    else:
        concept_font = 40

    parts.append(
        f'    <text x="{w // 2}" y="280" font-family="{font}" '
        f'font-size="{concept_font}" font-weight="700" fill="{p["accent"]}" '
        f'text-anchor="middle">{concept}</text>'
    )

    # Underline
    parts.append(
        f'    <rect x="{w // 2 - 40}" y="295" width="80" height="4" '
        f'rx="2" fill="{p["accent"]}" opacity="0.4"/>'
    )

    # Explanation lines
    y = 350
    for item in explanation_items:
        text = xml_escape(item.primary[:100])
        parts.append(
            f'    <text x="{w // 2}" y="{y}" font-family="{font}" '
            f'font-size="20" fill="{p["body"]}" text-anchor="middle">{text}</text>'
        )
        y += 36

    # Example box at bottom
    if plan.items and plan.items[0].secondary:
        example = xml_escape(plan.items[0].secondary[:120])
        box_y = h - 160
        box_w = w - 240
        parts.append(
            f'    <rect x="120" y="{box_y}" width="{box_w}" height="70" '
            f'rx="12" fill="{p["surface"]}"/>'
        )
        parts.append(
            f'    <text x="144" y="{box_y + 22}" font-family="{font}" '
            f'font-size="13" font-weight="600" fill="{p["accent"]}">'
            f'EXAMPLE</text>'
        )
        parts.append(
            f'    <text x="144" y="{box_y + 50}" font-family="{font}" '
            f'font-size="18" font-style="italic" fill="{p["body"]}">{example}</text>'
        )

    content = "\n".join(parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n{orb_defs}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock)}\n'
        f'  <g id="content-concept-{plan.index:02d}">\n'
        f'{content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Case Study Layout
# ---------------------------------------------------------------------------

def render_case_study(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a case study slide.

    Layout: Two-panel — left panel for case situation/background,
    right panel for analysis/findings. Clean split with accent divider.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    # Split items: first half = situation, second half = analysis
    items = plan.items
    mid = max(1, len(items) // 2)
    left_items = items[:mid]
    right_items = items[mid:]

    panel_w = (w - 200) // 2
    left_x = 80
    right_x = left_x + panel_w + 40  # 40px gap
    panel_y = 170
    panel_h = h - panel_y - 60

    parts: list[str] = []

    # Left panel — Case / Situation
    parts.append(
        f'    <rect x="{left_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" '
        f'rx="14" fill="{p["surface"]}"/>'
    )
    parts.append(
        f'    <rect x="{left_x}" y="{panel_y}" width="{panel_w}" height="6" '
        f'rx="3" fill="{p["accent"]}"/>'
    )
    parts.append(
        f'    <text x="{left_x + 24}" y="{panel_y + 36}" font-family="{font}" '
        f'font-size="14" font-weight="700" fill="{p["accent"]}">CASE</text>'
    )
    ly = panel_y + 65
    for item in left_items[:4]:
        text = xml_escape(item.primary[:60])
        parts.append(
            f'    <text x="{left_x + 24}" y="{ly}" font-family="{font}" '
            f'font-size="18" fill="{p["text"]}">{text}</text>'
        )
        ly += 32
        if item.secondary:
            sub = xml_escape(item.secondary[:80])
            parts.append(
                f'    <text x="{left_x + 24}" y="{ly}" font-family="{font}" '
                f'font-size="14" fill="{p["body"]}">{sub}</text>'
            )
            ly += 28

    # Vertical divider
    div_x = left_x + panel_w + 20
    parts.append(
        f'    <rect x="{div_x}" y="{panel_y + 20}" width="2" '
        f'height="{panel_h - 40}" fill="{p["accent"]}" opacity="0.25"/>'
    )

    # Right panel — Analysis / Findings
    parts.append(
        f'    <rect x="{right_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" '
        f'rx="14" fill="{p["surface"]}"/>'
    )
    parts.append(
        f'    <rect x="{right_x}" y="{panel_y}" width="{panel_w}" height="6" '
        f'rx="3" fill="{p["accent"]}" opacity="0.6"/>'
    )
    parts.append(
        f'    <text x="{right_x + 24}" y="{panel_y + 36}" font-family="{font}" '
        f'font-size="14" font-weight="700" fill="{p["accent"]}">ANALYSIS</text>'
    )
    ry = panel_y + 65
    for item in right_items[:4]:
        text = xml_escape(item.primary[:60])
        parts.append(
            f'    <text x="{right_x + 24}" y="{ry}" font-family="{font}" '
            f'font-size="18" fill="{p["text"]}">{text}</text>'
        )
        ry += 32
        if item.secondary:
            sub = xml_escape(item.secondary[:80])
            parts.append(
                f'    <text x="{right_x + 24}" y="{ry}" font-family="{font}" '
                f'font-size="14" fill="{p["body"]}">{sub}</text>'
            )
            ry += 28

    content = "\n".join(parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n{orb_defs}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock)}\n'
        f'  <g id="content-casestudy-{plan.index:02d}">\n'
        f'{content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Discussion Layout
# ---------------------------------------------------------------------------

def render_discussion(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a discussion/question prompt slide.

    Layout: Large question mark icon + discussion prompt centered,
    with optional sub-questions listed below.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h, intensity=0.15)
    title = xml_escape(plan.title)

    parts: list[str] = []

    # Large question mark circle
    parts.append(
        f'    <circle cx="{w // 2}" cy="260" r="60" '
        f'fill="{p["accent"]}" opacity="0.12"/>'
    )
    parts.append(
        f'    <text x="{w // 2}" y="285" font-family="{font}" '
        f'font-size="56" font-weight="700" fill="{p["accent"]}" '
        f'text-anchor="middle">?</text>'
    )

    # Main question/prompt
    main_q = xml_escape(plan.items[0].primary) if plan.items else ""
    q_len = len(main_q)
    q_font = 28 if q_len <= 30 else (22 if q_len <= 50 else 18)
    parts.append(
        f'    <text x="{w // 2}" y="370" font-family="{font}" '
        f'font-size="{q_font}" font-weight="600" fill="{p["text"]}" '
        f'text-anchor="middle">{main_q}</text>'
    )

    # Badge
    parts.append(
        f'    <rect x="{w // 2 - 70}" y="395" width="140" height="26" '
        f'rx="13" fill="{p["accent"]}" opacity="0.12"/>'
    )
    parts.append(
        f'    <text x="{w // 2}" y="413" font-family="{font}" font-size="11" '
        f'font-weight="600" fill="{p["accent"]}" text-anchor="middle">'
        f'DISCUSSION</text>'
    )

    # Sub-questions
    y = 460
    for item in plan.items[1:4]:
        text = xml_escape(item.primary[:100])
        parts.append(
            f'    <text x="{w // 2}" y="{y}" font-family="{font}" '
            f'font-size="18" fill="{p["body"]}" text-anchor="middle">'
            f'• {text}</text>'
        )
        y += 34

    content = "\n".join(parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n{orb_defs}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock)}\n'
        f'  <g id="content-discussion-{plan.index:02d}">\n'
        f'{content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

COURSE_RENDERERS: dict[str, callable] = {
    "learning-objectives": render_learning_objectives,
    "key-concept": render_key_concept,
    "case-study": render_case_study,
    "discussion": render_discussion,
}


def render_course_slide(plan: SlidePlan, lock: dict, total: int) -> str | None:
    """Try to render a course-specific layout. Returns None if layout is not course."""
    renderer = COURSE_RENDERERS.get(plan.layout)
    if renderer is None:
        return None
    return renderer(plan, lock, total)
