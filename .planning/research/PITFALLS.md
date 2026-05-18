# Domain Pitfalls: v2.3 Outer Glow, Soft Edge, Bilingual Export, PDF Handout

**Domain:** SVG-to-PPTX conversion pipeline (slide-skill v2.3)
**Researched:** 2026-05-10
**Codebase base:** `tools/slide/src/slide_skill/filter_effects.py`, `converters.py`, `exporter.py`, `pdf_export.py`, `i18n.py`

---

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Glow Is Not a Single SVG Primitive -- It Is a Multi-Step Filter Chain

**What goes wrong:** The current `_parse_filter()` (filter_effects.py:27-78) iterates filter children sequentially and stores at most one `blur`, one `shadow`, one `offset`, and one `flood_color`/`flood_opacity`. It silently drops `feComposite` and `feMerge` nodes (registered as no-op converters in converters.py:598). When an SVG glow arrives as `feGaussianBlur` + `feFlood` + `feComposite` (operator="in") + `feMerge`, the parser sees only the blur and the flood, never recognizing the composite operation that distinguishes glow from a plain blur or shadow.

**Why it happens:** Glow and shadow share the same building blocks (blur + color + offset). The composite operator (`in`, `out`, `over`, `atop`) is what differentiates them. The current parser has no composite awareness.

**Consequences:** Glow filters are either silently ignored or mis-identified as blur, producing wrong visual output. Shadow filter detection (line 70-76) already does a heuristic "blur + offset = shadow" -- adding glow detection without understanding composites will create ambiguous detection that wrongly classifies glow as shadow.

**Prevention:** Extend `_parse_filter()` to:
1. Collect ALL filter primitives (including `feComposite` with its `operator`, `in`, `in2` attributes and `feMerge` with its `feMergeNode` children).
2. Implement pattern matching: if the chain is `blur(SourceAlpha) + flood(color) + composite(in) + merge([glow, SourceGraphic])` then it is a glow, not a shadow.
3. Store a new `"glow"` key in the parsed filter dict alongside existing `"blur"` and `"shadow"`.

**Detection:** Any SVG glow filter in QA test input that fails to produce `<a:glow>` in the exported PPTX XML.

**Confidence:** HIGH -- verified against current code (filter_effects.py:27-78) and OOXML schema (CT_GlowEffect at dml-shapeEffects.xsd).

---

### Pitfall 2: DrawingML effectLst Element Ordering Is Schema-Validated

**What goes wrong:** The current `apply_filter_to_shape()` (filter_effects.py:106-153) appends effect children to `effectLst` in arbitrary order (blur first, then shadow). The OOXML XSD defines `CT_EffectList` as a **sequence** with fixed ordering: `blur`, `fillOverlay`, `glow`, `innerShdw`, `outerShdw`, `prstShdw`, `reflection`, `softEdge`. When glow and softEdge are added, inserting them in the wrong position will produce schema-invalid PPTX files.

**Why it happens:** The existing `_reorder_sppr()` (line 157-176) only reorders `effectLst` relative to its siblings in `spPr`. It does NOT reorder children within `effectLst` itself. Currently only blur and outerShdw are emitted, and they happen to be the first two in the sequence, so ordering has not mattered yet.

**Consequences:** PowerPoint may silently discard or ignore effects when opening a PPTX with out-of-order effectLst children. Some strict OOXML validators will reject the file.

**Prevention:** After building the `effectLst`, sort its children to match the XSD sequence order. Implement a `_reorder_effect_lst()` function that enforces: blur -> fillOverlay -> glow -> innerShdw -> outerShdw -> prstShdw -> reflection -> softEdge.

**Detection:** Validate exported PPTX against OOXML XSD; any ordering violation is a test failure.

**Confidence:** HIGH -- verified against the dml-shapeEffects.xsd schema (CT_EffectList sequence definition).

---

### Pitfall 3: Glow Radius Conversion -- SVG stdDeviation Is NOT DrawingML rad

**What goes wrong:** Directly using `stdDeviation` from `feGaussianBlur` as the DrawingML `<a:glow rad="...">` value produces incorrectly sized glow. The current blur implementation (filter_effects.py:125) uses `rad = int(blur["stdDeviation"] * 25400)`, treating stdDeviation as a pixel-like SVG unit and converting to EMU. For glow, the visual spread is typically 2-3x the stdDeviation because the Gaussian bell curve extends well beyond one standard deviation.

**Why it happens:** SVG `stdDeviation` controls the Gaussian kernel spread. DrawingML `rad` is the visual radius of the glow effect in EMU. PowerPoint internally applies its own glow rendering that may not match SVG's Gaussian convolution. A straight 1:1 conversion makes the PPTX glow look thinner than the SVG original.

**Consequences:** Visual QA snapshot comparison shows glow is too small or too large. Users perceive the PPTX as "missing the glow" or "wrong glow size."

**Prevention:** Apply a correction factor. The effective glow radius in SVG is approximately `2 * stdDeviation` (the 95% coverage radius of a Gaussian). Initial formula: `rad_emu = int(stdDeviation * 2.0 * 25400)`. Validate with a visual QA test comparing SVG rendering vs PPTX rendering at multiple stdDeviation values (2, 4, 8, 16).

**Detection:** Side-by-side visual QA with pixel-similarity scoring; threshold for glow radius mismatch.

**Confidence:** MEDIUM -- the 2x factor is based on Gaussian math, but PowerPoint's internal glow rendering may use a different falloff curve. Requires empirical validation.

---

### Pitfall 4: Glow Alpha/Color Must Come from feFlood, Not the Shape Fill

**What goes wrong:** When building `<a:glow>`, using the shape's fill color instead of the filter's `feFlood` color produces wrong glow color. SVG glow color is explicitly defined in the `feFlood` element's `flood-color` and `flood-opacity` attributes.

**Why it happens:** The existing shadow implementation (filter_effects.py:53-58) correctly extracts `flood-color` and `flood-opacity` from `feDropShadow`. But for glow, the flood attributes come from a separate `feFlood` element, not from `feDropShadow`. The parser must associate the flood element with the correct blur in the chain.

**Consequences:** A red shape with a blue glow in SVG becomes a red shape with a red glow in PPTX -- visually wrong.

**Prevention:** When the glow pattern is detected (feGaussianBlur + feFlood + feComposite), extract color from `feFlood` and pass it as `<a:srgbClr>` child of `<a:glow>`. Use `flood-opacity` as `<a:alpha>` inside the color element, matching the existing shadow pattern (filter_effects.py:149-152).

**Detection:** Unit test: SVG with explicit flood-color="#FF0000" on a shape with fill="#0000FF" -- verify the exported glow color is FF0000, not 0000FF.

**Confidence:** HIGH -- verified from OOXML schema (CT_GlowEffect requires EG_ColorChoice child) and current code pattern.

---

### Pitfall 5: SVG Soft Edge Has No Direct OOXML Equivalent -- Precision Will Differ

**What goes wrong:** SVG soft-edge effects are typically implemented as `feGaussianBlur` on `SourceAlpha` with `edgeMode="duplicate"` (or a `feComposite` that feathers the alpha channel inward). DrawingML `<a:softEdge>` is a single attribute `rad` (in EMU) that tells PowerPoint to apply its own internal alpha feathering. The two implementations use fundamentally different algorithms.

**Why it happens:** SVG's Gaussian blur applies a mathematical convolution that produces a smooth, symmetric alpha falloff. PowerPoint's softEdge is a proprietary implementation whose exact falloff curve is undocumented. There is no 1:1 mapping.

**Consequences:** Visual QA shows soft-edge in PPTX looks slightly different from SVG -- edges may be more or less feathered than intended. This is an inherent precision gap, not a bug.

**Prevention:**
1. Accept that pixel-perfect parity is impossible for soft-edge (already acknowledged in PROJECT.md "Out of Scope: Pixel-perfect cross-renderer parity in v1").
2. Use `rad_emu = int(stdDeviation * 25400)` as a reasonable approximation (same conversion as blur).
3. Document the expected visual tolerance in QA (e.g., 90% pixel similarity instead of 95%).
4. If the SVG soft-edge uses `feComponentTransfer` or `feColorMatrix` for custom alpha curves, flag it as unsupported and emit a QA warning instead of attempting conversion.

**Detection:** Visual QA with explicit tolerance relaxation for soft-edge slides.

**Confidence:** HIGH -- this is a fundamental algorithmic mismatch, verified from both SVG spec (W3C SVG11/filters) and OOXML schema (CT_SoftEdgesEffect has only `rad` attribute).

---

### Pitfall 6: Bilingual Parallel Text Requires Two Separate Text Frames, Not One

**What goes wrong:** Attempting to put Chinese and English parallel text in a single PPTX text frame with mixed fonts. PowerPoint applies a single default font per run; mixing CJK and Latin in the same run relies on font fallback, which is unpredictable across systems.

**Why it happens:** The existing `convert_text()` (converters.py:390-498) creates one text frame per SVG `<text>` element. It does set `<a:ea>` for CJK fonts (line 477-483), which handles mixed-font runs. But bilingual export is a different scenario: it requires rendering the SAME content in two languages side-by-side, which means two separate text elements in the SVG, each needing independent layout.

**Consequences:** If both languages are crammed into one text frame, line-height differences between CJK (1.5-1.6x) and Latin (1.2-1.4x) cause misalignment. CJK characters at the same point size appear visually smaller than Latin (monospaced square vs proportional), making the parallel text look unbalanced.

**Prevention:**
1. Define bilingual layout as two independent text blocks (e.g., upper/lower or left/right) with separate font-family, font-size, and line-height settings.
2. Use the existing `i18n.py` `LanguageProfile` system to apply per-language `line_height` and `measure_weight` multipliers.
3. Set `<a:ea>` for the CJK block and `<a:latin>` for the English block explicitly, avoiding font fallback.
4. Test with mixed content: CJK characters with embedded Latin (e.g., "PPT" inside Chinese text) -- ensure `<a:ea>` and `<a:latin>` are both set on the same run for these cases.

**Detection:** Visual QA on bilingual slides: text blocks should be vertically aligned with consistent spacing.

**Confidence:** HIGH -- verified from existing code (converters.py:460-483 already handles `<a:ea>`) and CJK typography references.

---

### Pitfall 7: CJK Line Height and Character Width Mismatch in Bilingual Layout

**What goes wrong:** The current `_approx_w_in()` (converters.py:424-426) uses a fixed heuristic of 1.0 for CJK and 0.55 for Latin character width estimation. But the `i18n.py` `LanguageProfile.measure_weight` for Chinese is 1.8, not 1.0. These two systems are inconsistent.

**Why it happens:** `_approx_w_in()` was written before `i18n.py` was introduced. It uses a hardcoded heuristic (CJK char = 1.0 em, Latin char = 0.55 em) that does not reference `LanguageProfile.measure_weight`. When bilingual export uses both systems, the width estimates will conflict.

**Consequences:** Text frame widths are miscalculated, causing overflow or excessive whitespace. CJK text may wrap incorrectly. The bilingual parallel text blocks will have mismatched widths.

**Prevention:** Refactor `_approx_w_in()` to accept a `LanguageProfile` parameter and use its `measure_weight` for character width estimation. For bilingual layouts, calculate each block's width independently using the appropriate profile.

**Detection:** Unit test: compute width for "Hello World" and for a CJK equivalent -- verify both fit their text frames without overflow.

**Confidence:** HIGH -- verified from code comparison between converters.py:424-426 and i18n.py:36-48.

---

## Moderate Pitfalls

### Pitfall 8: Filter Chain Ambiguity -- Shadow vs Glow with Same Primitives

**What goes wrong:** An SVG filter can contain `feGaussianBlur + feFlood + feOffset + feComposite`. The existing code (filter_effects.py:70-76) detects "blur + offset = shadow". But the same primitives with a `feComposite operator="in"` before the offset could be a glow with an offset, not a shadow.

**Prevention:** Implement explicit chain-type detection. Check for `feComposite` BEFORE checking for `feOffset`. Priority: if composite with `operator="in"` is present, classify as glow regardless of offset. If no composite, classify as shadow (existing behavior).

**Confidence:** HIGH -- derived from filter_effects.py code analysis.

---

### Pitfall 9: Glow Effect on Text Shapes May Be Ignored by PowerPoint

**What goes wrong:** DrawingML `<a:glow>` applies to shape geometry. When applied to a text box (p:sp with txBody), PowerPoint may only glow the text box outline, not the text glyphs themselves. This differs from SVG where the glow is applied to the rendered text appearance.

**Prevention:** Test glow on both geometric shapes (rect, path) and text boxes. Document any behavioral difference. Consider emitting a QA warning when glow is applied to text elements.

**Confidence:** MEDIUM -- based on DrawingML schema understanding; requires empirical testing.

---

### Pitfall 10: PDF Handout Requires Slide Rendering -- No Pure-Python Solution

**What goes wrong:** The existing `pdf_export.py` has two backends: `soffice` (LibreOffice headless) and `cairo` (cairosvg on SVG files). Neither produces a handout layout with multiple slides per page plus speaker notes. The `cairo` backend just concatenates SVG pages into a PDF. The `soffice` backend converts PPTX to single-slide-per-page PDF.

**Why it happens:** Handout layout (N slides per page with notes) requires compositing slide images + text on a custom page grid. This is a layout operation, not a format conversion.

**Consequences:** A new rendering pipeline is needed: render each slide to an image (via cairosvg or soffice), then compose into a handout grid using a PDF library (reportlab, pypdf, or Pillow).

**Prevention:**
1. Use cairosvg to render each SVG slide to a PNG/PDF image (existing `export_pdf_cairo` already does per-page PDF generation).
2. Use reportlab or pypdf to compose a handout layout: grid of slide thumbnails + speaker notes text alongside.
3. Extract notes from the project's `notes/` directory (existing `_read_project_notes` in exporter.py:318-332).
4. Avoid introducing heavy new dependencies -- reportlab or pypdf are already lightweight.

**Detection:** Unit test verifying handout PDF contains correct number of pages with both slide images and note text.

**Confidence:** HIGH -- verified from existing pdf_export.py code and known Python PDF library capabilities.

---

### Pitfall 11: PDF Handout Note Text May Exceed Available Space

**What goes wrong:** Speaker notes can be arbitrarily long. In a 2-per-page or 3-per-page handout layout, the space allocated for notes beside each slide thumbnail is fixed. Long notes overflow the layout or get truncated.

**Prevention:**
1. Implement text measurement (reportlab's `stringWidth` or a simple heuristic) to estimate note height.
2. If notes exceed available space, either: (a) truncate with ellipsis, (b) reduce font size, or (c) add an overflow page.
3. Make the layout strategy configurable: 1-per-page (full notes), 2-per-page (truncated notes), 3-per-page (slide titles only).

**Confidence:** HIGH -- standard PDF layout challenge.

---

### Pitfall 12: LibreOffice Rendering Fidelity Differs from PowerPoint

**What goes wrong:** The soffice backend renders PPTX via LibreOffice, which does not perfectly replicate PowerPoint's rendering of DrawingML effects. Glow and softEdge effects may look different (wrong radius, wrong color, missing entirely) when rendered by LibreOffice for PDF output.

**Why it happens:** LibreOffice implements a subset of OOXML effects. Its glow/softEdge rendering uses a different engine than PowerPoint.

**Consequences:** The PDF handout shows effects that look different from the PPTX opened in PowerPoint. Users perceive this as a bug in the export pipeline.

**Prevention:**
1. For handout PDFs, consider rendering slides from the SVG source (cairosvg) rather than from the PPTX (soffice). SVG glow/soft-edge uses standard Gaussian blur that cairosvg renders correctly.
2. Document that soffice-rendered PDFs may have slight effect fidelity differences.
3. Offer the cairo backend as the default for handout export (it renders from SVG, which is the source of truth for effects).

**Confidence:** MEDIUM -- based on known LibreOffice OOXML compatibility limitations; requires testing with actual glow/softEdge effects.

---

### Pitfall 13: Bilingual Export Font Availability Across Platforms

**What goes wrong:** The `i18n.py` language profiles specify font families like "Noto Sans SC", "PingFang SC", "Microsoft YaHei". These fonts must be installed on the system where the PPTX is opened. On Windows, "Microsoft YaHei" is available but "PingFang SC" is macOS-only. On Linux, most CJK fonts are missing by default.

**Why it happens:** The existing `font_preflight()` (i18n.py:167-216) only does heuristic checks (does the theme font stack contain CJK keywords?) -- it does not check whether fonts are actually installed on the current system.

**Consequences:** PPTX opens with fallback fonts on systems missing the specified CJK fonts, producing broken bilingual layout.

**Prevention:**
1. During bilingual export, check if specified CJK fonts are available (use `fontTools` or system font enumeration).
2. If missing, substitute with a platform-appropriate fallback (YaHei on Windows, PingFang on macOS, Noto Sans CJK on Linux).
3. The existing `font_preflight()` already flags CJK coverage issues -- extend it to also check system font availability.

**Confidence:** HIGH -- verified from i18n.py code and cross-platform font availability knowledge.

---

## Minor Pitfalls

### Pitfall 14: SVG filter `result` Attribute Chaining

**What goes wrong:** SVG filter primitives use `result` and `in`/`in2` attributes to chain operations. The current parser (filter_effects.py:27-78) ignores these attributes, assuming a flat sequential chain. Complex glow filters may use named results (e.g., `result="blur"`, `in="blur"`) that create non-linear chains.

**Prevention:** Parse `result`, `in`, and `in2` attributes to build a dependency graph of filter primitives. Process in topological order.

**Confidence:** MEDIUM -- complex filters are rare but possible in AI-generated SVG.

---

### Pitfall 15: Negative or Zero stdDeviation Values

**What goes wrong:** AI-generated SVG may produce `stdDeviation="0"` or negative values. The existing blur conversion (filter_effects.py:125) uses `max(rad, 1)` to avoid zero-radius blur, but the new glow/softEdge paths must also clamp.

**Prevention:** Apply `max(stdDeviation, 0.1)` or skip the effect entirely when stdDeviation is zero or negative.

**Confidence:** HIGH -- the existing hardening pattern (v2.2 commit f77ae2d) already handles this for blur/shadow.

---

### Pitfall 16: Multiple Effects on One Shape

**What goes wrong:** A shape may have both glow and shadow in SVG (via separate filters or combined filter chains). The current `apply_filter_to_shape()` replaces the entire `effectLst` each time it is called (filter_effects.py:118-120). If called twice for the same shape (once for shadow, once for glow), the second call destroys the first effect.

**Why it happens:** The exporter.py loop (line 130-152) calls `apply_filter_to_shape()` once per shape. But if the SVG filter contains both shadow AND glow primitives, the current parser returns a single dict that only represents one effect.

**Prevention:** Allow the parsed filter dict to contain both `"shadow"` and `"glow"` keys. In `apply_filter_to_shape()`, build all effect children before inserting the `effectLst`. Do NOT remove and recreate `effectLst` for each effect type.

**Confidence:** HIGH -- verified from filter_effects.py:118-120 (removes existing effectLst unconditionally).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Outer glow detection | Pitfall 1: Glow misidentified as shadow or blur | Implement feComposite/feMerge parsing with chain pattern matching |
| Glow XML generation | Pitfall 2: effectLst child ordering violation | Implement `_reorder_effect_lst()` matching XSD sequence |
| Glow radius conversion | Pitfall 3: stdDeviation != DrawingML rad | Apply 2x correction factor, validate with visual QA |
| Glow color extraction | Pitfall 4: Using shape fill instead of feFlood color | Extract from feFlood explicitly in glow chain |
| Soft edge conversion | Pitfall 5: Algorithm mismatch with SVG | Accept tolerance gap, use same EMU conversion as blur |
| Soft edge on complex shapes | Pitfall 14: result/in chaining ignored | Parse dependency graph for non-linear chains |
| Bilingual text layout | Pitfall 6: Single text frame for two languages | Use separate text frames per language block |
| Bilingual width estimation | Pitfall 7: Inconsistent measure_weight | Unify with i18n.py LanguageProfile.measure_weight |
| Bilingual font fallback | Pitfall 13: Missing CJK fonts on target system | Extend font_preflight with system font checks |
| PDF handout rendering | Pitfall 10: No existing multi-slide layout | Build new composition pipeline (cairosvg + reportlab) |
| PDF handout notes | Pitfall 11: Note text overflow | Implement text measurement and truncation |
| PDF rendering fidelity | Pitfall 12: LibreOffice effect differences | Default to cairo backend for handout export |
| Multiple effects | Pitfall 16: Second effect overwrites first | Build all effects before inserting effectLst |

## Research Flags for Phases

- **Outer glow phase:** Needs deeper research on AI-generated SVG glow patterns. Different AI tools may emit glow filters in different chain structures. Collect representative samples before finalizing detection logic.
- **Soft edge phase:** Standard implementation, low research risk. The main risk is visual tolerance, which needs empirical testing, not research.
- **Bilingual phase:** Moderate research needed on whether bilingual should be a new SVG layout mode or a post-export transformation. The current SVG pipeline may need a "bilingual template" that emits two text elements per content block.
- **PDF handout phase:** Low research risk. The rendering pipeline is well-understood (cairosvg + reportlab). The main decision is dependency justification (reportlab is the standard choice).

## Sources

- OOXML Schema CT_GlowEffect: https://schemas.liquid-technologies.com/OfficeOpenXML/2006/dml-shapeEffects_xsd.html (HIGH confidence)
- OOXML Glow Element Reference: https://c-rex.net/samples/ooxml/e1/Part4/OOXML_P4_DOCX_glow_topic_ID0EJKXMB.html (HIGH confidence)
- SVG Filter Effects (W3C): https://www.w3.org/TR/SVG11/filters.html (HIGH confidence)
- SVG feComposite (MDN): https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/feComposite (HIGH confidence)
- SVG feGaussianBlur (MDN): https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/feGaussianBlur (HIGH confidence)
- CJK Typesetting Challenges: https://asianabsolute.co.uk/blog/cjk-typesetting-challenges-workflows-and-best-practices/ (MEDIUM confidence)
- W3C Japanese Layout Requirements: https://www.w3.org/2007/02/japanese-layout/docs/aligned/japanese-layout-requirements-en.html (HIGH confidence)
- Microsoft CJK/Latin Text Spacing: https://support.microsoft.com/en-us/infopath/adjust-text-spacing-and-line-breaks-in-form-templates-that-contain-both-east-asian-and-latin-text (HIGH confidence)
- CJK/Latin Visual Size Imbalance (Ghostty): https://github.com/ghostty-org/ghostty/discussions/7774 (MEDIUM confidence)
- Codebase analysis: filter_effects.py, converters.py, exporter.py, pdf_export.py, i18n.py (HIGH confidence)
