"""Shared SVG design primitives for slide-skill.

Single source of truth for design tokens, chrome, decorations, and
helper functions used by all renderers (svg_pipeline, domain_*, layout_renderer).

Any change to visual DNA (colors, spacing, shadow, chrome) must happen HERE
and propagate automatically to all consumers.

KEY DESIGN RULE: All visual output is **theme-aware**. The is_light(lock)
function determines whether a theme has a light or dark background, and
decorators/chrome/cards adapt accordingly. Light themes get solid borders
and higher-contrast surfaces; dark themes get frosted glass and ambient orbs.
"""

from __future__ import annotations

from .util import xml_escape


# ---------------------------------------------------------------------------
# Theme detection — the single switch that drives all visual decisions
# ---------------------------------------------------------------------------

def is_light(lock: dict) -> bool:
    """Return True if the theme has a light background.

    This is the foundational decision: every visual element (card style,
    decoration, shadow, border) branches on this value.
    """
    bg = lock["palette"]["background"].lstrip("#")
    r, g, b = int(bg[0:2], 16), int(bg[2:4], 16), int(bg[4:6], 16)
    # Perceived luminance threshold — 0.4 separates light from dark.
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.4


# ---------------------------------------------------------------------------
# Design tokens — consistent across all templates
# ---------------------------------------------------------------------------

def design_tokens(w: int, h: int) -> dict:
    """Unified design token system.

    All renderers MUST call this function — never hardcode layout values.
    Canvas 1280×720 → unit=12; canvas 1024×768 → unit=12.
    """
    unit = min(w, h) // 60
    return {
        "margin": {"page": unit * 4, "content": unit * 3, "tight": unit * 2},
        "type": {
            "hero": unit * 6,       # 72px for 720h canvas
            "h1": unit * 5,         # 60px
            "h2": unit * 4,         # 48px
            "body": unit * 3,       # 36px
            "caption": unit * 2 + 2,  # 26px
            "overline": int(unit * 1.8),  # 22px
        },
        "radius": {"card": unit * 2, "pill": unit * 3, "sm": unit},
        "shadow": {
            "sm": (0, 1, 3, 0.06),
            "md": (0, 2, 6, 0.08),
            "lg": (0, 4, 12, 0.10),
        },
        "accent_stripe": unit // 2,
    }


def extended_palette(lock: dict) -> dict[str, str]:
    """Return the full 12-role palette from a spec lock dict.

    If the lock only has the original 6 roles, the missing 6 are derived.
    Convenience wrapper for renderers that receive a lock dict.
    """
    from .themes import derive_extended_palette
    return derive_extended_palette(lock.get("palette", {}))


def typography_from_lock(lock: dict):
    """Return a TypographySpec from a spec lock dict.

    Falls back to deriving from ``font_family`` if ``typography`` is absent.
    """
    from .themes import TypographySpec, derive_typography
    typo_data = lock.get("typography")
    if typo_data and isinstance(typo_data, dict):
        return TypographySpec.from_dict(typo_data)
    return derive_typography(lock.get("font_family", "Arial, sans-serif"))


# ---------------------------------------------------------------------------
# Font sizing — adaptive based on content length
# ---------------------------------------------------------------------------

def adaptive_title_font(text: str, base_px: int = 60, min_px: int = 28) -> int:
    """Title font size that adapts to text length. Chinese-aware thresholds.

    Args:
        text: The title text
        base_px: Base font size for short titles
        min_px: Minimum font size (prevents titles from becoming unreadable)

    Returns:
        Font size in pixels, guaranteed >= min_px
    """
    n = len(text)
    if n <= 12:
        return base_px
    if n <= 20:
        return max(min_px, base_px - 8)
    if n <= 30:
        return max(min_px, base_px - 14)
    if n <= 45:
        return max(min_px, base_px - 20)
    # Very long titles: scale down further
    return max(min_px, base_px - 26)


def title_with_overflow_protection(
    text: str,
    x: int,
    y: int,
    max_width: int,
    font_family: str,
    base_font_size: int = 60,
    **attrs: str,
) -> str:
    """Generate title <text> element with automatic overflow protection.

    If title is too long to fit in one line, it will either:
    1. Reduce font size (adaptive_title_font)
    2. Wrap to multiple lines if still too wide

    Args:
        text: Title text
        x, y: Position
        max_width: Maximum width in pixels
        font_family: Font family string
        base_font_size: Starting font size
        **attrs: Additional SVG attributes (fill, font-weight, etc.)

    Returns:
        SVG <text> element with optional <tspan> for multiline
    """
    from .text_wrap import _wrap_to_tspans, _token_width

    # Guard: empty text produces no element
    if not text or not text.strip():
        return ""

    # Step 1: Adaptive font sizing
    font_size = adaptive_title_font(text, base_px=base_font_size)

    # Step 2: Check if it fits in one line
    estimated_width = _token_width(text, font_size)

    # Build attribute string
    attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())

    if estimated_width <= max_width:
        # Fits in one line
        escaped = xml_escape(text)
        return (
            f'<text x="{x}" y="{y}" font-family="{font_family}" '
            f'font-size="{font_size}" {attr_str}>{escaped}</text>'
        )

    # Step 3: Needs wrapping - use tspans
    tspans, line_count = _wrap_to_tspans(text, x, font_size, max_width)
    if line_count == 0:
        # Empty text after wrapping
        return ""

    return (
        f'<text x="{x}" y="{y}" font-family="{font_family}" '
        f'font-size="{font_size}" {attr_str}>{tspans}</text>'
    )


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def hex_shift(hexc: str, delta: int) -> str:
    """Shift a hex color lighter (+) or darker (-) by delta per channel."""
    h_ = hexc.lstrip("#")
    r, g, b = (int(h_[i:i + 2], 16) for i in (0, 2, 4))
    r = max(0, min(255, r + delta))
    g = max(0, min(255, g + delta))
    b = max(0, min(255, b + delta))
    return f"#{r:02X}{g:02X}{b:02X}"


# ---------------------------------------------------------------------------
# SVG structure helpers
# ---------------------------------------------------------------------------

def svg_open(w: int, h: int) -> str:
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg">'


# ---------------------------------------------------------------------------
# Card styling — theme-aware frosted glass (dark) vs solid panel (light)
# ---------------------------------------------------------------------------

def card_defs(index: int, card_idx: int, lock: dict) -> list[str]:
    """Return defs entries for a frosted-glass (dark) or solid (light) card.

    Returns a list of <linearGradient> and <clipPath> defs strings.
    Light themes: solid fill from surface, no gradient transparency.
    Dark themes: gradient from surface with opacity fade for frosted glass.
    """
    p = lock["palette"]
    ca = hex_shift(p["accent"], card_idx * 15 - 30)
    light = is_light(lock)

    if light:
        # Solid card — surface fill, no transparency games
        surface_color = p["surface"]
        return [
            f'    <linearGradient id="card-grad-{index:02d}-{card_idx}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{surface_color}"/>\n'
            f'      <stop offset="100%" stop-color="{surface_color}"/>\n'
            f'    </linearGradient>',
        ]
    else:
        # Frosted glass — gradient with opacity
        return [
            f'    <linearGradient id="card-grad-{index:02d}-{card_idx}" x1="0%" y1="0%" x2="100%" y2="100%">\n'
            f'      <stop offset="0%" stop-color="{p["surface"]}" stop-opacity="0.85"/>\n'
            f'      <stop offset="100%" stop-color="{hex_shift(p["surface"], -10)}" stop-opacity="0.65"/>\n'
            f'    </linearGradient>',
        ]


def card_border_attrs(index: int, card_idx: int, lock: dict) -> dict:
    """Return border/shadow attributes appropriate for the theme.

    Light themes: slightly stronger border opacity, no inner border.
    Dark themes: subtle border + inner border for depth.
    """
    p = lock["palette"]
    ca = hex_shift(p["accent"], card_idx * 15 - 30)
    light = is_light(lock)

    if light:
        return {
            "stroke": ca,
            "stroke_opacity": 0.35,
            "stroke_width": 1.5,
            "inner_border": False,
            "shadow": True,
        }
    else:
        return {
            "stroke": ca,
            "stroke_opacity": 0.18,
            "stroke_width": 1.5,
            "inner_border": True,
            "inner_stroke": ca,
            "inner_stroke_opacity": 0.08,
            "inner_stroke_width": 1,
            "shadow": True,
        }


def card_style_params(lock: dict, card_idx: int = 0) -> dict:
    """Card visual style parameters — theme-aware.

    Light: solid panels, stronger borders, no inner glow.
    Dark: frosted glass, subtle borders, inner border line.

    Call once per card, use dict values in f-strings.
    """
    if is_light(lock):
        return {
            "fill_opacity_start": 1.0,
            "fill_opacity_end": 1.0,
            "stroke_opacity": 0.35,
            "stroke_width": 1.5,
            "inner_border": False,
        }
    else:
        return {
            "fill_opacity_start": 0.85,
            "fill_opacity_end": 0.65,
            "stroke_opacity": 0.18,
            "stroke_width": 1.5,
            "inner_border": True,
            "inner_stroke_opacity": 0.08,
            "inner_stroke_width": 1,
        }


# ---------------------------------------------------------------------------
# Chrome — left accent stripe + page number (consistent across ALL slides)
# ---------------------------------------------------------------------------

def chrome_defs(index: int, lock: dict, w: int, h: int) -> str:
    """Return <defs> content for chrome elements (to be merged into main <defs>)."""
    p = lock["palette"]
    return (
        f'    <linearGradient id="accent-fade-{index:02d}" x1="0%" y1="0%" x2="0%" y2="100%">\n'
        f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0.4"/>\n'
        f'      <stop offset="50%" stop-color="{p["accent"]}" stop-opacity="0.9"/>\n'
        f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0.4"/>\n'
        f'    </linearGradient>'
    )


def chrome_body(index: int, total: int, lock: dict, w: int, h: int) -> str:
    """Return <g> elements for chrome (stripe + footer page number)."""
    p = lock["palette"]
    font = lock["font_family"]
    t = design_tokens(w, h)
    light = is_light(lock)

    if light:
        sw = t["accent_stripe"] * 2
        footer_color = p["body"]
        footer_opacity = 0.7
    else:
        sw = t["accent_stripe"]
        footer_color = p["body"]
        footer_opacity = 0.6

    fx = w - t["margin"]["tight"] * 3
    fy = h - t["margin"]["tight"] * 2
    fs = t["type"]["overline"]
    return (
        f'  <g id="chrome-stripe">\n'
        f'    <rect x="0" y="0" width="{sw}" height="{h}" fill="url(#accent-fade-{index:02d})" />\n'
        f'  </g>\n'
        f'  <g id="chrome-footer">\n'
        f'    <text x="{fx}" y="{fy}" font-family="{font}" font-size="{fs}" '
        f'fill="{footer_color}" text-anchor="end" opacity="{footer_opacity}">'
        f'{index:02d} / {total:02d}</text>\n'
        f'  </g>'
    )


# ---------------------------------------------------------------------------
# Decorative orbs — theme-aware ambient decoration
# ---------------------------------------------------------------------------

def decor_orbs_defs(index: int, lock: dict, w: int, h: int, intensity: float = 0.12) -> str:
    """Return <defs> content for decorative orbs.

    Light themes: bold geometric accent shapes (visible on white).
    Dark themes: dot grid + radial gradient orbs.
    """
    p = lock["palette"]
    lighter = hex_shift(p["accent"], 40)
    light = is_light(lock)

    if light:
        # Light theme: solid accent geometric wash — actually visible
        return (
            f'    <radialGradient id="orb-{index:02d}" cx="85%" cy="15%" r="55%">\n'
            f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0.15"/>\n'
            f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
            f'    </radialGradient>\n'
            f'    <radialGradient id="orb2-{index:02d}" cx="15%" cy="85%" r="45%">\n'
            f'      <stop offset="0%" stop-color="{lighter}" stop-opacity="0.10"/>\n'
            f'      <stop offset="100%" stop-color="{lighter}" stop-opacity="0"/>\n'
            f'    </radialGradient>'
        )
    else:
        eff = min(intensity * 0.75, 0.15)
        return (
            f'    <pattern id="bg-dots-{index:02d}" x="0" y="0" width="24" height="24" patternUnits="userSpaceOnUse">\n'
            f'      <circle cx="2" cy="2" r="1.2" fill="{p["accent"]}" fill-opacity="0.04"/>\n'
            f'    </pattern>\n'
            f'    <radialGradient id="orb-{index:02d}" cx="80%" cy="20%" r="60%">\n'
            f'      <stop offset="0%" stop-color="{p["accent"]}" stop-opacity="{eff}"/>\n'
            f'      <stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/>\n'
            f'    </radialGradient>\n'
            f'    <radialGradient id="orb2-{index:02d}" cx="20%" cy="80%" r="50%">\n'
            f'      <stop offset="0%" stop-color="{lighter}" stop-opacity="{eff * 0.7}"/>\n'
            f'      <stop offset="100%" stop-color="{lighter}" stop-opacity="0"/>\n'
            f'    </radialGradient>'
        )


def decor_orbs_body(index: int, lock: dict, w: int, h: int) -> str:
    """Return <g> element for decorative orbs body.

    Light themes: radial wash + geometric accent line in corner.
    Dark themes: dot grid + ellipses.
    """
    p = lock["palette"]
    light = is_light(lock)

    if light:
        return (
            f'  <g id="decor-{index:02d}">\n'
            f'    <ellipse cx="{w - 40}" cy="30" rx="400" ry="280" fill="url(#orb-{index:02d})"/>\n'
            f'    <ellipse cx="60" cy="{h - 30}" rx="280" ry="200" fill="url(#orb2-{index:02d})"/>\n'
            f'    <line x1="{w}" y1="0" x2="{w - 200}" y2="180" stroke="{p["accent"]}" stroke-width="2" opacity="0.12"/>\n'
            f'    <line x1="{w}" y1="0" x2="{w - 140}" y2="120" stroke="{p["accent"]}" stroke-width="1" opacity="0.08"/>\n'
            f'  </g>'
        )
    else:
        return (
            f'  <g id="decor-{index:02d}">\n'
            f'    <rect x="0" y="0" width="{w}" height="{h}" fill="url(#bg-dots-{index:02d})" />\n'
            f'    <ellipse cx="{w - 80}" cy="40" rx="360" ry="260" fill="url(#orb-{index:02d})"/>\n'
            f'    <ellipse cx="80" cy="{h - 40}" rx="240" ry="180" fill="url(#orb2-{index:02d})"/>\n'
            f'  </g>'
        )


def decor_orbs(index: int, lock: dict, w: int, h: int, intensity: float = 0.12) -> tuple[str, str]:
    """Convenience: return (defs_str, body_str) for decorative orbs."""
    return (
        decor_orbs_defs(index, lock, w, h, intensity),
        decor_orbs_body(index, lock, w, h),
    )


def decor_adaptive(
    index: int,
    layout: str,
    lock: dict,
    w: int,
    h: int,
) -> tuple[str, str]:
    """Adaptive decorations based on page type/layout.

    Returns (defs_str, body_str) for context-appropriate decorations.

    Layout-specific intensity:
    - cover/closing: high (0.22) — big visual impact
    - section-divider: medium (0.15) — clear separation
    - content layouts: low (0.08) — subtle, don't distract
    """
    # Map layouts to decoration intensity
    intensity_map = {
        "cover": 0.22,
        "closing": 0.22,
        "section-divider": 0.15,
        "bullet-list": 0.08,
        "two-column": 0.08,
        "metric-highlight": 0.10,
        "quote": 0.12,
        # Teaching layouts
        "vocab-card": 0.06,
        "dialogue": 0.06,
        "sentence-example": 0.08,
        # Course layouts
        "learning-objectives": 0.10,
        "key-concept": 0.08,
        # Competition layouts
        "team-grid": 0.08,
        "metrics-dashboard": 0.10,
    }

    intensity = intensity_map.get(layout, 0.10)  # Default: medium-low
    return decor_orbs(index, lock, w, h, intensity)


# ---------------------------------------------------------------------------
# Shadow filter — theme-aware
# ---------------------------------------------------------------------------

def shadow_filter_def(index: int, lock: dict | None = None) -> str:
    """Return <filter> definition for card drop shadow.

    Light themes: stronger shadow (more blur, higher opacity) for depth on white.
    Dark themes: standard subtle shadow.
    """
    if lock and is_light(lock):
        return (
            f'    <filter id="card-shadow-{index:02d}" x="-20%" y="-20%" width="140%" height="150%">\n'
            f'      <feGaussianBlur in="SourceAlpha" stdDeviation="8" result="blur"/>\n'
            f'      <feOffset in="blur" dx="0" dy="4" result="offsetBlur"/>\n'
            f'      <feFlood flood-color="#000000" flood-opacity="0.10" result="shadowColor"/>\n'
            f'      <feComposite in="shadowColor" in2="offsetBlur" operator="in" result="shadow"/>\n'
            f'      <feMerge><feMergeNode in="shadow"/><feMergeNode in="SourceGraphic"/></feMerge>\n'
            f'    </filter>'
        )
    return (
        f'    <filter id="card-shadow-{index:02d}" x="-20%" y="-20%" width="140%" height="150%">\n'
        f'      <feGaussianBlur in="SourceAlpha" stdDeviation="6" result="blur"/>\n'
        f'      <feOffset in="blur" dx="0" dy="3" result="offsetBlur"/>\n'
        f'      <feFlood flood-color="#000000" flood-opacity="0.16" result="shadowColor"/>\n'
        f'      <feComposite in="shadowColor" in2="offsetBlur" operator="in" result="shadow"/>\n'
        f'      <feMerge><feMergeNode in="shadow"/><feMergeNode in="SourceGraphic"/></feMerge>\n'
        f'    </filter>'
    )


def should_use_shadow(lock: dict) -> bool:
    """Whether cards should use drop shadows in this theme.

    Light themes: yes, shadows create depth against white.
    Dark themes: yes, but frosted glass already provides visual separation.
    """
    return True  # Both benefit from shadow, but light themes benefit more


# ---------------------------------------------------------------------------
# Title underline
# ---------------------------------------------------------------------------

def title_underline(x: int, y: int, accent: str, lock: dict | None = None, w: int = 72) -> str:
    """Accent bar rendered under a slide title for visual weight."""
    if lock and is_light(lock):
        return (
            f'    <rect x="{x}" y="{y}" width="{max(w, 100)}" height="4" '
            f'rx="2" fill="{accent}"/>'
        )
    return (
        f'    <rect x="{x}" y="{y}" width="{w}" height="3.5" '
        f'rx="1.75" fill="{accent}" opacity="0.8"/>'
    )


# ---------------------------------------------------------------------------
# Title block — standard title + underline for content slides
# ---------------------------------------------------------------------------

def title_block(index: int, title: str, lock: dict, w: int, h: int) -> str:
    """Render a standard title with adaptive font sizing + underline accent."""
    p = lock["palette"]
    font = lock["font_family"]
    t = design_tokens(w, h)
    m = t["margin"]["content"]
    fsize = adaptive_title_font(title, base_px=t["type"]["h1"])
    ul = title_underline(m, m + 30, p["accent"], lock)
    return (
        f'  <g id="content-title-{index:02d}">\n'
        f'    <text x="{m}" y="{m + 18}" font-family="{font}" font-size="{fsize}" '
        f'font-weight="700" fill="{p["text"]}">{xml_escape(title)}</text>\n'
        f'{ul}\n'
        f'  </g>'
    )


# ---------------------------------------------------------------------------
# Badge / label text color — theme-aware
# ---------------------------------------------------------------------------

def badge_text_color(lock: dict) -> str:
    """Color for small badges/labels (PRACTICE, EXAMPLE, CORE CONCEPT).

    Light themes: use accent color (visible against white).
    Dark themes: use muted color (subtle against dark).
    """
    p = lock["palette"]
    if is_light(lock):
        return p["accent"]
    return p["body"]
