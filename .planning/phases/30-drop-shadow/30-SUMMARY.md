# Phase 30 Summary: Drop Shadow

**Phase:** 30 — Drop Shadow (feDropShadow → effectLst outerShdw)
**Status:** Complete
**Tests:** 15 passing (shared with Phase 29 in test_filter_effects.py)

## What Was Done

1. **SHAD-01**: `feDropShadow` dx/dy/stdDeviation/flood-color/flood-opacity parsed — ✅
2. **SHAD-02**: `feOffset`+`feGaussianBlur`+`feFlood` combination recognized as shadow — ✅ (card-shadow pattern)
3. **SHAD-03**: `<a:outerShdw>` with offset, blur, color, alpha injected — ✅
4. **SHAD-04**: SVG QA — no changes needed, feDropShadow/feOffset already allowed — ✅
5. **PIPE-03**: Multiple effects in same `<effectLst>` composed — ✅ (blur + shadow path)

## Key Implementation

All implemented in `filter_effects.py` alongside Phase 29:
- `_parse_filter()` detects both `feDropShadow` and card-shadow pattern
- `apply_filter_to_shape()` generates `<a:outerShdw>` when shadow info present
- Card-shadow (used by 3 layout primitives in svg_pipeline.py) now produces native PPTX shadows
