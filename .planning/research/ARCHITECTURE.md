# Architecture Patterns

**Domain:** slide-skill v2.3 -- outer glow, soft edge, bilingual export, PDF handout
**Researched:** 2026-05-10
**Confidence:** HIGH

## Recommended Architecture

### Integration Overview

All four v2.3 features plug into the existing SVG-first pipeline at well-defined seams. Two are filter-effects extensions (same seam as v2.2 blur/shadow), one is a new export layout mode, and one is a new output format.

```
                         EXISTING                           NEW
                    ┌──────────────┐
Source ──► Intake ──► Markdown     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ SVG Pipeline │
                    │  (generate)  │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │   SVG Finalize          │
              │  + filter <defs>        │  ◄── outer glow SVG filter pattern
              │  + bilingual layout     │  ◄── NEW: bilingual SVG group layout
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   Export Layer          │
              │                         │
              │  filter_effects.py      │  ◄── MODIFIED: add glow + softEdge
              │  converters.py          │
              │  exporter.py            │  ◄── MODIFIED: bilingual layout dispatch
              │  pdf_export.py          │  ◄── EXTENDED: handout mode
              └──────┬──────────────────┘
                     │
              ┌──────▼──────┐
              │   QA Layer  │
              └─────────────┘
```

## Component Boundaries

### 1. Outer Glow -- Extend filter_effects.py (MODIFY)

| Component | Change Type | Responsibility | Communicates With |
|-----------|-------------|----------------|-------------------|
| `_parse_filter()` | MODIFY | Parse `feGaussianBlur` + `feFlood` + `feComposite` pipeline as "glow" | Called by `collect_filters()` |
| `apply_filter_to_shape()` | MODIFY | Emit `<a:glow>` into effectLst | Called by `exporter.py` export loop |
| `_reorder_sppr()` | NO CHANGE | Already handles effectLst insertion position | Internal |

**SVG glow filter pattern to recognize:**

```xml
<filter id="glow1">
  <feGaussianBlur in="SourceAlpha" stdDeviation="4" result="blur"/>
  <feFlood flood-color="#00ffcc" flood-opacity="0.8" result="color"/>
  <feComposite in="color" in2="blur" operator="in" result="glow"/>
  <feMerge>
    <feMergeNode in="glow"/>
    <feMergeNode in="SourceGraphic"/>
  </feMerge>
</filter>
```

**DrawingML target XML:**

```xml
<a:effectLst>
  <a:glow rad="101600">
    <a:srgbClr val="00FFCC">
      <a:alpha val="80000"/>
    </a:srgbClr>
  </a:glow>
</a:effectLst>
```

**Mapping logic:**
- `stdDeviation` * 25400 = `rad` (EMU) -- same scale as blur
- `flood-color` -> `srgbClr val` -- reuse `_normalize_color()`
- `flood-opacity` * 100000 = `alpha val` -- same scale as shadow alpha
- The `feGaussianBlur + feFlood + feComposite (operator="in")` triple is the canonical SVG glow pattern. When `_parse_filter` detects this combination (blur present + flood present, and the filter has a composite with `operator="in"`), it synthesizes a "glow" dict rather than a "shadow" dict.

**Data flow change in `_parse_filter()`:**

Current return structure: `{"blur": {...}, "shadow": {...}}`
New return structure: `{"blur": {...}, "shadow": {...}, "glow": {...}}`

The glow detection heuristic:
1. Scan children of `<filter>` for `feGaussianBlur`, `feFlood`, `feComposite`
2. If composite has `operator="in"` AND flood_color != black OR there is no `feOffset` -- this is a glow, not a shadow
3. Alternatively: if there is no `feOffset` element but there is a `feFlood` and `feGaussianBlur` with `in="SourceAlpha"`, treat as glow
4. If `feDropShadow` exists -- that is shadow (existing behavior, unchanged)

**Integration point in `apply_filter_to_shape()`:**

Add a glow branch alongside existing blur and shadow branches:

```python
glow = filter_info.get("glow")
if glow:
    rad = int(glow["stdDeviation"] * 25400)
    glow_elem = etree.SubElement(effectLst, qn("a:glow"))
    glow_elem.set("rad", str(max(rad, 1)))
    srgb = etree.SubElement(glow_elem, qn("a:srgbClr"))
    srgb.set("val", glow.get("flood_color", "000000"))
    alpha = etree.SubElement(srgb, qn("a:alpha"))
    alpha.set("val", str(int(glow.get("flood_opacity", 1.0) * 100000)))
```

### 2. Soft Edge -- Extend filter_effects.py (MODIFY)

| Component | Change Type | Responsibility | Communicates With |
|-----------|-------------|----------------|-------------------|
| `_parse_filter()` | MODIFY | Parse `feGaussianBlur` with `in="SourceAlpha"` and no offset/flood as "soft_edge" | Called by `collect_filters()` |
| `apply_filter_to_shape()` | MODIFY | Emit `<a:softEdge>` into effectLst | Called by `exporter.py` export loop |

**SVG soft edge pattern:**

```xml
<filter id="soft1">
  <feGaussianBlur in="SourceAlpha" stdDeviation="3"/>
</filter>
```

Key distinction from existing blur: a standalone `feGaussianBlur` with `in="SourceAlpha"` (not `SourceGraphic`) is a soft-edge alpha feathering. The existing code treats any `feGaussianBlur` as a blur effect. The differentiation:

- **Blur** (existing): `feGaussianBlur` with `in="SourceGraphic"` or no `in` attribute -- visual blur of the entire shape
- **Soft Edge** (new): `feGaussianBlur` with `in="SourceAlpha"` and no companion `feOffset` or `feFlood` -- alpha feathering at edges only

**DrawingML target XML:**

```xml
<a:effectLst>
  <a:softEdge rad="76200"/>
</a:effectLst>
```

**Mapping logic:**
- `stdDeviation` * 25400 = `rad` (EMU)
- No color or opacity -- softEdge is purely a radius

**Return structure extension:**

New field: `{"blur": {...}, "shadow": {...}, "glow": {...}, "soft_edge": {...}}`

Where `soft_edge` is `{"stdDeviation": float}` or `None`.

**Distinguishing soft_edge from blur in `_parse_filter()`:**

When the filter contains ONLY a single `feGaussianBlur`:
- If `in` attribute is `"SourceAlpha"` -- soft_edge
- If `in` attribute is `"SourceGraphic"` or absent -- blur (existing behavior)
- If there is also a `feOffset` + `feFlood` -- shadow (existing behavior)

### 3. Bilingual Export -- New Layout Mode (MODIFY exporters + svg_pipeline)

| Component | Change Type | Responsibility | Communicates With |
|-----------|-------------|----------------|-------------------|
| `exporter.py` | MODIFY | Accept `--bilingual` flag, emit parallel text boxes | CLI via args |
| `converters.py` `convert_text()` | MODIFY | Detect bilingual data attributes, emit dual text frames | Called by registry dispatch |
| `svg_pipeline.py` | MODIFY (optional) | Generate bilingual SVG layout groups with data attributes | SVG generation |

**Architecture approach:**

Bilingual export does NOT require a fundamentally new pipeline. It is a layout transformation applied at the SVG generation or PPTX export stage. Two viable approaches:

**Approach A: SVG-stage bilingual layout (recommended)**
- In `svg_pipeline.py`, add a `_render_bilingual_*` family of layout functions
- Each produces SVG with paired `<text>` elements: one with `xml:lang="zh"` and one with `xml:lang="en"`
- The `convert_text()` function in `converters.py` detects `xml:lang` attributes and emits parallel PPTX text frames (Chinese above, English below, or side by side)
- Requires: new data attribute convention (`data-lang-zh`, `data-lang-en`) on SVG text elements

**Approach B: Export-stage bilingual injection**
- `exporter.py` receives a `--bilingual` flag and a second Markdown source
- During export, for each slide, it extracts the English text and adds a second text frame below or beside the Chinese one
- Less invasive to SVG pipeline, but requires coordinating two content sources

**Recommendation: Approach A (SVG-stage)** because:
1. SVG is the authoring layer -- bilingual pairing should be expressed in SVG
2. The AI executor can author bilingual SVG directly
3. QA can validate bilingual SVG structure before export
4. Consistent with the "SVG-first" design philosophy

**SVG element convention for bilingual text:**

```xml
<g id="content-body-01" data-bilingual="true">
  <text x="96" y="200" font-size="22" fill="#E0E0E0" xml:lang="zh"
        data-lang="zh">Chinese content here</text>
  <text x="96" y="260" font-size="16" fill="#999999" xml:lang="en"
        data-lang="en">English content here</text>
</g>
```

**converter modification for bilingual detection:**

In `convert_text()`, after creating the textbox, check if the element has `data-lang`. If so, also check siblings for the paired language. Emit a second textbox for the paired language, positioned relative to the first. The font sizing for the secondary language should be smaller (e.g., 70% of primary).

**spec_lock.json extension:**

```json
{
  "lang": "zh",
  "bilingual": true,
  "bilingual_layout": "stacked",
  "secondary_lang": "en"
}
```

### 4. PDF Handout -- New Output Format (EXTEND pdf_export.py)

| Component | Change Type | Responsibility | Communicates With |
|-----------|-------------|----------------|-------------------|
| `pdf_export.py` | EXTEND | New `export_handout_pdf()` function | CLI via `slide pdf-handout` |
| `cli.py` | MODIFY | Add `pdf-handout` subcommand | User |
| `pdf_export.py` | EXTEND | Render slide thumbnails + speaker notes per page | `render.py` for image extraction |

**Architecture approach:**

The handout PDF is a multi-page document where each page contains:
1. A scaled-down slide image (rendered from SVG or PPTX)
2. The speaker notes text below or beside it
3. Optional: slide number, title header

**Two rendering paths for slide images:**

Path 1 (cairo): Use existing `cairosvg.svg2png()` to rasterize each SVG from `svg_final/`, then embed into PDF. No LibreOffice dependency.

Path 2 (soffice): Use existing render pipeline to get PNG images from PPTX.

**Implementation strategy:**

Create `export_handout_pdf()` in `pdf_export.py`. Use `fpdf2` (lightweight pure-Python PDF library) for PDF composition. The function:

```python
def export_handout_pdf(
    project: Path,
    output: Path,
    *,
    layout: str = "notes-right",  # "notes-right" | "notes-below" | "notes-left"
    slides_per_page: int = 1,
    backend: str = "cairo",
) -> Path:
```

**Why fpdf2 over reportlab:**
- fpdf2 is pure Python, no C extensions, simpler to install on Windows
- ReportLab's PythonPoint is presentation-focused but adds a heavy dependency
- fpdf2 handles image embedding and text wrapping natively
- The existing `cairosvg` dependency already handles SVG-to-image conversion

**Dependency decision:**

Add `fpdf2` as an optional dependency:

```toml
[project.optional-dependencies]
handout = ["fpdf2>=2.8.0"]
```

The function falls back gracefully if fpdf2 is not installed.

**Data flow:**

```
svg_final/*.svg  ──► cairosvg.svg2png() ──► PNG images per slide
                                                    │
notes/*.md or PPTX notes ──► text extraction ──────┤
                                                    │
                                           fpdf2 PDF composition
                                                    │
                                              handout.pdf
```

**Notes extraction:**

Speaker notes already exist in two forms:
1. `project/notes/slide_N.md` files -- per-slide Markdown notes
2. Embedded in PPTX via `_embed_slide_notes()` -- extractable via `pptx_notes()`

The handout exporter reads both sources, preferring the Markdown files (more complete) with PPTX notes as fallback.

## Patterns to Follow

### Pattern 1: Filter Dict Extension

**What:** Extend the internal filter representation dict with new keys ("glow", "soft_edge") rather than creating new data structures.
**When:** Any new SVG filter effect type.
**Why:** `apply_filter_to_shape()` already operates on a dict with `blur` and `shadow` keys. Adding `glow` and `soft_edge` keys keeps the dispatch logic centralized.

```python
# _parse_filter return structure (v2.3)
{
    "blur": {"stdDeviation": float} | None,
    "shadow": {"dx": ..., "dy": ..., ...} | None,
    "glow": {"stdDeviation": float, "flood_color": str, "flood_opacity": float} | None,
    "soft_edge": {"stdDeviation": float} | None,
}
```

### Pattern 2: SVG Data Attribute Convention

**What:** Use `data-*` attributes on SVG elements to pass metadata to the export layer.
**When:** Features that need information not expressible in pure SVG attributes.
**Example:** `data-bilingual="true"`, `data-lang="zh"`, `data-lang="en"` on `<text>` elements.

```xml
<text x="96" y="200" data-lang="zh" xml:lang="zh">Content</text>
```

### Pattern 3: Graceful Dependency Degradation

**What:** New dependencies (fpdf2, cairosvg) are optional. Functions fail with clear error messages if missing.
**When:** Any feature that adds a new runtime dependency.
**Example:** Already used for cairosvg in `pdf_export.py`.

```python
try:
    import fpdf2
except ImportError as exc:
    raise RuntimeError(
        "PDF handout requires fpdf2. Install with: pip install slide-skill[handout]"
    ) from exc
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Glow/Shadow Ambiguity

**What:** The SVG glow pipeline (`feGaussianBlur` + `feFlood` + `feComposite`) looks very similar to the shadow pipeline (`feGaussianBlur` + `feOffset` + `feFlood` + `feComposite`).
**Why bad:** If the discriminator logic is wrong, a glow gets exported as a shadow (with wrong direction/dist) or vice versa.
**Instead:** Use the presence of `feOffset` as the discriminator. Glow has no `feOffset`; shadow does. Additionally, glow composite has `in="color" in2="blur"` while shadow composite has `in="shadowColor" in2="offsetBlur"`.

### Anti-Pattern 2: Bilingual at Export Time Only

**What:** Deferring bilingual layout to the PPTX export stage.
**Why bad:** Breaks the SVG-first philosophy. QA cannot validate bilingual layout visually in SVG. The AI executor loses control over bilingual positioning.
**Instead:** Express bilingual pairs in SVG with data attributes. Convert both text elements to native PPTX text frames during export.

### Anti-Pattern 3: Hardcoding PDF Layout Dimensions

**What:** Hardcoding pixel positions for slide thumbnails and notes text in the handout PDF.
**Why bad:** Different canvas formats (ppt169, xhs, wechat, story) have different aspect ratios. A hardcoded 960x540 thumbnail slot will distort or clip non-16:9 canvases.
**Instead:** Read canvas dimensions from `spec_lock.json` and compute thumbnail placement dynamically. Use aspect-ratio-preserving scaling.

## Suggested Build Order

The features have a natural dependency ordering based on codebase coupling and risk:

```
Phase 1: Soft Edge (lowest risk, simplest change)
    │   - Only modifies _parse_filter() discriminator
    │   - Adds soft_edge key to filter dict
    │   - Adds <a:softEdge> emission in apply_filter_to_shape()
    │   - Tests: 5-6 new unit tests following existing pattern
    │
Phase 2: Outer Glow (medium risk, pattern recognition)
    │   - Extends _parse_filter() to recognize glow pipeline
    │   - Adds glow key to filter dict
    │   - Adds <a:glow> emission in apply_filter_to_shape()
    │   - Risk: glow/shadow ambiguity -- needs careful discriminator
    │   - Tests: 8-10 new unit tests (various SVG glow patterns)
    │
Phase 3: Bilingual Export (medium risk, new data flow)
    │   - Adds data-lang convention to SVG
    │   - Modifies convert_text() to detect bilingual pairs
    │   - Adds --bilingual CLI flag
    │   - Optional: adds bilingual SVG renderers to svg_pipeline.py
    │   - Tests: converter tests + integration test with bilingual SVG
    │
Phase 4: PDF Handout (independent, new dependency)
        - Extends pdf_export.py with export_handout_pdf()
        - Adds fpdf2 optional dependency
        - Adds pdf-handout CLI subcommand
        - Reads notes from project + renders SVGs to images
        - Tests: unit tests for layout calculation + integration test
```

**Ordering rationale:**
1. Soft Edge first because it is the simplest -- just a new discriminator for `feGaussianBlur in="SourceAlpha"`. Zero risk of breaking existing blur/shadow.
2. Outer Glow second because it builds on the same `_parse_filter()` changes from Phase 1 and reuses the glow/shadow discriminator logic. The ambiguity risk is contained.
3. Bilingual Export third because it touches a different subsystem (converters, SVG pipeline) and can be developed independently after filters are stable.
4. PDF Handout last because it is completely independent -- new file, new dependency, new CLI command. Can be parallelized with Phase 3 if needed.

## Scalability Considerations

| Concern | At 10 slides | At 50 slides | At 200 slides |
|---------|-------------|--------------|---------------|
| Glow/soft_edge parsing | Negligible | Negligible | Negligible (filter parsing is O(n) where n = defs elements, not slide count) |
| Bilingual text conversion | Negligible | Negligible | Negligible (per-shape operation) |
| PDF handout rendering | ~2s (cairosvg) | ~8s | ~30s (I/O bound: SVG-to-PNG rasterization) |

The PDF handout is the only feature with scalability concerns. At 200+ slides, the cairosvg rasterization will be the bottleneck. Mitigation: parallel rendering of SVG pages (multiprocessing), or switching to the soffice path for bulk conversion.

## Integration Point Summary

| Feature | Files Modified | New Files | New Dependencies |
|---------|---------------|-----------|------------------|
| Outer Glow | `filter_effects.py`, `converters.py` (noop list) | None | None |
| Soft Edge | `filter_effects.py`, `converters.py` (noop list) | None | None |
| Bilingual | `converters.py`, `exporter.py`, `svg_pipeline.py`, `cli.py` | None | None |
| PDF Handout | `pdf_export.py`, `cli.py` | None | `fpdf2>=2.8.0` (optional) |

## Sources

- DrawingML `a:glow` and `a:softEdge` XML structure: ECMA-376 Part 1, Section 20.1.8 (confirmed via [python-pptx shadow analysis](https://python-pptx.readthedocs.io/en/latest/dev/analysis/shp-shadow.html))
- SVG glow filter pipeline: [W3C SVG 1.1 Filter Effects](https://www.w3.org/TR/SVG11/filters.html)
- python-pptx EffectFormat API: [python-pptx effect module](https://python-pptx.readthedocs.io/en/latest/_modules/pptx/dml/effect.html)
- fpdf2 documentation: [fpdf2 GitHub](https://github.com/PyFPDF/fpdf2)
- Existing codebase: all files under `tools/slide/src/slide_skill/` (read directly, HIGH confidence)

---
*Architecture research for: v2.3 outer glow, soft edge, bilingual export, PDF handout*
*Researched: 2026-05-10*
