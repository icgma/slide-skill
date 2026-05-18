# Phase 27 Summary: Clip-Path & Mask

**Phase:** 27 — Clip-Path & Mask (customGeometry clip)
**Status:** Complete
**Tests:** 19 passing

## What Was Done

Phase 27 was pre-implemented in prior milestones with the exporter integration gap now closed:

1. **CP-01**: SVG `<clipPath>` → DrawingML `a:clipPath` — ✅ Verified + exporter connected
2. **CP-02**: SVG `<mask>` → DrawingML `a:clipPath` (binary clip, no alpha) — ✅ Verified (known limitation: OOXML lacks alpha mask)
3. **CP-03**: `clip-path="url(#clipId)"` attribute resolved and applied — ✅ Verified
4. **CP-04**: SVG QA updated — clip-path/mask references not banned — ✅ Verified (was already allowed)

## Key Change

Connected `clip_path.py` application layer to the exporter dispatch loop:
- After each shape is created, check `clip-path` or `mask` attribute on the SVG element
- Resolve via `resolve_clip_path()` and apply via `apply_clip_path_to_shape()`

## Known Limitations

- Mask alpha/semi-transparency not supported (OOXML constraint)
- Only first child of clipPath/mask processed
- `clipPathUnits` / `maskContentUnits` not implemented
