# Executor Style: General / Creative

> **Use this style for:** Business presentations, pitch decks, marketing,
> product overviews, conference talks, creative portfolios.

---

## Visual Philosophy

The **General** style prioritises visual impact and audience engagement.
Slides should feel modern, polished, and visually rich — not corporate-flat.

**Guiding principle:** Every slide should have at least one element that
makes the viewer pause and pay attention.

---

## Composition Strategies

### Hero Compositions (for `anchor` rhythm pages)

- **Full-bleed gradient background** with centred hero text.
- **Large metric numbers** (72–96px) with subtle icon or accent tint.
- **Image-as-canvas** with semi-transparent overlay panel for text readability.
- **Split composition:** image left (50%), text right (50%) with accent divider.

### Content Compositions (for `anchor` / `dense` rhythm pages)

- **Card grids** (2-col, 3-col, 2×2) with accent-top cards.
- **Icon + text pairs** arranged in a grid or horizontal row.
- **Timeline/process flow** with connected accent-coloured nodes.
- **Comparison tables** with alternating row backgrounds.
- **KPI dashboard** — 3–4 large numbers in accent cards.

### Breathing Compositions (for `breathing` rhythm pages)

- **Single powerful quote** centred with large accent quotation mark.
- **Section divider** with gradient band and bold heading.
- **Image-only page** with overlay text (title + one sentence).
- **Minimal stat** — one number, one label, maximum whitespace.

---

## Image Integration

Images elevate visual quality dramatically. Guidelines:

1. **Aim for 50%+ content pages** with imagery.
2. **Full-bleed images** work as backgrounds with overlay panels.
3. **Contained images** in cards should have consistent aspect ratios.
4. **Never stretch** — use `preserveAspectRatio="xMidYMid slice"`.
5. **Alt-text:** Add `<title>` elements inside image groups for accessibility.

### Image-Text Overlay Pattern

```xml
<!-- Image as background canvas -->
<image href="image.jpg" x="0" y="0" width="1280" height="720"
       preserveAspectRatio="xMidYMid slice" />
<!-- Dark overlay for text readability -->
<rect x="0" y="0" width="1280" height="720"
      fill="{background}" fill-opacity="0.6" />
<!-- Text on top -->
<text x="640" y="360" font-family="{title_family}" font-size="52"
      fill="{text}" text-anchor="middle">HEADING</text>
```

---

## Colour Usage Tips

| Situation | Colour Role |
|-----------|-------------|
| Primary headings | `text` |
| Body copy | `body` / `text_secondary` |
| Call-to-action elements | `accent` |
| Supporting accents (chart series 2) | `secondary_accent` |
| Card backgrounds | `surface` |
| Alternating row backgrounds | `bg_secondary` |
| Subtle highlight behind text | `accent_tint` |
| Divider lines | `border` |
| De-emphasised labels | `text_tertiary` |

---

## Typography Tips

- **Hero titles:** 60–72px, weight 700, centred.
- **Body text:** 22–28px, weight 400, left-aligned.
- **Overlines:** 14px, weight 600, uppercase, in `accent` colour.
- **Captions:** 16px, weight 400, in `text_secondary` colour.

### The Overline Pattern

A small label above the main title adds visual sophistication:

```xml
<text x="96" y="78" font-family="{body_family}" font-size="14"
      font-weight="600" fill="{accent}" letter-spacing="2">
  SECTION TOPIC
</text>
<text x="96" y="110" font-family="{title_family}" font-size="44"
      font-weight="700" fill="{text}">
  Main Slide Title
</text>
```

---

## Decorative Elements

- Use **gradient orbs** (2–3 per slide max) for depth.
- Use **accent bars** to create visual rhythm.
- Use **rounded rectangles** (rx=12–20) for modern feel.
- Avoid sharp corners on cards and containers.
- Subtle **dot-grid patterns** on `breathing` pages add texture.

---

## Don'ts

- Don't make every page look the same — vary composition aggressively.
- Don't use more than 3 font sizes per page.
- Don't crowd text — leave breathing room between elements.
- Don't use drop shadows heavier than `stdDeviation="4"`.
- Don't place decorative elements over text.
