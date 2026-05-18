# Phase 29 Context: Gaussian Blur

**Phase:** 29 — Gaussian Blur (feGaussianBlur → effectLst blur)
**Date:** 2026-05-08
**Status:** Implementation

<domain>
SVG `<filter>` with `<feGaussianBlur>` converts to DrawingML `<a:effectLst><a:blur>` in the PPTX export pipeline.
</domain>

<decisions>
- New module `filter_effects.py` handles filter collection, resolution, and application.
- `collect_filters(svg_root)` gathers all `<filter>` elements from `<defs>`.
- For each filter, parse child primitives:
  - `feGaussianBlur` → extract `stdDeviation` (single value or x,y pair → use max)
  - `feDropShadow` → extract `dx`, `dy`, `stdDeviation`, `flood-color`, `flood-opacity`
  - `feOffset` → extract `dx`, `dy` (used in shadow pipeline)
  - `feFlood` → extract `flood-color`, `flood-opacity` (used in shadow pipeline)
- `apply_filter_to_shape(shape, filter_info, scale_x, scale_y)` injects DrawingML:
  - Blur: `<a:effectLst><a:blur rad="N"/></a:effectLst>` where rad = stdDeviation * 25400 (EMU-ish)
  - Shadow: `<a:effectLst><a:outerShdw sx="0" sy="0" tx="N" ty="N" rad="N" algn="bl"><a:srgbClr val="COLOR"><a:alpha val="N"/></a:srgbClr></a:outerShdw></a:effectLst>`
- `filter` attribute on SVG elements checked in exporter post-processing loop (alongside clip-path/pattern).
- `filter` elements remain `_noop_converter` (structural, non-drawable).
- SVG QA: no changes needed — filter tags already allowed.
- Card-shadow pattern (feGaussianBlur+feOffset+feFlood+feComposite+feMerge) recognized and converted to single outerShdw.
</decisions>

<code_context>
- `svg_pipeline.py`: `_shadow_filter_def()` already generates card-shadow filter SVG (L1118-1134).
- `exporter.py`: post-processing loop at L117-130 — add filter resolution here.
- `converters.py`: `_noop_converter` for filter tags (L574-577), `_apply_fill_and_line` for fill/stroke only.
- `gradient_fills.py`: pattern for collect/resolve/apply module (follow same shape).
</code_context>

<canonical_refs>
- tools/slide/src/slide_skill/svg_pipeline.py
- tools/slide/src/slide_skill/exporter.py
- tools/slide/src/slide_skill/converters.py
- tools/slide/src/slide_skill/gradient_fills.py
</canonical_refs>
