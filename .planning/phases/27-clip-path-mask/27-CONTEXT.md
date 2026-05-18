# Phase 27 Context: Clip-Path & Mask

**Phase:** 27 — Clip-Path & Mask (customGeometry clip)
**Date:** 2026-05-08
**Status:** Complete (pre-implemented + exporter integration)

<domain>
SVG `<clipPath>` and `<mask>` elements convert to DrawingML `a:clipPath` clipping applied to PPTX shapes.
</domain>

<decisions>
- Clip-path resolution via `resolve_clip_path()` from `url(#id)` attribute values.
- Both `clip-path` and `mask` SVG attributes checked on each element.
- `apply_clip_path_to_shape()` generates `<a:clipPath pref="1"><a:path>...</a:path></a:clipPath>` in `spPr`.
- Path commands built via `build_freeform_xml` from `geometry.py` (reuses existing geometry pipeline).
- Mask elements parsed same as clipPath (type="mask") — alpha/semi-transparency is not supported in OOXML, so masks degrade to binary clip.
- Only first child element of clipPath/mask is processed (multi-shape union not implemented).
- `clipPathUnits` / `maskContentUnits` not implemented (assumes userSpaceOnUse).
- clipPath and mask registered as `_noop_converter` in converter registry (structural, non-drawable).
- SVG QA does NOT ban clip-path/mask attributes or clipPath tag.
</decisions>

<code_context>
- `clip_path.py`: `collect_clip_paths()`, `resolve_clip_path()`, `apply_clip_path_to_shape()` — full pipeline.
- `exporter.py`: dispatch loop now tracks drawable elements and applies clip-path/mask after shape creation.
- `geometry.py`: `build_freeform_xml()`, `compute_bbox()` — reused for clip path geometry.
- `svg_pipeline.py`: `SUPPORTED_DRAWABLE_TAGS` includes "clipPath"; no banned attrs for clip-path/mask.
</code_context>

<canonical_refs>
- tools/slide/src/slide_skill/clip_path.py
- tools/slide/src/slide_skill/exporter.py
- tools/slide/src/slide_skill/geometry.py
- tools/slide/src/slide_skill/svg_pipeline.py
- tests/test_clip_path.py
</canonical_refs>
