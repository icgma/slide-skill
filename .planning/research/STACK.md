# Stack Research: Slide Skill v2.3

**Domain:** Outer glow, soft edge, bilingual export, PDF handout
**Researched:** 2026-05-10
**Confidence:** HIGH (glow/softEdge: DrawingML XML verified via ECMA-376 spec), MEDIUM (PDF handout: approach verified, library versions current)

## Executive Summary

Four features require stack decisions. Two (outer glow, soft edge) need **zero new dependencies** -- they are pure lxml DrawingML XML construction, extending the existing `filter_effects.py` pattern. One (bilingual export) needs **zero new dependencies** -- it extends the existing `i18n.py` + `converters.py` text layout logic. Only PDF handout export requires a **new runtime dependency**: `fpdf2` for multi-page PDF generation with CJK font support.

The key insight: slide-skill already has CairoSVG and Pillow in its environment (via transitive deps). But CairoSVG is *not* the right choice for the PDF handout because the handout is a structured document (slide thumbnail + speaker notes per page), not a simple SVG-to-PDF conversion. fpdf2 gives explicit page layout control with CJK TTF font embedding.

## Recommended Stack

### Feature 1 & 2: Outer Glow + Soft Edge (no new deps)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| lxml | 6.1+ (existing) | Construct `<a:glow>` and `<a:softEdge>` elements in `effectLst` | Already used in `filter_effects.py` for `<a:blur>` and `<a:outerShdw>` |
| python-pptx | 1.0.2+ (existing) | Access `shape._element.spPr` for OOXML manipulation | Already the core PPTX builder |

**DrawingML XML structure verified from ECMA-376 spec:**

`<a:glow>` element:
- Parent: `<a:effectLst>` (same as blur/shadow)
- Attributes: `rad` (radius in EMU, ST_PositiveCoordinate)
- Children: color choice group (`<a:srgbClr>`, `<a:schemeClr>`, etc.) with optional alpha transforms
- Example: `<a:glow rad="254000"><a:srgbClr val="FF6600"><a:alpha val="40000"/></a:srgbClr></a:glow>`

`<a:softEdge>` element:
- Parent: `<a:effectLst>`
- Attributes: `rad` (radius in EMU)
- No children (no color -- uses the object's own fill color)
- Example: `<a:softEdge rad="50800"/>`

**SVG input mapping:**

Outer glow in SVG uses `feGaussianBlur` + `feFlood` + `feComposite` (composite="in" on SourceAlpha) -- the existing `_parse_filter()` already captures `stdDeviation`, `flood_color`, and `flood_opacity`. The mapping is direct: stdDeviation -> `rad`, flood_color -> `srgbClr val`, flood_opacity -> `a:alpha val`.

Soft edge in SVG uses `feGaussianBlur` on a mask/alpha channel. The SVG representation is less standardized; the most common pattern is a `<filter>` containing only `feGaussianBlur` with `in="SourceAlpha"`. We detect this by: blur present, no shadow offset, no flood color -- the same signal the current code already has.

**Integration point:** Extend `filter_effects.py`:
- `_parse_filter()`: add glow detection (blur + flood + no offset -> glow dict)
- `apply_filter_to_shape()`: add `a:glow` and `a:softEdge` element construction alongside existing `a:blur` / `a:outerShdw`

### Feature 3: Bilingual Export (no new deps)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| python-pptx | 1.0.2+ (existing) | Create dual text frames with CJK font fallback | Already handles `<a:ea>` (East Asian) font spec in `convert_text()` |
| i18n.py | existing | Detect language, provide CJK font families | Already has `detect_language()`, `LANGUAGE_PROFILES["zh"]` with Noto Sans SC, PingFang SC, etc. |

**Approach:** Bilingual export creates two text frames per content area -- one for Chinese, one for English. The existing `convert_text()` in `converters.py` already sets `<a:ea>` for CJK fonts and handles `text-anchor`. The bilingual layout simply calls `convert_text` twice with different vertical offsets and font sizes (Chinese typically 80-90% the point size of English for visual balance).

This is a **layout concern**, not a library concern. The SVG generation prompt and/or the export pipeline arrange two text blocks. No new deps.

### Feature 4: PDF Handout Export (one new dep)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| fpdf2 | 2.8.7 (latest) | Multi-page PDF generation with CJK TTF embedding | Pure Python, no C extensions; explicit page layout control; Unicode TTF support for Chinese characters |
| CairoSVG | 2.8.2 (existing) | Render SVG slides to PNG images for PDF embedding | Already in environment; handles SVG-to-raster for slide thumbnails |
| Pillow | 10.4+ (existing) | Image processing intermediary | CairoSVG output -> Pillow Image -> fpdf2 image embedding |

### Why fpdf2 over alternatives

| Criterion | fpdf2 | reportlab | comtypes (PowerPoint COM) |
|-----------|-------|-----------|--------------------------|
| Cross-platform | Yes (pure Python) | Partial (C extensions) | No (Windows + PowerPoint only) |
| CJK support | TTF embedding | Built-in CID fonts + TTF | N/A (delegates to PowerPoint) |
| New dependency size | Lightweight (no C deps) | Heavy (C extensions, already installed) | None (uses installed app) |
| Layout control | Explicit x/y positioning | Canvas + Platypus | PowerPoint handles layout |
| License | LGPL | BSD | N/A |
| Already installed | No (needs install) | Yes (4.4.3 in env) | Yes (if PowerPoint present) |

**Decision: fpdf2** because:
1. The project constraint is "cross-platform components preferred, Windows support matters" -- comtypes is Windows-only.
2. fpdf2 is pure Python, adding zero binary complexity. reportlab's C extensions are already installed but add unnecessary weight for a simple multi-page PDF.
3. fpdf2's explicit `x, y` positioning model maps directly to the handout layout (slide thumbnail top half, notes bottom half).
4. CJK support via TTF embedding is straightforward -- load a .ttf file with `add_font()`.
5. The LGPL license is compatible with the project's clean-room scope.

**Why NOT reportlab** despite being already installed: reportlab is the heavier dependency and its Platypus layout engine adds conceptual complexity for what is essentially a fixed-layout two-zone page. For the handout use case (slide image on top, speaker notes text below, repeat per slide), fpdf2's simpler API is a better fit. That said, if fpdf2 proves insufficient, reportlab is a viable fallback since it is already in the environment.

## Installation

```bash
# New runtime dependency for PDF handout export
pip install fpdf2>=2.8.7

# No other new dependencies needed
# CairoSVG, Pillow, lxml, python-pptx already in environment
```

**pyproject.toml change:**

```toml
dependencies = [
    "edge-tts>=7.2.8",
    "fpdf2>=2.8.7",           # NEW: PDF handout export with CJK support
    "lxml>=6.1.0",
    "openai>=2.33.0",
    "python-pptx>=1.0.2",
    "svgpathtools>=1.7.2",
]
```

**Optional dependency for PDF:**

CairoSVG is needed for SVG->PNG rendering (slide thumbnails in PDF). It is *not* a direct dependency of slide-skill but exists in the environment. For users who want PDF handout export, they need CairoSVG installed. Consider adding to an optional dependency group:

```toml
[project.optional-dependencies]
pdf = [
    "cairosvg>=2.7.0",
    "Pillow>=10.0.0",
]
```

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| comtypes (PowerPoint COM) | Windows-only, requires PowerPoint installed, brittle COM interop | fpdf2 for cross-platform PDF generation |
| reportlab Platypus | Over-engineered for fixed two-zone page layout; the learning curve and complexity do not justify the benefit for a handout renderer | fpdf2 with explicit x/y positioning |
| WeasyPrint | Heavy dependency chain (cairocffi + cssselect2 + tinycss2 + pydyf + fonttools); designed for HTML-to-PDF, not structured document generation | fpdf2 for programmatic PDF construction |
| pdfkit / wkhtmltopdf | Requires wkhtmltopdf binary installed system-wide; HTML-centric approach adds unnecessary intermediate step | fpdf2 for direct PDF generation |
| aspose.slides | Commercial license required; overkill for PDF handout | fpdf2 + CairoSVG (both open source) |
| svglib for handout PDF | svglib converts SVG to reportlab Drawing objects, not to slide handouts with speaker notes; would still need reportlab for text layout | fpdf2 for the complete handout PDF |

## Stack Patterns by Variant

**If the user has PowerPoint installed on Windows:**
- PDF handout can optionally use comtypes for pixel-perfect handout export (PowerPoint's native handout layout)
- fpdf2 remains the default; comtypes can be a fallback/enhancement
- This does not change the dependency -- comtypes is stdlib on Windows

**If CJK fonts are not available on the system:**
- fpdf2 requires a .ttf file for CJK text rendering
- Bundle a Noto Sans SC Regular .ttf (Apache-2.0 license) or document the requirement
- The existing i18n.py `LANGUAGE_PROFILES["zh"]` already lists Noto Sans SC as primary

**If CairoSVG fails to render an SVG slide:**
- Fall back to embedding a placeholder rectangle with the slide number
- Log a warning; the PDF handout is best-effort for slide thumbnails
- The speaker notes text is always rendered (no dependency on CairoSVG)

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| fpdf2 | 2.8.7 | Python 3.11+ | Pure Python, no native extension issues |
| CairoSVG | 2.8.2 | Python 3.11+, requires cairocffi | System cairo library needed (GTK runtime on Windows) |
| Pillow | 10.4+ | Python 3.11+, fpdf2 | fpdf2 uses Pillow for image format support |
| lxml | 6.1+ | python-pptx 1.0.2 | Used for DrawingML element construction |
| python-pptx | 1.0.2 | lxml 5.x/6.x | Core PPTX library |

## Integration Points

| New Feature | Existing Module | Integration |
|-------------|----------------|-------------|
| Outer glow | `filter_effects.py` | Extend `_parse_filter()` to detect glow pattern; add `_apply_glow()` building `<a:glow>` XML |
| Soft edge | `filter_effects.py` | Add `_apply_soft_edge()` building `<a:softEdge>` XML; detect via blur-only-no-shadow pattern |
| Glow/softEdge | `svg_pipeline.py` | Add `feComposite` and `feMerge` to `SUPPORTED_DRAWABLE_TAGS` (already present) |
| Glow/softEdge | `converters.py` | Register structural noop for `feComposite`, `feMerge`, `feMergeNode` (already done) |
| Bilingual | `i18n.py` | Already has `detect_language()` and CJK font profiles |
| Bilingual | `converters.py` | Extend `convert_text()` or add `convert_bilingual_text()` for dual text frames |
| Bilingual | `exporter.py` | Add bilingual mode flag; emit two text boxes per content block |
| PDF handout | NEW: `pdf_handout.py` | New module: iterate slides, render SVG->PNG via CairoSVG, embed in fpdf2 pages with notes |
| PDF handout | `exporter.py` | Add `export_pdf_handout()` entry point alongside existing `export_project()` |
| PDF handout | `cli.py` | Add `pdf-handout` subcommand |

## Sources

- ECMA-376 Part 4 Section 20.1.8.32 (`<glow>` element) via [c-rex.net](https://c-rex.net/samples/ooxml/e1/Part4/OOXML_P4_DOCX_glow_topic_ID0EJKXMB.html) -- HIGH confidence
- ECMA-376 Part 3 Primer (Soft Edge Effects) via [c-rex.net](https://c-rex.net/samples/ooxml/e1/Part3/OOXML_P3_Primer_Soft_topic_ID0EABQO.html) -- HIGH confidence
- ECMA-376 Part 3 Primer (Glow Effects) via [c-rex.net](https://c-rex.net/samples/ooxml/e1/Part3/OOXML_P3_Primer_Glow_topic_ID0EBCQO.html) -- HIGH confidence
- Liquid Technologies OOXML Schema (`dml-shapeEffects.xsd`) via [schemas.liquid-technologies.com](https://schemas.liquid-technologies.com/officeopenxml/2006/dml-shapeeffects_xsd.html) -- HIGH confidence
- Microsoft Learn Glow class documentation via [learn.microsoft.com](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.drawing.glow) -- HIGH confidence
- fpdf2 PyPI page via [pypi.org/project/fpdf2](https://pypi.org/project/fpdf2/) -- version 2.8.7 confirmed -- HIGH confidence
- CairoSVG documentation via [cairosvg.org](https://cairosvg.org/documentation/) -- HIGH confidence
- Python PDF library comparison via [nutrient.io](https://www.nutrient.io/blog/top-10-ways-to-generate-pdfs-in-python/) -- MEDIUM confidence
- LibreOffice soft edge import/export commit (tdf#49247) via [cgit.freedesktop.org](https://cgit.freedesktop.org/libreoffice/core/commit/?id=5952331844450dad93e21d2e329d51841ae1700e) -- HIGH confidence (confirms softEdge OOXML interoperability)

---
*Stack research for: slide-skill v2.3 outer glow, soft edge, bilingual export, PDF handout*
*Researched: 2026-05-10*
