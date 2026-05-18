# Phase 28 Context: Pattern Fill

**Phase:** 28 — Pattern Fill (blipFill tile)
**Date:** 2026-05-08
**Status:** Complete (pre-implemented + exporter integration)

<domain>
SVG `<pattern>` elements convert to DrawingML `a:blipFill` with `a:tile` tiling applied to PPTX shapes.
</domain>

<decisions>
- Pattern resolution via `resolve_pattern_fill()` from `fill="url(#id)"` attribute values.
- `render_pattern_image()` uses Pillow to rasterize pattern children to PNG tile image.
- `apply_pattern_to_shape()` replaces shape fill with `<a:blipFill><a:blip r:embed="rIdN"/><a:tile tx="..." ty="..."/></a:blipFill>`.
- Pattern children support: rect, circle, line (3 types). Path/polygon/polyline/ellipse/text not rendered.
- `patternUnits` / `patternContentUnits` parsed but not used for scaling (fixed dpi/96 ratio).
- Pattern image added via `_add_image_relationship()` to the slide part.
- `pattern` registered as `_noop_converter` in converter registry (structural, non-drawable).
- SVG QA does NOT ban pattern tag or `fill="url(#id)"` references.
- Pattern fill takes precedence after gradient check (if fill url is not a gradient, check for pattern).
</decisions>

<code_context>
- `pattern_fill.py`: `collect_patterns()`, `resolve_pattern_fill()`, `render_pattern_image()`, `apply_pattern_to_shape()` — full pipeline.
- `exporter.py`: dispatch loop now applies pattern fill after shape creation (when fill attr starts with `url(#` and patterns dict has match).
- `svg_pipeline.py`: `SUPPORTED_DRAWABLE_TAGS` includes "pattern".
</code_context>

<canonical_refs>
- tools/slide/src/slide_skill/pattern_fill.py
- tools/slide/src/slide_skill/exporter.py
- tools/slide/src/slide_skill/svg_pipeline.py
- tests/test_pattern_fill.py
</canonical_refs>
