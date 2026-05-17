"""Icon library — Lucide / Tabler subset embedded as SVG.

Phase 19 (v1.4): introduced. v1.4-ICON-01..04.

Usage in a slide layout / spec:

    icon: rocket          # short form -> defaults to "lucide:rocket"
    icon: lucide:flame    # explicit pack
    icon: tabler:flame    # other pack

Resolution order:

    1. Vendored packs under `slide_skill/assets/icons/<pack>/<name>.svg`.
    2. Built-in inline fallbacks in INLINE_ICONS (this module).

The SVG is returned as a string with the theme stroke colour and weight
applied (replacing the placeholder `currentColor`). Suitable for direct
injection into a slide SVG via `<g>` wrapping or as a `<symbol>` reference.

For PPTX embedding, `icon_to_png_bytes(name, theme, size_px=128)` returns
PNG bytes via `cairosvg` if available; the exporter falls back to dropping
the icon if cairosvg isn't installed (with a warning surfaced through QA).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .themes import ThemeSpec, get_theme

ASSETS_DIR = Path(__file__).parent / "assets" / "icons"

# Compact starter set — Lucide-style stroke icons (MIT-licensed source paths).
# Uses currentColor so the caller can substitute the theme stroke. 24x24 viewBox.
# Full library lives in assets/icons/lucide/*.svg; this map is the always-available
# fallback used when the on-disk pack is missing or empty.
INLINE_ICONS: dict[str, str] = {
    "rocket": '<path d="M4.5 16.5c-1.5 1.5-2 5.5-2 5.5s4-.5 5.5-2c.85-.85.85-2.65 0-3.5-.85-.85-2.65-.85-3.5 0z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22 22 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "check-circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "alert-triangle": '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "info": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    "lightbulb": '<path d="M9 18h6"/><path d="M10 22h4"/><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "trending-up": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    "trending-down": '<polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/>',
    "bar-chart": '<line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>',
    "pie-chart": '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "heart": '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
    "code": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
}

ICON_NAME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*:)?([A-Za-z][A-Za-z0-9_-]*)$")


def _parse_name(spec: str) -> tuple[str, str]:
    m = ICON_NAME_RE.match(spec.strip())
    if not m:
        raise ValueError(f"Invalid icon spec: {spec!r}")
    pack = (m.group(1) or "lucide:").rstrip(":")
    return pack, m.group(2)


def list_icons(pack: str = "lucide") -> list[str]:
    """Return all known icon names in a pack (disk + inline)."""
    names: set[str] = set(INLINE_ICONS) if pack == "lucide" else set()
    pack_dir = ASSETS_DIR / pack
    if pack_dir.is_dir():
        for path in pack_dir.glob("*.svg"):
            names.add(path.stem)
    return sorted(names)


def get_icon_paths(name: str) -> str:
    """Return the inner SVG path/markup for an icon (no <svg> wrapper).

    Resolution: vendored file in assets/icons/<pack>/<name>.svg first, then
    INLINE_ICONS fallback.
    """
    pack, base = _parse_name(name)
    on_disk = ASSETS_DIR / pack / f"{base}.svg"
    if on_disk.is_file():
        raw = on_disk.read_text(encoding="utf-8")
        # Strip outer <svg ...> ... </svg> wrapper if present, keep inner content.
        m = re.search(r"<svg[^>]*>(.*)</svg>", raw, re.DOTALL)
        if m:
            return m.group(1).strip()
        return raw.strip()
    if pack == "lucide" and base in INLINE_ICONS:
        return INLINE_ICONS[base]
    raise KeyError(f"Icon not found: {name}")


def render_icon_svg(
    name: str,
    *,
    size: int = 48,
    stroke: Optional[str] = None,
    weight: Optional[float | str] = None,
    theme: Optional[ThemeSpec] = None,
    x: int | float = 0,
    y: int | float = 0,
) -> str:
    """Return a complete <svg> element for the icon, sized and themed.

    Suitable for direct injection into a parent SVG document. Uses 24x24
    Lucide viewBox.
    """
    inner = get_icon_paths(name)
    if theme is None:
        theme = get_theme("dark-tech")
    if stroke is None:
        stroke = theme.icons.get("stroke", theme.palette.get("text", "#000000"))
    if weight is None:
        weight = theme.icons.get("weight", "1.75")
    return (
        f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="{stroke}" stroke-width="{weight}" '
        f'stroke-linecap="round" stroke-linejoin="round">{inner}</svg>'
    )


def icon_to_png_bytes(
    name: str,
    *,
    size_px: int = 128,
    stroke: Optional[str] = None,
    weight: Optional[float | str] = None,
    theme: Optional[ThemeSpec] = None,
) -> bytes:
    """Rasterize an icon to PNG bytes for PPTX embedding.

    Requires `cairosvg`. Raises RuntimeError with a helpful message if missing.
    """
    try:
        import cairosvg  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "icon PNG rendering requires `cairosvg`. Install with `pip install cairosvg`."
        ) from exc
    svg = render_icon_svg(name, size=24, stroke=stroke, weight=weight, theme=theme)
    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=size_px, output_height=size_px)
