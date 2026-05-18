# Phase 29 Summary: Gaussian Blur

**Phase:** 29 — Gaussian Blur (feGaussianBlur → effectLst blur)
**Status:** Complete
**Tests:** 15 passing

## What Was Done

1. **BLUR-01**: `feGaussianBlur` `stdDeviation` parsed (single + x,y pair) — ✅
2. **BLUR-02**: `<a:effectLst><a:blur rad="N"/></a:effectLst>` injected into `spPr` — ✅
3. **BLUR-03**: `filter="url(#filterId)"` resolved and applied in exporter — ✅
4. **BLUR-04**: SVG QA — no changes needed, filter tags already allowed — ✅
5. **PIPE-01**: Exporter dispatch loop checks `filter` attribute — ✅
6. **PIPE-02**: `filter` elements registered as `_noop_converter` — ✅ (pre-existing)

## Key Implementation

- New `filter_effects.py` module: `collect_filters()`, `resolve_filter()`, `apply_filter_to_shape()`
- Parses `feGaussianBlur`, `feDropShadow`, `feOffset`+`feFlood` combination (card-shadow pattern)
- DrawingML output: `<a:blur>` for standalone blur, `<a:outerShdw>` for shadow
- `spPr` reordering ensures `effectLst` after geometry elements
- Integrated into exporter post-processing loop (before clip-path/pattern)
