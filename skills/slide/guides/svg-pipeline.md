# Guide: SVG Pipeline (v2.0)

The SVG pipeline is the heart of slide-skill. It converts source content into visually
rich SVG pages that are then exported to editable PPTX.

---

## Step 1: Create Design Spec and Guide

```bash
slide-skill spec <project> --source <project>/sources/source.md --theme dark-tech
```

This writes three files into the project directory:

| File | Purpose |
|------|---------|
| `design_spec.md` | Human-readable visual direction |
| `spec_lock.json` | Machine-readable palette, font, layout rhythm |
| `design_guide.md` | AI-facing per-layout spec with full SVG examples |

### Available Themes

| Theme | Background | Accent | Best for |
|-------|------------|--------|----------|
| `dark-tech` | `#0F172A` | `#3B82F6` | Engineering, SaaS |
| `light-corporate` | `#FFFFFF` | `#1D4ED8` | Business, corporate |
| `warm-editorial` | `#FDF6EE` | `#EA580C` | Humanities, editorial |
| `data-forward` | `#F1F5F9` | `#0284C7` | Analytics, research |
| `vibrant-startup` | `#FFFFFF` | `#7C3AED` | Startups, pitch decks |

---

## Step 2: Generate SVG Authoring Prompt (AI Executor workflow)

```bash
slide-skill generate-guide <project> --source <project>/sources/source.md
```

Writes `svg_generation_prompt.md` — a per-slide content breakdown that tells the
Executor role what to write for each slide: content, layout template, and file name.

**After running this command, the Executor must:**
1. Read `design_guide.md`
2. Read `svg_generation_prompt.md`
3. Write each `svg_output/slide_NN.svg` guided by those documents

---

## Step 3: Generate SVGs (programmatic fallback)

```bash
slide-skill svg <project> --source <project>/sources/source.md
```

Generates SVG pages programmatically. Layout is automatically selected:

| Layout | Triggers |
|--------|---------|
| `section-divider` | No body text |
| `bullet-list` | 3+ bullet points (`- item`) |
| `metric-highlight` | Contains numbers with `%` or `万`/`亿` |
| `two-column` | Body contains `vs` or `\|` separator |
| `default` | Everything else |

---

## Canvas Specification

- **Size**: 1280 × 720 px (16:9)
- **viewBox**: always `0 0 1280 720`
- **Content safe area**: x 80–1200 px, y 80–680 px
- **Left accent stripe**: `<rect x="0" y="0" width="6" height="720">` in accent colour
- **Footer bar**: `<rect x="0" y="688" width="1280" height="32">` in surface colour

---

## SVG Authoring Rules (v2.0)

### ALLOWED tags
```
rect circle ellipse line text tspan image path polygon polyline
g defs linearGradient radialGradient stop
filter feGaussianBlur feOffset feFlood feComposite feMerge feMergeNode
clipPath pattern use title desc
```

### BANNED tags (hard error)
```
script foreignObject iframe animate animateTransform set animateMotion
```

### BANNED attributes (hard error)
```
onclick onload onmouseover onmouseout onmousedown onmouseup onfocus onblur (any on* handler)
```

### ALLOWED (v2.0 — no longer restricted)
```
opacity fill-opacity stroke-opacity transform class style
fill="url(#local-id)"  (gradients/patterns, local references only)
```

---

## Typography Rules

| Element | font-size | font-weight |
|---------|-----------|-------------|
| Main title (≤15 chars) | 56–64px | 700 |
| Main title (16–25 chars) | 44–48px | 700 |
| Main title (26+ chars) | 36–40px | 700 |
| Section heading | 48–56px | 700 |
| Body / bullets | 18–22px | 400 |
| Metrics | 56–80px | 700 |
| Footer | 12px | 400 |

Bullet points: use a separate `<text>` element per bullet with `&#x2022;` marker in accent colour.

---

## Gradient Best Practices

```xml
<defs>
  <!-- Linear gradient for panel fill -->
  <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#0F172A" />
    <stop offset="100%" stop-color="#1E293B" />
  </linearGradient>

  <!-- Radial gradient for hero slide -->
  <radialGradient id="hero-grad" cx="50%" cy="50%" r="70%">
    <stop offset="0%" stop-color="#1E293B" />
    <stop offset="100%" stop-color="#0F172A" />
  </radialGradient>

  <!-- Drop shadow filter -->
  <filter id="shadow" x="-5%" y="-5%" width="110%" height="120%">
    <feGaussianBlur stdDeviation="4" />
    <feOffset dx="0" dy="4" />
    <feComposite in2="SourceGraphic" />
  </filter>
</defs>

<!-- Reference a gradient -->
<rect x="80" y="140" width="1120" height="440" rx="16" fill="url(#bg-grad)" />

<!-- Reference a filter -->
<rect x="80" y="140" width="1120" height="440" rx="16"
      fill="#1E293B" filter="url(#shadow)" />
```

Rules:
- All defs must be inside `<defs>` at the top of the SVG
- Gradient IDs must be unique per file (use slide number suffix: `bg-grad-01`)
- Only local `#id` references in `fill`/`stroke` — no external URLs
- `stdDeviation` ≤ 8 for blur filters

---

## Required Group Structure

```xml
<svg width="1280" height="720" viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg">
  <defs><!-- gradients / filters --></defs>
  <g id="background"><!-- full-bleed background rect --></g>
  <g id="chrome-stripe"><!-- left accent stripe --></g>
  <g id="content-title-NN"><!-- title text + underline --></g>
  <g id="content-body-NN"><!-- body content --></g>
  <g id="chrome-footer"><!-- footer bar + page number --></g>
</svg>
```

Every top-level `<g>` must have an `id`. Use `NN` = zero-padded slide number.

---

## Step 4: Run SVG Quality Gate

```bash
slide-skill check-svg <project>
```

Checks:
- Root is `<svg>` with `width`, `height`, `viewBox`
- No banned tags (script, foreignObject, animate*, set, iframe)
- No `on*` event-handler attributes
- Non-empty `d` on `<path>`, non-empty `points` on `<polygon>`/`<polyline>`
- At least one semantic top-level `<g id="...">` content group

Reports as `qa/SVG-QA.md`. Warnings (external `use` hrefs) are non-blocking.

---

## Step 5: Finalize

```bash
slide-skill finalize-svg <project>
```

Copies validated `svg_output/*.svg` to `svg_final/`. Only run after `check-svg` passes.
