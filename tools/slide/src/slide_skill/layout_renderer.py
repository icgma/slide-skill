"""Template-driven rendering engine — bridges LayoutTemplate → SVG.

This module maps template names to render functions and provides the
AI-friendly entry point: given a SlidePlan + template name, produce SVG.

NOTE (v4 scaffold): This module is scaffolding for the template-driven
architecture. It is not yet wired into the main rendering pipeline
(svg_pipeline.generate_svg / generate_svg_from_plan). Integration will
happen in a future milestone. For now, the existing domain renderers
continue to serve all layout needs.
"""

from __future__ import annotations

import re

from .content_planner import ContentItem, SlidePlan
from .layout_templates import LayoutTemplate, SlotSpec, get_template
from .svg_shared import (
    adaptive_title_font,
    chrome_body,
    chrome_defs,
    decor_orbs,
    design_tokens,
    hex_shift,
    shadow_filter_def,
    svg_open,
    title_block,
    title_underline,
)
from .util import xml_escape


# ---------------------------------------------------------------------------
# Template renderers — each uses shared design primitives
# ---------------------------------------------------------------------------

def _render_hero_cover(plan: SlidePlan, lock: dict, total: int, w: int, h: int) -> str:
    """Hero cover: oversized title, ambient orbs, geometric decoration."""
    from .svg_pipeline import _wrap_to_tspans
    p = lock["palette"]
    font = lock["font_family"]
    t = design_tokens(w, h)

    orb_defs, orb_body = decor_orbs(plan.index, lock, w, h, intensity=0.22)
    title = xml_escape(plan.title)
    subtitle = xml_escape(plan.items[0].primary) if plan.items else ""

    title_font = adaptive_title_font(title, base_px=t["type"]["hero"])
    mx = t["margin"]["page"]
    title_y = h // 2 - 20
    sub_y = title_y + title_font + 20

    # Build defs: merge chrome gradient + orb defs into single <defs>
    all_defs = [
        chrome_defs(plan.index, lock, w, h),
        f'    <radialGradient id="hero-orb-{plan.index:02d}" cx="80%" cy="20%" r="65%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0.22"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'    </radialGradient>',
        f'    <radialGradient id="hero-orb2-{plan.index:02d}" cx="20%" cy="80%" r="50%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0.10"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'    </radialGradient>',
        f'    <linearGradient id="hero-title-grad-{plan.index:02d}" x1="0%" y1="0%" x2="100%" y2="0%">\n'
        f'      <stop offset="0%" stop-color="{p["text"]}"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}"/>\n'
        f'    </linearGradient>',
        orb_defs,
    ]
    defs_content = "\n".join(all_defs)

    return (
        f'{svg_open(w, h)}\n'
        f'  <defs>\n{defs_content}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        # Geometric circles (right side)
        f'  <g id="decor-geo-{plan.index:02d}" opacity="0.6">\n'
        f'    <circle cx="{w - 200}" cy="{h // 2}" r="220" stroke="{p["accent"]}" stroke-width="1" stroke-dasharray="4,8" fill="none" opacity="0.10"/>\n'
        f'    <circle cx="{w - 200}" cy="{h // 2}" r="160" stroke="{p["accent"]}" stroke-width="1.5" stroke-dasharray="8,6" fill="none" opacity="0.16"/>\n'
        f'    <circle cx="{w - 200}" cy="{h // 2}" r="100" stroke="{p["accent"]}" stroke-width="1" fill="none" opacity="0.25"/>\n'
        f'    <circle cx="{w - 200}" cy="{h // 2}" r="5" fill="{p["accent"]}" opacity="0.7"/>\n'
        f'  </g>\n'
        f'{chrome_body(plan.index, total, lock, w, h)}\n'
        # Title
        f'  <g id="content-title-{plan.index:02d}">\n'
        f'    <text x="{mx}" y="{title_y}" font-family="{font}" '
        f'font-size="{title_font}" font-weight="700" fill="url(#hero-title-grad-{plan.index:02d})">{title}</text>\n'
        f'  </g>\n'
        # Subtitle
        + (f'  <g id="content-subtitle-{plan.index:02d}">\n'
           f'    <text x="{mx}" y="{sub_y}" font-family="{font}" '
           f'font-size="{t["type"]["caption"]}" fill="{p["body"]}" opacity="0.9">{subtitle}</text>\n'
           f'  </g>\n' if subtitle else '')
        +
        f'  <g id="content-footer-{plan.index:02d}">\n'
        f'    <rect x="{mx}" y="{h - 50}" width="40" height="2" rx="1" fill="{p["accent"]}" opacity="0.6"/>\n'
        f'    <text x="{mx + 52}" y="{h - 43}" font-family="{font}" '
        f'font-size="{t["type"]["overline"]}" fill="{p["muted"]}" letter-spacing="2" opacity="0.7">{total} PAGES DESIGNED</text>\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_bold_statement(plan: SlidePlan, lock: dict, total: int, w: int, h: int) -> str:
    """Bold statement: one large centered text, minimal decoration."""
    from .svg_pipeline import _wrap_to_tspans
    p = lock["palette"]
    font = lock["font_family"]
    t = design_tokens(w, h)

    orb_defs, orb_body = decor_orbs(plan.index, lock, w, h, intensity=0.08)
    title = xml_escape(plan.title)
    hero_text = xml_escape(plan.items[0].primary) if plan.items else ""
    caption = xml_escape(plan.items[0].secondary) if plan.items and plan.items[0].secondary else ""

    title_font = adaptive_title_font(title, base_px=t["type"]["h1"])
    cx = w // 2
    cy = h // 2

    tspans, line_count = _wrap_to_tspans(
        hero_text, cx, t["type"]["h2"], w - 240, line_height=1.4
    )

    all_defs = [chrome_defs(plan.index, lock, w, h), orb_defs]
    defs_content = "\n".join(all_defs)

    return (
        f'{svg_open(w, h)}\n'
        f'  <defs>\n{defs_content}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome_body(plan.index, total, lock, w, h)}\n'
        f'  <g id="content-title-{plan.index:02d}">\n'
        f'    <text x="{t["margin"]["page"]}" y="{t["margin"]["page"] + 30}" font-family="{font}" '
        f'font-size="{title_font}" font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="{t["margin"]["page"]}" y="{t["margin"]["page"] + 42}" width="72" height="3.5" rx="1.75" fill="{p["accent"]}" opacity="0.8"/>\n'
        f'  </g>\n'
        # Hero text (centered)
        f'  <g id="content-hero-{plan.index:02d}">\n'
        f'    <text x="{cx}" y="{cy - (line_count - 1) * int(t["type"]["h2"] * 0.7)}" font-family="{font}" '
        f'font-size="{t["type"]["h2"]}" font-weight="600" fill="{p["text"]}" '
        f'text-anchor="middle">{tspans}</text>\n'
        f'  </g>\n'
        # Caption
        + (f'  <g id="content-caption-{plan.index:02d}">\n'
           f'    <text x="{cx}" y="{cy + 60}" font-family="{font}" '
           f'font-size="{t["type"]["caption"]}" fill="{p["body"]}" '
           f'text-anchor="middle" opacity="0.8">{caption}</text>\n'
           f'  </g>\n' if caption else '')
        +
        f'</svg>'
    )


def _render_hero_metric(plan: SlidePlan, lock: dict, total: int, w: int, h: int) -> str:
    """Hero metric: one giant number + label centered."""
    p = lock["palette"]
    font = lock["font_family"]
    t = design_tokens(w, h)

    orb_defs, orb_body = decor_orbs(plan.index, lock, w, h, intensity=0.10)
    title = xml_escape(plan.title)
    metric = xml_escape(plan.items[0].primary) if plan.items else ""
    label = xml_escape(plan.items[0].secondary) if plan.items and plan.items[0].secondary else ""

    cx = w // 2
    cy = h // 2

    all_defs = [chrome_defs(plan.index, lock, w, h), orb_defs]
    defs_content = "\n".join(all_defs)

    return (
        f'{svg_open(w, h)}\n'
        f'  <defs>\n{defs_content}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome_body(plan.index, total, lock, w, h)}\n'
        f'  <g id="content-title-{plan.index:02d}">\n'
        f'    <text x="{t["margin"]["page"]}" y="{t["margin"]["page"] + 30}" font-family="{font}" '
        f'font-size="{t["type"]["h1"]}" font-weight="700" fill="{p["text"]}">{title}</text>\n'
        f'    <rect x="{t["margin"]["page"]}" y="{t["margin"]["page"] + 42}" width="72" height="3.5" rx="1.75" fill="{p["accent"]}" opacity="0.8"/>\n'
        f'  </g>\n'
        # Giant metric
        f'  <g id="content-metric-{plan.index:02d}">\n'
        f'    <text x="{cx}" y="{cy - 20}" font-family="{font}" '
        f'font-size="96" font-weight="800" fill="{p["accent"]}" '
        f'text-anchor="middle">{metric}</text>\n'
        f'    <text x="{cx}" y="{cy + 40}" font-family="{font}" '
        f'font-size="{t["type"]["h2"]}" font-weight="600" fill="{p["body"]}" '
        f'text-anchor="middle">{label}</text>\n'
        f'  </g>\n'
        f'</svg>'
    )


def _render_card_row(plan: SlidePlan, lock: dict, total: int, w: int, h: int) -> str:
    """Horizontal card row: 2-4 cards side by side with title + subtitle."""
    from .svg_pipeline import _wrap_to_tspans
    p = lock["palette"]
    font = lock["font_family"]
    t = design_tokens(w, h)

    orb_defs, orb_body = decor_orbs(plan.index, lock, w, h, intensity=0.10)
    title = xml_escape(plan.title)

    items = plan.items[:4]
    count = max(len(items), 1)
    mx = t["margin"]["content"]
    gap = 24
    card_w = (w - mx * 2 - (count - 1) * gap) // count
    card_h = 300
    card_y = 180

    defs_parts = [chrome_defs(plan.index, lock, w, h), shadow_filter_def(plan.index), orb_defs]
    cards = []

    for i, item in enumerate(items):
        cx = mx + i * (card_w + gap)
        mid_x = cx + card_w // 2
        primary = xml_escape(item.primary[:30])
        secondary = xml_escape(item.secondary[:60]) if item.secondary else ""
        ca = hex_shift(p["accent"], i * 15 - 30)

        grad_id = f"cr-grad-{plan.index:02d}-{i}"
        clip_id = f"cr-clip-{plan.index:02d}-{i}"

        defs_parts.append(
            f'    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="0.85"/>\n'
            f'      <stop offset="100%" stop-color="{hex_shift(p["surface"], -10)}" stop-opacity="0.65"/>\n'
            f'    </linearGradient>'
        )
        defs_parts.append(
            f'    <clipPath id="{clip_id}">\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="16" />\n'
            f'    </clipPath>'
        )

        cards.append(
            f'    <g clip-path="url(#{clip_id})">\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" fill="url(#{grad_id})"/>\n'
            f'      <rect x="{cx}" y="{card_y}" width="{card_w}" height="5" fill="{ca}" opacity="0.85"/>\n'
            f'    </g>'
        )
        cards.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" height="{card_h}" rx="16" fill="none" '
            f'stroke="{ca}" stroke-opacity="0.18" stroke-width="1.5" filter="url(#card-shadow-{plan.index:02d})"/>'
        )
        cards.append(
            f'    <text x="{mid_x}" y="{card_y + 120}" font-family="{font}" '
            f'font-size="{t["type"]["h2"]}" font-weight="700" fill="{p["text"]}" '
            f'text-anchor="middle">{primary}</text>'
        )
        if secondary:
            sub_tspans, sub_lines = _wrap_to_tspans(
                secondary, mid_x, t["type"]["caption"], card_w - 40, line_height=1.3
            )
            cards.append(
                f'    <text x="{mid_x}" y="{card_y + 170}" font-family="{font}" '
                f'font-size="{t["type"]["caption"]}" fill="{p["body"]}" '
                f'text-anchor="middle">{sub_tspans}</text>'
            )

    content = "\n".join(cards)
    defs_content = "\n".join(defs_parts)
    return (
        f'{svg_open(w, h)}\n'
        f'  <defs>\n{defs_content}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome_body(plan.index, total, lock, w, h)}\n'
        f'  <g id="content-title-{plan.index:02d}">\n'
        f'    <text x="{mx}" y="{mx + 30}" font-family="{font}" font-size="{t["type"]["h1"]}" '
        f'font-weight="700" fill="{p["text"]}">{xml_escape(plan.title)}</text>\n'
        f'    <rect x="{mx}" y="{mx + 42}" width="72" height="3.5" rx="1.75" fill="{p["accent"]}" opacity="0.8"/>\n'
        f'  </g>\n'
        f'  <g id="content-cards-{plan.index:02d}">\n{content}\n  </g>\n'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# Template → Renderer dispatch
# ---------------------------------------------------------------------------

_RENDERER_MAP: dict[str, callable] = {
    "hero-cover": _render_hero_cover,
    "bold-statement": _render_bold_statement,
    "hero-metric": _render_hero_metric,
    "card-row": _render_card_row,
}


def render_template_slide(
    plan: SlidePlan,
    template_name: str,
    lock: dict,
    total: int,
) -> str | None:
    """Render a slide using the specified template.

    Returns SVG string, or None if the template has no custom renderer
    (caller should fall back to existing domain renderers).
    """
    template = get_template(template_name)
    if template is None:
        return None

    canvas = lock["canvas"]
    w = int(canvas["width"])
    h = int(canvas["height"])

    renderer = _RENDERER_MAP.get(template_name)
    if renderer:
        return renderer(plan, lock, total, w, h)

    return None


def get_existing_layout_for_template(template_name: str) -> str | None:
    """Map a template name to an existing renderer layout name."""
    mapping = {
        "section-divider": "section-divider",
        "closing": "closing",
        "key-concept": "key-concept",
        "numbered-list": "bullet-list",
        "metrics-dashboard": "metrics-dashboard",
        "two-column": "comparison-matrix",
        "timeline": "timeline",
        "process-flow": "process-flow",
        "discussion": "discussion",
        "team-grid": "team-grid",
        "quote-block": "quote-block",
        "left-stack": "default",
        "image-showcase": "default",
    }
    return mapping.get(template_name)
