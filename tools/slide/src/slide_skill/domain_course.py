"""Course-presentation SVG renderers for slide-skill v3.0.

Provides specialized layouts for academic/course presentations:
  - learning-objectives:  Numbered objectives with checkmark icons
  - key-concept:          Large concept heading + explanation + example
  - case-study:           Two-panel case layout (situation + analysis)
  - discussion:           Open question card with prompt

All renderers share the same signature and reuse chrome/decor helpers
from svg_shared so they blend seamlessly with existing themes.
"""

from __future__ import annotations

from .content_planner import SlidePlan
from .svg_shared import (
    card_style_params,
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
from .util import xml_escape


# ---------------------------------------------------------------------------
# Local aliases — single source of truth is svg_shared
# ---------------------------------------------------------------------------

_tokens = design_tokens
_hex_shift = hex_shift
_shadow_filter_def = shadow_filter_def
_svg_open = svg_open
_title_underline = title_underline
_title_block = title_block
_decor_orbs = decor_orbs


def _chrome(index: int, total: int, lock: dict, w: int, h: int) -> str:
    """Wrapper combining svg_shared chrome_defs + chrome_body."""
    defs = chrome_defs(index, lock, w, h)
    body = chrome_body(index, total, lock, w, h)
    return f'  <defs>\n{defs}\n  </defs>\n{body}'


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
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items
    parts: list[str] = []
    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]

    # Premium top-left badge
    parts.append(
        f'    <rect x="90" y="145" width="200" height="24" rx="12" fill="{p["accent"]}" fill-opacity="0.15" stroke="{p["accent"]}" stroke-opacity="0.3"/>'
    )
    parts.append(
        f'    <text x="190" y="161" font-family="{font}" font-size="15" '
        f'font-weight="700" fill="{p["accent"]}" text-anchor="middle" letter-spacing="1">LEARNING OBJECTIVES</text>'
    )

    # Dynamic scaling
    count = len(items[:6])
    content_h = h - 230
    card_h = min(80, max(55, content_h // max(count, 1) - 12))
    gap = min(16, max(8, (content_h - card_h * count) // max(count - 1, 1))) if count > 1 else 12
    y = 185 + (content_h - (card_h * count + gap * (count - 1))) // 2

    card_w = w - 180

    for idx, item in enumerate(items[:6]):
        text = xml_escape(item.primary[:120])
        ca = _hex_shift(p["accent"], idx * 12 - 24)
        cs = card_style_params(lock, idx)

        grad_id = f"obj-card-grad-{plan.index:02d}-{idx}"
        clip_id = f"obj-card-clip-{plan.index:02d}-{idx}"

        defs_parts.append(
            f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
            f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
            f'    </linearGradient>'
        )
        defs_parts.append(
            f'    <clipPath id="{clip_id}">\n'
            f'      <rect x="90" y="{y}" width="{card_w}" height="{card_h}" rx="10" />\n'
            f'    </clipPath>'
        )

        parts.append(
            f'    <g clip-path="url(#{clip_id})">\n'
            f'      <rect x="90" y="{y}" width="{card_w}" height="{card_h}" fill="url(#{grad_id})"/>\n'
            f'      <rect x="90" y="{y}" width="4" height="{card_h}" fill="{ca}" opacity="0.85"/>\n'
            f'    </g>'
        )

        parts.append(
            f'    <rect x="90" y="{y}" width="{card_w}" height="{card_h}" rx="10" fill="none" '
            f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" '
            f'filter="url(#card-shadow-{plan.index:02d})"/>'
        )

        if cs["inner_border"]:
            parts.append(
                f'    <rect x="{90 + 6}" y="{y + 6}" width="{card_w - 12}" height="{card_h - 12}" rx="8" fill="none" '
                f'stroke="{ca}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
            )

        # Concentric glowing badge
        badge_cx = 90 + 36
        badge_cy = y + card_h // 2
        parts.append(
            f'    <circle cx="{badge_cx}" cy="{badge_cy}" r="18" '
            f'fill="{ca}" fill-opacity="0.06" stroke="{ca}" stroke-opacity="0.15" stroke-width="1"/>'
        )
        parts.append(
            f'    <circle cx="{badge_cx}" cy="{badge_cy}" r="13" '
            f'fill="{ca}" fill-opacity="0.12" stroke="{ca}" stroke-opacity="0.3" stroke-width="1"/>'
        )
        parts.append(
            f'    <text x="{badge_cx}" y="{badge_cy + 5}" font-family="{font}" '
            f'font-size="16" font-weight="700" fill="{ca}" '
            f'text-anchor="middle">{idx + 1}</text>'
        )

        # Text with dynamic wrapping to prevent overflow
        from .svg_pipeline import _wrap_to_tspans
        text_w = card_w - 90
        text_font = 18 if count > 4 else 21
        line_h = text_font + 3
        tspans, line_count = _wrap_to_tspans(item.primary, 162, text_font, text_w, line_height=1.25)
        text_y = y + (card_h - (line_count - 1) * line_h) // 2 + 5
        parts.append(
            f'    <text x="162" y="{text_y}" font-family="{font}" '
            f'font-size="{text_font}" font-weight="500" fill="{p["text"]}">{tspans}</text>'
        )

        y += card_h + gap

    content = "\n".join(parts)
    defs_content = "\n".join(defs_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n'
        f'{defs_content}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock, w, h)}\n'
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

    Layout: Beautiful asymmetric double-pane layout:
    - Left: Bold concept term inside a premium frosted glass card with glowing border
    - Right: Dynamic vertical list of explanation bullet cards + example card
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h, intensity=0.15)
    title = xml_escape(plan.title)

    concept = xml_escape(plan.items[0].primary) if plan.items else title
    explanations = plan.items[1:4] if len(plan.items) > 1 else []

    parts: list[str] = []
    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]

    # Layout bounds
    panel_y = 160
    panel_h = h - panel_y - 70
    left_w = (w - 180) * 4 // 10  # 40% width
    right_w = (w - 180) * 6 // 10 - 32  # 60% width minus gap
    left_x = 90
    right_x = left_x + left_w + 32

    cs = card_style_params(lock, 0)

    # Left Panel Defs
    defs_parts.append(
        f'    <linearGradient id="concept-left-grad-{plan.index:02d}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
        f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
        f'    </linearGradient>'
    )
    defs_parts.append(
        f'    <clipPath id="concept-left-clip-{plan.index:02d}">\n'
        f'      <rect x="{left_x}" y="{panel_y}" width="{left_w}" height="{panel_h}" rx="16" />\n'
        f'    </clipPath>'
    )

    parts.append(
        f'    <circle cx="{left_x + left_w // 2}" cy="{panel_y + panel_h // 2 - 10}" r="{min(left_w, panel_h) // 3}" fill="none" stroke="{p["accent"]}" stroke-opacity="0.08" stroke-width="1.5" stroke-dasharray="4 6"/>\n'
        f'    <circle cx="{left_x + left_w // 2}" cy="{panel_y + panel_h // 2 - 10}" r="{min(left_w, panel_h) // 3 + 24}" fill="none" stroke="{p["accent"]}" stroke-opacity="0.04" stroke-width="1" stroke-dasharray="2 4"/>'
    )

    parts.append(
        f'    <g clip-path="url(#concept-left-clip-{plan.index:02d})">\n'
        f'      <rect x="{left_x}" y="{panel_y}" width="{left_w}" height="{panel_h}" fill="url(#concept-left-grad-{plan.index:02d})"/>\n'
        f'      <rect x="{left_x}" y="{panel_y}" width="{left_w}" height="6" fill="{p["accent"]}" opacity="0.85"/>\n'
        f'    </g>'
    )

    parts.append(
        f'    <rect x="{left_x}" y="{panel_y}" width="{left_w}" height="{panel_h}" rx="16" fill="none" '
        f'stroke="{p["accent"]}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" filter="url(#card-shadow-{plan.index:02d})"/>'
    )
    if cs["inner_border"]:
        parts.append(
            f'    <rect x="{left_x + 6}" y="{panel_y + 6}" width="{left_w - 12}" height="{panel_h - 12}" rx="12" fill="none" '
            f'stroke="{p["accent"]}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
        )

    # Dynamic text sizing for the concept term
    concept_len = len(concept)
    if concept_len <= 4:
        concept_font = 48
    elif concept_len <= 8:
        concept_font = 36
    else:
        concept_font = 26

    # Decorative Quote Mark or Ornament
    parts.append(
        f'    <text x="{left_x + 36}" y="{panel_y + 60}" font-family="{font}" font-size="72" '
        f'font-weight="700" fill="{p["accent"]}" opacity="0.1" text-anchor="middle">“</text>'
    )

    parts.append(
        f'    <text x="{left_x + left_w // 2}" y="{panel_y + panel_h // 2 - 10}" font-family="{font}" '
        f'font-size="{concept_font}" font-weight="700" fill="{p["accent"]}" '
        f'text-anchor="middle">{concept}</text>'
    )
    
    parts.append(
        f'    <text x="{left_x + left_w // 2}" y="{panel_y + panel_h // 2 + 30}" font-family="{font}" '
        f'font-size="15" font-weight="700" fill="{p["muted"]}" letter-spacing="2" '
        f'text-anchor="middle">CORE CONCEPT</text>'
    )

    # Right Panel - Explanations and optional Example
    ry = panel_y
    r_item_h = min(75, max(50, (panel_h - 100) // max(len(explanations), 1) - 12))
    gap = 12

    for idx, item in enumerate(explanations):
        text = xml_escape(item.primary[:100])
        ca = _hex_shift(p["accent"], idx * 15 - 15)
        cs = card_style_params(lock, idx)
        grad_id = f"concept-right-grad-{plan.index:02d}-{idx}"
        clip_id = f"concept-right-clip-{plan.index:02d}-{idx}"

        defs_parts.append(
            f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
            f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -5)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
            f'    </linearGradient>'
        )
        defs_parts.append(
            f'    <clipPath id="{clip_id}">\n'
            f'      <rect x="{right_x}" y="{ry}" width="{right_w}" height="{r_item_h}" rx="10" />\n'
            f'    </clipPath>'
        )

        parts.append(
            f'    <g clip-path="url(#{clip_id})">\n'
            f'      <rect x="{right_x}" y="{ry}" width="{right_w}" height="{r_item_h}" fill="url(#{grad_id})"/>\n'
            f'      <rect x="{right_x}" y="{ry}" width="4" height="{r_item_h}" fill="{ca}" opacity="0.8"/>\n'
            f'    </g>'
        )
        parts.append(
            f'    <rect x="{right_x}" y="{ry}" width="{right_w}" height="{r_item_h}" rx="10" fill="none" '
            f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}"/>'
        )

        # Concentric glowing bullet marker
        bullet_cx = right_x + 24
        bullet_cy = ry + r_item_h // 2
        parts.append(
            f'    <circle cx="{bullet_cx}" cy="{bullet_cy}" r="6" fill="{ca}" fill-opacity="0.15" stroke="{ca}" stroke-opacity="0.3" stroke-width="1"/>\n'
            f'    <circle cx="{bullet_cx}" cy="{bullet_cy}" r="3" fill="{ca}"/>'
        )

        from .svg_pipeline import _wrap_to_tspans
        text_w = right_w - 60
        text_font = 17 if len(explanations) > 3 else 19
        line_h = text_font + 3
        tspans, line_count = _wrap_to_tspans(item.primary, right_x + 42, text_font, text_w, line_height=1.25)
        text_y = ry + (r_item_h - (line_count - 1) * line_h) // 2 + 5
        parts.append(
            f'    <text x="{right_x + 42}" y="{text_y}" font-family="{font}" '
            f'font-size="{text_font}" font-weight="500" fill="{p["text"]}">{tspans}</text>'
        )
        ry += r_item_h + gap

    # Example Card at the bottom of the right panel
    if plan.items and plan.items[0].secondary:
        example = xml_escape(plan.items[0].secondary[:120])
        ex_y = panel_y + panel_h - 80
        ex_ca = _hex_shift(p["accent"], 30)

        ex_cs = card_style_params(lock, 1)
        defs_parts.append(
            f'    <linearGradient id="concept-ex-grad-{plan.index:02d}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{ex_cs["fill_opacity_start"]}"/>\n'
            f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{ex_cs["fill_opacity_end"]}"/>\n'
            f'    </linearGradient>'
        )
        defs_parts.append(
            f'    <clipPath id="concept-ex-clip-{plan.index:02d}">\n'
            f'      <rect x="{right_x}" y="{ex_y}" width="{right_w}" height="80" rx="12" />\n'
            f'    </clipPath>'
        )

        parts.append(
            f'    <g clip-path="url(#concept-ex-clip-{plan.index:02d})">\n'
            f'      <rect x="{right_x}" y="{ex_y}" width="{right_w}" height="80" fill="url(#concept-ex-grad-{plan.index:02d})"/>\n'
            f'      <rect x="{right_x}" y="{ex_y}" width="{right_w}" height="4" fill="{ex_ca}" opacity="0.8"/>\n'
            f'    </g>'
        )
        parts.append(
            f'    <rect x="{right_x}" y="{ex_y}" width="{right_w}" height="80" rx="12" fill="none" '
            f'stroke="{ex_ca}" stroke-opacity="{ex_cs["stroke_opacity"]}" stroke-width="{ex_cs["stroke_width"]}" filter="url(#card-shadow-{plan.index:02d})"/>'
        )
        parts.append(
            f'    <rect x="{right_x + 5}" y="{ex_y + 5}" width="{right_w - 10}" height="70" rx="9" fill="none" '
            f'stroke="{ex_ca}" stroke-opacity="0.08" stroke-width="1"/>'
        )

        parts.append(
            f'    <text x="{right_x + 24}" y="{ex_y + 24}" font-family="{font}" '
            f'font-size="15" font-weight="700" fill="{ex_ca}" letter-spacing="1">EXAMPLE</text>'
        )
        from .svg_pipeline import _wrap_to_tspans
        text_w = right_w - 48
        text_font = 16
        line_h = 19
        tspans, line_count = _wrap_to_tspans(plan.items[0].secondary, right_x + 24, text_font, text_w, line_height=1.2)
        text_y = ex_y + (80 - (line_count - 1) * line_h) // 2 + 4
        parts.append(
            f'    <text x="{right_x + 24}" y="{text_y}" font-family="{font}" '
            f'font-size="{text_font}" font-style="italic" fill="{p["body"]}">{tspans}</text>'
        )

    content = "\n".join(parts)
    defs_content = "\n".join(defs_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n'
        f'{defs_content}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock, w, h)}\n'
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
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items
    mid = max(1, len(items) // 2)
    left_items = items[:mid]
    right_items = items[mid:]

    panel_w = (w - 220) // 2
    left_x = 90
    right_x = left_x + panel_w + 40  # 40px gap
    panel_y = 160
    panel_h = h - panel_y - 70

    parts: list[str] = []
    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]

    ca_left = p["accent"]
    ca_right = _hex_shift(p["accent"], 40)
    cs = card_style_params(lock, 0)

    defs_parts.append(
        f'    <linearGradient id="case-left-grad-{plan.index:02d}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
        f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
        f'    </linearGradient>'
    )
    defs_parts.append(
        f'    <clipPath id="case-left-clip-{plan.index:02d}">\n'
        f'      <rect x="{left_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="16" />\n'
        f'    </clipPath>'
    )
    defs_parts.append(
        f'    <linearGradient id="case-right-grad-{plan.index:02d}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
        f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
        f'    </linearGradient>'
    )
    defs_parts.append(
        f'    <clipPath id="case-right-clip-{plan.index:02d}">\n'
        f'      <rect x="{right_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="16" />\n'
        f'    </clipPath>'
    )

    parts.append(
        f'    <g clip-path="url(#case-left-clip-{plan.index:02d})">\n'
        f'      <rect x="{left_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" fill="url(#case-left-grad-{plan.index:02d})"/>\n'
        f'      <rect x="{left_x}" y="{panel_y}" width="{panel_w}" height="6" fill="{ca_left}" opacity="0.85"/>\n'
        f'    </g>'
    )
    parts.append(
        f'    <rect x="{left_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="16" fill="none" '
        f'stroke="{ca_left}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" filter="url(#card-shadow-{plan.index:02d})"/>'
    )
    if cs["inner_border"]:
        parts.append(
            f'    <rect x="{left_x + 6}" y="{panel_y + 6}" width="{panel_w - 12}" height="{panel_h - 12}" rx="12" fill="none" '
            f'stroke="{ca_left}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
        )
    
    # Left Header Badge
    parts.append(
        f'    <rect x="{left_x + 24}" y="{panel_y + 24}" width="70" height="20" rx="10" fill="{p["accent"]}" fill-opacity="0.15"/>'
    )
    parts.append(
        f'    <text x="{left_x + 59}" y="{panel_y + 38}" font-family="{font}" '
        f'font-size="15" font-weight="700" fill="{p["accent"]}" text-anchor="middle" letter-spacing="1">CASE</text>'
    )

    from .svg_pipeline import _wrap_to_tspans
    ly = panel_y + 75
    for item in left_items[:3]:
        text_font = 16
        line_h = 19
        text_w = panel_w - 48
        tspans, line_count = _wrap_to_tspans(item.primary, left_x + 24, text_font, text_w, line_height=1.25)
        parts.append(
            f'    <text x="{left_x + 24}" y="{ly}" font-family="{font}" '
            f'font-size="{text_font}" font-weight="600" fill="{p["text"]}">{tspans}</text>'
        )
        ly += line_count * line_h + 4
        if item.secondary:
            sub_font = 13
            sub_line_h = 16
            sub_tspans, sub_line_count = _wrap_to_tspans(item.secondary, left_x + 24, sub_font, text_w, line_height=1.2)
            parts.append(
                f'    <text x="{left_x + 24}" y="{ly}" font-family="{font}" '
                f'font-size="{sub_font}" fill="{p["body"]}" opacity="0.8">{sub_tspans}</text>'
            )
            ly += sub_line_count * sub_line_h + 8
        else:
            ly += 8

    # Vertical divider - Dashed line with central glowing orb
    div_x = left_x + panel_w + 20
    parts.append(
        f'    <line x1="{div_x}" y1="{panel_y + 20}" x2="{div_x}" y2="{panel_y + panel_h - 20}" '
        f'stroke="{p["accent"]}" stroke-opacity="0.25" stroke-width="1.5" stroke-dasharray="4 4"/>'
    )
    parts.append(
        f'    <circle cx="{div_x}" cy="{panel_y + panel_h // 2}" r="10" fill="{p["accent"]}" fill-opacity="0.08" stroke="{p["accent"]}" stroke-opacity="0.2" stroke-width="1"/>\n'
        f'    <circle cx="{div_x}" cy="{panel_y + panel_h // 2}" r="6" fill="{p["accent"]}" fill-opacity="0.16"/>\n'
        f'    <circle cx="{div_x}" cy="{panel_y + panel_h // 2}" r="3" fill="{p["accent"]}"/>'
    )

    parts.append(
        f'    <g clip-path="url(#case-right-clip-{plan.index:02d})">\n'
        f'      <rect x="{right_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" fill="url(#case-right-grad-{plan.index:02d})"/>\n'
        f'      <rect x="{right_x}" y="{panel_y}" width="{panel_w}" height="6" fill="{ca_right}" opacity="0.85"/>\n'
        f'    </g>'
    )
    parts.append(
        f'    <rect x="{right_x}" y="{panel_y}" width="{panel_w}" height="{panel_h}" rx="16" fill="none" '
        f'stroke="{ca_right}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" filter="url(#card-shadow-{plan.index:02d})"/>'
    )
    if cs["inner_border"]:
        parts.append(
            f'    <rect x="{right_x + 6}" y="{panel_y + 6}" width="{panel_w - 12}" height="{panel_h - 12}" rx="12" fill="none" '
            f'stroke="{ca_right}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
        )

    # Right Header Badge
    parts.append(
        f'    <rect x="{right_x + 24}" y="{panel_y + 24}" width="100" height="20" rx="10" fill="{p["accent"]}" fill-opacity="0.15"/>'
    )
    parts.append(
        f'    <text x="{right_x + 74}" y="{panel_y + 38}" font-family="{font}" '
        f'font-size="15" font-weight="700" fill="{p["accent"]}" text-anchor="middle" letter-spacing="1">ANALYSIS</text>'
    )

    from .svg_pipeline import _wrap_to_tspans
    ry = panel_y + 75
    for item in right_items[:3]:
        text_font = 16
        line_h = 19
        text_w = panel_w - 48
        tspans, line_count = _wrap_to_tspans(item.primary, right_x + 24, text_font, text_w, line_height=1.25)
        parts.append(
            f'    <text x="{right_x + 24}" y="{ry}" font-family="{font}" '
            f'font-size="{text_font}" font-weight="600" fill="{p["text"]}">{tspans}</text>'
        )
        ry += line_count * line_h + 4
        if item.secondary:
            sub_font = 13
            sub_line_h = 16
            sub_tspans, sub_line_count = _wrap_to_tspans(item.secondary, right_x + 24, sub_font, text_w, line_height=1.2)
            parts.append(
                f'    <text x="{right_x + 24}" y="{ry}" font-family="{font}" '
                f'font-size="{sub_font}" fill="{p["body"]}" opacity="0.8">{sub_tspans}</text>'
            )
            ry += sub_line_count * sub_line_h + 8
        else:
            ry += 8

    content = "\n".join(parts)
    defs_content = "\n".join(defs_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n'
        f'{defs_content}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock, w, h)}\n'
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
    with optional sub-questions listed below in beautiful cards.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h, intensity=0.15)
    title = xml_escape(plan.title)

    parts: list[str] = []
    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]

    # Centered design layout
    panel_y = 160
    panel_w = w - 240
    panel_x = 120

    # Header section with large glowing question mark circle
    badge_cy = panel_y + 50
    parts.append(
        f'    <!-- Orbital concentric rings -->\n'
        f'    <circle cx="{w // 2}" cy="{badge_cy}" r="52" fill="none" stroke="{p["accent"]}" stroke-opacity="0.04" stroke-width="1" stroke-dasharray="2 4"/>\n'
        f'    <circle cx="{w // 2}" cy="{badge_cy}" r="46" fill="none" stroke="{p["accent"]}" stroke-opacity="0.08" stroke-width="1.5" stroke-dasharray="4 6"/>\n'
        f'    <!-- Glowing bubble -->\n'
        f'    <circle cx="{w // 2}" cy="{badge_cy}" r="38" '
        f'fill="{p["accent"]}" fill-opacity="0.08" stroke="{p["accent"]}" stroke-opacity="0.2" stroke-width="1"/>\n'
        f'    <circle cx="{w // 2}" cy="{badge_cy}" r="30" '
        f'fill="{p["accent"]}" fill-opacity="0.14" stroke="{p["accent"]}" stroke-opacity="0.4" stroke-width="1"/>\n'
        f'    <text x="{w // 2}" y="{badge_cy + 13}" font-family="{font}" '
        f'font-size="38" font-weight="700" fill="{p["accent"]}" '
        f'text-anchor="middle">?</text>'
    )

    # Main question/prompt inside a premium frosted glass card
    main_q = xml_escape(plan.items[0].primary) if plan.items else ""
    q_len = len(main_q)
    q_font = 24 if q_len <= 30 else (20 if q_len <= 50 else 16)
    
    card_h = 100
    disc_cs = card_style_params(lock, 0)

    defs_parts.append(
        f'    <linearGradient id="disc-main-grad-{plan.index:02d}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{disc_cs["fill_opacity_start"]}"/>\n'
        f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{disc_cs["fill_opacity_end"]}"/>\n'
        f'    </linearGradient>'
    )
    defs_parts.append(
        f'    <clipPath id="disc-main-clip-{plan.index:02d}">\n'
        f'      <rect x="{panel_x}" y="{panel_y + 110}" width="{panel_w}" height="{card_h}" rx="14" />\n'
        f'    </clipPath>'
    )

    parts.append(
        f'    <g clip-path="url(#disc-main-clip-{plan.index:02d})">\n'
        f'      <rect x="{panel_x}" y="{panel_y + 110}" width="{panel_w}" height="{card_h}" fill="url(#disc-main-grad-{plan.index:02d})"/>\n'
        f'      <rect x="{panel_x}" y="{panel_y + 110}" width="{panel_w}" height="5" fill="{p["accent"]}" opacity="0.85"/>\n'
        f'    </g>'
    )
    parts.append(
        f'    <rect x="{panel_x}" y="{panel_y + 110}" width="{panel_w}" height="{card_h}" rx="14" fill="none" '
        f'stroke="{p["accent"]}" stroke-opacity="{disc_cs["stroke_opacity"]}" stroke-width="{disc_cs["stroke_width"]}" filter="url(#card-shadow-{plan.index:02d})"/>'
    )
    if disc_cs["inner_border"]:
        parts.append(
            f'    <rect x="{panel_x + 6}" y="{panel_y + 116}" width="{panel_w - 12}" height="{card_h - 12}" rx="10" fill="none" '
            f'stroke="{p["accent"]}" stroke-opacity="{disc_cs["inner_stroke_opacity"]}" stroke-width="{disc_cs["inner_stroke_width"]}"/>'
        )
    
    # Left quote decorator
    parts.append(
        f'    <text x="{panel_x + 36}" y="{panel_y + 156}" font-family="Georgia, serif" font-size="54" '
        f'font-weight="700" fill="{p["accent"]}" opacity="0.12" text-anchor="middle">“</text>'
    )

    from .svg_pipeline import _wrap_to_tspans
    text_w = panel_w - 96
    line_h = int(q_font * 1.3)
    tspans, line_count = _wrap_to_tspans(main_q, w // 2, q_font, text_w, line_height=1.3)
    text_y = panel_y + 110 + (card_h - (line_count - 1) * line_h) // 2 + 5
    parts.append(
        f'    <text x="{w // 2}" y="{text_y}" font-family="{font}" '
        f'font-size="{q_font}" font-weight="600" fill="{p["text"]}" '
        f'text-anchor="middle">{tspans}</text>'
    )

    # DISCUSSION badge at the bottom of main card
    badge_w = 110
    badge_x = w // 2 - badge_w // 2
    parts.append(
        f'    <rect x="{badge_x}" y="{panel_y + 198}" width="{badge_w}" height="22" '
        f'rx="11" fill="{p["accent"]}" fill-opacity="0.12" stroke="{p["accent"]}" stroke-opacity="0.2"/>'
    )
    parts.append(
        f'    <text x="{w // 2}" y="{panel_y + 213}" font-family="{font}" font-size="14" '
        f'font-weight="700" fill="{p["accent"]}" text-anchor="middle" letter-spacing="1">DISCUSSION</text>'
    )

    # Sub-questions listed as horizontal cards below
    sub_questions = plan.items[1:3]
    if sub_questions:
        sub_y = panel_y + 240
        sub_card_w = (panel_w - 24) // len(sub_questions)
        for idx, item in enumerate(sub_questions):
            sub_x = panel_x + idx * (sub_card_w + 24)
            text = xml_escape(item.primary[:100])
            ca_sub = _hex_shift(p["accent"], idx * 20 - 10)
            
            sub_cs = card_style_params(lock, idx)
            grad_id = f"disc-sub-grad-{plan.index:02d}-{idx}"
            clip_id = f"disc-sub-clip-{plan.index:02d}-{idx}"

            defs_parts.append(
                f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
                f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{sub_cs["fill_opacity_start"]}"/>\n'
                f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -5)}" stop-opacity="{sub_cs["fill_opacity_end"]}"/>\n'
                f'    </linearGradient>'
            )
            defs_parts.append(
                f'    <clipPath id="{clip_id}">\n'
                f'      <rect x="{sub_x}" y="{sub_y}" width="{sub_card_w}" height="60" rx="10" />\n'
                f'    </clipPath>'
            )
            
            parts.append(
                f'    <g clip-path="url(#{clip_id})">\n'
                f'      <rect x="{sub_x}" y="{sub_y}" width="{sub_card_w}" height="60" fill="url(#{grad_id})"/>\n'
                f'      <rect x="{sub_x}" y="{sub_y}" width="4" height="60" fill="{ca_sub}" opacity="0.8"/>\n'
                f'    </g>'
            )
            parts.append(
                f'    <rect x="{sub_x}" y="{sub_y}" width="{sub_card_w}" height="60" rx="10" fill="none" '
                f'stroke="{ca_sub}" stroke-opacity="{sub_cs["stroke_opacity"]}" stroke-width="{sub_cs["stroke_width"]}"/>'
            )
            
            # Concentric glowing bullet for sub-question
            bullet_cx = sub_x + 22
            bullet_cy = sub_y + 30
            parts.append(
                f'    <circle cx="{bullet_cx}" cy="{bullet_cy}" r="5" fill="{ca_sub}" fill-opacity="0.15" stroke="{ca_sub}" stroke-opacity="0.3" stroke-width="1"/>\n'
                f'    <circle cx="{bullet_cx}" cy="{bullet_cy}" r="2" fill="{ca_sub}"/>'
            )
            
            # Sub-question text wrapped dynamically
            from .svg_pipeline import _wrap_to_tspans
            text_w = sub_card_w - 54
            text_font = 16
            line_h = 16
            tspans, line_count = _wrap_to_tspans(item.primary, sub_x + 36, text_font, text_w, line_height=1.25)
            text_y = sub_y + (60 - (line_count - 1) * line_h) // 2 + 4
            parts.append(
                f'    <text x="{sub_x + 36}" y="{text_y}" font-family="{font}" '
                f'font-size="{text_font}" font-weight="500" fill="{p["text"]}">{tspans}</text>'
            )

    content = "\n".join(parts)
    defs_content = "\n".join(defs_parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n'
        f'{defs_content}\n'
        f'  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock, w, h)}\n'
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
