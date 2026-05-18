# Phase 30 Context: Drop Shadow

**Phase:** 30 — Drop Shadow (feDropShadow → effectLst outerShdw)
**Date:** 2026-05-08
**Status:** Complete (implemented alongside Phase 29)

<domain>
SVG `<feDropShadow>` and card-shadow pattern (feGaussianBlur+feOffset+feFlood+feComposite+feMerge) convert to DrawingML `<a:effectLst><a:outerShdw>`.
</domain>

<decisions>
- `feDropShadow` parsed for dx, dy, stdDeviation, flood-color, flood-opacity.
- Card-shadow pattern (feGaussianBlur+feOffset+feFlood) recognized and converted to equivalent `outerShdw`.
- DrawingML `<a:outerShdw>` with sx=0, sy=0, tx/ty offset, rad blur radius, algn="bl", rotWithShape="0".
- Shadow color via `<a:srgbClr val="COLOR"><a:alpha val="N"/></a:srgbClr>`.
- Multiple effects in same `<effectLst>` composed (blur + shadow both present).
- SVG QA: feDropShadow and feOffset already allowed — no changes needed.
</decisions>

<canonical_refs>
- tools/slide/src/slide_skill/filter_effects.py
- tools/slide/src/slide_skill/exporter.py
- tests/test_filter_effects.py
</canonical_refs>
