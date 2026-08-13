"""Competition-domain SVG renderers for slide-skill v3.0.

Provides specialized layouts for competition / pitch / defense presentations:
  - team-grid:         Team members in a card grid (photo placeholder + name + role)
  - metrics-dashboard: Key metrics in large number + label cards
  - timeline:          Horizontal milestone timeline
  - comparison-matrix: Two-column comparison (ours vs. theirs)

All renderers share the same chrome/decor pattern via svg_shared.
"""

from __future__ import annotations

import re

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
from .text_wrap import fitted_tspans
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
# Team Grid Layout
# ---------------------------------------------------------------------------

def render_team_grid(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a team members slide.

    Layout: Up to 4 team member cards in a row.
    Each card: avatar circle placeholder + name + role.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items[:4]
    count = max(len(items), 1)
    
    card_w = (w - 180 - (count - 1) * 32) // count
    card_h = 360
    card_y = 180

    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]
    parts: list[str] = []

    for i, item in enumerate(items):
        cx = 90 + i * (card_w + 32)
        mid_x = cx + card_w // 2
        name = xml_escape(item.primary[:30])
        role = xml_escape(item.secondary[:40]) if item.secondary else (xml_escape(item.meta.get("role", "")) if item.meta else "")

        ca = _hex_shift(p["accent"], i * 15 - 30)
        cs = card_style_params(lock, i)
        grad_id = f"team-card-grad-{plan.index:02d}-{i}"
        clip_id = f"team-card-clip-{plan.index:02d}-{i}"

        defs_parts.append(
            f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
            f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
            f'    </linearGradient>'
        )
        defs_parts.append(
            f'    <clipPath id="{clip_id}">\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="16" />\n'
            f'    </clipPath>'
        )

        parts.append(
            f'    <g clip-path="url(#{clip_id})">\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" fill="url(#{grad_id})"/>\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="5" fill="{ca}" opacity="0.85"/>\n'
            f'    </g>'
        )

        parts.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="16" fill="none" '
            f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" '
            f'filter="url(#card-shadow-{plan.index:02d})"/>'
        )

        if cs["inner_border"]:
            parts.append(
                f'    <rect x="{cx + 6}" y="{card_y + 6}" width="{card_w - 12}" height="{card_h - 12}" rx="12" fill="none" '
                f'stroke="{ca}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
            )

        # Avatar circle placeholder with concentric orbital rings and glowing inner circles
        avatar_cy = card_y + 100
        # Outer orbital dashed ring
        parts.append(
            f'    <circle cx="{mid_x}" cy="{avatar_cy}" r="58" fill="none" '
            f'stroke="{ca}" stroke-opacity="0.2" stroke-width="1" stroke-dasharray="3 3"/>'
        )
        # Inner orbital dashed ring
        parts.append(
            f'    <circle cx="{mid_x}" cy="{avatar_cy}" r="54" fill="none" '
            f'stroke="{ca}" stroke-opacity="0.15" stroke-width="1"/>'
        )
        # Concentric glowing inner circle (glowing double-ring)
        parts.append(
            f'    <circle cx="{mid_x}" cy="{avatar_cy}" r="46" '
            f'fill="{ca}" fill-opacity="0.12" stroke="{ca}" stroke-opacity="0.25" stroke-width="1"/>'
        )
        # Concentric inner overlay circle
        parts.append(
            f'    <circle cx="{mid_x}" cy="{avatar_cy}" r="38" '
            f'fill="{ca}" fill-opacity="0.08"/>'
        )

        # Initials in circle
        initials = name[0] if name else "?"
        parts.append(
            f'    <text x="{mid_x}" y="{avatar_cy + 10}" font-family="{font}" '
            f'font-size="28" font-weight="700" fill="{ca}" '
            f'text-anchor="middle">{initials}</text>'
        )

        # Name
        parts.append(
            f'    <text x="{mid_x}" y="{avatar_cy + 90}" font-family="{font}" '
            f'font-size="22" font-weight="600" fill="{p["text"]}" '
            f'text-anchor="middle">{name}</text>'
        )

        # Role badge or description paragraph (no capsule badge if description is long, just beautiful wrapped paragraph)
        if role:
            from .svg_pipeline import _wrap_to_tspans
            text_w = card_w - 36
            # Use smaller font if text is extremely long
            text_font = 16 if len(role) > 30 else 17
            line_h = text_font + 4
            tspans, line_count = _wrap_to_tspans(role, mid_x, text_font, text_w, line_height=1.3)
            
            if len(role) < 12:
                badge_h = 24
                badge_w = 110
                badge_x = mid_x - badge_w // 2
                badge_y = avatar_cy + 112
                parts.append(
                    f'    <rect x="{badge_x}" y="{badge_y}" width="{badge_w}" height="{badge_h}" rx="12" '
                    f'fill="{ca}" fill-opacity="0.08" stroke="{ca}" stroke-opacity="0.25" stroke-width="1"/>'
                )
                text_y = badge_y + 16
                parts.append(
                    f'    <text x="{mid_x}" y="{text_y}" font-family="{font}" '
                    f'font-size="{text_font}" font-weight="600" fill="{ca}" '
                    f'text-anchor="middle">{tspans}</text>'
                )
            else:
                # Centered multiline body text block for description (much cleaner & more premium)
                text_y = avatar_cy + 120
                parts.append(
                    f'    <text x="{mid_x}" y="{text_y}" font-family="{font}" '
                    f'font-size="{text_font}" font-weight="500" fill="{p["text"]}" '
                    f'text-anchor="middle" opacity="0.75">{tspans}</text>'
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
        f'  <g id="content-team-{plan.index:02d}">\n'
        f'{content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Metrics Dashboard Layout
# ---------------------------------------------------------------------------

def render_metrics_dashboard(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a metrics/KPI dashboard slide.

    Layout: 3-4 large metric cards showing a number + label.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h, intensity=0.10)
    title = xml_escape(plan.title)

    items = plan.items[:4]
    count = max(len(items), 1)
    
    card_w = (w - 180 - (count - 1) * 32) // count
    card_h = 320
    card_y = 190

    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]
    parts: list[str] = []

    def _looks_metric_value(text: str) -> bool:
        return bool(re.search(r"[$¥€£]?\s*\d|[%％]|x\b|\b[KMGB]\b|[万亿]", text, re.IGNORECASE))

    def _metric_value_and_label(item) -> tuple[str, str]:
        primary = item.primary.strip()
        secondary = (item.secondary or item.meta.get("label", "") if item.meta else item.secondary or "").strip()
        if secondary and _looks_metric_value(secondary) and not _looks_metric_value(primary):
            return secondary, primary
        return primary, secondary

    for i, item in enumerate(items):
        cx = 90 + i * (card_w + 32)
        mid_x = cx + card_w // 2
        
        metric_value, metric_label = _metric_value_and_label(item)

        ca = _hex_shift(p["accent"], i * 15 - 30)
        cs = card_style_params(lock, i)
        grad_id = f"metric-card-grad-{plan.index:02d}-{i}"
        clip_id = f"metric-card-clip-{plan.index:02d}-{i}"

        defs_parts.append(
            f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
            f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
            f'    </linearGradient>'
        )
        defs_parts.append(
            f'    <clipPath id="{clip_id}">\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="16" />\n'
            f'    </clipPath>'
        )

        parts.append(
            f'    <g clip-path="url(#{clip_id})">\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" fill="url(#{grad_id})"/>\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="5" fill="{ca}" opacity="0.85"/>\n'
            f'    </g>'
        )

        parts.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="16" fill="none" '
            f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" '
            f'filter="url(#card-shadow-{plan.index:02d})"/>'
        )

        if cs["inner_border"]:
            parts.append(
                f'    <rect x="{cx + 6}" y="{card_y + 6}" width="{card_w - 12}" height="{card_h - 12}" rx="12" fill="none" '
                f'stroke="{ca}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
            )
        
        value_w = card_w - 44
        value_h = 92
        value_tspans, value_lines, value_font, value_dy = fitted_tspans(
            metric_value,
            mid_x,
            value_w,
            value_h,
            max_font_size=46,
            min_font_size=20,
            line_height=1.08,
        )
        value_y = card_y + 108 - max(0, value_lines - 1) * value_dy // 2

        parts.append(
            f'    <text x="{mid_x}" y="{value_y}" font-family="{font}" '
            f'font-size="{value_font}" font-weight="800" fill="{ca}" '
            f'text-anchor="middle" data-fit-box="{mid_x - value_w // 2},{value_y - value_font},{value_w},{value_h}" '
            f'data-line-height="1.08">{value_tspans}</text>'
        )
        
        # Label card sub-panel upgraded to fine border glass box
        if metric_label:
            text_w = card_w - 48
            label_h = 68
            tspans, line_count, text_font, line_h = fitted_tspans(
                metric_label,
                mid_x,
                text_w,
                label_h - 16,
                max_font_size=18,
                min_font_size=12,
                line_height=1.2,
            )
            text_y = card_y + 185 + (68 - (line_count - 1) * line_h) // 2 + 4
            parts.append(
                f'    <rect x="{cx + 16}" y="{card_y + 185}" width="{card_w - 32}" height="68" rx="10" '
                f'fill="{ca}" fill-opacity="0.04" stroke="{ca}" stroke-opacity="0.2" stroke-width="1"/>'
            )
            parts.append(
                f'    <rect x="{cx + 20}" y="{card_y + 189}" width="{card_w - 40}" height="60" rx="8" fill="none" '
                f'stroke="{ca}" stroke-opacity="0.08" stroke-width="1"/>'
            )
            parts.append(
                f'    <text x="{mid_x}" y="{text_y}" font-family="{font}" '
                f'font-size="{text_font}" font-weight="600" fill="{p["text"]}" '
                f'text-anchor="middle" data-fit-box="{mid_x - text_w // 2},{card_y + 193},{text_w},{label_h - 16}" '
                f'data-line-height="1.2">{tspans}</text>'
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
        f'  <g id="content-metrics-{plan.index:02d}">\n'
        f'{content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Timeline Layout
# ---------------------------------------------------------------------------

def render_timeline(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a horizontal milestone timeline.

    Layout: Central horizontal line with milestone dots and labels above/below in beautiful cards.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    t = _tokens(w, h)
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items[:6]
    count = max(len(items), 1)

    line_y = h // 2 + 30
    line_left = 120
    line_right = w - 120
    line_w = line_right - line_left

    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]
    parts: list[str] = []

    # Central horizontal line (premium dashed stroke with glowing underglow)
    # Underglow line
    parts.append(
        f'    <line x1="{line_left}" y1="{line_y}" x2="{line_right}" y2="{line_y}" '
        f'stroke="{p["accent"]}" stroke-opacity="0.15" stroke-width="6"/>'
    )
    # Main dashed line
    parts.append(
        f'    <line x1="{line_left}" y1="{line_y}" x2="{line_right}" y2="{line_y}" '
        f'stroke="{p["accent"]}" stroke-opacity="0.4" stroke-width="2" stroke-dasharray="6 4"/>'
    )

    for i, item in enumerate(items):
        dot_x = line_left + int((i / max(count - 1, 1)) * line_w)
        milestone = xml_escape(item.primary[:30])
        date_label = xml_escape(item.secondary[:20]) if item.secondary else (xml_escape(item.meta.get("quarter", "")) if item.meta else "")

        ca = _hex_shift(p["accent"], i * 12 - 24)

        # Milestone dot (3-tier concentric glowing timeline orbs)
        parts.append(
            f'    <circle cx="{dot_x}" cy="{line_y}" r="24" '
            f'fill="{ca}" fill-opacity="0.05" stroke="{ca}" stroke-opacity="0.15" stroke-width="1"/>'
        )
        parts.append(
            f'    <circle cx="{dot_x}" cy="{line_y}" r="16" '
            f'fill="{ca}" fill-opacity="0.12" stroke="{ca}" stroke-opacity="0.25" stroke-dasharray="2 2"/>'
        )
        parts.append(
            f'    <circle cx="{dot_x}" cy="{line_y}" r="8" fill="{ca}"/>'
        )
        parts.append(
            f'    <circle cx="{dot_x}" cy="{line_y}" r="4" fill="#FFFFFF" fill-opacity="0.8"/>'
        )

        # Alternate card position (above/below)
        card_w = 160
        card_h = 90

        cs = card_style_params(lock, i)
        grad_id = f"timeline-card-grad-{plan.index:02d}-{i}"
        clip_id = f"timeline-card-clip-{plan.index:02d}-{i}"

        if i % 2 == 0:
            cx = dot_x - card_w // 2
            cy = line_y - card_h - 40

            parts.append(
                f'    <line x1="{dot_x}" y1="{line_y}" x2="{dot_x}" y2="{cy + card_h}" '
                f'stroke="{ca}" stroke-opacity="0.2" stroke-width="1.5" stroke-dasharray="2 2"/>'
            )

            defs_parts.append(
                f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
                f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
                f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
                f'    </linearGradient>'
            )
            defs_parts.append(
                f'    <clipPath id="{clip_id}">\n'
                f'      <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" rx="12" />\n'
                f'    </clipPath>'
            )

            parts.append(
                f'    <g clip-path="url(#{clip_id})">\n'
                f'      <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" fill="url(#{grad_id})"/>\n'
                f'      <rect x="{cx}" y="{cy + card_h - 4}" width="{card_w}" height="4" fill="{ca}" opacity="0.85"/>\n'
                f'    </g>'
            )

            parts.append(
                f'    <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" rx="12" fill="none" '
                f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" '
                f'filter="url(#card-shadow-{plan.index:02d})"/>'
            )

            if cs["inner_border"]:
                parts.append(
                    f'    <rect x="{cx + 4}" y="{cy + 4}" width="{card_w - 8}" height="{card_h - 8}" rx="8" fill="none" '
                    f'stroke="{ca}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
                )
            
            # Text inside card wrapped dynamically
            from .svg_pipeline import _wrap_to_tspans
            text_w = card_w - 16
            text_font = 15 if len(milestone) > 8 else 17
            dy_p = int(text_font * 1.25)
            
            tspans, line_count = _wrap_to_tspans(milestone, dot_x, text_font, text_w, line_height=1.25)
            p_h = line_count * dy_p
            
            sub_tspans, sub_line_count = "", 0
            s_h = 0
            sub_font = 12 if date_label and len(date_label) > 10 else 13
            dy_s = int(sub_font * 1.2)
            if date_label:
                sub_tspans, sub_line_count = _wrap_to_tspans(date_label, dot_x, sub_font, text_w, line_height=1.2)
                s_h = sub_line_count * dy_s
                
            text_h = p_h + (s_h + 6 if date_label else 0)
            text_padding = (card_h - text_h) // 2
            
            py = cy + text_padding + text_font - 2
            parts.append(
                f'    <text x="{dot_x}" y="{py}" font-family="{font}" '
                f'font-size="{text_font}" font-weight="700" fill="{p["text"]}" '
                f'text-anchor="middle">{tspans}</text>'
            )
            
            if date_label:
                sy = py + p_h + 6 - (text_font - sub_font) // 2
                parts.append(
                    f'    <text x="{dot_x}" y="{sy}" font-family="{font}" '
                    f'font-size="{sub_font}" font-weight="600" fill="{ca}" '
                    f'text-anchor="middle">{sub_tspans}</text>'
                )
        else:
            # Card below timeline
            cx = dot_x - card_w // 2
            cy = line_y + 40
            
            # Connector vertical line
            parts.append(
                f'    <line x1="{dot_x}" y1="{line_y}" x2="{dot_x}" y2="{cy}" '
                f'stroke="{ca}" stroke-opacity="0.2" stroke-width="1.5" stroke-dasharray="2 2"/>'
            )
            
            defs_parts.append(
                f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
                f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{cs["fill_opacity_start"]}"/>\n'
                f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{cs["fill_opacity_end"]}"/>\n'
                f'    </linearGradient>'
            )
            defs_parts.append(
                f'    <clipPath id="{clip_id}">\n'
                f'      <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" rx="12" />\n'
                f'    </clipPath>'
            )

            parts.append(
                f'    <g clip-path="url(#{clip_id})">\n'
                f'      <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" fill="url(#{grad_id})"/>\n'
                f'      <rect x="{cx}" y="{cy}" width="{card_w}" height="4" fill="{ca}" opacity="0.85"/>\n'
                f'    </g>'
            )

            parts.append(
                f'    <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" rx="12" fill="none" '
                f'stroke="{ca}" stroke-opacity="{cs["stroke_opacity"]}" stroke-width="{cs["stroke_width"]}" '
                f'filter="url(#card-shadow-{plan.index:02d})"/>'
            )

            if cs["inner_border"]:
                parts.append(
                    f'    <rect x="{cx + 4}" y="{cy + 4}" width="{card_w - 8}" height="{card_h - 8}" rx="8" fill="none" '
                    f'stroke="{ca}" stroke-opacity="{cs["inner_stroke_opacity"]}" stroke-width="{cs["inner_stroke_width"]}"/>'
                )
            
            # Text inside card wrapped dynamically
            from .svg_pipeline import _wrap_to_tspans
            text_w = card_w - 16
            text_font = 15 if len(milestone) > 8 else 17
            dy_p = int(text_font * 1.25)
            
            tspans, line_count = _wrap_to_tspans(milestone, dot_x, text_font, text_w, line_height=1.25)
            p_h = line_count * dy_p
            
            sub_tspans, sub_line_count = "", 0
            s_h = 0
            sub_font = 12 if date_label and len(date_label) > 10 else 13
            dy_s = int(sub_font * 1.2)
            if date_label:
                sub_tspans, sub_line_count = _wrap_to_tspans(date_label, dot_x, sub_font, text_w, line_height=1.2)
                s_h = sub_line_count * dy_s
                
            text_h = p_h + (s_h + 6 if date_label else 0)
            text_padding = (card_h - text_h) // 2
            
            py = cy + text_padding + text_font - 2
            parts.append(
                f'    <text x="{dot_x}" y="{py}" font-family="{font}" '
                f'font-size="{text_font}" font-weight="700" fill="{p["text"]}" '
                f'text-anchor="middle">{tspans}</text>'
            )
            
            if date_label:
                sy = py + p_h + 6 - (text_font - sub_font) // 2
                parts.append(
                    f'    <text x="{dot_x}" y="{sy}" font-family="{font}" '
                    f'font-size="{sub_font}" font-weight="600" fill="{ca}" '
                    f'text-anchor="middle">{sub_tspans}</text>'
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
        f'  <g id="content-timeline-{plan.index:02d}">\n'
        f'{content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Comparison Matrix Layout
# ---------------------------------------------------------------------------

def render_comparison_matrix(plan: SlidePlan, lock: dict, total: int) -> str:
    """Render a two-column comparison slide (Ours vs. Theirs / Before vs. After).

    Layout: Two columns with header badges, items listed vertically with green checkmarks or red crosses.
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

    col_w = (w - 220) // 2
    left_x = 90
    right_x = left_x + col_w + 40
    col_y = 160
    col_h = h - col_y - 70

    # Determine column headers from meta or defaults
    left_header = "OURS"
    right_header = "THEIRS"
    if plan.meta:
        left_header = plan.meta.get("left_header", left_header)
        right_header = plan.meta.get("right_header", right_header)
    if items and items[0].meta:
        left_header = items[0].meta.get("left_header", left_header)
        right_header = items[0].meta.get("right_header", right_header)

    ca_left = p["accent"]
    ca_right = _hex_shift(p["accent"], 60)

    grad_left_id = f"comp-matrix-grad-left-{plan.index:02d}"
    clip_left_id = f"comp-matrix-clip-left-{plan.index:02d}"
    grad_right_id = f"comp-matrix-grad-right-{plan.index:02d}"
    clip_right_id = f"comp-matrix-clip-right-{plan.index:02d}"

    comp_cs = card_style_params(lock, 0)
    comp_cs2 = card_style_params(lock, 1)

    defs_parts: list[str] = [
        _shadow_filter_def(plan.index),
        orb_defs
    ]
    parts: list[str] = []

    defs_parts.append(
        f'    <linearGradient id="{grad_left_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{comp_cs["fill_opacity_start"]}"/>\n'
        f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -10)}" stop-opacity="{comp_cs["fill_opacity_end"]}"/>\n'
        f'    </linearGradient>'
    )
    defs_parts.append(
        f'    <clipPath id="{clip_left_id}">\n'
        f'      <rect x="{left_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="16" />\n'
        f'    </clipPath>'
    )

    defs_parts.append(
        f'    <linearGradient id="{grad_right_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="{comp_cs2["fill_opacity_start"]}"/>\n'
        f'      <stop offset="100%" stop-color="{_hex_shift(p["surface"], -15)}" stop-opacity="{comp_cs2["fill_opacity_end"]}"/>\n'
        f'    </linearGradient>'
    )
    defs_parts.append(
        f'    <clipPath id="{clip_right_id}">\n'
        f'      <rect x="{right_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="16" />\n'
        f'    </clipPath>'
    )

    parts.append(
        f'    <g clip-path="url(#{clip_left_id})">\n'
        f'      <rect x="{left_x}" y="{col_y}" width="{col_w}" height="{col_h}" fill="url(#{grad_left_id})"/>\n'
        f'      <rect x="{left_x}" y="{col_y}" width="{col_w}" height="5" fill="{ca_left}" opacity="0.85"/>\n'
        f'    </g>'
    )

    parts.append(
        f'    <rect x="{left_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="16" fill="none" '
        f'stroke="{ca_left}" stroke-opacity="{comp_cs["stroke_opacity"]}" stroke-width="{comp_cs["stroke_width"]}" '
        f'filter="url(#card-shadow-{plan.index:02d})"/>'
    )

    if comp_cs["inner_border"]:
        parts.append(
            f'    <rect x="{left_x + 6}" y="{col_y + 6}" width="{col_w - 12}" height="{col_h - 12}" rx="12" fill="none" '
            f'stroke="{ca_left}" stroke-opacity="{comp_cs["inner_stroke_opacity"]}" stroke-width="{comp_cs["inner_stroke_width"]}"/>'
        )

    # Left header: Glowing status pill Left
    parts.append(
        f'    <rect x="{left_x + col_w // 2 - 60}" y="{col_y + 20}" width="120" height="26" rx="13" '
        f'fill="{ca_left}" fill-opacity="0.1" stroke="{ca_left}" stroke-opacity="0.3" stroke-width="1"/>'
    )
    parts.append(
        f'    <rect x="{left_x + col_w // 2 - 56}" y="{col_y + 24}" width="112" height="18" rx="9" fill="none" '
        f'stroke="{ca_left}" stroke-opacity="0.1" stroke-width="1"/>'
    )
    parts.append(
        f'    <text x="{left_x + col_w // 2}" y="{col_y + 37}" font-family="{font}" '
        f'font-size="15" font-weight="700" fill="{ca_left}" '
        f'text-anchor="middle" letter-spacing="1">{xml_escape(left_header)}</text>'
    )
    
    from .svg_pipeline import _wrap_to_tspans
    ly = col_y + 80
    for item in left_items[:5]:
        text_font = 15
        line_h = 18
        text_w = col_w - 72
        tspans, line_count = _wrap_to_tspans(item.primary, left_x + 58, text_font, text_w, line_height=1.2)
        cx_ = left_x + 36
        cy_ = ly - 5
        parts.append(
            f'    <circle cx="{cx_}" cy="{cy_}" r="11" fill="#10B981" fill-opacity="0.08" stroke="#10B981" stroke-opacity="0.25" stroke-width="1"/>'
        )
        parts.append(
            f'    <circle cx="{cx_}" cy="{cy_}" r="8" fill="#10B981" fill-opacity="0.12"/>'
        )
        parts.append(
            f'    <text x="{cx_}" y="{cy_ + 4}" font-family="{font}" font-size="15" '
            f'font-weight="700" fill="#10B981" text-anchor="middle">✓</text>'
        )
        parts.append(
            f'    <text x="{left_x + 58}" y="{ly}" font-family="{font}" '
            f'font-size="{text_font}" font-weight="500" fill="{p["text"]}">{tspans}</text>'
        )
        ly += max(42, line_count * line_h + 12)

    parts.append(
        f'    <g clip-path="url(#{clip_right_id})">\n'
        f'      <rect x="{right_x}" y="{col_y}" width="{col_w}" height="{col_h}" fill="url(#{grad_right_id})"/>\n'
        f'      <rect x="{right_x}" y="{col_y}" width="{col_w}" height="5" fill="{ca_right}" opacity="0.7"/>\n'
        f'    </g>'
    )

    parts.append(
        f'    <rect x="{right_x}" y="{col_y}" width="{col_w}" height="{col_h}" rx="16" fill="none" '
        f'stroke="{ca_right}" stroke-opacity="{comp_cs2["stroke_opacity"]}" stroke-width="{comp_cs2["stroke_width"]}" '
        f'filter="url(#card-shadow-{plan.index:02d})"/>'
    )

    if comp_cs2["inner_border"]:
        parts.append(
            f'    <rect x="{right_x + 6}" y="{col_y + 6}" width="{col_w - 12}" height="{col_h - 12}" rx="12" fill="none" '
            f'stroke="{ca_right}" stroke-opacity="{comp_cs2["inner_stroke_opacity"]}" stroke-width="{comp_cs2["inner_stroke_width"]}"/>'
        )

    # Right header: Glowing status pill Right
    parts.append(
        f'    <rect x="{right_x + col_w // 2 - 60}" y="{col_y + 20}" width="120" height="26" rx="13" '
        f'fill="{ca_right}" fill-opacity="0.06" stroke="{ca_right}" stroke-opacity="0.2" stroke-width="1"/>'
    )
    parts.append(
        f'    <rect x="{right_x + col_w // 2 - 56}" y="{col_y + 24}" width="112" height="18" rx="9" fill="none" '
        f'stroke="{ca_right}" stroke-opacity="0.08" stroke-width="1"/>'
    )
    parts.append(
        f'    <text x="{right_x + col_w // 2}" y="{col_y + 37}" font-family="{font}" '
        f'font-size="15" font-weight="700" fill="{p["muted"]}" '
        f'text-anchor="middle" letter-spacing="1">{xml_escape(right_header)}</text>'
    )
    
    from .svg_pipeline import _wrap_to_tspans
    ry = col_y + 80
    for item in right_items[:5]:
        text_font = 15
        line_h = 18
        text_w = col_w - 72
        tspans, line_count = _wrap_to_tspans(item.primary, right_x + 58, text_font, text_w, line_height=1.2)
        cx_ = right_x + 36
        cy_ = ry - 5
        parts.append(
            f'    <circle cx="{cx_}" cy="{cy_}" r="11" fill="#EF4444" fill-opacity="0.06" stroke="#EF4444" stroke-opacity="0.18" stroke-width="1"/>'
        )
        parts.append(
            f'    <circle cx="{cx_}" cy="{cy_}" r="8" fill="#EF4444" fill-opacity="0.08"/>'
        )
        parts.append(
            f'    <text x="{cx_}" y="{cy_ + 4}" font-family="{font}" font-size="15" '
            f'font-weight="700" fill="#EF4444" text-anchor="middle">✗</text>'
        )
        parts.append(
            f'    <text x="{right_x + 58}" y="{ry}" font-family="{font}" '
            f'font-size="{text_font}" font-weight="500" fill="{p["body"]}">{tspans}</text>'
        )
        ry += max(42, line_count * line_h + 12)

    # Middle vertical divider - Dashed line with central glowing node
    div_x = left_x + col_w + 20
    # Underglow line
    parts.append(
        f'    <line x1="{div_x}" y1="{col_y + 20}" x2="{div_x}" y2="{col_y + col_h - 20}" '
        f'stroke="{p["accent"]}" stroke-opacity="0.08" stroke-width="4"/>'
    )
    # Main divider line
    parts.append(
        f'    <line x1="{div_x}" y1="{col_y + 20}" x2="{div_x}" y2="{col_y + col_h - 20}" '
        f'stroke="{p["accent"]}" stroke-opacity="0.2" stroke-width="1.5" stroke-dasharray="4 4"/>'
    )
    # Center glowing status orb
    div_cy = col_y + col_h // 2
    parts.append(
        f'    <circle cx="{div_x}" cy="{div_cy}" r="14" fill="{p["background"]}" stroke="{p["accent"]}" stroke-opacity="0.15" stroke-width="1.5"/>'
    )
    parts.append(
        f'    <circle cx="{div_x}" cy="{div_cy}" r="8" fill="{p["accent"]}" fill-opacity="0.12" stroke="{p["accent"]}" stroke-opacity="0.4" stroke-dasharray="1 1"/>'
    )
    parts.append(
        f'    <circle cx="{div_x}" cy="{div_cy}" r="4" fill="{p["accent"]}"/>'
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
        f'  <g id="content-comparison-{plan.index:02d}">\n'
        f'{content}\n'
        f'  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

COMPETITION_RENDERERS: dict[str, callable] = {
    "team-grid": render_team_grid,
    "metrics-dashboard": render_metrics_dashboard,
    "timeline": render_timeline,
    "comparison-matrix": render_comparison_matrix,
}


def render_competition_slide(plan: SlidePlan, lock: dict, total: int) -> str | None:
    """Try to render a competition-specific layout. Returns None if layout is not competition."""
    renderer = COMPETITION_RENDERERS.get(plan.layout)
    if renderer is None:
        return None
    return renderer(plan, lock, total)
