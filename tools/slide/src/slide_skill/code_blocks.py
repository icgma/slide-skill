"""Code block syntax highlighting -> SVG.

Phase 20 (v1.4): introduced. v1.4-CODE-01..03.

Renders fenced code blocks (or any string + language hint) to themed SVG
suitable for embedding in a slide page. Uses Pygments when available; falls
back to a plain monospaced rendering otherwise (so the dependency stays
optional and CI doesn't hard-fail on minimal installs).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .themes import ThemeSpec, get_theme

FENCED_RE = re.compile(r"```([A-Za-z0-9_+\-]+)?\s*\n(.*?)\n```", re.DOTALL)

# Theme name -> Pygments style name mapping.
DEFAULT_PYGMENTS_STYLE = {
    "dark-tech": "monokai",
    "light-corporate": "default",
    "warm-editorial": "manni",
    "data-forward": "vs",
    "vibrant-startup": "dracula",
}


@dataclass
class CodeBlock:
    """A single fenced code block extracted from source markdown."""

    language: str
    text: str
    line_numbers: bool = False
    highlight: list[int] = field(default_factory=list)


def extract_code_blocks(markdown: str) -> list[CodeBlock]:
    """Pull all fenced code blocks out of a Markdown string."""
    out: list[CodeBlock] = []
    for m in FENCED_RE.finditer(markdown):
        lang = (m.group(1) or "text").strip().lower()
        out.append(CodeBlock(language=lang, text=m.group(2)))
    return out


def parse_highlight_spec(spec: str | Iterable[int | str]) -> list[int]:
    """Parse `[3, 7-9, 12]` style spec into a flat list of line numbers."""
    if isinstance(spec, str):
        spec = [p.strip() for p in spec.split(",") if p.strip()]
    out: list[int] = []
    for part in spec:
        s = str(part)
        if "-" in s:
            a, b = s.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(s))
    return sorted(set(out))


def _pygments_style_for(theme: ThemeSpec) -> str:
    return DEFAULT_PYGMENTS_STYLE.get(theme.name, "default")


def render_code_svg(
    block: CodeBlock,
    *,
    theme: Optional[ThemeSpec] = None,
    width: int = 1280,
    font_size: int = 22,
    padding: int = 24,
    x: int | float = 0,
    y: int | float = 0,
) -> str:
    """Render a CodeBlock as positioned SVG.

    Tries Pygments → SVG formatter for full syntax colouring; falls back to a
    plain monospace rendering using theme palette when Pygments is missing or
    the lexer is unknown.
    """
    if theme is None:
        theme = get_theme("dark-tech")

    panel_fill = theme.palette.get("surface", "#1E293B")
    text_color = theme.palette.get("text", "#F1F5F9")
    accent = theme.palette.get("accent", "#3B82F6")
    muted = theme.palette.get("body", "#94A3B8")

    lines = block.text.splitlines() or [""]
    line_height = int(font_size * 1.4)
    height = padding * 2 + line_height * len(lines)

    # Line numbers gutter width.
    gutter = 0
    if block.line_numbers:
        gutter = font_size * 3

    inner_x = padding + gutter
    parts: list[str] = []
    parts.append(
        f'<g transform="translate({x},{y})">'
        f'<rect width="{width}" height="{height}" rx="8" ry="8" fill="{panel_fill}"/>'
    )

    # Highlighted-row background bands.
    for ln in block.highlight:
        if 1 <= ln <= len(lines):
            ry = padding + (ln - 1) * line_height - 2
            parts.append(
                f'<rect x="{padding // 2}" y="{ry}" width="{width - padding}" '
                f'height="{line_height}" fill="{accent}" fill-opacity="0.18"/>'
            )

    pygments_inner = _try_pygments_inner(block, theme, font_size, line_height, inner_x, padding)
    if pygments_inner is not None:
        parts.append(pygments_inner)
    else:
        # Plain fallback.
        for i, line in enumerate(lines):
            row_y = padding + (i + 1) * line_height - (line_height - font_size) // 2
            if block.line_numbers:
                parts.append(
                    f'<text x="{padding}" y="{row_y}" font-family="monospace" '
                    f'font-size="{font_size}" fill="{muted}">{i + 1}</text>'
                )
            from .util import xml_escape
            parts.append(
                f'<text x="{inner_x}" y="{row_y}" font-family="monospace" '
                f'font-size="{font_size}" fill="{text_color}" xml:space="preserve">'
                f'{xml_escape(line)}</text>'
            )

    parts.append('</g>')
    return "".join(parts)


def _try_pygments_inner(
    block: CodeBlock,
    theme: ThemeSpec,
    font_size: int,
    line_height: int,
    inner_x: int,
    padding: int,
) -> Optional[str]:
    """Attempt to colour each line with Pygments tokens; return SVG fragment or None."""
    try:
        from pygments import lex
        from pygments.lexers import get_lexer_by_name
        from pygments.styles import get_style_by_name
        from pygments.token import Token
        from pygments.util import ClassNotFound
    except ImportError:
        return None

    try:
        lexer = get_lexer_by_name(block.language)
    except Exception:  # noqa: BLE001
        return None
    try:
        style = get_style_by_name(_pygments_style_for(theme))
    except Exception:  # noqa: BLE001 - ClassNotFound and friends
        return None

    from .util import xml_escape

    style_for = style.style_for_token  # type: ignore[attr-defined]
    text_color = theme.palette.get("text", "#F1F5F9")
    muted = theme.palette.get("body", "#94A3B8")

    tokens = list(lex(block.text, lexer))
    parts: list[str] = []
    line_idx = 0
    col_x = inner_x
    row_y = padding + line_height - (line_height - font_size) // 2
    if block.line_numbers:
        parts.append(
            f'<text x="{padding}" y="{row_y}" font-family="monospace" '
            f'font-size="{font_size}" fill="{muted}">1</text>'
        )

    for tok_type, tok_value in tokens:
        if not tok_value:
            continue
        meta = style_for(tok_type) or {}
        color = meta.get("color")
        bold = meta.get("bold")
        italic = meta.get("italic")
        # Split by newlines so each row keeps its own y.
        segments = tok_value.split("\n")
        for seg_idx, seg in enumerate(segments):
            if seg:
                weight_attr = ' font-weight="bold"' if bold else ""
                style_attr = ' font-style="italic"' if italic else ""
                fill = f"#{color}" if color else text_color
                parts.append(
                    f'<text x="{col_x}" y="{row_y}" font-family="monospace" '
                    f'font-size="{font_size}" fill="{fill}"{weight_attr}{style_attr} '
                    f'xml:space="preserve">{xml_escape(seg)}</text>'
                )
                col_x += int(font_size * 0.6 * len(seg))
            if seg_idx < len(segments) - 1:
                line_idx += 1
                col_x = inner_x
                row_y += line_height
                if block.line_numbers:
                    parts.append(
                        f'<text x="{padding}" y="{row_y}" font-family="monospace" '
                        f'font-size="{font_size}" fill="{muted}">{line_idx + 1}</text>'
                    )
    return "".join(parts)
