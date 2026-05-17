"""SVG enhancement expansion — wires charts/code/icon authoring placeholders
into the finalize-SVG step.

Authors (or the AI Executor) emit lightweight `<g data-enhance="..."/>`
placeholders during SVG generation. `expand_enhancements` rewrites them in
place into rendered fragments produced by the v1.4 modules:

    <g data-enhance="chart"  data-spec-b64="..." data-x=".." data-y=".." data-w=".." data-h=".."/>
    <g data-enhance="code"   data-language=".." data-text-b64="..." data-x=".." data-y=".." data-w=".."
                             [data-line-numbers="true"] [data-highlight="3,5-7"] [data-font-size="22"]/>
    <g data-enhance="icon"   data-name="rocket"  data-x=".." data-y=".." [data-size="48"] [data-stroke="#fff"]/>

Wiring point: svg_pipeline.finalize_svg calls expand_enhancements_in_file on
every finalized slide before they are sealed in svg_final/.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Optional

from .charts import ChartSpec, chart_to_svg
from .code_blocks import CodeBlock, parse_highlight_spec, render_code_svg
from .icons import render_icon_svg
from .themes import ThemeSpec, get_theme

# Match a self-closing or empty-bodied <g data-enhance="..."/> placeholder.
# We intentionally do not match arbitrarily nested bodies — placeholders
# must be self-closing or empty.
_PLACEHOLDER_RE = re.compile(
    r"""<g\b(?P<attrs>[^>]*?\bdata-enhance=(?P<q>["'])(?P<kind>chart|code|icon)(?P=q)[^>]*?)
        (?:/>|></g>|>\s*</g>)""",
    re.VERBOSE | re.DOTALL,
)

_ATTR_RE = re.compile(r"""\b([A-Za-z_:][\w:.\-]*)\s*=\s*(["'])(.*?)\2""", re.DOTALL)


def _parse_attrs(attr_str: str) -> dict[str, str]:
    return {m.group(1): m.group(3) for m in _ATTR_RE.finditer(attr_str)}


def _b64_decode(value: str) -> str:
    return base64.b64decode(value.encode("ascii")).decode("utf-8")


def _num(attrs: dict[str, str], key: str, default: float) -> float:
    raw = attrs.get(key) or attrs.get("data-" + key)
    if raw is None:
        return default
    try:
        f = float(raw)
        return int(f) if f.is_integer() else f
    except ValueError:
        return default


def _render_chart(attrs: dict[str, str], theme: ThemeSpec) -> str:
    spec_raw = attrs.get("data-spec-b64")
    if spec_raw:
        data = json.loads(_b64_decode(spec_raw))
    else:
        inline = attrs.get("data-spec")
        if not inline:
            raise ValueError("chart placeholder missing data-spec / data-spec-b64")
        data = json.loads(inline)
    spec = ChartSpec.from_dict(data)
    return chart_to_svg(
        spec,
        theme=theme,
        width=int(_num(attrs, "data-w", 800)),
        height=int(_num(attrs, "data-h", 480)),
        x=_num(attrs, "data-x", 0),
        y=_num(attrs, "data-y", 0),
    )


def _render_code(attrs: dict[str, str], theme: ThemeSpec) -> str:
    text_raw = attrs.get("data-text-b64")
    if text_raw:
        text = _b64_decode(text_raw)
    else:
        text = attrs.get("data-text", "")
    block = CodeBlock(
        language=attrs.get("data-language", "text"),
        text=text,
        line_numbers=(attrs.get("data-line-numbers", "").lower() == "true"),
        highlight=parse_highlight_spec(attrs.get("data-highlight", "")) if attrs.get("data-highlight") else [],
    )
    return render_code_svg(
        block,
        theme=theme,
        width=int(_num(attrs, "data-w", 1280)),
        font_size=int(_num(attrs, "data-font-size", 22)),
        x=_num(attrs, "data-x", 0),
        y=_num(attrs, "data-y", 0),
    )


def _render_icon(attrs: dict[str, str], theme: ThemeSpec) -> str:
    name = attrs.get("data-name")
    if not name:
        raise ValueError("icon placeholder missing data-name")
    return render_icon_svg(
        name,
        size=int(_num(attrs, "data-size", 48)),
        stroke=attrs.get("data-stroke") or None,
        weight=attrs.get("data-weight") or None,
        theme=theme,
        x=_num(attrs, "data-x", 0),
        y=_num(attrs, "data-y", 0),
    )


_RENDERERS = {"chart": _render_chart, "code": _render_code, "icon": _render_icon}


def expand_enhancements(svg_text: str, theme: Optional[ThemeSpec] = None) -> str:
    """Replace every recognised enhancement placeholder in `svg_text`.

    A placeholder that fails to render is replaced with an inline SVG comment
    so the slide layout still composes — the export does not get aborted by
    bad authoring.
    """
    if theme is None:
        theme = get_theme("dark-tech")

    def _sub(match: re.Match[str]) -> str:
        kind = match.group("kind")
        attrs = _parse_attrs(match.group("attrs"))
        try:
            return _RENDERERS[kind](attrs, theme)
        except Exception as exc:  # noqa: BLE001 — never abort the deck on bad placeholder
            return f"<!-- enhancement {kind} skipped: {exc} -->"

    return _PLACEHOLDER_RE.sub(_sub, svg_text)


def expand_enhancements_in_file(path: Path | str, theme: Optional[ThemeSpec] = None) -> bool:
    """Rewrite an SVG file in place. Returns True if any placeholder expanded."""
    p = Path(path)
    original = p.read_text(encoding="utf-8")
    rewritten = expand_enhancements(original, theme=theme)
    if rewritten != original:
        p.write_text(rewritten, encoding="utf-8")
        return True
    return False
