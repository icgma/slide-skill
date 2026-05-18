"""Competition-domain SVG renderers for slide-skill v3.0.

Provides specialized layouts for competition / pitch / defense presentations:
  - team-grid:         Team members in a card grid (photo placeholder + name + role)
  - metrics-dashboard: Key metrics in large number + label cards
  - timeline:          Horizontal milestone timeline
  - comparison-matrix: Two-column comparison (ours vs. theirs)

All renderers share the same chrome/decor pattern as domain_teaching.
"""

from __future__ import annotations

from .content_planner import SlidePlan
from .util import xml_escape


# ---------------------------------------------------------------------------
# Shared helpers
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
        f'    <radialGradient id="comp-orb-{index:02d}" cx="50%" cy="50%" r="50%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="{intensity}"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
        f'    </radialGradient>'
    )
    body = (
        f'  <g id="decor-{index:02d}">\n'
        f'    <circle cx="{w - 80}" cy="80" r="260" fill="url(#comp-orb-{index:02d})"/>\n'
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
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items[:4]
    count = max(len(items), 1)
    card_w = (w - 160 - (count - 1) * 24) // count
    card_h = 380
    card_y = 200
    parts: list[str] = []

    for i, item in enumerate(items):
        cx = 80 + i * (card_w + 24)
        mid_x = cx + card_w // 2
        name = xml_escape(item.primary[:30])
        role = xml_escape(item.secondary[:40]) if item.secondary else ""

        # Card background
        parts.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" '
            f'height="{card_h}" rx="14" fill="{p["surface"]}"/>'
        )
        # Avatar circle placeholder
        avatar_cy = card_y + 90
        parts.append(
            f'    <circle cx="{mid_x}" cy="{avatar_cy}" r="50" '
            f'fill="{p["accent"]}" opacity="0.12"/>'
        )
        # Initials in circle
        initials = name[0] if name else "?"
        parts.append(
            f'    <text x="{mid_x}" y="{avatar_cy + 12}" font-family="{font}" '
            f'font-size="36" font-weight="700" fill="{p["accent"]}" '
            f'text-anchor="middle">{initials}</text>'
        )
        # Name
        parts.append(
            f'    <text x="{mid_x}" y="{avatar_cy + 90}" font-family="{font}" '
            f'font-size="22" font-weight="600" fill="{p["text"]}" '
            f'text-anchor="middle">{name}</text>'
        )
        # Role
        if role:
            parts.append(
                f'    <text x="{mid_x}" y="{avatar_cy + 120}" font-family="{font}" '
                f'font-size="16" fill="{p["body"]}" '
                f'text-anchor="middle">{role}</text>'
            )
        # Bottom accent line
        parts.append(
            f'    <rect x="{mid_x - 20}" y="{card_y + card_h - 12}" '
            f'width="40" height="3" rx="2" fill="{p["accent"]}"/>'
        )

    content = "\n".join(parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n{orb_defs}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock)}\n'
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
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h, intensity=0.10)
    title = xml_escape(plan.title)

    items = plan.items[:4]
    count = max(len(items), 1)
    card_w = (w - 160 - (count - 1) * 32) // count
    card_h = 320
    card_y = 220

    def _hex_shift(hexc: str, delta: int) -> str:
        h_ = hexc.lstrip("#")
        r, g, b = (int(h_[i:i + 2], 16) for i in (0, 2, 4))
        r = max(0, min(255, r + delta))
        g = max(0, min(255, g + delta))
        b = max(0, min(255, b + delta))
        return f"#{r:02X}{g:02X}{b:02X}"

    accent = p["accent"]
    accents = [accent, _hex_shift(accent, -30), _hex_shift(accent, 30), _hex_shift(accent, -60)]

    parts: list[str] = []
    for i, item in enumerate(items):
        cx = 80 + i * (card_w + 32)
        mid_x = cx + card_w // 2
        ca = accents[i % len(accents)]

        # Card
        parts.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" '
            f'height="{card_h}" rx="14" fill="{p["surface"]}"/>'
        )
        # Top accent stripe
        parts.append(
            f'    <rect x="{cx}" y="{card_y}" width="{card_w}" '
            f'height="5" rx="3" fill="{ca}"/>'
        )
        # Big number / metric value
        metric_val = xml_escape(item.primary[:12])
        parts.append(
            f'    <text x="{mid_x}" y="{card_y + 140}" font-family="{font}" '
            f'font-size="56" font-weight="700" fill="{ca}" '
            f'text-anchor="middle">{metric_val}</text>'
        )
        # Label
        label = xml_escape(item.secondary[:30]) if item.secondary else ""
        if label:
            parts.append(
                f'    <text x="{mid_x}" y="{card_y + 190}" font-family="{font}" '
                f'font-size="16" fill="{p["body"]}" '
                f'text-anchor="middle">{label}</text>'
            )

    content = "\n".join(parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n{orb_defs}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock)}\n'
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

    Layout: Central horizontal line with milestone dots and labels above/below.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items[:6]
    count = max(len(items), 1)

    line_y = h // 2
    line_left = 120
    line_right = w - 120
    line_w = line_right - line_left

    parts: list[str] = []

    # Central horizontal line
    parts.append(
        f'    <rect x="{line_left}" y="{line_y}" width="{line_w}" '
        f'height="3" fill="{p["accent"]}" opacity="0.4"/>'
    )

    for i, item in enumerate(items):
        dot_x = line_left + int((i / max(count - 1, 1)) * line_w)
        milestone = xml_escape(item.primary[:30])
        date_label = xml_escape(item.secondary[:20]) if item.secondary else ""

        # Milestone dot
        parts.append(
            f'    <circle cx="{dot_x}" cy="{line_y + 1}" r="10" fill="{p["accent"]}"/>'
        )
        parts.append(
            f'    <circle cx="{dot_x}" cy="{line_y + 1}" r="18" '
            f'fill="{p["accent"]}" opacity="0.12"/>'
        )

        # Alternate label position (above/below)
        if i % 2 == 0:
            # Label above
            parts.append(
                f'    <text x="{dot_x}" y="{line_y - 40}" font-family="{font}" '
                f'font-size="16" font-weight="600" fill="{p["text"]}" '
                f'text-anchor="middle">{milestone}</text>'
            )
            if date_label:
                parts.append(
                    f'    <text x="{dot_x}" y="{line_y - 20}" font-family="{font}" '
                    f'font-size="12" fill="{p["body"]}" '
                    f'text-anchor="middle">{date_label}</text>'
                )
        else:
            # Label below
            parts.append(
                f'    <text x="{dot_x}" y="{line_y + 40}" font-family="{font}" '
                f'font-size="16" font-weight="600" fill="{p["text"]}" '
                f'text-anchor="middle">{milestone}</text>'
            )
            if date_label:
                parts.append(
                    f'    <text x="{dot_x}" y="{line_y + 58}" font-family="{font}" '
                    f'font-size="12" fill="{p["body"]}" '
                    f'text-anchor="middle">{date_label}</text>'
                )

    content = "\n".join(parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs></defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock)}\n'
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

    Layout: Two columns with header badges, items listed vertically.
    """
    canvas = lock["canvas"]
    w, h = int(canvas["width"]), int(canvas["height"])
    p = lock["palette"]
    font = lock["font_family"]
    chrome = _chrome(plan.index, total, lock, w, h)
    orb_defs, orb_body = _decor_orbs(plan.index, lock, w, h)
    title = xml_escape(plan.title)

    items = plan.items
    mid = max(1, len(items) // 2)
    left_items = items[:mid]
    right_items = items[mid:]

    col_w = (w - 200) // 2
    left_x = 80
    right_x = left_x + col_w + 40
    col_y = 190
    col_h = h - col_y - 60

    # Determine column headers from meta or defaults
    left_header = "OURS"
    right_header = "THEIRS"
    if items and items[0].meta:
        left_header = items[0].meta.get("left_header", left_header)
        right_header = items[0].meta.get("right_header", right_header)

    parts: list[str] = []

    # Left column
    parts.append(
        f'    <rect x="{left_x}" y="{col_y}" width="{col_w}" height="{col_h}" '
        f'rx="14" fill="{p["surface"]}"/>'
    )
    parts.append(
        f'    <rect x="{left_x + col_w // 2 - 50}" y="{col_y + 16}" width="100" '
        f'height="26" rx="13" fill="{p["accent"]}"/>'
    )
    parts.append(
        f'    <text x="{left_x + col_w // 2}" y="{col_y + 34}" font-family="{font}" '
        f'font-size="12" font-weight="700" fill="{p["background"]}" '
        f'text-anchor="middle">{xml_escape(left_header)}</text>'
    )
    ly = col_y + 70
    for item in left_items[:5]:
        text = xml_escape(item.primary[:50])
        parts.append(
            f'    <text x="{left_x + 24}" y="{ly}" font-family="{font}" '
            f'font-size="18" fill="{p["text"]}">✓ {text}</text>'
        )
        ly += 36

    # Right column
    parts.append(
        f'    <rect x="{right_x}" y="{col_y}" width="{col_w}" height="{col_h}" '
        f'rx="14" fill="{p["surface"]}"/>'
    )
    parts.append(
        f'    <rect x="{right_x + col_w // 2 - 50}" y="{col_y + 16}" width="100" '
        f'height="26" rx="13" fill="{p["muted"]}" opacity="0.3"/>'
    )
    parts.append(
        f'    <text x="{right_x + col_w // 2}" y="{col_y + 34}" font-family="{font}" '
        f'font-size="12" font-weight="700" fill="{p["body"]}" '
        f'text-anchor="middle">{xml_escape(right_header)}</text>'
    )
    ry = col_y + 70
    for item in right_items[:5]:
        text = xml_escape(item.primary[:50])
        parts.append(
            f'    <text x="{right_x + 24}" y="{ry}" font-family="{font}" '
            f'font-size="18" fill="{p["body"]}">✗ {text}</text>'
        )
        ry += 36

    # Vertical divider
    div_x = left_x + col_w + 20
    parts.append(
        f'    <rect x="{div_x}" y="{col_y + 20}" width="2" '
        f'height="{col_h - 40}" fill="{p["accent"]}" opacity="0.2"/>'
    )

    content = "\n".join(parts)
    return (
        f'{_svg_open(w, h)}\n'
        f'  <defs>\n{orb_defs}\n  </defs>\n'
        f'  <g id="background"><rect x="0" y="0" width="{w}" height="{h}" fill="{p["background"]}"/></g>\n'
        f'{orb_body}\n'
        f'{chrome}\n'
        f'{_title_block(plan.index, title, lock)}\n'
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
