# Phase 8 Context: SVG Path Geometry

**Phase:** 8
**Milestone:** v1.2
**Created:** 2026-05-01
**Status:** Discussed

## Goal

Add progressive SVG path/curve/arc/polygon conversion to native editable PPTX freeform shapes with an extensible converter registry.

## Requirements

- GEO-01: SVG `<path>` cubic beziers (C/c) → native freeform shapes
- GEO-02: SVG arc commands (A/a) → cubic bezier approximation → freeform shapes
- GEO-03: SVG `<polygon>` and `<polyline>` → native freeform paths
- GEO-04: Relative path commands (lowercase) resolve to absolute coordinates
- GEO-05: Smooth curve (S/s) and quadratic (Q/q) → cubic bezier equivalents
- GEO-06: Extensible converter registry (add converters without modifying dispatch)
- GEO-07: SVG QA checker allows path/polygon/polyline tags, validates attributes
- GEO-08: Test fixture covers all SVG path command types with round-trip verification

## Decisions from Discussion

### 1. Dependency: svgpathtools

Add `svgpathtools>=1.6` as a runtime dependency. Handles all SVG path command parsing including edge cases (implicit line-tos, repeated parameters, arc flags, relative→absolute, smooth/quadratic→cubic reduction). Writing a custom parser is error-prone and not justified for this scope.

**Why:** Covers all 20 SVG path commands (M/mLlCcSsQqTtAaZz) with mature, tested parsing. Avoids re-implementing complex arc flag handling and implicit command continuation.

### 2. File Decomposition: 2 New Files

- `geometry.py` — SVG path parsing + DrawingML freeform XML construction (the conversion pipeline from SVG segments to OOXML `<a:path>` elements)
- `converters.py` — Converter registry + converter functions/classes for path, polygon, polyline + refactored existing primitive handlers

**Why:** Keeps "how to convert geometry" separate from "what to dispatch to." The parser and builder are tightly coupled (segments → XML), so one module makes sense. The dispatch layer is a separate concern.

### 3. Registry Pattern: Pragmatic Dict Dispatch

Thin `ConverterRegistry` class wrapping a dict of `{tag: converter_fn}`. No abstract base class. A converter is a callable that accepts `(slide, elem, scale_x, scale_y)`. Extensibility (GEO-06) comes from `registry.register(tag, fn)` — no inheritance ceremony.

**Why:** We're adding 3 new converters to 6 existing ones. A dict is sufficient. The class exists for a clean public API (`register`, `find`, `iter_supported_tags`) without over-engineering.

### 4. Freeform Shape Construction: Hybrid Approach

Use python-pptx to create the shape container (positioning, fill, line styling) and inject custom `<a:cubicBezTo>` elements directly into the underlying XML via `lxml`. python-pptx's `build_freeform()` only supports `move_to`/`line_to` — cubic beziers require direct XML construction.

**Why:** Reuses python-pptx infrastructure for everything except bezier segments. Minimizes the surface for coordinate system bugs (python-pptx handles EMU conversion for the shape wrapper). Only the path geometry needs manual XML.

## Scope Boundaries

- **In scope:** path, polygon, polyline conversion; all 20 SVG path commands; arc→bezier approximation; converter registry; SVG QA rule updates
- **Out of scope:** `transform` attribute handling (remains banned); `<use>` element (remains unsupported); gradient fills; clip-paths; pattern fills
- **Must preserve:** All 6 existing primitives (rect, circle, ellipse, line, text, image) produce identical output. Full test suite passes.

## Technical Context

### Coordinate System

SVG uses top-left origin, Y-down, pixel units. DrawingML freeform paths use EMU (914400/inch) relative to the shape bounding box. Conversion pipeline:

1. Parse SVG path into segments (svgpathtools)
2. Compute bounding box of all points
3. Scale all points using existing `scale_x`/`scale_y`
4. Convert to EMU relative to bounding box
5. Build `<a:path w="..." h="...">` with child elements

### Arc → Bezier Approximation

Standard approach: subdivide arcs with sweep > 90° into multiple bezier segments. Each segment uses the 4/3·tan(θ/4) control point formula. Circular arcs are exact; elliptical arcs have negligible error (<0.03% max deviation for 90° segments).

### SVG QA Changes

- Move `path`, `polygon`, `polyline` from `UNSUPPORTED_DRAWABLE_TAGS` to `SUPPORTED_DRAWABLE_TAGS`
- Add attribute validation for path `d`, polygon `points`, polyline `points`
- Update `_iter_drawables` in exporter to use registry instead of hard-coded tag list

## Risk Areas

1. **Coordinate mismatch** — freeform paths have many points, each must scale correctly. Mitigate with bounding-box-first approach.
2. **Silent shape loss** — unhandled path commands must log warnings, not silently skip. Mitigate with explicit command mapping.
3. **Arc approximation fidelity** — elliptical arcs with rx≠ry need testing. Mitigate with dedicated arc test cases.

## Dependencies

- `svgpathtools>=1.6` (NEW) — SVG path `d` attribute parsing
- `lxml` (EXISTING via python-pptx) — DrawingML XML construction
- `python-pptx` (EXISTING) — shape container, fill/line styling

---
*Context created: 2026-05-01*
