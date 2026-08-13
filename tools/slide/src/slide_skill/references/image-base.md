# Image Generation Base Reference

> **Best practices for AI image generation in slide design.**
> Use this reference when generating images for slide pages.

---

## Core Principles

1. **Specify palette explicitly** — Always include hex colors from the spec lock in the prompt
2. **Match rendering style** — Choose a style that fits the deck's visual language
3. **Resolution matters** — Request 1024×1024 minimum, crop to needed aspect ratio
4. **Describe composition** — Specify where the subject is, what the background is, and lighting
5. **Avoid text in images** — AI-generated text is unreliable; overlay text in SVG instead

---

## Prompt Template

```
{rendering_style} illustration of {subject}.
{mood} atmosphere with {lighting} lighting.
Color palette: {primary_color}, {secondary_color}, {accent_color}.
{background_description}.
No text, no watermarks, no borders.
{aspect_ratio_hint}
```

### Example

```
Flat vector illustration of a data analytics dashboard on a laptop screen.
Professional atmosphere with soft studio lighting.
Color palette: #0D1117, #00D4FF, #1A1F2E.
Dark gradient background fading from navy to charcoal.
No text, no watermarks, no borders.
Landscape orientation, clean negative space on right side.
```

---

## Rendering Styles

| Style | Use For | Key Prompt Words |
|-------|---------|-----------------|
| `flat` | Business, corporate | "flat vector, clean lines, solid colors, minimal shadows" |
| `3d-render` | Product, tech | "3D render, soft shadows, studio lighting, glossy" |
| `isometric` | Process, architecture | "isometric view, 30-degree angle, precise geometry" |
| `glassmorphism` | Modern UI, tech | "frosted glass, translucent panels, blur, light refraction" |
| `editorial` | Magazine, story | "editorial photography style, cinematic, rule of thirds" |
| `watercolor` | Creative, art | "watercolor texture, soft edges, bleeding colors" |
| `line-art` | Technical, minimal | "line drawing, thin strokes, black and white, clean" |
| `gradient-abstract` | Background, mood | "abstract gradient, smooth color transitions, organic shapes" |
| `duotone` | Bold, contrast | "duotone, two-color, high contrast, graphic" |
| `photographic` | Real-world, case study | "photorealistic, natural lighting, shallow depth of field" |
| `paper-cutout` | Playful, education | "paper cutout style, layered, soft shadows between layers" |
| `neon-glow` | Nightlife, tech, gaming | "neon glow, dark background, vibrant colors, reflections" |

---

## Palette-to-Prompt Mapping

When generating images for a themed deck, derive the image prompt colors from the spec lock:

| Spec Lock Role | Image Prompt Usage |
|----------------|-------------------|
| `background` | Image background color / dominant tone |
| `accent` | Subject highlight, key object color |
| `secondary_accent` | Supporting element color |
| `surface` | Surrounding environment tone |
| `text` | Any high-contrast elements |

---

## Composition Guidelines

### For Background Images (full-bleed patterns)
- Request **wide landscape** orientation
- Include **negative space** for text overlay
- Use **gradient or blur** on edges for text readability
- Specify **low detail** in areas where text will go

### For Hero/Feature Images (center-hero, inset-card)
- Request **square** or **portrait** orientation
- Include **clean edges** for easy integration
- Specify **solid or transparent** background
- Focus subject in **center** of frame

### For Gallery/Grid Images
- Request **consistent style** across all images in set
- Use **same prompt prefix** for style consistency
- Specify **similar lighting and color temperature**
- Keep complexity **moderate** — grid images are small

---

## Size Recommendations

| Layout Pattern | Recommended Size | Aspect |
|---------------|-----------------|--------|
| `full-bleed` | 1280×720 or 2560×1440 | 16:9 |
| `left-half` / `right-half` | 640×720 or 1280×1440 | ~9:10 |
| `center-hero` | 1024×1024 | 1:1 |
| `inset-card` | 512×512 | 1:1 |
| `corner-accent` | 256×256 | 1:1 |
| `top-banner` | 1280×360 | ~3.5:1 |
| `grid-2x2` (each) | 512×512 | 1:1 |

---

## Integration Checklist

- [ ] Image prompt includes spec lock colors
- [ ] Rendering style matches deck mood
- [ ] No text baked into image
- [ ] Image saved to `images/` directory in project
- [ ] Image metadata recorded in `images_meta.json`
- [ ] `<image>` tag in SVG uses `href` (not `xlink:href`)
- [ ] `preserveAspectRatio` set correctly for layout pattern
