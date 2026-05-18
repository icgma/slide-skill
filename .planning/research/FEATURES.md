# Feature Research: Slide Skill v2.3

**Domain:** Outer glow, soft edge, bilingual export, PDF handout
**Researched:** 2026-05-10
**Confidence:** HIGH (DrawingML spec verified, SVG patterns well-understood from v2.2 codebase)

## Executive Summary

The four v2.3 features split into two pairs along architectural lines. Outer glow and soft edge extend the existing `filter_effects.py` module and `apply_filter_to_shape` pipeline -- they are incremental filter-effect additions that follow the exact same parse-collect-apply pattern established in v2.2 for blur and drop shadow. Bilingual export and PDF handout are new output modes that extend the exporter layer with no overlap with filter effects.

The filter effects are low-risk, high-confidence work. DrawingML `<a:glow>` and `<a:softEdge>` are leaf elements in `<a:effectLst>`, each with a single `rad` attribute and (for glow) a mandatory color child. The SVG input patterns are well-known multi-primitive filter chains. The codebase already handles filter parsing, collection, resolution, and spPr reordering -- glow and softEdge slot directly into `_parse_filter` and `apply_filter_to_shape`.

Bilingual export is the highest-complexity feature. It is not a filter effect; it is a layout transformation that must emit parallel text boxes (or dual-language paragraphs) in PPTX. The existing `convert_text` function in `converters.py` already handles CJK font detection and East-Asian typeface assignment via `a:ea` -- this is a strong foundation. The new work is the layout policy: how to position Chinese and English text relative to each other, how to size dual-language text boxes, and how the SVG layer signals bilingual intent.

PDF handout is a new renderer that reads the already-exported PPTX and emits a multi-page PDF with slides on top and speaker notes below. ReportLab is the right library for this -- it is cross-platform, pure-Python, and already used in the Python ecosystem for programmatic PDF generation. The existing project already depends on LibreOffice for render QA, but LibreOffice cannot export notes to PDF from the command line. ReportLab fills this gap.

## Table Stakes

Features users expect given the existing v2.2 capabilities. Missing = the toolkit feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Outer glow conversion to DrawingML | Glow is one of the three most common shape effects in PowerPoint (alongside shadow and reflection). v2.2 shipped shadow; glow is the natural next effect | LOW | Same pattern as drop shadow. SVG chain: feGaussianBlur(SourceAlpha) + feFlood(color) + feComposite(in) + feMerge. DrawingML: `<a:glow rad="N"><a:srgbClr val="RRGGBB"><a:alpha val="N"/></a:srgbClr></a:glow>` |
| Soft edge conversion to DrawingML | Soft edges are common on rounded shapes, photos, and cards in modern slide design. Completes the v2.2 filter effect set | LOW | Simplest DrawingML effect: `<a:softEdge rad="N"/>`. No color child. SVG: feGaussianBlur on SourceAlpha, applied as alpha mask. |
| Glow color and radius from SVG filter primitives | Users expect the glow to match their SVG design intent -- color, spread, opacity | LOW | Parse feFlood for flood-color/flood-opacity, feGaussianBlur for stdDeviation. Map to DrawingML rad (EMU) + srgbClr + alpha. |
| Glow + existing effects compose correctly | A shape may have both glow and drop shadow. Both must appear in the same `<a:effectLst>` | MEDIUM | The existing `_parse_filter` returns a dict with blur and shadow keys. Add glow and softEdge keys. `apply_filter_to_shape` must emit multiple children in one effectLst (already supported for blur+shadow). |
| Bilingual text visible in PPTX | Chinese + English parallel text is a core use case for academic and business presentations in China | MEDIUM | Two text boxes per content area (one per language) or a single text box with two paragraphs. Depends on layout policy. |
| PDF with slide images + speaker notes | Standard handout format: slide visual on top half, notes text on bottom half of each page | MEDIUM | ReportLab canvas: render slide image (from existing PNG snapshots) in top region, flow notes text in bottom region. |

## Differentiators

Features that set the toolkit apart. Not expected, but valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| SVG glow auto-detection from multi-primitive chains | AI authors SVG filters as feGaussianBlur+feFlood+feComposite chains, not as a single "glow" primitive. Auto-detecting this pattern and converting to DrawingML glow (rather than just blur) is the differentiator | MEDIUM | Pattern recognition in `_parse_filter`: when feGaussianBlur + feFlood + feComposite(operator="in") appear together WITHOUT feOffset, this is glow (not shadow). Shadow has an offset; glow does not. |
| SVG soft edge from feGaussianBlur on alpha | Soft edge in SVG is typically feGaussianBlur applied to SourceAlpha and composited back as a mask. Detecting this pattern and converting to `<a:softEdge>` is the differentiator | LOW | When a filter contains ONLY feGaussianBlur (no feFlood, no feOffset), and the result is composited with the original via feMerge, classify as soft edge candidate. |
| Bilingual layout via data attribute | Using `data-bilingual="zh,en"` on SVG groups to signal which text elements get duplicated into parallel language boxes. This keeps the SVG authoring model clean -- the AI writes one text per language and the exporter handles layout | MEDIUM | Requires extending SVG QA to accept data-bilingual, and extending exporters to emit dual text boxes. The existing `convert_text` already handles CJK font routing. |
| Handout PDF with configurable layout | Users can choose 1-up (one slide per page with notes), 2-up, or 3-up handout layouts. This matches PowerPoint's own handout printing options | MEDIUM | ReportLab PageTemplate with frames. 1-up = slide + notes stacked. 2-up/3-up = grid of slides with notes below each or at page bottom. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Full SVG filter chain interpreter | SVG has 20+ filter primitives (feTurbulence, feDisplacementMap, feConvolveMatrix, etc.). Implementing a general-purpose filter pipeline is massive scope with diminishing returns | Only support the filter patterns that map cleanly to DrawingML effects: blur, shadow, glow, soft edge. Reject unsupported primitives at SVG QA time. |
| Inner glow effect | DrawingML has no `<a:innerGlow>` element. PowerPoint does not support inner glow natively -- it renders as inner shadow with a glow-like appearance | If inner glow SVG is encountered, approximate with inner shadow (`<a:innerShdw>`) or skip with a QA warning. |
| Bilingual auto-translation | Translating between languages is an NLP/AI task, not a layout/export task. Mixing translation into the export pipeline violates separation of concerns | The bilingual feature handles layout only. Translation is the caller's responsibility (the AI agent or user provides both language versions). |
| Real-time PDF preview | Building a PDF viewer or live preview server is out of scope for a CLI toolkit | Write PDF to disk, let the caller open it. The existing `preview` command can be extended to open the PDF. |
| PDF export via LibreOffice macros | LibreOffice macro approach is fragile, platform-specific, and requires a running LibreOffice instance with macro configuration | Use ReportLab for pure-Python PDF generation. Cross-platform, no external process dependencies. |
| Reflection, 3D, bevel, extrusion effects | These DrawingML effects have no clean SVG filter mapping and would require significant reverse-engineering of rendering behavior | Defer indefinitely. The v2.3 scope is glow + soft edge only. |

## Feature Dependencies

```
[Outer Glow]
    requires --> [existing filter_effects.py collect/resolve/apply pipeline]
    requires --> [feGaussianBlur + feFlood + feComposite parsing in _parse_filter]
    modifies --> filter_effects.py: add glow key to filter dict, add glow XML emission
    modifies --> svg_pipeline.py: add feColorMatrix to SUPPORTED_DRAWABLE_TAGS if needed
    modifies --> converters.py: add any new SVG filter primitives to _noop_converter list

[Soft Edge]
    requires --> [existing filter_effects.py pipeline]
    requires --> [feGaussianBlur parsing (already exists)]
    modifies --> filter_effects.py: add soft_edge key to filter dict
    modifies --> filter_effects.py: apply_filter_to_shape emits <a:softEdge>

[Bilingual Export]
    requires --> [existing convert_text with CJK font detection]
    requires --> [new SVG data-bilingual attribute convention]
    modifies --> converters.py: detect bilingual groups, emit parallel text boxes
    modifies --> svg_pipeline.py: accept data-bilingual in SVG QA
    depends-on --> [existing _visual_wrap and CJK width estimation]

[PDF Handout]
    requires --> [new dependency: reportlab]
    requires --> [existing render.py PNG snapshots OR LibreOffice PDF export]
    modifies --> cli.py: add export-pdf-handout subcommand
    new-file --> handout.py: PDF generation module
    feeds-from --> [existing pptx_notes() function in exporter.py]
    feeds-from --> [existing render.py slide-to-PNG pipeline]
```

## MVP Recommendation

Prioritize in this order:

1. **Outer glow** -- Lowest risk, highest value. Follows the exact v2.2 shadow pattern. Extends `_parse_filter` to recognize feGaussianBlur+feFlood+feComposite glow chains and emits `<a:glow>`. One PR.

2. **Soft edge** -- Second lowest risk. Only marginally more complex than glow. Extends `_parse_filter` to classify blur-only filters as soft edge candidates and emits `<a:softEdge>`. One PR.

3. **PDF handout** -- New module, new dependency (reportlab), but well-bounded scope. Reads existing PPTX + notes, generates a multi-page PDF. Does not modify any existing modules except cli.py (new subcommand). Clean separation.

4. **Bilingual export** -- Highest complexity. Requires a new SVG authoring convention (data-bilingual), layout policy decisions, and modifications to the text converter. Defer to last because it touches the most sensitive code path (text layout) and has the most design decisions.

Defer:
- Multi-up handout layouts (2-up, 3-up): Start with 1-up only. Grid layouts add layout complexity without proportional value.
- Bilingual auto-detection (inferring which language a text is): Require explicit `data-bilingual` markup. Auto-detection via Unicode range is fragile and unnecessary when the AI can tag elements.

## Per-Feature Technical Notes

### Outer Glow

**SVG input pattern:**
```xml
<filter id="glow-1" x="-50%" y="-50%" width="200%" height="200%">
  <feGaussianBlur in="SourceAlpha" stdDeviation="4" result="blur"/>
  <feFlood flood-color="#00ffaa" flood-opacity="0.7" result="color"/>
  <feComposite in="color" in2="blur" operator="in" result="glow"/>
  <feMerge>
    <feMergeNode in="glow"/>
    <feMergeNode in="SourceGraphic"/>
  </feMerge>
</filter>
```

**DrawingML output:**
```xml
<a:effectLst>
  <a:glow rad="101600">
    <a:srgbClr val="00FFAA">
      <a:alpha val="70000"/>
    </a:srgbClr>
  </a:glow>
</a:effectLst>
```

**Key mapping:**
- `stdDeviation` (SVG px) x 25400 = `rad` (EMU). This matches the v2.2 blur/shadow conversion.
- `flood-color` hex = `a:srgbClr val`
- `flood-opacity` (0-1) x 100000 = `a:alpha val` (0-100000)
- Filter region expansion (x="-50%" etc.) is informational only; DrawingML glow auto-extends.

**Disambiguation from shadow:** Glow has NO feOffset. Shadow has feOffset (or feDropShadow with dx/dy). If a filter chain has feGaussianBlur + feFlood + feComposite but zero net offset, classify as glow.

### Soft Edge

**SVG input pattern:**
```xml
<filter id="soft-1">
  <feGaussianBlur in="SourceAlpha" stdDeviation="3" result="blur"/>
  <feComposite in="SourceGraphic" in2="blur" operator="in"/>
</filter>
```

**DrawingML output:**
```xml
<a:effectLst>
  <a:softEdge rad="76200"/>
</a:effectLst>
```

**Key mapping:**
- `stdDeviation` (SVG px) x 25400 = `rad` (EMU). Same conversion factor.
- No color child. `<a:softEdge>` is a leaf element with only the `rad` attribute.
- Per ECMA-376 Section 20.1.8.45 / ISO 29500-1: "The edges of the shape are blurred, while the fill is not affected."

### Bilingual Export

**SVG authoring convention (proposed):**
```xml
<g data-bilingual="true">
  <text x="100" y="200" lang="zh" font-family="Microsoft YaHei" font-size="28">
    中文标题
  </text>
  <text x="100" y="240" lang="en" font-family="Segoe UI" font-size="18">
    English Title
  </text>
</g>
```

**Layout policies (recommend stacked):**
- **Stacked** (recommended): Chinese on top, English below, within the same content region. Simpler to implement, handles variable text lengths better.
- **Side-by-side**: Two columns. Higher layout complexity, risk of overflow on both sides.
- **Single text box, two paragraphs**: Both languages in one PPTX text frame. Simplest PPTX structure but loses independent font control per language.

**Recommended approach:** Stacked text boxes. Each `<text>` with a `lang` attribute inside a `data-bilingual` group gets its own PPTX text box. The exporter positions the English text box immediately below the Chinese text box, with a configurable gap. This preserves independent font sizing per language (Chinese typically needs larger point size for readability).

### PDF Handout

**Recommended architecture:**
```
handout.py
  - reads PPTX via python-pptx (slides + notes)
  - renders slides to PNG via existing render.py pipeline
  - generates PDF via reportlab with 1-up layout:
    +---------------------------+
    |    Slide image (top 60%)  |
    |                           |
    +---------------------------+
    | Speaker notes (bottom 40%)|
    |                           |
    +---------------------------+
```

**Dependency:** reportlab (pure-Python, cross-platform, no system deps).

**CJK font handling:** ReportLab requires explicit CJK font registration. Use ReportLab's built-in CID fonts (`STSong-Light` for Simplified Chinese) or register system fonts. The handout must render Chinese notes correctly.

**Integration point:** New `cli.py` subcommand `export-pdf-handout` that calls `handout.export_handout_pdf(project_path)`. Works on the already-exported PPTX -- no changes to the SVG pipeline or exporter.

## Sources

- ECMA-376 / ISO 29500-1: DrawingML `<a:glow>` (Section 20.1.8.35), `<a:softEdge>` (Section 20.1.8.45)
- [Microsoft Learn: SoftEdge Class](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.softedge?view=openxml-3.0.1) -- confirmed `rad` attribute is `ST_PositiveCoordinate` (EMU)
- [c-rex.net: softEdge specification](https://c-rex.net/samples/ooxml/e1/Part4/OOXML_P4_DOCX_softEdge_topic_ID0EZFANB.html) -- confirmed `CT_SoftEdgesEffect` schema: single `rad` attribute, no child elements
- [Liquid Technologies: softEdge schema](https://schemas.liquid-technologies.com/OfficeOpenXML/2006/softedge1.html) -- XSD confirmation
- SVG Filter specification: feGaussianBlur, feFlood, feComposite operator="in" for glow pattern
- ReportLab User Guide: PageTemplates, Frames, multi-page PDF layout
- Existing codebase: filter_effects.py (v2.2), converters.py, exporter.py, svg_pipeline.py

---
*Feature research for: v2.3 Advanced Filters, Bilingual & PDF Export*
*Researched: 2026-05-10*
