# Executor Style: Academic / Formal

> **Use this style for:** Research presentations, conference papers,
> thesis defences, university lectures, scholarly seminars, grant proposals.

---

## Visual Philosophy

The **Academic** style prioritises clarity, precision, and information density.
Slides should feel authoritative and professional — clean rather than flashy.

**Guiding principle:** The content is the hero. Visual design serves readability,
never competes with information.

---

## Layout Preferences

### Structure-First Design

1. **Title + content** — clear top-down hierarchy on every page.
2. **Consistent title position** — top-left for all content pages.
3. **Data-heavy layouts** — tables, charts, and multi-item lists are expected.
4. **Generous line height** — CJK and mixed-language text needs 1.5× line-height.

### Academic Page Types

| Page Type | Rhythm | Layout Strategy |
|-----------|--------|----------------|
| Title slide | anchor | Centred, institution name, date |
| Outline/TOC | breathing | Numbered list, clean hierarchy |
| Literature review | dense | Bullet points with citations |
| Methodology | anchor | Flowchart or process diagram |
| Results/data | dense | Table + chart side by side |
| Discussion | anchor | Key findings as numbered cards |
| Conclusion | breathing | 3–5 takeaway bullet points |
| References | dense | Compact citation list, small font |
| Q&A / Thank you | breathing | Minimal text, centred |

---

## Typography Rules

- **Titles:** 40–52px, weight 700. Prefer clarity over size.
- **Body text:** 22–26px, weight 400. Ensure readability at distance.
- **Citations:** 14–16px, weight 400, in `text_tertiary` colour.
- **Data labels:** 14–18px, weight 400.
- **Footnotes:** 12px, in `muted` colour.

### Citation Formatting

Place in-text references as superscript-style small text:

```xml
<text x="96" y="180" font-family="{body_family}" font-size="24" fill="{body}">
  <tspan>Research shows significant effects (Smith et al., 2024)</tspan>
</text>
```

Or as footnotes at the bottom of the content area:

```xml
<text x="96" y="660" font-family="{body_family}" font-size="12" fill="{muted}">
  [1] Smith et al. (2024). Title of Paper. Journal Name, 12(3), 45-67.
</text>
```

---

## Colour Usage

- **Restrained palette usage** — academic slides should feel muted.
- Use `text` for headings, `body` for content.
- Use `accent` sparingly — for emphasis, not decoration.
- Data visualisation colours: `accent`, `secondary_accent`, `muted` as series 1/2/3.
- Avoid `accent_tint` backgrounds on data pages (distracting).

---

## Table Design

Tables are central to academic presentations:

```xml
<!-- Table header -->
<rect x="96" y="150" width="1080" height="36" fill="{surface}" />
<text x="120" y="175" font-family="{body_family}" font-size="16"
      font-weight="600" fill="{text}">Variable</text>

<!-- Alternating rows -->
<rect x="96" y="186" width="1080" height="32" fill="{bg_secondary}" />
<rect x="96" y="218" width="1080" height="32" fill="none" />
```

- Header row: `surface` background, bold text.
- Alternating rows: `bg_secondary` / transparent.
- Cell text: 16–18px, left-aligned for text, right-aligned for numbers.
- Border lines: 1px `border` colour for column separators.

---

## Decorative Restraint

- **Minimal orbs/gradients** — 0–1 per slide maximum.
- **No dot-grid patterns** — clean backgrounds only.
- **Simple accent bars** — thin underlines beneath titles only.
- **No image-as-canvas** overlays — images should be contained in cards or figures.
- **Figure labels:** Always add `Figure 1.`, `Table 1.` captions below charts/images.

---

## Don'ts for Academic Style

- Don't use large decorative gradient orbs.
- Don't centre body text — always left-align.
- Don't use more than 3 levels of heading hierarchy per page.
- Don't omit page numbers (essential for Q&A reference).
- Don't use novelty fonts — stick to the spec lock typography strictly.
- Don't crowd slides — maximum 8 bullet points or 6 table rows per page.
