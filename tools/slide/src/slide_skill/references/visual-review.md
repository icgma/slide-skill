# Visual Review Rubric

> **Purpose:** Self-check rubric for AI executors before declaring SVG pages complete.
> Run through this checklist after generating all slide SVGs for a deck.
> The automated quality gate (`svg-qa --quality`) covers items 1–3 programmatically;
> items 4–6 require visual judgment.

---

## 1. Design Consistency (automated)

| Check | Pass Criteria |
|-------|--------------|
| Palette compliance | Every `fill`/`stroke` hex matches the spec lock palette |
| Font compliance | All `font-family` values match spec lock typography |
| Chrome presence | Every page has left accent stripe + footer bar |
| Canvas dimensions | All pages are `1280×720` with matching viewBox |

**Fix:** Re-read `design_guide.md` §2 (Colour Palette) and §3 (Typography).

---

## 2. Visual Rhythm (automated + judgment)

| Check | Pass Criteria |
|-------|--------------|
| Rhythm assignment | Each page has `anchor`, `breathing`, or `dense` |
| No 3+ consecutive same | Three adjacent pages never share the same rhythm |
| Anchor slides are impactful | Cover/closing/key-metric pages feel visually heavy |
| Breathing slides have whitespace | Section dividers and light pages feel spacious |
| Dense slides are information-rich | Multi-item/table pages pack content efficiently |

**Fix:** Adjust element count, whitespace margins, or font sizes to match rhythm intent.

---

## 3. Layout Variety (automated + judgment)

| Check | Pass Criteria |
|-------|--------------|
| No 3+ identical layouts | Three consecutive pages never use the same group-id pattern |
| Template diversity | Deck uses ≥3 distinct layout types |
| Visual interest | Slides alternate between left-aligned, centered, and multi-column |

**Fix:** Swap middle slides in monotonous runs to different templates
(e.g., bullet-list → two-column, or metric-highlight → quote).

---

## 4. Image Integration (judgment)

| Check | Pass Criteria |
|-------|--------------|
| Content-to-image ratio | ≥30% of content slides contain `<image>` elements |
| Image placement | Images use layout patterns from `image-layout-patterns.md` |
| Aspect ratio | All images have `preserveAspectRatio` attribute |
| No placeholders | Every `<image>` `href` points to an actual file |

**Fix:** Add images on anchor/breathing slides using the 72+ layout patterns.
Use `image-layout-spec.md` for pixel-precise coordinates.

---

## 5. Typography Hierarchy (judgment)

| Check | Pass Criteria |
|-------|--------------|
| Size ramp consistency | Title sizes follow the size ramp from spec lock |
| Weight usage | Headings are `700`, body is `400`, captions are `400` |
| No orphan text | Every text element is within the safe area (x 80–1200, y 80–680) |
| CJK/Latin consistency | Mixed-language text uses appropriate font families |

**Fix:** Re-read `design_guide.md` §3 (Typography) and §4 (Canvas & Chrome).

---

## 6. Overall Composition (judgment)

| Check | Pass Criteria |
|-------|--------------|
| Visual flow | Deck tells a story: cover → content build-up → conclusion |
| Alignment grid | Elements snap to an invisible 80px grid |
| Negative space | No slide feels cramped; breathing room between elements |
| Color harmony | Accent color draws the eye to key elements, not distractions |

**Fix:** Step back and view all slides as a contact sheet. Adjust spacing,
alignment, and accent usage for overall visual coherence.

---

## Scoring Guide

| Score | Description |
|-------|-------------|
| 5/5 | Publication-ready. Zero automated issues, strong visual judgment. |
| 4/5 | Minor issues. A few info-level suggestions, no warnings or errors. |
| 3/5 | Acceptable. Some warnings present, rhythm or layout could improve. |
| 2/5 | Needs work. Multiple warnings, monotonous layouts, missing imagery. |
| 1/5 | Failing. Errors present, spec lock violated, fundamentally broken. |
