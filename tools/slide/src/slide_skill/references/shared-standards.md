# Shared SVG Technical Standards

> **Scope:** This document defines the complete technical rules for SVG files
> created by the slide-skill pipeline. All SVGs must comply with these standards
> to ensure correct rendering in browsers AND successful conversion to native
> editable PowerPoint (PPTX).

---

## 1. SVG Document Structure

### 1.1 Root Element

```xml
<svg width="1280" height="720" viewBox="0 0 1280 720"
     xmlns="http://www.w3.org/2000/svg">
```

**Required attributes:**
- `width` and `height` — always integers matching the canvas spec.
- `viewBox` — must be `"0 0 {width} {height}"` exactly.
- `xmlns` — always `"http://www.w3.org/2000/svg"`.

**Forbidden root attributes:**
- `xmlns:xlink` — not needed (use `href` instead of `xlink:href`)
- `xml:space` — not needed
- `version` — SVG2 does not require version

### 1.2 Document Order

Elements must appear in this order:
1. `<defs>` (optional — gradients, filters, clip-paths, patterns)
2. `<g id="background">` — full-canvas background
3. `<g id="chrome-stripe">` — accent stripe
4. Content groups (`<g id="content-...">`)
5. Decoration groups (`<g id="decoration-...">`)
6. `<g id="chrome-footer">` — footer bar (last visual layer)

**Why order matters:** The PPTX exporter processes groups in document order.
The footer must be last to appear on top of all content.

---

## 2. Tag Classification

### 2.1 Allowed Tags (Safe for SVG + PPTX)

These tags are fully supported in both SVG rendering and PPTX export:

| Tag | PPTX Conversion | Notes |
|-----|----------------|-------|
| `<rect>` | Native rectangle shape | `rx`/`ry` → corner radius |
| `<circle>` | Native ellipse (equal w/h) | |
| `<ellipse>` | Native ellipse | |
| `<line>` | Native connector/line | |
| `<text>` | Native text box | See §6 for text rules |
| `<tspan>` | Run within text box | |
| `<image>` | Embedded picture | Must use relative `href` |
| `<path>` | Native freeform shape | See §4 for path rules |
| `<polygon>` | Native freeform (closed) | |
| `<polyline>` | Native freeform (open) | |
| `<g>` | Shape group | Must have `id` at top level |
| `<defs>` | Definitions block | Not exported directly |
| `<linearGradient>` | Native gradient fill | Max 10 stops |
| `<radialGradient>` | Native gradient fill | Max 10 stops |
| `<stop>` | Gradient stop | |
| `<clipPath>` | Native clip region | See §5 |
| `<pattern>` | Pattern fill | Limited PPTX support |
| `<use>` | Clone reference | Local `#id` only |
| `<title>` | Alt-text / tooltip | |
| `<desc>` | Description metadata | |
| `<mask>` | Transparency mask | Limited PPTX support |

### 2.2 Banned Tags (Hard Error)

These tags will cause SVG QA to fail and must NEVER be used:

| Tag | Reason |
|-----|--------|
| `<script>` | Security: executable code |
| `<foreignObject>` | Contains HTML — not convertible to PPTX |
| `<iframe>` | Security: embedded document |
| `<animate>` | Not exportable to PPTX |
| `<animateTransform>` | Not exportable to PPTX |
| `<animateMotion>` | Not exportable to PPTX |
| `<set>` | SVG animation — not supported |

### 2.3 Conditionally Allowed Tags

These tags work in SVG but have limited or no PPTX equivalent:

| Tag | SVG Behaviour | PPTX Behaviour | Recommendation |
|-----|--------------|----------------|----------------|
| `<filter>` | Visual effects | Dropped on export | Use sparingly — for subtle shadows only |
| `<feGaussianBlur>` | Blur effect | Dropped | Keep `stdDeviation` ≤ 8 |
| `<feDropShadow>` | Drop shadow | Dropped (PPTX has native shadow) | Prefer native PPTX shadow post-export |
| `<feOffset>` | Offset for compositing | Dropped | Only in shadow filter chains |
| `<feFlood>` | Solid colour fill | Dropped | Only in filter chains |
| `<feComposite>` | Compositing | Dropped | Only in filter chains |
| `<feMerge>` | Layer merging | Dropped | Only in filter chains |
| `<feMergeNode>` | Merge source | Dropped | Only in filter chains |
| `<marker>` | Line endpoints | Not supported | Use explicit shapes instead |
| `<symbol>` | Reusable template | Use `<g>` + `<use>` | |
| `<switch>` | Conditional rendering | Not supported | Remove |

**Key rule:** If a visual effect is essential to the design, it must be
achievable with basic shapes. Filter effects are cosmetic enhancements only.

---

## 3. Attribute Rules

### 3.1 Banned Attributes (Hard Error)

Any attribute starting with `on` is banned:

```
onclick, onload, onmouseover, onmouseout, onmousedown, onmouseup,
onfocus, onblur, onchange, onerror, onsubmit
```

### 3.2 Colour Attributes

| Attribute | Format | Example |
|-----------|--------|---------|
| `fill` | 6-digit hex or `url(#id)` or `none` | `fill="#3B82F6"` |
| `stroke` | 6-digit hex or `none` | `stroke="#334155"` |
| `stop-color` | 6-digit hex | `stop-color="#0F172A"` |
| `fill-opacity` | 0.0–1.0 | `fill-opacity="0.15"` |
| `stroke-opacity` | 0.0–1.0 | `stroke-opacity="0.5"` |
| `stop-opacity` | 0.0–1.0 | `stop-opacity="0.7"` |
| `opacity` | 0.0–1.0 (whole element) | `opacity="0.8"` |

**Forbidden colour formats:**
- `rgb(r, g, b)` — not consistently handled in PPTX export
- `rgba(r, g, b, a)` — use `fill` + `fill-opacity` instead
- `hsl()` / `hsla()` — not supported
- Named colours (`red`, `blue`) — ambiguous, always use hex
- 3-digit hex (`#F00`) — always use 6-digit

### 3.3 Transform Attribute

The `transform` attribute is fully supported:

```xml
<g transform="translate(100, 50)">
<g transform="rotate(45, 640, 360)">
<g transform="scale(0.8)">
```

**Supported transform functions:**
- `translate(tx, ty)`
- `rotate(angle)` or `rotate(angle, cx, cy)`
- `scale(sx)` or `scale(sx, sy)`
- `skewX(angle)`, `skewY(angle)` (use sparingly)
- `matrix(a, b, c, d, e, f)` (last resort)

**PPTX export note:** Transforms are resolved during export. Complex
nested transforms may lose precision. Keep transforms simple.

### 3.4 Presentation Attributes vs. Style Attribute

**Prefer presentation attributes** over the `style` attribute:

```xml
<!-- GOOD: presentation attributes -->
<rect fill="#3B82F6" stroke="#1E293B" stroke-width="2" rx="12" />

<!-- AVOID: style attribute (works but harder to parse for export) -->
<rect style="fill:#3B82F6; stroke:#1E293B; stroke-width:2" rx="12" />
```

The `style` attribute is allowed but presentation attributes are preferred
because the PPTX exporter parses them more reliably.

---

## 4. Path Commands

### 4.1 Supported Path Commands

The `d` attribute of `<path>` supports:

| Command | Meaning | Example |
|---------|---------|---------|
| `M` / `m` | Move to | `M 100 200` |
| `L` / `l` | Line to | `L 300 200` |
| `H` / `h` | Horizontal line | `H 500` |
| `V` / `v` | Vertical line | `V 400` |
| `C` / `c` | Cubic Bézier | `C 100 100 200 200 300 100` |
| `S` / `s` | Smooth cubic | `S 400 200 500 100` |
| `Q` / `q` | Quadratic Bézier | `Q 200 100 300 200` |
| `T` / `t` | Smooth quadratic | `T 500 200` |
| `A` / `a` | Elliptical arc | `A 50 50 0 0 1 200 300` |
| `Z` / `z` | Close path | `Z` |

### 4.2 Path Best Practices

- Always start with `M` (absolute move).
- Close shapes with `Z` when appropriate.
- Keep path complexity reasonable — max ~50 commands per path.
- For simple shapes (rectangles, circles), prefer `<rect>` and `<circle>`.
- **PPTX export:** Paths are converted to DrawingML freeform shapes.
  Complex paths with many arc commands may lose precision.

### 4.3 Rounded Corner Alternatives

Instead of complex arc paths, prefer `<rect>` with `rx`:

```xml
<!-- Prefer this -->
<rect x="100" y="100" width="400" height="200" rx="16" fill="{surface}" />

<!-- Over this -->
<path d="M 116 100 H 484 Q 500 100 500 116 V 284 Q 500 300 484 300 H 116 Q 100 300 100 284 V 116 Q 100 100 116 100 Z" />
```

---

## 5. Clip Paths

### 5.1 Basic Usage

```xml
<defs>
  <clipPath id="clip-card">
    <rect x="80" y="140" width="520" height="400" rx="16" />
  </clipPath>
</defs>
<g clip-path="url(#clip-card)">
  <image href="photo.jpg" x="60" y="120" width="560" height="440"
         preserveAspectRatio="xMidYMid slice" />
</g>
```

### 5.2 PPTX Export Behaviour

Clip paths are preserved during export. The clip region becomes the shape's
fill area. Complex clip paths (multiple shapes, paths) may be simplified.

**Best practice:** Use simple rectangular or rounded-rectangular clip paths.

---

## 6. Text Rules

### 6.1 Text Element Structure

```xml
<text x="96" y="100"
      font-family="Aptos, Arial, sans-serif"
      font-size="44"
      font-weight="700"
      fill="#F1F5F9">
  Slide Title Text
</text>
```

**Required attributes:**
- `x`, `y` — position (baseline for text)
- `font-family` — must match spec lock
- `font-size` — integer, in pixels
- `fill` — text colour from palette

### 6.2 Multi-line Text

Use `<tspan>` with `dy` for line breaks:

```xml
<text x="96" y="180" font-family="{body_family}" font-size="24" fill="{body}">
  <tspan x="96" dy="0">First line</tspan>
  <tspan x="96" dy="32">Second line</tspan>
</text>
```

**Line height formula:** `dy = font-size × 1.3` (Latin) or `× 1.5` (CJK).

### 6.3 Text Anchoring

| Value | Behaviour |
|-------|-----------|
| `text-anchor="start"` | Left-aligned (default) |
| `text-anchor="middle"` | Centre-aligned |
| `text-anchor="end"` | Right-aligned |

Use `text-anchor="middle"` with `x="640"` for centred text.

### 6.4 PPTX Text Export

- Each `<text>` element becomes a text box in PPTX.
- `<tspan>` elements become text runs within the same text box.
- `font-weight="700"` → Bold.
- `font-style="italic"` → Italic.
- `text-decoration="underline"` → Underline.
- `letter-spacing` → Character spacing.

### 6.5 Font Safety

These fonts are safe for PowerPoint on all platforms:

**Western:**
Aptos, Arial, Calibri, Cambria, Consolas, Courier New, Georgia,
Segoe UI, Tahoma, Times New Roman, Trebuchet MS, Verdana

**CJK:**
Microsoft YaHei, SimSun, SimHei, KaiTi, FangSong,
Noto Sans SC, Noto Sans TC, Noto Sans JP, Noto Sans KR,
Source Han Sans SC

**Monospace:**
Consolas, Courier New, JetBrains Mono (if installed), Fira Code

If using a non-safe font, always provide a safe fallback in the font stack.

---

## 7. Image Rules

### 7.1 Image Element

```xml
<image href="images/photo.jpg" x="0" y="0" width="640" height="720"
       preserveAspectRatio="xMidYMid slice" />
```

**Required attributes:**
- `href` — relative path to image file (never absolute, never external URL)
- `x`, `y` — position
- `width`, `height` — display dimensions

### 7.2 Aspect Ratio Preservation

Always use `preserveAspectRatio` for images:

| Value | Behaviour |
|-------|-----------|
| `xMidYMid meet` | Fit inside (letterbox) — shows entire image |
| `xMidYMid slice` | Fill and crop — covers area, may crop edges |
| `none` | Stretch to fit — distorts image |

**Recommendation:** Use `slice` for background images, `meet` for figure/chart images.

### 7.3 Image File Formats

| Format | Supported | Best For |
|--------|-----------|----------|
| JPEG (.jpg) | ✅ | Photographs |
| PNG (.png) | ✅ | Graphics with transparency |
| SVG (.svg) | ⚠️ | Nested SVG — avoid for simplicity |
| WebP (.webp) | ⚠️ | Browser only — not PPTX safe |
| GIF (.gif) | ⚠️ | Static only — no animation |

**PPTX export:** Images are embedded into the PPTX file. Only JPEG and PNG
are guaranteed to work in all PowerPoint versions.

### 7.4 Image with Clip Path

To create non-rectangular image crops:

```xml
<defs>
  <clipPath id="img-clip">
    <circle cx="400" cy="360" r="200" />
  </clipPath>
</defs>
<image href="photo.jpg" x="200" y="160" width="400" height="400"
       clip-path="url(#img-clip)"
       preserveAspectRatio="xMidYMid slice" />
```

---

## 8. Gradient Rules

### 8.1 Linear Gradients

```xml
<defs>
  <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="{background}" />
    <stop offset="100%" stop-color="{surface}" stop-opacity="0.4" />
  </linearGradient>
</defs>
<rect fill="url(#bg-grad)" ... />
```

### 8.2 Radial Gradients

```xml
<defs>
  <radialGradient id="orb-glow" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="{accent}" stop-opacity="0.15" />
    <stop offset="100%" stop-color="{accent}" stop-opacity="0" />
  </radialGradient>
</defs>
<circle cx="200" cy="600" r="200" fill="url(#orb-glow)" />
```

### 8.3 Gradient Best Practices

- Maximum **10 stops** per gradient (PPTX limit).
- Use percentage coordinates (`x1="0%"`) for portability.
- Each gradient `id` must be unique within the file.
- **PPTX export:** Gradients are converted to native PowerPoint gradient fills.
  Complex multi-stop gradients are preserved.

### 8.4 Gradient ID Convention

Use descriptive, page-numbered IDs:
- `bg-grad-01` — background gradient, page 1
- `card-grad-01` — card gradient, page 1
- `orb-glow-01` — decorative orb, page 1

---

## 9. Filter Effects (Conditional)

### 9.1 Drop Shadow

```xml
<defs>
  <filter id="shadow-sm" x="-10%" y="-10%" width="120%" height="120%">
    <feDropShadow dx="0" dy="2" stdDeviation="3"
                  flood-color="#000000" flood-opacity="0.06" />
  </filter>
</defs>
<rect filter="url(#shadow-sm)" ... />
```

### 9.2 Filter Limits

| Parameter | Maximum | Reason |
|-----------|---------|--------|
| `stdDeviation` | 8 | Performance and visual quality |
| Filters per page | 3 | Performance |
| Filter chain length | 3 nodes | Complexity |

### 9.3 PPTX Export Behaviour

**Filters are DROPPED during PPTX export.** The content renders without
the filter effect. Design so that the slide looks good with OR without filters.

**Post-export alternative:** After PPTX generation, native PowerPoint
shadow/glow effects can be applied via python-pptx.

---

## 10. Coordinate System & Geometry

### 10.1 Coordinate Origin

- Origin (0, 0) is the top-left corner.
- X increases rightward, Y increases downward.
- All coordinates are in pixels (no units suffix needed in SVG attributes).

### 10.2 Safe Area Coordinates

| Zone | X Range | Y Range | Purpose |
|------|---------|---------|---------|
| Full canvas | 0–1280 | 0–720 | Background, decorative |
| Content safe | 80–1200 | 80–680 | All text and interactive content |
| Title zone | 80–1200 | 80–140 | Primary title area |
| Body zone | 80–1200 | 140–680 | Main content area |
| Footer zone | 0–1280 | 688–720 | Chrome footer bar |

### 10.3 Common Alignment Points

| Purpose | X | Y |
|---------|---|---|
| Left margin | 80 | — |
| Right margin | 1200 | — |
| Horizontal centre | 640 | — |
| Top margin | — | 80 |
| Bottom margin | — | 680 |
| Vertical centre | — | 360 |
| Footer top | — | 688 |

---

## 11. ID and Naming Conventions

### 11.1 Top-Level Group IDs

All top-level `<g>` elements must have an `id` attribute. Use this pattern:

```
{type}-{descriptor}-{page_number}
```

Examples: `content-title-03`, `decoration-orb-03`, `chrome-footer`

### 11.2 Defs Element IDs

```
{type}-{page_number}
```

Examples: `bg-grad-01`, `shadow-sm-01`, `clip-card-01`

### 11.3 Uniqueness Rule

Every `id` must be unique within a single SVG file.
IDs do NOT need to be unique across different SVG files.

---

## 12. File Naming

SVG output files follow this naming convention:

```
slide_01.svg
slide_02.svg
...
slide_NN.svg
```

Zero-padded two-digit page numbers. No spaces, no special characters.

---

## 13. Validation Summary

### Hard Errors (must fix — blocks export)

- Banned tags present (`script`, `foreignObject`, `animate`, etc.)
- Banned attributes present (`onclick`, `onload`, etc.)
- Missing `width`, `height`, or `viewBox` on root `<svg>`
- `viewBox` doesn't match `width`/`height`
- Empty `d` attribute on `<path>`
- Empty `points` attribute on `<polygon>`/`<polyline>`
- No semantic content groups (top-level `<g>` without `id`)
- Root element is not `<svg>`

### Warnings (should fix — may cause issues)

- Text overflow beyond canvas boundaries
- External `href` in `<use>` element (should be local `#id`)
- Non-hex colour format in `fill`/`stroke`
- Filter `stdDeviation` > 8
- More than 10 gradient stops
- Missing `preserveAspectRatio` on `<image>`

### Info (consider — quality improvement)

- Content page without imagery
- Same layout structure as previous page
- Same rhythm as previous 2 pages
- Title in identical position as previous page
