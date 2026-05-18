# Phase 31: Advanced Filter Effects - Context

**Gathered:** 2026-05-10
**Status:** Ready for planning

<domain>
## Phase Boundary

SVG soft edge, outer glow, and multi-effect composition all convert correctly to DrawingML, with effectLst child ordering enforced per OOXML schema.

Delivers: `_parse_filter()` detects soft edge (feGaussianBlur on SourceAlpha alone) and outer glow (feGaussianBlur + feFlood + feComposite chain) patterns. `apply_filter_to_shape()` composes multiple effects into a single `<a:effectLst>` with XSD-ordered children. SVG pipeline gains `_soft_edge_filter_def()` and `_glow_filter_def()` helper functions.

Requirements: FE-01, FE-02, FE-03, FE-04, FE-05.
FE-05 is already satisfied — `feFlood`, `feComposite`, `feMerge` are already in `SUPPORTED_DRAWABLE_TAGS` (svg_pipeline.py:66-67).

</domain>

<decisions>
## Implementation Decisions

### Filter Graph Detection
- **D-01:** Pattern-based detection — check `in=` attribute and sibling primitives (no full graph traversal)
- **D-02:** Glow takes precedence over soft edge when blur(SourceAlpha) + feFlood + feComposite are all present
- **D-03:** feMerge/feMergeNode ignored during detection (structural glue, doesn't change effect type)
- **D-04:** Detection priority order: Shadow > Glow > SoftEdge > Blur (shadow checked first via feOffset/feDropShadow)
- **D-05:** `in="SourceAlpha"` required for glow and soft edge; `SourceGraphic` or no `in` treated as regular blur
- **D-06:** feComposite `operator="in"` required specifically for glow detection; other operators not recognized as glow
- **D-07:** Glow requires feFlood — no glow without explicit flood color source
- **D-08:** feFlood+feComposite without feOffset = glow; feFlood+feComposite with feOffset = shadow (card-shadow pattern)
- **D-09:** feGaussianBlur(SourceAlpha) alone (no feFlood, no feOffset) = always soft edge, regardless of `result=` attribute
- **D-10:** Track feGaussianBlur `result=` names and verify feComposite `in2` references the blur result. If no `result=` attribute, use implicit SVG default (index-based)
- **D-11:** Only first feGaussianBlur processed for effect detection; additional blur elements ignored
- **D-12:** Additive return dict — new `soft_edge` and `glow` keys alongside existing `blur` and `shadow`. All 4 keys can be populated simultaneously from a single filter
- **D-13:** A single feGaussianBlur(SourceAlpha) used by both feOffset→shadow AND feFlood+feComposite→glow chains produces both shadow and glow effects
- **D-14:** Default glow color: black (#000000), 100% opacity when feFlood has no explicit flood-color
- **D-15:** Unrecognized filter patterns fallback to blur extraction (stdDeviation → DrawingML blur)
- **D-16:** Filters containing unsupported SVG primitives (feColorMatrix, feTurbulence, etc.) are skipped entirely — no effect detection

### Multi-Effect Composition
- **D-17:** Replace existing effectLst (same as current behavior) — don't merge with existing
- **D-18:** XSD ordering enforced via explicit order constant: `EFFECT_ORDER = ["blur", "glow", "outerShdw", "softEdge"]` (subset of full XSD: blur, fillOverlay, glow, innerShdw, outerShdw, prstShdw, reflection, softEdge)
- **D-19:** Two separate reorder functions: `_reorder_sppr()` (positions effectLst within spPr) and `_reorder_effectlst()` (orders children within effectLst per XSD)
- **D-20:** If filter_info has no effects (all keys None), return early without creating effectLst
- **D-21:** Glow XML: `<a:glow rad="EMU"><a:srgbClr val="COLOR"><a:alpha val="PCT"/></a:srgbClr></a:glow>`
- **D-22:** SoftEdge XML: `<a:softEdge rad="EMU"/>` — no children, just radius attribute
- **D-23:** Soft edge and blur are mutually exclusive — if softEdge is detected, don't also emit blur
- **D-24:** Glow and outerShdw can coexist in the same effectLst (success criterion 3)
- **D-25:** `apply_filter_to_shape()` handles all effect types internally — no exporter dispatch loop changes needed
- **D-26:** If one effect fails to convert (e.g., invalid stdDeviation), skip that effect but continue with others
- **D-27:** Filter propagation from parent `<g>` elements follows existing behavior — no changes for soft edge/glow

### Glow Radius and Color
- **D-28:** Glow radius: `stdDeviation * 25400` (same multiplier as blur, no scale_x/scale_y)
- **D-29:** SoftEdge radius: `stdDeviation * 25400` (same as blur and glow)
- **D-30:** Min radius: `max(rad, 1)` for all effect types consistently
- **D-31:** Opacity mapping: `int(flood_opacity * 100000)` (direct mapping, same formula as shadow)
- **D-32:** Default alpha when no flood-opacity: 100000 (full opacity per SVG spec)
- **D-33:** srgbClr only for glow color — no theme color (schemeClr) support
- **D-34:** Negative stdDeviation clamped to 0, effect skipped

### SVG Pipeline Glow Generation
- **D-35:** Add `_soft_edge_filter_def(index, std)` and `_glow_filter_def(index, color, opacity, std)` helper functions in svg_pipeline.py
- **D-36:** Filter ID naming: `soft-edge-{index:02d}` and `glow-{index:02d}` (consistent with `card-shadow-{index:02d}`)
- **D-37:** Glow defaults: stdDeviation from caller parameter, color from palette accent, flood-opacity=0.5
- **D-38:** Soft edge defaults: stdDeviation=3 (subtle softening)
- **D-39:** Filter region: same as card-shadow — x="-20%" y="-20%" width="140%" height="150%"
- **D-40:** Glow filter def includes feMerge at end (stack glow + SourceGraphic), same as card-shadow pattern
- **D-41:** Utility functions only — don't integrate into existing layout templates
- **D-42:** feFlood/feComposite/feMerge/feMergeNode already registered as `_noop_converter` — no changes needed

### Claude's Discretion
- No areas deferred to Claude — user selected all recommended options

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Core Pipeline
- `tools/slide/src/slide_skill/filter_effects.py` — Existing filter parsing, resolution, and DrawingML application. ALL Phase 31 changes happen here.
- `tools/slide/src/slide_skill/exporter.py` — Dispatch loop that calls `apply_filter_to_shape()`. Lines 117-130 apply filter resolution.
- `tools/slide/src/slide_skill/converters.py` — `_noop_converter` registrations (lines 574-577). Already handles filter primitives.

### SVG Pipeline
- `tools/slide/src/slide_skill/svg_pipeline.py` — `_shadow_filter_def()` at line 1118 is the pattern for new filter def functions. `SUPPORTED_DRAWABLE_TAGS` at line 63 already includes feFlood, feComposite, feMerge, feMergeNode.
- `tools/slide/src/slide_skill/qa.py` — No changes needed (FE-05 already satisfied).

### Tests
- `tests/test_charts.py` — Existing test patterns for filter effects.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `filter_effects.py:_parse_filter()` — Extend with soft_edge/glow detection. Current structure extracts blur/stdDeviation, shadow params, offset, flood_color/opacity. Add `soft_edge` and `glow` keys.
- `filter_effects.py:apply_filter_to_shape()` — Extend to handle glow and softEdge DrawingML output. Current function creates blur/shadow children in effectLst.
- `filter_effects.py:_reorder_sppr()` — Positions effectLst within spPr. Keep as-is.
- `filter_effects.py:_normalize_color()` — Color parsing utility. Reuse for glow color extraction.
- `svg_pipeline.py:_shadow_filter_def()` — Template for new `_glow_filter_def()` and `_soft_edge_filter_def()` functions.

### Established Patterns
- **Collect/resolve/apply pattern:** `collect_filters()` → `resolve_filter()` → `apply_filter_to_shape()`. Same as gradient_fills.py and pattern_fill.py.
- **Additive effect dict:** `{blur: {...}, shadow: {...}}` extends to `{blur, shadow, glow, soft_edge}`.
- **EMU conversion:** `int(value * 25400)` for radius, `int(value * 914400)` for offsets. Glow and softEdge use 25400.
- **_noop_converter:** Structural SVG elements registered as no-ops in converter registry.

### Integration Points
- `exporter.py` post-processing loop (L117-130) — calls `resolve_filter()` + `apply_filter_to_shape()` per shape. No changes needed (apply_filter handles new types internally).
- `svg_pipeline.py` SUPPORTED_DRAWABLE_TAGS (L63-69) — Already includes all needed filter primitives.
- `svg_pipeline.py` _shadow_filter_def — Pattern for new filter def functions.

</code_context>

<specifics>
## Specific Ideas

No specific requirements — user selected all recommended options consistently.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 31-Advanced Filter Effects*
*Context gathered: 2026-05-10*
