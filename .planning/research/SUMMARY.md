# Project Research Summary

**Project:** Slide Skill v2.3
**Domain:** SVG-to-PPTX conversion pipeline -- outer glow, soft edge, bilingual export, PDF handout
**Researched:** 2026-05-10
**Confidence:** HIGH

## Executive Summary

Slide Skill v2.3 adds four features to an established SVG-to-PPTX conversion pipeline. Two features (outer glow, soft edge) extend the existing filter_effects.py module using the exact same parse-collect-apply pattern shipped in v2.2 for blur and drop shadow. They require zero new dependencies -- pure lxml DrawingML XML construction. One feature (bilingual export) extends the existing converters.py text layout and i18n.py CJK font routing, also with no new dependencies. Only PDF handout export adds a new runtime dependency: fpdf2 for multi-page PDF generation with CJK TTF font embedding.

The recommended approach is to implement in four phases ordered by ascending risk and descending coupling: soft edge first (simplest discriminator change, zero ambiguity), outer glow second (builds on Phase 1 filter dict extension, requires glow-vs-shadow disambiguation logic), bilingual export third (new layout mode touching text converters, but isolated from filters), and PDF handout last (completely independent new module with a new dependency). This ordering ensures each phase delivers working, testable value before the next begins, and the highest-risk feature (bilingual layout) is approached only after the filter pipeline is stable.

The key risks are threefold. First, glow-vs-shadow ambiguity in SVG filter chains -- both use feGaussianBlur + feFlood, and the discriminator (presence/absence of feOffset and feComposite operator) must be correct or effects are silently misclassified. Second, DrawingML effectLst child ordering is schema-validated in the XSD as a fixed sequence; inserting glow or softEdge in the wrong position produces invalid PPTX. Third, bilingual layout requires two separate text frames per content area with independent font sizing, line height, and width estimation -- cramming both languages into one text frame produces misaligned output.

## Key Findings

### Recommended Stack

Three of four features require zero new dependencies. Only PDF handout adds fpdf2 (pure Python, no C extensions, LGPL license). The project already has lxml, python-pptx, CairoSVG, and Pillow in its environment.

**Core technologies:**
- **lxml 6.1+** (existing): Construct DrawingML glow and softEdge elements -- already used for blur and outerShdw in filter_effects.py
- **python-pptx 1.0.2+** (existing): Access shape XML for OOXML manipulation and create dual text frames for bilingual export
- **i18n.py** (existing): CJK font profiles, language detection, and East Asian typeface routing already work
- **fpdf2 2.8.7** (NEW): Multi-page PDF handout generation with CJK TTF embedding -- chosen over reportlab (heavier) and comtypes (Windows-only)
- **CairoSVG 2.8.2** (existing): Render SVG slides to PNG for PDF embedding as slide thumbnails

### Expected Features

**Must have (table stakes):**
- Outer glow conversion to DrawingML glow element -- natural next effect after v2.2 shadow, same pipeline pattern
- Soft edge conversion to DrawingML softEdge element -- completes the filter effect set
- Glow color and radius from SVG feFlood/feGaussianBlur primitives -- must match SVG design intent
- Multiple effects composing on one shape (glow + shadow in same effectLst) -- real slides combine effects
- Bilingual text visible in PPTX as parallel Chinese + English text frames -- core use case for Chinese academic/business presentations
- PDF handout with slide images on top and speaker notes below -- standard handout format

**Should have (differentiators):**
- SVG glow auto-detection from multi-primitive chains (feGaussianBlur + feFlood + feComposite without feOffset) -- AI authors SVG this way, not as a single primitive
- SVG soft edge detection from standalone feGaussianBlur on SourceAlpha -- differentiates from regular blur
- Bilingual layout via data-bilingual SVG attribute convention -- keeps SVG authoring clean, signals intent to exporter
- Configurable PDF handout layout (1-up, 2-up, 3-up) -- matches PowerPoint handout printing options

**Defer (v2+):**
- Multi-up handout layouts (2-up, 3-up): start with 1-up, grid layouts add complexity without proportional value
- Bilingual auto-detection via Unicode range: require explicit data-bilingual markup instead
- Inner glow, reflection, 3D, bevel, extrusion effects: no clean SVG-to-DrawingML mapping

### Architecture Approach

All four features plug into the existing SVG-first pipeline at well-defined seams. Filter effects extend _parse_filter() and apply_filter_to_shape() in filter_effects.py. Bilingual export is an SVG-stage layout transformation expressed via data-* attributes, converted to dual PPTX text frames during export. PDF handout is a completely new module (pdf_handout.py) that reads existing SVG slides and speaker notes, composes them into multi-page PDF via fpdf2.

**Major components:**
1. **filter_effects.py** (MODIFY): Extend _parse_filter() to return {blur, shadow, glow, soft_edge} dict; add glow and softEdge XML emission in apply_filter_to_shape(); add _reorder_effect_lst() to enforce XSD child ordering
2. **converters.py** (MODIFY): Detect data-bilingual groups in SVG, emit parallel PPTX text frames with per-language font sizing via existing CJK routing
3. **pdf_handout.py** (NEW): Iterate slides, render SVG to PNG via CairoSVG, compose handout pages with fpdf2 (slide thumbnail top half, speaker notes bottom half)
4. **cli.py** (MODIFY): Add pdf-handout subcommand; bilingual mode is triggered by SVG data-bilingual attributes (no CLI flag needed)

### Critical Pitfalls

1. **Glow-vs-shadow misclassification** -- Both use feGaussianBlur + feFlood; the discriminator is feOffset presence and feComposite operator. If wrong, glow exports as shadow with incorrect direction. Prevention: check feComposite operator=in before checking feOffset; if composite-in is present without offset, classify as glow.

2. **DrawingML effectLst child ordering violation** -- The XSD defines CT_EffectList as a fixed sequence: blur, fillOverlay, glow, innerShdw, outerShdw, prstShdw, reflection, softEdge. Out-of-order children cause PowerPoint to silently discard effects. Prevention: implement _reorder_effect_lst() that sorts effectLst children to match the XSD sequence.

3. **Glow radius conversion mismatch** -- SVG stdDeviation is not 1:1 with DrawingML rad. The Gaussian bell curve extends well beyond one stdDeviation. Prevention: apply a correction factor (rad_emu = int(stdDeviation * 2.0 * 25400)) and validate with visual QA at multiple stdDeviation values.

4. **Glow color extracted from shape fill instead of feFlood** -- When a blue shape has a red glow, using the shape fill produces a blue glow (wrong). Prevention: extract color from the feFlood element in the glow chain, not from the shape fill.

5. **Multiple effects on one shape -- second overwrites first** -- The current apply_filter_to_shape() removes and recreates effectLst on each call. If a shape has both glow and shadow, one gets destroyed. Prevention: build all effect children before inserting the effectLst; do not remove existing effectLst when adding new effects.

## Implications for Roadmap

### Phase 1: Soft Edge Filter
**Rationale:** Lowest risk, simplest change. Only modifies the _parse_filter() discriminator for standalone feGaussianBlur in=SourceAlpha with no companion offset or flood. Adds soft_edge key to the filter dict and softEdge emission. Zero risk of breaking existing blur/shadow -- the discriminator is additive.
**Delivers:** Soft edge SVG-to-DrawingML conversion, new unit tests
**Addresses:** Table-stakes feature soft edge conversion to DrawingML
**Avoids:** Pitfall 2 (effectLst ordering) -- softEdge is the last element in the XSD sequence, so insertion position is unambiguous
**Avoids:** Pitfall 5 (algorithm mismatch) -- accept that pixel-perfect parity is impossible for soft edge, use tolerance-based QA

### Phase 2: Outer Glow Filter
**Rationale:** Second lowest risk. Builds on Phase 1 filter dict extension and _reorder_effect_lst(). The glow-vs-shadow disambiguation (Pitfall 1) is the main risk, but it is well-defined: check feComposite before feOffset. The radius correction factor (Pitfall 3) needs empirical validation but the 2x Gaussian approximation is mathematically grounded.
**Delivers:** Outer glow SVG-to-DrawingML conversion with correct color extraction from feFlood, effectLst ordering enforcement, multi-effect composition on single shapes
**Addresses:** Table-stakes features outer glow conversion, glow color and radius from SVG primitives, multiple effects composing on one shape
**Avoids:** Pitfall 1 (glow-vs-shadow misclassification), Pitfall 2 (effectLst ordering), Pitfall 4 (wrong color source), Pitfall 16 (second effect overwrites first)

### Phase 3: Bilingual Export
**Rationale:** Touches a different subsystem (converters, SVG pipeline, i18n) and can be developed independently after filters are stable. The SVG-stage approach (Approach A from architecture research) is recommended -- bilingual pairing expressed in SVG with data-bilingual attributes, converted to dual PPTX text frames during export. This preserves the SVG-first philosophy and enables QA validation before export.
**Delivers:** Bilingual Chinese + English parallel text layout in PPTX, new SVG data-bilingual attribute convention, converter support for dual text frames
**Uses:** Existing i18n.py language profiles, existing converters.py CJK font routing
**Implements:** Bilingual layout component in converters.py
**Avoids:** Pitfall 6 (single text frame for two languages), Pitfall 7 (inconsistent measure_weight between _approx_w_in and LanguageProfile)

### Phase 4: PDF Handout Export
**Rationale:** Completely independent -- new module, new dependency, new CLI command. Can be parallelized with Phase 3 if needed. Uses CairoSVG (existing) for SVG-to-PNG rasterization and fpdf2 (new) for PDF composition. Reads speaker notes from existing notes/ directory and PPTX notes parts.
**Delivers:** Multi-page PDF handout with slide thumbnails and speaker notes, new pdf-handout CLI subcommand, optional fpdf2 dependency
**Uses:** fpdf2 2.8.7, CairoSVG 2.8.2 (existing), existing notes extraction
**Implements:** New pdf_handout.py module
**Avoids:** Pitfall 10 (no existing multi-slide layout), Pitfall 11 (note text overflow), Pitfall 12 (LibreOffice rendering fidelity differences -- use cairo backend instead)

### Phase Ordering Rationale

- Soft edge before outer glow because soft edge has zero ambiguity (standalone blur on alpha) while glow shares primitives with shadow and requires careful disambiguation
- Both filter effects before bilingual/PDF because they share filter_effects.py -- completing filter changes first avoids merge conflicts and ensures the filter pipeline is stable
- Bilingual before PDF handout because bilingual touches existing sensitive code paths (text converters) while PDF handout is a clean new module
- PDF handout last because it is fully independent and the lowest risk of regressions

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Outer Glow):** AI-generated SVG glow patterns vary across tools. Collect representative samples of glow filter chains from different AI SVG generators before finalizing detection logic. The feComposite operator and feMerge node structure may differ from the canonical pattern.
- **Phase 3 (Bilingual Export):** The layout policy decision (stacked vs side-by-side vs single-frame) needs validation with real bilingual content. The data-bilingual SVG attribute convention is new and needs testing with the SVG QA pipeline. CJK font availability on target systems needs a runtime check strategy.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Soft Edge):** Well-documented, single discriminator change, follows exact v2.2 blur pattern
- **Phase 4 (PDF Handout):** fpdf2 API is straightforward, rendering pipeline (CairoSVG to PNG to PDF) is well-understood
## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | DrawingML XML verified from ECMA-376 spec and XSD; fpdf2 evaluated against 4 alternatives; existing deps confirmed in environment |
| Features | HIGH | SVG filter patterns well-understood from v2.2 codebase; DrawingML leaf elements verified; bilingual layout is the only feature with design ambiguity |
| Architecture | HIGH | All four features have clear integration seams in existing codebase; filter dict extension pattern is proven; new PDF module is isolated |
| Pitfalls | HIGH | 16 pitfalls identified from code analysis and spec verification; top 5 have concrete prevention strategies; medium-confidence items (glow radius factor, text glow behavior) are testable empirically |

**Overall confidence:** HIGH

### Gaps to Address

- **Glow radius correction factor:** The 2x multiplier (stdDeviation to DrawingML rad) is based on Gaussian math but PowerPoint internal rendering may differ. Needs empirical validation with visual QA comparing SVG rendering vs PPTX rendering at stdDeviation values 2, 4, 8, 16.
- **Glow on text shapes:** DrawingML glow may only apply to shape geometry, not text glyphs, when applied to a text box. Needs empirical testing to determine if QA warnings are needed for text elements with glow.
- **CJK font bundling for PDF handout:** fpdf2 requires a .ttf file for CJK text. Decision needed on whether to bundle Noto Sans SC (Apache-2.0) or document the system font requirement.
- **Bilingual layout policy:** The recommended stacked approach (Chinese above, English below) needs validation with real content to confirm that line-height differences between CJK (1.5-1.6x) and Latin (1.2-1.4x) do not cause alignment issues at the boundary.
- **_approx_w_in vs LanguageProfile.measure_weight inconsistency:** converters.py uses a hardcoded 1.0 for CJK width while i18n.py uses 1.8. These must be unified before bilingual export can produce correct text frame widths.

## Sources

### Primary (HIGH confidence)
- ECMA-376 Part 4 Section 20.1.8.32 (glow) via c-rex.net -- DrawingML glow element structure
- ECMA-376 Part 3 Primer (Soft Edge Effects) via c-rex.net -- DrawingML softEdge specification
- ECMA-376 Part 3 Primer (Glow Effects) via c-rex.net -- DrawingML glow specification
- Liquid Technologies OOXML Schema (dml-shapeEffects.xsd) -- CT_EffectList sequence ordering, CT_GlowEffect, CT_SoftEdgesEffect
- Microsoft Learn: Glow class, SoftEdge class documentation -- API confirmation
- W3C SVG 1.1 Filter Effects specification -- feGaussianBlur, feFlood, feComposite, feMerge
- Existing codebase analysis: filter_effects.py, converters.py, exporter.py, pdf_export.py, i18n.py, svg_pipeline.py -- all files read directly

### Secondary (MEDIUM confidence)
- fpdf2 PyPI page -- version 2.8.7, API capabilities confirmed
- CairoSVG documentation -- SVG-to-PNG rendering pipeline
- Python PDF library comparison (nutrient.io) -- fpdf2 vs reportlab vs alternatives evaluation
- LibreOffice soft edge import/export commit (tdf#49247) -- OOXML interoperability confirmation
- CJK Typesetting Challenges (asianabsolute.co.uk) -- CJK/Latin layout differences

### Tertiary (LOW confidence)
- CJK/Latin Visual Size Imbalance (Ghostty discussions) -- measure_weight heuristic values
- Microsoft CJK/Latin Text Spacing support article -- line-height ratios

---
*Research completed: 2026-05-10*
*Ready for roadmap: yes*