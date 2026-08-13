# Image-Layout Patterns Vocabulary

> **72+ composition patterns for AI-authored slide design.**
> Use this vocabulary when selecting image placements for each slide page.

---

## Primary Structures

### Container Layouts (19 patterns)

| # | Pattern | Description | Best For |
|---|---------|-------------|----------|
| 1 | `full-bleed` | Image covers entire 1280×720 canvas as background | Cover slides, section dividers, atmosphere |
| 2 | `full-bleed-overlay` | Full-bleed image + dark/gradient overlay for text readability | Cover with title, impactful stats |
| 3 | `left-half` | Image fills left 50% (0–640px), content on right | Feature showcase, product reveal |
| 4 | `right-half` | Image fills right 50% (640–1280px), content on left | Balanced text-image layout |
| 5 | `left-third` | Image fills left 33% (0–427px), content on right 67% | Data-heavy with visual anchor |
| 6 | `right-third` | Image fills right 33% (853–1280px), content on left 67% | Content-heavy with visual accent |
| 7 | `top-banner` | Image spans full width at top (0–360px), content below | Chapter opener, topic introduction |
| 8 | `bottom-banner` | Image spans full width at bottom (360–720px), content above | Summary with visual evidence |
| 9 | `center-hero` | Large centered image (300–500px wide) with text above/below | Product photo, key visual |
| 10 | `corner-accent-tl` | Small image (200×200px) in top-left corner | Icon-style decoration |
| 11 | `corner-accent-tr` | Small image (200×200px) in top-right corner | Logo, badge, diagram |
| 12 | `corner-accent-br` | Small image (200×200px) in bottom-right corner | Signature visual |
| 13 | `inset-card` | Image inside a rounded card (rx=16) with padding | Gallery item, case study |
| 14 | `floating-circle` | Circular clipped image floating in layout | Profile photo, avatar |
| 15 | `diagonal-split` | Diagonal line separates image and content areas | Dynamic, editorial feel |
| 16 | `l-shape` | Image fills an L-shaped region (top + left) | Complex content framing |
| 17 | `window-peek` | Image visible through a geometric cutout in colored surface | Reveal effect, curiosity |
| 18 | `strip-accent` | Narrow image strip (80px tall) as decorative band | Texture, pattern accent |
| 19 | `polaroid` | Image with white border + slight rotation + shadow | Casual, storytelling |

### Image-as-Canvas Overlays (8 patterns)

| # | Pattern | Description | Best For |
|---|---------|-------------|----------|
| 20 | `text-over-dark` | White text directly on darkened image | Bold statement slides |
| 21 | `gradient-fade-left` | Image fades to solid color on left for text | Title + atmosphere |
| 22 | `gradient-fade-right` | Image fades to solid color on right for text | Content + visual |
| 23 | `gradient-fade-bottom` | Image fades to solid color at bottom for text | Stat overlays |
| 24 | `frosted-card` | Semi-transparent card over image background | Key points on visual |
| 25 | `duotone` | Image in two-tone palette matching theme | Brand consistency |
| 26 | `color-wash` | Image tinted with theme accent at low opacity | Subtle texture |
| 27 | `vignette` | Image with dark edges focusing attention to center | Portrait, product focus |

### Multi-Image Compositions (10 patterns)

| # | Pattern | Description | Best For |
|---|---------|-------------|----------|
| 28 | `grid-2x1` | Two images side by side, equal width | Before/after, comparison |
| 29 | `grid-1x2` | Two images stacked vertically | Process steps |
| 30 | `grid-2x2` | Four images in 2×2 grid | Portfolio, gallery |
| 31 | `grid-3x1` | Three images in a row | Feature trio |
| 32 | `grid-1-2` | One large image + two small stacked | Hero + details |
| 33 | `grid-2-1` | Two small stacked + one large | Details + hero |
| 34 | `masonry` | Pinterest-style varied heights | Creative portfolio |
| 35 | `filmstrip` | Narrow horizontal strip of sequential images | Timeline, process |
| 36 | `carousel-peek` | Center image large, side images peeking | Feature spotlight |
| 37 | `scattered` | 3–5 images at slight angles, overlapping | Mood board, inspiration |

---

## Modifier Layers

### Non-Rectangular Crops (8 patterns)

| # | Pattern | Description |
|---|---------|-------------|
| 38 | `clip-circle` | Circular clip-path on image |
| 39 | `clip-rounded-rect` | Large border-radius (rx=24+) |
| 40 | `clip-hexagon` | Hexagonal clip-path |
| 41 | `clip-diamond` | 45° rotated square clip |
| 42 | `clip-arch` | Arch-shaped clip (rounded top, flat bottom) |
| 43 | `clip-blob` | Organic blob shape clip |
| 44 | `clip-triangle` | Triangular clip |
| 45 | `clip-custom-path` | SVG path-defined custom shape |

### Overlay Treatments (8 patterns)

| # | Pattern | Description |
|---|---------|-------------|
| 46 | `overlay-gradient-linear` | Linear gradient overlay (transparent→solid) |
| 47 | `overlay-gradient-radial` | Radial gradient overlay (center transparent) |
| 48 | `overlay-solid-tint` | Solid color at 30–60% opacity |
| 49 | `overlay-pattern-dots` | Dot pattern overlay for texture |
| 50 | `overlay-pattern-grid` | Grid line overlay for technical feel |
| 51 | `overlay-noise` | Subtle noise texture overlay |
| 52 | `overlay-glass` | Frosted glass effect (blur + white overlay) |
| 53 | `overlay-scanline` | Horizontal scanline effect |

### Texture & Atmosphere (8 patterns)

| # | Pattern | Description |
|---|---------|-------------|
| 54 | `texture-grain` | Film grain added to image |
| 55 | `texture-halftone` | Halftone dot pattern conversion |
| 56 | `atmosphere-bokeh` | Soft bokeh circles overlaid |
| 57 | `atmosphere-particles` | Floating particle effects |
| 58 | `atmosphere-glow` | Soft glow from edges or focal point |
| 59 | `atmosphere-rays` | Light ray effects from corner |
| 60 | `atmosphere-mist` | Misty/foggy gradient overlay |
| 61 | `atmosphere-geometric` | Abstract geometric shapes scattered |

### Special Techniques (11 patterns)

| # | Pattern | Description |
|---|---------|-------------|
| 62 | `cutout` | Subject extracted from background |
| 63 | `mockup-screen` | Image placed inside device screen (laptop/phone) |
| 64 | `mockup-frame` | Image in picture frame or poster |
| 65 | `shadow-elevation` | Image with strong drop shadow for depth |
| 66 | `border-accent` | Image with thick accent-color border |
| 67 | `border-double` | Image with double border (inner thin, outer thick) |
| 68 | `reflection` | Image with mirrored reflection below |
| 69 | `3d-perspective` | Image rotated in perspective (CSS-like transform) |
| 70 | `parallax-layers` | Multiple image layers suggesting depth |
| 71 | `split-reveal` | Image split into strips with gaps between |
| 72 | `mask-text` | Image visible only through large text shape |

---

## Combination Rules

1. **One Primary Structure** per slide — never combine two container layouts
2. **Up to 2 Modifier Layers** can stack on any primary structure
3. **Atmospheric effects** should match theme mood (corporate → minimal, creative → rich)
4. **Multi-image compositions** should NOT use overlay treatments (too busy)
5. **Full-bleed patterns** pair well with frosted-card or gradient-fade modifiers
6. **Container layouts** pair well with shadow-elevation and clip modifiers

---

## Rhythm-Pattern Mapping

| Page Rhythm | Recommended Patterns |
|-------------|---------------------|
| **anchor** | `full-bleed-overlay`, `center-hero`, `left-half`, `right-half`, `diagonal-split` |
| **breathing** | `full-bleed`, `corner-accent-*`, `strip-accent`, `floating-circle` |
| **dense** | `right-third`, `left-third`, `inset-card`, `grid-2x2`, `corner-accent-tr` |

---

## SVG Implementation Notes

- Use `<image>` tag with `href` attribute (not `xlink:href`) for forward compatibility
- Clip-paths: define in `<defs>` with `<clipPath id="...">`, apply with `clip-path="url(#...)"`
- Overlays: use `<rect>` with `fill-opacity` over the image
- Circle clips: `<circle cx="..." cy="..." r="..." />` inside `<clipPath>`
- Image sizing: use `preserveAspectRatio="xMidYMid slice"` for cover behavior
- Image sizing: use `preserveAspectRatio="xMidYMid meet"` for contain behavior
