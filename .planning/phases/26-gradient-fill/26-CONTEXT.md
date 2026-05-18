# Phase 26 Context: Gradient Fill

**Phase:** 26 — Gradient Fill (linear + radial → DrawingML)
**Date:** 2026-05-08
**Status:** Complete (pre-implemented)

<domain>
SVG `<linearGradient>` and `<radialGradient>` elements convert to DrawingML `gradFill` in the PPTX export pipeline.
</domain>

<decisions>
- Gradient resolution uses SVG root element traversal (`_find_gradient_elem`) — no separate `gradients` dict passed through dispatch.
- `xlink:href` inheritance supported via `_resolve_xlink_href()`.
- Linear gradient angle computed via `atan2(dx, dy)` and converted to 1/60000 degree DrawingML units.
- Radial gradient always renders as `<a:path path="circle">` centered at 50%/50%.
- `stop-opacity` mapped to `<a:alpha>` on each stop's `<a:srgbClr>`.
- `url(#gradientId)` references in fill/stroke attributes resolved at dispatch time via `_apply_fill_and_line(shape, elem, rgb_cls, root)`.
- `linearGradient`, `radialGradient`, `stop` are registered as `_noop_converter` (structural, non-drawable).
- SVG QA does NOT ban gradient tags — `linearGradient`, `radialGradient` are in `SUPPORTED_DRAWABLE_TAGS`.
</decisions>

<code_context>
- `converters.py`: `extract_gradient_info()`, `_build_grad_fill_xml_string()`, `_apply_native_gradient()`, `_apply_fill_and_line_with_gradient()`, `_apply_fill_and_line()` — core gradient pipeline using direct DrawingML XML.
- `gradient_fills.py`: `collect_gradients()`, `resolve_gradient_fill()`, `apply_gradient_to_shape()` — parallel module using python-pptx API.
- `exporter.py`: calls `collect_gradients(root)` then `registry.dispatch()`; root set via `registry.set_root(root)`.
- `svg_pipeline.py`: `SUPPORTED_DRAWABLE_TAGS` includes gradient tags; `BANNED_TAGS` does not include them.
- `design_guide.py`: encourages gradient usage in layout examples.
</code_context>

<canonical_refs>
- tools/slide/src/slide_skill/converters.py
- tools/slide/src/slide_skill/gradient_fills.py
- tools/slide/src/slide_skill/exporter.py
- tools/slide/src/slide_skill/svg_pipeline.py
- tests/test_gradient_fills.py
</canonical_refs>
