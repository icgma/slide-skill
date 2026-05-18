---
name: slide
description: "Use this skill when a user asks to create, read, edit, verify, or package a PowerPoint deck or any `.pptx`/slide output. The skill uses a local SVG-first pipeline that produces native editable PPTX objects. v2.0 introduces multi-role workflow (Strategist + Executor), 5 design themes, and visually rich SVG support (gradients, opacity, filters)."
---

# Slide Skill v2.0

## Quick Reference

| Task | Command |
|------|---------|
| End-to-end deck from source | `slide-skill quickstart <source.md> --name <name> --theme <theme>` |
| Create workspace | `slide-skill init <name> --format ppt169 --theme <theme>` |
| Convert source to Markdown | `slide-skill source-to-md <file> -o <project>/sources/source.md` |
| Create design spec + guide | `slide-skill spec <project> --source <source.md> --theme <theme>` |
| Generate AI authoring prompt | `slide-skill generate-guide <project> --source <source.md>` |
| Generate SVG (programmatic) | `slide-skill svg <project> --source <source.md>` |
| Run SVG QA | `slide-skill check-svg <project>` |
| Finalize SVG | `slide-skill finalize-svg <project>` |
| Export PPTX | `slide-skill export <project>` |
| Run QA | `slide-skill qa <project>` |
| Run strict QA | `slide-skill qa <project> --strict` |
| List themes | `slide-skill themes` |
| List formats | `slide-skill formats` |
| List competition templates | `slide-skill competitions` |
| Rehearse timing | `slide-skill rehearse <project>` |
| Generate notes draft | `slide-skill draft-notes <project>` |
| Narrate (TTS) | `slide-skill narrate <project> --engine edge-tts` |
| Template operations | Read `guides/editing.md` |

---

## Core Pipeline

```
source → Markdown → project workspace
  → spec (design_spec.md + spec_lock.json + design_guide.md)
  → svg_output/ (Executor writes SVG guided by design_guide.md)
  → SVG QA → svg_final/ → editable PPTX export → QA report
```

---

## Multi-Role Model

Slide Skill v2.0 uses a **Strategist → Executor** workflow for production decks:

### Strategist Role

The Strategist prepares all planning artifacts before any SVG is written.

**Responsibilities:**
1. Normalize source content: convert from PDF/DOCX/URL to clean Markdown
2. Choose a design theme (see `slide-skill themes`)
3. Run `slide-skill spec <project> --source <source.md> --theme <theme>` to write:
   - `design_spec.md` — human-readable visual direction
   - `spec_lock.json` — machine-readable palette, font, layout rhythm
   - `design_guide.md` — AI-facing per-layout specification with SVG examples
4. Run `slide-skill generate-guide <project> --source <source.md>` to write:
   - `svg_generation_prompt.md` — per-slide content breakdown and layout assignments

**Strategist must confirm before execution:**
- Content outline and slide count (recommended 6–14 slides)
- Theme choice from: `dark-tech` | `light-corporate` | `warm-editorial` | `data-forward` | `vibrant-startup`
- Canvas format: `ppt169` (default) | `ppt43` | `a4` | `square`
- Speaker notes required? (yes/no)
- Narration audio required? (yes/no)

### Executor Role

The Executor writes the SVG files, guided strictly by the planning artifacts.

**Before writing any SVG:**
1. Read `design_guide.md` in the project directory — contains palette, typography, layout examples
2. Read `svg_generation_prompt.md` — contains per-slide content and layout assignments
3. Read `spec_lock.json` — palette hex codes and font family

**SVG authoring rules:**
- Canvas is always **1280 × 720 px** (`width="1280" height="720" viewBox="0 0 1280 720"`)
- Every slide MUST include:
  - Left accent stripe: `<rect x="0" y="0" width="6" height="720" fill="{accent}" />`
  - Footer bar: `<rect x="0" y="688" width="1280" height="32" fill="{surface}" />`
- Every top-level `<g>` must have an `id` attribute
- Use `<defs>` for all gradients and filters
- Only use palette colours from `spec_lock.json` — no other colours
- Write exactly the slide count specified in `spec_lock.json`
- Place SVG files in `svg_output/` as `slide_01.svg`, `slide_02.svg`, …

---

## Design Themes

| Theme | Best For | Background | Accent |
|-------|----------|------------|--------|
| `dark-tech` | Engineering, SaaS, research | `#0F172A` | `#3B82F6` |
| `light-corporate` | Business, corporate | `#FFFFFF` | `#1D4ED8` |
| `warm-editorial` | Humanities, editorial | `#FDF6EE` | `#EA580C` |
| `data-forward` | Analytics, research | `#F1F5F9` | `#0284C7` |
| `vibrant-startup` | Startups, pitch decks | `#FFFFFF` | `#7C3AED` |

Run `slide-skill themes` for full details.

---

## SVG Writing Standards

### Allowed Tags
`rect` `circle` `ellipse` `line` `text` `tspan` `image` `path` `polygon` `polyline`
`g` `defs` `linearGradient` `radialGradient` `stop`
`filter` `feGaussianBlur` `feOffset` `feFlood` `feComposite` `feMerge` `feMergeNode`
`clipPath` `pattern` `use` `title` `desc`

### Banned Tags (hard error)
`script` `foreignObject` `iframe` `animate` `animateTransform` `set` `animateMotion`

### Banned Attributes (hard error)
All DOM event handlers: `onclick` `onload` `onmouseover` `onmouseout` and any `on*` attribute.

### Fully Permitted (v2.0 — previously restricted)
`opacity` `fill-opacity` `stroke-opacity` `transform` `class` `style`
Gradient `fill="url(#id)"` references (local only)
`<filter>` with `feGaussianBlur` (stdDeviation ≤ 8)

### Layout Templates

| Template | Use When |
|----------|----------|
| `cover` | Deck title / first slide |
| `section-divider` | Heading with no body text |
| `bullet-list` | 3–7 bullet points |
| `two-column` | Side-by-side comparison |
| `metric-highlight` | 2–4 large numbers / percentages |
| `quote` | Strong single quote |
| `closing` | Thank-you / CTA slide |

Full SVG examples for each template are in `design_guide.md` (generated per project).

---

## Required Discipline

1. Normalize source content before designing slides.
2. Always run `slide-skill spec` to write `spec_lock.json` and `design_guide.md` before SVG.
3. Executor must read `design_guide.md` before writing any SVG file.
4. SVG files must pass `slide-skill check-svg` before finalization.
5. Speaker notes go in `notes/total.md` using `## Slide N` sections.
6. Run `slide-skill finalize-svg` then export from `svg_final/`.
7. Run `slide-skill render-doctor` before visual QA.
8. Run `slide-skill qa <project> --strict` before declaring production completion.

---

## MiMo TTS Engine

```bash
# Use a pre-built voice
slide-skill narrate <project> --engine mimo --voice 冰糖

# Voice cloning from an audio sample
slide-skill narrate <project> --engine mimo --voice-clone /path/to/sample.mp3

# Voice design via text description
slide-skill narrate <project> --engine mimo --voice-design "gentle, young female voice"
```

Requires: `pip install slide-skill[mimo]` and `MIMO_API_KEY` env var.

---

## Student Competition Toolkit

| Command | Description |
|---------|-------------|
| `slide-skill competitions` | List templates |
| `slide-skill init <name> --competition <type>` | Initialize competition project |
| `slide-skill rehearse <project>` | Timing analysis |
| `slide-skill draft-notes <project>` | Generate notes draft |

Supported: `internet-plus` `challenge-cup` `math-modeling` `innovation-training` `thesis-defense` `course-presentation`

---

## Guides

- `guides/intake.md` — source conversion and project workspace
- `guides/svg-pipeline.md` — design guide, SVG rules, layout templates, finalization
- `guides/export.md` — native PPTX export and validation
- `guides/editing.md` — template inspection and safe operations
- `guides/qa.md` — QA loop and artifact expectations

---

## Output Contract

For every generated deck, report:

- Project path
- Exported `.pptx` path
- Theme used
- Embedded notes status (if notes were requested)
- QA report path
- Known limitations (unsupported SVG constructs, non-native fallback objects)
